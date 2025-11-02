from flask import render_template, request, redirect, url_for, flash, session, make_response, jsonify
from sqlalchemy import func
from datetime import datetime, timedelta
import csv, io
from extensions import db
from models import Agency, User, Order, Product, Customer, ActivityLog, Location, AppSetting, MenuItem, MenuRole, Role
from . import super_admin_bp
from auth.utils import login_required, role_required, get_role_permissions
from utils.decorators import log_activity
from service.menu_service import MenuService

@super_admin_bp.route('/dashboard')
@role_required('super_admin', 'agency_manager')
def dashboard():
    user_role = session.get('role')
    user_id = session.get('user_id')
    managed_agency_ids = []

    # Base queries
    agency_query = Agency.query
    user_query = User.query
    order_query = Order.query
    product_query = Product.query
    customer_query = Customer.query

    if user_role == 'agency_manager':
        # Get agencies managed by this manager
        managed_agencies = Agency.query.filter_by(agency_manager_id=user_id).all()
        managed_agency_ids = [agency.id for agency in managed_agencies]

        # Filter all queries by managed agency IDs
        agency_query = agency_query.filter(Agency.id.in_(managed_agency_ids))
        user_query = user_query.filter(User.agency_id.in_(managed_agency_ids))
        order_query = order_query.filter(Order.agency_id.in_(managed_agency_ids))
        # Products are global, but customers are tied to agencies via locations
        customer_query = customer_query.join(Location).filter(Location.agency_id.in_(managed_agency_ids))

    # Get statistics
    stats = {
        'total_agencies': agency_query.count(),
        'active_agencies': agency_query.filter(Agency.is_active == True).count(),
        'total_users': user_query.count(),
        'total_agency_managers': user_query.filter(User.role == 'agency_manager').count(),
        'active_users': user_query.filter(User.is_active == True).count(),
        'total_orders': order_query.count(),
        'pending_orders': order_query.filter(Order.status == 'pending').count(),
        'total_products': product_query.count(),  # Products are global
        'total_customers': customer_query.count(),
    }
    
    # Enhanced business metrics (Ticket #25)
    # Calculate total revenue
    total_revenue_result = order_query.with_entities(func.sum(Order.total_amount)).scalar()
    stats['total_revenue'] = float(total_revenue_result) if total_revenue_result else 0
    
    # Calculate revenue for current month
    current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_revenue_result = order_query.filter(Order.created_at >= current_month_start).with_entities(func.sum(Order.total_amount)).scalar()
    stats['monthly_revenue'] = float(monthly_revenue_result) if monthly_revenue_result else 0
    
    # Calculate average order value
    if stats['total_orders'] > 0:
        stats['avg_order_value'] = stats['total_revenue'] / stats['total_orders']
    else:
        stats['avg_order_value'] = 0

    # Recent activities removed as not required

    # Get order statistics by status
    order_stats = order_query.with_entities(
        Order.status,
        func.count(Order.id).label('count')
    ).group_by(Order.status).all()

    # Get monthly order trends (last 6 months)
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    monthly_orders = order_query.filter(Order.created_at >= six_months_ago).with_entities(
        func.date_trunc('month', Order.created_at).label('month'),
        func.count(Order.id).label('count')
    ).group_by(func.date_trunc('month', Order.created_at)).order_by(func.date_trunc('month', Order.created_at)).all()

    # Get top agencies by orders
    top_agencies_query = db.session.query(
        Agency.name,
        func.count(Order.id).label('order_count')
    ).join(Order, Order.agency_id == Agency.id)

    if user_role == 'agency_manager':
        top_agencies_query = top_agencies_query.filter(Agency.id.in_(managed_agency_ids))

    top_agencies = top_agencies_query.group_by(Agency.id).order_by(func.count(Order.id).desc()).limit(5).all()
    
    # Get top products by order count (Ticket #25)
    from models import OrderItem
    top_products_query = db.session.query(
        Product.name,
        Product.sku,
        func.count(OrderItem.id).label('order_count'),
        func.sum(OrderItem.quantity).label('total_quantity')
    ).join(OrderItem, OrderItem.product_id == Product.id).join(Order, Order.id == OrderItem.order_id)
    
    if user_role == 'agency_manager':
        top_products_query = top_products_query.filter(Order.agency_id.in_(managed_agency_ids))
    
    top_products = top_products_query.group_by(Product.id).order_by(func.count(OrderItem.id).desc()).limit(5).all()
    
    # Get recent orders (Ticket #25)
    recent_orders = order_query.order_by(Order.created_at.desc()).limit(10).all()

    return render_template('super_admin/dashboard.html',
                         stats=stats,
                         order_stats=order_stats,
                         monthly_orders=monthly_orders,
                         top_agencies=top_agencies,
                         top_products=top_products,
                         recent_orders=recent_orders)

@super_admin_bp.route('/users')
@role_required('super_admin', 'agency_manager')
def manage_users():
    user_role = session.get('role')
    user_id = session.get('user_id')
    agency_filter = request.args.get('agency_filter', type=int)

    agencies_for_filter = []
    if user_role == 'super_admin':
        agencies_for_filter = Agency.query.order_by(Agency.name).all()
        query = User.query
        if agency_filter:
            query = query.filter(User.agency_id == agency_filter)
        users = query.all()
    elif user_role == 'agency_manager':
        # Get agencies managed by this manager
        managed_agencies = Agency.query.filter_by(agency_manager_id=user_id).all()
        agencies_for_filter = managed_agencies
        managed_agency_ids = [agency.id for agency in managed_agencies]
        
        # Get users from those agencies
        query = User.query.filter(User.agency_id.in_(managed_agency_ids))
        
        # If a specific agency is filtered, ensure it's one they manage
        if agency_filter and agency_filter in managed_agency_ids:
            query = query.filter(User.agency_id == agency_filter)
        
        users = query.all()
    else:
        users = []
    return render_template('super_admin/users.html', users=users, agencies_for_filter=agencies_for_filter, current_agency_filter=agency_filter)

@super_admin_bp.route('/users/create')
@role_required('super_admin', 'agency_manager')
def create_user():
    """Redirects to the main user registration page."""
    return redirect(url_for('auth.register'))

@super_admin_bp.route('/users/create_agency_admin')
@role_required('super_admin', 'agency_manager')
def create_agency_admin():
    """Catches an incorrect endpoint and redirects to the main user registration page."""
    return redirect(url_for('auth.register'))

@super_admin_bp.route('/users/<int:user_id>/toggle_status', methods=['POST'])
@role_required('super_admin')
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    
    # Don't allow deactivating the last super admin
    if user.role == 'super_admin' and user.is_active:
        active_super_admins = User.query.filter_by(role='super_admin', is_active=True).count()
        if active_super_admins <= 1:
            flash('Cannot deactivate the last super admin', 'error')
            return redirect(url_for('super_admin.manage_users'))
    
    user.is_active = not user.is_active
    db.session.commit()
    
    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {status} successfully!', 'success')
    return redirect(url_for('super_admin.manage_users'))

@super_admin_bp.route('/activities')
@login_required
def view_activities():
    """
    Displays activity logs.
    - Super Admins see all logs.
    - Other users see only their own activity logs.
    """
    page = request.args.get('page', 1, type=int)
    query = ActivityLog.query.order_by(ActivityLog.created_at.desc())

    if session.get('role') != 'super_admin':
        query = query.filter_by(user_id=session.get('user_id'))

    activities = query.paginate(page=page, per_page=50, error_out=False)
    return render_template('super_admin/activities.html', activities=activities)

@super_admin_bp.route('/system_config', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_manager')
def system_config():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_menu':
            # Create new menu item
            name = request.form.get('name', '').strip()
            display_name = request.form.get('display_name', '').strip() or None
            url = request.form.get('url', '').strip() or None
            icon = request.form.get('icon', '').strip()
            parent_id = request.form.get('parent_id')
            order_index = int(request.form.get('order_index', 0))
            
            if not name:
                flash('Menu name is required.', 'error')
            else:
                menu = MenuItem(
                    name=name,
                    display_name=display_name,
                    url=url,
                    icon=icon,
                    parent_id=int(parent_id) if parent_id else None,
                    order_index=order_index,
                    is_active=True
                )
                db.session.add(menu)
                db.session.commit()
                MenuService.invalidate_cache()
                flash(f'Menu "{name}" created successfully!', 'success')
            
            return redirect(url_for('super_admin.system_config', tab='menu_management'))
        
        elif action == 'update_menu':
            # Update menu item
            menu_id = request.form.get('menu_id')
            menu = MenuItem.query.get(menu_id)
            
            if not menu:
                flash('Menu not found.', 'error')
            else:
                menu.name = request.form.get('name', '').strip()
                menu.display_name = request.form.get('display_name', '').strip() or None
                menu.url = request.form.get('url', '').strip() or None
                menu.icon = request.form.get('icon', '').strip()
                menu.order_index = int(request.form.get('order_index', 0))
                menu.is_active = request.form.get('is_active') == 'on'
                
                db.session.commit()
                MenuService.invalidate_cache()
                flash(f'Menu "{menu.name}" updated successfully!', 'success')
            
            return redirect(url_for('super_admin.system_config', tab='menu_management'))
        
        elif action == 'delete_menu':
            # Delete menu item
            menu_id = request.form.get('menu_id')
            menu = MenuItem.query.get(menu_id)
            
            if not menu:
                flash('Menu not found.', 'error')
            else:
                name = menu.name
                db.session.delete(menu)
                db.session.commit()
                MenuService.invalidate_cache()
                flash(f'Menu "{name}" deleted successfully!', 'success')
            
            return redirect(url_for('super_admin.system_config', tab='menu_management'))
        
        else:
            # Save system configuration to database
            AppSetting.set('system_name', request.form.get('system_name'))
            AppSetting.set('default_currency', request.form.get('default_currency'))
            AppSetting.set('timezone', request.form.get('timezone'))
            AppSetting.set('email_notifications', '1' if request.form.get('email_notifications') else '0')
            AppSetting.set('auto_backup', '1' if request.form.get('auto_backup') else '0')
            
            flash('System configuration updated successfully!', 'success')
            return redirect(url_for('super_admin.system_config', tab='config'))
    
    # Fetch settings from database with defaults
    settings = {
        'system_name': AppSetting.get('system_name', 'AgencySales Pro'),
        'default_currency': AppSetting.get('default_currency', 'USD'),
        'timezone': AppSetting.get('timezone', 'UTC'),
        'email_notifications': AppSetting.get('email_notifications', '1') == '1',
        'auto_backup': AppSetting.get('auto_backup', '1') == '1',
    }
    
    # Fetch menu items and roles
    all_menus = MenuService.get_all_menus()
    roles = Role.query.all()
    parent_menus = MenuItem.query.filter_by(parent_id=None, is_active=True).order_by(MenuItem.order_index).all()
    
    return render_template('super_admin/config.html', 
                         settings=settings,
                         all_menus=all_menus,
                         roles=roles,
                         parent_menus=parent_menus,
                         tab=request.args.get('tab', 'config'))

# ==================== Menu Management Routes ====================

@super_admin_bp.route('/manage_menus', methods=['GET', 'POST'])
@role_required('super_admin')
def manage_menus():
    """Manage menu items and role-menu mappings"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'create_menu':
            # Create new menu item
            name = request.form.get('name', '').strip()
            display_name = request.form.get('display_name', '').strip() or None
            url = request.form.get('url', '').strip() or None
            icon = request.form.get('icon', '').strip()
            parent_id = request.form.get('parent_id')
            order_index = int(request.form.get('order_index', 0))
            
            if not name:
                flash('Menu name is required.', 'error')
            else:
                menu = MenuItem(
                    name=name,
                    display_name=display_name,
                    url=url,
                    icon=icon,
                    parent_id=int(parent_id) if parent_id else None,
                    order_index=order_index,
                    is_active=True
                )
                db.session.add(menu)
                db.session.commit()
                MenuService.invalidate_cache()
                flash(f'Menu "{name}" created successfully!', 'success')
            
            return redirect(url_for('super_admin.manage_menus'))
        
        elif action == 'update_menu':
            # Update menu item
            menu_id = request.form.get('menu_id')
            menu = MenuItem.query.get(menu_id)
            
            if not menu:
                flash('Menu not found.', 'error')
            else:
                menu.name = request.form.get('name', '').strip()
                menu.display_name = request.form.get('display_name', '').strip() or None
                menu.url = request.form.get('url', '').strip() or None
                menu.icon = request.form.get('icon', '').strip()
                menu.order_index = int(request.form.get('order_index', 0))
                menu.is_active = request.form.get('is_active') == 'on'
                
                db.session.commit()
                MenuService.invalidate_cache()
                flash(f'Menu "{menu.name}" updated successfully!', 'success')
            
            return redirect(url_for('super_admin.manage_menus'))
        
        elif action == 'delete_menu':
            # Delete menu item
            menu_id = request.form.get('menu_id')
            menu = MenuItem.query.get(menu_id)
            
            if not menu:
                flash('Menu not found.', 'error')
            else:
                name = menu.name
                db.session.delete(menu)
                db.session.commit()
                MenuService.invalidate_cache()
                flash(f'Menu "{name}" deleted successfully!', 'success')
            
            return redirect(url_for('super_admin.manage_menus'))
    
    # GET: Display menu management interface
    all_menus = MenuService.get_all_menus()
    roles = Role.query.all()
    parent_menus = MenuItem.query.filter_by(parent_id=None, is_active=True).order_by(MenuItem.order_index).all()
    
    return render_template('super_admin/config.html', 
                         settings={},
                         all_menus=all_menus, 
                         roles=roles,
                         parent_menus=parent_menus,
                         tab='menu_management')

@super_admin_bp.route('/api/menu/<int:menu_id>', methods=['GET'])
@role_required('super_admin')
def api_menu_details(menu_id):
    """API endpoint to get menu details"""
    menu = MenuItem.query.get(menu_id)
    
    if not menu:
        return jsonify({'error': 'Menu not found'}), 404
    
    return jsonify({
        'menu': {
            'id': menu.id,
            'name': menu.name,
            'display_name': menu.display_name,
            'url': menu.url,
            'icon': menu.icon,
            'order_index': menu.order_index,
            'is_active': menu.is_active,
            'parent_id': menu.parent_id
        }
    })

@super_admin_bp.route('/api/menu/<int:menu_id>/roles', methods=['GET', 'POST', 'DELETE'])
@role_required('super_admin')
def api_menu_roles(menu_id):
    """API endpoint to manage menu-role relationships"""
    menu = MenuItem.query.get(menu_id)
    
    if not menu:
        return jsonify({'error': 'Menu not found'}), 404
    
    if request.method == 'GET':
        # Get roles assigned to this menu
        menu_roles = MenuRole.query.filter_by(menu_id=menu_id).all()
        return jsonify([{'role_id': mr.role_id, 'role_name': mr.role.name} for mr in menu_roles])
    
    elif request.method == 'POST':
        # Assign role to menu
        data = request.get_json()
        role_id = data.get('role_id')
        
        if not role_id:
            return jsonify({'error': 'role_id required'}), 400
        
        # Check if already exists
        existing = MenuRole.query.filter_by(menu_id=menu_id, role_id=role_id).first()
        if existing:
            return jsonify({'error': 'Role already assigned to this menu'}), 409
        
        menu_role = MenuRole(menu_id=menu_id, role_id=role_id)
        db.session.add(menu_role)
        db.session.commit()
        MenuService.invalidate_cache(role_id)
        
        return jsonify({'success': True, 'message': 'Role assigned to menu'})
    
    elif request.method == 'DELETE':
        # Remove role from menu
        data = request.get_json()
        role_id = data.get('role_id')
        
        if not role_id:
            return jsonify({'error': 'role_id required'}), 400
        
        menu_role = MenuRole.query.filter_by(menu_id=menu_id, role_id=role_id).first()
        if not menu_role:
            return jsonify({'error': 'Role not assigned to this menu'}), 404
        
        db.session.delete(menu_role)
        db.session.commit()
        MenuService.invalidate_cache(role_id)
        
        return jsonify({'success': True, 'message': 'Role removed from menu'})

@super_admin_bp.route('/api/role/<int:role_id>/menus', methods=['GET'])
@role_required('super_admin')
def api_role_menus(role_id):
    """API endpoint to get menus for a specific role"""
    role = Role.query.get(role_id)
    
    if not role:
        return jsonify({'error': 'Role not found'}), 404
    
    menus = MenuService.get_menus_by_role(role_id)
    return jsonify(menus)

@super_admin_bp.route('/reports')
@role_required('super_admin', 'agency_manager')
def reports():
    # Generate various reports
    
    # Agency performance report
    agency_performance = db.session.query(
        Agency.name,
        Agency.code,
        func.count(Order.id).label('total_orders'),
        func.sum(Order.total_amount).label('total_revenue'),
        func.count(Product.id).label('total_products'),
        func.count(Customer.id).label('total_customers')
    ).outerjoin(Order).outerjoin(Product).outerjoin(Location).outerjoin(Customer).group_by(Agency.id).all()
    
    # User activity report
    user_activity = db.session.query(
        User.username,
        User.role,
        Agency.name.label('agency_name'),
        func.count(ActivityLog.id).label('activity_count'),
        func.max(ActivityLog.created_at).label('last_activity')
    ).join(Agency, User.agency_id == Agency.id, isouter=True).outerjoin(ActivityLog).group_by(User.id).all()
    
    return render_template('super_admin/reports.html',
                         agency_performance=agency_performance,
                         user_activity=user_activity)

@super_admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_manager')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        role = request.form.get('role')
        username = request.form.get('username')

        # If the role is 'customer', the username must be the customer's phone number.
        if role == 'customer':
            customer_record = Customer.query.filter_by(email=user.email).first()
            if not customer_record or not customer_record.phone:
                flash('A customer record with a valid phone number must exist for this email before assigning the customer role.', 'error')
                return render_template('super_admin/edit_user.html', user=user, agencies=Agency.query.filter_by(is_active=True).all())
            user.username = customer_record.phone

        agency_id = request.form.get('agency_id')
        
        # Check if email is unique (excluding current user)
        existing = User.query.filter_by(email=user.email).first()
        if existing and existing.id != user.id:
            flash('Email already exists', 'error')
            agencies = Agency.query.filter_by(is_active=True).all()
            return render_template('super_admin/edit_user.html', user=user, agencies=agencies)
        
        # Prevent role change if user is an active agency manager
        if user.role == 'agency_manager' and user.role != role:
            managed_agency = Agency.query.filter_by(agency_manager_id=user.id).first()
            if managed_agency:
                flash(f"Cannot change role for user '{user.username}' because they are the manager of the '{managed_agency.name}' agency. Please reassign the manager first.", 'error')
                agencies = Agency.query.filter_by(is_active=True).all()
                return render_template('super_admin/edit_user.html', user=user, agencies=agencies)

        # Ensure agency-specific roles are assigned to an agency
        roles_requiring_agency = ['agency_admin', 'staff', 'salesperson', 'pos_user', 'agency_manager', 'customer']
        if role in roles_requiring_agency and not agency_id:
            flash(f"The role '{role.replace('_', ' ').title()}' requires an agency assignment. Please select an agency.", 'error')
            agencies = Agency.query.filter_by(is_active=True).all()
            # Pass back the attempted form data
            return render_template('super_admin/edit_user.html', user=user, agencies=agencies)

        # Set username only if it's not a customer role
        user.role = role
        user.agency_id = agency_id if agency_id else None
        
        # Handle subscription status for customers
        # NOTE: This requires a new `is_subscribed` boolean field on the User model.
        if user.role == 'customer':
            user.is_subscribed = 'is_subscribed' in request.form

        # Handle password change if provided
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash(f'User {user.username} updated successfully!', 'success')
        return redirect(url_for('super_admin.manage_users'))
    
    agencies = Agency.query.filter_by(is_active=True).all()
    return render_template('super_admin/edit_user.html', user=user, agencies=agencies)

@super_admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@role_required('super_admin', 'agency_manager')
@log_activity('delete_user')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)

    # Prevent deleting super admins
    if user.role == 'super_admin':
        flash('Super admin accounts cannot be deleted.', 'error')
        return redirect(url_for('super_admin.manage_users'))

    # Check if the user is an active agency manager
    managed_agency = Agency.query.filter_by(agency_manager_id=user.id).first()
    if managed_agency:
        flash(f"Cannot delete user '{user.username}' because they are the manager of the '{managed_agency.name}' agency. Please reassign the manager first.", 'error')
        return redirect(url_for('super_admin.manage_users'))

    # Add other checks here if needed (e.g., if user has orders)

    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.username} has been deleted successfully.', 'success')
    return redirect(url_for('super_admin.manage_users'))

@super_admin_bp.route('/users/<int:user_id>/reset_password', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_manager')
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('super_admin/reset_password.html', user=user)
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('super_admin/reset_password.html', user=user)
        
        user.set_password(new_password)
        db.session.commit()
        
        flash(f'Password reset successfully for {user.username}!', 'success')
        return redirect(url_for('super_admin.manage_users'))
    
    return render_template('super_admin/reset_password.html', user=user)

# User Import/Export Routes

@super_admin_bp.route('/users/download_template')
@role_required('super_admin', 'agency_manager')
def download_user_template():
    """Download CSV template for user import"""
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header row
    writer.writerow(['username', 'email', 'first_name', 'last_name', 'role', 'agency_code', 'password'])
    
    # Write sample data
    writer.writerow(['sample_user', 'user@example.com', 'John', 'Doe', 'staff', 'AGENCY001', 'password123']) # username can be phone for customer
    writer.writerow(['sample_admin', 'admin@example.com', 'Jane', 'Smith', 'agency_admin', 'AGENCY001', 'admin123'])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=user_template.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response

@super_admin_bp.route('/users/export')
@role_required('super_admin', 'agency_manager')
def export_users():
    """Export existing users to CSV"""
    users = User.query.join(Agency).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['username', 'email', 'first_name', 'last_name', 'role', 'agency_code', 'is_active', 'created_at', 'last_login'])
    
    # Write data
    for user in users:
        writer.writerow([
            user.username,
            user.email,
            user.first_name or '',
            user.last_name or '',
            user.role,
            user.agency.code if user.agency else '',
            'Yes' if user.is_active else 'No',
            user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else ''
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=users_export.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response

@super_admin_bp.route('/users/import', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_manager')
@log_activity('import_users')
def import_users():
    """Import users from CSV file"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('super_admin.import_users'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('super_admin.import_users'))
        
        if not file.filename.lower().endswith('.csv'):
            flash('Please upload a CSV file', 'error')
            return redirect(url_for('super_admin.import_users'))
        
        try:
            # Read CSV file
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_input = csv.DictReader(stream)
            
            success_count = 0
            error_count = 0
            errors = []
            
            # Get all defined roles dynamically
            valid_roles = list(get_role_permissions(None).keys())
            
            for row_num, row in enumerate(csv_input, start=2):  # Start from 2 to account for header
                try:
                    # Validate required fields
                    required_fields = ['username', 'email', 'role', 'agency_code', 'password']
                    missing_fields = [field for field in required_fields if not row.get(field, '').strip()]
                    
                    if missing_fields:
                        errors.append(f"Row {row_num}: Missing required fields: {', '.join(missing_fields)}")
                        error_count += 1
                        continue
                    
                    # Validate role
                    role = row['role'].strip()
                    if role not in valid_roles:
                        errors.append(f"Row {row_num}: Invalid role '{role}'. Must be one of: {', '.join(valid_roles)}")
                        error_count += 1
                        continue
                    
                    # Find agency by code
                    agency_code = row['agency_code'].strip()
                    agency = Agency.query.filter_by(code=agency_code, is_active=True).first()
                    if not agency:
                        errors.append(f"Row {row_num}: Agency with code '{agency_code}' not found or inactive")
                        error_count += 1
                        continue
                    
                    # Check for existing username
                    existing_user = User.query.filter_by(username=row['username'].strip()).first()
                    if existing_user:
                        errors.append(f"Row {row_num}: Username '{row['username'].strip()}' already exists")
                        error_count += 1
                        continue
                    
                    # Check for existing email
                    existing_email = User.query.filter_by(email=row['email'].strip()).first()
                    if existing_email:
                        errors.append(f"Row {row_num}: Email '{row['email'].strip()}' already exists")
                        error_count += 1
                        continue
                    
                    # Validate password length
                    password = row['password'].strip()
                    if len(password) < 6:
                        errors.append(f"Row {row_num}: Password must be at least 6 characters long")
                        error_count += 1
                        continue
                    
                    # Create new user
                    user = User(
                        username=row['username'].strip(),
                        email=row['email'].strip(),
                        first_name=row.get('first_name', '').strip(),
                        last_name=row.get('last_name', '').strip(),
                        role=role,
                        agency_id=agency.id,
                        is_active=True
                    )
                    user.set_password(password)
                    
                    db.session.add(user)
                    success_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
                    error_count += 1
            
            if success_count > 0:
                db.session.commit()
                flash(f'Successfully imported {success_count} users', 'success')
            
            if error_count > 0:
                flash(f'{error_count} errors occurred during import', 'warning')
                # Show first 5 errors
                for error in errors[:5]:
                    flash(error, 'error')
                if len(errors) > 5:
                    flash(f'... and {len(errors) - 5} more errors', 'error')
            
            return redirect(url_for('super_admin.manage_users'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error processing file: {str(e)}', 'error')
            return redirect(url_for('super_admin.import_users'))
    
    return render_template('super_admin/import_users.html')

@super_admin_bp.route('/export_data')
@role_required('super_admin', 'agency_manager')
def export_data():
    # Export comprehensive system data
    # This would be implemented with pandas/Excel export functionality
    flash('Data export functionality will be implemented', 'info')
    return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/agency/<int:agency_id>/reset_manager_password', methods=['POST'])
@role_required('super_admin')
@log_activity('reset_agency_manager_password')
def reset_agency_manager_password(agency_id):
    """
    Resets the password for an agency's manager to a default value.
    """
    agency = Agency.query.get_or_404(agency_id)
    
    if not agency.agency_manager_id:
        flash(f"Agency '{agency.name}' does not have a manager assigned.", "warning")
        return redirect(url_for('agency.list_agencies'))
        
    manager = User.query.get(agency.agency_manager_id)
    if not manager:
        flash(f"Manager for agency '{agency.name}' not found.", "danger")
        return redirect(url_for('agency.list_agencies'))

    try:
        manager.set_password('Welcome@123')
        db.session.commit()
        flash(f"Password for manager '{manager.username}' of agency '{agency.name}' has been reset to 'Welcome@123'.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"An error occurred while resetting the password: {str(e)}", "danger")

    return redirect(url_for('agency.list_agencies'))

@super_admin_bp.route('/user-manual')
@login_required
def user_manual():
    """Display Super Admin User Manual"""
    return render_template('super_admin/user_manual.html')
