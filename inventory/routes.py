from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
from decimal import Decimal
from app import db
from models import (
    Product, Agency, Location, User, ProductAgency, Category,
    InventoryTransaction, Supplier, PurchaseOrder
)
from inventory import inventory_bp
from auth.utils import login_required, permission_required, get_role_permissions
from utils.decorators import log_activity
import uuid


def _get_agency_context(user_role, current_agency_id, form):
    """Determine agency context for supplier operations."""
    if user_role == 'super_admin':
        selected_agency_id = form.get('agency_id', '').strip()
        if not selected_agency_id:
            return None, 'Please select an agency for this supplier.'
        try:
            agency_id = int(selected_agency_id)
        except ValueError:
            return None, 'Invalid agency selection.'
        return agency_id, None

    return current_agency_id, None if current_agency_id else 'Unable to determine agency context for supplier.'


def _build_supplier_form_data(supplier):
    """Prepare supplier data for form rendering."""
    return {
        'agency_id': str(supplier.agency_id) if supplier.agency_id else '',
        'name': supplier.name or '',
        'contact_person': supplier.contact_person or '',
        'email': supplier.email or '',
        'phone': supplier.phone or '',
        'address': supplier.address or '',
        'notes': supplier.notes or '',
        'is_active': 'on' if supplier.is_active else ''
    }

@inventory_bp.route('/dashboard')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def dashboard(current_agency_id=None):
    """Inventory Dashboard with stock levels and alerts"""
    from sqlalchemy import func, case
    user_role = session.get('role')

    # Subquery to calculate current stock for each product
    stock_subquery = db.session.query(
        InventoryTransaction.product_id,
        func.sum(InventoryTransaction.quantity_change).label('stock_quantity')
    ).group_by(InventoryTransaction.product_id).subquery()

    # Base query joining products, agency mappings, and the calculated stock
    query = db.session.query(
        ProductAgency.id,
        ProductAgency.buy_price,
        ProductAgency.agency_id,
        # Add other ProductAgency columns if needed by the template
        # For example: ProductAgency.display_name
        # We need the agency object itself for the template
        Agency,
        Product,
        stock_subquery.c.stock_quantity
    ).join(Product, ProductAgency.product_id == Product.id)\
     .join(Agency, ProductAgency.agency_id == Agency.id)\
     .outerjoin(stock_subquery, Product.id == stock_subquery.c.product_id)\
     .filter(ProductAgency.is_active == True and stock_subquery.c.stock_quantity != None)

    if user_role != 'super_admin':
        query = query.filter(ProductAgency.agency_id == current_agency_id)

    print(query)
    results = query.all()

    low_stock_products = []
    out_of_stock_products = []
    total_inventory_value = Decimal(0)

    # The query now returns a tuple with the columns we selected
    for pa_id, pa_buy_price, agency_id, agency, product, stock_quantity in results:
        stock = stock_quantity or 0
        # NOTE: low_stock_threshold is not on the model. Using a hardcoded value of 10 for now.
        low_stock_threshold = 10 
        if stock <= 0:
            out_of_stock_products.append(product)
        elif stock <= low_stock_threshold:
            low_stock_products.append(product)
        
        total_inventory_value += (pa_buy_price or product.buy_price or 0) * stock

    # Recent inventory transactions
    if user_role == 'super_admin':
        recent_transactions = InventoryTransaction.query.order_by(
            InventoryTransaction.created_at.desc()
        ).limit(10).all()
    else:
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
        movement_transactions = InventoryTransaction.query.join(Product).join(ProductAgency).filter(
            ProductAgency.agency_id == current_agency_id,
            InventoryTransaction.created_at >= thirty_days_ago
        ).all()

    total_in = sum(t.quantity_change for t in movement_transactions if t.quantity_change > 0)
    total_out = abs(sum(t.quantity_change for t in movement_transactions if t.quantity_change < 0))

    dashboard_stats = {
        'total_products': len(results),
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
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def stock_levels(current_agency_id=None):
    """View and manage stock levels"""
    user_role = session.get('role')
    
    # Get filter parameters
    category = request.args.get('category')
    stock_status = request.args.get('stock_status')
    search = request.args.get('search', '').strip()
    
    # Subquery to calculate current stock for each product
    from sqlalchemy import func
    stock_subquery = db.session.query(
        InventoryTransaction.product_id,
        func.sum(InventoryTransaction.quantity_change).label('stock_quantity')
    ).group_by(InventoryTransaction.product_id).subquery()

    # Base query joining products with their calculated stock
    query = db.session.query(
        Product,
        func.coalesce(stock_subquery.c.stock_quantity, 0).label('current_stock')
    ).outerjoin(stock_subquery, Product.id == stock_subquery.c.product_id)

    # Filter by agency for non-super-admins
    if user_role != 'super_admin':
        query = query.join(ProductAgency, Product.id == ProductAgency.product_id)\
            .filter(ProductAgency.agency_id == current_agency_id)

    query = query.filter(Product.is_active == True)

    # Apply filters
    if category:
        query = query.filter(Product.category_id == category)
    
    if search:
        query = query.filter(
            or_(
                Product.name.ilike(f'%{search}%'),
                Product.sku.ilike(f'%{search}%')
            )
        )
    
    # Apply stock status filter on the calculated column
    # NOTE: Using a hardcoded low_stock_threshold of 10. This should ideally be a setting or a model field.
    if stock_status:
        # We need to wrap the query to filter on the alias 'current_stock'
        aliased_query = query.subquery()
        query = db.session.query(aliased_query)
        if stock_status == 'out':
            query = query.filter(aliased_query.c.current_stock <= 0)
        elif stock_status == 'low':
            query = query.filter(aliased_query.c.current_stock.between(1, 10))
        elif stock_status == 'normal':
            query = query.filter(aliased_query.c.current_stock > 10)

        # When filtering, we query from the subquery, so we order by its columns
        # The columns of the subquery are named after the original query's columns
        query = query.order_by(aliased_query.c.name)
    else:
        # Order by the original Product.name if no subquery was created
        query = query.order_by(Product.name)

    # Get paginated results
    products_with_stock = query.paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20,
        error_out=False
    )
    
    categories = Category.query.filter_by(is_active=True).all()
    
    return render_template('inventory/stock_levels.html',
                         products=products_with_stock,
                         categories=categories,
                         current_filters={
                             'category': category,
                             'stock_status': stock_status,
                             'search': search
                         })

@inventory_bp.route('/adjust_stock/<int:product_id>', methods=['GET', 'POST'])
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('stock_adjusted')
def adjust_stock(product_id, current_agency_id=None):
    """Adjust stock levels for a product"""
    user_role = session.get('role')
    user_id = session.get('user_id')

    # Get product with permission check
    if user_role == 'super_admin':
        product = Product.query.get_or_404(product_id)
        # For super_admin, we need to know which agency's stock to adjust.
        # This needs to be passed in the form or as a query parameter.
        # For now, let's assume it's passed in the form.
        agency_id_from_form = request.form.get('agency_id', type=int)
        if not agency_id_from_form:
            flash('Please select an agency for stock adjustment.', 'error')
            return render_template('inventory/adjust_stock.html', product=product)
        product_agency = ProductAgency.query.filter_by(product_id=product_id, agency_id=agency_id_from_form).first_or_404()
    else:
        from models import ProductAgency
        product_agency = ProductAgency.query.filter_by(product_id=product_id, agency_id=current_agency_id).first_or_404()
        product = product_agency.product # Get the actual product object

    # Calculate current stock for the product
    current_stock_result = db.session.query(func.sum(InventoryTransaction.quantity_change)).filter(
        InventoryTransaction.product_id == product_id
    ).scalar()
    current_stock = current_stock_result or 0


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
                return render_template('inventory/adjust_stock.html', product=product, product_agency=product_agency)
            
            quantity_change = 0

            if adjustment_type == 'increase':
                quantity_change = quantity
            elif adjustment_type == 'decrease':
                if current_stock < quantity:
                    flash('Cannot decrease stock below zero.', 'error')
                    return render_template('inventory/adjust_stock.html', product=product, product_agency=product_agency, current_stock=current_stock)
                quantity_change = -quantity
            else:
                flash('Invalid adjustment type.', 'error')
                return render_template('inventory/adjust_stock.html', product=product, product_agency=product_agency, current_stock=current_stock)

            # Create inventory transaction
            quantity_before = current_stock
            quantity_after = current_stock + quantity_change

            transaction = InventoryTransaction(
                product_id=product.id,
                transaction_type='adjustment',
                quantity_change=quantity_change,
                quantity_before=quantity_before,
                quantity_after=quantity_after,
                unit_cost=product_agency.buy_price, # Use agency-specific buy price
                reference_type='manual_adjustment',
                notes=f'{reason}: {notes}' if notes else reason,
                created_by=user_id
            )

            db.session.add(transaction)
            db.session.commit()

            flash(f'Stock adjusted successfully. New quantity: {quantity_after}', 'success')
            return redirect(url_for('inventory.stock_levels'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error adjusting stock: {str(e)}', 'error')

    # For GET request, fetch product_agency to display current stock
    if user_role == 'super_admin':
        # Super admin needs to select an agency to view/adjust stock
        agencies = Agency.query.filter_by(is_active=True).all()
        selected_agency_id = request.args.get('agency_id', type=int)
        if selected_agency_id:
            product_agency = ProductAgency.query.filter_by(product_id=product_id, agency_id=selected_agency_id).first()
        else:
            product_agency = None # No agency selected yet
        return render_template('inventory/adjust_stock.html', product=product, product_agency=product_agency, agencies=agencies, current_stock=current_stock)
    else:
        product_agency = ProductAgency.query.filter_by(product_id=product_id, agency_id=current_agency_id).first_or_404()
        return render_template('inventory/adjust_stock.html', product=product, product_agency=product_agency, current_stock=current_stock)

@inventory_bp.route('/transactions')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
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
        query = InventoryTransaction.query.options(
            db.joinedload(InventoryTransaction.product),
            db.joinedload(InventoryTransaction.user)
        )
    else:
        from models import ProductAgency
        query = InventoryTransaction.query.join(Product).join(ProductAgency).options(
            db.joinedload(InventoryTransaction.product),
            db.joinedload(InventoryTransaction.user)
        ).filter(
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
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def list_suppliers(current_agency_id=None):
    """List suppliers for inventory management"""
    user_role = session.get('role')
    search = request.args.get('search', '').strip()

    if user_role == 'super_admin':
        query = Supplier.query
    else:
        query = Supplier.query.filter_by(agency_id=current_agency_id)

    if search:
        query = query.filter(
            db.or_(
                Supplier.name.ilike(f'%{search}%'),
                Supplier.contact_person.ilike(f'%{search}%'),
                Supplier.email.ilike(f'%{search}%')
            )
        )

    suppliers = query.order_by(Supplier.name).paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20,
        error_out=False
    )
    return render_template('inventory/suppliers.html', suppliers=suppliers)

@inventory_bp.route('/add_supplier', methods=['GET', 'POST'])
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
@log_activity('supplier_added')
def add_supplier(current_agency_id=None):
    """Add new supplier"""
    user_role = session.get('role')
    agencies = []
    form_data = request.form if request.method == 'POST' else {}

    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).order_by(Agency.name).all()

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

            agency_id, agency_error = _get_agency_context(user_role, current_agency_id, request.form)
            if agency_error:
                flash(agency_error, 'error')
                return render_template(
                    'inventory/add_supplier.html',
                    agencies=agencies,
                    form_data=form_data
                )

            # Validation
            if not name:
                flash('Supplier name is required', 'error')
                return render_template(
                    'inventory/add_supplier.html',
                    agencies=agencies,
                    form_data=form_data
                )

            # Check for duplicate name within agency
            existing = Supplier.query.filter_by(
                name=name,
                agency_id=agency_id
            ).first()

            if existing:
                flash('Supplier with this name already exists for the selected agency.', 'error')
                return render_template(
                    'inventory/add_supplier.html',
                    agencies=agencies,
                    form_data=form_data
                )

            # Create supplier
            supplier = Supplier(
                name=name,
                contact_person=contact_person,
                email=email,
                phone=phone,
                address=address,
                notes=notes,
                agency_id=agency_id,
                is_active=is_active
            )

            db.session.add(supplier)
            db.session.commit()

            flash('Supplier added successfully', 'success')
            return redirect(url_for('inventory.list_suppliers'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error adding supplier: {str(e)}', 'error')

    return render_template('inventory/add_supplier.html', agencies=agencies, form_data=form_data)


@inventory_bp.route('/edit_supplier/<int:supplier_id>', methods=['GET', 'POST'])
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
@log_activity('supplier_updated')
def edit_supplier(supplier_id, current_agency_id=None):
    """Edit existing supplier."""
    user_role = session.get('role')

    # Fetch supplier with access control
    if user_role == 'super_admin':
        supplier = Supplier.query.get_or_404(supplier_id)
    else:
        supplier = Supplier.query.filter_by(id=supplier_id, agency_id=current_agency_id).first_or_404()

    agencies = []
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).order_by(Agency.name).all()

    if request.method == 'POST':
        form_data = request.form
        try:
            name = request.form.get('name', '').strip()
            contact_person = request.form.get('contact_person', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            address = request.form.get('address', '').strip()
            notes = request.form.get('notes', '').strip()
            is_active = request.form.get('is_active') == 'on'

            agency_id, agency_error = _get_agency_context(user_role, supplier.agency_id, request.form)
            if agency_error:
                flash(agency_error, 'error')
                return render_template(
                    'inventory/add_supplier.html',
                    agencies=agencies, supplier=supplier,
                    form_data=form_data,
                    page_title='Edit Supplier',
                    submit_label='Update Supplier',
                    back_url=url_for('inventory.list_suppliers')
                )

            if not name:
                flash('Supplier name is required', 'error')
                return render_template(
                    'inventory/add_supplier.html',
                    agencies=agencies, supplier=supplier,
                    form_data=form_data,
                    page_title='Edit Supplier',
                    submit_label='Update Supplier',
                    back_url=url_for('inventory.list_suppliers')
                )

            # Check for duplicates within agency, excluding current supplier
            existing = Supplier.query.filter(
                Supplier.name == name,
                Supplier.agency_id == agency_id,
                Supplier.id != supplier.id
            ).first()

            if existing:
                flash('Supplier with this name already exists for the selected agency.', 'error')
                return render_template(
                    'inventory/add_supplier.html',
                    agencies=agencies, supplier=supplier,
                    form_data=form_data,
                    page_title='Edit Supplier',
                    submit_label='Update Supplier',
                    back_url=url_for('inventory.list_suppliers')
                )

            # Update supplier
            supplier.name = name
            supplier.contact_person = contact_person
            supplier.email = email
            supplier.phone = phone
            supplier.address = address
            supplier.notes = notes
            supplier.agency_id = agency_id
            supplier.is_active = is_active

            db.session.commit()

            flash('Supplier updated successfully', 'success')
            return redirect(url_for('inventory.list_suppliers'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating supplier: {str(e)}', 'error')

    form_data = _build_supplier_form_data(supplier)
    return render_template(
        'inventory/add_supplier.html',
        agencies=agencies, supplier=supplier,
        form_data=form_data,
        page_title='Edit Supplier',
        submit_label='Update Supplier',
        back_url=url_for('inventory.list_suppliers')
    )


@inventory_bp.route('/toggle_supplier_status/<int:supplier_id>', methods=['POST'])
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
@log_activity('supplier_status_toggled')
def toggle_supplier_status(supplier_id, current_agency_id=None):
    """Toggle supplier active/inactive status."""
    user_role = session.get('role')

    if user_role == 'super_admin':
        supplier = Supplier.query.get_or_404(supplier_id)
    else:
        supplier = Supplier.query.filter_by(id=supplier_id, agency_id=current_agency_id).first_or_404()

    supplier.is_active = not supplier.is_active
    db.session.commit()

    status_label = 'activated' if supplier.is_active else 'deactivated'
    flash(f'Supplier {status_label} successfully', 'success')
    return redirect(url_for('inventory.list_suppliers'))


@inventory_bp.route('/reports')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
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