from flask import render_template, request, session, jsonify, redirect, url_for
from datetime import datetime, timedelta
from decimal import Decimal
from extensions import db
from models import (
    Order, Product, ProductAgency, Customer, Invoice, Payment, InventoryTransaction,
    User, Agency, Location
)
from reports import reports_bp
from auth.utils import login_required, permission_required
from sqlalchemy import func, and_, or_
import logging

@reports_bp.route('/dashboard')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def unified_dashboard(current_agency_id=None):
    """Unified reporting dashboard showing KPIs across all modules"""
    user_role = session.get('role')
    
    # Get date range (last 30 days by default)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Base queries based on role
    if user_role == 'super_admin':
        order_query = Order.query
        product_query = Product.query
        invoice_query = Invoice.query
        payment_query = Payment.query
        transaction_query = InventoryTransaction.query
    else:
        order_query = Order.query.filter_by(agency_id=current_agency_id)
        product_query = db.session.query(Product).join(ProductAgency, ProductAgency.product_id == Product.id)\
            .filter(ProductAgency.agency_id == current_agency_id)
        invoice_query = Invoice.query.filter_by(agency_id=current_agency_id)
        payment_query = Payment.query.join(Invoice).filter(Invoice.agency_id == current_agency_id)
        transaction_query = InventoryTransaction.query.join(Product).join(ProductAgency).filter(ProductAgency.agency_id == current_agency_id)
    
    # Sales Performance (30 days)
    period_orders = order_query.filter(
        Order.order_date >= start_date,
        Order.order_date <= end_date
    ).all()
    
    sales_stats = {
        'total_orders': len(period_orders),
        'total_revenue': sum(order.total_amount for order in period_orders),
        'avg_order_value': sum(order.total_amount for order in period_orders) / len(period_orders) if period_orders else 0,
        'completed_orders': len([o for o in period_orders if o.status == 'completed'])
    }
    
    # Billing Performance
    period_invoices = invoice_query.filter(
        Invoice.issue_date >= start_date,
        Invoice.issue_date <= end_date
    ).all()
    logging.info(invoice_query)
    billing_stats = {
        'total_invoices': len(period_invoices),
        'total_invoiced': sum(inv.total_amount for inv in period_invoices),
        'total_collected': sum(inv.total_amount for inv in period_invoices if inv.status == 'paid'),
        'collection_rate': (sum(inv.total_amount for inv in period_invoices if inv.status == 'paid') / 
                          sum(inv.total_amount for inv in period_invoices) * 100) if period_invoices else 0
    }
    
    # Calculate pending payments from invoices in the period
    pending_payment = sum(inv.total_amount for inv in period_invoices if inv.status != 'paid')
    # Placeholder values for other finance metrics
    total_receipt = 0
    pending_receipt = 0
    cash_on_hand = 0
    cash_in_bank = 0
    
    # Inventory Status (simplified - stock tracking removed)
    active_products = product_query.filter_by(is_active=True).all()
    inventory_stats = {
        'total_products': len(active_products),
        'total_inventory_value': 0,  # Stock tracking disabled
        'low_stock_items': 0,
        'out_of_stock_items': 0
    }
    
    # Top performing products (by sales volume)
    product_sales = {}
    for order in period_orders:
        for item in order.order_items:
            if item.product_id not in product_sales:
                product_sales[item.product_id] = {
                    'product': item.product,
                    'quantity_sold': 0,
                    'revenue': 0
                }
            product_sales[item.product_id]['quantity_sold'] += item.quantity
            product_sales[item.product_id]['revenue'] += item.total_price
    
    top_products = sorted(
        product_sales.values(),
        key=lambda x: x['revenue'],
        reverse=True
    )[:10]
    
    # Recent activity summary
    recent_orders = order_query.order_by(Order.order_date.desc()).limit(5).all()
    recent_payments = payment_query.order_by(Payment.payment_date.desc()).limit(5).all()

    # Calculate total payments for the period
    period_payments = payment_query.filter(
        Payment.payment_date >= start_date,
        Payment.payment_date <= end_date
    ).all()
    total_payment = sum(p.amount for p in period_payments)
    
    # Daily sales trend (last 7 days including today)
    daily_sales = []
    for i in range(6, -1, -1):
        day = end_date - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        day_orders = order_query.filter(
            Order.order_date >= day_start,
            Order.order_date <= day_end
        ).all()
        
        daily_sales.append({
            'date': day.strftime('%Y-%m-%d'),
            'day_name': day.strftime('%A'),
            'so_total': float(sum(order.total_amount for order in day_orders)),
            'po_total': 0,
            'so_count': len(day_orders),
            'po_count': 0
        })
    
    # Render the unified dashboard for all permitted roles.
    return render_template('finance/dashboard.html',
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
                         start_date=start_date,
                         end_date=end_date)

@reports_bp.route('/sales_analytics', endpoint='sales_analytics') # Old route, will redirect
def sales_analytics_redirect():
    """Redirects old sales analytics URL to the new unified dashboard."""
    return redirect(url_for('reports.unified_dashboard'))

@reports_bp.route('/accounting_report/<report_type>', endpoint='accounting_report')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def accounting_report(current_agency_id=None, report_type=None):
    """Handles detailed accounting reports like Sales, AR, and AP."""
    user_role = session.get('role')
    
    # Default to 'sales' if no report_type is specified
    # Get date range from query params
    period = request.args.get('period', '30')  # days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(period))
    
    # Base queries
    if user_role == 'super_admin':
        order_query = Order.query
    else:
        # Ensure agency_id is available for non-super_admin roles
        if not current_agency_id:
            # This can happen if the route is accessed directly without middleware context
            # A more robust solution would be to fetch it from the user session
            user = User.query.get(session.get('user_id'))
            current_agency_id = user.agency_id if user else None
        order_query = Order.query.filter_by(agency_id=current_agency_id)
    
    # Get orders for the period
    period_orders = order_query.filter(
        Order.order_date >= start_date,
        Order.order_date <= end_date
    ).all()

    # Handle different report types
    if report_type == 'ar':
        # Logic for AR Transaction Report
        # This is a placeholder; you would query AR-specific data here
        return render_template('reports/ar_report.html', period=period, start_date=start_date, end_date=end_date)
    elif report_type == 'ap':
        # Logic for AP Transaction Report
        # This is a placeholder; you would query AP-specific data here
        return render_template('reports/ap_report.html', period=period, start_date=start_date, end_date=end_date)
    
    # Default to sales analytics report
    # Sales by salesperson
    salesperson_sales = {}
    for order in period_orders:
        if order.salesperson:
            sp_id = order.salesperson.id
            if sp_id not in salesperson_sales:
                salesperson_sales[sp_id] = {
                    'name': order.salesperson.full_name,
                    'total_sales': 0,
                    'order_count': 0
                }
            salesperson_sales[sp_id]['total_sales'] += order.total_amount
            salesperson_sales[sp_id]['order_count'] += 1
    
    # Sales by location
    location_sales = {}
    for order in period_orders:
        if order.customer and order.customer.location:
            loc_id = order.customer.location.id
            if loc_id not in location_sales:
                location_sales[loc_id] = {
                    'name': order.customer.location.name,
                    'total_sales': 0,
                    'order_count': 0
                }
            location_sales[loc_id]['total_sales'] += order.total_amount
            location_sales[loc_id]['order_count'] += 1
    
    # Sales trends by day
    daily_trends = {}
    for order in period_orders:
        day = order.order_date.date()
        if day not in daily_trends:
            daily_trends[day] = {'sales': 0, 'orders': 0}
        daily_trends[day]['sales'] += order.total_amount
        daily_trends[day]['orders'] += 1
    
    # Convert to list and sort
    daily_data = [
        {
            'date': day.strftime('%Y-%m-%d'),
            'sales': float(data['sales']),
            'orders': data['orders']
        }
        for day, data in sorted(daily_trends.items())
    ]
    
    return render_template('reports/sales_analytics.html',
                         period=period,
                         total_sales=sum(order.total_amount for order in period_orders),
                         total_orders=len(period_orders),
                         salesperson_sales=list(salesperson_sales.values()),
                         location_sales=list(location_sales.values()),
                         daily_data=daily_data,
                         start_date=start_date.strftime('%Y-%m-%d'),
                         end_date=end_date.strftime('%Y-%m-%d'))

@reports_bp.route('/api/dashboard_data')
@reports_bp.route('/api/sales_trend_data') # More specific endpoint
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def sales_trend_api(current_agency_id=None):
    """API endpoint for sales trend chart"""
    user_role = session.get('role')
    chart_type = request.args.get('type', 'sales_trend')
    days = int(request.args.get('days', 30))
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    if user_role == 'super_admin':
        order_query = Order.query
        invoice_query = Invoice.query
    else:
        order_query = Order.query.filter_by(agency_id=current_agency_id)
        invoice_query = Invoice.query.filter_by(agency_id=current_agency_id)
    
    # Daily sales for the last N days
    daily_data = []
    for i in range(days):
        day = end_date - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        day_orders = order_query.filter(
            Order.order_date >= day_start,
            Order.order_date <= day_end
        ).all()
        
        daily_data.append({
            'date': day.strftime('%Y-%m-%d'),
            'sales': float(sum(order.total_amount for order in day_orders)),
            'orders': len(day_orders)
        })
    
    daily_data.reverse()
    return jsonify(daily_data)

@reports_bp.route('/api/collection_rate_data')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def collection_rate_api(current_agency_id=None):
    """API endpoint for collection rate chart"""
    user_role = session.get('role')
    
    end_date = datetime.now()
    
    if user_role == 'super_admin':
        invoice_query = Invoice.query
    else:
        invoice_query = Invoice.query.filter_by(agency_id=current_agency_id)

    monthly_data = []
    for i in range(6):  # Last 6 months
        month_start = (end_date.replace(day=1) - timedelta(days=30*i)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        month_invoices = invoice_query.filter(Invoice.issue_date >= month_start, Invoice.issue_date <= month_end).all()
        
        total_invoiced = sum(inv.total_amount for inv in month_invoices)
        total_collected = sum(inv.total_amount for inv in month_invoices if inv.status == 'paid')
        collection_rate = (total_collected / total_invoiced * 100) if total_invoiced > 0 else 0
        
        monthly_data.append({
            'month': month_start.strftime('%Y-%m'),
            'invoiced': float(total_invoiced),
            'collected': float(total_collected),
            'rate': round(collection_rate, 1)
        })
    
    monthly_data.reverse()
    return jsonify(monthly_data)

@reports_bp.route('/export/<report_type>')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def export_report(report_type, current_agency_id=None):
    """Export reports to CSV format"""
    user_role = session.get('role')
    
    # Get date range
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    
    try:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
    except ValueError:
        return "Invalid date format", 400
    
    if report_type == 'sales':
        if user_role == 'super_admin':
            orders = Order.query.filter(
                Order.order_date >= start_dt,
                Order.order_date <= end_dt
            ).all()
        else:
            orders = Order.query.filter(
                Order.agency_id == current_agency_id,
                Order.order_date >= start_dt,
                Order.order_date <= end_dt
            ).all()
        
        # Generate CSV content
        csv_content = "Order Number,Date,Customer,Salesperson,Total Amount,Status\n"
        for order in orders:
            order_date_str = order.order_date.strftime("%Y-%m-%d") if order.order_date else ""
            customer_name = order.customer.name if order.customer else "N/A"
            csv_content += f'"{order.order_number}","{order_date_str}","{customer_name}","{order.salesperson.full_name if order.salesperson else ""}","{order.total_amount}","{order.status}"\n'
        
        from flask import Response
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={"Content-disposition": f"attachment; filename=sales_report_{start_date}_to_{end_date}.csv"}
        )
    
    return "Report type not supported", 400