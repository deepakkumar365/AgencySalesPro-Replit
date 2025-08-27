from flask import render_template, request, redirect, url_for, flash, session
from sqlalchemy import func
from datetime import datetime, timedelta
from app import db
from models import Agency, User, Order, Product, Customer, ActivityLog, Location
from super_admin import super_admin_bp
from auth.utils import login_required, role_required

@super_admin_bp.route('/dashboard')
@login_required
@role_required('super_admin')
def dashboard():
    # Get statistics
    stats = {
        'total_agencies': Agency.query.count(),
        'active_agencies': Agency.query.filter_by(is_active=True).count(),
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(is_active=True).count(),
        'total_orders': Order.query.count(),
        'pending_orders': Order.query.filter_by(status='pending').count(),
        'total_products': Product.query.count(),
        'total_customers': Customer.query.count()
    }
    
    # Get recent activities
    recent_activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(10).all()
    
    # Get order statistics by status
    order_stats = db.session.query(
        Order.status,
        func.count(Order.id).label('count')
    ).group_by(Order.status).all()
    
    # Get monthly order trends (last 6 months)
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    monthly_orders = db.session.query(
        func.date_trunc('month', Order.created_at).label('month'),
        func.count(Order.id).label('count')
    ).filter(Order.created_at >= six_months_ago).group_by(func.date_trunc('month', Order.created_at)).all()
    
    # Get top agencies by orders
    top_agencies = db.session.query(
        Agency.name,
        func.count(Order.id).label('order_count')
    ).join(Order).group_by(Agency.id).order_by(func.count(Order.id).desc()).limit(5).all()
    
    return render_template('super_admin/dashboard.html',
                         stats=stats,
                         recent_activities=recent_activities,
                         order_stats=order_stats,
                         monthly_orders=monthly_orders,
                         top_agencies=top_agencies)

@super_admin_bp.route('/users')
@login_required
@role_required('super_admin')
def manage_users():
    users = User.query.all()
    return render_template('super_admin/users.html', users=users)

@super_admin_bp.route('/users/<int:user_id>/toggle_status', methods=['POST'])
@login_required
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
@role_required('super_admin')
def view_activities():
    page = request.args.get('page', 1, type=int)
    activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    return render_template('super_admin/activities.html', activities=activities)

@super_admin_bp.route('/system_config', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def system_config():
    if request.method == 'POST':
        # Handle system configuration updates
        # This is a placeholder for system-wide settings
        flash('System configuration updated successfully!', 'success')
        return redirect(url_for('super_admin.system_config'))
    
    return render_template('super_admin/config.html')

@super_admin_bp.route('/reports')
@login_required
@role_required('super_admin')
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

@super_admin_bp.route('/create_agency_admin', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def create_agency_admin():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        agency_id = request.form.get('agency_id')
        
        # Validation
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return redirect(url_for('super_admin.create_agency_admin'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return redirect(url_for('super_admin.create_agency_admin'))
        
        # Create agency admin
        new_admin = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='agency_admin',
            agency_id=agency_id,
            is_active=True
        )
        new_admin.set_password(password)
        
        db.session.add(new_admin)
        db.session.commit()
        
        flash(f'Agency admin {username} created successfully!', 'success')
        return redirect(url_for('super_admin.manage_users'))
    
    agencies = Agency.query.filter_by(is_active=True).all()
    return render_template('super_admin/create_agency_admin.html', agencies=agencies)

@super_admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        role = request.form.get('role')
        agency_id = request.form.get('agency_id')
        
        # Check if email is unique (excluding current user)
        existing = User.query.filter_by(email=user.email).first()
        if existing and existing.id != user.id:
            flash('Email already exists', 'error')
            agencies = Agency.query.filter_by(is_active=True).all()
            return render_template('super_admin/edit_user.html', user=user, agencies=agencies)
        
        user.role = role
        user.agency_id = agency_id if agency_id else None
        
        # Handle password change if provided
        new_password = request.form.get('new_password')
        if new_password:
            user.set_password(new_password)
        
        db.session.commit()
        flash(f'User {user.username} updated successfully!', 'success')
        return redirect(url_for('super_admin.manage_users'))
    
    agencies = Agency.query.filter_by(is_active=True).all()
    return render_template('super_admin/edit_user.html', user=user, agencies=agencies)

@super_admin_bp.route('/users/<int:user_id>/reset_password', methods=['GET', 'POST'])
@login_required
@role_required('super_admin')
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

@super_admin_bp.route('/export_data')
@login_required
@role_required('super_admin')
def export_data():
    # Export comprehensive system data
    # This would be implemented with pandas/Excel export functionality
    flash('Data export functionality will be implemented', 'info')
    return redirect(url_for('super_admin.dashboard'))
