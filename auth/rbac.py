from functools import wraps
from flask import abort, g
from flask_login import current_user
from flask import session
from models import Role, Permission, User


def permission_required(permission_code):
    """Decorator to require a permission code for a Flask route or view function.

    Usage:
        @permission_required('order.create')
        def create_order():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Support two modes: session-based auth (project uses session['user_id'])
            # and flask-login's current_user. Check session cache first for performance.
            if 'user_id' in session:
                perms = session.get('permissions', [])
                # super_admin shortcut
                if 'super_admin' in session.get('roles', []) or session.get('role') == 'super_admin':
                    return f(*args, **kwargs)
                if permission_code not in perms:
                    abort(403)
                return f(*args, **kwargs)

            user = current_user
            # If user object not loaded via flask-login, try abort
            if not user or not getattr(user, 'is_authenticated', False):
                abort(401)
            if not getattr(user, 'has_perm', None):
                abort(403)
            if not user.has_perm(permission_code):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


def get_permissions_for_user(user):
    """Compute a set of permission codes for a user from their roles.

    Returns a set of strings.
    """
    if not user:
        return set()
    # legacy role string check
    if getattr(user, 'role', None) == 'super_admin':
        return {'*'}
    perms = set()
    for r in (user.roles or []):
        for p in (r.permissions or []):
            perms.add(p.code)
    return perms


def agency_object_required(model, id_arg='id', agency_field='agency_id', permission=None):
    """Decorator to ensure the current user can access an object scoped to an agency.

    - model: SQLAlchemy model class
    - id_arg: name of view kwarg that contains the object's id
    - agency_field: attribute on model that references agency id
    - permission: optional permission code to also require
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            obj_id = kwargs.get(id_arg)
            if obj_id is None:
                abort(400)
            obj = model.query.get_or_404(obj_id)

            # Permission short-circuits
            if permission:
                # re-use permission_required logic via session/current_user
                # Check session first
                if 'user_id' in session:
                    if session.get('role') == 'super_admin' or 'super_admin' in session.get('roles', []):
                        return f(*args, **kwargs)
                    if permission not in session.get('permissions', []):
                        abort(403)
                else:
                    u = current_user
                    if not u or not getattr(u, 'is_authenticated', False) or not getattr(u, 'has_perm', None) or not u.has_perm(permission):
                        abort(403)

            # Agency scoping
            obj_agency = getattr(obj, agency_field, None)
            if obj_agency is None:
                # allow if object has no agency
                return f(*args, **kwargs)

            # Super admin bypass
            if 'user_id' in session:
                if session.get('role') == 'super_admin' or 'super_admin' in session.get('roles', []):
                    return f(*args, **kwargs)
                if session.get('agency_id') == obj_agency:
                    return f(*args, **kwargs)
                abort(403)

            # If using flask-login
            u = current_user
            if not u or not getattr(u, 'is_authenticated', False):
                abort(401)
            if getattr(u, 'role', None) == 'super_admin' or any(r.name == 'super_admin' for r in (u.roles or [])):
                return f(*args, **kwargs)
            if getattr(u, 'agency_id', None) == obj_agency:
                return f(*args, **kwargs)
            abort(403)
        return wrapped
    return decorator
