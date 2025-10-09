from functools import wraps
from flask import session, redirect, url_for, flash, request
from werkzeug.local import LocalProxy
from models import User, Agency

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(roles=None, permission_check=None, message=None):
    """
    A flexible decorator to check user roles and permissions.

    :param roles: A list of role names that are allowed access.
    :param permission_check: A function that takes the user and returns True if they have permission.
    :param message: A custom flash message for permission denial.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))

            user_role = session.get('role')
            
            # Role-based check
            if roles and user_role not in roles:
                flash(message or 'You do not have permission to access this page.', 'error')
                return redirect(url_for('index'))

            # Custom permission function check
            if permission_check:
                user = User.query.get(session['user_id'])
                if not permission_check(user):
                    flash(message or 'You do not have permission to perform this action.', 'error')
                    return redirect(url_for('index'))

            # If not a super_admin, inject the current_agency_id for filtering.
            # This replaces the functionality of agency_access_required.
            if user_role != 'super_admin':
                kwargs['current_agency_id'] = session.get('agency_id')

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page', 'warning')
                return redirect(url_for('auth.login'))
            
            user_role = session.get('role')
            if user_role not in roles:
                flash('You do not have permission to access this page', 'error')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def order_owner_required(f):
    """
    Decorator to ensure a user has permission to access a specific order.
    - super_admin: Always has access.
    - salesperson: Must be the salesperson assigned to the order.
    - Other agency roles: Must belong to the same agency as the order.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from models import Order
        order_id = kwargs.get('order_id')
        if not order_id:
            flash('Order ID is missing.', 'error')
            return redirect(url_for('order.list_orders'))

        order = Order.query.get_or_404(order_id)
        user_role = session.get('role')
        user_id = session.get('user_id')

        if user_role == 'super_admin' or \
           (user_role == 'salesperson' and order.salesperson_id == user_id) or \
           (user_role not in ['super_admin', 'salesperson'] and order.agency_id == session.get('agency_id')):
            return f(*args, **kwargs)

        flash('You do not have permission to access this order.', 'error')
        return redirect(url_for('order.list_orders'))
    return decorated_function

def get_current_user():
    """Get current logged in user"""
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None

def get_role_permissions(role):
    """Get permissions for a specific role"""
    permissions = {
        'super_admin': {
            'can_manage_agencies': True,
            'can_manage_all_users': True,
            'can_view_all_data': True,
            'can_access_pos': True,
            'can_manage_inventory': True,
            'can_manage_billing': True,
            'can_view_reports': True
        },
        'agency_admin': {
            'can_manage_agencies': False,
            'can_manage_all_users': True,
            'can_view_all_data': False,
            'can_access_pos': True,
            'can_manage_inventory': True,
            'can_manage_billing': True,
            'can_view_reports': True,
            'can_manage_agency_users': True
        },
        'agency_manager': {
            'can_manage_agencies': True, # Can view/create/edit their own
            'can_manage_all_users': True,
            'can_view_all_data': True,
            'can_access_pos': True,
            'can_manage_inventory': True,
            'can_manage_billing': True,
            'can_view_reports': True,
            'can_manage_agency_users': True
        },
        'staff': {
            'can_manage_agencies': False,
            'can_manage_all_users': False,
            'can_view_all_data': False,
            'can_access_pos': False,
            'can_manage_inventory': True,
            'can_manage_billing': True,
            'can_view_reports': False
        },
        'salesperson': {
            'can_manage_agencies': False,
            'can_manage_all_users': False,
            'can_view_all_data': False,
            'can_access_pos': False,
            'can_manage_inventory': True,
            'can_manage_billing': False,
            'can_view_reports': False,
            'can_manage_orders': True
        },
        'pos_user': {
            'can_manage_agencies': False,
            'can_manage_all_users': False,
            'can_view_all_data': False,
            'can_access_pos': True,
            'can_manage_inventory': False,
            'can_manage_billing': True,
            'can_view_reports': False,
            'can_create_quick_sales': True
        }
    }
    return permissions.get(role, {})
