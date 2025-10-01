from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import func, extract, and_, or_, case
from datetime import datetime, timedelta
from decimal import Decimal

from app import db
from models import (
    Agency, User, Subscription, SubscriptionPlan, 
    SubscriptionInvoice, SubscriptionItem, ActivityLog
)
from auth.utils import role_required
from . import subscription_bp

def _log_subscription_activity(action, description):
    """Helper function to log subscription-related activities."""
    try:
        log = ActivityLog(
            user_id=session.get('user_id'),
            action=action,
            description=description
        )
        db.session.add(log)
    except Exception:
        # Log and continue if logging fails
        pass

def _validate_plan_form(form_data, plan_id=None):
    """Helper function to validate subscription plan form data."""
    name = form_data.get('name')
    code = form_data.get('code')
    price = form_data.get('price')
    billing_cycle = form_data.get('billing_cycle')

    if not all([name, code, price, billing_cycle]):
        flash('Name, code, price, and billing cycle are required.', 'error')
        return False

    # Check if code already exists (and is not the current plan being edited)
    code_query = SubscriptionPlan.query.filter_by(code=code)
    if plan_id:
        code_query = code_query.filter(SubscriptionPlan.id != plan_id)
    if code_query.first():
        flash('Plan code already exists.', 'error')
        return False

    # Check if name already exists (and is not the current plan being edited)
    name_query = SubscriptionPlan.query.filter_by(name=name)
    if plan_id:
        name_query = name_query.filter(SubscriptionPlan.id != plan_id)
    if name_query.first():
        flash('Plan name already exists.', 'error')
        return False
    
    return True

# ============================================================================
# SUPER ADMIN ROUTES - Full Control
# ============================================================================

@subscription_bp.route('/dashboard')
@role_required('super_admin', 'agency_manager')
def dashboard():
    """Subscription overview dashboard for super admin and agency managers"""
    user_role = session.get('role')
    user_id = session.get('user_id')

    # Base query for subscriptions
    sub_query = Subscription.query
    invoice_query = SubscriptionInvoice.query

    if user_role == 'agency_manager':
        managed_agency_ids = [a.id for a in Agency.query.filter_by(agency_manager_id=user_id).all()]
        sub_query = sub_query.filter(Subscription.agency_id.in_(managed_agency_ids))
        invoice_query = invoice_query.filter(SubscriptionInvoice.agency_id.in_(managed_agency_ids))
    
    # Statistics
    total_subscriptions = sub_query.count()
    active_subscriptions = sub_query.filter(Subscription.status == 'active').count()
    suspended_subscriptions = sub_query.filter(Subscription.status == 'suspended').count()
    cancelled_subscriptions = sub_query.filter(Subscription.status == 'cancelled').count()
    
    # Optimized Revenue Calculation (MRR/ARR)
    mrr_query = db.session.query(
            func.sum(
                case(
                    (SubscriptionPlan.billing_cycle == 'monthly', SubscriptionPlan.price),
                    (SubscriptionPlan.billing_cycle == 'quarterly', SubscriptionPlan.price / 3),
                    (SubscriptionPlan.billing_cycle == 'half_yearly', SubscriptionPlan.price / 6),
                    (SubscriptionPlan.billing_cycle == 'yearly', SubscriptionPlan.price / 12),
                    else_=0
                )
            )
        ).join(Subscription).filter(Subscription.status == 'active')

    if user_role == 'agency_manager':
        mrr_query = mrr_query.filter(Subscription.agency_id.in_(managed_agency_ids))

    total_mrr = mrr_query.scalar() or 0
    
    total_mrr = float(total_mrr)
    total_arr = total_mrr * 12
    
    # Expiring subscriptions (next 30 days)
    thirty_days_from_now = datetime.utcnow() + timedelta(days=30)
    expiring_soon = sub_query.filter(
        Subscription.status == 'active',
        Subscription.next_billing_date <= thirty_days_from_now,
        Subscription.next_billing_date >= datetime.utcnow()
    ).count()
    
    # Overdue invoices
    overdue_invoices = invoice_query.filter(
        SubscriptionInvoice.status.in_(['issued', 'draft']),
        SubscriptionInvoice.due_date < datetime.utcnow()
    ).count()
    
    # Subscription by status for chart
    subscription_stats = db.session.query(
        Subscription.status,
        func.count(Subscription.id)
    ).select_from(sub_query).group_by(Subscription.status).all()
    
    # Subscriptions by plan
    plan_stats = db.session.query(
        SubscriptionPlan.name,
        func.count(Subscription.id)
    ).select_from(sub_query).join(SubscriptionPlan).group_by(SubscriptionPlan.name).all()
    
    # Recent subscriptions
    recent_subscriptions = sub_query.order_by(
        Subscription.created_at.desc()
    ).limit(10).all()
    
    # Monthly revenue trend (last 6 months)
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    revenue_query_base = db.session.query(
        extract('year', SubscriptionInvoice.paid_at).label('year'),
        extract('month', SubscriptionInvoice.paid_at).label('month'),
        func.sum(SubscriptionInvoice.amount).label('total')
    ).filter(
        SubscriptionInvoice.status == 'paid',
        SubscriptionInvoice.paid_at >= six_months_ago
    )
    
    if user_role == 'agency_manager':
        revenue_query_base = revenue_query_base.filter(SubscriptionInvoice.agency_id.in_(managed_agency_ids))

    monthly_revenue = revenue_query_base.group_by('year', 'month').order_by('year', 'month').all()

    stats = {
        'total_subscriptions': total_subscriptions,
        'active_subscriptions': active_subscriptions,
        'suspended_subscriptions': suspended_subscriptions,
        'cancelled_subscriptions': cancelled_subscriptions,
        'total_mrr': round(total_mrr, 2),
        'total_arr': round(total_arr, 2),
        'expiring_soon': expiring_soon,
        'overdue_invoices': overdue_invoices
    }
    
    return render_template(
        'subscription/dashboard.html',
        stats=stats,
        subscription_stats=subscription_stats,
        plan_stats=plan_stats,
        recent_subscriptions=recent_subscriptions,
        monthly_revenue=monthly_revenue
    )


@subscription_bp.route('/plans')
@role_required('super_admin')
def list_plans():
    """List all subscription plans"""
    # Optimized query to avoid N+1 problem
    # Subquery to count all subscriptions per plan
    all_subs_count = db.session.query(
        Subscription.plan_id,
        func.count(Subscription.id).label('subscription_count')
    ).group_by(Subscription.plan_id).subquery()

    # Subquery to count only active subscriptions per plan
    active_subs_count = db.session.query(
        Subscription.plan_id,
        func.count(Subscription.id).label('active_subscription_count')
    ).filter(Subscription.status == 'active').group_by(Subscription.plan_id).subquery()

    # Main query to join plans with counts
    plans = db.session.query(
        SubscriptionPlan,
        func.coalesce(all_subs_count.c.subscription_count, 0).label('subscription_count'),
        func.coalesce(active_subs_count.c.active_subscription_count, 0).label('active_subscription_count')
    ).outerjoin(all_subs_count, SubscriptionPlan.id == all_subs_count.c.plan_id)\
     .outerjoin(active_subs_count, SubscriptionPlan.id == active_subs_count.c.plan_id)\
     .order_by(SubscriptionPlan.price).all()
    
    return render_template('subscription/plans_list.html', plans=plans)


@subscription_bp.route('/plans/create', methods=['GET', 'POST'])
@role_required('super_admin')
def create_plan():
    """Create a new subscription plan"""
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        description = request.form.get('description')
        price = request.form.get('price')
        billing_cycle = request.form.get('billing_cycle')
        features = request.form.get('features')
        is_active = request.form.get('is_active') == 'on'
        
        if not _validate_plan_form(request.form):
            return render_template('subscription/plan_form.html')
        
        try:
            new_plan = SubscriptionPlan(
                name=name,
                code=code,
                description=description,
                price=Decimal(price),
                billing_cycle=billing_cycle,
                features=features,
                is_active=is_active
            )
            
            db.session.add(new_plan)
            db.session.commit()
            
            _log_subscription_activity('create_subscription_plan', f'Created subscription plan: {name}')
            db.session.commit()
            
            flash(f'Subscription plan "{name}" created successfully!', 'success')
            return redirect(url_for('subscription.list_plans'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating plan: {str(e)}', 'error')
    
    return render_template('subscription/plan_form.html', plan=None)


@subscription_bp.route('/plans/<int:plan_id>/edit', methods=['GET', 'POST'])
@role_required('super_admin')
def edit_plan(plan_id):
    """Edit an existing subscription plan"""
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        description = request.form.get('description')
        price = request.form.get('price')
        billing_cycle = request.form.get('billing_cycle')
        features = request.form.get('features')
        is_active = request.form.get('is_active') == 'on'
        
        if not _validate_plan_form(request.form, plan_id=plan_id):
            return render_template('subscription/plan_form.html', plan=plan)
        
        try:
            plan.name = name
            plan.code = code
            plan.description = description
            plan.price = Decimal(price)
            plan.billing_cycle = billing_cycle
            plan.features = features
            plan.is_active = is_active
            
            db.session.commit()
            
            _log_subscription_activity('update_subscription_plan', f'Updated subscription plan: {name}')
            db.session.commit()
            
            flash(f'Subscription plan "{name}" updated successfully!', 'success')
            return redirect(url_for('subscription.list_plans'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating plan: {str(e)}', 'error')
    
    return render_template('subscription/plan_form.html', plan=plan)


@subscription_bp.route('/plans/<int:plan_id>/delete', methods=['POST'])
@role_required('super_admin')
def delete_plan(plan_id):
    """Delete a subscription plan"""
    plan = SubscriptionPlan.query.get_or_404(plan_id)
    
    # Check if plan has active subscriptions
    active_subs = Subscription.query.filter_by(plan_id=plan_id, status='active').count()
    if active_subs > 0:
        flash(f'Cannot delete plan. It has {active_subs} active subscription(s).', 'error')
        return redirect(url_for('subscription.list_plans'))
    
    try:
        plan_name = plan.name
        db.session.delete(plan)
        db.session.commit()
        
        _log_subscription_activity('delete_subscription_plan', f'Deleted subscription plan: {plan_name}')
        db.session.commit()
        
        flash(f'Subscription plan "{plan_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting plan: {str(e)}', 'error')
    
    return redirect(url_for('subscription.list_plans'))


@subscription_bp.route('/subscriptions')
@role_required('super_admin', 'agency_manager')
def list_subscriptions():
    """List all subscriptions"""
    status_filter = request.args.get('status', 'all')
    agency_filter = request.args.get('agency', type=int)
    plan_filter = request.args.get('plan', type=int)
    
    # Base query
    query = Subscription.query
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if agency_filter:
        query = query.filter_by(agency_id=agency_filter)
    
    if plan_filter:
        query = query.filter_by(plan_id=plan_filter)
    
    # For agency managers, only show their agencies
    if session.get('role') == 'agency_manager':
        manager_id = session.get('user_id')
        managed_agency_ids = [a.id for a in Agency.query.filter_by(agency_manager_id=manager_id).all()]
        query = query.filter(Subscription.agency_id.in_(managed_agency_ids))
    
    subscriptions = query.order_by(Subscription.created_at.desc()).all()
    
    # Get all agencies and plans for filters
    agencies = Agency.query.order_by(Agency.name).all()
    plans = SubscriptionPlan.query.order_by(SubscriptionPlan.name).all()
    
    return render_template(
        'subscription/subscriptions_list.html',
        subscriptions=subscriptions,
        agencies=agencies,
        plans=plans,
        status_filter=status_filter,
        agency_filter=agency_filter,
        plan_filter=plan_filter,
        now=datetime.utcnow()
    )


@subscription_bp.route('/subscriptions/create', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_manager')
def create_subscription():
    """Create a new subscription for an agency"""
    agency_id = request.args.get('agency_id', type=int)
    
    if request.method == 'POST':
        agency_id = request.form.get('agency_id', type=int)
        plan_id = request.form.get('plan_id', type=int)
        start_date_str = request.form.get('start_date')
        billing_cycle_count = request.form.get('billing_cycle_count', type=int, default=1)
        
        # Validation
        if not all([agency_id, plan_id, start_date_str]):
            flash('Agency, plan, and start date are required.', 'error')
            return redirect(url_for('subscription.create_subscription'))
        
        agency = Agency.query.get_or_404(agency_id)
        plan = SubscriptionPlan.query.get_or_404(plan_id)
        
        # Check if agency already has a subscription
        existing_sub = Subscription.query.filter_by(agency_id=agency_id).first()
        if existing_sub:
            flash(f'Agency "{agency.name}" already has a subscription.', 'error')
            return redirect(url_for('subscription.list_subscriptions'))
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            
            # Calculate next billing date based on billing cycle
            if plan.billing_cycle == 'monthly':
                next_billing = start_date + timedelta(days=30 * billing_cycle_count)
            elif plan.billing_cycle == 'quarterly':
                next_billing = start_date + timedelta(days=90 * billing_cycle_count)
            elif plan.billing_cycle == 'half_yearly':
                next_billing = start_date + timedelta(days=180 * billing_cycle_count)
            elif plan.billing_cycle == 'yearly':
                next_billing = start_date + timedelta(days=365 * billing_cycle_count)
            else:
                next_billing = start_date + timedelta(days=30)
            
            new_subscription = Subscription(
                agency_id=agency_id,
                plan_id=plan_id,
                status='active',
                start_date=start_date,
                next_billing_date=next_billing
            )
            
            db.session.add(new_subscription)
            db.session.commit()
            
            _log_subscription_activity('create_subscription', f'Created subscription for agency: {agency.name} with plan: {plan.name}')
            db.session.commit()
            
            flash(f'Subscription created successfully for "{agency.name}"!', 'success')
            return redirect(url_for('subscription.view_subscription', subscription_id=new_subscription.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating subscription: {str(e)}', 'error')
    
    # Get agencies and plans for form
    if session.get('role') == 'agency_manager':
        manager_id = session.get('user_id')
        agencies = Agency.query.filter_by(agency_manager_id=manager_id).order_by(Agency.name).all()
    else:
        agencies = Agency.query.order_by(Agency.name).all()
    
    plans = SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.price).all()
    
    # Pre-select agency if provided
    selected_agency = None
    if agency_id:
        selected_agency = Agency.query.get(agency_id)
    
    return render_template(
        'subscription/subscription_form.html',
        subscription=None,
        agencies=agencies,
        plans=plans,
        selected_agency=selected_agency
    )


@subscription_bp.route('/subscriptions/<int:subscription_id>')
@role_required('super_admin', 'agency_manager', 'agency_admin')
def view_subscription(subscription_id):
    """View subscription details"""
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Permission check for agency manager and agency admin
    if session.get('role') == 'agency_manager':
        manager_id = session.get('user_id')
        managed_agency_ids = [a.id for a in Agency.query.filter_by(agency_manager_id=manager_id).all()]
        if subscription.agency_id not in managed_agency_ids:
            flash('You do not have permission to view this subscription.', 'error')
            return redirect(url_for('subscription.list_subscriptions'))
    
    if session.get('role') == 'agency_admin':
        user = User.query.get(session.get('user_id'))
        if user.agency_id != subscription.agency_id:
            flash('You do not have permission to view this subscription.', 'error')
            return redirect(url_for('index'))
    
    # Get invoices for this subscription
    invoices = SubscriptionInvoice.query.filter_by(
        subscription_id=subscription_id
    ).order_by(SubscriptionInvoice.created_at.desc()).all()
    
    # Get subscription items
    items = SubscriptionItem.query.filter_by(subscription_id=subscription_id).all()
    
    return render_template(
        'subscription/subscription_detail.html',
        subscription=subscription,
        invoices=invoices,
        items=items
    )


@subscription_bp.route('/subscriptions/<int:subscription_id>/edit', methods=['GET', 'POST'])
@role_required('super_admin', 'agency_manager')
def edit_subscription(subscription_id):
    """Edit subscription details"""
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Permission check for agency manager
    if session.get('role') == 'agency_manager':
        manager_id = session.get('user_id')
        managed_agency_ids = [a.id for a in Agency.query.filter_by(agency_manager_id=manager_id).all()]
        if subscription.agency_id not in managed_agency_ids:
            flash('You do not have permission to edit this subscription.', 'error')
            return redirect(url_for('subscription.list_subscriptions'))
    
    if request.method == 'POST':
        plan_id = request.form.get('plan_id', type=int)
        status = request.form.get('status')
        next_billing_date_str = request.form.get('next_billing_date')
        
        try:
            if plan_id and plan_id != subscription.plan_id:
                subscription.plan_id = plan_id
            
            if status:
                old_status = subscription.status
                subscription.status = status
                
                # If suspending, log it
                if status == 'suspended' and old_status != 'suspended':
                    _log_subscription_activity('suspend_subscription', f'Suspended subscription for agency: {subscription.agency_rel.name}')
                
                # If cancelling, set cancelled_at
                if status == 'cancelled' and old_status != 'cancelled':
                    subscription.cancelled_at = datetime.utcnow()
                    _log_subscription_activity('cancel_subscription', f'Cancelled subscription for agency: {subscription.agency_rel.name}')
                
                if status == 'active' and old_status != 'active':
                    _log_subscription_activity('activate_subscription', f'Activated subscription for agency: {subscription.agency_rel.name}')
            
            if next_billing_date_str:
                subscription.next_billing_date = datetime.strptime(next_billing_date_str, '%Y-%m-%d')
            
            subscription.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash('Subscription updated successfully!', 'success')
            return redirect(url_for('subscription.view_subscription', subscription_id=subscription_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating subscription: {str(e)}', 'error')
    
    plans = SubscriptionPlan.query.filter_by(is_active=True).order_by(SubscriptionPlan.price).all()
    
    return render_template(
        'subscription/subscription_edit.html',
        subscription=subscription,
        plans=plans
    )


@subscription_bp.route('/subscriptions/<int:subscription_id>/suspend', methods=['POST'])
@role_required('super_admin')
def suspend_subscription(subscription_id):
    """Suspend a subscription"""
    subscription = Subscription.query.get_or_404(subscription_id)
    
    try:
        subscription.status = 'suspended'
        subscription.updated_at = datetime.utcnow()
        db.session.commit()
        
        _log_subscription_activity('suspend_subscription', f'Suspended subscription for agency: {subscription.agency_rel.name}')
        db.session.commit()
        
        flash('Subscription suspended successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error suspending subscription: {str(e)}', 'error')
    
    return redirect(url_for('subscription.view_subscription', subscription_id=subscription_id))


@subscription_bp.route('/subscriptions/<int:subscription_id>/activate', methods=['POST'])
@role_required('super_admin', 'agency_manager')
def activate_subscription(subscription_id):
    """Activate a suspended subscription"""
    subscription = Subscription.query.get_or_404(subscription_id)
    
    # Permission check for agency manager
    if session.get('role') == 'agency_manager':
        manager_id = session.get('user_id')
        managed_agency_ids = [a.id for a in Agency.query.filter_by(agency_manager_id=manager_id).all()]
        if subscription.agency_id not in managed_agency_ids:
            flash('You do not have permission to activate this subscription.', 'error')
            return redirect(url_for('subscription.list_subscriptions'))
    
    try:
        subscription.status = 'active'
        subscription.updated_at = datetime.utcnow()
        db.session.commit()
        
        _log_subscription_activity('activate_subscription', f'Activated subscription for agency: {subscription.agency_rel.name}')
        db.session.commit()
        
        flash('Subscription activated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error activating subscription: {str(e)}', 'error')
    
    return redirect(url_for('subscription.view_subscription', subscription_id=subscription_id))


@subscription_bp.route('/subscriptions/<int:subscription_id>/cancel', methods=['POST'])
@role_required('super_admin')
def cancel_subscription(subscription_id):
    """Cancel a subscription"""
    subscription = Subscription.query.get_or_404(subscription_id)
    
    try:
        subscription.status = 'cancelled'
        subscription.updated_at = datetime.utcnow()
        db.session.commit()
        
        _log_subscription_activity('cancel_subscription', f'Cancelled subscription for agency: {subscription.agency_rel.name}')
        db.session.commit()
        
        flash('Subscription cancelled successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling subscription: {str(e)}', 'error')
    
    return redirect(url_for('subscription.view_subscription', subscription_id=subscription_id))


@subscription_bp.route('/invoices')
@role_required('super_admin', 'agency_manager')
def list_invoices():
    """List all subscription invoices"""
    status_filter = request.args.get('status', 'all')
    agency_filter = request.args.get('agency', type=int)
    
    # Base query
    query = SubscriptionInvoice.query
    
    # Apply filters
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if agency_filter:
        query = query.filter_by(agency_id=agency_filter)
    
    # For agency managers, only show their agencies
    if session.get('role') == 'agency_manager':
        manager_id = session.get('user_id')
        managed_agency_ids = [a.id for a in Agency.query.filter_by(agency_manager_id=manager_id).all()]
        query = query.filter(SubscriptionInvoice.agency_id.in_(managed_agency_ids))
    
    invoices = query.order_by(SubscriptionInvoice.created_at.desc()).all()
    
    # Get all agencies for filters
    agencies = Agency.query.order_by(Agency.name).all()
    
    return render_template(
        'subscription/invoices_list.html',
        invoices=invoices,
        agencies=agencies,
        status_filter=status_filter,
        agency_filter=agency_filter,
        now=datetime.utcnow()
    )


@subscription_bp.route('/invoices/<int:invoice_id>/mark-paid', methods=['POST'])
@role_required('super_admin')
def mark_invoice_paid(invoice_id):
    """Mark an invoice as paid"""
    invoice = SubscriptionInvoice.query.get_or_404(invoice_id)
    
    try:
        invoice.status = 'paid'
        invoice.paid_at = datetime.utcnow()
        db.session.commit()
        
        _log_subscription_activity('mark_invoice_paid', f'Marked invoice {invoice.invoice_number} as paid')
        db.session.commit()
        
        flash('Invoice marked as paid successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error marking invoice as paid: {str(e)}', 'error')
    
    return redirect(url_for('subscription.list_invoices'))


@subscription_bp.route('/reports')
@role_required('super_admin')
def reports():
    """Subscription reports and analytics"""
    
    # Revenue by month (last 12 months)
    twelve_months_ago = datetime.utcnow() - timedelta(days=365)
    monthly_revenue = db.session.query(
        extract('year', SubscriptionInvoice.paid_at).label('year'),
        extract('month', SubscriptionInvoice.paid_at).label('month'),
        func.sum(SubscriptionInvoice.amount).label('total')
    ).filter(
        SubscriptionInvoice.status == 'paid',
        SubscriptionInvoice.paid_at >= twelve_months_ago
    ).group_by('year', 'month').order_by('year', 'month').all()
    
    # Churn rate calculation
    total_agencies = Agency.query.count()
    cancelled_this_month = Subscription.query.filter(
        Subscription.status == 'cancelled',
        extract('year', Subscription.cancelled_at) == datetime.utcnow().year,
        extract('month', Subscription.cancelled_at) == datetime.utcnow().month
    ).count()
    
    churn_rate = (cancelled_this_month / total_agencies * 100) if total_agencies > 0 else 0
    
    # Plan distribution
    plan_distribution = db.session.query(
        SubscriptionPlan.name,
        func.count(Subscription.id).label('count'),
        func.sum(SubscriptionPlan.price).label('revenue')
    ).join(Subscription).filter(
        Subscription.status == 'active'
    ).group_by(SubscriptionPlan.name).all()
    
    return render_template(
        'subscription/reports.html',
        monthly_revenue=monthly_revenue,
        churn_rate=round(churn_rate, 2),
        plan_distribution=plan_distribution
    )


# ============================================================================
# AGENCY ADMIN ROUTES - View Own Subscription
# ============================================================================

@subscription_bp.route('/my-subscription')
@role_required('agency_admin')
def view_agency_subscription():
    """View own agency's subscription"""
    user = User.query.get(session.get('user_id'))
    
    if not user.agency_id:
        flash('You are not associated with any agency.', 'error')
        return redirect(url_for('index'))
    
    subscription = Subscription.query.filter_by(agency_id=user.agency_id).first()
    
    if not subscription:
        flash('Your agency does not have an active subscription.', 'warning')
        return render_template('subscription/no_subscription.html')
    
    # Get invoices
    invoices = SubscriptionInvoice.query.filter_by(
        agency_id=user.agency_id
    ).order_by(SubscriptionInvoice.created_at.desc()).limit(10).all()
    
    return render_template(
        'subscription/my_subscription.html',
        subscription=subscription,
        invoices=invoices
    )