from flask import render_template, request, redirect, url_for, flash, session, send_file, jsonify
from datetime import datetime
import uuid
from sqlalchemy import or_, and_, func, union_all
from app import db
from models import Order, OrderItem, Customer, Product, Location, User, Agency, IndianTaxCode, ProductAgency, InventoryTransaction, Job
from order import order_bp
from auth.utils import login_required, permission_required, order_owner_required
from utils.decorators import log_activity
from utils.excel_utils import export_orders_to_excel

from models import PurchaseOrder, Supplier
@order_bp.route('/api/tax-codes')
@login_required
def get_tax_codes():
    """API endpoint to get Indian tax codes for the order form"""
    tax_codes = IndianTaxCode.query.filter_by(is_active=True).all()
    return jsonify({
        code.code: {
            'name': code.name,
            'rate': float(code.rate),
            'description': code.description
        }
        for code in tax_codes
    })

@order_bp.route('/')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff', 'salesperson'])
def list_orders(current_agency_id=None):
    user_role = session.get('role')
    user_id = session.get('user_id')    

    # Get filters from request
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    agency_filter = request.args.get('agency')
    location_filter = request.args.get('location')
    customer_filter = request.args.get('customer')
    supplier_filter = request.args.get('supplier') # For POs
    salesperson_filter = request.args.get('salesperson')
    status_filter = request.args.get('status')
    
    # --- Sales Orders (SO) Query ---
    so_query = Order.query
    if user_role == 'salesperson':
        so_query = so_query.filter(Order.salesperson_id == user_id)
    elif user_role != 'super_admin':
        so_query = so_query.filter(Order.agency_id == current_agency_id)

    if date_from:
        try:
            from datetime import datetime
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Order.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            from datetime import datetime
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            query = query.filter(Order.created_at <= date_to_obj)
        except ValueError:
            pass
    
    if agency_filter and user_role == 'super_admin':
        so_query = so_query.filter(Order.agency_id == agency_filter)
    
    if location_filter:
        so_query = so_query.join(Customer).filter(Customer.location_id == location_filter)
    
    if customer_filter:
        so_query = so_query.filter(Order.customer_id == customer_filter)
    
    if salesperson_filter:
        so_query = so_query.filter(Order.salesperson_id == salesperson_filter)
    
    if status_filter:
        so_query = so_query.filter(Order.status == status_filter)
    
    sales_orders = so_query.all()

    # --- Purchase Orders (PO) Query ---
    po_query = PurchaseOrder.query
    if user_role != 'super_admin':
        po_query = po_query.filter(PurchaseOrder.agency_id == current_agency_id)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            po_query = po_query.filter(PurchaseOrder.created_at >= date_from_obj)
        except ValueError: pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            po_query = po_query.filter(PurchaseOrder.created_at <= date_to_obj)
        except ValueError: pass

    if agency_filter and user_role == 'super_admin':
        po_query = po_query.filter(PurchaseOrder.agency_id == agency_filter)

    if supplier_filter:
        po_query = po_query.filter(PurchaseOrder.supplier_id == supplier_filter)

    if status_filter:
        po_query = po_query.filter(PurchaseOrder.status == status_filter)

    purchase_orders = po_query.all()

    # --- Combine and Sort ---
    # Add a 'type' attribute to each object before combining
    for so in sales_orders: so.type = 'SO'
    for po in purchase_orders: po.type = 'PO'
    
    combined_list = sorted(sales_orders + purchase_orders, key=lambda x: x.created_at, reverse=True)

    # Get filter options
    agencies = []
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
    
    locations = []
    customers = []
    salespersons = []
    suppliers = []
    
    if user_role == 'super_admin':
        locations = Location.query.filter_by(is_active=True).all()
        customers = Customer.query.filter_by(is_active=True).all()
        salespersons = User.query.filter(User.role.in_(['salesperson', 'staff', 'agency_admin'])).all()
        suppliers = Supplier.query.filter_by(is_active=True).all()
    else:
        locations = Location.query.filter_by(agency_id=current_agency_id, is_active=True).all()
        customers = Customer.query.join(Location).filter(Location.agency_id == current_agency_id, Customer.is_active == True).all()
        salespersons = User.query.filter_by(agency_id=current_agency_id).filter(User.role.in_(['salesperson', 'staff', 'agency_admin'])).all()
        suppliers = Supplier.query.filter_by(agency_id=current_agency_id, is_active=True).all()
    
    return render_template('order/list.html', 
                         orders=combined_list,
                         agencies=agencies,
                         locations=locations,
                         customers=customers,
                         suppliers=suppliers,
                         salespersons=salespersons,
                         filters={
                             'date_from': date_from,
                             'date_to': date_to,
                             'agency': agency_filter,
                             'location': location_filter,
                             'customer': customer_filter,
                             'supplier': supplier_filter,
                             'salesperson': salesperson_filter,
                             'status': status_filter
                         })

@order_bp.route('/cart')
@login_required
def view_cart():
    """Renders the e-commerce style cart page."""
    # This is a static example page for now.
    return render_template('ecommerce/cart.html')

@order_bp.route('/create', methods=['GET', 'POST'])
@login_required
@log_activity('create_order')
def create_order():
    """
    Handles the creation of a new order.
    GET: Renders the new dynamic order form.
    POST: Accepts a JSON payload to create the order.
    """
    if request.method == 'POST':
        data = request.get_json()
        user_role = session.get('role')
        current_agency_id = session.get('agency_id')
        user_id = session.get('user_id')

        try:
            customer_id = data.get('customer_id')
            items = data.get('items', [])
            tax_amount = float(data.get('tax', 0))
            discount_amount = float(data.get('discount', 0))

            if not customer_id or not items:
                return jsonify({'error': 'Customer and at least one item are required.'}), 400

            customer = Customer.query.get(customer_id)
            if not customer:
                return jsonify({'error': 'Invalid customer selected.'}), 404

            if user_role != 'super_admin' and customer.location.agency_id != current_agency_id:
                return jsonify({'error': 'Customer does not belong to your agency.'}), 403

            order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            
            order = Order(
                order_number=order_number,
                customer_id=customer.id,
                agency_id=customer.location.agency_id,
                salesperson_id=user_id,
                status='pending',
                payment_status='pending',
                notes=data.get('notes'),
                order_date=datetime.utcnow(),
                tax=tax_amount,
                discount=discount_amount
            )
            if data.get('delivery_date'):
                order.delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d')

            db.session.add(order)
            db.session.flush()

            subtotal = 0

            for item_data in items:
                product = Product.query.get(item_data['id'])
                if not product:
                    db.session.rollback()
                    return jsonify({'error': f"Product with ID {item_data['id']} not found."}), 400

                # Auto-create/activate ProductAgency mapping if needed
                if user_role != 'super_admin':
                    pa_mapping = ProductAgency.query.filter_by(product_id=product.id, agency_id=customer.location.agency_id).first()
                    if not pa_mapping:
                        pa_mapping = ProductAgency(product_id=product.id, agency_id=customer.location.agency_id, is_active=True)
                        db.session.add(pa_mapping)
                    elif not pa_mapping.is_active:
                        pa_mapping.is_active = True

                quantity = float(item_data['quantity'])
                unit_price = float(item_data['price'])
                discount_pct = float(item_data.get('discount', 0))

                discounted_price = unit_price * (1 - (discount_pct / 100))
                line_total = discounted_price * quantity

                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    uom=product.uom_ref.short_name if product.uom_ref else 'pcs',
                    unit_price=unit_price,
                    mrp_price=product.mrp_price or unit_price,
                    discount_percentage=discount_pct,
                    discounted_price=discounted_price,
                    tax_code='N/A', # Tax is now at order level
                    tax_rate=0,
                    tax_amount=0,
                    line_total=line_total,
                    total_price=line_total  # Backward compatibility
                )
                db.session.add(order_item)
                
                subtotal += line_total

            order.subtotal_amount = subtotal
            order.total_tax_amount = tax_amount # From payload
            order.total_amount = subtotal + tax_amount - discount_amount
            order.total_items_count = len(items)
            
            # Legacy fields (optional, can be removed if not needed elsewhere)
            # order.discount = 0 # This was already a global discount
            # order.tax = tax_amount # This is already set

            db.session.commit()
            
            # Auto-create Job for this Order
            try:
                # Generate job number
                last_job = Job.query.order_by(Job.id.desc()).first()
                job_number = f"JOB{(last_job.id + 1):05d}" if last_job else "JOB00001"
                
                # Create job linked to this order
                job = Job(
                    job_number=job_number,
                    name=f"Order {order_number} - {customer.name}",
                    description=f"Auto-generated job for order {order_number}. Customer: {customer.name}",
                    job_type='service',
                    agency_id=order.agency_id,
                    customer_id=order.customer_id,
                    order_id=order.id,  # Link job to order
                    assigned_to=order.salesperson_id,
                    status='draft',
                    budget_amount=order.total_amount,
                    estimated_cost=0,
                    start_date=order.order_date,
                    end_date=order.delivery_date,
                    created_by=user_id
                )
                db.session.add(job)
                db.session.commit()
                
                flash(f'Order created successfully! Job {job_number} has been automatically created.', 'success')
            except Exception as job_error:
                # If job creation fails, log it but don't fail the order creation
                db.session.rollback()
                flash(f'Order created successfully, but job creation failed: {str(job_error)}', 'warning')
            
            return jsonify({'success': True, 'order_id': order.id, 'redirect_url': url_for('order.view_order', order_id=order.id)})

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
    
    # Add today's date for the template
    from datetime import date, timedelta
    today = date.today()
    default_delivery_date = today + timedelta(days=10)
    user_role = session.get('role')

    # Fetch initial customers for the dropdown
    initial_customers_query = get_customers_for_user_query()
    initial_customers = initial_customers_query.order_by(Customer.name.asc()).limit(25).all()
    
    customer_options = [{
        'id': c.id,
        'name': c.name,
        'phone': c.phone,
        'email': c.email,
        'address': c.address,
        'location_name': c.location.name if c.location else None,
        'credit_period': c.credit_period,
        'display_text': f"{c.name} — {c.phone or ''} — {c.city or ''}".strip(' —')
    } for c in initial_customers]

    # Fetch initial products for the dropdown
    agency_id = session.get('agency_id')
    if user_role != 'super_admin' and agency_id:
        # Non-super-admins: show products actively mapped to their agency
        initial_products_query = db.session.query(Product).join(
            ProductAgency,
            and_(ProductAgency.product_id == Product.id,
                 ProductAgency.agency_id == agency_id,
                 ProductAgency.is_active == True)
        )
    else:
        # Super admin: see all master products, with potential price overrides for context agency
        initial_products_query = db.session.query(Product).outerjoin(
            ProductAgency,
            and_(ProductAgency.product_id == Product.id, ProductAgency.agency_id == agency_id))
    
    initial_products_query = initial_products_query.add_entity(ProductAgency)
    initial_products_query = initial_products_query.filter(Product.is_active == True)
    initial_products_rows = initial_products_query.order_by(Product.name.asc()).limit(25).all()

    product_options = []
    for prod, pa in initial_products_rows:
        sell_price = float(pa.sell_price) if pa and pa.sell_price is not None else (float(prod.sell_price) if prod.sell_price is not None else 0)
        buy_price = float(pa.buy_price) if pa and pa.buy_price is not None else (float(prod.buy_price) if prod.buy_price is not None else 0)
        mrp_price = float(pa.mrp_price) if pa and pa.mrp_price is not None else (float(prod.mrp_price) if prod.mrp_price is not None else sell_price)
        uom = (pa.uom_ref.short_name if pa and pa.uom_ref else (prod.uom_ref.short_name if prod.uom_ref else 'pcs'))
        tax_code = (pa.tax_master_ref.tax_code if pa and pa.tax_master_ref else (prod.tax_master_ref.tax_code if prod.tax_master_ref else 'GST18'))
        tax_rate = float(pa.tax_master_ref.tax_rate) if pa and pa.tax_master_ref else (float(prod.tax_master_ref.tax_rate) if prod.tax_master_ref else 18.0)
        display_name = pa.display_name if pa and pa.display_name else prod.name
        display = f"{display_name} — {prod.sku} — ₹{sell_price:.2f}"
        product_options.append({
            'id': prod.id,
            'name': display_name,
            'sku': prod.sku,
            'price': sell_price,
            'buy_price': buy_price,
            'mrp_price': mrp_price,
            'uom': uom,
            'tax_code': tax_code,
            'tax_rate': tax_rate,
            'display_text': display
        })

    return render_template('order/form.html',
                         default_delivery_date=default_delivery_date,
                         initial_customers=customer_options,
                         initial_products=product_options)

@order_bp.route('/api/search-customers-v2')
@login_required
def search_customers_v2(current_agency_id=None):
    """Return customer suggestions for Tom Select
    Response: [ { id, name, phone, email, address, location_name, credit_period, display_text } ]
    """
    q = (request.args.get('q') or '').strip()
    if not q or len(q) < 2:
        return jsonify([])

    # Base query: active customers, restricted by agency for non-super admins
    query = Customer.query.join(Location, Customer.location_id == Location.id)

    user_role = session.get('role')
    if user_role != 'super_admin':
        # Restrict to current agency
        agency_id = current_agency_id or session.get('agency_id')
        query = query.filter(Location.agency_id == agency_id)

    # Case-insensitive search across fields
    like = f"%{q}%"
    query = query.filter(
        or_(
            Customer.name.ilike(like),
            Customer.phone.ilike(like),
            Customer.email.ilike(like),
            Customer.city.ilike(like)
        )
    ).filter(Customer.is_active == True)

    results = (
        query.order_by(Customer.name.asc()).limit(50).all()
    )

    items = []
    for c in results:
        display = f"{c.name} — {c.phone or ''} — {c.city or ''}"
        items.append({
            'id': c.id,
            'name': c.name,
            'phone': c.phone,
            'email': c.email,
            'address': c.address,
            'location_name': c.location.name if c.location else None,
            'credit_period': c.credit_period,
            'display_text': display.strip(' —')
        })
    return jsonify(items)

def get_customers_for_user_query():
    """Returns a query for customers based on current user role"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        return Customer.query.filter_by(is_active=True)
    else:
        agency_id = session.get('agency_id')
        return Customer.query.join(Location).filter(
            Location.agency_id == agency_id,
            Customer.is_active == True
        )
@order_bp.route('/api/search-products-v2')
@login_required
def search_products_v2(current_agency_id=None):
    """Return product suggestions for Tom Select with agency validation
    Response: [ { id, name, sku, price, mrp_price, uom, tax_code, tax_rate, display_text } ]
    """
    q = (request.args.get('q') or '').strip()
    if not q or len(q) < 2:
        return jsonify([])

    # Check if a global search is requested (e.g., from the product creation form)
    is_global_search = request.args.get('scope') == 'global'

    user_role = session.get('role')    
    # Prefer agency_id from request, fallback to session, then to what's passed in.
    agency_id = request.args.get('agency_id', type=int) or current_agency_id or session.get('agency_id')

    # Restrict by agency unless it's a super_admin or a global search
    # If an agency_id is provided, we must filter by it.
    if agency_id and (user_role != 'super_admin' or not is_global_search):
        # For non-super-admins, only show products actively mapped to their agency
        base = db.session.query(Product).join(
            ProductAgency,
            and_(ProductAgency.product_id == Product.id,
                 ProductAgency.agency_id == agency_id,
                 ProductAgency.is_active == True) # Explicitly filter for active mappings
        )
    else:
        # Super admin or global search: see all master products.
        # We still join ProductAgency to fetch override prices if an agency context exists.
        target_agency_id = None if is_global_search else agency_id
        base = db.session.query(Product).outerjoin(
            ProductAgency,
            and_(ProductAgency.product_id == Product.id, ProductAgency.agency_id == target_agency_id))
    base = base.add_entity(ProductAgency) # Add ProductAgency as an entity to the query for selection

    # Active products only
    base = base.filter(Product.is_active == True)

    # Search across name and SKU (case-insensitive)
    like = f"%{q}%"
    base = base.filter(or_(Product.name.ilike(like), Product.sku.ilike(like)))

    # If not super admin, ensure there is either an active mapping or allow fallback to global product
    # The requirement notes imply auto-create/reactivate mapping on use; here we just allow listing

    rows = base.order_by(Product.name.asc()).limit(50).all()

    items = []
    for prod, pa in rows:
        # Prefer agency override values when present, else fallback to product master
        sell_price = float(pa.sell_price) if pa and pa.sell_price is not None else (float(prod.sell_price) if prod.sell_price is not None else 0)
        buy_price = float(pa.buy_price) if pa and pa.buy_price is not None else (float(prod.buy_price) if prod.buy_price is not None else 0)
        mrp_price = float(pa.mrp_price) if pa and pa.mrp_price is not None else (float(prod.mrp_price) if prod.mrp_price is not None else sell_price)
        uom = (pa.uom_ref.short_name if pa and pa.uom_ref else (prod.uom_ref.short_name if prod.uom_ref else 'pcs'))
        tax_code = (pa.tax_master_ref.tax_code if pa and pa.tax_master_ref else (prod.tax_master_ref.tax_code if prod.tax_master_ref else 'GST18'))
        tax_rate = float(pa.tax_master_ref.tax_rate) if pa and pa.tax_master_ref else (float(prod.tax_master_ref.tax_rate) if prod.tax_master_ref else 18.0)
        display_name = pa.display_name if pa and pa.display_name else prod.name
        display = f"{display_name} — {prod.sku} — ₹{sell_price:.2f}"
        items.append({
            'id': prod.id,
            'name': display_name,
            'sku': prod.sku,
            'price': sell_price,
            'buy_price': buy_price,
            'mrp_price': mrp_price,
            'uom': uom,
            'tax_code': tax_code,
            'tax_rate': tax_rate,
            'display_text': display
        })

    return jsonify(items)

@order_bp.route('/<int:order_id>')
@login_required
def view_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    user_id = session.get('user_id')
    
    # Check permissions
    if user_role == 'salesperson' and order.salesperson_id != user_id:
        flash('You can only view your own orders', 'error')
        return redirect(url_for('order.list_orders'))
    elif user_role not in ['super_admin', 'salesperson'] and order.agency_id != current_agency_id:
        flash('You can only view orders from your agency', 'error')
        return redirect(url_for('order.list_orders'))
    
    return render_template('order/view.html', order=order)

@order_bp.route('/<int:order_id>/edit', methods=['GET', 'POST'])
@login_required
@log_activity('edit_order')
def edit_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    user_id = session.get('user_id')
    
    # Check permissions
    if user_role == 'salesperson' and order.salesperson_id != user_id:
        flash('You can only edit your own orders', 'error')
        return redirect(url_for('order.list_orders'))
    elif user_role not in ['super_admin', 'salesperson'] and order.agency_id != current_agency_id:
        flash('You can only edit orders from your agency', 'error')
        return redirect(url_for('order.list_orders'))
    
    # Can only edit pending orders
    if order.status != 'pending':
        flash('Only pending orders can be edited.', 'error')
        return redirect(url_for('order.view_order', order_id=order_id))
    
    if request.method == 'POST':
        data = request.get_json()
        try:
            # Update order fields
            order.notes = data.get('notes')
            order.tax = float(data.get('tax', 0))
            order.discount = float(data.get('discount', 0))
            if data.get('delivery_date'):
                order.delivery_date = datetime.strptime(data['delivery_date'], '%Y-%m-%d')
            
            # Delete existing items
            OrderItem.query.filter_by(order_id=order.id).delete()
            
            subtotal = 0
            items = data.get('items', [])
            
            for item_data in items:
                product = Product.query.get(item_data['id'])
                if not product:
                    db.session.rollback()
                    return jsonify({'error': f"Product with ID {item_data['id']} not found."}), 400

                quantity = float(item_data['quantity'])
                unit_price = float(item_data['price'])
                discount_pct = float(item_data.get('discount', 0))

                discounted_price = unit_price * (1 - (discount_pct / 100))
                line_total = discounted_price * quantity

                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    uom=product.uom_ref.short_name if product.uom_ref else 'pcs',
                    unit_price=unit_price,
                    mrp_price=product.mrp_price or unit_price,
                    discount_percentage=discount_pct,
                    discounted_price=discounted_price,
                    tax_code='N/A',
                    tax_rate=0,
                    tax_amount=0,
                    line_total=line_total,
                    total_price=line_total
                )
                db.session.add(order_item)
                subtotal += line_total

            order.subtotal_amount = subtotal
            order.total_tax_amount = order.tax
            order.total_amount = subtotal + order.tax - order.discount
            order.total_items_count = len(items)

            db.session.commit()
            flash('Order updated successfully!', 'success')
            return jsonify({'success': True, 'redirect_url': url_for('order.view_order', order_id=order.id)})

        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
    
    # For GET request, render the dynamic form with existing order data
    from datetime import date, timedelta
    default_delivery_date = order.delivery_date or (date.today() + timedelta(days=10))
    return render_template('order/edit.html', order=order, default_delivery_date=default_delivery_date)

@order_bp.route('/<int:order_id>/update_status', methods=['POST'])
@login_required
@log_activity('update_order_status')
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    user_id = session.get('user_id')
    
    # Check permissions
    if user_role == 'salesperson':
        # Salesperson can only update their own orders and limited status changes
        if order.salesperson_id != user_id:
            flash('You can only update your own orders', 'error')
            return redirect(url_for('order.list_orders'))
        if new_status not in ['pending', 'confirmed', 'cancelled']:
            flash('You cannot update to this status', 'error')
            return redirect(url_for('order.view_order', order_id=order_id))
    elif user_role not in ['super_admin'] and order.agency_id != current_agency_id:
        flash('You can only update orders from your agency', 'error')
        return redirect(url_for('order.list_orders'))
    
    if new_status not in ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']:
        flash('Invalid status', 'error')
        return redirect(url_for('order.view_order', order_id=order_id))

    try:
        # Check if stock needs to be deducted
        if new_status in ['shipped', 'delivered'] and order.status in ['pending', 'confirmed']:
            for item in order.order_items:
                # Calculate current stock before this transaction
                current_stock = db.session.query(func.sum(InventoryTransaction.quantity_change)).filter(
                    InventoryTransaction.product_id == item.product_id
                ).scalar() or 0

                # Create a negative inventory transaction for the sale
                transaction = InventoryTransaction(
                    product_id=item.product_id,
                    agency_id=order.agency_id, # Associate transaction with the order's agency
                    customer_id=order.customer_id, # Associate transaction with the customer
                    transaction_type='sale',
                    quantity_change=-item.quantity,
                    quantity_before=current_stock,
                    quantity_after=current_stock - item.quantity,
                    unit_cost=item.unit_price, # Or a calculated cost if available
                    reference_id=order.id,
                    reference_type='order',
                    notes=f"Sale for Order {order.order_number}",
                    created_by=user_id
                )
                db.session.add(transaction)

        # Check if a fulfilled order is being cancelled (restock items)
        elif new_status == 'cancelled' and order.status in ['shipped', 'delivered']:
            for item in order.order_items:
                current_stock = db.session.query(func.sum(InventoryTransaction.quantity_change)).filter(
                    InventoryTransaction.product_id == item.product_id
                ).scalar() or 0

                # Create a positive inventory transaction to restock
                transaction = InventoryTransaction(
                    product_id=item.product_id,
                    agency_id=order.agency_id, # Associate transaction with the order's agency
                    customer_id=order.customer_id, # Associate transaction with the customer
                    transaction_type='return',
                    quantity_change=item.quantity,
                    quantity_before=current_stock,
                    quantity_after=current_stock + item.quantity,
                    reference_id=order.id,
                    reference_type='order_cancellation',
                    notes=f"Restock from cancelled Order {order.order_number}",
                    created_by=user_id
                )
                db.session.add(transaction)

        # Update the order status and commit all changes
        order.status = new_status
        db.session.commit()
        flash(f'Order status updated to {new_status.capitalize()}', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while updating status: {str(e)}', 'danger')
    
    return redirect(url_for('order.view_order', order_id=order_id))

@order_bp.route('/<int:order_id>/delete', methods=['POST'])
@login_required
@log_activity('delete_order')
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    user_id = session.get('user_id')
    
    # Check permissions
    if user_role == 'salesperson' and order.salesperson_id != user_id:
        flash('You can only delete your own orders', 'error')
        return redirect(url_for('order.list_orders'))
    elif user_role not in ['super_admin', 'agency_admin'] and order.agency_id != current_agency_id:
        flash('You do not have permission to delete orders', 'error')
        return redirect(url_for('order.list_orders'))
    
    # Can only delete pending or cancelled orders
    if order.status not in ['pending', 'cancelled']:
        flash('Can only delete pending or cancelled orders', 'error')
        return redirect(url_for('order.view_order', order_id=order_id))
    
    db.session.delete(order)
    db.session.commit()
    
    flash('Order deleted successfully!', 'success')
    return redirect(url_for('order.list_orders'))

@order_bp.route('/export')
@login_required
@log_activity('export_orders')
def export_orders():
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    user_id = session.get('user_id')
    
    if user_role == 'super_admin':
        orders = Order.query.all()
    elif user_role == 'salesperson':
        orders = Order.query.filter_by(salesperson_id=user_id).all()
    else:
        orders = Order.query.filter_by(agency_id=current_agency_id).all()
    
    # Create Excel file
    output = export_orders_to_excel(orders)
    
    return send_file(
        output,
        as_attachment=True,
        download_name='orders_export.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@order_bp.route('/api/customers/<int:location_id>')
@login_required
def get_customers_by_location(location_id):
    """API endpoint to get customers by location"""
    location = Location.query.get_or_404(location_id)
    customers = Customer.query.filter_by(location_id=location_id, is_active=True).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'email': c.email,
        'phone': c.phone
    } for c in customers])

def get_customers_for_user():
    """Get customers based on current user role"""
    return get_customers_for_user_query().all()

def get_products_for_user():
    """Get products based on current user role"""
    user_role = session.get('role')
    
    # Products are global master; visibility comes from mapping at point of use.
    return Product.query.filter_by(is_active=True).all()

@order_bp.route('/api/search-customers', methods=['GET'])
@login_required
def search_customers():
    """Search customers with autocomplete support"""
    query = request.args.get('q', '').strip()
    user_role = session.get('role')
    agency_id = session.get('agency_id')
    
    # Build base query
    customers_query = Customer.query.filter(Customer.is_active == True)
    
    # Apply agency filter for non-super admins
    if user_role != 'super_admin':
        customers_query = customers_query.join(Location).filter(Location.agency_id == agency_id)
    
    # Apply search filter
    if query:
        customers_query = customers_query.filter(
            db.or_(
                Customer.name.ilike(f'%{query}%'),
                Customer.phone.ilike(f'%{query}%'),
                Customer.email.ilike(f'%{query}%'),
                Customer.city.ilike(f'%{query}%')
            )
        )
    
    customers = customers_query.limit(50).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'email': c.email or '',
        'phone': c.phone or '',
        'address': c.address or '',
        'city': c.city or '',
        'location_name': c.location.name if c.location else '',
        'credit_period': c.credit_period or 30,
        'gst_number': c.gst_number or '',
        'display_text': f"{c.name} - {c.location.name if c.location else ''} ({c.phone or 'No phone'})"
    } for c in customers])

@order_bp.route('/api/search-products', methods=['GET'])
@login_required
def search_products():
    """Search products with autocomplete support"""
    query = request.args.get('q', '').strip()
    user_role = session.get('role')
    agency_id = session.get('agency_id')
    
    # For non-super-admins: restrict strictly to current agency's mapped products
    if user_role != 'super_admin':
        products_query = db.session.query(Product, ProductAgency).join(
            ProductAgency,
            db.and_(
                ProductAgency.product_id == Product.id,
                ProductAgency.agency_id == agency_id,
                ProductAgency.is_active == True
            )
        ).filter(Product.is_active == True)
    else:
        # Super admin: allow global search; optional ?agency_id= to filter
        filter_agency = request.args.get('agency_id', type=int)
        if filter_agency:
            products_query = db.session.query(Product, ProductAgency).join(
                ProductAgency,
                db.and_(
                    ProductAgency.product_id == Product.id,
                    ProductAgency.agency_id == filter_agency,
                    ProductAgency.is_active == True
                )
            ).filter(Product.is_active == True)
        else:
            # Super admin without agency filter: keep Product master; if session has agency_id, only join active mapping
            products_query = db.session.query(Product, ProductAgency).outerjoin(
                ProductAgency,
                db.and_(
                    ProductAgency.product_id == Product.id,
                    ProductAgency.agency_id == agency_id,
                    ProductAgency.is_active == True
                )
            ).filter(Product.is_active == True)

    # Apply search filter: match on master name/SKU and agency display_name/description
    if query:
        products_query = products_query.filter(db.or_(
            Product.name.ilike(f'%{query}%'),
            Product.sku.ilike(f'%{query}%'),
            Product.description.ilike(f'%{query}%'),
            ProductAgency.display_name.ilike(f'%{query}%'),
            Product.category_ref.has(Category.name.ilike(f'%{query}%'))
        ))

    results = products_query.limit(50).all()

    def safe_float(val, default=0.0):
        try:
            return float(val) if val is not None else default
        except Exception:
            return default

    return jsonify([{
        'id': p.id,
        'name': (pa.display_name if pa and pa.display_name else p.name),
        'sku': p.sku,
        'description': p.description or '',
        'price': safe_float(pa.sell_price if pa and pa.sell_price is not None else p.sell_price, 0.0),
        'buy_price': safe_float(pa.buy_price if pa and getattr(pa, 'buy_price', None) is not None else p.buy_price, 0.0),
        'mrp_price': safe_float(pa.mrp_price if pa and getattr(pa, 'mrp_price', None) is not None else p.mrp_price, 0.0),
        'uom': ((pa.uom_ref.short_name.lower() if pa and pa.uom_ref and getattr(pa.uom_ref, 'short_name', None) else (p.uom_ref.short_name.lower() if p and p.uom_ref and getattr(p.uom_ref, 'short_name', None) else 'pcs'))),
        'uom_id': (int(pa.uom_id) if pa and getattr(pa, 'uom_id', None) is not None else (int(p.uom_id) if getattr(p, 'uom_id', None) is not None else None)),
        'uom_short': (pa.uom_ref.short_name if pa and pa.uom_ref and getattr(pa.uom_ref, 'short_name', None) else (p.uom_ref.short_name if p and p.uom_ref and getattr(p.uom_ref, 'short_name', None) else '')), 
        'tax_rate': (
            safe_float(pa.tax_master_ref.tax_rate) if pa and pa.tax_master_ref else (
                safe_float(p.tax_master_ref.tax_rate) if p and p.tax_master_ref else 18.0
            )
        ),
        'tax_code': (pa.tax_master_ref.tax_code if pa and pa.tax_master_ref else (p.tax_master_ref.tax_code if p and p.tax_master_ref else 'GST18')),
        'tax_master_id': (int(pa.tax_master_id) if pa and getattr(pa, 'tax_master_id', None) is not None else (int(p.tax_master_id) if getattr(p, 'tax_master_id', None) is not None else None)),
        'stock_available': True,  # Stock tracking disabled
        'category': (pa.category_ref.name if pa and pa.category_ref else (p.category_ref.name if p and p.category_ref else '')),
        'category_id': (int(pa.category_id) if pa and getattr(pa, 'category_id', None) is not None else (int(p.category_id) if getattr(p, 'category_id', None) is not None else None)),
        'category_short': (pa.category_ref.short_name if pa and pa.category_ref and getattr(pa.category_ref, 'short_name', None) else (p.category_ref.short_name if p and p.category_ref and getattr(p.category_ref, 'short_name', None) else '')),
        'display_text': (
            f"{(pa.display_name if pa and pa.display_name else p.name)} ({p.sku})"
            + (
                f" [{pa.category_ref.short_name}]" if pa and pa.category_ref and getattr(pa.category_ref, 'short_name', None)
                else (f" [{p.category_ref.short_name}]" if p and p.category_ref and getattr(p.category_ref, 'short_name', None) else "")
            )
            + (
                f" • {pa.uom_ref.short_name}" if pa and pa.uom_ref and getattr(pa.uom_ref, 'short_name', None)
                else (f" • {p.uom_ref.short_name}" if p and p.uom_ref and getattr(p.uom_ref, 'short_name', None) else "")
            )
            + f" - ₹{safe_float(pa.sell_price if pa and pa.sell_price is not None else p.sell_price, 0.0)}"
        )
    } for (p, pa) in results])
