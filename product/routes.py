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
        query = query.filter(Product.category_id == category_filter)
    
    if status_filter == 'active':
        query = query.filter(Product.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(Product.is_active == False)
    
    products = query.order_by(Product.created_at.desc()).all()
    
    # Get filter options
    agencies = []
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
    
    # Get unique categories from Category table
    from models import Category
    if user_role == 'super_admin':
        categories = Category.query.filter_by(is_active=True).all()
    else:
        categories = Category.query.filter_by(agency_id=current_agency_id, is_active=True).all()
    
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
        sku = request.form.get('sku')
        buy_price = request.form.get('buy_price')
        sell_price = request.form.get('sell_price')
        mrp_price = request.form.get('mrp_price')
        category_id = request.form.get('category_id')
        uom_id = request.form.get('uom_id')
        tax_master_id = request.form.get('tax_master_id')
        agency_id = request.form.get('agency_id')
        
        user_role = session.get('role')
        current_agency_id = session.get('agency_id')
        
        if not all([name, sku, buy_price, sell_price, mrp_price]):
            flash('Name, SKU, Buy Price, Sell Price, and MRP are required', 'error')
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
            buy_price = float(buy_price) if buy_price else 0.0
            sell_price = float(sell_price) if sell_price else 0.0
            mrp_price = float(mrp_price) if mrp_price else 0.0
        except (ValueError, TypeError):
            flash('Invalid numeric values', 'error')
            return render_template('product/form.html', agencies=get_agencies_for_user())
        
        # Calculate margin
        margin = round(((sell_price - buy_price) / buy_price) * 100, 2) if buy_price > 0 else 0
        
        product = Product(
            name=name,
            sku=sku,
            buy_price=buy_price,
            sell_price=sell_price,
            mrp_price=mrp_price,
            margin=margin,
            category_id=int(category_id) if category_id else None,
            uom_id=int(uom_id) if uom_id else None,
            tax_master_id=int(tax_master_id) if tax_master_id else None,
            agency_id=agency_id,
            is_active=True
        )
        
        # Sync legacy fields for backward compatibility
        product.price = sell_price
        product.cost = buy_price
        
        db.session.add(product)
        db.session.commit()
        
        flash('Product created successfully!', 'success')
        return redirect(url_for('product.list_products'))
    
    # Get master data for dropdowns
    from models import Category, UOM, TaxMaster
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    if user_role == 'super_admin':
        categories = Category.query.filter_by(is_active=True).all()
        uoms = UOM.query.filter_by(is_active=True).all()
        tax_masters = TaxMaster.query.filter_by(is_active=True).all()
    else:
        categories = Category.query.filter_by(agency_id=current_agency_id, is_active=True).all()
        uoms = UOM.query.filter_by(agency_id=current_agency_id, is_active=True).all()
        tax_masters = TaxMaster.query.filter_by(agency_id=current_agency_id, is_active=True).all()
    
    return render_template('product/form.html', 
                         agencies=get_agencies_for_user(),
                         categories=categories,
                         uoms=uoms,
                         tax_masters=tax_masters)

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
        product.sku = request.form.get('sku')
        buy_price = request.form.get('buy_price')
        sell_price = request.form.get('sell_price')
        mrp_price = request.form.get('mrp_price')
        category_id = request.form.get('category_id')
        uom_id = request.form.get('uom_id')
        tax_master_id = request.form.get('tax_master_id')
        
        # Super admin can change agency
        if user_role == 'super_admin':
            agency_id = request.form.get('agency_id')
            if agency_id:
                product.agency_id = agency_id
        
        if not all([product.name, product.sku, buy_price, sell_price, mrp_price]):
            flash('Name, SKU, Buy Price, Sell Price, and MRP are required', 'error')
            return render_template('product/form.html', product=product, agencies=get_agencies_for_user())
        
        # Check if SKU already exists (excluding current product)
        existing = Product.query.filter_by(sku=product.sku).first()
        if existing and existing.id != product.id:
            flash('SKU already exists', 'error')
            return render_template('product/form.html', product=product, agencies=get_agencies_for_user())
        
        try:
            product.buy_price = float(buy_price)
            product.sell_price = float(sell_price)
            product.mrp_price = float(mrp_price)
            product.margin = round(((float(sell_price) - float(buy_price)) / float(buy_price)) * 100, 2) if float(buy_price) > 0 else 0
            product.category_id = int(category_id) if category_id else None
            product.uom_id = int(uom_id) if uom_id else None
            product.tax_master_id = int(tax_master_id) if tax_master_id else None
        except ValueError:
            flash('Invalid numeric values', 'error')
            return render_template('product/form.html', product=product, agencies=get_agencies_for_user())
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('product.list_products'))
    
    # Get master data for dropdowns
    from models import Category, UOM, TaxMaster
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    if user_role == 'super_admin':
        categories = Category.query.filter_by(is_active=True).all()
        uoms = UOM.query.filter_by(is_active=True).all()
        tax_masters = TaxMaster.query.filter_by(is_active=True).all()
    else:
        categories = Category.query.filter_by(agency_id=current_agency_id, is_active=True).all()
        uoms = UOM.query.filter_by(agency_id=current_agency_id, is_active=True).all()
        tax_masters = TaxMaster.query.filter_by(agency_id=current_agency_id, is_active=True).all()
    
    return render_template('product/form.html', 
                         product=product,
                         agencies=get_agencies_for_user(),
                         categories=categories,
                         uoms=uoms,
                         tax_masters=tax_masters)

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
