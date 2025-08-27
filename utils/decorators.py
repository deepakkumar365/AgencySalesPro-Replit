from functools import wraps
from flask import session, request
from app import db
from models import ActivityLog

def log_activity(action):
    """Decorator to log user activities"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if user_id:
                # Execute the function first
                result = f(*args, **kwargs)
                
                # Log the activity after successful execution
                try:
                    log = ActivityLog(
                        user_id=user_id,
                        action=action,
                        description=f'User performed {action}',
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent')
                    )
                    db.session.add(log)
                    db.session.commit()
                except Exception as e:
                    # Don't fail the request if logging fails
                    pass
                
                return result
            else:
                return f(*args, **kwargs)
        return decorated_function
    return decorator
