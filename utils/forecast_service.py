"""
Stock Forecasting Service
Handles demand prediction, shortage alerts, and profit impact analysis
"""
import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from sqlalchemy import func, and_, or_
from extensions import db
from models import (
    StockForecast, ForecastAlertConfig, ForecastRefreshLog,
    Product, ProductAgency, Order, OrderItem, InventoryTransaction,
    Agency, Category, User
)
from utils.email_service import email_service

logger = logging.getLogger(__name__)


class ForecastService:
    """Service for stock forecasting and analytics"""
    
    # Constants for profit impact calculation
    HOLDING_COST_PERCENTAGE = Decimal('0.02')  # 2% of product cost per week
    OPPORTUNITY_COST_MULTIPLIER = Decimal('1.0')  # 100% of potential profit lost
    
    def __init__(self):
        self.logger = logger
    
    def get_week_dates(self, target_date: date = None) -> Tuple[date, date]:
        """
        Get the start and end dates for a week (Monday to Sunday)
        
        Args:
            target_date: Date to get week for (defaults to today)
            
        Returns:
            Tuple of (week_start_date, week_end_date)
        """
        if target_date is None:
            target_date = date.today()
        
        # Get Monday of the week
        week_start = target_date - timedelta(days=target_date.weekday())
        # Get Sunday of the week
        week_end = week_start + timedelta(days=6)
        
        return week_start, week_end
    
    def calculate_current_stock(self, product_id: int, agency_id: int) -> Decimal:
        """
        Calculate current stock level for a product at an agency
        
        Args:
            product_id: Product ID
            agency_id: Agency ID
            
        Returns:
            Current stock quantity
        """
        # Sum all inventory transactions for this product and agency
        stock_result = db.session.query(
            func.sum(InventoryTransaction.quantity_change)
        ).filter(
            InventoryTransaction.product_id == product_id,
            InventoryTransaction.agency_id == agency_id
        ).scalar()
        
        return Decimal(stock_result or 0)
    
    def calculate_weekly_demand(self, product_id: int, agency_id: int, weeks_history: int = 4) -> Decimal:
        """
        Calculate average weekly demand based on historical sales
        
        Args:
            product_id: Product ID
            agency_id: Agency ID
            weeks_history: Number of weeks to look back (default: 4)
            
        Returns:
            Average weekly demand quantity
        """
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(weeks=weeks_history)
        
        # Query sales from orders
        total_sales = db.session.query(
            func.sum(OrderItem.quantity)
        ).join(
            Order, OrderItem.order_id == Order.id
        ).filter(
            OrderItem.product_id == product_id,
            Order.agency_id == agency_id,
            Order.order_date >= start_date,
            Order.order_date <= end_date,
            Order.status.in_(['confirmed', 'shipped', 'delivered', 'completed'])
        ).scalar()
        
        total_qty = Decimal(total_sales or 0)
        
        # Calculate average per week
        if weeks_history > 0:
            avg_weekly = total_qty / Decimal(weeks_history)
        else:
            avg_weekly = Decimal(0)
        
        return avg_weekly
    
    def calculate_profit_impact(
        self,
        product: Product,
        product_agency: ProductAgency,
        shortage_qty: Decimal,
        excess_qty: Decimal
    ) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate profit impact of shortage or excess inventory
        
        Args:
            product: Product instance
            product_agency: ProductAgency instance
            shortage_qty: Shortage quantity
            excess_qty: Excess quantity
            
        Returns:
            Tuple of (total_profit_impact, holding_cost, opportunity_cost)
        """
        holding_cost = Decimal(0)
        opportunity_cost = Decimal(0)
        
        # Get product costs
        buy_price = product_agency.buy_price or product.buy_price or Decimal(0)
        sell_price = product_agency.sell_price or product.sell_price or Decimal(0)
        margin = sell_price - buy_price
        
        # Calculate holding cost for excess inventory
        if excess_qty > 0:
            holding_cost = excess_qty * buy_price * self.HOLDING_COST_PERCENTAGE
        
        # Calculate opportunity cost for shortage (lost sales)
        if shortage_qty > 0:
            opportunity_cost = shortage_qty * margin * self.OPPORTUNITY_COST_MULTIPLIER
        
        # Total profit impact (negative for loss, positive for potential gain)
        # Shortage causes negative impact, excess causes negative impact
        total_impact = -(holding_cost + opportunity_cost)
        
        return total_impact, holding_cost, opportunity_cost
    
    def generate_forecast_for_product(
        self,
        product_id: int,
        agency_id: int,
        week_start_date: date,
        week_end_date: date
    ) -> Optional[StockForecast]:
        """
        Generate forecast for a single product
        
        Args:
            product_id: Product ID
            agency_id: Agency ID
            week_start_date: Start date of forecast week
            week_end_date: End date of forecast week
            
        Returns:
            StockForecast instance or None if error
        """
        try:
            # Get product and agency mapping
            product = Product.query.get(product_id)
            product_agency = ProductAgency.query.filter_by(
                product_id=product_id,
                agency_id=agency_id,
                is_active=True
            ).first()
            
            if not product or not product_agency:
                self.logger.warning(f"Product {product_id} not found or not mapped to agency {agency_id}")
                return None
            
            # Calculate forecast demand
            forecast_qty = self.calculate_weekly_demand(product_id, agency_id)
            
            # Calculate current stock
            actual_stock = self.calculate_current_stock(product_id, agency_id)
            
            # Calculate shortage or excess
            shortage_qty = Decimal(0)
            excess_qty = Decimal(0)
            
            if forecast_qty > actual_stock:
                shortage_qty = forecast_qty - actual_stock
            elif actual_stock > forecast_qty:
                excess_qty = actual_stock - forecast_qty
            
            # Calculate profit impact
            profit_impact, holding_cost, opportunity_cost = self.calculate_profit_impact(
                product, product_agency, shortage_qty, excess_qty
            )
            
            # Check if forecast already exists
            existing_forecast = StockForecast.query.filter_by(
                product_id=product_id,
                agency_id=agency_id,
                week_start_date=week_start_date
            ).first()
            
            if existing_forecast:
                # Update existing forecast
                existing_forecast.week_end_date = week_end_date
                existing_forecast.forecast_qty = forecast_qty
                existing_forecast.actual_stock = actual_stock
                existing_forecast.shortage_qty = shortage_qty
                existing_forecast.excess_qty = excess_qty
                existing_forecast.profit_impact = profit_impact
                existing_forecast.holding_cost = holding_cost
                existing_forecast.opportunity_cost = opportunity_cost
                existing_forecast.updated_at = datetime.utcnow()
                forecast = existing_forecast
            else:
                # Create new forecast
                forecast = StockForecast(
                    product_id=product_id,
                    agency_id=agency_id,
                    week_start_date=week_start_date,
                    week_end_date=week_end_date,
                    forecast_qty=forecast_qty,
                    actual_stock=actual_stock,
                    shortage_qty=shortage_qty,
                    excess_qty=excess_qty,
                    profit_impact=profit_impact,
                    holding_cost=holding_cost,
                    opportunity_cost=opportunity_cost
                )
                db.session.add(forecast)
            
            return forecast
            
        except Exception as e:
            self.logger.error(f"Error generating forecast for product {product_id}: {str(e)}")
            return None
    
    def check_and_trigger_alerts(self, forecast: StockForecast) -> bool:
        """
        Check if forecast meets alert thresholds and trigger alerts
        
        Args:
            forecast: StockForecast instance
            
        Returns:
            True if alert was triggered, False otherwise
        """
        try:
            # Get alert configuration for this agency
            product = forecast.product
            
            # Try to get category-specific config first
            alert_config = None
            if product.category_id:
                alert_config = ForecastAlertConfig.query.filter_by(
                    agency_id=forecast.agency_id,
                    category_id=product.category_id,
                    is_active=True
                ).first()
            
            # Fall back to general agency config
            if not alert_config:
                alert_config = ForecastAlertConfig.query.filter_by(
                    agency_id=forecast.agency_id,
                    category_id=None,
                    is_active=True
                ).first()
            
            # If no config exists, use default thresholds
            if not alert_config:
                shortage_threshold_qty = Decimal(10)
                shortage_threshold_pct = Decimal(20)
                excess_threshold_qty = Decimal(50)
                excess_threshold_pct = Decimal(30)
                email_enabled = False
                dashboard_enabled = True
                recipients = None
            else:
                shortage_threshold_qty = alert_config.shortage_threshold_qty
                shortage_threshold_pct = alert_config.shortage_threshold_percentage
                excess_threshold_qty = alert_config.excess_threshold_qty
                excess_threshold_pct = alert_config.excess_threshold_percentage
                email_enabled = alert_config.email_alerts_enabled
                dashboard_enabled = alert_config.dashboard_alerts_enabled
                recipients = alert_config.alert_recipients
            
            # Check if alert should be triggered
            alert_triggered = False
            alert_type = None
            
            # Check shortage thresholds
            if forecast.shortage_qty > 0:
                shortage_pct = (forecast.shortage_qty / forecast.forecast_qty * 100) if forecast.forecast_qty > 0 else 0
                if (forecast.shortage_qty >= shortage_threshold_qty or 
                    shortage_pct >= shortage_threshold_pct):
                    alert_triggered = True
                    alert_type = 'shortage'
            
            # Check excess thresholds
            if forecast.excess_qty > 0:
                excess_pct = (forecast.excess_qty / forecast.forecast_qty * 100) if forecast.forecast_qty > 0 else 0
                if (forecast.excess_qty >= excess_threshold_qty or 
                    excess_pct >= excess_threshold_pct):
                    alert_triggered = True
                    alert_type = 'excess'
            
            if alert_triggered:
                forecast.alert_triggered = True
                forecast.alert_sent_at = datetime.utcnow()
                
                # Send email alert if enabled
                if email_enabled and recipients:
                    self.send_alert_email(forecast, alert_type, recipients)
                
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking alerts for forecast {forecast.id}: {str(e)}")
            return False
    
    def send_alert_email(self, forecast: StockForecast, alert_type: str, recipients: str):
        """
        Send email alert for forecast shortage/excess
        
        Args:
            forecast: StockForecast instance
            alert_type: 'shortage' or 'excess'
            recipients: Comma-separated email addresses
        """
        try:
            product = forecast.product
            agency = forecast.agency
            
            # Prepare email content
            if alert_type == 'shortage':
                subject = f"Stock Shortage Alert: {product.name}"
                alert_message = f"""
                <p><strong>Stock Shortage Detected</strong></p>
                <p>Product: <strong>{product.name}</strong> (SKU: {product.sku})</p>
                <p>Agency: <strong>{agency.name}</strong></p>
                <p>Forecasted Demand: <strong>{forecast.forecast_qty}</strong> units</p>
                <p>Current Stock: <strong>{forecast.actual_stock}</strong> units</p>
                <p>Shortage: <strong style="color: red;">{forecast.shortage_qty}</strong> units</p>
                <p>Estimated Profit Impact: <strong style="color: red;">₹{abs(forecast.profit_impact):.2f}</strong></p>
                <p>Recommended Action: Order additional <strong>{forecast.shortage_qty}</strong> units to meet demand.</p>
                """
            else:
                subject = f"Excess Stock Alert: {product.name}"
                alert_message = f"""
                <p><strong>Excess Stock Detected</strong></p>
                <p>Product: <strong>{product.name}</strong> (SKU: {product.sku})</p>
                <p>Agency: <strong>{agency.name}</strong></p>
                <p>Forecasted Demand: <strong>{forecast.forecast_qty}</strong> units</p>
                <p>Current Stock: <strong>{forecast.actual_stock}</strong> units</p>
                <p>Excess: <strong style="color: orange;">{forecast.excess_qty}</strong> units</p>
                <p>Holding Cost: <strong style="color: orange;">₹{forecast.holding_cost:.2f}</strong></p>
                <p>Recommended Action: Consider promotional activities to reduce excess inventory.</p>
                """
            
            body_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
                    .content {{ background-color: #f9f9f9; padding: 30px; border: 1px solid #ddd; }}
                    .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Stock Forecast Alert</h1>
                    </div>
                    <div class="content">
                        {alert_message}
                        <p>Week: {forecast.week_start_date} to {forecast.week_end_date}</p>
                        <p>Please review the forecast dashboard for more details.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; {datetime.utcnow().year} Agency Sales Pro. All rights reserved.</p>
                        <p>This is an automated alert. Please do not reply.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Send to each recipient
            recipient_list = [email.strip() for email in recipients.split(',')]
            for recipient in recipient_list:
                if recipient:
                    email_service.send_email(recipient, subject, body_html)
            
            self.logger.info(f"Alert email sent for forecast {forecast.id} to {len(recipient_list)} recipients")
            
        except Exception as e:
            self.logger.error(f"Error sending alert email: {str(e)}")
    
    def refresh_forecasts(
        self,
        agency_id: Optional[int] = None,
        user_id: Optional[int] = None,
        refresh_type: str = 'manual'
    ) -> ForecastRefreshLog:
        """
        Refresh forecasts for all products in an agency or all agencies
        
        Args:
            agency_id: Agency ID (None for all agencies)
            user_id: User who triggered the refresh
            refresh_type: 'manual' or 'scheduled'
            
        Returns:
            ForecastRefreshLog instance
        """
        start_time = datetime.utcnow()
        
        # Create refresh log
        refresh_log = ForecastRefreshLog(
            agency_id=agency_id,
            refresh_type=refresh_type,
            triggered_by=user_id,
            status='running',
            started_at=start_time
        )
        db.session.add(refresh_log)
        db.session.commit()
        
        try:
            # Get week dates
            week_start, week_end = self.get_week_dates()
            
            # Query products to forecast
            query = db.session.query(ProductAgency).filter(
                ProductAgency.is_active == True
            )
            
            if agency_id:
                query = query.filter(ProductAgency.agency_id == agency_id)
            
            product_agencies = query.all()
            
            products_processed = 0
            forecasts_created = 0
            forecasts_updated = 0
            alerts_triggered = 0
            
            for pa in product_agencies:
                try:
                    # Check if forecast exists
                    existing = StockForecast.query.filter_by(
                        product_id=pa.product_id,
                        agency_id=pa.agency_id,
                        week_start_date=week_start
                    ).first()
                    
                    is_new = existing is None
                    
                    # Generate forecast
                    forecast = self.generate_forecast_for_product(
                        pa.product_id,
                        pa.agency_id,
                        week_start,
                        week_end
                    )
                    
                    if forecast:
                        products_processed += 1
                        
                        if is_new:
                            forecasts_created += 1
                        else:
                            forecasts_updated += 1
                        
                        # Check and trigger alerts
                        if self.check_and_trigger_alerts(forecast):
                            alerts_triggered += 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing product {pa.product_id}: {str(e)}")
                    continue
            
            # Commit all forecasts
            db.session.commit()
            
            # Update refresh log
            end_time = datetime.utcnow()
            duration = int((end_time - start_time).total_seconds())
            
            refresh_log.status = 'completed'
            refresh_log.products_processed = products_processed
            refresh_log.forecasts_created = forecasts_created
            refresh_log.forecasts_updated = forecasts_updated
            refresh_log.alerts_triggered = alerts_triggered
            refresh_log.completed_at = end_time
            refresh_log.duration_seconds = duration
            
            db.session.commit()
            
            self.logger.info(
                f"Forecast refresh completed: {products_processed} products, "
                f"{forecasts_created} created, {forecasts_updated} updated, "
                f"{alerts_triggered} alerts triggered"
            )
            
            return refresh_log
            
        except Exception as e:
            # Update refresh log with error
            refresh_log.status = 'failed'
            refresh_log.error_message = str(e)
            refresh_log.completed_at = datetime.utcnow()
            db.session.commit()
            
            self.logger.error(f"Forecast refresh failed: {str(e)}")
            raise


# Global forecast service instance
forecast_service = ForecastService()