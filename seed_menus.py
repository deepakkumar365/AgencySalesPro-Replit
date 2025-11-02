"""
Seed script for menu items and role-menu mappings.
Run this script to initialize the menu system with sample data.

Usage: python seed_menus.py
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app import create_app
from extensions import db
from models import MenuItem, MenuRole, Role

def seed_menus():
    """Create sample menu items"""
    
    # Check if menus already exist
    if MenuItem.query.count() > 0:
        print("Menus already exist. Skipping menu creation.")
        return
    
    menus_data = [
        # Dashboard
        {
            'name': 'Dashboard',
            'url': 'super_admin.dashboard',
            'icon': 'fas fa-home',
            'order_index': 0,
            'parent_id': None,
            'children': []
        },
        # Users & Roles
        {
            'name': 'Administration',
            'url': None,
            'icon': 'fas fa-cog',
            'order_index': 10,
            'parent_id': None,
            'children': [
                {'name': 'System Configuration', 'url': 'super_admin.system_config', 'icon': 'fas fa-sliders-h', 'order_index': 0},
                {'name': 'Users', 'url': 'super_admin.users', 'icon': 'fas fa-users', 'order_index': 1},
                {'name': 'Roles & Permissions', 'url': 'super_admin.roles', 'icon': 'fas fa-lock', 'order_index': 2},
                {'name': 'Menu Management', 'url': 'super_admin.manage_menus', 'icon': 'fas fa-bars', 'order_index': 3},
            ]
        },
        # Agencies
        {
            'name': 'Agencies',
            'url': None,
            'icon': 'fas fa-building',
            'order_index': 20,
            'parent_id': None,
            'children': [
                {'name': 'List Agencies', 'url': 'agency.list_agencies', 'icon': 'fas fa-list', 'order_index': 0},
                {'name': 'Create Agency', 'url': 'agency.create_agency', 'icon': 'fas fa-plus', 'order_index': 1},
            ]
        },
        # Locations
        {
            'name': 'Locations',
            'url': None,
            'icon': 'fas fa-map-marker-alt',
            'order_index': 30,
            'parent_id': None,
            'children': [
                {'name': 'List Locations', 'url': 'location.list_locations', 'icon': 'fas fa-list', 'order_index': 0},
                {'name': 'Create Location', 'url': 'location.create_location', 'icon': 'fas fa-plus', 'order_index': 1},
            ]
        },
        # Products
        {
            'name': 'Products',
            'url': None,
            'icon': 'fas fa-box',
            'order_index': 40,
            'parent_id': None,
            'children': [
                {'name': 'List Products', 'url': 'product.list_products', 'icon': 'fas fa-list', 'order_index': 0},
                {'name': 'Create Product', 'url': 'product.create_product', 'icon': 'fas fa-plus', 'order_index': 1},
                {'name': 'Product Overrides', 'url': 'product_overrides.list', 'icon': 'fas fa-edit', 'order_index': 2},
            ]
        },
        # Customers
        {
            'name': 'Customers',
            'url': None,
            'icon': 'fas fa-users',
            'order_index': 50,
            'parent_id': None,
            'children': [
                {'name': 'List Customers', 'url': 'customer.list_customers', 'icon': 'fas fa-list', 'order_index': 0},
                {'name': 'Create Customer', 'url': 'customer.create_customer', 'icon': 'fas fa-plus', 'order_index': 1},
            ]
        },
        # Orders
        {
            'name': 'Orders',
            'url': None,
            'icon': 'fas fa-shopping-cart',
            'order_index': 60,
            'parent_id': None,
            'children': [
                {'name': 'List Orders', 'url': 'order.list_orders', 'icon': 'fas fa-list', 'order_index': 0},
                {'name': 'Create Order', 'url': 'order.create_order', 'icon': 'fas fa-plus', 'order_index': 1},
            ]
        },
        # Inventory
        {
            'name': 'Inventory',
            'url': None,
            'icon': 'fas fa-warehouse',
            'order_index': 70,
            'parent_id': None,
            'children': [
                {'name': 'Dashboard', 'url': 'inventory.dashboard', 'icon': 'fas fa-home', 'order_index': 0},
                {'name': 'Stock Levels', 'url': 'inventory.stock_levels', 'icon': 'fas fa-list', 'order_index': 1},
                {'name': 'Adjust Stock', 'url': 'inventory.adjust_stock', 'icon': 'fas fa-adjust', 'order_index': 2},
            ]
        },
        # Reports
        {
            'name': 'Reports',
            'url': None,
            'icon': 'fas fa-chart-bar',
            'order_index': 80,
            'parent_id': None,
            'children': [
                {'name': 'Sales Analytics', 'url': 'reports.sales_analytics', 'icon': 'fas fa-chart-line', 'order_index': 0},
                {'name': 'AR Aging', 'url': 'reports.ar_aging', 'icon': 'fas fa-hourglass', 'order_index': 1},
                {'name': 'AP Aging', 'url': 'reports.ap_aging', 'icon': 'fas fa-hourglass', 'order_index': 2},
            ]
        },
        # Billing
        {
            'name': 'Billing',
            'url': None,
            'icon': 'fas fa-file-invoice-dollar',
            'order_index': 90,
            'parent_id': None,
            'children': [
                {'name': 'Dashboard', 'url': 'billing.dashboard', 'icon': 'fas fa-home', 'order_index': 0},
                {'name': 'Invoices', 'url': 'billing.invoices', 'icon': 'fas fa-file-invoice', 'order_index': 1},
            ]
        },
    ]
    
    # Create parent and child menu items
    parent_menu_objects = {}
    
    for menu_data in menus_data:
        # Create parent menu
        parent_menu = MenuItem(
            name=menu_data['name'],
            url=menu_data['url'],
            icon=menu_data['icon'],
            order_index=menu_data['order_index'],
            parent_id=None,
            is_active=True
        )
        db.session.add(parent_menu)
        db.session.flush()  # Get the ID
        
        parent_menu_objects[menu_data['name']] = parent_menu
        
        # Create children menus
        for child_data in menu_data.get('children', []):
            child_menu = MenuItem(
                name=child_data['name'],
                url=child_data['url'],
                icon=child_data['icon'],
                order_index=child_data['order_index'],
                parent_id=parent_menu.id,
                is_active=True
            )
            db.session.add(child_menu)
    
    db.session.commit()
    print(f"✓ Created {len(menus_data)} parent menus with children")


def seed_role_menu_mappings():
    """Assign menus to roles"""
    
    # Get all roles
    roles = Role.query.all()
    if not roles:
        print("⚠ No roles found. Please create roles first.")
        return
    
    # Delete existing mappings to avoid duplicates
    MenuRole.query.delete()
    db.session.commit()
    
    # Define menu mappings per role
    role_menu_mappings = {
        'super_admin': [
            'Dashboard', 'Administration', 'Agencies', 'Locations', 'Products',
            'Customers', 'Orders', 'Inventory', 'Reports', 'Billing'
        ],
        'agency_admin': [
            'Dashboard', 'Locations', 'Products', 'Customers', 'Orders',
            'Inventory', 'Reports', 'Billing'
        ],
        'agency_manager': [
            'Dashboard', 'Locations', 'Products', 'Customers', 'Orders',
            'Inventory', 'Reports', 'Billing'
        ],
        'staff': [
            'Dashboard', 'Products', 'Customers', 'Orders', 'Inventory'
        ],
        'salesperson': [
            'Dashboard', 'Orders', 'Customers'
        ],
        'pos_user': [
            'Dashboard', 'Orders'
        ],
    }
    
    # Create mappings
    mapping_count = 0
    for role in roles:
        menu_names = role_menu_mappings.get(role.name, [])
        
        for menu_name in menu_names:
            # Get menu by name (parent menus only for now)
            menu = MenuItem.query.filter(
                MenuItem.name == menu_name,
                MenuItem.parent_id == None
            ).first()
            
            if menu:
                mapping = MenuRole(menu_id=menu.id, role_id=role.id)
                db.session.add(mapping)
                mapping_count += 1
                
                # Also add children menus
                children = MenuItem.query.filter(MenuItem.parent_id == menu.id).all()
                for child in children:
                    child_mapping = MenuRole(menu_id=child.id, role_id=role.id)
                    db.session.add(child_mapping)
                    mapping_count += 1
    
    db.session.commit()
    print(f"✓ Created {mapping_count} role-menu mappings")


def main():
    """Main seed function"""
    app = create_app()
    
    with app.app_context():
        print("🌱 Seeding menu system...")
        
        try:
            seed_menus()
            seed_role_menu_mappings()
            print("\n✅ Menu seeding completed successfully!")
        except Exception as e:
            print(f"\n❌ Error during seeding: {e}")
            db.session.rollback()
            sys.exit(1)


if __name__ == '__main__':
    main()