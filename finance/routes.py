from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import or_, func, and_, extract
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
import calendar

from app import db
from models import (
    FinancePayment, Receipt, PaymentPurchaseOrder, ReceiptSalesOrder,
    PurchaseOrder, Order, Customer, Supplier, Agency, User, PaymentConfiguration
)
from . import finance_bp
from auth.utils import login_required, permission_required
from utils.decorators import log_activity


def generate_payment_number():
    """Generate unique payment number"""
    last_payment = FinancePayment.query.order_by(FinancePayment.id.desc()).first()
    if last_payment:
        last_num = int(last_payment.payment_number.split('-')[1])
        return f"PAY-{last_num + 1:06d}"
    return "PAY-000001"


def generate_receipt_number():
    """Generate unique receipt number"""
    last_receipt = Receipt.query.order_by(Receipt.id.desc()).first()
    if last_receipt:
        last_num = int(last_receipt.receipt_number.split('-')[1])
        return f"REC-{last_num + 1:06d}"
    return "REC-000001"


# ==================== DASHBOARD ====================
@finance_bp.route('/dashboard')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def dashboard(current_agency_id=None):
    """Finance Dashboard with period filters"""
    user_role = session.get('role')
    
    # Get filter parameters
    period = request.args.get('period', 'monthly')  # daily, weekly, monthly, yearly
    selected_date = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        filter_date = datetime.strptime(selected_date, '%Y-%m-%d')
    except:
        filter_date = datetime.now()
    
    # Calculate date range based on period
    if period == 'daily':
        start_date = filter_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
    elif period == 'weekly':
        start_date = filter_date - timedelta(days=filter_date.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=7)
    elif period == 'monthly':
        start_date = filter_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(filter_date.year, filter_date.month)[1]
        end_date = filter_date.replace(day=last_day, hour=23, minute=59, second=59)
    elif period == 'yearly':
        start_date = filter_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = filter_date.replace(month=12, day=31, hour=23, minute=59, second=59)
    else:
        start_date = filter_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day = calendar.monthrange(filter_date.year, filter_date.month)[1]
        end_date = filter_date.replace(day=last_day, hour=23, minute=59, second=59)
    
    # Build queries based on role
    payment_query = FinancePayment.query.filter(FinancePayment.status == 'confirmed')
    receipt_query = Receipt.query.filter(Receipt.status == 'confirmed')
    
    if user_role != 'super_admin':
        payment_query = payment_query.filter(FinancePayment.agency_id == current_agency_id)
        receipt_query = receipt_query.filter(Receipt.agency_id == current_agency_id)
    
    # Apply date filters
    payment_query = payment_query.filter(
        FinancePayment.payment_date >= start_date,
        FinancePayment.payment_date <= end_date
    )
    receipt_query = receipt_query.filter(
        Receipt.receipt_date >= start_date,
        Receipt.receipt_date <= end_date
    )
    
    # Calculate totals
    total_payment = db.session.query(func.sum(FinancePayment.amount)).filter(
        FinancePayment.id.in_([p.id for p in payment_query.all()])
    ).scalar() or Decimal('0')
    
    total_receipt = db.session.query(func.sum(Receipt.amount)).filter(
        Receipt.id.in_([r.id for r in receipt_query.all()])
    ).scalar() or Decimal('0')
    
    # Calculate pending amounts (all time, not filtered by period)
    pending_payment_query = FinancePayment.query.filter(FinancePayment.status == 'pending')
    pending_receipt_query = Receipt.query.filter(Receipt.status == 'pending')
    
    if user_role != 'super_admin':
        pending_payment_query = pending_payment_query.filter(FinancePayment.agency_id == current_agency_id)
        pending_receipt_query = pending_receipt_query.filter(Receipt.agency_id == current_agency_id)
    
    pending_payment = db.session.query(func.sum(FinancePayment.amount)).filter(
        FinancePayment.id.in_([p.id for p in pending_payment_query.all()])
    ).scalar() or Decimal('0')
    
    pending_receipt = db.session.query(func.sum(Receipt.amount)).filter(
        Receipt.id.in_([r.id for r in pending_receipt_query.all()])
    ).scalar() or Decimal('0')
    
    # Calculate cash on hand and cash in bank (all confirmed transactions)
    all_payments = FinancePayment.query.filter(FinancePayment.status == 'confirmed')
    all_receipts = Receipt.query.filter(Receipt.status == 'confirmed')
    
    if user_role != 'super_admin':
        all_payments = all_payments.filter(FinancePayment.agency_id == current_agency_id)
        all_receipts = all_receipts.filter(Receipt.agency_id == current_agency_id)
    
    # Cash on hand
    cash_receipts = db.session.query(func.sum(Receipt.amount)).filter(
        Receipt.id.in_([r.id for r in all_receipts.filter(Receipt.account_type == 'cash').all()])
    ).scalar() or Decimal('0')
    
    cash_payments = db.session.query(func.sum(FinancePayment.amount)).filter(
        FinancePayment.id.in_([p.id for p in all_payments.filter(FinancePayment.account_type == 'cash').all()])
    ).scalar() or Decimal('0')
    
    cash_on_hand = cash_receipts - cash_payments
    
    # Cash in bank
    bank_receipts = db.session.query(func.sum(Receipt.amount)).filter(
        Receipt.id.in_([r.id for r in all_receipts.filter(Receipt.account_type == 'bank').all()])
    ).scalar() or Decimal('0')
    
    bank_payments = db.session.query(func.sum(FinancePayment.amount)).filter(
        FinancePayment.id.in_([p.id for p in all_payments.filter(FinancePayment.account_type == 'bank').all()])
    ).scalar() or Decimal('0')
    
    cash_in_bank = bank_receipts - bank_payments
    
    return render_template(
        'finance/dashboard.html',
        total_payment=total_payment,
        total_receipt=total_receipt,
        pending_payment=pending_payment,
        pending_receipt=pending_receipt,
        cash_on_hand=cash_on_hand,
        cash_in_bank=cash_in_bank,
        period=period,
        selected_date=selected_date,
        start_date=start_date,
        end_date=end_date
    )


# ==================== PAYMENT ROUTES ====================
@finance_bp.route('/payments')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def list_payments(current_agency_id=None):
    """List all payments"""
    user_role = session.get('role')
    query = FinancePayment.query
    
    if user_role != 'super_admin':
        query = query.filter(FinancePayment.agency_id == current_agency_id)
    
    # Filters
    search = request.args.get('search')
    status_filter = request.args.get('status')
    
    if search:
        query = query.filter(or_(
            FinancePayment.payment_number.ilike(f'%{search}%'),
            FinancePayment.payee_name.ilike(f'%{search}%')
        ))
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    payments = query.order_by(FinancePayment.payment_date.desc()).all()
    
    return render_template(
        'finance/payment_list.html',
        payments=payments,
        search=search,
        status_filter=status_filter
    )


@finance_bp.route('/payments/create', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
@log_activity('create_payment')
def create_payment(current_agency_id=None):
    """Create new payment"""
    user_role = session.get('role')
    
    if request.method == 'POST':
        try:
            data = request.form
            
            # Create payment
            payment = FinancePayment(
                payment_number=generate_payment_number(),
                agency_id=current_agency_id if user_role != 'super_admin' else int(data.get('agency_id')),
                payment_date=datetime.strptime(data.get('payment_date'), '%Y-%m-%d'),
                payee_type=data.get('payee_type', 'other'),
                payee_name=data.get('payee_name'),
                amount=Decimal(data.get('amount')),
                mode_of_payment=data.get('mode_of_payment'),
                account_type=data.get('account_type', 'cash'),
                reference_number=data.get('reference_number'),
                notes=data.get('notes'),
                status=data.get('status', 'confirmed'),
                created_by=session.get('user_id')
            )
            
            # Handle payee_id if supplier is selected
            if data.get('payee_id'):
                payment.payee_id = int(data.get('payee_id'))
            
            db.session.add(payment)
            db.session.flush()
            
            # Handle linked purchase orders
            po_ids = request.form.getlist('po_ids[]')
            po_amounts = request.form.getlist('po_amounts[]')
            
            for po_id, po_amount in zip(po_ids, po_amounts):
                if po_id and po_amount:
                    link = PaymentPurchaseOrder(
                        payment_id=payment.id,
                        purchase_order_id=int(po_id),
                        amount=Decimal(po_amount)
                    )
                    db.session.add(link)
            
            db.session.commit()
            flash(f"Payment {payment.payment_number} created successfully!", "success")
            return redirect(url_for('finance.list_payments'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating payment: {str(e)}", "danger")
    
    # GET request - load form data
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
        suppliers = Supplier.query.filter_by(is_active=True).all()
        purchase_orders_query = PurchaseOrder.query.filter(
            PurchaseOrder.status.in_(['pending', 'approved', 'received'])
        ).all()
    else:
        agencies = None
        suppliers = Supplier.query.filter_by(agency_id=current_agency_id, is_active=True).all()
        purchase_orders_query = PurchaseOrder.query.filter(
            PurchaseOrder.agency_id == current_agency_id,
            PurchaseOrder.status.in_(['pending', 'approved', 'received'])
        ).all()

    purchase_orders = [
        {"id": po.id, "po_number": po.po_number, "total_amount": float(po.total_amount)}
        for po in purchase_orders_query
    ]
    
    return render_template(
        'finance/payment_form.html',
        agencies=agencies,
        suppliers=suppliers,
        purchase_orders=purchase_orders
    )


@finance_bp.route('/payments/<int:payment_id>')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def view_payment(payment_id, current_agency_id=None):
    """View payment details"""
    payment = FinancePayment.query.get_or_404(payment_id)
    user_role = session.get('role')
    
    # Permission check
    if user_role != 'super_admin' and payment.agency_id != current_agency_id:
        flash("You do not have permission to view this payment.", "danger")
        return redirect(url_for('finance.list_payments'))
    
    return render_template('finance/payment_view.html', payment=payment)


@finance_bp.route('/payments/<int:payment_id>/delete', methods=['POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('delete_payment')
def delete_payment(payment_id, current_agency_id=None):
    """Delete payment"""
    payment = FinancePayment.query.get_or_404(payment_id)
    user_role = session.get('role')
    
    # Permission check
    if user_role != 'super_admin' and payment.agency_id != current_agency_id:
        flash("You do not have permission to delete this payment.", "danger")
        return redirect(url_for('finance.list_payments'))
    
    try:
        payment_number = payment.payment_number
        db.session.delete(payment)
        db.session.commit()
        flash(f"Payment {payment_number} deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting payment: {str(e)}", "danger")
    
    return redirect(url_for('finance.list_payments'))


# ==================== RECEIPT ROUTES ====================
@finance_bp.route('/receipts')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def list_receipts(current_agency_id=None):
    """List all receipts"""
    user_role = session.get('role')
    query = Receipt.query
    
    if user_role != 'super_admin':
        query = query.filter(Receipt.agency_id == current_agency_id)
    
    # Filters
    search = request.args.get('search')
    status_filter = request.args.get('status')
    
    if search:
        query = query.filter(or_(
            Receipt.receipt_number.ilike(f'%{search}%'),
            Receipt.customer_name.ilike(f'%{search}%')
        ))
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    receipts = query.order_by(Receipt.receipt_date.desc()).all()
    
    return render_template(
        'finance/receipt_list.html',
        receipts=receipts,
        search=search,
        status_filter=status_filter
    )


@finance_bp.route('/receipts/create', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
@log_activity('create_receipt')
def create_receipt(current_agency_id=None):
    """Create new receipt"""
    user_role = session.get('role')
    
    if request.method == 'POST':
        try:
            data = request.form
            
            # Create receipt
            receipt = Receipt(
                receipt_number=generate_receipt_number(),
                agency_id=current_agency_id if user_role != 'super_admin' else int(data.get('agency_id')),
                receipt_date=datetime.strptime(data.get('receipt_date'), '%Y-%m-%d'),
                customer_name=data.get('customer_name'),
                amount=Decimal(data.get('amount')),
                mode_of_receipt=data.get('mode_of_receipt'),
                account_type=data.get('account_type', 'cash'),
                reference_number=data.get('reference_number'),
                notes=data.get('notes'),
                status=data.get('status', 'confirmed'),
                created_by=session.get('user_id')
            )
            
            # Handle customer_id if selected
            if data.get('customer_id'):
                receipt.customer_id = int(data.get('customer_id'))
            
            db.session.add(receipt)
            db.session.flush()
            
            # Handle linked sales orders
            so_ids = request.form.getlist('so_ids[]')
            so_amounts = request.form.getlist('so_amounts[]')
            
            for so_id, so_amount in zip(so_ids, so_amounts):
                if so_id and so_amount:
                    link = ReceiptSalesOrder(
                        receipt_id=receipt.id,
                        order_id=int(so_id),
                        amount=Decimal(so_amount)
                    )
                    db.session.add(link)
            
            db.session.commit()
            flash(f"Receipt {receipt.receipt_number} created successfully!", "success")
            return redirect(url_for('finance.list_receipts'))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating receipt: {str(e)}", "danger")
    
    # GET request - load form data
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
        customers = Customer.query.filter_by(is_active=True).all()
        sales_orders_query = Order.query.filter(
            Order.status.in_(['pending', 'confirmed', 'shipped'])
        ).all()
    else:
        agencies = None
        customers = Customer.query.join(Customer.location).filter(
            Customer.location.has(agency_id=current_agency_id),
            Customer.is_active == True
        ).all()
        sales_orders_query = Order.query.filter(
            Order.agency_id == current_agency_id,
            Order.status.in_(['pending', 'confirmed', 'shipped'])
        ).all()

    sales_orders = [
        {"id": so.id, "order_number": so.order_number, "total_amount": float(so.total_amount)}
        for so in sales_orders_query
    ]
    
    return render_template(
        'finance/receipt_form.html',
        agencies=agencies,
        customers=customers,
        sales_orders=sales_orders
    )


@finance_bp.route('/receipts/<int:receipt_id>')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def view_receipt(receipt_id, current_agency_id=None):
    """View receipt details"""
    receipt = Receipt.query.get_or_404(receipt_id)
    user_role = session.get('role')
    
    # Permission check
    if user_role != 'super_admin' and receipt.agency_id != current_agency_id:
        flash("You do not have permission to view this receipt.", "danger")
        return redirect(url_for('finance.list_receipts'))
    
    return render_template('finance/receipt_view.html', receipt=receipt)


@finance_bp.route('/receipts/<int:receipt_id>/delete', methods=['POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('delete_receipt')
def delete_receipt(receipt_id, current_agency_id=None):
    """Delete receipt"""
    receipt = Receipt.query.get_or_404(receipt_id)
    user_role = session.get('role')
    
    # Permission check
    if user_role != 'super_admin' and receipt.agency_id != current_agency_id:
        flash("You do not have permission to delete this receipt.", "danger")
        return redirect(url_for('finance.list_receipts'))
    
    try:
        receipt_number = receipt.receipt_number
        db.session.delete(receipt)
        db.session.commit()
        flash(f"Receipt {receipt_number} deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting receipt: {str(e)}", "danger")
    
    return redirect(url_for('finance.list_receipts'))


# ==================== API ENDPOINTS ====================
@finance_bp.route('/api/suppliers/<int:supplier_id>')
@login_required
def get_supplier_details(supplier_id):
    """Get supplier details for auto-fill"""
    supplier = Supplier.query.get_or_404(supplier_id)
    return jsonify({
        'id': supplier.id,
        'name': supplier.name,
        'email': supplier.email,
        'phone': supplier.phone
    })


@finance_bp.route('/api/customers/<int:customer_id>')
@login_required
def get_customer_details(customer_id):
    """Get customer details for auto-fill"""
    customer = Customer.query.get_or_404(customer_id)
    return jsonify({
        'id': customer.id,
        'name': customer.name,
        'email': customer.email,
        'phone': customer.phone
    })


# ==================== PAYMENT CONFIGURATION ====================
@finance_bp.route('/payment_configurations', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_manager'])
@log_activity('manage_payment_configuration')
def payment_configurations():
    """
    Create or update payment configurations for tenants (agencies).
    Super Admin and Agency Manager can define billing rules.
    """
    user_role = session.get('role')

    if request.method == 'POST':
        try:
            form_data = request.form
            agency_id = form_data.get('agency_id')
            billing_type = form_data.get('billing_type')

            # --- Permission Check ---
            if user_role == 'agency_manager':
                managed_agencies = Agency.query.filter_by(agency_manager_id=session.get('user_id')).all()
                managed_agency_ids = [str(a.id) for a in managed_agencies]
                if agency_id not in managed_agency_ids:
                    flash("You do not have permission to configure this agency.", "danger")
                    return redirect(url_for('finance.payment_configurations'))
            
            agency = Agency.query.get_or_404(agency_id)
            config = agency.payment_configuration or PaymentConfiguration(agency_id=agency.id)

            config.billing_type = billing_type

            if billing_type == 'fixed':
                config.fixed_period = form_data.get('fixed_period')
                config.fixed_value = Decimal(form_data.get('fixed_value'))
                config.currency_code = agency.country.currency_code if agency.country else 'USD'
                # Clear variable fields
                config.variable_type = None
            elif billing_type == 'variable':
                config.variable_type = form_data.get('variable_type')
                # Clear fixed fields
                config.fixed_period = None
                config.fixed_value = None
                config.currency_code = None
            
            db.session.add(config)
            db.session.commit()

            flash(f"Payment configuration for '{agency.name}' saved successfully!", "success")
            return redirect(url_for('finance.payment_configurations'))

        except (InvalidOperation, ValueError):
            db.session.rollback()
            flash("Invalid value provided. Please check the numbers and try again.", "danger")
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {str(e)}", "danger")

    # --- GET Request ---
    # Fetch agencies that can be configured
    if user_role == 'super_admin':
        agencies = Agency.query.options(db.joinedload(Agency.payment_configuration), db.joinedload(Agency.country)).filter_by(is_active=True).order_by(Agency.name).all()
    elif user_role == 'agency_manager':
        agencies = Agency.query.options(db.joinedload(Agency.payment_configuration), db.joinedload(Agency.country)).filter(
            Agency.agency_manager_id == session.get('user_id'),
            Agency.is_active == True
        ).order_by(Agency.name).all()
    else:
        agencies = []

    # Prepare data for the template
    configs = {agency.id: agency.payment_configuration for agency in agencies}

    return render_template(
        'finance/payment_configurations.html',
        agencies=agencies,
        configs=configs
    )