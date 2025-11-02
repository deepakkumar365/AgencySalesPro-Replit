"""
Migration Script: Move hardcoded menus to database
This script creates all menu items and assigns them to appropriate roles.
Run once with: python migrate_menus_to_database.py
"""

from app import create_app, db
from models import MenuItem, MenuRole, Role

app = create_app()

def get_role_id(role_name):
    """Get role ID by name"""
    role = Role.query.filter_by(name=role_name).first()
    if not role:
        raise ValueError(f"Role '{role_name}' not found")
    return role.id


def create_menu_item(name, display_name, url=None, icon=None, parent_id=None, order_index=0):
    """Create or get existing menu item"""
    item = MenuItem.query.filter_by(name=name).first()
    if not item:
        item = MenuItem(
            name=name,
            display_name=display_name,
            url=url,
            icon=icon,
            parent_id=parent_id,
            order_index=order_index,
            is_active=True
        )
        db.session.add(item)
        db.session.flush()
    return item


def assign_menu_to_role(menu_item, role_names):
    """Assign menu to specified roles"""
    for role_name in role_names:
        role_id = get_role_id(role_name)
        existing = MenuRole.query.filter_by(menu_id=menu_item.id, role_id=role_id).first()
        if not existing:
            menu_role = MenuRole(menu_id=menu_item.id, role_id=role_id)
            db.session.add(menu_role)


def migrate():
    """Execute migration"""
    with app.app_context():
        print("Starting menu migration...")
        
        # Define all menus from hardcoded structure
        menus = [
            # Agencies Menu (Super Admin, Agency Manager)
            {
                'name': 'Agencies',
                'display_name': 'Agencies',
                'icon': 'fas fa-building',
                'order_index': 1,
                'roles': ['super_admin', 'agency_manager'],
                'children': [
                    {'name': 'All Agencies', 'display_name': 'All Agencies', 'icon': 'fas fa-list', 'url': '/agency/', 'order_index': 1},
                    {'name': 'Create Agency', 'display_name': 'Create Agency', 'icon': 'fas fa-plus-circle', 'url': '/agency/create', 'order_index': 2},
                ]
            },
            
            # People Menu (User Management)
            {
                'name': 'People',
                'display_name': 'People',
                'icon': 'fas fa-users',
                'order_index': 2,
                'roles': ['super_admin', 'agency_manager', 'agency_admin'],
                'children': [
                    {'name': 'All Users', 'display_name': 'All Users', 'icon': 'fas fa-users-cog', 'url': '/agency/users', 'order_index': 1},
                ]
            },
            
            # Masters Menu
            {
                'name': 'Masters',
                'display_name': 'Masters',
                'icon': 'fas fa-cogs',
                'order_index': 3,
                'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff', 'salesperson'],
                'children': [
                    {'name': 'Masters Dashboard', 'display_name': 'Masters Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/masters/', 'order_index': 1},
                    {'name': 'Locations', 'display_name': 'Locations', 'icon': 'fas fa-map-marker-alt', 'url': '/location/', 'order_index': 2},
                    {'name': 'Categories', 'display_name': 'Categories', 'icon': 'fas fa-tags', 'url': '/masters/categories', 'order_index': 3},
                    {'name': 'Units of Measure', 'display_name': 'Units of Measure', 'icon': 'fas fa-balance-scale', 'url': '/masters/uoms', 'order_index': 4},
                    {'name': 'Tax Masters', 'display_name': 'Tax Masters', 'icon': 'fas fa-percent', 'url': '/masters/tax_masters', 'order_index': 5},
                    {'name': 'Customers', 'display_name': 'Customers', 'icon': 'fas fa-user-friends', 'url': '/customer/', 'order_index': 6},
                    {'name': 'Suppliers', 'display_name': 'Suppliers', 'icon': 'fas fa-truck', 'url': '/inventory/suppliers', 'order_index': 7},
                ]
            },
            
            # Inventory Menu
            {
                'name': 'Inventory',
                'display_name': 'Inventory',
                'icon': 'fas fa-boxes',
                'order_index': 4,
                'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff', 'salesperson'],
                'children': [
                    {'name': 'Inventory Dashboard', 'display_name': 'Inventory Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/inventory/dashboard', 'order_index': 1},
                    {'name': 'Products', 'display_name': 'Products', 'icon': 'fas fa-box', 'url': '/product_overrides/list', 'order_index': 2},
                    {'name': 'Stock Levels', 'display_name': 'Stock Levels', 'icon': 'fas fa-layer-group', 'url': '/inventory/stock_levels', 'order_index': 3},
                    {'name': 'Inventory Reports', 'display_name': 'Inventory Reports', 'icon': 'fas fa-chart-bar', 'url': '/inventory/reports', 'order_index': 4},
                ]
            },
            
            # Forecasting Menu
            {
                'name': 'Forecasting',
                'display_name': 'Forecasting',
                'icon': 'fas fa-chart-line',
                'order_index': 5,
                'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff'],
                'children': [
                    {'name': 'Forecast Dashboard', 'display_name': 'Forecast Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/forecasting/dashboard', 'order_index': 1},
                    {'name': 'Forecast Report', 'display_name': 'Forecast Report', 'icon': 'fas fa-file-alt', 'url': '/forecasting/report', 'order_index': 2},
                    {'name': 'Alert Configuration', 'display_name': 'Alert Configuration', 'icon': 'fas fa-cog', 'url': '/forecasting/alert_config', 'order_index': 3},
                ]
            },
            
            # Sales Menu
            {
                'name': 'Sales',
                'display_name': 'Sales',
                'icon': 'fas fa-shopping-cart',
                'order_index': 6,
                'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff', 'salesperson', 'pos_user'],
                'children': [
                    {'name': 'All Orders', 'display_name': 'All Orders', 'icon': 'fas fa-list', 'url': '/order/', 'order_index': 1},
                    {'name': 'New Sales Order', 'display_name': 'New Sales Order', 'icon': 'fas fa-plus-circle', 'url': '/order/create', 'order_index': 2},
                    {'name': 'Purchase Orders', 'display_name': 'Purchase Orders', 'icon': 'fas fa-receipt', 'url': '/purchase_order/', 'order_index': 3},
                ]
            },
            
            # Accounting Menu
            {
                'name': 'Accounting',
                'display_name': 'Accounting',
                'icon': 'fas fa-file-invoice-dollar',
                'order_index': 7,
                'roles': ['super_admin', 'agency_manager', 'agency_admin', 'accountant'],
                'children': [
                    {'name': 'Accounting Dashboard', 'display_name': 'Accounting Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/reports/unified_dashboard', 'order_index': 1},
                    {'name': 'AR Transaction Report', 'display_name': 'AR Transaction Report', 'icon': 'fas fa-chart-bar', 'url': '/reports/accounting_report?report_type=ar', 'order_index': 2},
                    {'name': 'AP Transaction Report', 'display_name': 'AP Transaction Report', 'icon': 'fas fa-chart-line', 'url': '/reports/accounting_report?report_type=ap', 'order_index': 3},
                    {'name': 'Gross Profit Report', 'display_name': 'Gross Profit Report', 'icon': 'fas fa-dollar-sign', 'url': '/reports/accounting_report?report_type=gp', 'order_index': 4},
                ]
            },
            
            # POS Menu
            {
                'name': 'POS',
                'display_name': 'POS',
                'icon': 'fas fa-cash-register',
                'order_index': 8,
                'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff', 'pos_user'],
                'children': [
                    {'name': 'POS Dashboard', 'display_name': 'POS Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/pos/dashboard', 'order_index': 1},
                    {'name': 'New POS Sale', 'display_name': 'New POS Sale', 'icon': 'fas fa-plus-circle', 'url': '/pos/sale', 'order_index': 2},
                    {'name': 'Sales History', 'display_name': 'Sales History', 'icon': 'fas fa-history', 'url': '/pos/sales_history', 'order_index': 3},
                ]
            },
            
            # Finance Menu
            {
                'name': 'Finance',
                'display_name': 'Finance',
                'icon': 'fas fa-wallet',
                'order_index': 9,
                'roles': ['super_admin', 'agency_manager'],
                'children': [
                    {'name': 'Finance Dashboard', 'display_name': 'Finance Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/reports/unified_dashboard', 'order_index': 1},
                    {'name': 'Payments', 'display_name': 'Payments', 'icon': 'fas fa-money-bill-wave', 'url': '/finance/payments', 'order_index': 2},
                    {'name': 'Receipts', 'display_name': 'Receipts', 'icon': 'fas fa-receipt', 'url': '/finance/receipts', 'order_index': 3},
                    {'name': 'New Payment', 'display_name': 'New Payment', 'icon': 'fas fa-plus-circle', 'url': '/finance/create_payment', 'order_index': 4},
                    {'name': 'New Receipt', 'display_name': 'New Receipt', 'icon': 'fas fa-plus-circle', 'url': '/finance/create_receipt', 'order_index': 5},
                    {'name': 'Payment Configurations', 'display_name': 'Payment Configurations', 'icon': 'fas fa-cogs', 'url': '/finance/payment_configurations', 'order_index': 6},
                ]
            },
            
            # Reports Menu
            {
                'name': 'Reports',
                'display_name': 'Reports',
                'icon': 'fas fa-chart-bar',
                'order_index': 10,
                'roles': ['super_admin', 'agency_manager', 'agency_admin', 'accountant'],
                'children': [
                    {'name': 'Sales Analytics', 'display_name': 'Sales Analytics', 'icon': 'fas fa-chart-line', 'url': '/reports/sales_analytics', 'order_index': 1},
                    {'name': 'AR Aging Report', 'display_name': 'AR Aging Report', 'icon': 'fas fa-hourglass-end', 'url': '/reports/ar_report', 'order_index': 2},
                    {'name': 'AP Aging Report', 'display_name': 'AP Aging Report', 'icon': 'fas fa-hourglass-end', 'url': '/reports/ap_report', 'order_index': 3},
                ]
            },
            
            # Configuration Menu (Super Admin, Agency Manager)
            {
                'name': 'Configuration',
                'display_name': 'Configuration',
                'icon': 'fas fa-sliders-h',
                'order_index': 11,
                'roles': ['super_admin', 'agency_manager'],
                'children': [
                    {'name': 'System Settings', 'display_name': 'System Settings', 'icon': 'fas fa-cog', 'url': '/super_admin/config', 'order_index': 1},
                    {'name': 'Menu Management', 'display_name': 'Menu Management', 'icon': 'fas fa-bars', 'url': '/super_admin/menus', 'order_index': 2},
                ]
            },
        ]
        
        # Create all menu items
        print("Creating menu items...")
        menu_cache = {}
        
        for menu_def in menus:
            # Create parent menu
            parent = create_menu_item(
                menu_def['name'],
                menu_def['display_name'],
                url=menu_def.get('url'),
                icon=menu_def.get('icon'),
                order_index=menu_def.get('order_index', 0)
            )
            menu_cache[menu_def['name']] = parent
            
            # Assign to roles
            assign_menu_to_role(parent, menu_def['roles'])
            
            # Create children
            if 'children' in menu_def:
                for child_def in menu_def['children']:
                    child = create_menu_item(
                        child_def['name'],
                        child_def['display_name'],
                        url=child_def.get('url'),
                        icon=child_def.get('icon'),
                        parent_id=parent.id,
                        order_index=child_def.get('order_index', 0)
                    )
                    # Children inherit parent's roles
                    assign_menu_to_role(child, menu_def['roles'])
        
        # Commit all changes
        db.session.commit()
        print("✅ Menu migration completed successfully!")
        print(f"Created {MenuItem.query.count()} menu items")
        print(f"Created {MenuRole.query.count()} role assignments")


if __name__ == '__main__':
    migrate()