from flask import render_template, request, redirect, url_for, flash, session
from app import db
from models import Agency, User
from agency import agency_bp
from auth.utils import login_required, role_required
from utils.decorators import log_activity

@agency_bp.route('/')
@login_required
@role_required('super_admin', 'agency_admin')
def list_agencies():
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        agencies = Agency.query.all()
    else:
        # Agency admin can only see their own agency
        agency_id = session.get('agency_id')
        agencies = Agency.query.filter_by(id=agency_id).all()
    
    return render_template('agency/list.html', agencies=agencies)

@agency_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
@log_activity('create_agency')
def create_agency():
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        address = request.form.get('address')
        phone = request.form.get('phone')
        email = request.form.get('email')
        
        if not name or not code:
            flash('Name and code are required', 'error')
            return render_template('agency/form.html')
        
        # Check if code already exists
        if Agency.query.filter_by(code=code).first():
            flash('Agency code already exists', 'error')
            return render_template('agency/form.html')
        
        agency = Agency(
            name=name,
            code=code,
            address=address,
            phone=phone,
            email=email,
            is_active=True
        )
        
        db.session.add(agency)
        db.session.commit()
        
        flash('Agency created successfully!', 'success')
        return redirect(url_for('agency.list_agencies'))
    
    return render_template('agency/form.html')

@agency_bp.route('/<int:agency_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'agency_admin')
@log_activity('edit_agency')
def edit_agency(agency_id):
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role == 'agency_admin' and current_agency_id != agency_id:
        flash('You can only edit your own agency', 'error')
        return redirect(url_for('agency.list_agencies'))
    
    agency = Agency.query.get_or_404(agency_id)
    
    if request.method == 'POST':
        agency.name = request.form.get('name')
        agency.code = request.form.get('code')
        agency.address = request.form.get('address')
        agency.phone = request.form.get('phone')
        agency.email = request.form.get('email')
        
        if not agency.name or not agency.code:
            flash('Name and code are required', 'error')
            return render_template('agency/form.html', agency=agency)
        
        # Check if code already exists (excluding current agency)
        existing = Agency.query.filter_by(code=agency.code).first()
        if existing and existing.id != agency.id:
            flash('Agency code already exists', 'error')
            return render_template('agency/form.html', agency=agency)
        
        db.session.commit()
        flash('Agency updated successfully!', 'success')
        return redirect(url_for('agency.list_agencies'))
    
    return render_template('agency/form.html', agency=agency)

@agency_bp.route('/<int:agency_id>/toggle_status', methods=['POST'])
@login_required
@role_required('super_admin')
@log_activity('toggle_agency_status')
def toggle_agency_status(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    agency.is_active = not agency.is_active
    db.session.commit()
    
    status = 'activated' if agency.is_active else 'deactivated'
    flash(f'Agency {status} successfully!', 'success')
    return redirect(url_for('agency.list_agencies'))

@agency_bp.route('/<int:agency_id>/users')
@login_required
@role_required('super_admin', 'agency_admin')
def agency_users(agency_id):
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role == 'agency_admin' and current_agency_id != agency_id:
        flash('You can only view users from your own agency', 'error')
        return redirect(url_for('agency.list_agencies'))
    
    agency = Agency.query.get_or_404(agency_id)
    users = User.query.filter_by(agency_id=agency_id).all()
    
    return render_template('agency/users.html', agency=agency, users=users)

@agency_bp.route('/<int:agency_id>/create_user', methods=['GET', 'POST'])
@login_required
@role_required('agency_admin')
@log_activity('create_user')
def create_user(agency_id):
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if current_agency_id != agency_id:
        flash('You can only create users for your own agency', 'error')
        return redirect(url_for('agency.list_agencies'))
    
    agency = Agency.query.get_or_404(agency_id)
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        role = request.form.get('role')
        
        # Validation
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('agency/create_user.html', agency=agency)
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return render_template('agency/create_user.html', agency=agency)
        
        # Agency admin can only create staff and salesperson roles
        if role not in ['staff', 'salesperson']:
            flash('You can only create staff and salesperson users', 'error')
            return render_template('agency/create_user.html', agency=agency)
        
        # Create user
        new_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            agency_id=agency_id,
            is_active=True
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash(f'{role.title()} {username} created successfully!', 'success')
        return redirect(url_for('agency.agency_users', agency_id=agency_id))
    
    return render_template('agency/create_user.html', agency=agency)

@agency_bp.route('/<int:agency_id>/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('agency_admin')
@log_activity('edit_user')
def edit_user(agency_id, user_id):
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if current_agency_id != agency_id:
        flash('You can only edit users from your own agency', 'error')
        return redirect(url_for('agency.list_agencies'))
    
    agency = Agency.query.get_or_404(agency_id)
    user = User.query.filter_by(id=user_id, agency_id=agency_id).first_or_404()
    
    # Agency admin cannot edit other agency admins
    if user.role == 'agency_admin':
        flash('You cannot edit other agency administrators', 'error')
        return redirect(url_for('agency.agency_users', agency_id=agency_id))
    
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        role = request.form.get('role')
        
        # Check if email is unique (excluding current user)
        existing = User.query.filter_by(email=user.email).first()
        if existing and existing.id != user.id:
            flash('Email already exists', 'error')
            return render_template('agency/edit_user.html', agency=agency, user=user)
        
        # Agency admin can only assign staff and salesperson roles
        if role not in ['staff', 'salesperson']:
            flash('You can only assign staff and salesperson roles', 'error')
            return render_template('agency/edit_user.html', agency=agency, user=user)
        
        user.role = role
        
        # Handle password change if provided
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash(f'User {user.username} updated successfully!', 'success')
        return redirect(url_for('agency.agency_users', agency_id=agency_id))
    
    return render_template('agency/edit_user.html', agency=agency, user=user)

@agency_bp.route('/<int:agency_id>/users/<int:user_id>/toggle_status', methods=['POST'])
@login_required
@role_required('agency_admin')
@log_activity('toggle_user_status')
def toggle_user_status(agency_id, user_id):
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if current_agency_id != agency_id:
        flash('You can only manage users from your own agency', 'error')
        return redirect(url_for('agency.list_agencies'))
    
    user = User.query.filter_by(id=user_id, agency_id=agency_id).first_or_404()
    
    # Agency admin cannot deactivate other agency admins
    if user.role == 'agency_admin':
        flash('You cannot deactivate other agency administrators', 'error')
        return redirect(url_for('agency.agency_users', agency_id=agency_id))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {status} successfully!', 'success')
    return redirect(url_for('agency.agency_users', agency_id=agency_id))

@agency_bp.route('/<int:agency_id>/delete', methods=['POST'])
@login_required
@role_required('super_admin')
@log_activity('delete_agency')
def delete_agency(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    
    # Check if agency has users
    if agency.users:
        flash('Cannot delete agency with existing users', 'error')
        return redirect(url_for('agency.list_agencies'))
    
    db.session.delete(agency)
    db.session.commit()
    
    flash('Agency deleted successfully!', 'success')
    return redirect(url_for('agency.list_agencies'))
