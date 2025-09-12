from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
from decimal import Decimal
from app import db
from models import (
    Product, Agency, Location, User,
    InventoryTransaction, Supplier, PurchaseOrder
)
from inventory import inventory_bp
from auth.utils import login_required, agency_access_required, get_role_permissions
from utils.decorators import log_activity
import uuid

@inventory_bp.route('/dashboard')
@login_required
@agency_access_required
def dashboard(current_agency_id=None):
    """Inventory Dashboard with stock levels and alerts"""
    user_role = session.get('role')
    
    # Base query for products
    if user_role == 'super_admin':
        base_query = Product.query
    else:
        from models import ProductAgency
        base_query = db.session.query(Product).join(ProductAgency, ProductAgency.product_id == Product.id).filter(ProductAgency.agency_id == current_agency_id)
    
    # Stock level analysis (disabled - stock tracking removed)
    total_products = base_query.filter_by(is_active=True).count()
    low_stock_products = []
    out_of_stock_products = []
    
    # Calculate total inventory value (disabled)
    active_products = base_query.filter_by(is_active=True).all()
    total_inventory_value = 0
    
    # Recent inventory transactions
    if user_role == 'super_admin':
        recent_transactions = InventoryTransaction.query.order_by(
            InventoryTransaction.created_at.desc()
        ).limit(10).all()
    else:
        from models import ProductAgency
        recent_transactions = InventoryTransaction.query.join(Product).join(ProductAgency).filter(
            ProductAgency.agency_id == current_agency_id
        ).order_by(InventoryTransaction.created_at.desc()).limit(10).all()
    
    # Stock movement trends (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    if user_role == 'super_admin':
        movement_transactions = InventoryTransaction.query.filter(
            InventoryTransaction.created_at >= thirty_days_ago
        ).all()
    else:
        from models import ProductAgency
        movement_transactions = InventoryTransaction.query.join(Product).join(ProductAgency).filter(
            ProductAgency.agency_id == current_agency_id,
            InventoryTransaction.created_at >= thirty_days_ago
        ).all()
    
    total_in = sum(t.quantity_change for t in movement_transactions if t.quantity_change > 0)
    total_out = abs(sum(t.quantity_change for t in movement_transactions if t.quantity_change < 0))
    
    dashboard_stats = {
        'total_products': total_products,
        'low_stock_count': len(low_stock_products),
        'out_of_stock_count': len(out_of_stock_products),
        'total_inventory_value': total_inventory_value,
        'total_in_30_days': total_in,
        'total_out_30_days': total_out
    }
    
    return render_template('inventory/dashboard.html',
                         stats=dashboard_stats,
                         low_stock_products=low_stock_products[:5],  # Top 5 for display
                         out_of_stock_products=out_of_stock_products[:5],
                         recent_transactions=recent_transactions)

@inventory_bp.route('/stock_levels')
@login_required
@agency_access_required
def stock_levels(current_agency_id=None):
    """View and manage stock levels"""
    user_role = session.get('role')
    
    # Get filter parameters
    category = request.args.get('category')
    stock_status = request.args.get('stock_status')
    search = request.args.get('search', '').strip()
    
    # Base query
    if user_role == 'super_admin':
        query = Product.query.filter_by(is_active=True)
    else:
        from models import ProductAgency
        query = db.session.query(Product).join(ProductAgency, ProductAgency.product_id == Product.id)\
            .filter(ProductAgency.agency_id == current_agency_id, Product.is_active == True)
    
    # Apply filters
    if category:
        query = query.filter_by(category_id=category)
    
    if search:
        query = query.filter(
            db.or_(
                Product.name.ilike(f'%{search}%'),
                Product.sku.ilike(f'%{search}%')
            )
        )
    
    # Stock status filtering disabled (stock tracking removed)
    if stock_status == 'low':
        query = query.filter(Product.id == -1)  # No results
    elif stock_status == 'out':
        query = query.filter(Product.id == -1)  # No results
    elif stock_status == 'normal':
        pass  # Show all products
    
    # Get paginated results
    products = query.order_by(Product.name).paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20,
        error_out=False
    )
    
    # Get unique categories for filter from Category table
    from models import Category
    categories = Category.query.filter_by(is_active=True).all()
    
    return render_template('inventory/stock_levels.html',
                         products=products,
                         categories=categories,
                         current_filters={
                             'category': category,
                             'stock_status': stock_status,
                             'search': search
                         })

@inventory_bp.route('/adjust_stock/<int:product_id>', methods=['GET', 'POST'])
@login_required
@agency_access_required
@log_activity('stock_adjusted')
def adjust_stock(product_id, current_agency_id=None):
    """Adjust stock levels for a product"""
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Get product with permission check
    if user_role == 'super_admin':
        product = Product.query.get_or_404(product_id)
    else:
        from models import ProductAgency
        product = db.session.query(Product).join(ProductAgency, ProductAgency.product_id == Product.id)\
            .filter(Product.id == product_id, ProductAgency.agency_id == current_agency_id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Get form data
            adjustment_type = request.form.get('adjustment_type')  # 'increase' or 'decrease'
            quantity = int(request.form.get('quantity', 0))
            reason = request.form.get('reason', '').strip()
            notes = request.form.get('notes', '').strip()
            
            # Validate
            if quantity <= 0:
                flash('Quantity must be greater than 0', 'error')
                return render_template('inventory/adjust_stock.html', product=product)
            
            # Stock adjustment disabled (stock tracking removed)
            flash('Stock management has been disabled', 'info')
            return render_template('inventory/adjust_stock.html', product=product)
            
            # Create inventory transaction
            transaction = InventoryTransaction(
                product_id=product.id,
                transaction_type='adjustment',
                quantity_change=quantity_change,
                quantity_before=quantity_before,
                quantity_after=product.stock_quantity,
                unit_cost=product.cost,
                reference_type='manual_adjustment',
                notes=f'{reason}: {notes}' if notes else reason,
                created_by=user_id
            )
            
            db.session.add(transaction)
            db.session.commit()
            
            flash(f'Stock adjusted successfully. New quantity: {product.stock_quantity}', 'success')
            return redirect(url_for('inventory.stock_levels'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adjusting stock: {str(e)}', 'error')
    
    return render_template('inventory/adjust_stock.html', product=product)

@inventory_bp.route('/transactions')
@login_required
@agency_access_required
def transaction_history(current_agency_id=None):
    """View inventory transaction history"""
    user_role = session.get('role')
    
    # Get filter parameters
    product_id = request.args.get('product_id')
    transaction_type = request.args.get('transaction_type')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Base query
    if user_role == 'super_admin':
        query = InventoryTransaction.query
    else:
        from models import ProductAgency
        query = InventoryTransaction.query.join(Product).join(ProductAgency).filter(
            ProductAgency.agency_id == current_agency_id
        )
    
    # Apply filters
    if product_id:
        query = query.filter(InventoryTransaction.product_id == product_id)
    
    if transaction_type:
        query = query.filter(InventoryTransaction.transaction_type == transaction_type)
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(InventoryTransaction.created_at >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(InventoryTransaction.created_at <= end_dt)
        except ValueError:
            pass
    
    # Get paginated results
    transactions = query.order_by(InventoryTransaction.created_at.desc()).paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20,
        error_out=False
    )
    
    # Get products for filter dropdown
    if user_role == 'super_admin':
        products = Product.query.filter_by(is_active=True).all()
    else:
        from models import ProductAgency
        products = db.session.query(Product).join(ProductAgency).filter(ProductAgency.agency_id == current_agency_id, Product.is_active == True).all()
    
    return render_template('inventory/transactions.html',
                         transactions=transactions,
                         products=products,
                         current_filters={
                             'product_id': product_id,
                             'transaction_type': transaction_type,
                             'start_date': start_date,
                             'end_date': end_date
                         })

@inventory_bp.route('/suppliers')
@login_required
@agency_access_required
def list_suppliers(current_agency_id=None):
    """List suppliers for inventory management"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        suppliers = Supplier.query.all()
    else:
        suppliers = Supplier.query.filter_by(agency_id=current_agency_id).all()
    
    return render_template('inventory/suppliers.html', suppliers=suppliers)

@inventory_bp.route('/add_supplier', methods=['GET', 'POST'])
@login_required
@agency_access_required
@log_activity('supplier_added')
def add_supplier(current_agency_id=None):
    """Add new supplier"""
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            contact_person = request.form.get('contact_person', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            notes = request.form.get('notes', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            # Validation
            if not name:
                flash('Supplier name is required', 'error')
                return render_template('inventory/add_supplier.html')
            
            # Check for duplicate name within agency
            user_role = session.get('role')
            if user_role == 'super_admin':
                existing = Supplier.query.filter_by(name=name).first()
            else:
                existing = Supplier.query.filter_by(
                    name=name, agency_id=current_agency_id
                ).first()
            
            if existing:
                flash('Supplier with this name already exists', 'error')
                return render_template('inventory/add_supplier.html')
            
            # Create supplier
            supplier = Supplier(
                name=name,
                contact_person=contact_person,
                email=email,
                phone=phone,
                address=address,
                notes=notes,
                agency_id=current_agency_id,
                is_active=is_active
            )
            
            db.session.add(supplier)
            db.session.commit()
            
            flash('Supplier added successfully', 'success')
            return redirect(url_for('inventory.list_suppliers'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding supplier: {str(e)}', 'error')
    
    return render_template('inventory/add_supplier.html')

@inventory_bp.route('/reports')
@login_required
@agency_access_required
def reports(current_agency_id=None):
    """Inventory reports and analytics"""
    user_role = session.get('role')
    
    # Get date range from query params (default to current month)
    today = datetime.utcnow().date()
    start_date = request.args.get('start_date', today.replace(day=1).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', today.strftime('%Y-%m-%d'))
    
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        start_dt = datetime.combine(today.replace(day=1), datetime.min.time())
        end_dt = datetime.combine(today, datetime.max.time())
    
    # Base queries
    if user_role == 'super_admin':
        product_query = Product.query.filter_by(is_active=True)
        transaction_query = InventoryTransaction.query
    else:
        from models import ProductAgency
        product_query = db.session.query(Product).join(ProductAgency, ProductAgency.product_id == Product.id)\
            .filter(ProductAgency.agency_id == current_agency_id, Product.is_active == True)
        transaction_query = InventoryTransaction.query.join(Product).join(ProductAgency).filter(
            ProductAgency.agency_id == current_agency_id
        )
    
    # Stock level analysis
    products = product_query.all()
    total_products = len(products)
    total_inventory_value = 0  # Stock tracking disabled
    low_stock_count = 0
    out_of_stock_count = 0
    
    # Movement analysis for period
    period_transactions = transaction_query.filter(
        InventoryTransaction.created_at >= start_dt,
        InventoryTransaction.created_at <= end_dt
    ).all()
    
    # Calculate movement totals by type
    movement_summary = {}
    for transaction in period_transactions:
        tx_type = transaction.transaction_type
        if tx_type not in movement_summary:
            movement_summary[tx_type] = {'in': 0, 'out': 0, 'count': 0}
        
        movement_summary[tx_type]['count'] += 1
        if transaction.quantity_change > 0:
            movement_summary[tx_type]['in'] += transaction.quantity_change
        else:
            movement_summary[tx_type]['out'] += abs(transaction.quantity_change)
    
    # Top products by movement
    product_movements = {}
    for transaction in period_transactions:
        product_id = transaction.product_id
        if product_id not in product_movements:
            product_movements[product_id] = {
                'product': transaction.product,
                'total_movement': 0
            }
        product_movements[product_id]['total_movement'] += abs(transaction.quantity_change)
    
    top_products = sorted(
        product_movements.values(),
        key=lambda x: x['total_movement'],
        reverse=True
    )[:10]
    
    report_data = {
        'total_products': total_products,
        'total_inventory_value': total_inventory_value,
        'low_stock_count': low_stock_count,
        'out_of_stock_count': out_of_stock_count,
        'period_transactions': len(period_transactions),
        'start_date': start_date,
        'end_date': end_date
    }
    
    return render_template('inventory/reports.html',
                         report_data=report_data,
                         movement_summary=movement_summary,
                         top_products=top_products)