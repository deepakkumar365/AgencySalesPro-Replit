"""
Seed initial RBAC Roles and Permissions.
Run with the app context, e.g.:
    from app import create_app
    app = create_app()
    with app.app_context():
        import scripts.seed_rbac as s
        s.run()
"""
from extensions import db
from models import Role, Permission, User
import os
import json
try:
    import yaml
except Exception:
    yaml = None

# Default matrix if no file is provided
DEFAULT_MATRIX = {
    'permissions': [
        {'code': 'product.view', 'description': 'View products'},
        {'code': 'product.create', 'description': 'Create products'},
        {'code': 'order.view', 'description': 'View orders'},
        {'code': 'order.create', 'description': 'Create orders'},
        {'code': 'invoice.issue', 'description': 'Issue invoices'},
        {'code': 'user.manage', 'description': 'Manage users'},
    ],
    'roles': {
        'super_admin': {
            'description': 'Full access',
            'permissions': ['product.view', 'product.create', 'order.view', 'order.create', 'invoice.issue', 'user.manage']
        },
        'agency_admin': {
            'description': 'Agency admin',
            'permissions': ['product.view', 'order.view', 'order.create', 'invoice.issue']
        },
        'salesperson': {
            'description': 'Sales person',
            'permissions': ['product.view', 'order.create']
        }
    }
}


def load_matrix():
    # Look for rbac_matrix.yaml or rbac_matrix.json at repo root
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    yaml_path = os.path.join(root, 'rbac_matrix.yaml')
    json_path = os.path.join(root, 'rbac_matrix.json')
    if os.path.exists(yaml_path) and yaml:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return DEFAULT_MATRIX


def run(matrix=None):
    matrix = matrix or load_matrix()

    # Create or update permissions
    perm_map = {}
    for p in matrix.get('permissions', []):
        code = p.get('code')
        if not code:
            continue
        perm = Permission.query.filter_by(code=code).first()
        if not perm:
            perm = Permission(code=code, description=p.get('description'))
            db.session.add(perm)
            db.session.flush()
        else:
            # update description if needed
            perm.description = p.get('description') or perm.description
            db.session.add(perm)
        perm_map[code] = perm

    db.session.commit()

    # Create or update roles and attach permissions
    for role_name, meta in matrix.get('roles', {}).items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=meta.get('description'))
            db.session.add(role)
            db.session.flush()
        else:
            role.description = meta.get('description') or role.description
        # Attach permissions (idempotent)
        perms = [perm_map[c] for c in (meta.get('permissions') or []) if c in perm_map]
        role.permissions = perms
        db.session.add(role)

    db.session.commit()

    # Migrate existing users that have a legacy role string
    for u in User.query.all():
        legacy = getattr(u, 'role', None)
        if legacy:
            role = Role.query.filter_by(name=legacy).first()
            if role and role not in (u.roles or []):
                u.roles.append(role)
                db.session.add(u)

    db.session.commit()
    print('RBAC seed completed')


if __name__ == '__main__':
    run()
