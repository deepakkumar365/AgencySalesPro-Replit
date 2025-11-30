from flask import render_template, request, redirect, url_for, flash, session, make_response
import csv, io
import re
from datetime import datetime
from sqlalchemy import func, and_
from werkzeug.security import generate_password_hash
from extensions import db
from models import Customer, Location, Agency, User, Product, ProductAgency, Order, CustomerAgency
from customer import customer_bp
from auth.utils import login_required, permission_required, role_required
from utils.decorators import log_activity

@customer_bp.route('/')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff', 'salesperson'])
def list_customers(current_agency_id=None):
    user_role = session.get('role')
    
    # Start with base query using CustomerAgency mapping
    if user_role == 'super_admin':
        query = Customer.query
    else:
        # Filter customers by agency mapping
        query = Customer.query.join(CustomerAgency).filter(
            CustomerAgency.agency_id == current_agency_id,
            CustomerAgency.is_active == True
        )
    
    # Apply filters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    agency_filter = request.args.get('agency')
    location_filter = request.args.get('location')
    status_filter = request.args.get('status')
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Customer.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Customer.created_at <= date_to_obj)
        except ValueError:
            pass
    
    if agency_filter and user_role == 'super_admin':
        # Filter by agency using the mapping table
        query = query.join(CustomerAgency).filter(CustomerAgency.agency_id == agency_filter)
    
    if location_filter:
        query = query.filter(Customer.location_id == location_filter)
    
    if status_filter == 'active':
        query = query.filter(Customer.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Customer.is_active == False)
    
    # Get pagination parameters from request args
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if per_page not in [10, 20, 50, 100]:
        per_page = 20

    # Use the paginate() method on the query
    pagination = query.order_by(Customer.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    # Get filter options
    agencies = []
    locations = []
    
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
        locations = Location.query.filter_by(is_active=True).all()
    else:
        locations = Location.query.filter_by(agency_id=current_agency_id, is_active=True).all()
    
    return render_template('customer/list.html', 
                         pagination=pagination,
                         per_page=per_page,
                         agencies=agencies,
                         locations=locations,
                         filters={
                             'date_from': date_from,
                             'date_to': date_to,
                             'agency': agency_filter,
                             'location': location_filter,
                             'status': status_filter
                         })

@customer_bp.route('/dashboard')
@role_required('customer')
def customer_dashboard():
    """Dashboard for a logged-in customer user."""
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)

    # Assuming a customer user's email matches a customer record's email.
    # This is one way to link a User to a Customer.
    customer_record = Customer.query.filter_by(email=user.email).first()

    # Get subscription if it exists
    subscription = customer_record.subscription if customer_record else None

    return render_template('customer/dashboard.html', user=user, customer=customer_record, subscription=subscription)


@customer_bp.route('/create', methods=['GET', 'POST'])
@login_required
@log_activity('create_customer')
def create_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        customer_code = request.form.get('customer_code', '').strip().upper()
        email = request.form.get('email')
        # Clean phone number: remove non-numeric characters except +
        phone_raw = request.form.get('phone', '')
        phone = re.sub(r'[^0-9+]', '', phone_raw)
        address = request.form.get('address')
        location_id = request.form.get('location_id')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([name, customer_code, phone, location_id]):
            flash('Customer name, customer code, phone number, and location are required.', 'error')
            return render_template('customer/form.html', locations=get_locations_for_user())
        
        # Validate customer code format (6 alphanumeric characters)
        if not re.match(r'^[A-Z0-9]{6}$', customer_code):
            flash('Customer code must be exactly 6 alphanumeric characters (e.g., AB12C3).', 'error')
            return render_template('customer/form.html', locations=get_locations_for_user())
        
        # Check if customer code already exists
        if Customer.query.filter_by(customer_code=customer_code).first():
            flash('Customer code already exists. Please use a different code.', 'error')
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

        # --- User Creation Logic ---
        if user_role in ['super_admin', 'agency_manager', 'agency_admin'] and password:
            if password != confirm_password:
                flash('Passwords do not match.', 'error')
                return render_template('customer/form.html', locations=get_locations_for_user())
            
            if len(password) < 6:
                flash('Password must be at least 6 characters long.', 'error')
                return render_template('customer/form.html', locations=get_locations_for_user())

            # Check for existing user by phone (username) or email
            if User.query.filter((User.username == phone) | (User.email == email)).first():
                flash('A user with this phone number or email already exists.', 'error')
                return render_template('customer/form.html', locations=get_locations_for_user())
        
        # Check for existing customer with the same phone number
        if Customer.query.filter_by(phone=phone).first():
            flash('A customer with this phone number already exists.', 'error')
            return render_template('customer/form.html', locations=get_locations_for_user())
        
        customer = Customer(
            name=name,
            customer_code=customer_code,
            email=email,
            phone=phone,
            address=address,
            location_id=location_id,
            is_active=True
        )
        db.session.add(customer)
        db.session.flush()  # Get customer ID before creating mapping
        
        # Create customer-agency mapping
        customer_agency = CustomerAgency(
            customer_id=customer.id,
            agency_id=location.agency_id,
            is_active=True
        )
        db.session.add(customer_agency)
        
        # Create user only if password was provided by an authorized role
        if user_role in ['super_admin', 'agency_manager', 'agency_admin'] and password:
            user = User(
                username=phone, # Use phone as username
                email=email,
                first_name=name.split(' ')[0],
                last_name=' '.join(name.split(' ')[1:]) if ' ' in name else '',
                role='customer',
                agency_id=location.agency_id,
                is_active=True
            )
            user.set_password(password)
            db.session.add(user)
            flash('Customer and user portal access created successfully!', 'success')
        else:
            flash('Customer created successfully!', 'success')

        db.session.commit()
        
        return redirect(url_for('customer.list_customers'))
    
    return render_template('customer/form.html', locations=get_locations_for_user())

@customer_bp.route('/<int:customer_id>/edit', methods=['GET', 'POST'])
@login_required
@log_activity('edit_customer')
def edit_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions using agency mapping
    if user_role != 'super_admin':
        customer_agency = CustomerAgency.query.filter_by(
            customer_id=customer_id,
            agency_id=current_agency_id,
            is_active=True
        ).first()
        if not customer_agency:
            flash('You can only edit customers from your agency', 'error')
            return redirect(url_for('customer.list_customers'))

    original_email = customer.email  # Capture original email before any changes

    if request.method == 'POST':
        # Update customer fields from form
        customer.name = request.form.get('name')
        customer.email = request.form.get('email')
        # Clean phone number: remove non-numeric characters except +
        phone_raw = request.form.get('phone', '')
        customer.phone = re.sub(r'[^0-9+]', '', phone_raw)
        customer.address = request.form.get('address')
        location_id = request.form.get('location_id')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([customer.name, customer.phone, location_id]):
            flash('Customer name, phone number, and location are required.', 'error')
            return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())
        
        # Validate location
        location = Location.query.get(location_id)
        if not location:
            flash('Invalid location selected', 'error')
            return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())
        
        if user_role != 'super_admin' and location.agency_id != current_agency_id:
            flash('You can only assign customers to your agency locations', 'error')
            return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())
        
        # Update location
        old_location = Location.query.get(customer.location_id)
        customer.location_id = location_id
        
        # Update agency mapping if location's agency changed
        if old_location and old_location.agency_id != location.agency_id:
            # Check if mapping exists for new agency
            existing_mapping = CustomerAgency.query.filter_by(
                customer_id=customer.id,
                agency_id=location.agency_id
            ).first()
            
            if existing_mapping:
                existing_mapping.is_active = True
            else:
                # Create new mapping
                new_mapping = CustomerAgency(
                    customer_id=customer.id,
                    agency_id=location.agency_id,
                    is_active=True
                )
                db.session.add(new_mapping)
        
        # --- User Update Logic ---
        user = User.query.filter_by(email=original_email).first()
        flash_message = 'Customer updated successfully!'

        # Only process user updates if an authorized role is acting
        if user_role in ['super_admin', 'agency_manager', 'agency_admin']:
            if user:
                # Check for username (phone) uniqueness if changed
                if user.username != customer.phone and User.query.filter_by(username=customer.phone).first():
                    flash('Another user with this phone number already exists.', 'error')
                    return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())
                
                # Check for email uniqueness if changed
                if user.email != customer.email and User.query.filter_by(email=customer.email).first():
                    flash('Another user with this email address already exists.', 'error')
                    return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())

                user.username = customer.phone
                user.email = customer.email
                user.agency_id = location.agency_id
                
                # Update password if provided
                if password:
                    if password != confirm_password:
                        flash('Passwords do not match.', 'error')
                        return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())
                    if len(password) < 6:
                        flash('Password must be at least 6 characters long.', 'error')
                        return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())
                    user.set_password(password)
                    if password:
                        flash_message = 'Customer and user password updated successfully!'
            elif password:
                # If a user doesn't exist, we can't update them.
                flash('Cannot set password because no linked user account was found for the original email.', 'warning')

        # --- End User Update Logic ---

        db.session.commit()
        flash(flash_message, 'success')
        return redirect(url_for('customer.list_customers'))
    
    return render_template('customer/form.html', customer=customer, locations=get_locations_for_user())

@customer_bp.route('/<int:customer_id>/toggle_status', methods=['POST'])
@login_required
@log_activity('toggle_customer_status')
def toggle_customer_status(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions using agency mapping
    if user_role != 'super_admin':
        customer_agency = CustomerAgency.query.filter_by(
            customer_id=customer_id,
            agency_id=current_agency_id,
            is_active=True
        ).first()
        if not customer_agency:
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
    
    # Check permissions using agency mapping
    if user_role != 'super_admin':
        customer_agency = CustomerAgency.query.filter_by(
            customer_id=customer_id,
            agency_id=current_agency_id,
            is_active=True
        ).first()
        if not customer_agency:
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
    writer.writerow(['customer_code', 'name', 'email', 'phone', 'address', 'location_name', 'agency_code'])
    
    # Write sample data
    writer.writerow(['CUST01', 'John Doe', 'john@example.com', '5550123', '123 Main St', 'Main Office', 'AGENCY001'])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=customer_import_template.csv'
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
    writer.writerow(['customer_code', 'name', 'email', 'phone', 'address', 'location_name', 'agency_code', 'is_active', 'created_at'])
    
    # Write data
    for customer in customers:
        writer.writerow([
            customer.customer_code,
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
            update_count = 0
            error_count = 0
            errors = []
            
            for row_num, row in enumerate(csv_input, start=2):  # Start from 2 to account for header
                try:
                    # Validate required fields
                    customer_code = row.get('customer_code', '').strip().upper()
                    if not customer_code or not row.get('name', '').strip():
                        errors.append(f"Row {row_num}: Customer Code and Name are required.")
                        error_count += 1
                        continue
                    
                    location_name = row.get('location_name', '').strip() or None
                    agency_code = row.get('agency_code', '').strip() or None
                    agency = None
                    location = None
                    
                    if user_role == 'super_admin':
                        if not agency_code or not location_name:
                            errors.append(f"Row {row_num}: Agency Code and Location Name are required for Super Admin.")
                            error_count += 1
                            continue
                        agency = Agency.query.filter_by(code=agency_code, is_active=True).first()
                        if not agency:
                            errors.append(f"Row {row_num}: Agency with code '{agency_code}' not found or inactive.")
                            error_count += 1
                            continue
                    else: # For agency-level users
                        if agency_code:
                            # If agency code is provided, validate it
                            if agency_code.upper() != Agency.query.get(current_agency_id).code.upper():
                                errors.append(f"Row {row_num}: You can only import customers for your own agency.")
                                error_count += 1
                                continue
                        agency = Agency.query.get(current_agency_id)

                    # Determine location
                    if location_name:
                        # If location name is provided, find it within the agency
                        location = Location.query.filter_by(name=location_name, agency_id=agency.id, is_active=True).first()
                    elif user_role != 'super_admin':
                        # If not provided for an agency user, find the first active location for that agency
                        location = Location.query.filter_by(agency_id=agency.id, is_active=True).first()
                        if location:
                            flash(f"Row {row_num}: No location provided, defaulted to '{location.name}'.", 'info')

                    # Final validation for location
                    if not location:
                        errors.append(f"Row {row_num}: Location '{location_name}' not found for agency '{agency_code}' or inactive")
                        error_count += 1
                        continue
                    
                    # Validate email format if provided
                    email = row.get('email', '').strip()
                    if email and '@' not in email:
                        errors.append(f"Row {row_num}: Invalid email format")
                        error_count += 1
                        continue

                    # Upsert logic: Check if customer exists by customer_code
                    customer = Customer.query.filter_by(customer_code=customer_code).first()

                    if customer:
                        # --- UPDATE EXISTING CUSTOMER ---
                        customer.name = row['name'].strip()
                        customer.email = email if email else customer.email
                        customer.phone = re.sub(r'[^0-9+]', '', row.get('phone', '')) or customer.phone
                        customer.address = row.get('address', '').strip() or customer.address
                        customer.location_id = location.id
                        update_count += 1
                    else:
                        # --- CREATE NEW CUSTOMER ---
                        customer = Customer(
                            customer_code=customer_code,
                            name=row['name'].strip(),
                            email=email if email else None,
                            phone=re.sub(r'[^0-9+]', '', row.get('phone', '')),
                            address=row.get('address', '').strip(),
                            location_id=location.id,
                            is_active=True
                        )
                        db.session.add(customer)
                        db.session.flush()  # Get customer ID before creating mapping
                        success_count += 1

                    # Ensure customer-agency mapping exists and is active
                    customer_agency = CustomerAgency.query.filter_by(
                        customer_id=customer.id,
                        agency_id=agency.id
                    ).first()

                    if customer_agency:
                        if not customer_agency.is_active:
                            customer_agency.is_active = True
                    else:
                        new_mapping = CustomerAgency(
                            customer_id=customer.id,
                            agency_id=agency.id,
                            is_active=True
                        )
                        db.session.add(new_mapping)
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1
            
            if success_count > 0 or update_count > 0:
                db.session.commit()
            
            if success_count > 0:
                flash(f'Successfully imported {success_count} customers', 'success')
            
            if update_count > 0:
                flash(f'Successfully updated {update_count} customers', 'info')
            
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

@customer_bp.route('/products')
@login_required
@role_required('customer')
def view_products():
    """
    Displays a product catalog for the logged-in customer.
    Shows only products actively mapped to the customer's agency.
    """
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    # Find the customer record linked to the user's email
    customer = Customer.query.filter(func.lower(Customer.email) == func.lower(user.email)).first()

    if not customer or not customer.location or not customer.location.agency_id:
        flash('Could not determine your agency. Please contact support.', 'error')
        return render_template('customer/product_catalog.html', products=[], agency_name=None)

    agency_id = customer.location.agency_id
    agency_name = customer.location.agency.name

    # Query for products actively mapped to the customer's agency
    # This joins Product and ProductAgency and filters by the agency_id and active status
    product_rows = db.session.query(
        Product,
        ProductAgency
    ).join(
        ProductAgency,
        and_(
            ProductAgency.product_id == Product.id,
            ProductAgency.agency_id == agency_id,
            ProductAgency.is_active == True
        )
    ).filter(Product.is_active == True).order_by(Product.name).all()

    # Prepare products for display, using agency-specific overrides where available
    products_to_display = []
    for product, pa_mapping in product_rows:
        products_to_display.append({
            'id': product.id,
            'name': pa_mapping.display_name or product.name,
            'sku': product.sku,
            'description': product.description,
            'price': pa_mapping.sell_price if pa_mapping.sell_price is not None else product.sell_price,
            'category': product.category_ref.name if product.category_ref else 'Uncategorized'
        })

    return render_template('customer/product_catalog.html', 
                           products=products_to_display, 
                           agency_name=agency_name)

@customer_bp.route('/orders')
@login_required
@role_required('customer')
def view_orders():
    """
    Displays a list of orders for the logged-in customer.
    """
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    
    # Find the customer record linked to the user's email
    customer = Customer.query.filter(func.lower(Customer.email) == func.lower(user.email)).first()

    if not customer:
        flash('Could not find your customer profile. Please contact support.', 'error')
        return render_template('customer/my_orders.html', orders=[])

    # Fetch all orders for this customer, newest first
    orders = Order.query.filter_by(customer_id=customer.id).order_by(Order.created_at.desc()).all()

    status_classes = {
        'pending': 'bg-warning',
        'confirmed': 'bg-info',
        'shipped': 'bg-primary',
        'delivered': 'bg-success',
        'cancelled': 'bg-danger',
    }

    return render_template('customer/my_orders.html', orders=orders, status_classes=status_classes)
