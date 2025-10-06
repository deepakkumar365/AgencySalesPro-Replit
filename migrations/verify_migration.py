#!/usr/bin/env python3
"""
Verify that the order_id migration was applied successfully
"""

import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def verify_migration():
    """Verify the migration was applied"""
    
    print("=" * 60)
    print("Verifying Migration: order_id column in ASP_jobs")
    print("=" * 60)
    print()
    
    try:
        # Connect to PostgreSQL
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cursor = conn.cursor()
        
        # Check column exists
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name='ASP_jobs' AND column_name='order_id'
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"✓ Column 'order_id' exists")
            print(f"  - Data type: {result[1]}")
            print(f"  - Nullable: {result[2]}")
        else:
            print("❌ Column 'order_id' NOT found")
            return
        
        # Check foreign key constraint
        cursor.execute("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name='ASP_jobs' 
            AND constraint_name='fk_jobs_order_id'
            AND constraint_type='FOREIGN KEY'
        """)
        
        if cursor.fetchone():
            print("✓ Foreign key constraint 'fk_jobs_order_id' exists")
        else:
            print("❌ Foreign key constraint NOT found")
        
        # Check index
        cursor.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename='ASP_jobs' 
            AND indexname='idx_jobs_order_id'
        """)
        
        if cursor.fetchone():
            print("✓ Index 'idx_jobs_order_id' exists")
        else:
            print("❌ Index NOT found")
        
        print()
        print("=" * 60)
        print("✅ Migration verification complete!")
        print("=" * 60)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ ERROR: Verification failed: {str(e)}")
        raise

if __name__ == '__main__':
    verify_migration()