from flask import render_template, request, redirect, url_for, flash, session
from app import db
from models import Customer, Location, Agency
from customer import customer_bp
from auth.utils import login_required, agency_access_required
from utils.decorators import log_activity

@customer_bp.route('/')
@login_required
@agency_access_required
def list_customers(current_agency_id=None):
    user_role = session.get('role')
    
    # Start with base query
    if user_role == 'super_admin':
        query = Customer.query.join(Location)
    else:
        query = Customer.query.join(Location).filter(Location.agency_id == current_agency_id)
    
    # Apply filters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    agency_filter = request.args.get('agency')
    location_filter = request.args.get('location')
    status_filter = request.args.get('status')
    
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Customer.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Customer.created_at <= date_to_obj)
        except ValueError:
            pass
    
    if agency_filter and user_role == 'super_admin':
        query = query.filter(Location.agency_id == agency_filter)
    
    if location_filter:
        query = query.filter(Customer.location_id == location_filter)
    
    if status_filter == 'active':
        query = query.filter(Customer.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Customer.is_active == False)
    
    customers = query.order_by(Customer.created_at.desc()).all()
    
    # Get filter options
    agencies = []
    locations = []
    
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
        locations = Location.query.filter_by(is_active=True).all()
    else:
        locations = Location.query.filter_by(agency_id=current_agency_id, is_active=True).all()
    
    return render_template('customer/list.html', 
                         customers=customers,
                         agencies=agencies,
                         locations=locations,
                         filters={
                             'date_from': date_from,
                             'date_to': date_to,
                             'agency': agency_filter,
                             'location': location_filter,
                             'status': status_filter
                         })

@customer_bp.route('/create', methods=['GET', 'POST'])
@login_required
@log_activity('create_customer')
def create_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        location_id = request.form.get('location_id')
        
        if not name or not location_id:
            flash('Customer name and location are required', 'error')
            return render_template('customer/form.html', locations=get_locations_for_user())
        
        # Validate location belongs to user's agency
        user_role = session.get('role')
        current_agency_id = session.get('agency_id')
        
        location = Location.query.get(location_id)
        if not location:
            flash('Invalid location selected', 'error')
            return render_template('customer/form.html', locations=get_locations_for_user())
        
        if user_role != 'super_admin' and location.agency_id != current_agency_id:
            flash('You can only create customers for your agency locations', 'error')
            return render_template('customer/form.html', locations=get_locations_for_user())
        
        customer = Customer(
            name=name,
            email=email,
            phone=phone,
            address=address,
            location_id=location_id,
            is_active=True
        )
        
        db.session.add(customer)
        db.session.commit()
        
        flash('Customer created successfully!', 'success')
        return redirect(url_for('customer.list_customers'))
    
    return render_template('customer/form.html', locations=get_locations_for_user())

@customer_bp.route('/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
@log_activity('edit_customer')
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and customer.location.agency_id != current_agency_id:
        flash('You can only edit customers from your agency', 'error')
        return redirect(url_for('customer.list_customers'))
    
    if request.method == 'POST':
        customer.name = request.form.get('name')
        customer.email = request.form.get('email')
        customer.phone = request.form.get('phone')
        customer.address = request.form.get('address')
        location_id = request.form.get('location_id')
        
        if not customer.name or not location_id:
            flash('Customer name and location are required', 'error')
            return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())
        
        # Validate location
        location = Location.query.get(location_id)
        if not location:
            flash('Invalid location selected', 'error')
            return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())
        
        if user_role != 'super_admin' and location.agency_id != current_agency_id:
            flash('You can only assign customers to your agency locations', 'error')
            return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())
        
        customer.location_id = location_id
        
        db.session.commit()
        flash('Customer updated successfully!', 'success')
        return redirect(url_for('customer.list_customers'))
    
    return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())

@customer_bp.route('/<int:customer_id>/toggle_status', methods=['POST'])
@login_required
@log_activity('toggle_customer_status')
def toggle_customer_status(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and customer.location.agency_id != current_agency_id:
        flash('You can only modify customers from your agency', 'error')
        return redirect(url_for('customer.list_customers'))
    
    customer.is_active = not customer.is_active
    db.session.commit()
    
    status = 'activated' if customer.is_active else 'deactivated'
    flash(f'Customer {status} successfully!', 'success')
    return redirect(url_for('customer.list_customers'))

@customer_bp.route('/<int:customer_id>/delete', methods=['POST'])
@login_required
@log_activity('delete_customer')
def delete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and customer.location.agency_id != current_agency_id:
        flash('You can only delete customers from your agency', 'error')
        return redirect(url_for('customer.list_customers'))
    
    # Check if customer has orders
    if customer.orders:
        flash('Cannot delete customer with existing orders', 'error')
        return redirect(url_for('customer.list_customers'))
    
    db.session.delete(customer)
    db.session.commit()
    
    flash('Customer deleted successfully!', 'success')
    return redirect(url_for('customer.list_customers'))

def get_locations_for_user():
    """Get locations based on current user role"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        return Location.query.filter_by(is_active=True).all()
    else:
        agency_id = session.get('agency_id')
        return Location.query.filter_by(agency_id=agency_id, is_active=True).all()
