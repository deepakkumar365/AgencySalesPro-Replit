from flask import render_template, request, redirect, url_for, flash, session
import re
from extensions import db
from models import Agency, User, CustomerAgency, Location
from . import agency_bp
from auth.utils import login_required, role_required
from utils.decorators import log_activity
from utils.pagination import apply_pagination

@agency_bp.route('/')
@role_required('super_admin', 'agency_admin', 'agency_manager')
def list_agencies():
    user_role = session.get('role')
    user_id = session.get('user_id')
    search = request.args.get('search')
    
    # Subquery for user count per agency
    user_count_subquery = db.session.query(
        User.agency_id,
        db.func.count(User.id).label('user_count')
    ).group_by(User.agency_id).subquery()

    # Subquery for customer count per agency using the mapping table
    customer_count_subquery = db.session.query(
        CustomerAgency.agency_id,
        db.func.count(CustomerAgency.customer_id).label('customer_count')
    ).group_by(CustomerAgency.agency_id).subquery()

    # Main query to fetch agencies with additional data
    query = db.session.query(
        Agency,
        User.username.label('manager_username'),
        db.func.coalesce(user_count_subquery.c.user_count, 0).label('login_id_count'),
        db.func.coalesce(customer_count_subquery.c.customer_count, 0).label('customer_count')
    ).outerjoin(User, Agency.agency_manager_id == User.id) \
     .outerjoin(user_count_subquery, Agency.id == user_count_subquery.c.agency_id) \
     .outerjoin(customer_count_subquery, Agency.id == customer_count_subquery.c.agency_id)
    
    # Role-based filtering
    if user_role == 'agency_manager':
        query = query.filter(Agency.agency_manager_id == user_id)
    elif user_role == 'agency_admin':
        agency_id = session.get('agency_id')
        query = query.filter(Agency.id == agency_id)

    if search:
        query = query.filter(db.or_(
            Agency.name.ilike(f'%{search}%'),
            Agency.code.ilike(f'%{search}%'),
            User.username.ilike(f'%{search}%')
        ))

    pagination = apply_pagination(query.order_by(Agency.name))
    
    return render_template('agency/list.html', pagination=pagination, search=search)

@agency_bp.route('/create', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_manager')
@log_activity('create_agency')
def create_agency():
    user_role = session.get('role')
    user_id = session.get('user_id')

    if request.method == 'POST':
        name = request.form.get('name')
        # Get split address fields
        address1 = request.form.get('address1', '').strip()
        address2 = request.form.get('address2', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        country = request.form.get('country', '').strip()
        registration_number = request.form.get('registration_number', '').strip()
        
        # Combine address fields for backward compatibility with old 'address' field
        address_parts = [address1, address2, city, state, country]
        address = ', '.join([part for part in address_parts if part])
        
        # Clean phone number: remove non-numeric characters except +
        phone_raw = request.form.get('phone', '')
        phone = re.sub(r'[^0-9+]', '', phone_raw)
        email = request.form.get('email')
        
        # Validate required fields
        if not name:
            flash('Agency Name is required', 'error')
            return redirect(url_for('agency.create_agency'))
        
        if not address1 or not city or not state or not country:
            flash('Address Line 1, City, State, and Country are required', 'error')
            return redirect(url_for('agency.create_agency'))
        
        # Auto-generate a unique agency code
        words = name.strip().split()
        base_code = "".join([word[:2] for word in words]).upper()
        
        # Fallback for empty or very short names
        if not base_code:
            base_code = "XX"

        new_code = base_code
        counter = 1
        while Agency.query.filter_by(code=new_code).first():
            new_code = f"{base_code}{counter}"
            counter += 1

        # Determine manager_id based on role
        if user_role == 'agency_manager':
            manager_id = user_id
        else: # super_admin
            manager_id = request.form.get('agency_manager_id')

        agency = Agency(
            name=name,
            code=new_code,
            address=address,
            address1=address1,
            address2=address2,
            city=city,
            state=state,
            country=country,
            registration_number=registration_number,
            phone=phone,
            email=email,
            is_active=True,
            agency_manager_id=int(manager_id) if manager_id else None
        )
        
        db.session.add(agency)
        db.session.commit()
        
        flash('Agency created successfully! Next, set up the default users.', 'success')
        return redirect(url_for('agency.setup_users', agency_id=agency.id))
    
    # Get potential managers for the dropdown
    managers = []
    if user_role == 'super_admin':
        managers = User.query.filter(User.role.in_(['agency_manager', 'super_admin'])).all()

    return render_template('agency/form.html', managers=managers, user_role=user_role)

@agency_bp.route('/<int:agency_id>/setup/users', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_manager')
def setup_users(agency_id):
    """Wizard step 1: Create default users for a new agency."""
    from models import User
    agency = Agency.query.get_or_404(agency_id)

    if request.method == 'POST':
        users_to_create = request.form.getlist('create_user_role')
        created_count = 0
        
        for role in users_to_create:
            email = request.form.get(f'email_{role}')
            password = request.form.get(f'password_{role}')

            if not email or not password:
                flash(f'Email and password are required for the {role} user.', 'error')
                continue

            username_suffix_map = {
                'agency_admin': 'admin',
                'staff': 'staff',
                'salesperson': 'sales'
            }
            username_suffix = username_suffix_map.get(role, 'user')
            
            username = f"{agency.code.lower()}_{username_suffix}"

            # Check for uniqueness
            if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
                flash(f'Username ({username}) or email ({email}) already exists. Please choose another.', 'error')
                continue

            new_user = User(
                username=username,
                email=email,
                role=role,
                agency_id=agency.id,
                is_active=True
            )
            new_user.set_password(password)
            db.session.add(new_user)
            created_count += 1

        if created_count > 0:
            db.session.commit()
            flash(f'{created_count} user(s) created. Now, create a mandatory location for the agency.', 'success')
            return redirect(url_for('agency.setup_location', agency_id=agency.id))
        else:
            flash('No users were created. Please correct the errors and try again.', 'warning')

    default_users = [
        {'role': 'agency_admin', 'name': 'Agency Admin'},
        {'role': 'staff', 'name': 'Staff'},
        {'role': 'salesperson', 'name': 'Salesperson'}
    ]
    return render_template('agency/setup_users.html', agency=agency, default_users=default_users)

@agency_bp.route('/<int:agency_id>/setup/location', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_manager')
def setup_location(agency_id):
    """Wizard step 2: Create the first location for a new agency."""
    from models import Location
    agency = Agency.query.get_or_404(agency_id)

    if request.method == 'POST':
        name = request.form.get('name')
        if not name:
            flash('Location name is required.', 'error')
        else:
            new_location = Location(
                name=name,
                address=request.form.get('address'),
                agency_id=agency.id,
                is_active=True
            )
            db.session.add(new_location)
            db.session.commit()
            flash(f'Agency "{agency.name}" setup is complete!', 'success')
            return redirect(url_for('agency.list_agencies'))

    return render_template('agency/setup_location.html', agency=agency)

@agency_bp.route('/<int:agency_id>/edit', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_admin', 'agency_manager')
@log_activity('edit_agency')
def edit_agency(agency_id):
    user_role = session.get('role')
    agency = Agency.query.get_or_404(agency_id)
    
    if request.method == 'POST':
        agency.name = request.form.get('name')
        agency.code = request.form.get('code')
        
        # Get split address fields
        address1 = request.form.get('address1', '').strip()
        address2 = request.form.get('address2', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        country = request.form.get('country', '').strip()
        registration_number = request.form.get('registration_number', '').strip()
        
        # Combine address fields for backward compatibility with old 'address' field
        address_parts = [address1, address2, city, state, country]
        agency.address = ', '.join([part for part in address_parts if part])
        
        # Update split address fields
        agency.address1 = address1
        agency.address2 = address2
        agency.city = city
        agency.state = state
        agency.country = country
        agency.registration_number = registration_number
        
        # Clean phone number: remove non-numeric characters except +
        phone_raw = request.form.get('phone', '')
        agency.phone = re.sub(r'[^0-9+]', '', phone_raw)
        agency.email = request.form.get('email')
        manager_id = request.form.get('agency_manager_id')
        
        if not agency.name or not agency.code:
            flash('Name and code are required', 'error')
            return redirect(url_for('agency.edit_agency', agency_id=agency_id))
        
        if not address1 or not city or not state or not country:
            flash('Address Line 1, City, State, and Country are required', 'error')
            return redirect(url_for('agency.edit_agency', agency_id=agency_id))
        
        # Check if code already exists (excluding current agency)
        existing = Agency.query.filter_by(code=agency.code).first()
        if existing and existing.id != agency.id:
            flash('Agency code already exists', 'error')
            return redirect(url_for('agency.edit_agency', agency_id=agency_id))

        if user_role == 'super_admin':
            agency.agency_manager_id = int(manager_id) if manager_id else None
        db.session.commit()
        flash('Agency updated successfully!', 'success')
        return redirect(url_for('agency.list_agencies'))
    
    # Get potential managers for the dropdown
    managers = User.query.filter(User.role.in_(['agency_manager', 'super_admin'])).all() if user_role == 'super_admin' else []
    return render_template('agency/form.html', agency=agency, managers=managers)

@agency_bp.route('/<int:agency_id>/toggle_status', methods=['POST'])
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
@role_required('super_admin', 'agency_admin', 'agency_manager')
def agency_users(agency_id):
    agency = Agency.query.get_or_404(agency_id)
    
    # Use the apply_pagination() method on the query
    pagination = apply_pagination(User.query.filter_by(agency_id=agency_id).order_by(User.created_at.desc()))
    
    return render_template(
        'agency/users.html', 
        agency=agency, 
        pagination=pagination
    )

@agency_bp.route('/<int:agency_id>/create_user', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_admin', 'agency_manager')
@log_activity('create_user')
def create_user(agency_id):
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
@role_required('super_admin', 'agency_admin', 'agency_manager')
@log_activity('edit_user')
def edit_user(agency_id, user_id):
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
@role_required('super_admin', 'agency_admin', 'agency_manager')
@log_activity('toggle_user_status')
def toggle_user_status(agency_id, user_id):
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
