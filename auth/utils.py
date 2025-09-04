from functools import wraps
from flask import session, redirect, url_for, flash, request
from models import User

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

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

def agency_access_required(f):
    """Ensures user can only access data from their agency (except super_admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        
        user_role = session.get('role')
        if user_role == 'super_admin':
            return f(*args, **kwargs)
        
        # Add agency_id to kwargs for filtering
        kwargs['current_agency_id'] = session.get('agency_id')
        return f(*args, **kwargs)
    return decorated_function

def pos_access_required(f):
    """Ensures user can access POS functionality (pos_user, agency_admin, super_admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        
        user_role = session.get('role')
        allowed_roles = ['pos_user', 'agency_admin', 'super_admin']
        
        if user_role not in allowed_roles:
            flash('You do not have permission to access POS functionality', 'error')
            return redirect(url_for('index'))
        
        # Add agency_id for non-super_admin users
        if user_role != 'super_admin':
            kwargs['current_agency_id'] = session.get('agency_id')
        
        return f(*args, **kwargs)
    return decorated_function

def inventory_access_required(f):
    """Ensures user can access inventory functionality (agency_admin, staff, super_admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        
        user_role = session.get('role')
        allowed_roles = ['agency_admin', 'staff', 'super_admin']
        
        if user_role not in allowed_roles:
            flash('You do not have permission to access inventory functionality', 'error')
            return redirect(url_for('index'))
        
        # Add agency_id for non-super_admin users
        if user_role != 'super_admin':
            kwargs['current_agency_id'] = session.get('agency_id')
        
        return f(*args, **kwargs)
    return decorated_function

def billing_access_required(f):
    """Ensures user can access billing functionality (agency_admin, staff, pos_user, super_admin)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page', 'warning')
            return redirect(url_for('auth.login'))
        
        user_role = session.get('role')
        allowed_roles = ['agency_admin', 'staff', 'pos_user', 'super_admin']
        
        if user_role not in allowed_roles:
            flash('You do not have permission to access billing functionality', 'error')
            return redirect(url_for('index'))
        
        # Add agency_id for non-super_admin users
        if user_role != 'super_admin':
            kwargs['current_agency_id'] = session.get('agency_id')
        
        return f(*args, **kwargs)
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
            'can_manage_all_users': False,
            'can_view_all_data': False,
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
            'can_manage_inventory': False,
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
