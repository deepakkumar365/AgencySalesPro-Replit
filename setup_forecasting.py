"""
Forecasting Module Setup Script
Run this script to verify the forecasting module setup
"""

import os
import sys
from datetime import datetime

# Add the application directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def check_database_tables():
    """Check if forecasting tables exist"""
    print("\n" + "="*80)
    print("Checking Database Tables...")
    print("="*80)
    
    from app import app
    from extensions import db
    from sqlalchemy import inspect
    
    with app.app_context():
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        required_tables = [
            'ASP_stock_forecasts',
            'ASP_forecast_alert_configs',
            'ASP_forecast_refresh_logs'
        ]
        
        all_exist = True
        for table in required_tables:
            exists = table in tables
            status = "✅ EXISTS" if exists else "❌ MISSING"
            print(f"{status}: {table}")
            if not exists:
                all_exist = False
        
        if all_exist:
            print("\n✅ All forecasting tables exist!")
        else:
            print("\n⚠️  Some tables are missing. They will be created on next app start.")
        
        return all_exist


def check_email_configuration():
    """Check if email service is configured"""
    print("\n" + "="*80)
    print("Checking Email Configuration...")
    print("="*80)
    
    email_enabled = os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true'
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_username = os.environ.get('SMTP_USERNAME', '')
    smtp_password = os.environ.get('SMTP_PASSWORD', '')
    
    print(f"EMAIL_ENABLED: {email_enabled}")
    print(f"SMTP_HOST: {smtp_host or '(not set)'}")
    print(f"SMTP_USERNAME: {smtp_username or '(not set)'}")
    print(f"SMTP_PASSWORD: {'***' if smtp_password else '(not set)'}")
    
    if email_enabled and smtp_host and smtp_username and smtp_password:
        print("\n✅ Email service is configured!")
        return True
    else:
        print("\n⚠️  Email service is not fully configured.")
        print("   Email alerts will not be sent until configuration is complete.")
        print("   Add the following to your .env file:")
        print("   EMAIL_ENABLED=true")
        print("   SMTP_HOST=smtp.gmail.com")
        print("   SMTP_PORT=587")
        print("   SMTP_USERNAME=your-email@example.com")
        print("   SMTP_PASSWORD=your-app-password")
        return False


def check_dependencies():
    """Check if required Python packages are installed"""
    print("\n" + "="*80)
    print("Checking Dependencies...")
    print("="*80)
    
    required_packages = {
        'flask': 'Flask',
        'sqlalchemy': 'SQLAlchemy',
        'pandas': 'pandas',
        'openpyxl': 'openpyxl'
    }
    
    all_installed = True
    for package, display_name in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {display_name} is installed")
        except ImportError:
            print(f"❌ {display_name} is NOT installed")
            all_installed = False
    
    if all_installed:
        print("\n✅ All required packages are installed!")
    else:
        print("\n⚠️  Some packages are missing. Install them with:")
        print("   pip install flask sqlalchemy pandas openpyxl")
    
    return all_installed


def check_blueprint_registration():
    """Check if forecasting blueprint is registered"""
    print("\n" + "="*80)
    print("Checking Blueprint Registration...")
    print("="*80)
    
    try:
        from app import app
        
        # Check if forecasting blueprint is registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        
        if 'forecasting' in blueprint_names:
            print("✅ Forecasting blueprint is registered!")
            return True
        else:
            print("❌ Forecasting blueprint is NOT registered!")
            print("   Check app.py for blueprint registration.")
            return False
    except Exception as e:
        print(f"❌ Error checking blueprint: {str(e)}")
        return False


def test_forecast_service():
    """Test if forecast service can be imported"""
    print("\n" + "="*80)
    print("Testing Forecast Service...")
    print("="*80)
    
    try:
        from utils.forecast_service import forecast_service
        print("✅ Forecast service imported successfully!")
        
        # Test basic functionality
        week_start, week_end = forecast_service.get_week_dates()
        print(f"✅ Week calculation works: {week_start} to {week_end}")
        
        return True
    except Exception as e:
        print(f"❌ Error importing forecast service: {str(e)}")
        return False


def create_sample_alert_config():
    """Create a sample alert configuration"""
    print("\n" + "="*80)
    print("Creating Sample Alert Configuration...")
    print("="*80)
    
    try:
        from app import app
        from extensions import db
        from models import ForecastAlertConfig, Agency
        
        with app.app_context():
            # Get first active agency
            agency = Agency.query.filter_by(is_active=True).first()
            
            if not agency:
                print("⚠️  No active agencies found. Create an agency first.")
                return False
            
            # Check if config already exists
            existing_config = ForecastAlertConfig.query.filter_by(
                agency_id=agency.id,
                category_id=None
            ).first()
            
            if existing_config:
                print(f"✅ Alert configuration already exists for agency: {agency.name}")
                return True
            
            # Create default configuration
            config = ForecastAlertConfig(
                agency_id=agency.id,
                category_id=None,  # Default for all categories
                shortage_threshold_qty=10,
                shortage_threshold_percentage=20,
                excess_threshold_qty=50,
                excess_threshold_percentage=30,
                email_alerts_enabled=True,
                dashboard_alerts_enabled=True,
                alert_recipients='',  # User should configure this
                is_active=True
            )
            
            db.session.add(config)
            db.session.commit()
            
            print(f"✅ Created default alert configuration for agency: {agency.name}")
            print("   Please update alert recipients in the Alert Configuration page.")
            return True
            
    except Exception as e:
        print(f"❌ Error creating sample config: {str(e)}")
        return False


def print_next_steps():
    """Print next steps for setup"""
    print("\n" + "="*80)
    print("Next Steps")
    print("="*80)
    
    print("""
1. Configure Email Service (if not done):
   - Add SMTP settings to .env file
   - Test email sending

2. Set Up Scheduled Task:
   
   Linux/Unix (Cron):
   $ crontab -e
   # Add this line:
   0 0 * * * cd /path/to/AgencySalesPro-Replit && python scheduled_forecast_refresh.py
   
   Windows (Task Scheduler):
   - Open Task Scheduler
   - Create Basic Task → Daily at 12:00 AM
   - Action: Start program python.exe
   - Arguments: scheduled_forecast_refresh.py
   - Start in: C:\\Repo\\AgencySalesPro-Replit

3. Configure Alert Thresholds:
   - Log in to the application
   - Navigate to Forecasting > Alert Configuration
   - Set thresholds and email recipients
   - Save configuration

4. Generate First Forecast:
   - Navigate to Forecasting > Forecast Dashboard
   - Click "Refresh Forecasts" button
   - Wait for completion
   - Review generated forecasts

5. Review Documentation:
   - See docs/FORECASTING_MODULE.md for detailed documentation
   - See FORECASTING_IMPLEMENTATION_SUMMARY.md for implementation details

For support, refer to the documentation or contact your system administrator.
""")


def main():
    """Main setup verification function"""
    print("\n" + "="*80)
    print("FORECASTING MODULE SETUP VERIFICATION")
    print("="*80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {
        'dependencies': check_dependencies(),
        'blueprint': check_blueprint_registration(),
        'forecast_service': test_forecast_service(),
        'database': check_database_tables(),
        'email': check_email_configuration(),
        'sample_config': create_sample_alert_config()
    }
    
    print("\n" + "="*80)
    print("SETUP VERIFICATION SUMMARY")
    print("="*80)
    
    for check, passed in results.items():
        status = "✅ PASS" if passed else "⚠️  NEEDS ATTENTION"
        print(f"{status}: {check.replace('_', ' ').title()}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n" + "="*80)
        print("✅ ALL CHECKS PASSED!")
        print("="*80)
        print("The forecasting module is ready to use.")
    else:
        print("\n" + "="*80)
        print("⚠️  SOME CHECKS NEED ATTENTION")
        print("="*80)
        print("Please address the issues above before using the forecasting module.")
    
    print_next_steps()
    
    return all_passed


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Setup verification failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)