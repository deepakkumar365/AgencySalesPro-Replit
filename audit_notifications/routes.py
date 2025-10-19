from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import AuditLog, Notification, User
from functools import wraps
from datetime import datetime, timedelta
from audit_notifications import audit_notifications_bp

# Authorization decorators
def require_admin_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['super_admin', 'agency_admin']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== AUDIT LOGS ====================

# AUDIT LOG DASHBOARD
@audit_notifications_bp.route('/audit', methods=['GET'])
@login_required
@require_admin_access
def audit_dashboard():
    """Audit log dashboard"""
    user_id = request.args.get('user_id', None)
    action = request.args.get('action', None)
    entity_name = request.args.get('entity_name', None)
    from_date = request.args.get('from_date', None)
    to_date = request.args.get('to_date', None)
    page = request.args.get('page', 1, type=int)
    
    query = AuditLog.query
    
    if user_id:
        query = query.filter_by(user_id=user_id)
    if action:
        query = query.filter_by(action=action)
    if entity_name:
        query = query.filter_by(entity_name=entity_name)
    if from_date:
        query = query.filter(AuditLog.timestamp >= f"{from_date} 00:00:00")
    if to_date:
        query = query.filter(AuditLog.timestamp <= f"{to_date} 23:59:59")
    
    # Paginate
    audit_logs = query.order_by(AuditLog.timestamp.desc()).paginate(
        page=page, per_page=50
    )
    
    # Get unique actions and entities for filters
    all_actions = db.session.query(AuditLog.action.distinct()).all()
    all_entities = db.session.query(AuditLog.entity_name.distinct()).all()
    
    return render_template(
        'audit_notifications/audit_dashboard.html',
        audit_logs=audit_logs,
        actions=[a[0] for a in all_actions],
        entities=[e[0] for e in all_entities],
        current_user_id=user_id,
        current_action=action,
        current_entity=entity_name
    )

# VIEW AUDIT LOG DETAILS
@audit_notifications_bp.route('/audit/<int:log_id>', methods=['GET'])
@login_required
@require_admin_access
def view_audit_log(log_id):
    """View detailed audit log entry"""
    log = AuditLog.query.get_or_404(log_id)
    return render_template('audit_notifications/audit_detail.html', log=log)

# EXPORT AUDIT LOGS
@audit_notifications_bp.route('/audit/export/csv', methods=['GET'])
@login_required
@require_admin_access
def export_audit_logs():
    """Export audit logs as CSV"""
    from io import StringIO
    import csv
    
    from_date = request.args.get('from_date', None)
    to_date = request.args.get('to_date', None)
    
    query = AuditLog.query
    
    if from_date:
        query = query.filter(AuditLog.timestamp >= f"{from_date} 00:00:00")
    if to_date:
        query = query.filter(AuditLog.timestamp <= f"{to_date} 23:59:59")
    
    logs = query.order_by(AuditLog.timestamp.desc()).all()
    
    # Create CSV
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp', 'User', 'Action', 'Entity', 'Entity ID', 'IP Address'])
    
    for log in logs:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.username,
            log.action,
            log.entity_name,
            log.entity_id,
            log.ip_address
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=audit_logs.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response

# ==================== NOTIFICATIONS ====================

# NOTIFICATION CENTER
@audit_notifications_bp.route('/notifications', methods=['GET'])
@login_required
def notifications_center():
    """User notification center"""
    status = request.args.get('status', 'Unread')
    notification_type = request.args.get('type', None)
    page = request.args.get('page', 1, type=int)
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if status and status != 'all':
        query = query.filter_by(status=status)
    if notification_type:
        query = query.filter_by(notification_type=notification_type)
    
    notifications = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=20
    )
    
    return render_template(
        'audit_notifications/notifications_center.html',
        notifications=notifications,
        current_status=status,
        current_type=notification_type
    )

# MARK NOTIFICATION AS READ
@audit_notifications_bp.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark notification as read"""
    notification = Notification.query.get_or_404(notification_id)
    
    # Verify ownership
    if notification.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    notification.status = 'Read'
    notification.read_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})

# MARK ALL NOTIFICATIONS AS READ
@audit_notifications_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for current user"""
    Notification.query.filter_by(user_id=current_user.id, status='Unread').update({
        'status': 'Read',
        'read_at': datetime.utcnow()
    })
    db.session.commit()
    
    return jsonify({'success': True})

# DELETE NOTIFICATION
@audit_notifications_bp.route('/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification(notification_id):
    """Delete notification"""
    notification = Notification.query.get_or_404(notification_id)
    
    # Verify ownership
    if notification.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    db.session.delete(notification)
    db.session.commit()
    
    return jsonify({'success': True})

# GET UNREAD COUNT
@audit_notifications_bp.route('/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_count():
    """Get count of unread notifications"""
    count = Notification.query.filter_by(user_id=current_user.id, status='Unread').count()
    return jsonify({'unread_count': count})

# GET RECENT NOTIFICATIONS
@audit_notifications_bp.route('/notifications/recent', methods=['GET'])
@login_required
def get_recent_notifications():
    """Get recent notifications (last 5)"""
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).limit(5).all()
    
    return jsonify([
        {
            'id': n.id,
            'message': n.message,
            'type': n.notification_type,
            'status': n.status,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'related_entity': n.related_entity,
            'related_entity_id': n.related_entity_id
        }
        for n in notifications
    ])

# ==================== NOTIFICATION MANAGEMENT ====================

# CREATE NOTIFICATION (for system use)
def create_notification(user_id, message, notification_type='Info', related_entity=None, related_entity_id=None):
    """Create a notification for a user (internal function)"""
    notification = Notification(
        user_id=user_id,
        message=message,
        notification_type=notification_type,
        related_entity=related_entity,
        related_entity_id=related_entity_id
    )
    db.session.add(notification)
    db.session.commit()
    return notification

# CREATE AUDIT LOG (for system use)
def create_audit_log(user_id, action, entity_name, entity_id, old_value=None, new_value=None, ip_address=None):
    """Create an audit log entry (internal function)"""
    audit_log = AuditLog(
        user_id=user_id,
        action=action,
        entity_name=entity_name,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address
    )
    db.session.add(audit_log)
    db.session.commit()
    return audit_log

# NOTIFICATION RULES
def notify_estimate_approved(estimate_id, work_order_id, approver_id):
    """Notify relevant users when estimate is approved"""
    work_order = WorkOrder.query.get(work_order_id)
    if work_order and work_order.created_by:
        create_notification(
            user_id=work_order.created_by,
            message=f"Estimate #{estimate_id} for Work Order #{work_order_id} has been approved",
            notification_type='Success',
            related_entity='Estimate',
            related_entity_id=estimate_id
        )

def notify_invoice_paid(invoice_id, amount):
    """Notify when invoice is fully paid"""
    invoice = GarageInvoice.query.get(invoice_id)
    if invoice and invoice.work_order.created_by:
        create_notification(
            user_id=invoice.work_order.created_by,
            message=f"Invoice #{invoice.invoice_number} has been paid (₹{amount})",
            notification_type='Success',
            related_entity='GarageInvoice',
            related_entity_id=invoice_id
        )

def notify_work_order_completed(work_order_id):
    """Notify when work order is completed"""
    work_order = WorkOrder.query.get(work_order_id)
    if work_order:
        # Notify creator
        if work_order.created_by:
            create_notification(
                user_id=work_order.created_by,
                message=f"Work Order #{work_order.job_number} has been completed",
                notification_type='Success',
                related_entity='WorkOrder',
                related_entity_id=work_order_id
            )

# API: Get notification statistics
@audit_notifications_bp.route('/api/notifications/stats', methods=['GET'])
@login_required
def get_notification_stats():
    """Get notification statistics for current user"""
    unread_count = Notification.query.filter_by(user_id=current_user.id, status='Unread').count()
    total_count = Notification.query.filter_by(user_id=current_user.id).count()
    
    by_type = {}
    notifications = Notification.query.filter_by(user_id=current_user.id).all()
    for n in notifications:
        by_type[n.notification_type] = by_type.get(n.notification_type, 0) + 1
    
    return jsonify({
        'unread_count': unread_count,
        'total_count': total_count,
        'by_type': by_type
    })