import uuid
from datetime import datetime
from decimal import Decimal

from flask import jsonify, request, session
from sqlalchemy import func

from auth.utils import login_required, permission_required
from extensions import db
from models import (WorkOrder, WorkOrderLineItem, Customer,
                    ServiceCatalog, Product, User, Agency, InventoryTransaction)
from utils.service_utils import deduct_inventory_for_work_order

from . import service_bp


def generate_job_number(agency_id):
    """Generates a unique job number for a new work order."""
    today_str = datetime.utcnow().strftime('%Y%m')
    prefix = f"WO-{today_str}-"
    
    last_job = WorkOrder.query.filter(
        WorkOrder.job_number.like(f"{prefix}%"),
        WorkOrder.agency_id == agency_id
    ).order_by(WorkOrder.job_number.desc()).first()
    
    if last_job:
        last_seq = int(last_job.job_number.split('-')[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1
        
    return f"{prefix}{new_seq:04d}"


@service_bp.route('/api/service/jobs', methods=['GET'])
@permission_required(roles=['service_manager', 'service_advisor', 'technician'])
def list_work_orders(current_agency_id=None):
    """List all work orders with filters."""
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    query = WorkOrder.query.join(Customer)

    # Agency-based filtering
    if user_role != 'super_admin':
        query = query.filter(WorkOrder.agency_id == current_agency_id)
    
    # Technician can only see their assigned jobs
    if user_role == 'technician':
        query = query.filter(WorkOrder.assigned_technician_id == user_id)

    # Apply filters from query parameters
    if 'status' in request.args:
        query = query.filter(WorkOrder.status == request.args['status'])
    if 'customer_id' in request.args:
        query = query.filter(WorkOrder.customer_id == request.args['customer_id'])
    # vehicle filtering removed; work orders are linked to customer only

    page = request.args.get('page', 1, type=int)
    per_page = 20

    paginated_orders = query.order_by(WorkOrder.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    results = [{
        'id': wo.id,
        'job_number': wo.job_number,
        'customer_name': wo.customer.name,
    # Vehicle removed: no direct vehicle data stored on work orders
    'vehicle': '',
        'status': wo.status,
        'estimated_cost': float(wo.estimated_cost or 0),
        'actual_cost': float(wo.actual_cost or 0),
        'created_at': wo.created_at.isoformat()
    } for wo in paginated_orders.items]

    return jsonify({
        'work_orders': results,
        'total_pages': paginated_orders.pages,
        'current_page': paginated_orders.page,
        'total_items': paginated_orders.total
    })


@service_bp.route('/api/service/jobs', methods=['POST'])
@permission_required(roles=['service_manager', 'service_advisor'])
def create_work_order(current_agency_id=None):
    """Create a new work order."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON payload'}), 400

    customer_id = data.get('customer_id')
    if not customer_id:
        return jsonify({'error': 'customer_id is required'}), 400

    try:
        job_number = generate_job_number(current_agency_id)
        
        work_order = WorkOrder(
            job_number=job_number,
            agency_id=current_agency_id,
            customer_id=customer_id,
            assigned_technician_id=data.get('assigned_technician_id'),
            estimated_cost=Decimal(data.get('estimated_cost', 0)),
            status='Estimate',
            created_by=session.get('user_id')
        )
        db.session.add(work_order)
        db.session.flush() # Get work_order.id for line items

        total_cost = Decimal('0.0')

        # Add services
        for item in data.get('services', []):
            service = ServiceCatalog.query.get(item['service_id'])
            if service:
                quantity = Decimal(item.get('quantity', 1))
                unit_cost = service.default_price
                line_total = quantity * unit_cost
                total_cost += line_total
                
                line_item = WorkOrderLineItem(
                    work_order_id=work_order.id,
                    line_type='service',
                    description=service.name,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    total_cost=line_total,
                    service_id=service.id
                )
                db.session.add(line_item)

        # Add materials
        for item in data.get('materials', []):
            product = Product.query.get(item['product_id'])
            if product:
                quantity = Decimal(item.get('quantity', 1))
                unit_cost = Decimal(item.get('unit_cost', product.buy_price or 0))
                line_total = quantity * unit_cost
                total_cost += line_total

                line_item = WorkOrderLineItem(
                    work_order_id=work_order.id,
                    line_type='material',
                    description=product.name,
                    quantity=quantity,
                    unit_cost=unit_cost,
                    total_cost=line_total,
                    product_id=product.id
                )
                db.session.add(line_item)

        work_order.estimated_cost = total_cost
        db.session.commit()

        return jsonify({
            'message': 'Work order created successfully',
            'job_id': work_order.id,
            'job_number': work_order.job_number
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500


@service_bp.route('/api/service/jobs/<int:job_id>', methods=['GET'])
@permission_required(roles=['service_manager', 'service_advisor', 'technician'])
def get_work_order(job_id, current_agency_id=None):
    """Fetch full details of a single work order."""
    query = WorkOrder.query.filter_by(id=job_id)
    if session.get('role') != 'super_admin':
        query = query.filter_by(agency_id=current_agency_id)
    
    work_order = query.first_or_404()

    # Vehicle removed: respond with no vehicle data
    response = {
        'id': work_order.id,
        'job_number': work_order.job_number,
        'status': work_order.status,
        'customer': {'id': work_order.customer.id, 'name': work_order.customer.name},
    'vehicle': None,
        'assigned_technician': {'id': work_order.assigned_technician.id, 'name': work_order.assigned_technician.full_name} if work_order.assigned_technician else None,
        'line_items': [{
            'id': item.id,
            'line_type': item.line_type,
            'description': item.description,
            'quantity': float(item.quantity),
            'unit_cost': float(item.unit_cost),
            'total_cost': float(item.total_cost),
            'product_id': item.product_id,
            'service_id': item.service_id
        } for item in work_order.line_items],
        'estimated_cost': float(work_order.estimated_cost or 0),
        'actual_cost': float(work_order.actual_cost or 0),
        'created_at': work_order.created_at.isoformat(),
        'completed_at': work_order.completed_at.isoformat() if work_order.completed_at else None,
    }
    return jsonify(response)


@service_bp.route('/api/service/jobs/<int:job_id>', methods=['PATCH'])
@permission_required(roles=['service_manager', 'service_advisor', 'technician'])
def update_work_order(job_id, current_agency_id=None):
    """Update job status, assigned technician, or costs."""
    query = WorkOrder.query.filter_by(id=job_id)
    if session.get('role') != 'super_admin':
        query = query.filter_by(agency_id=current_agency_id)
    
    work_order = query.first_or_404()
    data = request.get_json()

    if 'status' in data:
        work_order.status = data['status']
    if 'assigned_technician_id' in data:
        work_order.assigned_technician_id = data['assigned_technician_id']
    if 'actual_cost' in data:
        work_order.actual_cost = Decimal(data['actual_cost'])
    
    # Add logic here to update line items if needed

    db.session.commit()
    return jsonify({'message': 'Work order updated successfully'})


@service_bp.route('/api/service/jobs/<int:job_id>/finalize', methods=['POST'])
@permission_required(roles=['service_manager', 'service_advisor'])
def finalize_work_order(job_id, current_agency_id=None):
    """
    Finalize a work order: mark as completed and deduct material inventory.
    
    Request body (optional):
    {
        'actual_cost': 1200.50,  # Final cost
        'consumed_materials': [  # Override consumed quantities
            {'line_item_id': 5, 'consumed_quantity': 2.5}
        ]
    }
    
    Returns:
        {
            'success': bool,
            'message': str,
            'work_order': {...},
            'inventory_deduction': {...}
        }
    """
    try:
        query = WorkOrder.query.filter_by(id=job_id)
        if session.get('role') != 'super_admin':
            query = query.filter_by(agency_id=current_agency_id)
        
        work_order = query.first_or_404()
        
        # Check if already completed or cancelled
        if work_order.status in ['Completed', 'Delivered', 'Cancelled']:
            return jsonify({
                'success': False,
                'error': f'Cannot finalize a work order that is already {work_order.status}'
            }), 400
        
        data = request.get_json() or {}
        
        # Update consumed quantities if provided
        if 'consumed_materials' in data:
            for consumed_item in data['consumed_materials']:
                line_item_id = consumed_item.get('line_item_id')
                consumed_qty = consumed_item.get('consumed_quantity')
                
                if line_item_id and consumed_qty is not None:
                    line_item = WorkOrderLineItem.query.filter_by(
                        id=line_item_id,
                        work_order_id=job_id
                    ).first()
                    
                    if line_item and line_item.line_type == 'material':
                        line_item.consumed_quantity = Decimal(str(consumed_qty))
        
        # Update actual cost if provided
        if 'actual_cost' in data:
            work_order.actual_cost = Decimal(str(data['actual_cost']))
        
        # Mark as completed
        work_order.status = 'Completed'
        work_order.completed_at = datetime.utcnow()
        
        db.session.flush()  # Flush to ensure line items are updated
        
        # Deduct inventory for material items
        inventory_result = deduct_inventory_for_work_order(work_order, session.get('user_id'))
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Work order finalized successfully',
            'work_order': {
                'id': work_order.id,
                'job_number': work_order.job_number,
                'status': work_order.status,
                'completed_at': work_order.completed_at.isoformat(),
                'actual_cost': float(work_order.actual_cost or 0)
            },
            'inventory_deduction': inventory_result
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': f'Failed to finalize work order: {str(e)}'
        }), 500


@service_bp.route('/api/service/jobs/<int:job_id>/inventory-consumption', methods=['GET'])
@permission_required(roles=['service_manager', 'service_advisor', 'store_manager', 'technician'])
def get_work_order_inventory_consumption(job_id, current_agency_id=None):
    """
    Get inventory consumption details and transactions for a work order.
    
    Returns:
        {
            'work_order_id': int,
            'job_number': str,
            'material_items': [
                {
                    'line_item_id': int,
                    'product_id': int,
                    'product_name': str,
                    'estimated_quantity': float,
                    'consumed_quantity': float,
                    'unit_cost': float,
                    'total_cost': float,
                    'is_inventory_deducted': bool,
                    'inventory_transactions': [
                        {
                            'transaction_id': int,
                            'transaction_type': str,
                            'quantity_change': int,
                            'quantity_before': int,
                            'quantity_after': int,
                            'created_at': str
                        }
                    ]
                }
            ]
        }
    """
    try:
        query = WorkOrder.query.filter_by(id=job_id)
        if session.get('role') != 'super_admin':
            query = query.filter_by(agency_id=current_agency_id)
        
        work_order = query.first_or_404()
        
        # Get all material items
        material_items = WorkOrderLineItem.query.filter_by(
            work_order_id=job_id,
            line_type='material'
        ).all()
        
        items_data = []
        for line_item in material_items:
            # Get linked inventory transactions
            transactions = InventoryTransaction.query.filter_by(
                work_order_line_item_id=line_item.id
            ).order_by(InventoryTransaction.created_at.desc()).all()
            
            item_data = {
                'line_item_id': line_item.id,
                'product_id': line_item.product_id,
                'product_name': line_item.product.name if line_item.product else 'Unknown',
                'estimated_quantity': float(line_item.quantity),
                'consumed_quantity': float(line_item.consumed_quantity or 0),
                'unit_cost': float(line_item.unit_cost),
                'total_cost': float(line_item.total_cost),
                'is_inventory_deducted': line_item.is_inventory_deducted,
                'inventory_transactions': [{
                    'transaction_id': t.id,
                    'transaction_type': t.transaction_type,
                    'quantity_change': t.quantity_change,
                    'quantity_before': t.quantity_before,
                    'quantity_after': t.quantity_after,
                    'unit_cost': float(t.unit_cost) if t.unit_cost else None,
                    'reference_type': t.reference_type,
                    'created_at': t.created_at.isoformat()
                } for t in transactions]
            }
            items_data.append(item_data)
        
        return jsonify({
            'work_order_id': work_order.id,
            'job_number': work_order.job_number,
            'status': work_order.status,
            'agency_id': work_order.agency_id,
            'material_items': items_data
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to retrieve consumption details: {str(e)}'
        }), 500


@service_bp.route('/api/service/jobs/<int:job_id>', methods=['DELETE'])
@permission_required(roles=['service_manager'])
def delete_work_order(job_id, current_agency_id=None):
    """Delete a work order (restricted to manager)."""
    query = WorkOrder.query.filter_by(id=job_id)
    if session.get('role') != 'super_admin':
        query = query.filter_by(agency_id=current_agency_id)
        
    work_order = query.first_or_404()

    # It's safer to mark as 'Cancelled' than to hard delete
    if work_order.status in ['Estimate', 'Approved']:
        work_order.status = 'Cancelled'
        db.session.commit()
        return jsonify({'message': 'Work order has been cancelled.'})
    else:
        return jsonify({'error': 'Cannot delete a work order that is in progress or completed. Please cancel it instead.'}), 400