import os
import logging
from flask import Flask
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
    app = Flask(__name__)
    
    # Configuration
    app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///agency_sales.db")
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "jwt-secret-string")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
    
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    
    # Initialize extensions
    db.init_app(app)
    jwt.init_app(app)
    
    # Register blueprints
    from auth import auth_bp
    from agency import agency_bp
    from salesperson import salesperson_bp
    from location import location_bp
    from customer import customer_bp
    from product import product_bp
    from order import order_bp
    from super_admin import super_admin_bp
    from api import api_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(agency_bp, url_prefix='/agency')
    app.register_blueprint(salesperson_bp, url_prefix='/salesperson')
    app.register_blueprint(location_bp, url_prefix='/location')
    app.register_blueprint(customer_bp, url_prefix='/customer')
    app.register_blueprint(product_bp, url_prefix='/product')
    app.register_blueprint(order_bp, url_prefix='/order')
    app.register_blueprint(super_admin_bp, url_prefix='/super_admin')
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    
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
        
        # Create default super admin if not exists
        from models import User, Agency
        from werkzeug.security import generate_password_hash
        
        if not User.query.filter_by(role='super_admin').first():
            admin = User(
                username='admin',
                email='admin@system.com',
                password_hash=generate_password_hash('admin123'),
                role='super_admin',
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            logging.info("Default super admin created: admin/admin123")
        
        # Create sample agency and users for testing
        if not Agency.query.first():
            # Create sample agency
            sample_agency = Agency(
                name='Sample Marketing Agency',
                code='SMA001',
                address='123 Business Street, City, State 12345',
                phone='(555) 123-4567',
                email='info@sampleagency.com',
                is_active=True
            )
            db.session.add(sample_agency)
            db.session.commit()
            
            # Create agency admin
            agency_admin = User(
                username='agency_admin',
                email='admin@sampleagency.com',
                password_hash=generate_password_hash('admin123'),
                first_name='John',
                last_name='Manager',
                role='agency_admin',
                agency_id=sample_agency.id,
                is_active=True
            )
            
            # Create agency staff
            agency_staff = User(
                username='agency_staff',
                email='staff@sampleagency.com',
                password_hash=generate_password_hash('staff123'),
                first_name='Jane',
                last_name='Staff',
                role='staff',
                agency_id=sample_agency.id,
                is_active=True
            )
            
            # Create salesperson
            salesperson = User(
                username='salesperson',
                email='sales@sampleagency.com',
                password_hash=generate_password_hash('sales123'),
                first_name='Mike',
                last_name='Sales',
                role='salesperson',
                agency_id=sample_agency.id,
                is_active=True
            )
            
            db.session.add_all([agency_admin, agency_staff, salesperson])
            db.session.commit()
            logging.info("Sample agency and users created:")
            logging.info("  Agency Admin: agency_admin/admin123")
            logging.info("  Staff: agency_staff/staff123")
            logging.info("  Salesperson: salesperson/sales123")
    
    return app

app = create_app()
