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

def get_current_user():
    """Get current logged in user"""
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None
