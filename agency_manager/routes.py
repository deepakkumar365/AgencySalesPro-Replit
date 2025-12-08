from flask import render_template, request, redirect, url_for, flash, session
from sqlalchemy import func

from werkzeug.security import generate_password_hash
from extensions import db
from models import Agency, User, ActivityLog
from auth.utils import permission_required
from . import agency_manager_bp
from utils.pagination import apply_pagination


@agency_manager_bp.route('/dashboard')
@permission_required(roles=['agency_manager'])
def dashboard():
    """Redirects agency managers to the main dashboard, which will show their scoped data."""
    return redirect(url_for('super_admin.dashboard'))


@agency_manager_bp.route('/users')
@permission_required(roles=['agency_manager'])
def manage_users():
    user_id = session.get('user_id')
    agency_filter = request.args.get('agency_filter', type=int)

    # Agencies managed by this manager
    managed_agencies = Agency.query.filter_by(agency_manager_id=user_id).order_by(Agency.name).all()
    managed_agency_ids = [agency.id for agency in managed_agencies]

    # Base query for users in managed agencies
    query = User.query.filter(User.agency_id.in_(managed_agency_ids))

    # If a specific agency is filtered, ensure it's one they manage
    if agency_filter and agency_filter in managed_agency_ids:
        query = query.filter(User.agency_id == agency_filter)

    pagination = apply_pagination(query)

    return render_template(
        'super_admin/users.html',
        pagination=pagination,
        agencies_for_filter=managed_agencies,
        current_agency_filter=agency_filter,
    )


@agency_manager_bp.route('/users/create', methods=['GET', 'POST'])
@permission_required(roles=['agency_manager'])
def create_user():
    manager_id = session.get('user_id')
    managed_agencies = Agency.query.filter_by(agency_manager_id=manager_id).all()
    managed_agency_ids = [agency.id for agency in managed_agencies]
    editable_roles = ['agency_admin', 'staff', 'salesperson', 'pos_user']

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        agency_id = request.form.get('agency_id')

        if not all([username, email, password, role, agency_id]):
            flash('All fields are required.', 'error')
            return render_template('super_admin/edit_user.html', agencies=managed_agencies, roles=editable_roles, is_new=True)

        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or email already exists.', 'error')
            return render_template('super_admin/edit_user.html', agencies=managed_agencies, roles=editable_roles, is_new=True)

        if role not in editable_roles:
            flash('You cannot assign this role.', 'error')
            return render_template('super_admin/edit_user.html', agencies=managed_agencies, roles=editable_roles, is_new=True)

        if int(agency_id) not in managed_agency_ids:
            flash('You can only assign users to agencies you manage.', 'error')
            return render_template('super_admin/edit_user.html', agencies=managed_agencies, roles=editable_roles, is_new=True)

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            role=role,
            agency_id=int(agency_id),
            is_active=True
        )
        db.session.add(new_user)
        db.session.commit()
        flash(f'User {username} created successfully!', 'success')
        return redirect(url_for('agency_manager.manage_users'))

    return render_template('super_admin/edit_user.html', agencies=managed_agencies, roles=editable_roles, is_new=True)

@agency_manager_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@permission_required(roles=['agency_manager'])
def edit_user(user_id):
    # Ensure the user being edited belongs to an agency managed by the current manager
    manager_id = session.get('user_id')
    managed_agencies = Agency.query.filter_by(agency_manager_id=manager_id).all()
    managed_agency_ids = [agency.id for agency in managed_agencies]

    user = User.query.get_or_404(user_id)
    if user.agency_id not in managed_agency_ids:
        flash('You do not have permission to edit this user.', 'error')
        return redirect(url_for('agency_manager.manage_users'))

    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        role = request.form.get('role')
        agency_id = request.form.get('agency_id')

        # Prevent assigning the agency_manager role directly
        if role == 'agency_manager':
            flash('You cannot assign the Agency Manager role.', 'error')
            return render_template('super_admin/edit_user.html', user=user, agencies=managed_agencies,
                                   roles=['agency_admin', 'staff', 'salesperson', 'pos_user'])

        if agency_id and int(agency_id) not in managed_agency_ids:
            flash('You can only assign users to agencies you manage.', 'error')
            return render_template('super_admin/edit_user.html', user=user, agencies=managed_agencies,
                                   roles=['agency_admin', 'staff', 'salesperson', 'pos_user'])

        user.role = role
        user.agency_id = int(agency_id) if agency_id else None

        db.session.commit()
        flash(f'User {user.username} updated successfully!', 'success')
        return redirect(url_for('agency_manager.manage_users'))

    # Agency managers can assign these roles
    editable_roles = ['agency_admin', 'staff', 'salesperson', 'pos_user']
    return render_template('super_admin/edit_user.html', user=user, agencies=managed_agencies, roles=editable_roles)


@agency_manager_bp.route('/activities')
@permission_required(roles=['agency_manager'])
def view_activities():
    # Scoped to activities within managed agencies
    manager_id = session.get('user_id')
    managed_agencies = Agency.query.filter_by(agency_manager_id=manager_id).all()
    managed_agency_ids = [agency.id for agency in managed_agencies]

    activities_query = (
        ActivityLog.query
        .join(User)
        .filter(User.agency_id.in_(managed_agency_ids))
        .order_by(ActivityLog.created_at.desc())
    )
    pagination = apply_pagination(activities_query)
    
    # Use super_admin/activities.html as it is compatible
    return render_template('super_admin/activities.html', activities=pagination)