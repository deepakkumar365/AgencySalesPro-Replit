from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Branch, Agency, User
from functools import wraps
from datetime import datetime
from branch_management import branch_management_bp

# Authorization decorators
def require_agency_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['super_admin', 'agency_admin']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# LIST BRANCHES
@branch_management_bp.route('/', methods=['GET'])
@login_required
@require_agency_admin
def list_branches():
    """List all branches for agency"""
    is_active = request.args.get('is_active', '1')
    
    if current_user.role == 'super_admin':
        query = Branch.query
    else:
        query = Branch.query.filter_by(agency_id=current_user.agency_id)
    
    if is_active != 'all':
        query = query.filter_by(is_active=is_active == '1')
    
    branches = query.all()
    
    return render_template('branch_management/list.html', branches=branches, is_active=is_active)

# CREATE BRANCH
@branch_management_bp.route('/create', methods=['GET', 'POST'])
@login_required
@require_agency_admin
def create_branch():
    """Create new branch"""
    if request.method == 'POST':
        data = request.get_json()
        
        # Verify unique name per agency
        agency_id = current_user.agency_id if current_user.role != 'super_admin' else data['agency_id']
        
        existing = Branch.query.filter_by(
            agency_id=agency_id,
            name=data['name']
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Branch name already exists for this agency'}), 400
        
        branch = Branch(
            agency_id=agency_id,
            name=data['name'],
            address=data.get('address', ''),
            city=data.get('city', ''),
            state=data.get('state', ''),
            phone=data.get('phone', ''),
            manager_id=data.get('manager_id')
        )
        db.session.add(branch)
        db.session.commit()
        
        flash('Branch created successfully', 'success')
        return jsonify({'success': True, 'branch_id': branch.id})
    
    # Get users for manager selection
    if current_user.role == 'super_admin':
        managers = User.query.filter(User.role.in_(['agency_admin', 'agency_manager', 'service_manager'])).all()
    else:
        managers = User.query.filter_by(agency_id=current_user.agency_id).filter(
            User.role.in_(['agency_admin', 'agency_manager', 'service_manager'])
        ).all()
    
    return render_template('branch_management/form.html', managers=managers)

# EDIT BRANCH
@branch_management_bp.route('/<int:branch_id>/edit', methods=['GET', 'POST'])
@login_required
@require_agency_admin
def edit_branch(branch_id):
    """Edit branch details"""
    branch = Branch.query.get_or_404(branch_id)
    
    # Verify access
    if current_user.role != 'super_admin' and branch.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('branch_management.list_branches'))
    
    if request.method == 'POST':
        data = request.get_json()
        
        # Verify unique name (excluding current branch)
        existing = Branch.query.filter(
            Branch.agency_id == branch.agency_id,
            Branch.name == data['name'],
            Branch.id != branch_id
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Branch name already exists for this agency'}), 400
        
        branch.name = data['name']
        branch.address = data.get('address', '')
        branch.city = data.get('city', '')
        branch.state = data.get('state', '')
        branch.phone = data.get('phone', '')
        branch.manager_id = data.get('manager_id')
        branch.is_active = data.get('is_active', True)
        branch.updated_at = datetime.utcnow()
        
        db.session.commit()
        flash('Branch updated successfully', 'success')
        return jsonify({'success': True})
    
    # Get users for manager selection
    if current_user.role == 'super_admin':
        managers = User.query.filter(User.role.in_(['agency_admin', 'agency_manager', 'service_manager'])).all()
    else:
        managers = User.query.filter_by(agency_id=current_user.agency_id).filter(
            User.role.in_(['agency_admin', 'agency_manager', 'service_manager'])
        ).all()
    
    return render_template('branch_management/form.html', branch=branch, managers=managers)

# VIEW BRANCH
@branch_management_bp.route('/<int:branch_id>', methods=['GET'])
@login_required
@require_agency_admin
def view_branch(branch_id):
    """View branch details"""
    branch = Branch.query.get_or_404(branch_id)
    
    # Verify access
    if current_user.role != 'super_admin' and branch.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('branch_management.list_branches'))
    
    # Get branch statistics
    from models import WorkOrder, Labour, Contractor
    
    total_work_orders = WorkOrder.query.count()  # TODO: Filter by branch once work orders have branch_id
    total_labour = Labour.query.count()  # TODO: Filter by branch
    total_contractors = Contractor.query.count()  # TODO: Filter by branch
    
    return render_template(
        'branch_management/view.html',
        branch=branch,
        total_work_orders=total_work_orders,
        total_labour=total_labour,
        total_contractors=total_contractors
    )

# DELETE BRANCH
@branch_management_bp.route('/<int:branch_id>/delete', methods=['POST'])
@login_required
@require_agency_admin
def delete_branch(branch_id):
    """Delete branch (soft delete via is_active flag)"""
    branch = Branch.query.get_or_404(branch_id)
    
    # Verify access
    if current_user.role != 'super_admin' and branch.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('branch_management.list_branches'))
    
    branch.is_active = False
    branch.updated_at = datetime.utcnow()
    db.session.commit()
    
    flash('Branch deactivated successfully', 'success')
    return redirect(url_for('branch_management.list_branches'))

# ACTIVATE BRANCH
@branch_management_bp.route('/<int:branch_id>/activate', methods=['POST'])
@login_required
@require_agency_admin
def activate_branch(branch_id):
    """Reactivate branch"""
    branch = Branch.query.get_or_404(branch_id)
    
    # Verify access
    if current_user.role != 'super_admin' and branch.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('branch_management.list_branches'))
    
    branch.is_active = True
    branch.updated_at = datetime.utcnow()
    db.session.commit()
    
    flash('Branch activated successfully', 'success')
    return redirect(url_for('branch_management.list_branches'))

# API: Get branches by agency
@branch_management_bp.route('/api/<int:agency_id>/branches', methods=['GET'])
@login_required
def get_branches_by_agency(agency_id):
    """API endpoint to get branches for an agency"""
    branches = Branch.query.filter_by(agency_id=agency_id, is_active=True).all()
    return jsonify([
        {
            'id': b.id,
            'name': b.name,
            'city': b.city,
            'state': b.state,
            'manager_id': b.manager_id,
            'manager_name': b.branch_manager.full_name if b.branch_manager else 'Unassigned'
        }
        for b in branches
    ])

# API: Get branch details
@branch_management_bp.route('/api/<int:branch_id>/details', methods=['GET'])
@login_required
def get_branch_details(branch_id):
    """API endpoint to get branch details"""
    branch = Branch.query.get_or_404(branch_id)
    return jsonify({
        'id': branch.id,
        'name': branch.name,
        'address': branch.address,
        'city': branch.city,
        'state': branch.state,
        'phone': branch.phone,
        'agency_id': branch.agency_id,
        'manager_id': branch.manager_id,
        'manager_name': branch.branch_manager.full_name if branch.branch_manager else None,
        'is_active': branch.is_active,
        'created_at': branch.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': branch.updated_at.strftime('%Y-%m-%d %H:%M:%S') if branch.updated_at else None
    })

# BRANCH STATISTICS
@branch_management_bp.route('/<int:branch_id>/statistics', methods=['GET'])
@login_required
def branch_statistics(branch_id):
    """Get statistics for a branch"""
    branch = Branch.query.get_or_404(branch_id)
    
    # Verify access
    if current_user.role != 'super_admin' and branch.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('branch_management.list_branches'))
    
    # TODO: Implement branch-specific statistics once all models support branch_id
    stats = {
        'total_work_orders': 0,
        'total_labour': 0,
        'total_contractors': 0,
        'total_invoices': 0,
        'total_revenue': 0
    }
    
    return render_template('branch_management/statistics.html', branch=branch, stats=stats)