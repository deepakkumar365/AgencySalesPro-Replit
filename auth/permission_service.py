from flask import session, g
from datetime import datetime, timedelta
from extensions import db
from models import User, MenuItem, Permission, Role

# Simple in-process TTL cache to avoid adding new dependencies.
_CACHE = {}
_DEFAULT_TTL = timedelta(seconds=300)

def _cache_get(key):
    entry = _CACHE.get(key)
    if not entry:
        return None
    value, expires = entry
    if datetime.utcnow() > expires:
        del _CACHE[key]
        return None
    return value

def _cache_set(key, value, ttl=_DEFAULT_TTL):
    _CACHE[key] = (value, datetime.utcnow() + ttl)


class PermissionService:
    @staticmethod
    def get_user_permissions(user_id):
        """Return a set of permission codes for the given user id.

        Uses a small TTL cache to reduce DB hits. Falls back to the legacy
        `role` string on User if `role_id`/Role isn't populated yet.
        """
        cache_key = f"user_permissions:{user_id}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        user = User.query.get(user_id)
        if not user:
            _cache_set(cache_key, set())
            return set()

        # Prefer normalized role relationship, fallback to role string
        perms = set()
        if getattr(user, 'role_obj', None):
            for p in user.role_obj.permissions:
                perms.add(p.code)
        else:
            # Legacy fallback: find Role by name if exists
            if user.role:
                role = Role.query.filter_by(name=user.role).first()
                if role:
                    for p in role.permissions:
                        perms.add(p.code)

        _cache_set(cache_key, perms)
        return perms

    @staticmethod
    def has_permission(permission_code):
        """Check if current session user has the given permission code."""
        if 'user_id' not in session:
            return False
        # Use flask.g to avoid repeated DB lookups during a request
        if not hasattr(g, 'user_permissions'):
            g.user_permissions = PermissionService.get_user_permissions(session['user_id'])
        return permission_code in g.user_permissions

    @staticmethod
    def get_user_menu(user_id):
        """Return top-level menu items accessible to the user.

        Each returned MenuItem will have `.accessible_children` set to a list
        of allowed children.
        """
        cache_key = f"user_menu:{user_id}"
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        user = User.query.get(user_id)
        if not user:
            _cache_set(cache_key, [])
            return []

        user_permissions = PermissionService.get_user_permissions(user_id)

        menu_items = MenuItem.query.filter(
            MenuItem.parent_id.is_(None),
            MenuItem.is_active == True
        ).order_by(MenuItem.order_index).all()

        accessible = []
        for item in menu_items:
            if not item.required_permission_code or item.required_permission_code in user_permissions:
                children = []
                for child in item.children.filter(MenuItem.is_active == True).order_by(MenuItem.order_index):
                    if not child.required_permission_code or child.required_permission_code in user_permissions:
                        children.append(child)

                item.accessible_children = children
                accessible.append(item)

        _cache_set(cache_key, accessible)
        return accessible

    @staticmethod
    def get_dashboard_url(role_name):
        item = MenuItem.query.filter_by(dashboard_for_role=role_name, is_active=True).first()
        if item and item.url:
            return item.url
        return 'index'


permission_service = PermissionService()
