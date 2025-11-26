from flask import render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import or_, func, and_, extract
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
import calendar
import logging

from extensions import db
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
    
    # Build base queries based on role
    order_query = Order.query
    payment_query = FinancePayment.query.filter(FinancePayment.status == 'confirmed')
    receipt_query = Receipt.query.filter(Receipt.status == 'confirmed')
    
    if user_role != 'super_admin':
        order_query = order_query.filter(Order.agency_id == current_agency_id)
        payment_query = payment_query.filter(FinancePayment.agency_id == current_agency_id)
        receipt_query = receipt_query.filter(Receipt.agency_id == current_agency_id)
    
    # Apply date filters for transactions
    period_payment_query = payment_query.filter(
        FinancePayment.payment_date >= start_date,
        FinancePayment.payment_date <= end_date
    )
    period_receipt_query = receipt_query.filter(
        Receipt.receipt_date >= start_date,
        Receipt.receipt_date <= end_date
    )
    
    # Calculate totals for the period
    total_payment = db.session.query(func.sum(FinancePayment.amount)).filter(
        FinancePayment.id.in_([p.id for p in period_payment_query.all()])
    ).scalar() or Decimal('0')
    
    total_receipt = db.session.query(func.sum(Receipt.amount)).filter(
        Receipt.id.in_([r.id for r in period_receipt_query.all()])
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
    
    # Sales Performance (last 30 days for stats)
    period_orders = order_query.filter(
        Order.order_date >= start_date,
        Order.order_date <= end_date
    ).all()
    logging.info(f"Period Orders: {(period_orders)}")
    sales_stats = {
        'total_orders': len(period_orders),
        'total_revenue': sum(Decimal(str(order.total_amount)) if order.total_amount else Decimal('0') for order in period_orders),
        'avg_order_value': sum(Decimal(str(order.total_amount)) if order.total_amount else Decimal('0') for order in period_orders) / len(period_orders) if period_orders else Decimal('0'),
        'completed_orders': len([o for o in period_orders if o.status.lower() == 'completed'])
    }
    
    # Billing Performance
    billing_stats = {
        'total_invoices': 0,
        'total_invoiced': Decimal('0'),
        'total_collected': total_receipt,
        'collection_rate': 0
    }
    
    # Correctly calculate active products
    from models import Product, ProductAgency
    product_base_query = Product.query.filter(Product.is_active == True)
    if user_role != 'super_admin':
        product_base_query = product_base_query.join(ProductAgency).filter(ProductAgency.agency_id == current_agency_id)
    
    # Inventory Stats
    inventory_stats = {
        'total_products': product_base_query.count(),
        'total_inventory_value': 0,
        'low_stock_items': 0,
        'out_of_stock_items': 0
    }
    
    # Top performing products (by sales volume)
    product_sales = {}
    # Use a wider range for top products to be more meaningful
    top_products_end_date = datetime.now()
    top_products_start_date = top_products_end_date - timedelta(days=30)
    top_products_orders = order_query.filter(
        Order.order_date >= top_products_start_date, Order.order_date <= top_products_end_date
    ).all()
    for order in top_products_orders:
        for item in order.order_items:
            if item.product_id not in product_sales:
                product_sales[item.product_id] = {
                    'product_name': item.product_name,
                    'product': item.product,
                    'quantity_sold': 0,
                    'revenue': 0
                }
            product_sales[item.product_id]['quantity_sold'] += item.quantity
            product_sales[item.product_id]['revenue'] += Decimal(str(item.total_price)) if item.total_price else Decimal('0')
    
    top_products = sorted(
        product_sales.values(),
        key=lambda x: float(x['revenue']),
        reverse=True
    )[:10]
    
    # Recent activity summary
    recent_orders = order_query.order_by(Order.order_date.desc()).limit(5).all()
    recent_payments = []
    
    # Daily sales trend (last 7 days) - Sales Orders and Purchase Orders
    po_query = PurchaseOrder.query
    stats_end_date = datetime.now() # for daily sales trend

    if user_role != 'super_admin':
        po_query = po_query.filter(PurchaseOrder.agency_id == current_agency_id)
    
    daily_sales = []
    for i in range(6, -1, -1):
        day = stats_end_date - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        day_so = order_query.filter(
            Order.order_date >= day_start,
            Order.order_date <= day_end
        ).all()
        
        day_po = po_query.filter(
            PurchaseOrder.created_at >= day_start,
            PurchaseOrder.created_at <= day_end
        ).all()
        
        total_so = sum(Decimal(str(order.total_amount)) if order.total_amount else Decimal('0') for order in day_so)
        total_po = sum(Decimal(str(po.total_amount)) if po.total_amount else Decimal('0') for po in day_po)
        
        daily_sales.append({
            'date': day.strftime('%Y-%m-%d'),
            'day_name': day.strftime('%A'),
            'so_total': float(total_so),
            'po_total': float(total_po),
            'so_count': len(day_so),
            'po_count': len(day_po)
        })
    
    return render_template(
        'finance/dashboard.html',
        sales_stats=sales_stats,
        billing_stats=billing_stats,
        inventory_stats=inventory_stats,
        top_products=top_products,
        recent_orders=recent_orders,
        recent_payments=recent_payments,
        pending_payment=pending_payment,
        total_receipt=total_receipt,
        pending_receipt=pending_receipt,
        cash_on_hand=cash_on_hand,
        cash_in_bank=cash_in_bank,
        total_payment=total_payment,
        daily_sales=daily_sales,
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


@finance_bp.route('/payments/<int:payment_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('edit_payment')
def edit_payment(payment_id, current_agency_id=None):
    """Edit existing payment"""
    payment = FinancePayment.query.get_or_404(payment_id)
    user_role = session.get('role')
    
    # Permission check
    if user_role != 'super_admin' and payment.agency_id != current_agency_id:
        flash("You do not have permission to edit this payment.", "danger")
        return redirect(url_for('finance.list_payments'))
    
    # Only allow editing of pending payments
    if payment.status != 'pending':
        flash("Only pending payments can be edited.", "warning")
        return redirect(url_for('finance.view_payment', payment_id=payment_id))
    
    if request.method == 'POST':
        try:
            data = request.form
            
            # Update payment fields
            payment.payment_date = datetime.strptime(data.get('payment_date'), '%Y-%m-%d')
            payment.payee_type = data.get('payee_type', 'other')
            payment.payee_name = data.get('payee_name')
            payment.amount = Decimal(data.get('amount'))
            payment.mode_of_payment = data.get('mode_of_payment')
            payment.account_type = data.get('account_type', 'cash')
            payment.reference_number = data.get('reference_number')
            payment.notes = data.get('notes')
            payment.status = data.get('status', 'pending')
            
            if data.get('payee_id'):
                payment.payee_id = int(data.get('payee_id'))
            
            # Update linked purchase orders
            payment.purchase_orders.clear()
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
            flash(f"Payment {payment.payment_number} updated successfully!", "success")
            return redirect(url_for('finance.view_payment', payment_id=payment_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating payment: {str(e)}", "danger")
    
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
    
    # Get linked purchase orders for this payment
    linked_pos = [
        {"id": po_link.purchase_order_id, "po_number": po_link.purchase_order_ref.po_number, "amount": float(po_link.amount)}
        for po_link in payment.purchase_orders
    ]
    
    return render_template(
        'finance/payment_form.html',
        payment=payment,
        agencies=agencies,
        suppliers=suppliers,
        purchase_orders=purchase_orders,
        linked_pos=linked_pos,
        is_edit=True
    )


@finance_bp.route('/payments/<int:payment_id>/delete', methods=['POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('delete_payment')
def delete_payment(payment_id, current_agency_id=None):
    """Delete payment (only pending payments)"""
    payment = FinancePayment.query.get_or_404(payment_id)
    user_role = session.get('role')
    
    # Permission check
    if user_role != 'super_admin' and payment.agency_id != current_agency_id:
        flash("You do not have permission to delete this payment.", "danger")
        return redirect(url_for('finance.list_payments'))
    
    # Only allow deletion of pending payments
    if payment.status != 'pending':
        flash(f"Cannot delete {payment.status} payments. Only pending payments can be deleted.", "warning")
        return redirect(url_for('finance.view_payment', payment_id=payment_id))
    
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


@finance_bp.route('/receipts/<int:receipt_id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('edit_receipt')
def edit_receipt(receipt_id, current_agency_id=None):
    """Edit existing receipt"""
    receipt = Receipt.query.get_or_404(receipt_id)
    user_role = session.get('role')
    
    # Permission check
    if user_role != 'super_admin' and receipt.agency_id != current_agency_id:
        flash("You do not have permission to edit this receipt.", "danger")
        return redirect(url_for('finance.list_receipts'))
    
    # Only allow editing of pending receipts
    if receipt.status != 'pending':
        flash("Only pending receipts can be edited.", "warning")
        return redirect(url_for('finance.view_receipt', receipt_id=receipt_id))
    
    if request.method == 'POST':
        try:
            data = request.form
            
            # Update receipt fields
            receipt.receipt_date = datetime.strptime(data.get('receipt_date'), '%Y-%m-%d')
            receipt.customer_name = data.get('customer_name')
            receipt.amount = Decimal(data.get('amount'))
            receipt.mode_of_receipt = data.get('mode_of_receipt')
            receipt.account_type = data.get('account_type', 'cash')
            receipt.reference_number = data.get('reference_number')
            receipt.notes = data.get('notes')
            receipt.status = data.get('status', 'pending')
            
            if data.get('customer_id'):
                receipt.customer_id = int(data.get('customer_id'))
            
            # Update linked sales orders
            receipt.sales_orders.clear()
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
            flash(f"Receipt {receipt.receipt_number} updated successfully!", "success")
            return redirect(url_for('finance.view_receipt', receipt_id=receipt_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating receipt: {str(e)}", "danger")
    
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
    
    # Get linked sales orders for this receipt
    linked_sos = [
        {"id": so_link.order_id, "order_number": so_link.order_ref.order_number, "amount": float(so_link.amount)}
        for so_link in receipt.sales_orders
    ]
    
    return render_template(
        'finance/receipt_form.html',
        receipt=receipt,
        agencies=agencies,
        customers=customers,
        sales_orders=sales_orders,
        linked_sos=linked_sos,
        is_edit=True
    )


@finance_bp.route('/receipts/<int:receipt_id>/delete', methods=['POST'])
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
@log_activity('delete_receipt')
def delete_receipt(receipt_id, current_agency_id=None):
    """Delete receipt (only pending receipts)"""
    receipt = Receipt.query.get_or_404(receipt_id)
    user_role = session.get('role')
    
    # Permission check
    if user_role != 'super_admin' and receipt.agency_id != current_agency_id:
        flash("You do not have permission to delete this receipt.", "danger")
        return redirect(url_for('finance.list_receipts'))
    
    # Only allow deletion of pending receipts
    if receipt.status != 'pending':
        flash(f"Cannot delete {receipt.status} receipts. Only pending receipts can be deleted.", "warning")
        return redirect(url_for('finance.view_receipt', receipt_id=receipt_id))
    
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
@permission_required(roles=['super_admin', 'agency_manager', 'agency_admin'])
@log_activity('manage_payment_configuration')
def payment_configurations(current_agency_id=None):
    """
    Create or update payment configurations for tenants (agencies).
    Super Admin and Agency Manager can define billing rules.
    Agency Admin can configure their own agency's payment settings.
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
            elif user_role == 'agency_admin':
                user = User.query.get(session.get('user_id'))
                if str(user.agency_id) != agency_id:
                    flash("You can only configure your own agency's payment settings.", "danger")
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
        agencies = Agency.query.options(db.joinedload(Agency.payment_configuration)).filter_by(is_active=True).order_by(Agency.name).all()
    elif user_role == 'agency_manager':
        agencies = Agency.query.options(db.joinedload(Agency.payment_configuration)).filter(
            Agency.agency_manager_id == session.get('user_id'),
            Agency.is_active == True
        ).order_by(Agency.name).all()
    elif user_role == 'agency_admin':
        user = User.query.get(session.get('user_id'))
        if user.agency_id:
            agencies = Agency.query.options(db.joinedload(Agency.payment_configuration)).filter_by(id=user.agency_id).all()
        else:
            agencies = []
    else:
        agencies = []

    # Prepare data for the template
    configs = {agency.id: agency.payment_configuration for agency in agencies}

    return render_template(
        'finance/payment_configurations.html',
        agencies=agencies,
        configs=configs
    )


# ==================== AR/AP AGING REPORTS ====================
@finance_bp.route('/ar_aging')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def ar_aging_report(current_agency_id=None):
    """Accounts Receivable Aging Report - Track customer outstanding invoices"""
    user_role = session.get('role')
    
    # Base query for orders (sales orders)
    orders_query = Order.query.filter(Order.status.in_(['pending', 'confirmed', 'delivered']))
    
    if user_role != 'super_admin':
        orders_query = orders_query.filter(Order.agency_id == current_agency_id)
    
    # Get all orders with their receipt allocations
    orders = orders_query.all()
    
    # Calculate aging buckets
    today = datetime.utcnow()
    aging_data = []
    
    for order in orders:
        # Calculate total received amount for this order
        total_received = sum(
            receipt_link.amount 
            for receipt_link in order.receipt_links 
            if receipt_link.receipt.status == 'confirmed'
        )
        
        # Calculate outstanding amount
        outstanding = float(order.total_amount or 0) - float(total_received or 0)
        
        if outstanding > 0.01:  # Only include if there's outstanding amount
            # Calculate days overdue based on order date
            days_overdue = (today - order.order_date).days if order.order_date else 0
            
            # Determine aging bucket
            if days_overdue <= 30:
                bucket = 'current'
            elif days_overdue <= 60:
                bucket = '31-60'
            elif days_overdue <= 90:
                bucket = '61-90'
            else:
                bucket = '90+'
            
            aging_data.append({
                'order_number': order.order_number,
                'customer_name': order.customer.name if order.customer else 'N/A',
                'order_date': order.order_date,
                'total_amount': float(order.total_amount or 0),
                'received_amount': float(total_received or 0),
                'outstanding': outstanding,
                'days_overdue': days_overdue,
                'bucket': bucket,
                'agency_name': order.agency.name if order.agency else 'N/A'
            })
    
    # Calculate summary by bucket
    summary = {
        'current': sum(item['outstanding'] for item in aging_data if item['bucket'] == 'current'),
        '31-60': sum(item['outstanding'] for item in aging_data if item['bucket'] == '31-60'),
        '61-90': sum(item['outstanding'] for item in aging_data if item['bucket'] == '61-90'),
        '90+': sum(item['outstanding'] for item in aging_data if item['bucket'] == '90+'),
    }
    summary['total'] = sum(summary.values())
    
    # Sort by days overdue (descending)
    aging_data.sort(key=lambda x: x['days_overdue'], reverse=True)
    
    return render_template(
        'finance/ar_aging.html',
        aging_data=aging_data,
        summary=summary,
        report_date=today
    )


@finance_bp.route('/ap_aging')
@login_required
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def ap_aging_report(current_agency_id=None):
    """Accounts Payable Aging Report - Track supplier outstanding bills"""
    user_role = session.get('role')
    
    # Base query for purchase orders
    po_query = PurchaseOrder.query.filter(PurchaseOrder.status.in_(['pending', 'confirmed', 'received']))
    
    if user_role != 'super_admin':
        po_query = po_query.filter(PurchaseOrder.agency_id == current_agency_id)
    
    # Get all purchase orders with their payment allocations
    purchase_orders = po_query.all()
    
    # Calculate aging buckets
    today = datetime.utcnow()
    aging_data = []
    
    for po in purchase_orders:
        # Calculate total paid amount for this PO
        total_paid = sum(
            payment_link.amount 
            for payment_link in po.finance_payment_links 
            if payment_link.finance_payment.status == 'confirmed'
        )
        
        # Calculate outstanding amount
        outstanding = float(po.total_amount or 0) - float(total_paid or 0)
        
        if outstanding > 0.01:  # Only include if there's outstanding amount
            # Calculate days overdue based on PO date
            days_overdue = (today - po.order_date).days if po.order_date else 0
            
            # Determine aging bucket
            if days_overdue <= 30:
                bucket = 'current'
            elif days_overdue <= 60:
                bucket = '31-60'
            elif days_overdue <= 90:
                bucket = '61-90'
            else:
                bucket = '90+'
            
            aging_data.append({
                'po_number': po.po_number,
                'supplier_name': po.supplier.name if po.supplier else 'N/A',
                'order_date': po.order_date,
                'total_amount': float(po.total_amount or 0),
                'paid_amount': float(total_paid or 0),
                'outstanding': outstanding,
                'days_overdue': days_overdue,
                'bucket': bucket,
                'agency_name': po.agency.name if po.agency else 'N/A'
            })
    
    # Calculate summary by bucket
    summary = {
        'current': sum(item['outstanding'] for item in aging_data if item['bucket'] == 'current'),
        '31-60': sum(item['outstanding'] for item in aging_data if item['bucket'] == '31-60'),
        '61-90': sum(item['outstanding'] for item in aging_data if item['bucket'] == '61-90'),
        '90+': sum(item['outstanding'] for item in aging_data if item['bucket'] == '90+'),
    }
    summary['total'] = sum(summary.values())
    
    # Sort by days overdue (descending)
    aging_data.sort(key=lambda x: x['days_overdue'], reverse=True)
    
    return render_template(
        'finance/ap_aging.html',
        aging_data=aging_data,
        summary=summary,
        report_date=today
    )