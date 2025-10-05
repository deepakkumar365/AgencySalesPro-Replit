#!/usr/bin/env python3
"""
Simple migration script to add order_id column to ASP_jobs table
Connects directly to PostgreSQL without Flask dependencies
"""

import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration():
    """Add order_id column to ASP_jobs table"""
    
    print("=" * 60)
    print("Migration: Add order_id to ASP_jobs table")
    print("=" * 60)
    print()
    
    # Get database connection details from environment
    db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        print("❌ ERROR: DATABASE_URL not found in environment")
        return
    
    # Parse the database URL
    # Format: postgresql://user:password@host:port/database
    db_url = db_url.replace("postgresql://", "")
    
    try:
        # Connect to PostgreSQL
        print(f"Connecting to database...")
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        conn.autocommit = False
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='ASP_jobs' AND column_name='order_id'
        """)
        
        if cursor.fetchone():
            print("✓ Column 'order_id' already exists in ASP_jobs table")
            print("Migration already applied. Skipping.")
            cursor.close()
            conn.close()
            return
        
        print("Adding order_id column to ASP_jobs table...")
        
        # Add order_id column
        cursor.execute("""
            ALTER TABLE "ASP_jobs" 
            ADD COLUMN order_id INTEGER
        """)
        print("✓ Added order_id column")
        
        # Add foreign key constraint
        cursor.execute("""
            ALTER TABLE "ASP_jobs" 
            ADD CONSTRAINT fk_jobs_order_id 
            FOREIGN KEY (order_id) REFERENCES "ASP_orders"(id) ON DELETE SET NULL
        """)
        print("✓ Added foreign key constraint to ASP_orders")
        
        # Add index
        cursor.execute("""
            CREATE INDEX idx_jobs_order_id ON "ASP_jobs"(order_id)
        """)
        print("✓ Added index for better query performance")
        
        # Commit the transaction
        conn.commit()
        
        print()
        print("=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ ERROR: Migration failed: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        raise

if __name__ == '__main__':
    run_migration()