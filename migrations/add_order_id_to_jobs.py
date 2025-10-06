#!/usr/bin/env python3
"""
Migration: Add order_id column to ASP_jobs table
This allows jobs to be linked to orders for automatic job creation
"""

import os
import sys
from dotenv import load_dotenv

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Import the Flask app
from app import create_app, db

def run_migration():
    """Add order_id column to ASP_jobs table"""
    
    print("=" * 60)
    print("Migration: Add order_id to ASP_jobs table")
    print("=" * 60)
    print()
    
    app = create_app()
    
    with app.app_context():
        try:
            # Check if column already exists
            result = db.session.execute(db.text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='ASP_jobs' AND column_name='order_id'
            """))
            
            if result.fetchone():
                print("✓ Column 'order_id' already exists in ASP_jobs table")
                print("Migration already applied. Skipping.")
                return
            
            print("Adding order_id column to ASP_jobs table...")
            
            # Add order_id column
            db.session.execute(db.text("""
                ALTER TABLE "ASP_jobs" 
                ADD COLUMN order_id INTEGER
            """))
            
            # Add foreign key constraint
            db.session.execute(db.text("""
                ALTER TABLE "ASP_jobs" 
                ADD CONSTRAINT fk_jobs_order_id 
                FOREIGN KEY (order_id) REFERENCES "ASP_orders"(id) ON DELETE SET NULL
            """))
            
            # Add index
            db.session.execute(db.text("""
                CREATE INDEX idx_jobs_order_id ON "ASP_jobs"(order_id)
            """))
            
            db.session.commit()
            
            print("✓ Successfully added order_id column to ASP_jobs table")
            print("✓ Added foreign key constraint to ASP_orders")
            print("✓ Added index for better query performance")
            print()
            print("Migration completed successfully!")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ ERROR: Migration failed: {str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    run_migration()