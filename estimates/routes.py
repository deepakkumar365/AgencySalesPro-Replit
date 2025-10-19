from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Estimate, EstimateItem, WorkOrder, User, Agency
from functools import wraps
from datetime import datetime
from estimates import estimates_bp

# Authorization decorators
def require_agency_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['super_admin', 'agency_admin', 'agency_manager', 'service_manager']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# LIST ESTIMATES
@estimates_bp.route('/', methods=['GET'])
@login_required
@require_agency_access
def list_estimates():
    """List all estimates for current agency"""
    if current_user.role == 'super_admin':
        estimates = Estimate.query.all()
    else:
        # Get estimates for user's agency work orders
        estimates = db.session.query(Estimate).join(WorkOrder).filter(
            WorkOrder.agency_id == current_user.agency_id
        ).all()
    
    return render_template('estimates/list.html', estimates=estimates)

# CREATE ESTIMATE FROM WORK ORDER
@estimates_bp.route('/create/<int:work_order_id>', methods=['GET', 'POST'])
@login_required
@require_agency_access
def create_estimate(work_order_id):
    """Create new estimate from work order"""
    work_order = WorkOrder.query.get_or_404(work_order_id)
    
    # Verify access
    if current_user.role != 'super_admin' and work_order.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('estimates.list_estimates'))
    
    if request.method == 'POST':
        data = request.get_json()
        
        # Generate estimate number
        last_estimate = Estimate.query.order_by(Estimate.id.desc()).first()
        estimate_num = f"EST-{datetime.utcnow().strftime('%Y%m%d')}-{(last_estimate.id + 1 if last_estimate else 1):04d}"
        
        estimate = Estimate(
            work_order_id=work_order_id,
            estimate_number=estimate_num,
            estimated_total=data.get('estimated_total', 0),
            notes=data.get('notes', '')
        )
        db.session.add(estimate)
        db.session.flush()
        
        # Add line items
        for item in data.get('items', []):
            estimate_item = EstimateItem(
                estimate_id=estimate.id,
                description=item['description'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                line_total=float(item['quantity']) * float(item['unit_price'])
            )
            db.session.add(estimate_item)
        
        db.session.commit()
        flash('Estimate created successfully', 'success')
        return jsonify({'success': True, 'estimate_id': estimate.id})
    
    return render_template('estimates/create.html', work_order=work_order)

# VIEW ESTIMATE
@estimates_bp.route('/<int:estimate_id>', methods=['GET'])
@login_required
@require_agency_access
def view_estimate(estimate_id):
    """View estimate details"""
    estimate = Estimate.query.get_or_404(estimate_id)
    
    # Verify access
    if current_user.role != 'super_admin' and estimate.work_order.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('estimates.list_estimates'))
    
    return render_template('estimates/view.html', estimate=estimate)

# EDIT ESTIMATE
@estimates_bp.route('/<int:estimate_id>/edit', methods=['GET', 'POST'])
@login_required
@require_agency_access
def edit_estimate(estimate_id):
    """Edit estimate (only if Draft status)"""
    estimate = Estimate.query.get_or_404(estimate_id)
    
    # Verify access and status
    if current_user.role != 'super_admin' and estimate.work_order.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('estimates.list_estimates'))
    
    if estimate.status != 'Draft':
        flash('Can only edit Draft estimates', 'warning')
        return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))
    
    if request.method == 'POST':
        data = request.get_json()
        estimate.estimated_total = data.get('estimated_total', 0)
        estimate.notes = data.get('notes', '')
        
        # Update line items
        EstimateItem.query.filter_by(estimate_id=estimate_id).delete()
        for item in data.get('items', []):
            estimate_item = EstimateItem(
                estimate_id=estimate.id,
                description=item['description'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                line_total=float(item['quantity']) * float(item['unit_price'])
            )
            db.session.add(estimate_item)
        
        db.session.commit()
        flash('Estimate updated successfully', 'success')
        return jsonify({'success': True})
    
    return render_template('estimates/edit.html', estimate=estimate)

# APPROVE ESTIMATE
@estimates_bp.route('/<int:estimate_id>/approve', methods=['POST'])
@login_required
@require_agency_access
def approve_estimate(estimate_id):
    """Approve estimate (changes status to Approved)"""
    estimate = Estimate.query.get_or_404(estimate_id)
    
    # Verify access and authorization
    if current_user.role not in ['super_admin', 'agency_admin']:
        flash('Unauthorized to approve estimates', 'danger')
        return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))
    
    if estimate.work_order.agency_id != current_user.agency_id and current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('estimates.list_estimates'))
    
    if estimate.status == 'Draft':
        estimate.status = 'Approved'
        estimate.approved_at = datetime.utcnow()
        estimate.approved_by = current_user.id
        db.session.commit()
        flash('Estimate approved successfully', 'success')
    else:
        flash('Estimate is not in Draft status', 'warning')
    
    return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))

# REJECT ESTIMATE
@estimates_bp.route('/<int:estimate_id>/reject', methods=['POST'])
@login_required
@require_agency_access
def reject_estimate(estimate_id):
    """Reject estimate"""
    estimate = Estimate.query.get_or_404(estimate_id)
    
    # Verify access and authorization
    if current_user.role not in ['super_admin', 'agency_admin']:
        flash('Unauthorized to reject estimates', 'danger')
        return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))
    
    if estimate.work_order.agency_id != current_user.agency_id and current_user.role != 'super_admin':
        flash('Unauthorized access', 'danger')
        return redirect(url_for('estimates.list_estimates'))
    
    estimate.status = 'Rejected'
    db.session.commit()
    flash('Estimate rejected', 'success')
    
    return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))

# DELETE ESTIMATE
@estimates_bp.route('/<int:estimate_id>/delete', methods=['POST'])
@login_required
@require_agency_access
def delete_estimate(estimate_id):
    """Delete estimate (only if Draft)"""
    estimate = Estimate.query.get_or_404(estimate_id)
    
    # Verify access
    if current_user.role != 'super_admin' and estimate.work_order.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('estimates.list_estimates'))
    
    if estimate.status != 'Draft':
        flash('Can only delete Draft estimates', 'warning')
        return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))
    
    db.session.delete(estimate)
    db.session.commit()
    flash('Estimate deleted successfully', 'success')
    
    return redirect(url_for('estimates.list_estimates'))

# API: Get estimate items
@estimates_bp.route('/api/<int:estimate_id>/items', methods=['GET'])
@login_required
def get_estimate_items(estimate_id):
    """API endpoint to get estimate items"""
    estimate = Estimate.query.get_or_404(estimate_id)
    items = [
        {
            'id': item.id,
            'description': item.description,
            'quantity': float(item.quantity),
            'unit_price': float(item.unit_price),
            'line_total': float(item.line_total)
        }
        for item in estimate.items
    ]
    return jsonify(items)