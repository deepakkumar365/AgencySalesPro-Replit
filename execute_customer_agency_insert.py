#!/usr/bin/env python3
"""
Customer-Agency Mapping Insert Script
======================================
This script populates the ASP_customer_agencies table from existing
customer-location-agency relationships.

Usage:
    python execute_customer_agency_insert.py [--dry-run] [--verbose]

Options:
    --dry-run    Show what would be inserted without actually inserting
    --verbose    Show detailed progress information
"""

import sys
import argparse
from datetime import datetime
from app import app, db
from models import Customer, Location, Agency, CustomerAgency


def print_header(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def verify_existing_data():
    """Verify existing data before migration"""
    print_header("STEP 1: VERIFYING EXISTING DATA")
    
    total_customers = Customer.query.count()
    active_customers = Customer.query.filter_by(is_active=True).count()
    total_locations = Location.query.count()
    total_agencies = Agency.query.count()
    
    print(f"✓ Total Customers: {total_customers}")
    print(f"✓ Active Customers: {active_customers}")
    print(f"✓ Total Locations: {total_locations}")
    print(f"✓ Total Agencies: {total_agencies}")
    
    # Check for customers without valid location
    customers_without_location = db.session.query(Customer).outerjoin(
        Location, Customer.location_id == Location.id
    ).filter(Location.id == None).count()
    
    if customers_without_location > 0:
        print(f"⚠ WARNING: {customers_without_location} customers have invalid location_id")
    
    # Check for locations without valid agency
    locations_without_agency = db.session.query(Location).outerjoin(
        Agency, Location.agency_id == Agency.id
    ).filter(Agency.id == None).count()
    
    if locations_without_agency > 0:
        print(f"⚠ WARNING: {locations_without_agency} locations have invalid agency_id")
    
    # Show customers per agency
    print("\nCustomers per Agency (via Location):")
    agency_stats = db.session.query(
        Agency.id,
        Agency.name,
        Agency.code,
        db.func.count(Customer.id).label('customer_count')
    ).outerjoin(Location, Agency.id == Location.agency_id)\
     .outerjoin(Customer, Location.id == Customer.location_id)\
     .group_by(Agency.id, Agency.name, Agency.code)\
     .order_by(db.desc('customer_count')).all()
    
    for stat in agency_stats:
        print(f"  • {stat.name} ({stat.code}): {stat.customer_count} customers")
    
    return {
        'total_customers': total_customers,
        'active_customers': active_customers,
        'customers_without_location': customers_without_location,
        'locations_without_agency': locations_without_agency
    }


def check_existing_mappings():
    """Check if mappings already exist"""
    print_header("STEP 2: CHECKING EXISTING MAPPINGS")
    
    existing_count = CustomerAgency.query.count()
    active_count = CustomerAgency.query.filter_by(is_active=True).count()
    
    print(f"✓ Existing Mappings: {existing_count}")
    print(f"✓ Active Mappings: {active_count}")
    
    if existing_count > 0:
        print("\n⚠ WARNING: Mappings already exist!")
        print("  The script will skip existing customer-agency pairs to prevent duplicates.")
    
    return existing_count


def get_mappings_to_insert():
    """Get list of customer-agency mappings that need to be inserted"""
    print_header("STEP 3: IDENTIFYING MAPPINGS TO INSERT")
    
    # Query customers with their location and agency
    customers_with_agency = db.session.query(
        Customer.id.label('customer_id'),
        Location.agency_id.label('agency_id'),
        Customer.is_active.label('is_active'),
        Customer.created_at.label('created_at'),
        Customer.name.label('customer_name'),
        Agency.name.label('agency_name')
    ).join(Location, Customer.location_id == Location.id)\
     .join(Agency, Location.agency_id == Agency.id)\
     .all()
    
    print(f"✓ Found {len(customers_with_agency)} customer-location-agency relationships")
    
    # Filter out existing mappings
    mappings_to_insert = []
    skipped_count = 0
    
    for mapping in customers_with_agency:
        # Check if mapping already exists
        existing = CustomerAgency.query.filter_by(
            customer_id=mapping.customer_id,
            agency_id=mapping.agency_id
        ).first()
        
        if existing:
            skipped_count += 1
        else:
            mappings_to_insert.append(mapping)
    
    print(f"✓ Mappings to insert: {len(mappings_to_insert)}")
    print(f"✓ Mappings to skip (already exist): {skipped_count}")
    
    return mappings_to_insert


def insert_mappings(mappings, dry_run=False, verbose=False):
    """Insert customer-agency mappings"""
    print_header("STEP 4: INSERTING MAPPINGS")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No data will be inserted\n")
    
    if len(mappings) == 0:
        print("✓ No new mappings to insert. All mappings already exist!")
        return 0
    
    inserted_count = 0
    error_count = 0
    
    for i, mapping in enumerate(mappings, 1):
        try:
            if verbose or (i % 100 == 0):
                print(f"  Processing {i}/{len(mappings)}: Customer '{mapping.customer_name}' → Agency '{mapping.agency_name}'")
            
            if not dry_run:
                new_mapping = CustomerAgency(
                    customer_id=mapping.customer_id,
                    agency_id=mapping.agency_id,
                    is_active=mapping.is_active,
                    created_at=mapping.created_at or datetime.utcnow()
                )
                db.session.add(new_mapping)
                
                # Commit in batches of 100 for better performance
                if i % 100 == 0:
                    db.session.commit()
                    if verbose:
                        print(f"  ✓ Committed batch of 100 mappings")
            
            inserted_count += 1
            
        except Exception as e:
            error_count += 1
            print(f"  ✗ ERROR inserting mapping for customer {mapping.customer_id}: {str(e)}")
            if not dry_run:
                db.session.rollback()
    
    # Final commit for remaining records
    if not dry_run and inserted_count > 0:
        try:
            db.session.commit()
            print(f"\n✓ Successfully committed all mappings")
        except Exception as e:
            print(f"\n✗ ERROR during final commit: {str(e)}")
            db.session.rollback()
            return 0
    
    print(f"\n{'Would insert' if dry_run else 'Inserted'}: {inserted_count} mappings")
    if error_count > 0:
        print(f"✗ Errors: {error_count}")
    
    return inserted_count


def verify_migration():
    """Verify the migration was successful"""
    print_header("STEP 5: VERIFYING MIGRATION")
    
    total_mappings = CustomerAgency.query.count()
    active_mappings = CustomerAgency.query.filter_by(is_active=True).count()
    total_customers = Customer.query.count()
    
    print(f"✓ Total Mappings: {total_mappings}")
    print(f"✓ Active Mappings: {active_mappings}")
    print(f"✓ Total Customers: {total_customers}")
    
    # Check for customers without mappings
    customers_without_mapping = db.session.query(Customer).outerjoin(
        CustomerAgency, Customer.id == CustomerAgency.customer_id
    ).filter(CustomerAgency.id == None).count()
    
    if customers_without_mapping > 0:
        print(f"\n⚠ WARNING: {customers_without_mapping} customers have no agency mappings!")
        
        # Show details
        orphaned_customers = db.session.query(Customer).outerjoin(
            CustomerAgency, Customer.id == CustomerAgency.customer_id
        ).filter(CustomerAgency.id == None).limit(10).all()
        
        print("\nFirst 10 customers without mappings:")
        for customer in orphaned_customers:
            print(f"  • ID: {customer.id}, Name: {customer.name}, Location ID: {customer.location_id}")
    else:
        print("\n✓ All customers have agency mappings!")
    
    # Show mappings per agency
    print("\nMappings per Agency:")
    agency_stats = db.session.query(
        Agency.id,
        Agency.name,
        Agency.code,
        db.func.count(CustomerAgency.id).label('mapping_count'),
        db.func.sum(db.case([(CustomerAgency.is_active == True, 1)], else_=0)).label('active_count')
    ).outerjoin(CustomerAgency, Agency.id == CustomerAgency.agency_id)\
     .group_by(Agency.id, Agency.name, Agency.code)\
     .order_by(db.desc('mapping_count')).all()
    
    for stat in agency_stats:
        print(f"  • {stat.name} ({stat.code}): {stat.mapping_count} total, {stat.active_count} active")
    
    # Verify data integrity
    print("\nVerifying Data Integrity:")
    mismatches = db.session.query(
        Customer.id,
        Customer.name,
        Location.agency_id.label('location_agency_id'),
        CustomerAgency.agency_id.label('mapping_agency_id')
    ).join(Location, Customer.location_id == Location.id)\
     .join(CustomerAgency, Customer.id == CustomerAgency.customer_id)\
     .filter(Location.agency_id != CustomerAgency.agency_id).count()
    
    if mismatches > 0:
        print(f"  ⚠ WARNING: {mismatches} customers have mismatched agency mappings!")
    else:
        print(f"  ✓ All customer-agency mappings match their location-agency relationships")
    
    return {
        'total_mappings': total_mappings,
        'active_mappings': active_mappings,
        'customers_without_mapping': customers_without_mapping,
        'mismatches': mismatches
    }


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(
        description='Insert customer-agency mappings from existing data'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be inserted without actually inserting'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed progress information'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("  CUSTOMER-AGENCY MAPPING INSERT SCRIPT")
    print("=" * 80)
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print(f"  Verbose: {'Yes' if args.verbose else 'No'}")
    print("=" * 80)
    
    try:
        with app.app_context():
            # Step 1: Verify existing data
            data_stats = verify_existing_data()
            
            if data_stats['customers_without_location'] > 0 or data_stats['locations_without_agency'] > 0:
                print("\n⚠ WARNING: Data integrity issues detected!")
                response = input("Do you want to continue anyway? (yes/no): ")
                if response.lower() != 'yes':
                    print("Aborted by user.")
                    return 1
            
            # Step 2: Check existing mappings
            existing_mappings = check_existing_mappings()
            
            # Step 3: Get mappings to insert
            mappings = get_mappings_to_insert()
            
            if len(mappings) == 0:
                print("\n✓ Migration complete - no new mappings needed!")
                return 0
            
            # Confirm before inserting
            if not args.dry_run:
                print(f"\n⚠ About to insert {len(mappings)} new mappings.")
                response = input("Do you want to proceed? (yes/no): ")
                if response.lower() != 'yes':
                    print("Aborted by user.")
                    return 1
            
            # Step 4: Insert mappings
            inserted = insert_mappings(mappings, dry_run=args.dry_run, verbose=args.verbose)
            
            # Step 5: Verify migration (only if not dry run)
            if not args.dry_run and inserted > 0:
                verification = verify_migration()
                
                if verification['customers_without_mapping'] > 0 or verification['mismatches'] > 0:
                    print("\n⚠ WARNING: Migration completed with issues!")
                    print("  Please review the verification results above.")
                    return 1
            
            print_header("MIGRATION COMPLETE")
            print(f"✓ Successfully {'simulated' if args.dry_run else 'inserted'} {inserted} mappings")
            print(f"✓ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            if args.dry_run:
                print("\n💡 Run without --dry-run to actually insert the data")
            
            return 0
            
    except KeyboardInterrupt:
        print("\n\n⚠ Interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())