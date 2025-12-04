from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
from decimal import Decimal
from extensions import db
from models import (
    Order, Customer, Agency, Location, User,
    Invoice, Payment, PaymentMethod, TaxRule
)
from . import billing_bp
from auth.utils import login_required, permission_required, get_role_permissions
from utils.decorators import log_activity
import uuid

@billing_bp.route('/dashboard')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def dashboard(current_agency_id=None):
    """Billing Dashboard with key metrics"""
    user_role = session.get('role')
    
    # Get date range (last 30 days by default)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=30)
    
    # Base query for invoices
    if user_role == 'super_admin':
        base_query = Invoice.query
    else:
        base_query = Invoice.query.filter_by(agency_id=current_agency_id)
    
    # Dashboard metrics
    period_invoices = base_query.filter(
        Invoice.issue_date >= start_date,
        Invoice.issue_date <= end_date
    ).all()
    
    total_invoiced = sum(inv.total_amount for inv in period_invoices)
    total_paid = sum(inv.total_amount for inv in period_invoices if inv.status == 'paid')
    total_pending = sum(inv.total_amount for inv in period_invoices if inv.status == 'pending')
    total_overdue = sum(inv.total_amount for inv in period_invoices if inv.status == 'overdue')
    
    # Recent invoices
    recent_invoices = base_query.order_by(Invoice.issue_date.desc()).limit(10).all()
    
    # Overdue invoices
    overdue_invoices = base_query.filter_by(status='overdue').limit(5).all()
    
    # Payment methods for agency
    if user_role == 'super_admin':
        payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
    else:
        payment_methods = PaymentMethod.query.filter_by(
            agency_id=current_agency_id, is_active=True
        ).all()
    
    dashboard_stats = {
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'total_pending': total_pending,
        'total_overdue': total_overdue,
        'collection_rate': (total_paid / total_invoiced * 100) if total_invoiced > 0 else 0
    }
    
    return render_template('billing/dashboard.html',
                         stats=dashboard_stats,
                         recent_invoices=recent_invoices,
                         overdue_invoices=overdue_invoices,
                         payment_methods=payment_methods)

@billing_bp.route('/invoices')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def list_invoices(current_agency_id=None):
    """List all invoices with filtering"""
    user_role = session.get('role')
    
    # Get filter parameters
    status = request.args.get('status')
    customer_id = request.args.get('customer_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Base query
    if user_role == 'super_admin':
        query = Invoice.query
    else:
        query = Invoice.query.filter_by(agency_id=current_agency_id)
    
    # Apply filters
    if status:
        query = query.filter_by(status=status)
    
    if customer_id:
        query = query.filter_by(customer_id=customer_id)
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(Invoice.issue_date >= start_dt)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_dt = end_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Invoice.issue_date <= end_dt)
        except ValueError:
            pass
    
    # Get paginated results
    invoices = query.order_by(Invoice.issue_date.desc()).paginate(
        page=request.args.get('page', 1, type=int),
        per_page=20,
        error_out=False
    )
    
    # Get customers for filter dropdown
    if user_role == 'super_admin':
        customers = Customer.query.all()
    else:
        customers = Customer.query.join(Location).filter(
            Location.agency_id == current_agency_id
        ).all()
    
    return render_template('billing/invoices.html', 
                         invoices=invoices, 
                         customers=customers,
                         current_filters={
                             'status': status,
                             'customer_id': customer_id,
                             'start_date': start_date,
                             'end_date': end_date
                         })

@billing_bp.route('/invoice/<int:invoice_id>')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def view_invoice(invoice_id, current_agency_id=None):
    """View individual invoice details"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        invoice = Invoice.query.get_or_404(invoice_id)
    else:
        invoice = Invoice.query.filter_by(id=invoice_id, agency_id=current_agency_id).first_or_404()
    
    return render_template('billing/invoice_detail.html', invoice=invoice, now=datetime.utcnow())

@billing_bp.route('/create_invoice/<int:order_id>')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
@log_activity('invoice_created')
def create_invoice_from_order(order_id, current_agency_id=None):
    """Create invoice from existing order"""
    user_role = session.get('role')
    
    # Get order with permission check
    if user_role == 'super_admin':
        order = Order.query.get_or_404(order_id)
    else:
        order = Order.query.filter_by(id=order_id, agency_id=current_agency_id).first_or_404()
    
    # Check if invoice already exists
    existing_invoice = Invoice.query.filter_by(order_id=order_id).first()
    if existing_invoice:
        flash('Invoice already exists for this order', 'warning')
        return redirect(url_for('billing.view_invoice', invoice_id=existing_invoice.id))
    
    try:
        # Calculate totals
        subtotal = sum(item.total_price for item in order.order_items)
        
        # Generate invoice number
        invoice_number = f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
        
        # Create invoice
        invoice = Invoice(
            invoice_number=invoice_number,
            order_id=order.id,
            agency_id=order.agency_id,
            customer_id=order.customer_id,
            subtotal=subtotal,
            tax_amount=order.tax,
            discount_amount=order.discount,
            total_amount=order.total_amount,
            status='pending',
            issue_date=datetime.utcnow(),
            due_date=datetime.utcnow() + timedelta(days=30),  # 30 days payment terms
            payment_terms='Net 30'
        )
        
        db.session.add(invoice)
        db.session.commit()
        
        flash('Invoice created successfully', 'success')
        return redirect(url_for('billing.view_invoice', invoice_id=invoice.id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating invoice: {str(e)}', 'error')
        return redirect(url_for('order.view_order', order_id=order_id))

@billing_bp.route('/record_payment/<int:invoice_id>', methods=['GET', 'POST'])
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
@log_activity('payment_recorded')
def record_payment(invoice_id, current_agency_id=None):
    """Record payment for an invoice"""
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # Get invoice with permission check
    if user_role == 'super_admin':
        invoice = Invoice.query.get_or_404(invoice_id)
    else:
        invoice = Invoice.query.filter_by(id=invoice_id, agency_id=current_agency_id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Get form data
            amount = Decimal(str(request.form.get('amount', 0)))
            payment_method_id = request.form.get('payment_method_id')
            transaction_id = request.form.get('transaction_id', '')
            notes = request.form.get('notes', '')
            
            # Validate amount
            remaining_amount = invoice.total_amount - sum(p.amount for p in invoice.payments)
            if amount <= 0 or amount > remaining_amount:
                flash('Invalid payment amount', 'error')
                return render_template('billing/record_payment.html', invoice=invoice)
            
            # Generate payment number
            payment_number = f"PAY-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
            
            # Create payment record
            payment = Payment(
                payment_number=payment_number,
                invoice_id=invoice.id,
                payment_method_id=payment_method_id,
                amount=amount,
                payment_date=datetime.utcnow(),
                transaction_id=transaction_id,
                status='completed',
                notes=notes,
                processed_by=user_id
            )
            
            db.session.add(payment)
            
            # Update invoice status
            total_paid = sum(p.amount for p in invoice.payments) + amount
            if total_paid >= invoice.total_amount:
                invoice.status = 'paid'
                invoice.paid_date = datetime.utcnow()
            else:
                invoice.status = 'partial'
            
            db.session.commit()
            
            flash('Payment recorded successfully', 'success')
            return redirect(url_for('billing.view_invoice', invoice_id=invoice.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording payment: {str(e)}', 'error')
    
    # Get payment methods
    if user_role == 'super_admin':
        payment_methods = PaymentMethod.query.filter_by(is_active=True).all()
    else:
        payment_methods = PaymentMethod.query.filter_by(
            agency_id=current_agency_id, is_active=True
        ).all()
    
    return render_template('billing/record_payment.html', 
                         invoice=invoice, 
                         payment_methods=payment_methods)

@billing_bp.route('/payment_methods')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def list_payment_methods(current_agency_id=None):
    """List payment methods for agency"""
    user_role = session.get('role')
    
    if user_role == 'super_admin':
        payment_methods = PaymentMethod.query.all()
    else:
        payment_methods = PaymentMethod.query.filter_by(agency_id=current_agency_id).all()
    
    return render_template('billing/payment_methods.html', payment_methods=payment_methods)

@billing_bp.route('/add_payment_method', methods=['GET', 'POST'])
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('payment_method_added')
def add_payment_method(current_agency_id=None):
    """Add new payment method"""
    user_role = session.get('role')
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            method_type = request.form.get('method_type', '')
            description = request.form.get('description', '').strip()
            is_active = request.form.get('is_active') == 'on'
            
            # Validation
            if not name or not method_type:
                flash('Name and type are required', 'error')
                return render_template('billing/add_payment_method.html')
            
            # Check for duplicate name within agency
            if user_role == 'super_admin':
                existing = PaymentMethod.query.filter_by(name=name).first()
            else:
                existing = PaymentMethod.query.filter_by(
                    name=name, agency_id=current_agency_id
                ).first()
            
            if existing:
                flash('Payment method with this name already exists', 'error')
                return render_template('billing/add_payment_method.html')
            
            # Generate a unique code
            base_code = name.upper().replace(' ', '_')[:15]
            unique_code = base_code
            counter = 1
            while PaymentMethod.query.filter_by(code=unique_code).first():
                unique_code = f"{base_code}_{counter}"
                counter += 1

            # Create payment method
            payment_method = PaymentMethod(
                name=name,
                code=unique_code,
                agency_id=current_agency_id,
                is_active=is_active,
            )
            
            db.session.add(payment_method)
            db.session.commit()
            
            flash('Payment method added successfully', 'success')
            return redirect(url_for('billing.list_payment_methods'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding payment method: {str(e)}', 'error')
    
    return render_template('billing/add_payment_method.html')

@billing_bp.route('/reports')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def reports(current_agency_id=None):
    """Billing reports and analytics"""
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
    
    # Base query
    if user_role == 'super_admin':
        invoice_query = Invoice.query
        payment_query = Payment.query
    else:
        invoice_query = Invoice.query.filter_by(agency_id=current_agency_id)
        payment_query = Payment.query.join(Invoice).filter(Invoice.agency_id == current_agency_id)
    
    # Filter by date range
    period_invoices = invoice_query.filter(
        Invoice.issue_date.between(start_dt, end_dt)
    ).all()
    
    period_payments = payment_query.filter(
        Payment.payment_date >= start_dt,
        Payment.payment_date <= end_dt
    ).all()
    
    # Calculate report metrics
    report_data = {
        'total_invoices': len(period_invoices),
        'total_invoiced': sum(inv.total_amount for inv in period_invoices),
        'total_payments': len(period_payments),
        'total_collected': sum(pay.amount for pay in period_payments),
        'avg_invoice_value': (sum(inv.total_amount for inv in period_invoices) / len(period_invoices)) if period_invoices else 0,
        'avg_payment_value': (sum(pay.amount for pay in period_payments) / len(period_payments)) if period_payments else 0,
        'start_date': start_date,
        'end_date': end_date
    }
    
    # Status breakdown
    status_counts = {}
    status_amounts = {}
    for invoice in period_invoices:
        status = invoice.status
        status_counts[status] = status_counts.get(status, 0) + 1
        status_amounts[status] = status_amounts.get(status, 0) + invoice.total_amount
    
    # Payment method breakdown
    payment_method_amounts = {}
    for payment in period_payments:
        method = payment.payment_method.name
        payment_method_amounts[method] = payment_method_amounts.get(method, 0) + payment.amount
    
    return render_template('billing/reports.html',
                         report_data=report_data,
                         status_counts=status_counts,
                         status_amounts=status_amounts,
                         payment_method_amounts=payment_method_amounts)
 
@billing_bp.route('/payments')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def list_payments(current_agency_id=None):
    """List all payments with filtering and pagination"""
    user_role = session.get('role')
    search = request.args.get('search', '').strip()

    # Get pagination parameters from request args
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    if per_page not in [10, 20, 50, 100]:
        per_page = 20

    # Base query, joining with related tables for searching
    query = Payment.query.join(Invoice, Payment.invoice_id == Invoice.id).join(Customer, Invoice.customer_id == Customer.id)

    # Apply role-based filtering
    if user_role != 'super_admin':
        query = query.filter(Invoice.agency_id == current_agency_id)

    # Apply search filter if a query is provided
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Payment.payment_number.ilike(search_term),
                Invoice.invoice_number.ilike(search_term),
                Customer.name.ilike(search_term)
            )
        )

    # Order the results and apply pagination
    pagination = query.order_by(Payment.payment_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return render_template(
        'billing/payments.html',
        pagination=pagination,
        per_page=per_page,
        search=search
    )