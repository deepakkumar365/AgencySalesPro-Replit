from extensions import db
from models import Role, Permission, RolePermission, MenuItem, User

def populate_roles():
    roles = [
        {'name': 'super_admin', 'description': 'Full system control with focus on tenant/agency management', 'is_system': True},
        {'name': 'support', 'description': 'Full access to all features (support team)', 'is_system': True},
        {'name': 'agency_manager', 'description': 'Full control within managed agencies', 'is_system': True},
        {'name': 'agency_admin', 'description': 'Manages users and operations within a single agency', 'is_system': True},
        {'name': 'staff', 'description': 'Operational role within an agency', 'is_system': True},
        {'name': 'salesperson', 'description': 'Sales-focused role', 'is_system': True},
        {'name': 'pos_user', 'description': 'POS terminal user', 'is_system': True},
        {'name': 'accountant', 'description': 'Finance/accounting focused role', 'is_system': True}
    ]

    for role_data in roles:
        role = Role.query.filter_by(name=role_data['name']).first()
        if not role:
            role = Role(**role_data)
            db.session.add(role)

    db.session.commit()

def populate_permissions():
    permissions = [
        {'name': 'Manage Agencies', 'code': 'agency.manage', 'category': 'Agency'},
        {'name': 'View Agencies', 'code': 'agency.view', 'category': 'Agency'},
        {'name': 'Manage Users', 'code': 'user.manage', 'category': 'User'},
        {'name': 'View Users', 'code': 'user.view', 'category': 'User'},
        {'name': 'Manage Inventory', 'code': 'inventory.manage', 'category': 'Inventory'},
        {'name': 'View Inventory', 'code': 'inventory.view', 'category': 'Inventory'},
        {'name': 'Manage Billing', 'code': 'billing.manage', 'category': 'Billing'},
        {'name': 'View Billing', 'code': 'billing.view', 'category': 'Billing'},
        {'name': 'View Billing Dashboard', 'code': 'billing.view_dashboard', 'category': 'Billing'},
        {'name': 'Manage Reports', 'code': 'report.manage', 'category': 'Report'},
        {'name': 'View Reports', 'code': 'report.view', 'category': 'Report'},
        {'name': 'Manage Orders', 'code': 'order.manage', 'category': 'Order'},
        {'name': 'View Orders', 'code': 'order.view', 'category': 'Order'},
        {'name': 'Manage Customers', 'code': 'customer.manage', 'category': 'Customer'},
        {'name': 'View Customers', 'code': 'customer.view', 'category': 'Customer'},
        {'name': 'Manage Locations', 'code': 'location.manage', 'category': 'Location'},
        {'name': 'View Locations', 'code': 'location.view', 'category': 'Location'},
        {'name': 'Access POS', 'code': 'pos.access', 'category': 'POS'},
        {'name': 'View Forecasting', 'code': 'forecasting.view', 'category': 'Forecasting'},
        {'name': 'Manage Roles', 'code': 'role.manage', 'category': 'Role'},
        {'name': 'View All Data', 'code': 'system.view_all_data', 'category': 'System'},
    ]

    for perm_data in permissions:
        perm = Permission.query.filter_by(code=perm_data['code']).first()
        if not perm:
            perm = Permission(**perm_data)
            db.session.add(perm)

    db.session.commit()

def assign_permissions_to_roles():
    roles = {role.name: role for role in Role.query.all()}
    perms = {perm.code: perm for perm in Permission.query.all()}

    role_permissions = {
        'super_admin': [
            'agency.manage', 'agency.view', 'user.view', 'system.view_all_data',
            'billing.view', 'role.manage', 'customer.manage', 'location.manage'
        ],
        'support': [
            'agency.manage', 'agency.view', 'user.manage', 'user.view', 'system.view_all_data',
            'pos.access', 'inventory.manage', 'inventory.view', 'billing.manage', 'billing.view',
            'report.manage', 'report.view', 'role.manage', 'order.manage', 'customer.manage',
            'location.manage', 'forecasting.view'
        ],
    }

    for role_name, perm_codes in role_permissions.items():
        role = roles.get(role_name)
        if role:
            for code in perm_codes:
                perm = perms.get(code)
                if perm and perm not in role.permissions:
                    role.permissions.append(perm)

    db.session.commit()

def create_menu_items():
    menus = [
        {
            'name': 'Dashboard',
            'url': 'index',
            'icon': 'tachometer-alt',
            'required_permission_code': None,
            'order_index': 1
        },
        {
            'name': 'Agencies',
            'url': 'super_admin.manage_agencies',
            'icon': 'building',
            'required_permission_code': 'agency.manage',
            'order_index': 2
        },
    ]

    for menu_data in menus:
        menu = MenuItem.query.filter_by(name=menu_data['name'], parent_id=None).first()
        if not menu:
            menu = MenuItem(**menu_data)
            db.session.add(menu)

    db.session.commit()

def update_user_role_ids():
    roles = {role.name: role.id for role in Role.query.all()}

    users = User.query.all()
    for user in users:
        if user.role in roles and not user.role_id:
            user.role_id = roles[user.role]

    db.session.commit()

def run_migration():
    populate_roles()
    populate_permissions()
    assign_permissions_to_roles()
    create_menu_items()
    update_user_role_ids()
    print("Migration completed successfully!")

if __name__ == '__main__':
    run_migration()
