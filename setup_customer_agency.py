"""
Setup script to create CustomerAgency table and migrate existing data.
Run this script once to set up the new customer-agency mapping system.
"""

from app import app, db
from models import CustomerAgency
from migrate_customer_agency import migrate_customer_agency_mappings

def setup_customer_agency_table():
    """
    Create the CustomerAgency table and populate it with existing data.
    """
    with app.app_context():
        print("="*60)
        print("Customer-Agency Mapping Setup")
        print("="*60)
        
        # Step 1: Create the table
        print("\nStep 1: Creating CustomerAgency table...")
        try:
            db.create_all()
            print("✓ Table created successfully")
        except Exception as e:
            print(f"✗ Error creating table: {str(e)}")
            return
        
        # Step 2: Migrate existing data
        print("\nStep 2: Migrating existing customer-location-agency relationships...")
        try:
            migrate_customer_agency_mappings()
        except Exception as e:
            print(f"✗ Error during migration: {str(e)}")
            return
        
        print("\n" + "="*60)
        print("Setup completed successfully!")
        print("="*60)
        print("\nNext steps:")
        print("1. Test the customer listing page")
        print("2. Test creating new customers")
        print("3. Test editing existing customers")
        print("4. Verify agency filtering works correctly")

if __name__ == '__main__':
    setup_customer_agency_table()