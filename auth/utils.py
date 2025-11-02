from functools import wraps
from flask import session, redirect, url_for, flash, request, current_app, g
from werkzeug.local import LocalProxy
from models import User, Agency
from .permission_service import permission_service

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission_code=None, message=None, roles=None, permission_check=None):
    """
    A decorator to check user permissions from the database.

    :param permission_code: The permission code required to access the route
    :param message: A custom flash message for permission denial
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ensure user is logged in
            if 'user_id' not in session:
                flash('Please log in to access this page', 'warning')
                return redirect(url_for('auth.login'))

            # Legacy: if a roles list was provided (positional or kw 'roles'), honor it
            effective_roles = None
            # If permission_code was passed a list/tuple (positional legacy usage)
            if isinstance(permission_code, (list, tuple, set)):
                effective_roles = set(permission_code)
                permission_code_val = None
            else:
                permission_code_val = permission_code

            if roles is not None:
                effective_roles = set(roles)

            if effective_roles:
                user_role = session.get('role')
                if user_role not in effective_roles:
                    flash(message or 'You do not have permission to access this page.', 'error')
                    return redirect(url_for('index'))

                # Passed role check; inject agency filter for non-super-admins
                if user_role != 'super_admin':
                    kwargs['current_agency_id'] = session.get('agency_id')

                # Also allow an optional permission_check callable for finer checks
                if permission_check:
                    user = User.query.get(session['user_id'])
                    if not permission_check(user):
                        flash(message or 'You do not have permission to perform this action.', 'error')
                        return redirect(url_for('index'))

                return f(*args, **kwargs)

            # If no specific permission code is required, allow access (but inject agency id)
            if not permission_code_val:
                user_role = session.get('role')
                if user_role != 'super_admin':
                    kwargs['current_agency_id'] = session.get('agency_id')
                return f(*args, **kwargs)

            # Check permission via PermissionService
            if not permission_service.has_permission(permission_code_val):
                flash(message or 'You do not have permission to access this page.', 'error')
                return redirect(url_for('index'))

            # If permission granted, inject agency id for non-super admins
            user_role = session.get('role')
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
    """
    Get permissions for a specific role.
    
    Access levels used: Full (full CRUD), View (read-only), Limited (some actions), 
    Partial (limited view), None (no access)
    
    Role Matrix:
    - super_admin: Tenant Management (Full), Agency Management (Full), User Management (View only)
    - support: Full access to everything
    - agency_manager: Full most features except Tenant Management (View)
    - agency_admin: Full within single agency, Limited Agency/Payment Configuration
    - staff: Partial Dashboard, Full Inventory/Sales, View Forecasting, Limited Reports
    - accountant: Partial Dashboard, View Inventory/Sales/Payment Config, Full Reports
    """
    permissions = {
        'super_admin': {
            # Full system control but focus on Tenant/Agency Management
            # Dashboard: Full
            'can_manage_agencies': True,          # Tenant Management: Full
            'can_manage_users': False,            # User Management: View only (not edit/delete)
            'can_view_users': True,               # User Management: View
            'can_view_all_data': True,
            'can_access_pos': False,              # Not for super admin
            'can_manage_inventory': False,        # Inventory: None
            'can_view_inventory': False,
            'can_manage_billing': False,          # Payment Configuration: Full (but not shown in nav)
            'can_view_billing': True,
            'can_view_reports': False,            # Reports: None
            'can_manage_reports': False,
            'can_manage_roles': True,
            'can_manage_orders': False,           # Sales: None
            'can_manage_customers': True,
            'can_manage_locations': True,
            'view_forecasting': False             # Forecasting: None
        },

        'support': {
            # Full access to everything - support team role
            # All access levels: Full
            'can_manage_agencies': True,
            'can_manage_users': True,
            'can_view_users': True,
            'can_view_all_data': True,
            'can_access_pos': True,
            'can_manage_inventory': True,
            'can_view_inventory': True,
            'can_manage_billing': True,
            'can_view_billing': True,
            'can_view_reports': True,
            'can_manage_reports': True,
            'can_manage_roles': True,
            'can_manage_orders': True,
            'can_manage_customers': True,
            'can_manage_locations': True,
            'view_forecasting': True
        },

        'agency_manager': {
            # Full control within their managed agencies
            # Tenant Management: View, Agency Management: Full, User Management: Full
            'can_manage_agencies': True,
            'can_manage_users': True,
            'can_view_users': True,
            'can_view_all_data': True,
            'can_access_pos': True,
            'can_manage_inventory': True,
            'can_view_inventory': True,
            'can_manage_billing': True,           # Payment Configuration: View
            'can_view_billing': True,
            'can_view_reports': True,
            'can_manage_reports': False,
            'can_manage_roles': False,
            'can_manage_orders': True,
            'can_manage_customers': True,
            'can_manage_locations': True,
            'view_forecasting': True
        },

        'agency_admin': {
            # Manages users and operations within a single agency
            # Agency Management: Limited, Payment Configuration: Limited
            'can_manage_agencies': False,
            'can_manage_users': True,
            'can_view_users': True,
            'can_view_all_data': False,
            'can_access_pos': True,
            'can_manage_inventory': True,
            'can_view_inventory': True,
            'can_manage_billing': True,           # Limited - can view/manage but not configure
            'can_view_billing': True,
            'can_view_reports': True,
            'can_manage_reports': False,
            'can_manage_roles': False,
            'can_manage_orders': True,
            'can_manage_customers': True,
            'can_manage_locations': True,
            'view_forecasting': True
        },

        'staff': {
            # Operational role within an agency
            # Dashboard: Partial, Inventory: Full, Sales: Full, 
            # Forecasting: View, Reports: Limited
            'can_manage_agencies': False,
            'can_manage_users': False,
            'can_view_users': False,
            'can_view_all_data': False,
            'can_access_pos': True,
            'can_manage_inventory': True,
            'can_view_inventory': True,
            'can_manage_billing': False,
            'can_view_billing': False,
            'can_view_reports': False,            # Limited reports access (view only, no manage)
            'can_manage_reports': False,
            'can_manage_roles': False,
            'can_manage_orders': True,
            'can_manage_customers': True,
            'can_manage_locations': True,
            'view_forecasting': True              # View only
        },

        'salesperson': {
            # Sales-focused role
            'can_manage_agencies': False,
            'can_manage_users': False,
            'can_view_users': False,
            'can_view_all_data': False,
            'can_access_pos': False,
            'can_manage_inventory': False,
            'can_view_inventory': True,
            'can_manage_billing': False,
            'can_view_billing': False,
            'can_view_reports': False,
            'can_manage_reports': False,
            'can_manage_roles': False,
            'can_manage_orders': True,
            'can_manage_customers': True,
            'can_manage_locations': True,
            'view_forecasting': False
        },

        'pos_user': {
            # POS-only role
            'can_manage_agencies': False,
            'can_manage_users': False,
            'can_view_users': False,
            'can_view_all_data': False,
            'can_access_pos': True,
            'can_manage_inventory': False,
            'can_view_inventory': True,
            'can_manage_billing': True,
            'can_view_billing': True,
            'can_view_reports': False,
            'can_manage_reports': False,
            'can_manage_roles': False,
            'can_manage_orders': True,
            'can_manage_customers': True,
            'can_manage_locations': True,
            'view_forecasting': False
        },

        'accountant': {
            # Accounting/Finance focused role
            # Dashboard: Partial, Payment Configuration: View, 
            # Inventory: View, Sales: View, Reports: Full
            'can_manage_agencies': False,
            'can_manage_users': False,
            'can_view_users': False,
            'can_view_all_data': False,
            'can_access_pos': False,
            'can_manage_inventory': False,
            'can_view_inventory': True,           # View only
            'can_manage_billing': False,
            'can_view_billing': True,             # Payment Configuration: View
            'can_view_reports': True,             # Reports: Full (can view and manage)
            'can_manage_reports': True,
            'can_manage_roles': False,
            'can_manage_orders': False,           # Sales: View only (doesn't appear in nav)
            'can_manage_customers': False,
            'can_manage_locations': False,
            'view_forecasting': False
        }
    }

    return permissions.get(role, {})

def inject_permissions():
    """Inject user permissions and menu into all templates"""
    if 'user_id' in session:
        role = session.get('role', '')
        return {
            'permissions': get_role_permissions(role),
            'user_menu': permission_service.get_user_menu(session['user_id']),
            'has_permission': permission_service.has_permission
        }
    return {
        'permissions': {},
        'user_menu': [],
        'has_permission': lambda code: False
    }

def inject_dynamic_menus():
    """Inject role-based menus from ASP_menu_roles table into all templates"""
    from service.menu_service import MenuService
    from models import User
    
    if 'user_id' in session:
        try:
            # Get user and their role
            user = User.query.get(session.get('user_id'))
            if user and user.role:
                # Get menus for this role
                menus = MenuService.get_menus_by_role(user.role_id)
                return {'dynamic_menus': menus, 'role_id': user.role_id}
        except Exception as e:
            # Log error but don't break the app
            import logging
            logging.error(f"Error loading dynamic menus: {e}")
    
    return {'dynamic_menus': [], 'role_id': None}
