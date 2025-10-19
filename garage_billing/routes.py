from flask import render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import (
    GarageInvoice, GarageInvoiceItem, GaragePayment, WorkOrder, 
    Customer, Agency, User, Estimate
)
from functools import wraps
from datetime import datetime
from decimal import Decimal
from garage_billing import garage_billing_bp

# Authorization decorators
def require_agency_access(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.role not in ['super_admin', 'agency_admin', 'agency_manager', 'service_manager']:
            flash('Unauthorized access', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# ==================== GARAGE INVOICES ====================

# LIST INVOICES
@garage_billing_bp.route('/invoices', methods=['GET'])
@login_required
@require_agency_access
def list_invoices():
    """List all garage invoices"""
    status = request.args.get('status', None)
    
    if current_user.role == 'super_admin':
        query = GarageInvoice.query
    else:
        query = GarageInvoice.query.filter_by(agency_id=current_user.agency_id)
    
    if status:
        query = query.filter_by(payment_status=status)
    
    invoices = query.order_by(GarageInvoice.created_at.desc()).all()
    
    return render_template('garage_billing/invoices_list.html', invoices=invoices, status=status)

# CREATE INVOICE FROM ESTIMATE
@garage_billing_bp.route('/invoices/create/<int:estimate_id>', methods=['GET', 'POST'])
@login_required
@require_agency_access
def create_invoice_from_estimate(estimate_id):
    """Create garage invoice from approved estimate"""
    estimate = Estimate.query.get_or_404(estimate_id)
    work_order = estimate.work_order
    
    # Verify access
    if current_user.role != 'super_admin' and work_order.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('garage_billing.list_invoices'))
    
    if estimate.status != 'Approved':
        flash('Can only create invoices from Approved estimates', 'warning')
        return redirect(url_for('estimates.view_estimate', estimate_id=estimate_id))
    
    if request.method == 'POST':
        data = request.get_json()
        
        # Generate invoice number
        last_invoice = GarageInvoice.query.order_by(GarageInvoice.id.desc()).first()
        invoice_num = f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{(last_invoice.id + 1 if last_invoice else 1):04d}"
        
        subtotal = Decimal(str(data.get('subtotal_amount', 0)))
        tax = Decimal(str(data.get('tax_amount', 0)))
        discount = Decimal(str(data.get('discount', 0)))
        total = subtotal + tax - discount
        
        invoice = GarageInvoice(
            work_order_id=work_order.id,
            invoice_number=invoice_num,
            agency_id=work_order.agency_id,
            customer_id=work_order.customer_id,
            subtotal_amount=subtotal,
            tax_amount=tax,
            discount=discount,
            total_amount=total,
            balance_due=total,
            payment_terms=data.get('payment_terms', ''),
            notes=data.get('notes', '')
        )
        db.session.add(invoice)
        db.session.flush()
        
        # Add invoice items from estimate items
        for item in estimate.items:
            invoice_item = GarageInvoiceItem(
                garage_invoice_id=invoice.id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                line_total=item.line_total
            )
            db.session.add(invoice_item)
        
        db.session.commit()
        flash('Garage invoice created successfully', 'success')
        return jsonify({'success': True, 'invoice_id': invoice.id})
    
    return render_template('garage_billing/create_invoice.html', estimate=estimate, work_order=work_order)

# VIEW INVOICE
@garage_billing_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
@login_required
@require_agency_access
def view_invoice(invoice_id):
    """View invoice details"""
    invoice = GarageInvoice.query.get_or_404(invoice_id)
    
    # Verify access
    if current_user.role != 'super_admin' and invoice.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('garage_billing.list_invoices'))
    
    return render_template('garage_billing/view_invoice.html', invoice=invoice)

# PRINT/DOWNLOAD INVOICE
@garage_billing_bp.route('/invoices/<int:invoice_id>/download', methods=['GET'])
@login_required
@require_agency_access
def download_invoice(invoice_id):
    """Download invoice as PDF"""
    invoice = GarageInvoice.query.get_or_404(invoice_id)
    
    # Verify access
    if current_user.role != 'super_admin' and invoice.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('garage_billing.list_invoices'))
    
    # TODO: Implement PDF generation using reportlab or similar
    flash('PDF generation not yet implemented', 'info')
    return redirect(url_for('garage_billing.view_invoice', invoice_id=invoice_id))

# ==================== GARAGE PAYMENTS ====================

# RECORD PAYMENT
@garage_billing_bp.route('/invoices/<int:invoice_id>/payment', methods=['GET', 'POST'])
@login_required
@require_agency_access
def record_payment(invoice_id):
    """Record payment against invoice"""
    invoice = GarageInvoice.query.get_or_404(invoice_id)
    
    # Verify access
    if current_user.role != 'super_admin' and invoice.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('garage_billing.list_invoices'))
    
    if request.method == 'POST':
        data = request.get_json()
        
        amount = Decimal(str(data.get('amount', 0)))
        
        # Validate amount
        if amount <= 0:
            return jsonify({'success': False, 'message': 'Payment amount must be greater than 0'}), 400
        
        if amount > invoice.balance_due:
            return jsonify({'success': False, 'message': f'Payment exceeds balance due (₹{float(invoice.balance_due)})'}), 400
        
        # Create payment record
        payment = GaragePayment(
            garage_invoice_id=invoice_id,
            amount=amount,
            payment_mode=data.get('payment_mode', 'Cash'),
            reference_number=data.get('reference_number', ''),
            received_by=current_user.id,
            notes=data.get('notes', '')
        )
        db.session.add(payment)
        
        # Update invoice
        invoice.amount_paid = (invoice.amount_paid or 0) + amount
        invoice.balance_due = invoice.total_amount - invoice.amount_paid
        
        if invoice.balance_due <= 0:
            invoice.payment_status = 'Paid'
            invoice.paid_at = datetime.utcnow()
        else:
            invoice.payment_status = 'Partially Paid'
        
        db.session.commit()
        flash('Payment recorded successfully', 'success')
        return jsonify({'success': True, 'payment_id': payment.id})
    
    return render_template('garage_billing/record_payment.html', invoice=invoice)

# VIEW PAYMENTS
@garage_billing_bp.route('/invoices/<int:invoice_id>/payments', methods=['GET'])
@login_required
@require_agency_access
def view_payments(invoice_id):
    """View all payments for an invoice"""
    invoice = GarageInvoice.query.get_or_404(invoice_id)
    
    # Verify access
    if current_user.role != 'super_admin' and invoice.agency_id != current_user.agency_id:
        flash('Unauthorized access', 'danger')
        return redirect(url_for('garage_billing.list_invoices'))
    
    payments = GaragePayment.query.filter_by(garage_invoice_id=invoice_id).order_by(
        GaragePayment.payment_date.desc()
    ).all()
    
    return render_template('garage_billing/payments_list.html', invoice=invoice, payments=payments)

# API: Get invoice summary
@garage_billing_bp.route('/api/invoices/<int:invoice_id>/summary', methods=['GET'])
@login_required
def get_invoice_summary(invoice_id):
    """API endpoint to get invoice summary"""
    invoice = GarageInvoice.query.get_or_404(invoice_id)
    return jsonify({
        'invoice_number': invoice.invoice_number,
        'total_amount': float(invoice.total_amount),
        'amount_paid': float(invoice.amount_paid or 0),
        'balance_due': float(invoice.balance_due),
        'payment_status': invoice.payment_status
    })

# ==================== REPORTS ====================

# BILLING REPORT
@garage_billing_bp.route('/reports/billing', methods=['GET'])
@login_required
@require_agency_access
def billing_report():
    """Garage billing report"""
    from_date = request.args.get('from_date', None)
    to_date = request.args.get('to_date', None)
    status = request.args.get('status', None)
    
    query = GarageInvoice.query
    if current_user.role != 'super_admin':
        query = query.filter_by(agency_id=current_user.agency_id)
    
    if from_date:
        query = query.filter(GarageInvoice.created_at >= from_date)
    if to_date:
        query = query.filter(GarageInvoice.created_at <= to_date)
    if status:
        query = query.filter_by(payment_status=status)
    
    invoices = query.all()
    
    # Calculate summary
    total_invoiced = sum(float(inv.total_amount) for inv in invoices)
    total_collected = sum(float(inv.amount_paid or 0) for inv in invoices)
    total_pending = sum(float(inv.balance_due) for inv in invoices)
    
    return render_template(
        'garage_billing/billing_report.html',
        invoices=invoices,
        total_invoiced=total_invoiced,
        total_collected=total_collected,
        total_pending=total_pending,
        from_date=from_date,
        to_date=to_date
    )