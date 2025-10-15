"""
Stock Forecasting & Profit Impact Analytics Routes
"""
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
from datetime import datetime, timedelta, date
from decimal import Decimal
import io
import pandas as pd
from extensions import db
from models import (
    StockForecast, ForecastAlertConfig, ForecastRefreshLog,
    Product, ProductAgency, Agency, Category, User
)
from forecasting import forecasting_bp
from auth.utils import login_required, permission_required
from utils.decorators import log_activity
from utils.forecast_service import forecast_service
from sqlalchemy import func, and_, or_, desc


@forecasting_bp.route('/dashboard')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def dashboard(current_agency_id=None):
    """
    Main forecasting dashboard showing demand predictions and alerts
    """
    user_role = session.get('role')
    
    # For agency managers, allow tenant selection
    selected_agency_id = current_agency_id
    if user_role == 'agency_manager':
        selected_agency_id = request.args.get('agency_id', type=int)
        if not selected_agency_id:
            # Show agency selection page
            agencies = Agency.query.filter_by(
                agency_manager_id=session.get('user_id'),
                is_active=True
            ).all()
            return render_template('forecasting/select_agency.html', agencies=agencies)
    
    # Get current week dates
    week_start, week_end = forecast_service.get_week_dates()
    
    # Base query for forecasts
    forecast_query = StockForecast.query.filter(
        StockForecast.week_start_date == week_start
    )
    
    if user_role != 'super_admin':
        forecast_query = forecast_query.filter(
            StockForecast.agency_id == selected_agency_id
        )
    
    # Get all forecasts for the current week
    forecasts = forecast_query.join(Product).order_by(
        desc(StockForecast.shortage_qty),
        desc(StockForecast.excess_qty)
    ).all()
    
    # Calculate summary statistics
    total_products = len(forecasts)
    shortage_count = sum(1 for f in forecasts if f.shortage_qty > 0)
    excess_count = sum(1 for f in forecasts if f.excess_qty > 0)
    total_shortage_qty = sum(f.shortage_qty for f in forecasts)
    total_excess_qty = sum(f.excess_qty for f in forecasts)
    total_profit_impact = sum(f.profit_impact for f in forecasts)
    total_opportunity_cost = sum(f.opportunity_cost for f in forecasts)
    total_holding_cost = sum(f.holding_cost for f in forecasts)
    
    # Get alerts (forecasts with alert_triggered = True)
    alerts = [f for f in forecasts if f.alert_triggered]
    
    # Get recent refresh logs
    refresh_log_query = ForecastRefreshLog.query
    
    if user_role != 'super_admin' and selected_agency_id:
        refresh_log_query = refresh_log_query.filter(
            ForecastRefreshLog.agency_id == selected_agency_id
        )
    
    refresh_log_query = refresh_log_query.order_by(
        desc(ForecastRefreshLog.started_at)
    ).limit(5)
    
    recent_refreshes = refresh_log_query.all()
    
    # Get last refresh time
    last_refresh = recent_refreshes[0] if recent_refreshes else None
    
    # Prepare data for charts
    # Top 10 products by shortage
    top_shortages = sorted(
        [f for f in forecasts if f.shortage_qty > 0],
        key=lambda x: x.shortage_qty,
        reverse=True
    )[:10]
    
    # Top 10 products by excess
    top_excess = sorted(
        [f for f in forecasts if f.excess_qty > 0],
        key=lambda x: x.excess_qty,
        reverse=True
    )[:10]
    
    # Get agencies for super admin
    agencies = None
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
    elif user_role == 'agency_manager':
        agencies = Agency.query.filter_by(
            agency_manager_id=session.get('user_id'),
            is_active=True
        ).all()
    
    return render_template(
        'forecasting/dashboard.html',
        forecasts=forecasts,
        alerts=alerts,
        total_products=total_products,
        shortage_count=shortage_count,
        excess_count=excess_count,
        total_shortage_qty=total_shortage_qty,
        total_excess_qty=total_excess_qty,
        total_profit_impact=total_profit_impact,
        total_opportunity_cost=total_opportunity_cost,
        total_holding_cost=total_holding_cost,
        top_shortages=top_shortages,
        top_excess=top_excess,
        week_start=week_start,
        week_end=week_end,
        last_refresh=last_refresh,
        recent_refreshes=recent_refreshes,
        agencies=agencies,
        selected_agency_id=selected_agency_id
    )


@forecasting_bp.route('/refresh', methods=['POST'])
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def refresh_forecasts(current_agency_id=None):
    """
    Manually trigger forecast refresh
    """
    user_role = session.get('role')
    user_id = session.get('user_id')
    
    # For agency managers, get selected agency
    selected_agency_id = current_agency_id
    if user_role == 'agency_manager':
        selected_agency_id = request.form.get('agency_id', type=int)
    
    # For super admin, allow refreshing all agencies or specific one
    if user_role == 'super_admin':
        selected_agency_id = request.form.get('agency_id', type=int)
    
    try:
        # Trigger refresh
        refresh_log = forecast_service.refresh_forecasts(
            agency_id=selected_agency_id,
            user_id=user_id,
            refresh_type='manual'
        )
        
        flash(
            f'Forecast refresh completed successfully! '
            f'Processed {refresh_log.products_processed} products, '
            f'triggered {refresh_log.alerts_triggered} alerts.',
            'success'
        )
    except Exception as e:
        flash(f'Error refreshing forecasts: {str(e)}', 'danger')
    
    return redirect(url_for('forecasting.dashboard'))


@forecasting_bp.route('/report')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def report(current_agency_id=None):
    """
    Detailed forecast report with filters and export options
    """
    user_role = session.get('role')
    
    # Get filter parameters
    selected_agency_id = current_agency_id
    if user_role in ['super_admin', 'agency_manager']:
        selected_agency_id = request.args.get('agency_id', type=int) or current_agency_id
    
    category_id = request.args.get('category_id', type=int)
    alert_only = request.args.get('alert_only', type=bool, default=False)
    sort_by = request.args.get('sort_by', default='shortage_desc')
    
    # Get date range
    week_start_str = request.args.get('week_start')
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
        week_end = week_start + timedelta(days=6)
    else:
        week_start, week_end = forecast_service.get_week_dates()
    
    # Build query
    forecast_query = StockForecast.query.filter(
        StockForecast.week_start_date == week_start
    ).join(Product)
    
    if user_role != 'super_admin':
        forecast_query = forecast_query.filter(
            StockForecast.agency_id == selected_agency_id
        )
    elif selected_agency_id:
        forecast_query = forecast_query.filter(
            StockForecast.agency_id == selected_agency_id
        )
    
    if category_id:
        forecast_query = forecast_query.filter(Product.category_id == category_id)
    
    if alert_only:
        forecast_query = forecast_query.filter(StockForecast.alert_triggered == True)
    
    # Apply sorting
    if sort_by == 'shortage_desc':
        forecast_query = forecast_query.order_by(desc(StockForecast.shortage_qty))
    elif sort_by == 'excess_desc':
        forecast_query = forecast_query.order_by(desc(StockForecast.excess_qty))
    elif sort_by == 'profit_impact':
        forecast_query = forecast_query.order_by(StockForecast.profit_impact)
    elif sort_by == 'product_name':
        forecast_query = forecast_query.order_by(Product.name)
    
    forecasts = forecast_query.all()
    
    # Get filter options
    categories = Category.query.filter_by(is_active=True).all()
    agencies = None
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
    elif user_role == 'agency_manager':
        agencies = Agency.query.filter_by(
            agency_manager_id=session.get('user_id'),
            is_active=True
        ).all()
    
    return render_template(
        'forecasting/report.html',
        forecasts=forecasts,
        categories=categories,
        agencies=agencies,
        selected_agency_id=selected_agency_id,
        selected_category_id=category_id,
        alert_only=alert_only,
        sort_by=sort_by,
        week_start=week_start,
        week_end=week_end
    )


@forecasting_bp.route('/export', endpoint='export')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def export_report(current_agency_id=None):
    """
    Export forecast report to Excel
    """
    user_role = session.get('role')
    
    # Get filter parameters (same as report)
    selected_agency_id = current_agency_id
    if user_role in ['super_admin', 'agency_manager']:
        selected_agency_id = request.args.get('agency_id', type=int) or current_agency_id
    
    category_id = request.args.get('category_id', type=int)
    alert_only = request.args.get('alert_only', type=bool, default=False)
    
    # Get date range
    week_start_str = request.args.get('week_start')
    if week_start_str:
        week_start = datetime.strptime(week_start_str, '%Y-%m-%d').date()
    else:
        week_start, _ = forecast_service.get_week_dates()
    
    # Build query (same as report)
    forecast_query = StockForecast.query.filter(
        StockForecast.week_start_date == week_start
    ).join(Product).join(Agency)
    
    if user_role != 'super_admin':
        forecast_query = forecast_query.filter(
            StockForecast.agency_id == selected_agency_id
        )
    elif selected_agency_id:
        forecast_query = forecast_query.filter(
            StockForecast.agency_id == selected_agency_id
        )
    
    if category_id:
        forecast_query = forecast_query.filter(Product.category_id == category_id)
    
    if alert_only:
        forecast_query = forecast_query.filter(StockForecast.alert_triggered == True)
    
    forecasts = forecast_query.all()
    
    # Prepare data for Excel
    data = []
    for f in forecasts:
        data.append({
            'Agency': f.agency.name,
            'Product': f.product.name,
            'SKU': f.product.sku,
            'Category': f.product.category_ref.name if f.product.category_ref else '',
            'Week Start': f.week_start_date.strftime('%Y-%m-%d'),
            'Week End': f.week_end_date.strftime('%Y-%m-%d'),
            'Forecast Demand': float(f.forecast_qty),
            'Current Stock': float(f.actual_stock),
            'Shortage': float(f.shortage_qty),
            'Excess': float(f.excess_qty),
            'Profit Impact': float(f.profit_impact),
            'Holding Cost': float(f.holding_cost),
            'Opportunity Cost': float(f.opportunity_cost),
            'Alert Triggered': 'Yes' if f.alert_triggered else 'No',
            'Forecast Accuracy': float(f.forecast_accuracy) if f.forecast_accuracy else ''
        })
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Forecast Report', index=False)
    
    output.seek(0)
    
    # Generate filename
    filename = f'forecast_report_{week_start.strftime("%Y%m%d")}.xlsx'
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )


@forecasting_bp.route('/alert-config', methods=['GET', 'POST'])
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager'])
def alert_config(current_agency_id=None):
    """
    Configure alert thresholds
    """
    user_role = session.get('role')
    
    # Get agency context
    selected_agency_id = current_agency_id
    if user_role in ['super_admin', 'agency_manager']:
        selected_agency_id = request.args.get('agency_id', type=int) or current_agency_id
    
    if not selected_agency_id:
        flash('Please select an agency', 'warning')
        return redirect(url_for('forecasting.dashboard'))
    
    if request.method == 'POST':
        try:
            category_id = request.form.get('category_id', type=int) or None
            
            # Check if config exists
            config = ForecastAlertConfig.query.filter_by(
                agency_id=selected_agency_id,
                category_id=category_id
            ).first()
            
            if not config:
                config = ForecastAlertConfig(
                    agency_id=selected_agency_id,
                    category_id=category_id
                )
                db.session.add(config)
            
            # Update config
            config.shortage_threshold_qty = Decimal(request.form.get('shortage_threshold_qty', 10))
            config.shortage_threshold_percentage = Decimal(request.form.get('shortage_threshold_percentage', 20))
            config.excess_threshold_qty = Decimal(request.form.get('excess_threshold_qty', 50))
            config.excess_threshold_percentage = Decimal(request.form.get('excess_threshold_percentage', 30))
            config.email_alerts_enabled = request.form.get('email_alerts_enabled') == 'on'
            config.dashboard_alerts_enabled = request.form.get('dashboard_alerts_enabled') == 'on'
            config.alert_recipients = request.form.get('alert_recipients', '').strip()
            config.is_active = request.form.get('is_active') == 'on'
            
            db.session.commit()
            
            flash('Alert configuration saved successfully!', 'success')
            return redirect(url_for('forecasting.alert_config', agency_id=selected_agency_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving configuration: {str(e)}', 'danger')
    
    # Get existing configs
    configs = ForecastAlertConfig.query.filter_by(
        agency_id=selected_agency_id
    ).all()
    
    # Get categories for dropdown
    categories = Category.query.filter_by(is_active=True).all()
    
    # Get agencies for selection
    agencies = None
    if user_role == 'super_admin':
        agencies = Agency.query.filter_by(is_active=True).all()
    elif user_role == 'agency_manager':
        agencies = Agency.query.filter_by(
            agency_manager_id=session.get('user_id'),
            is_active=True
        ).all()
    
    return render_template(
        'forecasting/alert_config.html',
        configs=configs,
        categories=categories,
        agencies=agencies,
        selected_agency_id=selected_agency_id
    )


@forecasting_bp.route('/api/forecast-data')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def api_forecast_data(current_agency_id=None):
    """
    API endpoint for forecast chart data
    """
    user_role = session.get('role')
    
    selected_agency_id = current_agency_id
    if user_role in ['super_admin', 'agency_manager']:
        selected_agency_id = request.args.get('agency_id', type=int) or current_agency_id
    
    # Get current week
    week_start, week_end = forecast_service.get_week_dates()
    
    # Query forecasts
    forecast_query = StockForecast.query.filter(
        StockForecast.week_start_date == week_start
    ).join(Product)
    
    if user_role != 'super_admin':
        forecast_query = forecast_query.filter(
            StockForecast.agency_id == selected_agency_id
        )
    elif selected_agency_id:
        forecast_query = forecast_query.filter(
            StockForecast.agency_id == selected_agency_id
        )
    
    forecasts = forecast_query.limit(20).all()
    
    # Prepare chart data
    data = {
        'labels': [f.product.name[:20] for f in forecasts],
        'forecast': [float(f.forecast_qty) for f in forecasts],
        'actual_stock': [float(f.actual_stock) for f in forecasts],
        'shortage': [float(f.shortage_qty) for f in forecasts],
        'excess': [float(f.excess_qty) for f in forecasts]
    }
    
    return jsonify(data)


@forecasting_bp.route('/api/profit-impact-data')
@permission_required(roles=['super_admin', 'agency_admin', 'agency_manager', 'staff'])
def api_profit_impact_data(current_agency_id=None):
    """
    API endpoint for profit impact chart data
    """
    user_role = session.get('role')
    
    selected_agency_id = current_agency_id
    if user_role in ['super_admin', 'agency_manager']:
        selected_agency_id = request.args.get('agency_id', type=int) or current_agency_id
    
    # Get current week
    week_start, week_end = forecast_service.get_week_dates()
    
    # Query forecasts with significant profit impact
    forecast_query = StockForecast.query.filter(
        StockForecast.week_start_date == week_start
    ).join(Product).order_by(StockForecast.profit_impact)
    
    if user_role != 'super_admin':
        forecast_query = forecast_query.filter(
            StockForecast.agency_id == selected_agency_id
        )
    elif selected_agency_id:
        forecast_query = forecast_query.filter(
            StockForecast.agency_id == selected_agency_id
        )
    
    forecasts = forecast_query.limit(15).all()
    
    # Prepare chart data
    data = {
        'labels': [f.product.name[:20] for f in forecasts],
        'profit_impact': [float(f.profit_impact) for f in forecasts],
        'holding_cost': [float(f.holding_cost) for f in forecasts],
        'opportunity_cost': [float(f.opportunity_cost) for f in forecasts]
    }
    
    return jsonify(data)