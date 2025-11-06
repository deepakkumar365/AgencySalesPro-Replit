import os
import logging
import json
from flask import Flask, url_for
from markupsafe import escape, Markup
from dotenv import load_dotenv
from sqlalchemy.engine import Row
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import timedelta, datetime, date
from decimal import Decimal
from extensions import db, jwt, cache

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Custom JSON encoder to handle types like datetime, date, and Decimal
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, Row):
            return dict(obj._mapping)
        return super(CustomJSONEncoder, self).default(obj)

# Helper function to get dashboard URL based on user role
def get_dashboard_url(role):
    """
    Returns the appropriate dashboard URL based on the user's role.
    
    Args:
        role: The user's role (super_admin, agency_manager, agency_admin, customer, etc.)
    
    Returns:
        The endpoint name for the user's dashboard
    """
    role_dashboard_map = {
        'super_admin': 'super_admin.dashboard',
        'agency_manager': 'agency_manager.dashboard',
        'agency_admin': 'inventory.dashboard',
        'customer': 'customer.customer_dashboard',
    }
    return role_dashboard_map.get(role, 'index')

def create_app():
    # Load environment variables from .env file
    load_dotenv()

    app = Flask(__name__)
    
    # Use the custom JSON encoder for consistent API responses
    app.json_encoder = CustomJSONEncoder
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

    # Use DATABASE_URL from the environment. This is required for the app to run.
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set. Please create a .env file with the database connection string.")

    # SQLAlchemy 2.0+ prefers 'postgresql://' over 'postgres://'
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "jwt-secret-string")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)

    # Ensure Jinja's tojson filter uses our custom encoder
    app.config["JSONIFY_PRETTYPRINT_REGULAR"] = False
    
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Initialize extensions
    
    # Custom Jinja2 filter for nl2br
    def nl2br_filter(s):
        if s:
            return Markup(str(escape(s)).replace('\n', '<br>\n'))
        return ''
    app.jinja_env.filters['nl2br'] = nl2br_filter
    
    # Add functions to Jinja2 globals
    app.jinja_env.globals['abs'] = abs
    app.jinja_env.globals['get_dashboard_url'] = get_dashboard_url

    # Register the context processor to inject permissions into templates
    from auth.utils import inject_permissions, inject_dynamic_menus
    from flask import session

    @app.context_processor
    def _inject_permissions_context():
        return inject_permissions()
    
    @app.context_processor
    def _inject_menus_context():
        """Inject dynamic menus based on user role from ASP_menu_roles"""
        return inject_dynamic_menus()

    db.init_app(app)
    jwt.init_app(app)
    cache.init_app(app)
    
    def register_blueprints(app):
        from auth import auth_bp
        from agency import agency_bp
        from salesperson import salesperson_bp
        from location import location_bp
        from customer import customer_bp
        from product import product_bp
        from order import order_bp
        from purchase_order import purchase_order_bp
        from super_admin import super_admin_bp
        from pos import pos_bp
        from inventory import inventory_bp
        from reports import reports_bp
        from agency_manager import agency_manager_bp
        from api import api_bp
        from masters.routes import masters_bp
        from subscription import subscription_bp
        from job_accounting import job_accounting_bp
        from product_overrides import overrides_bp
        from finance import finance_bp
        from forecasting import forecasting_bp

        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(agency_bp, url_prefix='/agency')
        app.register_blueprint(salesperson_bp, url_prefix='/salesperson')
        app.register_blueprint(location_bp, url_prefix='/location')
        app.register_blueprint(customer_bp, url_prefix='/customer')
        app.register_blueprint(product_bp, url_prefix='/product')
        app.register_blueprint(order_bp, url_prefix='/order')
        app.register_blueprint(purchase_order_bp, url_prefix='/purchase-order')
        app.register_blueprint(super_admin_bp, url_prefix='/super_admin')
        app.register_blueprint(pos_bp, url_prefix='/pos')
        app.register_blueprint(inventory_bp, url_prefix='/inventory')
        app.register_blueprint(reports_bp, url_prefix='/reports')
        app.register_blueprint(agency_manager_bp, url_prefix='/agency_manager')
        app.register_blueprint(api_bp, url_prefix='/api/v1')
        app.register_blueprint(masters_bp, url_prefix='/masters')
        app.register_blueprint(subscription_bp, url_prefix='/subscription')
        app.register_blueprint(job_accounting_bp, url_prefix='/job-accounting')
        app.register_blueprint(finance_bp, url_prefix='/billing') # Changed from /finance to /billing
        app.register_blueprint(overrides_bp)
        app.register_blueprint(forecasting_bp, url_prefix='/forecasting')

    register_blueprints(app)
    
    # Main routes
    @app.route('/')
    def index():
        from flask import render_template, session, redirect, url_for
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return render_template('index.html')
    
    with app.app_context():
        import models
        db.create_all()

        from models import User, Agency, AppSetting
        from werkzeug.security import generate_password_hash

        def is_installed() -> bool:
            try:
                return AppSetting.get("app_installed", "false") == "true"
            except Exception as e:
                logging.exception("Failed to read installation flag: %s", e)
                return False

        def seed_menus():
            """Seed database menus from migration data if not already present"""
            try:
                from models import MenuItem, MenuRole, Role
                
                # Skip if menus already exist
                if MenuItem.query.count() > 0:
                    logging.info("Menus already seeded, skipping")
                    return True
                
                logging.info("Seeding menus from database...")
                
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

                # Define all menus
                menus = [
                    {'name': 'Agencies', 'display_name': 'Agencies', 'icon': 'fas fa-building', 'order_index': 1, 'roles': ['super_admin', 'agency_manager'], 'children': [
                        {'name': 'All Agencies', 'display_name': 'All Agencies', 'icon': 'fas fa-list', 'url': '/agency/', 'order_index': 1},
                        {'name': 'Create Agency', 'display_name': 'Create Agency', 'icon': 'fas fa-plus-circle', 'url': '/agency/create', 'order_index': 2},
                    ]},
                    {'name': 'People', 'display_name': 'People', 'icon': 'fas fa-users', 'order_index': 2, 'roles': ['super_admin', 'agency_manager', 'agency_admin'], 'children': [
                        {'name': 'All Users', 'display_name': 'All Users', 'icon': 'fas fa-users-cog', 'url': '/agency/users', 'order_index': 1},
                    ]},
                    {'name': 'Masters', 'display_name': 'Masters', 'icon': 'fas fa-cogs', 'order_index': 3, 'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff', 'salesperson'], 'children': [
                        {'name': 'Masters Dashboard', 'display_name': 'Masters Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/masters/', 'order_index': 1},
                        {'name': 'Locations', 'display_name': 'Locations', 'icon': 'fas fa-map-marker-alt', 'url': '/location/', 'order_index': 2},
                        {'name': 'Categories', 'display_name': 'Categories', 'icon': 'fas fa-tags', 'url': '/masters/categories', 'order_index': 3},
                        {'name': 'Units of Measure', 'display_name': 'Units of Measure', 'icon': 'fas fa-balance-scale', 'url': '/masters/uoms', 'order_index': 4},
                        {'name': 'Tax Masters', 'display_name': 'Tax Masters', 'icon': 'fas fa-percent', 'url': '/masters/tax_masters', 'order_index': 5},
                        {'name': 'Customers', 'display_name': 'Customers', 'icon': 'fas fa-user-friends', 'url': '/customer/', 'order_index': 6},
                        {'name': 'Suppliers', 'display_name': 'Suppliers', 'icon': 'fas fa-truck', 'url': '/inventory/suppliers', 'order_index': 7},
                    ]},
                    {'name': 'Inventory', 'display_name': 'Inventory', 'icon': 'fas fa-boxes', 'order_index': 4, 'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff', 'salesperson'], 'children': [
                        {'name': 'Inventory Dashboard', 'display_name': 'Inventory Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/inventory/dashboard', 'order_index': 1},
                        {'name': 'Products', 'display_name': 'Products', 'icon': 'fas fa-box', 'url': '/product_overrides/list', 'order_index': 2},
                        {'name': 'Stock Levels', 'display_name': 'Stock Levels', 'icon': 'fas fa-layer-group', 'url': '/inventory/stock_levels', 'order_index': 3},
                        {'name': 'Inventory Reports', 'display_name': 'Inventory Reports', 'icon': 'fas fa-chart-bar', 'url': '/inventory/reports', 'order_index': 4},
                    ]},
                    {'name': 'Forecasting', 'display_name': 'Forecasting', 'icon': 'fas fa-chart-line', 'order_index': 5, 'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff'], 'children': [
                        {'name': 'Forecast Dashboard', 'display_name': 'Forecast Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/forecasting/dashboard', 'order_index': 1},
                        {'name': 'Forecast Report', 'display_name': 'Forecast Report', 'icon': 'fas fa-file-alt', 'url': '/forecasting/report', 'order_index': 2},
                        {'name': 'Alert Configuration', 'display_name': 'Alert Configuration', 'icon': 'fas fa-cog', 'url': '/forecasting/alert_config', 'order_index': 3},
                    ]},
                    {'name': 'Sales', 'display_name': 'Sales', 'icon': 'fas fa-shopping-cart', 'order_index': 6, 'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff', 'salesperson', 'pos_user'], 'children': [
                        {'name': 'All Orders', 'display_name': 'All Orders', 'icon': 'fas fa-list', 'url': '/order/', 'order_index': 1},
                        {'name': 'New Sales Order', 'display_name': 'New Sales Order', 'icon': 'fas fa-plus-circle', 'url': '/order/create', 'order_index': 2},
                        {'name': 'Purchase Orders', 'display_name': 'Purchase Orders', 'icon': 'fas fa-receipt', 'url': '/purchase_order/', 'order_index': 3},
                    ]},
                    {'name': 'Accounting', 'display_name': 'Accounting', 'icon': 'fas fa-file-invoice-dollar', 'order_index': 7, 'roles': ['super_admin', 'agency_manager', 'agency_admin', 'accountant'], 'children': [
                        {'name': 'Accounting Dashboard', 'display_name': 'Accounting Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/reports/unified_dashboard', 'order_index': 1},
                        {'name': 'AR Transaction Report', 'display_name': 'AR Transaction Report', 'icon': 'fas fa-chart-bar', 'url': '/reports/accounting_report?report_type=ar', 'order_index': 2},
                        {'name': 'AP Transaction Report', 'display_name': 'AP Transaction Report', 'icon': 'fas fa-chart-line', 'url': '/reports/accounting_report?report_type=ap', 'order_index': 3},
                        {'name': 'Gross Profit Report', 'display_name': 'Gross Profit Report', 'icon': 'fas fa-dollar-sign', 'url': '/reports/accounting_report?report_type=gp', 'order_index': 4},
                    ]},
                    {'name': 'POS', 'display_name': 'POS', 'icon': 'fas fa-cash-register', 'order_index': 8, 'roles': ['super_admin', 'agency_manager', 'agency_admin', 'staff', 'pos_user'], 'children': [
                        {'name': 'POS Dashboard', 'display_name': 'POS Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/pos/dashboard', 'order_index': 1},
                        {'name': 'New POS Sale', 'display_name': 'New POS Sale', 'icon': 'fas fa-plus-circle', 'url': '/pos/sale', 'order_index': 2},
                        {'name': 'Sales History', 'display_name': 'Sales History', 'icon': 'fas fa-history', 'url': '/pos/sales_history', 'order_index': 3},
                    ]},
                    {'name': 'Finance', 'display_name': 'Finance', 'icon': 'fas fa-wallet', 'order_index': 9, 'roles': ['super_admin', 'agency_manager'], 'children': [
                        {'name': 'Finance Dashboard', 'display_name': 'Finance Dashboard', 'icon': 'fas fa-tachometer-alt', 'url': '/reports/unified_dashboard', 'order_index': 1},
                        {'name': 'Payments', 'display_name': 'Payments', 'icon': 'fas fa-money-bill-wave', 'url': '/finance/payments', 'order_index': 2},
                        {'name': 'Receipts', 'display_name': 'Receipts', 'icon': 'fas fa-receipt', 'url': '/finance/receipts', 'order_index': 3},
                        {'name': 'New Payment', 'display_name': 'New Payment', 'icon': 'fas fa-plus-circle', 'url': '/finance/create_payment', 'order_index': 4},
                        {'name': 'New Receipt', 'display_name': 'New Receipt', 'icon': 'fas fa-plus-circle', 'url': '/finance/create_receipt', 'order_index': 5},
                        {'name': 'Payment Configurations', 'display_name': 'Payment Configurations', 'icon': 'fas fa-cogs', 'url': '/finance/payment_configurations', 'order_index': 6},
                    ]},
                    {'name': 'Reports', 'display_name': 'Reports', 'icon': 'fas fa-chart-bar', 'order_index': 10, 'roles': ['super_admin', 'agency_manager', 'agency_admin', 'accountant'], 'children': [
                        {'name': 'Sales Analytics', 'display_name': 'Sales Analytics', 'icon': 'fas fa-chart-line', 'url': '/reports/sales_analytics', 'order_index': 1},
                        {'name': 'AR Aging Report', 'display_name': 'AR Aging Report', 'icon': 'fas fa-hourglass-end', 'url': '/reports/ar_report', 'order_index': 2},
                        {'name': 'AP Aging Report', 'display_name': 'AP Aging Report', 'icon': 'fas fa-hourglass-end', 'url': '/reports/ap_report', 'order_index': 3},
                    ]},
                    {'name': 'Configuration', 'display_name': 'Configuration', 'icon': 'fas fa-sliders-h', 'order_index': 11, 'roles': ['super_admin', 'agency_manager'], 'children': [
                        {'name': 'System Settings', 'display_name': 'System Settings', 'icon': 'fas fa-cog', 'url': '/super_admin/config', 'order_index': 1},
                        {'name': 'Menu Management', 'display_name': 'Menu Management', 'icon': 'fas fa-bars', 'url': '/super_admin/menus', 'order_index': 2},
                    ]},
                ]
                
                # Create all menu items
                for menu_def in menus:
                    parent = create_menu_item(
                        menu_def['name'],
                        menu_def['display_name'],
                        url=menu_def.get('url'),
                        icon=menu_def.get('icon'),
                        order_index=menu_def.get('order_index', 0)
                    )
                    assign_menu_to_role(parent, menu_def['roles'])
                    
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
                            assign_menu_to_role(child, menu_def['roles'])
                
                db.session.commit()
                logging.info(f"✅ Seeded {MenuItem.query.count()} menu items and {MenuRole.query.count()} role assignments")
                return True
            except Exception as e:
                logging.exception(f"Menu seeding failed: {e}")
                return False

        def run_setup():
            try:
                # Only super admin in production (from env)
                if not User.query.filter_by(role='super_admin').first():
                    admin = User(
                        username=os.environ.get("DEFAULT_ADMIN_USER", "admin"),
                        email=os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@system.com"),
                        password_hash=generate_password_hash(os.environ.get("DEFAULT_ADMIN_PASS", "admin123")),
                        role='super_admin',
                        is_active=True
                    )
                    db.session.add(admin)
                    db.session.commit()
                    logging.info("Default super admin created")

                # Seed menus
                seed_menus()

                # Do NOT seed sample/demo data in production as per requirement
                AppSetting.set("app_installed", "true")
                logging.info("Installation flag set")
                return True
            except Exception as e:
                logging.exception("Setup failed: %s", e)
                return False

        if not is_installed():
            logging.info("App not installed. Running setup...")
            run_setup()

    # Register CLI commands
    @app.cli.command('resync-product-names')
    def resync_product_names_command():
        """Resync all item product names across all tables to respect current ProductAgency overrides.
        
        This command updates product names for:
        - Order Items
        - Purchase Order Items  
        - Invoice Items
        - Delivery Challan Items
        """
        try:
            from utils.maintenance import resync_product_names
            from flask import current_app
            
            with app.app_context():
                logging.info('Starting comprehensive product names resync across all item tables...')
                stats = resync_product_names()
                
                # Log results
                logging.info(f'Resync completed:')
                logging.info(f'  - Order Items: {stats["order_items_updated"]} updated')
                logging.info(f'  - Purchase Order Items: {stats["po_items_updated"]} updated')
                logging.info(f'  - Invoice Items: {stats["invoice_items_updated"]} updated')
                logging.info(f'  - Delivery Challan Items: {stats["challan_items_updated"]} updated')
                logging.info(f'  - Total: {stats["total_updated"]} records updated')
                
                if stats['errors']:
                    logging.warning(f'  - Errors: {len(stats["errors"])} error(s) occurred')
                    for error in stats['errors']:
                        logging.warning(f'    - {error}')
                
                # Console output
                print(f'\n✓ Product names resync completed!')
                print(f'  Order Items: {stats["order_items_updated"]} updated')
                print(f'  Purchase Order Items: {stats["po_items_updated"]} updated')
                print(f'  Invoice Items: {stats["invoice_items_updated"]} updated')
                print(f'  Delivery Challan Items: {stats["challan_items_updated"]} updated')
                print(f'  Total: {stats["total_updated"]} records updated\n')
                
                if stats['errors']:
                    print(f'⚠ {len(stats["errors"])} error(s) occurred:')
                    for error in stats['errors']:
                        print(f'  - {error}')
                    print()
                
        except Exception as e:
            logging.error(f'Resync failed: {str(e)}')
            print(f'\n✗ Error: {str(e)}\n')
            return 1
        return 0
    
    return app

app = create_app()
