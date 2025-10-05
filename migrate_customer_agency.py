"""
Migration script to populate CustomerAgency mapping table from existing customer-location-agency relationships.
This script should be run once after adding the CustomerAgency model.
"""

from app import app, db
from models import Customer, Location, CustomerAgency
from datetime import datetime

def migrate_customer_agency_mappings():
    """
    Migrate existing customer-location-agency relationships to the new CustomerAgency mapping table.
    """
    with app.app_context():
        print("Starting Customer-Agency mapping migration...")
        
        # Get all customers
        customers = Customer.query.all()
        total_customers = len(customers)
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        print(f"Found {total_customers} customers to process")
        
        for customer in customers:
            try:
                # Get the location to find the agency
                location = Location.query.get(customer.location_id)
                
                if not location:
                    print(f"Warning: Customer {customer.id} ({customer.name}) has no valid location. Skipping.")
                    skipped_count += 1
                    continue
                
                # Check if mapping already exists
                existing_mapping = CustomerAgency.query.filter_by(
                    customer_id=customer.id,
                    agency_id=location.agency_id
                ).first()
                
                if existing_mapping:
                    print(f"Mapping already exists for Customer {customer.id} ({customer.name}) - Agency {location.agency_id}")
                    skipped_count += 1
                    continue
                
                # Create new mapping
                customer_agency = CustomerAgency(
                    customer_id=customer.id,
                    agency_id=location.agency_id,
                    is_active=True,
                    created_at=customer.created_at or datetime.utcnow()
                )
                
                db.session.add(customer_agency)
                migrated_count += 1
                
                if migrated_count % 100 == 0:
                    print(f"Progress: {migrated_count}/{total_customers} customers migrated")
                    db.session.commit()
                
            except Exception as e:
                print(f"Error processing customer {customer.id} ({customer.name}): {str(e)}")
                error_count += 1
                db.session.rollback()
        
        # Final commit
        try:
            db.session.commit()
            print("\n" + "="*60)
            print("Migration completed successfully!")
            print(f"Total customers: {total_customers}")
            print(f"Migrated: {migrated_count}")
            print(f"Skipped: {skipped_count}")
            print(f"Errors: {error_count}")
            print("="*60)
        except Exception as e:
            print(f"Error during final commit: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    migrate_customer_agency_mappings()