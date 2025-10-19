"""
Service module routes - handles all service-centric operations.
Focus: Work Orders, Vehicles, Services, and Technician Management
"""

from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import func, or_, and_
import math
from decimal import Decimal
from datetime import datetime, timedelta

from extensions import db
from models import (
    WorkOrder, WorkOrderLineItem, ServiceCatalog, Customer, 
    User, Agency, Product, InventoryTransaction, Location
)
    
from auth.utils import login_required, permission_required
from utils.decorators import log_activity
from utils.service_utils import deduct_inventory_for_work_order

from . import service_bp


# ==================== DASHBOARD ====================

@service_bp.route('/dashboard')
@login_required
@permission_required(roles=['service_manager', 'service_advisor', 'technician'])
def dashboard(**kwargs):
    """Service operation dashboard with KPIs and quick stats."""
    current_agency_id = kwargs.get('current_agency_id')
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Base query for work orders
    wo_query = WorkOrder.query
    if user_role != 'super_admin':
        wo_query = wo_query.filter(WorkOrder.agency_id == current_agency_id)
    
    # Technician sees only their work orders
    if user_role == 'technician':
        wo_query = wo_query.filter(WorkOrder.assigned_technician_id == user_id)
    
    all_work_orders = wo_query.all()
    
    # Calculate KPIs
    total_work_orders = len(all_work_orders)
    active_wos = len([wo for wo in all_work_orders if wo.status in ['Estimate', 'Approved', 'In Progress']])
    completed_today = len([wo for wo in all_work_orders 
                          if wo.status == 'Completed' 
                          and wo.completed_at 
                          and wo.completed_at.date() == datetime.utcnow().date()])
    
    # Calculate total revenue
    total_estimated_revenue = sum(Decimal(wo.estimated_cost or 0) for wo in all_work_orders)
    total_actual_revenue = sum(Decimal(wo.actual_cost or 0) for wo in all_work_orders if wo.status == 'Completed')
    
    # Status breakdown
    status_breakdown = {}
    for wo in all_work_orders:
        status_breakdown[wo.status] = status_breakdown.get(wo.status, 0) + 1
    
    # Recent work orders
    recent_wos = sorted(all_work_orders, key=lambda x: x.created_at, reverse=True)[:5]
    
    # Pending approvals (service_manager only)
    pending_approvals = len([wo for wo in all_work_orders if wo.status == 'Estimate'])
    
    # Technician stats (if applicable)
    technician_stats = None
    if user_role == 'technician':
        completed_by_tech = len([wo for wo in all_work_orders if wo.status == 'Completed'])
        in_progress_by_tech = len([wo for wo in all_work_orders if wo.status == 'In Progress'])
        technician_stats = {
            'completed': completed_by_tech,
            'in_progress': in_progress_by_tech,
            'total_assigned': len(all_work_orders)
        }
    
    return render_template(
        'service/dashboard.html',
        total_work_orders=total_work_orders,
        active_wos=active_wos,
        completed_today=completed_today,
        total_estimated_revenue=float(total_estimated_revenue),
        total_actual_revenue=float(total_actual_revenue),
        status_breakdown=status_breakdown,
        recent_wos=recent_wos,
        pending_approvals=pending_approvals,
        technician_stats=technician_stats,
        user_role=user_role
    )


# ==================== WORK ORDER MANAGEMENT ====================

def generate_work_order_number(agency_id):
    """Generate unique work order number."""
    today_str = datetime.utcnow().strftime('%Y%m')
    prefix = f"WO-{today_str}-"
    
    last_wo = WorkOrder.query.filter(
        WorkOrder.job_number.like(f"{prefix}%"),
        WorkOrder.agency_id == agency_id
    ).order_by(WorkOrder.job_number.desc()).first()
    
    if last_wo:
        last_seq = int(last_wo.job_number.split('-')[-1])
        new_seq = last_seq + 1
    else:
        new_seq = 1
    
    return f"{prefix}{new_seq:04d}"


@service_bp.route('/work-orders')
@login_required
@permission_required(roles=['service_manager', 'service_advisor', 'technician'])
def list_work_orders(**kwargs):
    """List all work orders with filters."""
    current_agency_id = kwargs.get('current_agency_id')
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Base query
    query = WorkOrder.query
    if user_role != 'super_admin':
        query = query.filter(WorkOrder.agency_id == current_agency_id)
    
    # Technician sees only their work orders
    if user_role == 'technician':
        query = query.filter(WorkOrder.assigned_technician_id == user_id)
    
    # Apply filters
    status_filter = request.args.get('status')
    if status_filter:
        query = query.filter(WorkOrder.status == status_filter)
    
    customer_filter = request.args.get('customer_id')
    if customer_filter:
        query = query.filter(WorkOrder.customer_id == customer_filter)
    
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    if date_from:
        query = query.filter(WorkOrder.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(WorkOrder.created_at <= datetime.strptime(date_to, '%Y-%m-%d'))
    
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 15
    paginated = query.order_by(WorkOrder.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template(
        'service/work_orders/list.html',
        work_orders=paginated.items,
        paginated=paginated,
        current_status=status_filter
    )


@service_bp.route('/work-orders/create', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['service_manager', 'service_advisor'])
@log_activity('Create work order')
def create_work_order(**kwargs):
    """Create new work order."""
    current_agency_id = kwargs.get('current_agency_id')
    
    if request.method == 'POST':
        try:
            customer_id = request.form.get('customer_id', type=int)
            technician_id = request.form.get('technician_id', type=int)
            estimated_cost = Decimal(request.form.get('estimated_cost', 0))
            notes = request.form.get('notes', '')
            
            # Validate customer and vehicle
            customer = Customer.query.get(customer_id)
            if not customer:
                flash('Invalid customer selected', 'danger')
                return redirect(url_for('service.create_work_order'))

            # Vehicle handling removed - work orders map to customer only
            
            # Create work order
            work_order = WorkOrder(
                job_number=generate_work_order_number(current_agency_id),
                agency_id=current_agency_id,
                customer_id=customer_id,
                assigned_technician_id=technician_id,
                estimated_cost=estimated_cost,
                notes=notes,
                status='Estimate',
                created_by=session.get('user_id')
            )
            db.session.add(work_order)
            db.session.flush()
            
            # Add services (if provided)
            service_ids = request.form.getlist('service_ids')
            for svc_id in service_ids:
                service = ServiceCatalog.query.get(svc_id)
                if service:
                    qty = Decimal(request.form.get(f'service_qty_{svc_id}', 1))
                    line_item = WorkOrderLineItem(
                        work_order_id=work_order.id,
                        line_type='service',
                        description=service.name,
                        quantity=qty,
                        unit_cost=service.default_price,
                        total_cost=qty * service.default_price,
                        service_id=service.id
                    )
                    db.session.add(line_item)
            
            # Add materials/parts (if provided)
            product_ids = request.form.getlist('product_ids')
            for prod_id in product_ids:
                product = Product.query.get(prod_id)
                if product:
                    qty = Decimal(request.form.get(f'product_qty_{prod_id}', 0))
                    unit_cost = Decimal(request.form.get(f'product_cost_{prod_id}', product.buy_price or 0))
                    line_item = WorkOrderLineItem(
                        work_order_id=work_order.id,
                        line_type='material',
                        description=product.name,
                        quantity=qty,
                        unit_cost=unit_cost,
                        total_cost=qty * unit_cost,
                        product_id=product.id
                    )
                    db.session.add(line_item)
            
            db.session.commit()
            flash(f'Work order {work_order.job_number} created successfully', 'success')
            return redirect(url_for('service.view_work_order', work_order_id=work_order.id))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating work order: {str(e)}', 'danger')
            return redirect(url_for('service.create_work_order'))
    
    # GET request - show form
    customers = Customer.query.join(Location).filter(
        Location.agency_id == current_agency_id
    ).all()
    # Allow selecting which service_type to use when creating a work order
    service_type = request.args.get('service_type', 'garage')
    services = ServiceCatalog.query.filter_by(
        agency_id=current_agency_id, is_active=True, service_type=service_type
    ).all()
    products = Product.query.all()
    technicians = User.query.filter(
        User.agency_id == current_agency_id,
        User.role.in_(['technician'])
    ).all()
    
    return render_template(
        'service/work_orders/create.html',
        customers=customers,
        services=services,
        products=products,
        technicians=technicians
    )


@service_bp.route('/work-orders/<int:work_order_id>')
@login_required
@permission_required(roles=['service_manager', 'service_advisor', 'technician'])
def view_work_order(work_order_id, **kwargs):
    """View work order details."""
    current_agency_id = kwargs.get('current_agency_id')
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    query = WorkOrder.query.filter_by(id=work_order_id)
    if user_role != 'super_admin':
        query = query.filter_by(agency_id=current_agency_id)
    
    work_order = query.first_or_404()
    
    # Technician can only view their assigned work orders
    if user_role == 'technician' and work_order.assigned_technician_id != user_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('service.list_work_orders'))
    
    # Get inventory transactions for this work order by line items
    line_item_ids = [li.id for li in work_order.line_items]
    inventory_transactions = []
    if line_item_ids:
        inventory_transactions = InventoryTransaction.query.filter(
            InventoryTransaction.work_order_line_item_id.in_(line_item_ids)
        ).order_by(InventoryTransaction.created_at.desc()).all()
    
    return render_template(
        'service/work_orders/view.html',
        work_order=work_order,
        inventory_transactions=inventory_transactions,
        user_role=user_role
    )


@service_bp.route('/work-orders/<int:work_order_id>/approve', methods=['POST'])
@login_required
@permission_required(roles=['service_manager'])
@log_activity('Approve work order')
def approve_work_order(work_order_id, **kwargs):
    """Approve work order estimate."""
    current_agency_id = kwargs.get('current_agency_id')
    
    work_order = WorkOrder.query.filter_by(
        id=work_order_id, 
        agency_id=current_agency_id
    ).first_or_404()
    
    if work_order.status != 'Estimate':
        flash('Only estimates can be approved', 'warning')
    else:
        work_order.status = 'Approved'
        work_order.approved_at = datetime.utcnow()
        db.session.commit()
        flash(f'Work order {work_order.job_number} approved', 'success')
    
    return redirect(url_for('service.view_work_order', work_order_id=work_order_id))


@service_bp.route('/work-orders/<int:work_order_id>/start', methods=['POST'])
@login_required
@permission_required(roles=['service_manager', 'service_advisor', 'technician'])
@log_activity('Start work order')
def start_work_order(work_order_id, **kwargs):
    """Start work on a work order."""
    current_agency_id = kwargs.get('current_agency_id')
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    work_order = WorkOrder.query.filter_by(
        id=work_order_id, 
        agency_id=current_agency_id
    ).first_or_404()
    
    # Technician can only start their own work orders
    if user_role == 'technician' and work_order.assigned_technician_id != user_id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('service.list_work_orders'))
    
    if work_order.status not in ['Approved', 'Estimate']:
        flash('Can only start approved or estimate work orders', 'warning')
    else:
        work_order.status = 'In Progress'
        work_order.in_progress_at = datetime.utcnow()
        db.session.commit()
        flash(f'Work on {work_order.job_number} started', 'success')
    
    return redirect(url_for('service.view_work_order', work_order_id=work_order_id))


@service_bp.route('/work-orders/<int:work_order_id>/complete', methods=['POST'])
@login_required
@permission_required(roles=['service_manager', 'service_advisor', 'technician'])
@log_activity('Complete work order')
def complete_work_order(work_order_id, **kwargs):
    """Complete work order and deduct inventory."""
    current_agency_id = kwargs.get('current_agency_id')
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    work_order = WorkOrder.query.filter_by(
        id=work_order_id, 
        agency_id=current_agency_id
    ).first_or_404()
    
    # Technician can only complete their own work orders
    if user_role == 'technician' and work_order.assigned_technician_id != user_id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('service.list_work_orders'))
    
    if work_order.status != 'In Progress':
        flash('Only in-progress work orders can be completed', 'warning')
    else:
        try:
            work_order.status = 'Completed'
            work_order.completed_at = datetime.utcnow()
            
            # If actual cost not set, use estimated cost
            if not work_order.actual_cost:
                work_order.actual_cost = work_order.estimated_cost
            
            # Deduct inventory for material items
            inventory_result = deduct_inventory_for_work_order(work_order, user_id)
            
            db.session.commit()
            flash(f'Work order {work_order.job_number} completed', 'success')
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error completing work order: {str(e)}', 'danger')
    
    return redirect(url_for('service.view_work_order', work_order_id=work_order_id))


@service_bp.route('/work-orders/<int:work_order_id>/deliver', methods=['POST'])
@login_required
@permission_required(roles=['service_manager', 'service_advisor'])
@log_activity('Deliver work order')
def deliver_work_order(work_order_id, **kwargs):
    """Mark work order as delivered."""
    current_agency_id = kwargs.get('current_agency_id')
    
    work_order = WorkOrder.query.filter_by(
        id=work_order_id, 
        agency_id=current_agency_id
    ).first_or_404()
    
    if work_order.status != 'Completed':
        flash('Only completed work orders can be delivered', 'warning')
    else:
        work_order.status = 'Delivered'
        work_order.delivered_at = datetime.utcnow()
        db.session.commit()
        flash(f'Work order {work_order.job_number} delivered', 'success')
    
    return redirect(url_for('service.view_work_order', work_order_id=work_order_id))


# VEHICLE MANAGEMENT endpoints removed from UI (Vehicle model retained for data).
# If you need to re-enable vehicle pages, restore the functions below.


# ==================== SERVICE CATALOG ====================

@service_bp.route('/services')
@login_required
@permission_required(roles=['service_manager', 'service_advisor'])
def list_services(**kwargs):
    """List all available services."""
    current_agency_id = kwargs.get('current_agency_id')
    # Allow filtering by service_type (garage, chitfund, subscription) or 'all'
    service_type = request.args.get('service_type', 'all')
    # Active filter: 'all' (default), 'true' (only active), 'false' (only inactive)
    is_active = request.args.get('is_active', 'all')
    # Free-text search
    q = request.args.get('q', '').strip()
    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 24, type=int)

    # Base query
    query = ServiceCatalog.query.filter(ServiceCatalog.agency_id == current_agency_id)

    if service_type and service_type != 'all':
        query = query.filter(ServiceCatalog.service_type == service_type)

    if is_active == 'true':
        query = query.filter(ServiceCatalog.is_active == True)
    elif is_active == 'false':
        query = query.filter(ServiceCatalog.is_active == False)

    if q:
        likeq = f"%{q}%"
        query = query.filter(or_(
            ServiceCatalog.name.ilike(likeq),
            ServiceCatalog.description.ilike(likeq)
        ))

    total = query.count()
    total_pages = max(1, math.ceil(total / per_page))

    services = query.order_by(ServiceCatalog.name).offset((page - 1) * per_page).limit(per_page).all()

    return render_template(
        'service/services/list.html',
        services=services,
        service_type=service_type,
        is_active=is_active,
        q=q,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages
    )


@service_bp.route('/services/create', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['service_manager'])
@log_activity('Create service')
def create_service(**kwargs):
    """Add new service to catalog."""
    current_agency_id = kwargs.get('current_agency_id')
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            description = request.form.get('description')
            default_price = Decimal(request.form.get('default_price', 0))
            estimated_hours = request.form.get('estimated_hours', type=float)
            service_type = request.form.get('service_type', 'garage')

            if not name or not name.strip():
                flash('Service name is required', 'warning')
                return redirect(url_for('service.create_service'))

            # Check for existing service with same name (case-insensitive) in this agency
            existing = ServiceCatalog.query.filter(
                func.lower(ServiceCatalog.name) == name.strip().lower(),
                ServiceCatalog.agency_id == current_agency_id,
                ServiceCatalog.service_type == service_type
            ).first()
            if existing:
                flash(f'A service named "{name}" already exists for this agency', 'warning')
                return redirect(url_for('service.create_service'))

            service = ServiceCatalog(
                agency_id=current_agency_id,
                name=name.strip(),
                description=description,
                default_price=default_price,
                estimated_hours=estimated_hours,
                is_active=True,
                service_type=service_type
            )
            db.session.add(service)
            db.session.commit()
            flash(f'Service "{name}" added to catalog', 'success')
            return redirect(url_for('service.list_services', service_type=service_type))

        except Exception as e:
            db.session.rollback()
            # Friendly fallback for DB unique constraint or other integrity issues
            flash(f'Error creating service: {str(e)}', 'danger')
    
    return render_template('service/services/form.html')


@service_bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['service_manager'])
@log_activity('Edit service')
def edit_service(service_id, **kwargs):
    """Edit existing service."""
    current_agency_id = kwargs.get('current_agency_id')
    
    service = ServiceCatalog.query.filter_by(
        id=service_id,
        agency_id=current_agency_id
    ).first_or_404()
    
    if request.method == 'POST':
        try:
            new_name = request.form.get('name')
            # Validate name
            if not new_name or not new_name.strip():
                flash('Service name is required', 'warning')
                return redirect(url_for('service.edit_service', service_id=service_id))

            # Check duplicates (excluding self)
            duplicate = ServiceCatalog.query.filter(
                func.lower(ServiceCatalog.name) == new_name.strip().lower(),
                ServiceCatalog.agency_id == current_agency_id,
                ServiceCatalog.id != service_id,
                ServiceCatalog.service_type == request.form.get('service_type', service.service_type)
            ).first()
            if duplicate:
                flash(f'Another service with name "{new_name}" already exists', 'warning')
                return redirect(url_for('service.edit_service', service_id=service_id))

            service.name = new_name.strip()
            service.description = request.form.get('description')
            service.default_price = Decimal(request.form.get('default_price', service.default_price))
            service.estimated_hours = request.form.get('estimated_hours', type=float)
            service.is_active = request.form.get('is_active') == 'on'
            service.service_type = request.form.get('service_type', service.service_type)
            
            db.session.commit()
            flash(f'Service "{service.name}" updated', 'success')
            return redirect(url_for('service.list_services', service_type=service.service_type))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating service: {str(e)}', 'danger')
    
    return render_template('service/services/form.html', service=service)


# ==================== TECHNICIAN MANAGEMENT ====================

@service_bp.route('/technicians')
@login_required
@permission_required(roles=['service_manager', 'service_advisor'])
def list_technicians(**kwargs):
    """List all technicians in agency."""
    current_agency_id = kwargs.get('current_agency_id')
    
    technicians = User.query.filter(
        User.agency_id == current_agency_id,
        User.role == 'technician'
    ).all()
    
    # Calculate workload for each technician
    tech_stats = {}
    for tech in technicians:
        active_wos = WorkOrder.query.filter(
            WorkOrder.assigned_technician_id == tech.id,
            WorkOrder.status.in_(['In Progress', 'Approved'])
        ).count()
        
        completed_wos = WorkOrder.query.filter(
            WorkOrder.assigned_technician_id == tech.id,
            WorkOrder.status == 'Completed'
        ).count()
        
        tech_stats[tech.id] = {
            'active': active_wos,
            'completed': completed_wos
        }
    
    return render_template(
        'service/technicians/list.html',
        technicians=technicians,
        tech_stats=tech_stats
    )


@service_bp.route('/technicians/<int:tech_id>/workload')
@login_required
@permission_required(roles=['service_manager', 'service_advisor'])
def technician_workload(tech_id, **kwargs):
    """View detailed workload for a technician."""
    current_agency_id = kwargs.get('current_agency_id')
    
    technician = User.query.filter_by(
        id=tech_id,
        agency_id=current_agency_id,
        role='technician'
    ).first_or_404()
    
    # Get all work orders assigned to technician
    work_orders = WorkOrder.query.filter_by(
        assigned_technician_id=tech_id
    ).order_by(WorkOrder.created_at.desc()).all()
    
    # Categorize by status
    by_status = {}
    for wo in work_orders:
        status = wo.status
        by_status[status] = by_status.get(status, []) + [wo]
    
    return render_template(
        'service/technicians/workload.html',
        technician=technician,
        work_orders_by_status=by_status
    )