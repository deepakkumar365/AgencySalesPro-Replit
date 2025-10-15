"""
Scheduled Forecast Refresh Script
Run this script daily at midnight to automatically refresh forecasts
Can be scheduled using cron (Linux) or Task Scheduler (Windows)

Example cron entry (runs at midnight):
0 0 * * * cd /path/to/app && python scheduled_forecast_refresh.py

Example Windows Task Scheduler:
- Trigger: Daily at 12:00 AM
- Action: Start a program
- Program: python.exe
- Arguments: scheduled_forecast_refresh.py
- Start in: C:\path\to\app
"""

import os
import sys
import logging
from datetime import datetime

# Add the application directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('forecast_refresh.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def run_forecast_refresh():
    """Run the forecast refresh for all agencies"""
    try:
        logger.info("Starting scheduled forecast refresh...")
        
        # Import Flask app and create context
        from app import app
        from utils.forecast_service import forecast_service
        
        with app.app_context():
            # Refresh forecasts for all agencies
            refresh_log = forecast_service.refresh_forecasts(
                agency_id=None,  # None = all agencies
                user_id=None,    # System-triggered
                refresh_type='scheduled'
            )
            
            logger.info(
                f"Forecast refresh completed successfully: "
                f"{refresh_log.products_processed} products processed, "
                f"{refresh_log.forecasts_created} created, "
                f"{refresh_log.forecasts_updated} updated, "
                f"{refresh_log.alerts_triggered} alerts triggered, "
                f"Duration: {refresh_log.duration_seconds}s"
            )
            
            return True
            
    except Exception as e:
        logger.error(f"Forecast refresh failed: {str(e)}", exc_info=True)
        return False


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info(f"Scheduled Forecast Refresh - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    success = run_forecast_refresh()
    
    if success:
        logger.info("Scheduled forecast refresh completed successfully")
        sys.exit(0)
    else:
        logger.error("Scheduled forecast refresh failed")
        sys.exit(1)