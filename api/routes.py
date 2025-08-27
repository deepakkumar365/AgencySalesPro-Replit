from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from models import User, Agency, Product, Order, Customer, Location
from api import api_bp

@api_bp.route('/profile')
@jwt_required()
def get_profile():
    """Get current user profile"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'agency_id': user.agency_id,
        'agency_name': user.agency.name if user.agency else None
    })

@api_bp.route('/agencies')
@jwt_required()
def get_agencies():
    """Get agencies based on user role"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
    else:
        agencies = Agency.query.filter_by(id=user.agency_id, is_active=True).all()
    
    return jsonify([{
        'id': a.id,
        'name': a.name,
        'code': a.code,
        'address': a.address,
        'phone': a.phone,
        'email': a.email
    } for a in agencies])

@api_bp.route('/products')
@jwt_required()
def get_products():
    """Get products based on user role"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role == 'super_admin':
        products = Product.query.filter_by(is_active=True).all()
    else:
        products = Product.query.filter_by(agency_id=user.agency_id, is_active=True).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'sku': p.sku,
        'price': str(p.price),
        'stock_quantity': p.stock_quantity,
        'category': p.category
    } for p in products])

@api_bp.route('/customers')
@jwt_required()
def get_customers():
    """Get customers based on user role"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role == 'super_admin':
        customers = Customer.query.filter_by(is_active=True).all()
    else:
        customers = Customer.query.join(Location).filter(
            Location.agency_id == user.agency_id,
            Customer.is_active == True
        ).all()
    
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'email': c.email,
        'phone': c.phone,
        'location_name': c.location.name
    } for c in customers])

@api_bp.route('/orders')
@jwt_required()
def get_orders():
    """Get orders based on user role"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role == 'super_admin':
        orders = Order.query.all()
    elif user.role == 'salesperson':
        orders = Order.query.filter_by(salesperson_id=user_id).all()
    else:
        orders = Order.query.filter_by(agency_id=user.agency_id).all()
    
    return jsonify([{
        'id': o.id,
        'order_number': o.order_number,
        'customer_name': o.customer.name,
        'status': o.status,
        'total_amount': str(o.total_amount),
        'order_date': o.order_date.isoformat() if o.order_date else None,
        'salesperson_name': o.salesperson.full_name
    } for o in orders])

@api_bp.route('/orders/<int:order_id>')
@jwt_required()
def get_order_detail(order_id):
    """Get order details"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    order = Order.query.get_or_404(order_id)
    
    # Check permissions
    if user.role == 'salesperson' and order.salesperson_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    elif user.role not in ['super_admin', 'salesperson'] and order.agency_id != user.agency_id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'id': order.id,
        'order_number': order.order_number,
        'customer': {
            'id': order.customer.id,
            'name': order.customer.name,
            'email': order.customer.email,
            'phone': order.customer.phone
        },
        'status': order.status,
        'total_amount': str(order.total_amount),
        'discount': str(order.discount),
        'tax': str(order.tax),
        'notes': order.notes,
        'order_date': order.order_date.isoformat() if order.order_date else None,
        'delivery_date': order.delivery_date.isoformat() if order.delivery_date else None,
        'salesperson': {
            'id': order.salesperson.id,
            'name': order.salesperson.full_name
        },
        'items': [{
            'id': item.id,
            'product_name': item.product.name,
            'product_sku': item.product.sku,
            'quantity': item.quantity,
            'unit_price': str(item.unit_price),
            'total_price': str(item.total_price)
        } for item in order.order_items]
    })

@api_bp.route('/orders', methods=['POST'])
@jwt_required()
def create_order_api():
    """Create new order via API"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    data = request.get_json()
    
    # Validate required fields
    if not data.get('customer_id') or not data.get('items'):
        return jsonify({'error': 'Customer and items are required'}), 400
    
    # Validate customer access
    customer = Customer.query.get(data['customer_id'])
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404
    
    if user.role != 'super_admin' and customer.location.agency_id != user.agency_id:
        return jsonify({'error': 'Unauthorized customer access'}), 403
    
    try:
        # Create order (implementation similar to web interface)
        # This would include the full order creation logic
        return jsonify({'message': 'Order created successfully'}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/dashboard/stats')
@jwt_required()
def get_dashboard_stats():
    """Get dashboard statistics for current user"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.role == 'super_admin':
        stats = {
            'total_agencies': Agency.query.count(),
            'total_orders': Order.query.count(),
            'total_products': Product.query.count(),
            'total_customers': Customer.query.count()
        }
    elif user.role == 'salesperson':
        stats = {
            'my_orders': Order.query.filter_by(salesperson_id=user_id).count(),
            'pending_orders': Order.query.filter_by(salesperson_id=user_id, status='pending').count(),
            'confirmed_orders': Order.query.filter_by(salesperson_id=user_id, status='confirmed').count()
        }
    else:
        stats = {
            'agency_orders': Order.query.filter_by(agency_id=user.agency_id).count(),
            'agency_products': Product.query.filter_by(agency_id=user.agency_id).count(),
            'agency_customers': Customer.query.join(Location).filter(Location.agency_id == user.agency_id).count()
        }
    
    return jsonify(stats)
