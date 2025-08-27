from flask import render_template, request, redirect, url_for, flash, session
from app import db
from models import User, Agency
from salesperson import salesperson_bp
from auth.utils import login_required, role_required, agency_access_required
from utils.decorators import log_activity

@salesperson_bp.route('/')
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
@agency_access_required
def list_salespersons(current_agency_id=None):
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        salespersons = User.query.filter_by(role='salesperson').all()
    else:
        salespersons = User.query.filter_by(role='salesperson', agency_id=current_agency_id).all()
    
    return render_template('salesperson/list.html', salespersons=salespersons)

@salesperson_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'agency_admin')
@log_activity('create_salesperson')
def create_salesperson():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        agency_id = request.form.get('agency_id')
        
        user_role = session.get('role')
        current_agency_id = session.get('agency_id')
        
        # Validation
        if not all([username, email, password, first_name, last_name]):
            flash('All fields are required', 'error')
            return render_template('salesperson/form.html', agencies=get_agencies_for_user())
        
        # Agency admin can only create salespersons for their agency
        if user_role == 'agency_admin':
            agency_id = current_agency_id
        
        if not agency_id:
            flash('Agency is required', 'error')
            return render_template('salesperson/form.html', agencies=get_agencies_for_user())
        
        # Check if username exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('salesperson/form.html', agencies=get_agencies_for_user())
        
        # Check if email exists
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return render_template('salesperson/form.html', agencies=get_agencies_for_user())
        
        salesperson = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='salesperson',
            agency_id=agency_id,
            is_active=True
        )
        salesperson.set_password(password)
        
        db.session.add(salesperson)
        db.session.commit()
        
        flash('Salesperson created successfully!', 'success')
        return redirect(url_for('salesperson.list_salespersons'))
    
    return render_template('salesperson/form.html', agencies=get_agencies_for_user())

@salesperson_bp.route('/<int:salesperson_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'agency_admin')
@log_activity('edit_salesperson')
def edit_salesperson(salesperson_id):
    salesperson = User.query.filter_by(id=salesperson_id, role='salesperson').first_or_404()
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role == 'agency_admin' and salesperson.agency_id != current_agency_id:
        flash('You can only edit salespersons from your agency', 'error')
        return redirect(url_for('salesperson.list_salespersons'))
    
    if request.method == 'POST':
        salesperson.username = request.form.get('username')
        salesperson.email = request.form.get('email')
        salesperson.first_name = request.form.get('first_name')
        salesperson.last_name = request.form.get('last_name')
        
        # Update password if provided
        new_password = request.form.get('password')
        if new_password:
            salesperson.set_password(new_password)
        
        # Agency admin cannot change agency
        if user_role == 'super_admin':
            agency_id = request.form.get('agency_id')
            if agency_id:
                salesperson.agency_id = agency_id
        
        # Check for duplicate username (excluding current user)
        existing_user = User.query.filter_by(username=salesperson.username).first()
        if existing_user and existing_user.id != salesperson.id:
            flash('Username already exists', 'error')
            return render_template('salesperson/form.html', salesperson=salesperson, agencies=get_agencies_for_user())
        
        # Check for duplicate email (excluding current user)
        existing_email = User.query.filter_by(email=salesperson.email).first()
        if existing_email and existing_email.id != salesperson.id:
            flash('Email already exists', 'error')
            return render_template('salesperson/form.html', salesperson=salesperson, agencies=get_agencies_for_user())
        
        db.session.commit()
        flash('Salesperson updated successfully!', 'success')
        return redirect(url_for('salesperson.list_salespersons'))
    
    return render_template('salesperson/form.html', salesperson=salesperson, agencies=get_agencies_for_user())

@salesperson_bp.route('/<int:salesperson_id>/toggle_status', methods=['POST'])
@login_required
@role_required('super_admin', 'agency_admin')
@log_activity('toggle_salesperson_status')
def toggle_salesperson_status(salesperson_id):
    salesperson = User.query.filter_by(id=salesperson_id, role='salesperson').first_or_404()
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role == 'agency_admin' and salesperson.agency_id != current_agency_id:
        flash('You can only modify salespersons from your agency', 'error')
        return redirect(url_for('salesperson.list_salespersons'))
    
    salesperson.is_active = not salesperson.is_active
    db.session.commit()
    
    status = 'activated' if salesperson.is_active else 'deactivated'
    flash(f'Salesperson {status} successfully!', 'success')
    return redirect(url_for('salesperson.list_salespersons'))

@salesperson_bp.route('/<int:salesperson_id>/delete', methods=['POST'])
@login_required
@role_required('super_admin', 'agency_admin')
@log_activity('delete_salesperson')
def delete_salesperson(salesperson_id):
    salesperson = User.query.filter_by(id=salesperson_id, role='salesperson').first_or_404()
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role == 'agency_admin' and salesperson.agency_id != current_agency_id:
        flash('You can only delete salespersons from your agency', 'error')
        return redirect(url_for('salesperson.list_salespersons'))
    
    # Check if salesperson has orders
    if salesperson.orders:
        flash('Cannot delete salesperson with existing orders', 'error')
        return redirect(url_for('salesperson.list_salespersons'))
    
    db.session.delete(salesperson)
    db.session.commit()
    
    flash('Salesperson deleted successfully!', 'success')
    return redirect(url_for('salesperson.list_salespersons'))

def get_agencies_for_user():
    """Get agencies based on current user role"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        return Agency.query.filter_by(is_active=True).all()
    else:
        agency_id = session.get('agency_id')
        return Agency.query.filter_by(id=agency_id, is_active=True).all()
