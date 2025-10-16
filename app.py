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
from extensions import db, jwt

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
    from auth.utils import inject_permissions

    @app.context_processor
    def _inject_permissions_context():
        return inject_permissions()

    db.init_app(app)
    jwt.init_app(app)
    
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
        from service import service_bp
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
        app.register_blueprint(service_bp) # No prefix, as it's an API blueprint with its own prefix
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
