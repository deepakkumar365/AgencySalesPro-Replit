import os
import logging
from flask import Flask
from markupsafe import escape, Markup
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from datetime import timedelta

# Configure logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
jwt = JWTManager()

def create_app():
    # Load environment variables from .env file
    load_dotenv()

    app = Flask(__name__)
    
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
    
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Initialize extensions
    
    # Custom Jinja2 filter for nl2br
    def nl2br_filter(s):
        if s:
            return Markup(str(escape(s)).replace('\n', '<br>\n'))
        return ''
    app.jinja_env.filters['nl2br'] = nl2br_filter

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
        from billing import billing_bp
        from inventory import inventory_bp
        from reports import reports_bp
        from agency_manager import agency_manager_bp
        from api import api_bp
        from masters.routes import masters_bp
        from subscription import subscription_bp
        from job_accounting import job_accounting_bp
        from product_overrides import overrides_bp

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
        app.register_blueprint(billing_bp, url_prefix='/billing')
        app.register_blueprint(inventory_bp, url_prefix='/inventory')
        app.register_blueprint(reports_bp, url_prefix='/reports')
        app.register_blueprint(agency_manager_bp, url_prefix='/agency_manager')
        app.register_blueprint(api_bp, url_prefix='/api/v1')
        app.register_blueprint(masters_bp, url_prefix='/masters')
        app.register_blueprint(subscription_bp, url_prefix='/subscription')
        app.register_blueprint(job_accounting_bp, url_prefix='/job-accounting')
        app.register_blueprint(overrides_bp)

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

    return app

app = create_app()
