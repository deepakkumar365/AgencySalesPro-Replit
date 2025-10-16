import uuid
from datetime import datetime
from decimal import Decimal

from flask import jsonify, request, session
from sqlalchemy import func

from auth.utils import login_required, permission_required
from extensions import db
from models import (WorkOrder, WorkOrderLineItem, Customer, Vehicle,
                    ServiceCatalog, Product, User, Agency, InventoryTransaction)

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
    
    query = WorkOrder.query.join(Customer).join(Vehicle)

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
    if 'vehicle_id' in request.args:
        query = query.filter(WorkOrder.vehicle_id == request.args['vehicle_id'])

    page = request.args.get('page', 1, type=int)
    per_page = 20

    paginated_orders = query.order_by(WorkOrder.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    results = [{
        'id': wo.id,
        'job_number': wo.job_number,
        'customer_name': wo.customer.name,
        'vehicle': f"{wo.vehicle.make} {wo.vehicle.model}",
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
    vehicle_id = data.get('vehicle_id')

    if not all([customer_id, vehicle_id]):
        return jsonify({'error': 'customer_id and vehicle_id are required'}), 400

    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle or vehicle.customer_id != customer_id:
        return jsonify({'error': 'Vehicle does not belong to the specified customer'}), 400

    try:
        job_number = generate_job_number(current_agency_id)
        
        work_order = WorkOrder(
            job_number=job_number,
            agency_id=current_agency_id,
            customer_id=customer_id,
            vehicle_id=vehicle_id,
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

    response = {
        'id': work_order.id,
        'job_number': work_order.job_number,
        'status': work_order.status,
        'customer': {'id': work_order.customer.id, 'name': work_order.customer.name},
        'vehicle': {'id': work_order.vehicle.id, 'make': work_order.vehicle.make, 'model': work_order.vehicle.model, 'license_plate': work_order.vehicle.license_plate},
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