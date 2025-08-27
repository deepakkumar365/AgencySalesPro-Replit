from flask import render_template, request, redirect, url_for, flash, session
from app import db
from models import Location, Agency
from location import location_bp
from auth.utils import login_required, role_required, agency_access_required
from utils.decorators import log_activity

@location_bp.route('/')
@login_required
@agency_access_required
def list_locations(current_agency_id=None):
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        locations = Location.query.all()
    else:
        locations = Location.query.filter_by(agency_id=current_agency_id).all()
    
    return render_template('location/list.html', locations=locations)

@location_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
@log_activity('create_location')
def create_location():
    if request.method == 'POST':
        name = request.form.get('name')
        address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        zip_code = request.form.get('zip_code')
        phone = request.form.get('phone')
        agency_id = request.form.get('agency_id')
        
        user_role = session.get('role')
        current_agency_id = session.get('agency_id')
        
        if not name:
            flash('Location name is required', 'error')
            return render_template('location/form.html', agencies=get_agencies_for_user())
        
        # Non-super admin users can only create locations for their agency
        if user_role != 'super_admin':
            agency_id = current_agency_id
        
        if not agency_id:
            flash('Agency is required', 'error')
            return render_template('location/form.html', agencies=get_agencies_for_user())
        
        location = Location(
            name=name,
            address=address,
            city=city,
            state=state,
            zip_code=zip_code,
            phone=phone,
            agency_id=agency_id,
            is_active=True
        )
        
        db.session.add(location)
        db.session.commit()
        
        flash('Location created successfully!', 'success')
        return redirect(url_for('location.list_locations'))
    
    return render_template('location/form.html', agencies=get_agencies_for_user())

@location_bp.route('/<int:location_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
@log_activity('edit_location')
def edit_location(location_id):
    location = Location.query.get_or_404(location_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and location.agency_id != current_agency_id:
        flash('You can only edit locations from your agency', 'error')
        return redirect(url_for('location.list_locations'))
    
    if request.method == 'POST':
        location.name = request.form.get('name')
        location.address = request.form.get('address')
        location.city = request.form.get('city')
        location.state = request.form.get('state')
        location.zip_code = request.form.get('zip_code')
        location.phone = request.form.get('phone')
        
        # Super admin can change agency
        if user_role == 'super_admin':
            agency_id = request.form.get('agency_id')
            if agency_id:
                location.agency_id = agency_id
        
        if not location.name:
            flash('Location name is required', 'error')
            return render_template('location/form.html', location=location, agencies=get_agencies_for_user())
        
        db.session.commit()
        flash('Location updated successfully!', 'success')
        return redirect(url_for('location.list_locations'))
    
    return render_template('location/form.html', location=location, agencies=get_agencies_for_user())

@location_bp.route('/<int:location_id>/toggle_status', methods=['POST'])
@login_required
@role_required('super_admin', 'agency_admin')
@log_activity('toggle_location_status')
def toggle_location_status(location_id):
    location = Location.query.get_or_404(location_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and location.agency_id != current_agency_id:
        flash('You can only modify locations from your agency', 'error')
        return redirect(url_for('location.list_locations'))
    
    location.is_active = not location.is_active
    db.session.commit()
    
    status = 'activated' if location.is_active else 'deactivated'
    flash(f'Location {status} successfully!', 'success')
    return redirect(url_for('location.list_locations'))

@location_bp.route('/<int:location_id>/delete', methods=['POST'])
@login_required
@role_required('super_admin', 'agency_admin')
@log_activity('delete_location')
def delete_location(location_id):
    location = Location.query.get_or_404(location_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and location.agency_id != current_agency_id:
        flash('You can only delete locations from your agency', 'error')
        return redirect(url_for('location.list_locations'))
    
    # Check if location has customers
    if location.customers:
        flash('Cannot delete location with existing customers', 'error')
        return redirect(url_for('location.list_locations'))
    
    db.session.delete(location)
    db.session.commit()
    
    flash('Location deleted successfully!', 'success')
    return redirect(url_for('location.list_locations'))

def get_agencies_for_user():
    """Get agencies based on current user role"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        return Agency.query.filter_by(is_active=True).all()
    else:
        agency_id = session.get('agency_id')
        return Agency.query.filter_by(id=agency_id, is_active=True).all()
