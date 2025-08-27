from flask import render_template, request, redirect, url_for, flash, session, send_file
from werkzeug.utils import secure_filename
import pandas as pd
import io
import os
from app import db
from models import Product, Agency
from product import product_bp
from auth.utils import login_required, agency_access_required
from utils.decorators import log_activity
from utils.excel_utils import export_products_to_excel, import_products_from_excel

@product_bp.route('/')
@login_required
@agency_access_required
def list_products(current_agency_id=None):
    user_role = session.get('role')
    
    # Start with base query
    if user_role == 'super_admin':
        query = Product.query
    else:
        query = Product.query.filter_by(agency_id=current_agency_id)
    
    # Apply filters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    agency_filter = request.args.get('agency')
    category_filter = request.args.get('category')
    status_filter = request.args.get('status')
    
    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Product.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Product.created_at <= date_to_obj)
        except ValueError:
            pass
    
    if agency_filter and user_role == 'super_admin':
        query = query.filter(Product.agency_id == agency_filter)
    
    if category_filter:
        query = query.filter(Product.category == category_filter)
    
    if status_filter == 'active':
        query = query.filter(Product.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Product.is_active == False)
    
    products = query.order_by(Product.created_at.desc()).all()
    
    # Get filter options
    agencies = []
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
    
    # Get unique categories
    if user_role == 'super_admin':
        categories = db.session.query(Product.category.distinct()).filter(Product.category.isnot(None)).all()
    else:
        categories = db.session.query(Product.category.distinct()).filter(Product.agency_id == current_agency_id, Product.category.isnot(None)).all()
    
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('product/list.html', 
                         products=products,
                         agencies=agencies,
                         categories=categories,
                         filters={
                             'date_from': date_from,
                             'date_to': date_to,
                             'agency': agency_filter,
                             'category': category_filter,
                             'status': status_filter
                         })

@product_bp.route('/create', methods=['GET', 'POST'])
@login_required
@log_activity('create_product')
def create_product():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        sku = request.form.get('sku')
        price = request.form.get('price')
        cost = request.form.get('cost')
        stock_quantity = request.form.get('stock_quantity', 0)
        category = request.form.get('category')
        agency_id = request.form.get('agency_id')
        
        user_role = session.get('role')
        current_agency_id = session.get('agency_id')
        
        if not all([name, sku, price]):
            flash('Name, SKU, and price are required', 'error')
            return render_template('product/form.html', agencies=get_agencies_for_user())
        
        # Non-super admin users can only create products for their agency
        if user_role != 'super_admin':
            agency_id = current_agency_id
        
        if not agency_id:
            flash('Agency is required', 'error')
            return render_template('product/form.html', agencies=get_agencies_for_user())
        
        # Check if SKU already exists
        if Product.query.filter_by(sku=sku).first():
            flash('SKU already exists', 'error')
            return render_template('product/form.html', agencies=get_agencies_for_user())
        
        try:
            price = float(price)
            cost = float(cost) if cost else 0
            stock_quantity = int(stock_quantity) if stock_quantity else 0
        except ValueError:
            flash('Invalid numeric values', 'error')
            return render_template('product/form.html', agencies=get_agencies_for_user())
        
        product = Product(
            name=name,
            description=description,
            sku=sku,
            price=price,
            cost=cost,
            stock_quantity=stock_quantity,
            category=category,
            agency_id=agency_id,
            is_active=True
        )
        
        db.session.add(product)
        db.session.commit()
        
        flash('Product created successfully!', 'success')
        return redirect(url_for('product.list_products'))
    
    return render_template('product/form.html', agencies=get_agencies_for_user())

@product_bp.route('/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
@log_activity('edit_product')
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and product.agency_id != current_agency_id:
        flash('You can only edit products from your agency', 'error')
        return redirect(url_for('product.list_products'))
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.sku = request.form.get('sku')
        price = request.form.get('price')
        cost = request.form.get('cost')
        stock_quantity = request.form.get('stock_quantity')
        product.category = request.form.get('category')
        
        # Super admin can change agency
        if user_role == 'super_admin':
            agency_id = request.form.get('agency_id')
            if agency_id:
                product.agency_id = agency_id
        
        if not all([product.name, product.sku, price]):
            flash('Name, SKU, and price are required', 'error')
            return render_template('product/form.html', product=product, agencies=get_agencies_for_user())
        
        # Check if SKU already exists (excluding current product)
        existing = Product.query.filter_by(sku=product.sku).first()
        if existing and existing.id != product.id:
            flash('SKU already exists', 'error')
            return render_template('product/form.html', product=product, agencies=get_agencies_for_user())
        
        try:
            product.price = float(price)
            product.cost = float(cost) if cost else 0
            product.stock_quantity = int(stock_quantity) if stock_quantity else 0
        except ValueError:
            flash('Invalid numeric values', 'error')
            return render_template('product/form.html', product=product, agencies=get_agencies_for_user())
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('product.list_products'))
    
    return render_template('product/form.html', product=product, agencies=get_agencies_for_user())

@product_bp.route('/<int:product_id>/toggle_status', methods=['POST'])
@login_required
@log_activity('toggle_product_status')
def toggle_product_status(product_id):
    product = Product.query.get_or_404(product_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and product.agency_id != current_agency_id:
        flash('You can only modify products from your agency', 'error')
        return redirect(url_for('product.list_products'))
    
    product.is_active = not product.is_active
    db.session.commit()
    
    status = 'activated' if product.is_active else 'deactivated'
    flash(f'Product {status} successfully!', 'success')
    return redirect(url_for('product.list_products'))

@product_bp.route('/<int:product_id>/delete', methods=['POST'])
@login_required
@log_activity('delete_product')
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Check permissions
    if user_role != 'super_admin' and product.agency_id != current_agency_id:
        flash('You can only delete products from your agency', 'error')
        return redirect(url_for('product.list_products'))
    
    # Check if product has order items
    if product.order_items:
        flash('Cannot delete product with existing orders', 'error')
        return redirect(url_for('product.list_products'))
    
    db.session.delete(product)
    db.session.commit()
    
    flash('Product deleted successfully!', 'success')
    return redirect(url_for('product.list_products'))

@product_bp.route('/export')
@login_required
@log_activity('export_products')
def export_products():
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    if user_role == 'super_admin':
        products = Product.query.all()
    else:
        products = Product.query.filter_by(agency_id=current_agency_id).all()
    
    # Create Excel file
    output = export_products_to_excel(products)
    
    return send_file(
        output,
        as_attachment=True,
        download_name='products_export.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@product_bp.route('/import', methods=['GET', 'POST'])
@login_required
@log_activity('import_products')
def import_products():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
            flash('Invalid file format. Please upload Excel or CSV file', 'error')
            return redirect(request.url)
        
        try:
            user_role = session.get('role')
            current_agency_id = session.get('agency_id')
            
            # Import products
            result = import_products_from_excel(file, current_agency_id, user_role)
            
            if result['success']:
                flash(f"Successfully imported {result['imported']} products. Skipped {result['skipped']} duplicates.", 'success')
            else:
                flash(f"Import failed: {result['message']}", 'error')
                
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'error')
        
        return redirect(url_for('product.list_products'))
    
    return render_template('product/import.html')

def get_agencies_for_user():
    """Get agencies based on current user role"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        return Agency.query.filter_by(is_active=True).all()
    else:
        agency_id = session.get('agency_id')
        return Agency.query.filter_by(id=agency_id, is_active=True).all()
