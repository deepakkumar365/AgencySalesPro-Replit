from flask import render_template, request, redirect, url_for, flash, session, make_response
import csv, io
from app import db
from models import Customer, Location, Agency
from customer import customer_bp
from auth.utils import login_required, agency_access_required, role_required
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

# Customer Import/Export Routes

@customer_bp.route('/download_template')
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
def download_customer_template():
    """Download CSV template for customer import"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow(['name', 'email', 'phone', 'address', 'location_name', 'agency_code'])
    
    # Write sample data
    writer.writerow(['John Doe', 'john@example.com', '555-0123', '123 Main St', 'Main Office', 'AGENCY001'])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=customer_template.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response

@customer_bp.route('/export')
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
def export_customers():
    """Export existing customers to CSV"""
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Get customers based on user role
    if user_role == 'super_admin':
        customers = Customer.query.join(Location).join(Agency).all()
    else:
        customers = Customer.query.join(Location).filter(Location.agency_id == current_agency_id).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['name', 'email', 'phone', 'address', 'location_name', 'agency_code', 'is_active', 'created_at'])
    
    # Write data
    for customer in customers:
        writer.writerow([
            customer.name,
            customer.email or '',
            customer.phone or '',
            customer.address or '',
            customer.location.name,
            customer.location.agency.code,
            'Yes' if customer.is_active else 'No',
            customer.created_at.strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=customers_export.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response

@customer_bp.route('/import', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'agency_admin', 'staff')
@log_activity('import_customers')
def import_customers():
    """Import customers from CSV file"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('customer.import_customers'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('customer.import_customers'))
        
        if not file.filename.lower().endswith('.csv'):
            flash('Please upload a CSV file', 'error')
            return redirect(url_for('customer.import_customers'))
        
        try:
            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            
            user_role = session.get('role')
            current_agency_id = session.get('agency_id')
            
            success_count = 0
            error_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_input, start=2):  # Start from 2 to account for header
                try:
                    # Validate required fields
                    if not row.get('name') or not row.get('name').strip():
                        errors.append(f"Row {row_num}: Customer name is required")
                        error_count += 1
                        continue
                    
                    location_name = row.get('location_name', '').strip()
                    agency_code = row.get('agency_code', '').strip()
                    
                    if not location_name or not agency_code:
                        errors.append(f"Row {row_num}: Location name and agency code are required")
                        error_count += 1
                        continue
                    
                    # Find agency by code
                    agency = Agency.query.filter_by(code=agency_code, is_active=True).first()
                    if not agency:
                        errors.append(f"Row {row_num}: Agency with code '{agency_code}' not found or inactive")
                        error_count += 1
                        continue
                    
                    # Check permissions for non-super admin users
                    if user_role != 'super_admin' and agency.id != current_agency_id:
                        errors.append(f"Row {row_num}: You can only import customers for your agency")
                        error_count += 1
                        continue
                    
                    # Find location by name and agency
                    location = Location.query.filter_by(name=location_name, agency_id=agency.id, is_active=True).first()
                    if not location:
                        errors.append(f"Row {row_num}: Location '{location_name}' not found for agency '{agency_code}' or inactive")
                        error_count += 1
                        continue
                    
                    # Check if customer already exists (by name and location)
                    existing_customer = Customer.query.filter_by(name=row['name'].strip(), location_id=location.id).first()
                    if existing_customer:
                        errors.append(f"Row {row_num}: Customer '{row['name'].strip()}' already exists at location '{location_name}'")
                        error_count += 1
                        continue
                    
                    # Validate email format if provided
                    email = row.get('email', '').strip()
                    if email and '@' not in email:
                        errors.append(f"Row {row_num}: Invalid email format")
                        error_count += 1
                        continue
                    
                    # Create new customer
                    customer = Customer(
                        name=row['name'].strip(),
                        email=email if email else None,
                        phone=row.get('phone', '').strip(),
                        address=row.get('address', '').strip(),
                        location_id=location.id,
                        is_active=True
                    )
                    
                    db.session.add(customer)
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1
            
            if success_count > 0:
                db.session.commit()
                flash(f'Successfully imported {success_count} customers', 'success')
            
            if error_count > 0:
                flash(f'{error_count} errors occurred during import', 'warning')
                # Show first 5 errors
                for error in errors[:5]:
                    flash(error, 'error')
                if len(errors) > 5:
                    flash(f'... and {len(errors) - 5} more errors', 'error')
            
            return redirect(url_for('customer.list_customers'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing file: {str(e)}', 'error')
            return redirect(url_for('customer.import_customers'))
    
    return render_template('customer/import.html')
