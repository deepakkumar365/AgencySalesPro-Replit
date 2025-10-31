"""
Database Migration Script: Change quantity columns from INTEGER to NUMERIC(10,2)

This script updates the following columns:
1. ASP_order_items.quantity: INTEGER -> NUMERIC(10,2)
2. ASP_purchase_order_items.quantity_ordered: INTEGER -> NUMERIC(10,2)
3. ASP_purchase_order_items.quantity_received: INTEGER -> NUMERIC(10,2)

Run this script once to update your database schema.
"""

from app import app, db
from sqlalchemy import text

def migrate_quantity_columns():
    """Migrate quantity columns from INTEGER to NUMERIC(10,2)"""
    
    with app.app_context():
        try:
            print("Starting database migration...")
            print("=" * 60)
            
            # PostgreSQL ALTER TABLE commands
            queries = [
                "ALTER TABLE \"ASP_order_items\" ALTER COLUMN quantity TYPE NUMERIC(10, 2);",
                "ALTER TABLE \"ASP_purchase_order_items\" ALTER COLUMN quantity_ordered TYPE NUMERIC(10, 2);",
                "ALTER TABLE \"ASP_purchase_order_items\" ALTER COLUMN quantity_received TYPE NUMERIC(10, 2);"
            ]
            
            for i, query in enumerate(queries, 1):
                print(f"\nExecuting migration {i}/{len(queries)}...")
                print(f"  {query}")
                db.session.execute(text(query))
                db.session.commit()
                print(f"  ✓ Success")
            
            print()
            print("=" * 60)
            print("Migration completed successfully!")
            print()
            print("Updated columns:")
            print("  ✓ ASP_order_items.quantity: INTEGER -> NUMERIC(10,2)")
            print("  ✓ ASP_purchase_order_items.quantity_ordered: INTEGER -> NUMERIC(10,2)")
            print("  ✓ ASP_purchase_order_items.quantity_received: INTEGER -> NUMERIC(10,2)")
            print()
            print("You can now use decimal quantities like 1.5, 2.25, etc.")
            
        except Exception as e:
            print(f"\nERROR during migration: {str(e)}")
            print("Rolling back changes...")
            db.session.rollback()
            raise

if __name__ == '__main__':
    print()
    print("=" * 60)
    print("DATABASE MIGRATION: Quantity Columns to NUMERIC(10,2)")
    print("=" * 60)
    print()
    print("This will modify the following PostgreSQL database columns:")
    print("  1. ASP_order_items.quantity")
    print("  2. ASP_purchase_order_items.quantity_ordered")
    print("  3. ASP_purchase_order_items.quantity_received")
    print()
    print("IMPORTANT: Make sure you have a database backup before proceeding!")
    print()
    
    response = input("Do you want to continue? (yes/no): ").strip().lower()
    
    if response in ['yes', 'y']:
        migrate_quantity_columns()
    else:
        print("\nMigration cancelled.")