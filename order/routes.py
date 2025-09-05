from flask import render_template, request, redirect, url_for, flash, session, send_file, jsonify
from datetime import datetime
import uuid
from app import db
from models import Order, OrderItem, Customer, Product, Location, User, Agency, IndianTaxCode
from order import order_bp
from auth.utils import login_required, agency_access_required
from utils.decorators import log_activity
from utils.excel_utils import export_orders_to_excel

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
@login_required
@agency_access_required
def list_orders(current_agency_id=None):
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Start with base query
    if user_role == 'super_admin':
        query = Order.query
    elif user_role == 'salesperson':
        query = Order.query.filter_by(salesperson_id=user_id)
    else:
        query = Order.query.filter_by(agency_id=current_agency_id)
    
    # Apply filters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    agency_filter = request.args.get('agency')
    location_filter = request.args.get('location')
    customer_filter = request.args.get('customer')
    salesperson_filter = request.args.get('salesperson')
    status_filter = request.args.get('status')
    
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
        query = query.filter(Order.agency_id == agency_filter)
    
    if location_filter:
        query = query.join(Customer).filter(Customer.location_id == location_filter)
    
    if customer_filter:
        query = query.filter(Order.customer_id == customer_filter)
    
    if salesperson_filter:
        query = query.filter(Order.salesperson_id == salesperson_filter)
    
    if status_filter:
        query = query.filter(Order.status == status_filter)
    
    orders = query.order_by(Order.created_at.desc()).all()
    
    # Get filter options
    agencies = []
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
    
    locations = []
    customers = []
    salespersons = []
    
    if user_role == 'super_admin':
        locations = Location.query.filter_by(is_active=True).all()
        customers = Customer.query.filter_by(is_active=True).all()
        salespersons = User.query.filter(User.role.in_(['salesperson', 'staff', 'agency_admin'])).all()
    else:
        locations = Location.query.filter_by(agency_id=current_agency_id, is_active=True).all()
        customers = Customer.query.join(Location).filter(Location.agency_id == current_agency_id, Customer.is_active == True).all()
        salespersons = User.query.filter_by(agency_id=current_agency_id).filter(User.role.in_(['salesperson', 'staff', 'agency_admin'])).all()
    
    return render_template('order/list.html', 
                         orders=orders,
                         agencies=agencies,
                         locations=locations,
                         customers=customers,
                         salespersons=salespersons,
                         filters={
                             'date_from': date_from,
                             'date_to': date_to,
                             'agency': agency_filter,
                             'location': location_filter,
                             'customer': customer_filter,
                             'salesperson': salesperson_filter,
                             'status': status_filter
                         })

@order_bp.route('/create', methods=['GET', 'POST'])
@login_required
@log_activity('create_order')
def create_order():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        products_data = request.form.getlist('products')
        quantities = request.form.getlist('quantities')
        uoms = request.form.getlist('uoms')
        mrp_prices = request.form.getlist('mrp_prices')
        unit_prices = request.form.getlist('unit_prices')
        discounts = request.form.getlist('discounts')
        tax_codes = request.form.getlist('tax_codes')
        line_totals = request.form.getlist('line_totals')
        # payment_status removed as per requirement
        notes = request.form.get('notes')
        delivery_date = request.form.get('delivery_date')
        
        user_role = session.get('role')
        current_agency_id = session.get('agency_id')
        user_id = session.get('user_id')
        
        if not customer_id:
            flash('Customer is required', 'error')
            return render_template('order/form.html', 
                                 customers=get_customers_for_user(),
                                 products=get_products_for_user())
        
        if not products_data or not quantities:
            flash('At least one product is required', 'error')
            return render_template('order/form.html',
                                 customers=get_customers_for_user(),
                                 products=get_products_for_user())
        
        # Validate customer belongs to user's agency
        customer = Customer.query.get(customer_id)
        if not customer:
            flash('Invalid customer selected', 'error')
            return render_template('order/form.html',
                                 customers=get_customers_for_user(),
                                 products=get_products_for_user())
        
        if user_role != 'super_admin' and customer.location.agency_id != current_agency_id:
            flash('You can only create orders for your agency customers', 'error')
            return render_template('order/form.html',
                                 customers=get_customers_for_user(),
                                 products=get_products_for_user())
        
        # Generate order number
        order_number = f"ORD-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        
        # Create order with enhanced fields
        order = Order()
        order.order_number = order_number
        order.customer_id = customer_id
        order.agency_id = customer.location.agency_id
        order.salesperson_id = user_id
        order.status = 'pending'
        order.payment_status = 'pending'  # Default to pending
        order.total_amount = 0
        order.subtotal_amount = 0
        order.total_tax_amount = 0
        order.total_items_count = 0
        order.discount = 0  # Legacy field
        order.tax = 0       # Legacy field
        order.notes = notes
        
        if delivery_date:
            order.delivery_date = datetime.strptime(delivery_date, '%Y-%m-%d')
        
        db.session.add(order)
        db.session.flush()  # Get order ID
        
        # Add enhanced order items
        subtotal = 0
        total_tax = 0
        valid_items = 0
        
        for i, product_id in enumerate(products_data):
            if (i < len(quantities) and quantities[i] and 
                i < len(unit_prices) and unit_prices[i]):
                
                quantity = int(quantities[i])
                unit_price = float(unit_prices[i])
                product = Product.query.get(product_id)
                
                if product and quantity > 0 and unit_price > 0:
                    # Validate product belongs to same agency
                    if user_role != 'super_admin' and product.agency_id != customer.location.agency_id:
                        continue
                    
                    # Get enhanced item data
                    uom = uoms[i] if i < len(uoms) else 'pcs'
                    mrp_price = float(mrp_prices[i]) if i < len(mrp_prices) and mrp_prices[i] else unit_price
                    discount_pct = float(discounts[i]) if i < len(discounts) and discounts[i] else 0
                    tax_code = tax_codes[i] if i < len(tax_codes) else 'GST18'
                    
                    # Calculate pricing
                    discount_amount = (unit_price * discount_pct / 100)
                    discounted_price = unit_price - discount_amount
                    
                    # Get tax rate
                    tax_rate = 18.0  # Default GST 18%
                    tax_code_obj = IndianTaxCode.query.filter_by(code=tax_code, is_active=True).first()
                    if tax_code_obj:
                        tax_rate = float(tax_code_obj.rate)
                    
                    # Calculate tax and line total
                    line_subtotal = discounted_price * quantity
                    tax_amount = (line_subtotal * tax_rate / 100)
                    line_total = line_subtotal + tax_amount
                    
                    order_item = OrderItem()
                    order_item.order_id = order.id
                    order_item.product_id = product_id
                    order_item.quantity = quantity
                    order_item.uom = uom
                    order_item.unit_price = unit_price
                    order_item.mrp_price = mrp_price
                    order_item.discount_percentage = discount_pct
                    order_item.discounted_price = discounted_price
                    order_item.tax_code = tax_code
                    order_item.tax_rate = tax_rate
                    order_item.tax_amount = tax_amount
                    order_item.line_total = line_total
                    order_item.total_price = line_total  # For backward compatibility
                    
                    subtotal += line_subtotal
                    total_tax += tax_amount
                    valid_items += 1
                    db.session.add(order_item)
        
        # Update order totals
        order.subtotal_amount = subtotal
        order.total_tax_amount = total_tax
        order.total_amount = subtotal + total_tax
        order.total_items_count = valid_items
        db.session.commit()
        
        flash('Order created successfully!', 'success')
        return redirect(url_for('order.list_orders'))
    
    # Add today's date for the template
    from datetime import date
    return render_template('order/form.html',
                         customers=get_customers_for_user(),
                         products=get_products_for_user(),
                         today=date.today())

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
    
    # Can't edit shipped or delivered orders
    if order.status in ['shipped', 'delivered']:
        flash('Cannot edit shipped or delivered orders', 'error')
        return redirect(url_for('order.view_order', order_id=order_id))
    
    if request.method == 'POST':
        order.discount = float(request.form.get('discount', 0))
        order.tax = float(request.form.get('tax', 0))
        order.notes = request.form.get('notes')
        delivery_date = request.form.get('delivery_date')
        
        if delivery_date:
            order.delivery_date = datetime.strptime(delivery_date, '%Y-%m-%d')
        
        db.session.commit()
        flash('Order updated successfully!', 'success')
        return redirect(url_for('order.view_order', order_id=order_id))
    
    return render_template('order/edit.html', order=order)

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
    
    if new_status in ['pending', 'confirmed', 'shipped', 'delivered', 'cancelled']:
        order.status = new_status
        db.session.commit()
        flash(f'Order status updated to {new_status}', 'success')
    else:
        flash('Invalid status', 'error')
    
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
    user_role = session.get('role')
    current_agency_id = session.get('agency_id')
    
    # Validate location access
    location = Location.query.get_or_404(location_id)
    if user_role != 'super_admin' and location.agency_id != current_agency_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    customers = Customer.query.filter_by(location_id=location_id, is_active=True).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'email': c.email,
        'phone': c.phone
    } for c in customers])

def get_customers_for_user():
    """Get customers based on current user role"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        return Customer.query.filter_by(is_active=True).all()
    else:
        agency_id = session.get('agency_id')
        return Customer.query.join(Location).filter(
            Location.agency_id == agency_id,
            Customer.is_active == True
        ).all()

def get_products_for_user():
    """Get products based on current user role"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        return Product.query.filter_by(is_active=True).all()
    else:
        agency_id = session.get('agency_id')
        return Product.query.filter_by(agency_id=agency_id, is_active=True).all()

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
    
    # Build base query
    products_query = Product.query.filter(Product.is_active == True)
    
    # Apply agency filter for non-super admins
    if user_role != 'super_admin':
        products_query = products_query.filter(Product.agency_id == agency_id)
    
    # Apply search filter
    if query:
        products_query = products_query.filter(
            db.or_(
                Product.name.ilike(f'%{query}%'),
                Product.sku.ilike(f'%{query}%')
            )
        )
    
    products = products_query.limit(50).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'sku': p.sku,
        'description': p.description or '',
        'price': float(p.price) if p.price else 0,
        'mrp_price': float(p.mrp_price) if p.mrp_price else 0,
        'uom': p.uom or 'pcs',
        'tax_rate': float(p.tax_rate) if p.tax_rate else 18.0,
        'tax_code': p.tax_code or 'GST18',
        'stock_available': True,  # Stock tracking disabled
        'category': p.category_ref.name if p.category_ref else '',
        'display_text': f"{p.name} ({p.sku}) - ₹{p.price}"
    } for p in products])
