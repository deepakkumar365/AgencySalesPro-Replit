"""
Database Migration Script: Add 'customer_id' to 'ASP_subscriptions' table.

This script addresses a schema mismatch where the Subscription model has a
'customer_id' field that is missing from the database table.

Run this script once to update your database schema.
"""

import sys
from app import app, db
from sqlalchemy import text

def migrate_add_customer_id_column():
    """Adds the customer_id column and its foreign key constraint."""
    
    with app.app_context():
        try:
            print("Starting database migration: Add customer_id to ASP_subscriptions...")
            print("=" * 70)
            
            # Use raw SQL to add the column if it doesn't exist, to make the script runnable multiple times.
            # Note: ALTER TABLE ADD COLUMN IF NOT EXISTS is for PostgreSQL 9.6+
            query = text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='ASP_subscriptions' AND column_name='customer_id') THEN
                        ALTER TABLE "ASP_subscriptions" ADD COLUMN customer_id INTEGER;
                        ALTER TABLE "ASP_subscriptions" ADD CONSTRAINT "ASP_subscriptions_customer_id_fkey" 
                              FOREIGN KEY (customer_id) REFERENCES "ASP_customers" (id);
                        CREATE INDEX ix_ASP_subscriptions_customer_id ON "ASP_subscriptions" (customer_id);
                        ALTER TABLE "ASP_subscriptions" ADD CONSTRAINT uq_ASP_subscriptions_customer_id UNIQUE (customer_id);
                        RAISE NOTICE 'Column customer_id added to ASP_subscriptions.';
                    ELSE
                        RAISE NOTICE 'Column customer_id already exists in ASP_subscriptions.';
                    END IF;
                END $$;
            """)
            
            db.session.execute(query)
            db.session.commit()
            
            print("\n✓ Migration completed successfully!")
            
        except Exception as e:
            print(f"\n✗ ERROR during migration: {str(e)}")
            db.session.rollback()
            raise

if __name__ == '__main__':
    response = input("This script will add the 'customer_id' column to the 'ASP_subscriptions' table. Continue? (yes/no): ").strip().lower()
    if response in ['yes', 'y']:
        migrate_add_customer_id_column()
    else:
        print("\nMigration cancelled.")
        sys.exit(1)