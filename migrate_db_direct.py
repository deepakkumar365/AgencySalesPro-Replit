"""
Direct Database Migration Script: Change quantity columns from INTEGER to NUMERIC(10,2)

This script connects directly to PostgreSQL without loading the Flask app.
"""

import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def migrate_quantity_columns():
    """Migrate quantity columns from INTEGER to NUMERIC(10,2)"""
    
    # Get database connection details from environment
    db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        return
    
    # Parse the database URL
    # Format: postgresql://user:password@host:port/database
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
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
    
    try:
        # Connect to PostgreSQL
        print("Connecting to database...")
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        cursor = conn.cursor()
        print("✓ Connected successfully")
        print()
        
        # Show current column types
        print("Checking current column types...")
        cursor.execute("""
            SELECT 
                table_name, 
                column_name, 
                data_type 
            FROM information_schema.columns 
            WHERE table_name IN ('ASP_order_items', 'ASP_purchase_order_items')
                AND column_name IN ('quantity', 'quantity_ordered', 'quantity_received')
            ORDER BY table_name, column_name;
        """)
        
        print("\nCurrent column types:")
        for row in cursor.fetchall():
            print(f"  {row[0]}.{row[1]}: {row[2]}")
        print()
        
        # Execute migrations
        queries = [
            ('ASP_order_items.quantity', 
             'ALTER TABLE "ASP_order_items" ALTER COLUMN quantity TYPE NUMERIC(10, 2);'),
            ('ASP_purchase_order_items.quantity_ordered',
             'ALTER TABLE "ASP_purchase_order_items" ALTER COLUMN quantity_ordered TYPE NUMERIC(10, 2);'),
            ('ASP_purchase_order_items.quantity_received',
             'ALTER TABLE "ASP_purchase_order_items" ALTER COLUMN quantity_received TYPE NUMERIC(10, 2);')
        ]
        
        print("Starting migration...")
        print()
        
        for i, (column_name, query) in enumerate(queries, 1):
            print(f"[{i}/{len(queries)}] Altering {column_name}...")
            cursor.execute(query)
            print(f"      ✓ Success")
        
        # Commit the changes
        conn.commit()
        print()
        print("=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        print()
        
        # Show updated column types
        cursor.execute("""
            SELECT 
                table_name, 
                column_name, 
                data_type,
                numeric_precision,
                numeric_scale
            FROM information_schema.columns 
            WHERE table_name IN ('ASP_order_items', 'ASP_purchase_order_items')
                AND column_name IN ('quantity', 'quantity_ordered', 'quantity_received')
            ORDER BY table_name, column_name;
        """)
        
        print("Updated column types:")
        for row in cursor.fetchall():
            print(f"  ✓ {row[0]}.{row[1]}: {row[2]}({row[3]},{row[4]})")
        
        print()
        print("You can now use decimal quantities like 1.5, 2.25, etc.")
        print()
        
        # Close connection
        cursor.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"\nERROR during migration: {str(e)}")
        if conn:
            conn.rollback()
            print("Changes rolled back.")
        raise
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        migrate_quantity_columns()
    except KeyboardInterrupt:
        print("\n\nMigration cancelled by user.")
    except Exception as e:
        print(f"\nMigration failed: {str(e)}")
        exit(1)