from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from models import Category, UOM, TaxMaster, Agency, db
from functools import wraps
from datetime import datetime
from utils.pagination import apply_pagination

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def log_activity(activity_type):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Simple activity logging - can be enhanced later
            return f(*args, **kwargs)
        return decorated_function
    return decorator

masters_bp = Blueprint('masters', __name__, url_prefix='/masters')

@masters_bp.route('/')
@login_required
def index():
    """Masters dashboard"""
    user_role = session.get('role')
    agency_id = session.get('agency_id')
    
    # Global masters: counts are not agency-specific
    categories = Category.query.filter_by(is_active=True).count()
    uoms = UOM.query.filter_by(is_active=True).count()
    tax_masters = TaxMaster.query.filter_by(is_active=True).count()
    
    return render_template('masters/dashboard.html', 
                         categories=categories, 
                         uoms=uoms, 
                         tax_masters=tax_masters)

# Category Master Routes
@masters_bp.route('/categories')
@login_required
def categories():
    """List all categories with pagination"""
    pagination = apply_pagination(Category.query.order_by(Category.name.asc()))
    
    return render_template('masters/categories.html', 
                           pagination=pagination)

@masters_bp.route('/categories/create', methods=['GET', 'POST'])
@login_required
@log_activity('create_category')
def create_category():
    """Create new category"""
    if request.method == 'POST':
        name = request.form.get('name')
        short_name = request.form.get('short_name', '').strip()
        description = request.form.get('description')
        if not name or not short_name:
            flash('Category name and short name are required', 'error')
            return render_template('masters/category_form.html')
        if len(short_name) != 3:
            flash('Short name must be exactly 3 characters', 'error')
            return render_template('masters/category_form.html')
        
        category = Category(
            name=name,
            short_name=short_name.upper(),
            description=description
        )
        
        try:
            db.session.add(category)
            db.session.commit()
            flash('Category created successfully', 'success')
            return redirect(url_for('masters.categories'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating category', 'error')
    
    return render_template('masters/category_form.html')

# UOM Master Routes
@masters_bp.route('/uoms')
@login_required
def uoms():
    """List all UOMs with pagination"""
    pagination = apply_pagination(UOM.query.order_by(UOM.name.asc()))
    
    return render_template('masters/uoms.html', 
                           pagination=pagination)

@masters_bp.route('/uoms/create', methods=['GET', 'POST'])
@login_required
@log_activity('create_uom')
def create_uom():
    """Create new UOM"""
    if request.method == 'POST':
        name = request.form.get('name')
        short_name = request.form.get('short_name')
        description = request.form.get('description')
        if not name or not short_name:
            flash('UOM name and short name are required', 'error')
            return render_template('masters/uom_form.html')
        
        uom = UOM(
            name=name,
            short_name=short_name,
            description=description
        )
        
        try:
            db.session.add(uom)
            db.session.commit()
            flash('UOM created successfully', 'success')
            return redirect(url_for('masters.uoms'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating UOM', 'error')
    
    return render_template('masters/uom_form.html')

# Tax Master Routes
@masters_bp.route('/tax-masters')
@login_required
def tax_masters():
    """List all tax masters with pagination"""
    pagination = apply_pagination(TaxMaster.query.order_by(TaxMaster.name.asc()))
    
    return render_template('masters/tax_masters.html', 
                           pagination=pagination)

@masters_bp.route('/tax-masters/create', methods=['GET', 'POST'])
@login_required
@log_activity('create_tax_master')
def create_tax_master():
    """Create new tax master"""
    if request.method == 'POST':
        name = request.form.get('name')
        tax_code = request.form.get('tax_code')
        tax_rate = request.form.get('tax_rate')
        description = request.form.get('description')
        if not name or not tax_code or not tax_rate:
            flash('Name, tax code and tax rate are required', 'error')
            return render_template('masters/tax_master_form.html')
        
        tax_master = TaxMaster(
            name=name,
            tax_code=tax_code,
            tax_rate=float(tax_rate),
            description=description
        )
        
        try:
            db.session.add(tax_master)
            db.session.commit()
            flash('Tax master created successfully', 'success')
            return redirect(url_for('masters.tax_masters'))
        except Exception as e:
            db.session.rollback()
            flash('Error creating tax master', 'error')
    
    return render_template('masters/tax_master_form.html')

# API endpoints for dropdowns
@masters_bp.route('/api/categories')
@login_required
def api_categories():
    """Get categories for dropdowns"""
    user_role = session.get('role')
    agency_id = session.get('agency_id')
    
    # Global masters
    categories = Category.query.filter_by(is_active=True).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'short_name': c.short_name,
        'description': c.description
    } for c in categories])

@masters_bp.route('/api/uoms')
@login_required
def api_uoms():
    """Get UOMs for dropdowns"""
    user_role = session.get('role')
    agency_id = session.get('agency_id')
    
    # Global masters
    uoms = UOM.query.filter_by(is_active=True).all()
    
    return jsonify([{
        'id': u.id,
        'name': u.name,
        'short_name': u.short_name,
        'description': u.description
    } for u in uoms])

@masters_bp.route('/api/tax-masters')
@login_required
def api_tax_masters():
    """Get tax masters for dropdowns"""
    user_role = session.get('role')
    agency_id = session.get('agency_id')
    
    # Global masters
    tax_masters = TaxMaster.query.filter_by(is_active=True).all()
    
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'tax_code': t.tax_code,
        'tax_rate': float(t.tax_rate),
        'description': t.description
    } for t in tax_masters])