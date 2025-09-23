from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
from decimal import Decimal
from app import db
from models import (
    Product, ProductAgency, Customer, Order, OrderItem, Location, Agency, Category,
    Invoice, Payment, PaymentMethod, TaxRule, InventoryTransaction
)
from pos import pos_bp
from auth.utils import login_required, permission_required, get_role_permissions
from utils.decorators import log_activity
import uuid

@pos_bp.route('/dashboard')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'pos_user'])
def dashboard(current_agency_id=None):
    """POS Dashboard with quick stats and recent transactions"""
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Get today's stats
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    # Base query for orders
    if user_role == 'super_admin':
        base_query = Order.query
    elif user_role == 'pos_user':
        base_query = Order.query.filter_by(salesperson_id=user_id)
    else:
        base_query = Order.query.filter_by(agency_id=current_agency_id)
    
    # Today's stats
    today_orders = base_query.filter(
        Order.created_at >= today_start,
        Order.created_at <= today_end
    ).all()
    
    today_stats = {
        'total_sales': sum(order.total_amount for order in today_orders),
        'total_orders': len(today_orders),
        'total_items': sum(len(order.order_items) for order in today_orders),
        'avg_order_value': sum(order.total_amount for order in today_orders) / len(today_orders) if today_orders else 0
    }
    
    # Recent orders (last 10)
    recent_orders = base_query.order_by(Order.created_at.desc()).limit(10).all()
    
    # Low stock alerts for agency (disabled since stock tracking removed)
    low_stock_products = []
    
    # Payment methods for agency
    if user_role == 'super_admin':
        payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
    else:
        payment_methods = PaymentMethod.query.filter_by(
            agency_id=current_agency_id, is_active=True
        ).all()
    
    return render_template('pos/dashboard.html',
                         today_stats=today_stats,
                         recent_orders=recent_orders,
                         low_stock_products=low_stock_products,
                         payment_methods=payment_methods)

@pos_bp.route('/sale')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'pos_user'])
def new_sale(current_agency_id=None):
    """Create new POS sale"""
    user_role = session.get('role')
    
    # Get products for the agency
    if user_role == 'super_admin':
        products = Product.query.filter_by(is_active=True).all()
        locations = Location.query.filter_by(is_active=True).all()
    else:
        products = db.session.query(Product).join(ProductAgency, ProductAgency.product_id == Product.id)\
            .filter(ProductAgency.agency_id == current_agency_id, Product.is_active == True).all()
        locations = Location.query.filter_by(agency_id=current_agency_id, is_active=True).all()
    
    # Get payment methods
    if user_role == 'super_admin':
        payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
    else:
        payment_methods = PaymentMethod.query.filter_by(
            agency_id=current_agency_id, is_active=True
        ).all()
    
    return render_template('pos/sale.html',
                         products=products,
                         locations=locations,
                         payment_methods=payment_methods)

@pos_bp.route('/api/search_products')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'pos_user'])
def search_products(current_agency_id=None):
    """Search products for POS with robust error handling"""
    query = (request.args.get('q') or '').strip()
    user_role = session.get('role')

    if not query:
        return jsonify([])

    # Resolve effective agency context
    filter_agency = request.args.get('agency_id', type=int)
    effective_agency_id = None
    if user_role != 'super_admin':
        effective_agency_id = current_agency_id
    else:
        effective_agency_id = filter_agency or current_agency_id

    # For non-super-admins, agency context must be present
    if user_role != 'super_admin' and not effective_agency_id:
        return jsonify({'error': 'Agency context missing'}), 400

    def safe_float(val, default=0.0):
        try:
            return float(val) if val is not None else default
        except Exception:
            return default

    try:
        # Build query similar to order search to respect agency mappings and overrides
        if user_role != 'super_admin':
            products_query = db.session.query(Product, ProductAgency).join(
                ProductAgency,
                db.and_(
                    ProductAgency.product_id == Product.id,
                    ProductAgency.agency_id == effective_agency_id,
                    ProductAgency.is_active == True
                )
            ).filter(Product.is_active == True)
        else:
            if effective_agency_id:
                products_query = db.session.query(Product, ProductAgency).join(
                    ProductAgency,
                    db.and_(
                        ProductAgency.product_id == Product.id,
                        ProductAgency.agency_id == effective_agency_id,
                        ProductAgency.is_active == True
                    )
                ).filter(Product.is_active == True)
            else:
                # Super admin without a specific agency: allow global search with optional active mapping
                products_query = db.session.query(Product, ProductAgency).outerjoin(
                    ProductAgency,
                    db.and_(
                        ProductAgency.product_id == Product.id,
                        ProductAgency.is_active == True
                    )
                ).filter(Product.is_active == True)

        # Apply search filter: match on master name/SKU/category and agency display_name
        products_query = products_query.filter(db.or_(
            Product.name.ilike(f'%{query}%'),
            Product.sku.ilike(f'%{query}%'),
            Product.description.ilike(f'%{query}%'),
            ProductAgency.display_name.ilike(f'%{query}%'),
            Product.category_ref.has(Category.name.ilike(f'%{query}%'))
        ))

        results = products_query.limit(50).all()

        # Build safe response, prioritizing agency overrides when present
        response = [{
            'id': p.id,
            'name': (pa.display_name if pa and pa.display_name else p.name),
            'sku': p.sku,
            'price': safe_float(pa.sell_price if pa and getattr(pa, 'sell_price', None) is not None else p.sell_price, 0.0),
            'stock_available': True,
            'category': (pa.category_ref.name if pa and getattr(pa, 'category_ref', None) else (p.category_ref.name if getattr(p, 'category_ref', None) else ''))
        } for (p, pa) in results]

        return jsonify(response)
    except Exception as e:
        return jsonify({'error': 'Failed to search products', 'details': str(e)}), 500

@pos_bp.route('/api/get_customer')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'pos_user'])
def get_customer(current_agency_id=None):
    """Get or create customer for POS sale"""
    phone = request.args.get('phone', '').strip()
    email = request.args.get('email', '').strip()
    user_role = session.get('role')
    
    if not phone and not email:
        return jsonify({'error': 'Phone or email required'}), 400
    
    # Search for existing customer
    if user_role == 'super_admin':
        if phone:
            customer = Customer.query.filter_by(phone=phone).first()
        else:
            customer = Customer.query.filter_by(email=email).first()
    else:
        if phone:
            customer = Customer.query.join(Location).filter(
                Customer.phone == phone,
                Location.agency_id == current_agency_id
            ).first()
        else:
            customer = Customer.query.join(Location).filter(
                Customer.email == email,
                Location.agency_id == current_agency_id
            ).first()
    
    if customer:
        return jsonify({
            'id': customer.id,
            'name': customer.name,
            'email': customer.email,
            'phone': customer.phone,
            'address': customer.address
        })
    
    return jsonify({'error': 'Customer not found'}), 404

@pos_bp.route('/api/create_sale', methods=['POST'])
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'pos_user'])
@log_activity('pos_sale_created')
def create_sale(current_agency_id=None):
    """Create POS sale"""
    data = request.get_json()
    user_id = session.get('user_id')
    user_role = session.get('role')
    
    try:
        # Validate required fields
        required_fields = ['customer_info', 'items', 'payment_method_id']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Get or create customer
        customer_info = data['customer_info']
        location_id = data.get('location_id')
        
        # If no location specified, get first location for agency
        if not location_id:
            if user_role == 'super_admin':
                location = Location.query.filter_by(is_active=True).first()
            else:
                location = Location.query.filter_by(agency_id=current_agency_id, is_active=True).first()
            
            if not location:
                return jsonify({'error': 'No active location found'}), 400
            location_id = location.id
        
        # Create walk-in customer if needed
        customer = Customer.query.filter_by(
            phone=customer_info.get('phone'),
            location_id=location_id
        ).first()
        
        if not customer:
            customer = Customer(
                name=customer_info.get('name', 'Walk-in Customer'),
                email=customer_info.get('email'),
                phone=customer_info.get('phone'),
                address=customer_info.get('address'),
                location_id=location_id,
                is_active=True
            )
            db.session.add(customer)
            db.session.flush()  # Get customer ID
        
        # Get agency_id from location
        location = Location.query.get(location_id)
        agency_id = location.agency_id
        
        # Create order
        order_number = f"POS-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
        
        order = Order(
            order_number=order_number,
            customer_id=customer.id,
            agency_id=agency_id,
            salesperson_id=user_id,
            status='completed',  # POS sales are immediately completed
            total_amount=0,  # Will be calculated
            discount=Decimal(str(data.get('discount', 0))),
            tax=Decimal(str(data.get('tax', 0))),
            notes=data.get('notes', ''),
            order_date=datetime.utcnow()
        )
        db.session.add(order)
        db.session.flush()  # Get order ID
        
        # Add order items and update inventory
        total_amount = Decimal('0')
        for item_data in data['items']:
            product = Product.query.get(item_data['product_id'])
            if not product:
                return jsonify({'error': f'Product {item_data["product_id"]} not found'}), 400
            
            quantity = int(item_data['quantity'])
            unit_price = Decimal(str(item_data['unit_price']))
            
            # Stock checking disabled (inventory management removed)
            # Product availability is assumed
            
            # Create order item
            # Align with the newer OrderItem model structure
            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price,
                mrp_price=unit_price, # Assuming unit_price is MRP for POS
                discount_percentage=0, # No line-item discount in POS UI
                discounted_price=unit_price,
                tax_code='GST0', # Default, as POS doesn't handle line-item tax
                tax_rate=0,
                tax_amount=0,
                line_total=quantity * unit_price,
                total_price=quantity * unit_price, # For backward compatibility if needed
            )
            db.session.add(order_item)
            
            total_amount += order_item.total_price
        
        # Update order total
        order.total_amount = total_amount + order.tax - order.discount
        
        # Create invoice
        invoice_number = f"INV-{order_number}"
        invoice = Invoice(
            invoice_number=invoice_number,
            order_id=order.id,
            agency_id=agency_id,
            customer_id=customer.id,
            subtotal=total_amount,
            tax_amount=order.tax,
            discount_amount=order.discount,
            total_amount=order.total_amount,
            status='paid',  # POS sales are immediately paid
            issue_date=datetime.utcnow(),
            payment_terms='Cash/Card'
        )
        db.session.add(invoice)
        db.session.flush()  # Get invoice ID
        
        # Create payment record
        payment_number = f"PAY-{order_number}"
        payment = Payment(
            payment_number=payment_number,
            invoice_id=invoice.id,
            payment_method_id=data['payment_method_id'],
            amount=order.total_amount,
            payment_date=datetime.utcnow(),
            transaction_id=data.get('transaction_id'),
            status='completed',
            notes=data.get('payment_notes', ''),
            processed_by=user_id
        )
        db.session.add(payment)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'order_id': order.id,
            'order_number': order_number,
            'invoice_id': invoice.id,
            'total_amount': float(order.total_amount)
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@pos_bp.route('/receipt/<int:order_id>')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'pos_user'])
def receipt(order_id, current_agency_id=None):
    """Display receipt for POS sale"""
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Get order with permission check
    if user_role == 'super_admin':
        order = Order.query.get_or_404(order_id)
    elif user_role == 'pos_user':
        order = Order.query.filter_by(id=order_id, salesperson_id=user_id).first_or_404()
    else:
        order = Order.query.filter_by(id=order_id, agency_id=current_agency_id).first_or_404()
    
    return render_template('pos/receipt.html', order=order)

@pos_bp.route('/sales_history')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'pos_user'])
def sales_history(current_agency_id=None):
    """View POS sales history"""
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Get date range from query params
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Base query
    if user_role == 'super_admin':
        query = Order.query
    elif user_role == 'pos_user':
        query = Order.query.filter_by(salesperson_id=user_id)
    else:
        query = Order.query.filter_by(agency_id=current_agency_id)
    
    # Filter by date range if provided
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Order.order_date >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Order.order_date <= end_dt)
        except ValueError:
            pass
    
    # Get orders
    orders = query.order_by(Order.order_date.desc()).paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20,
        error_out=False
    )
    
    return render_template('pos/sales_history.html', orders=orders)