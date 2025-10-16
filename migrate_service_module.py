#!/usr/bin/env python3
"""
Service Module Database Migration Script

This script creates the necessary database tables for the Service Extension module.
It uses SQLAlchemy's create_all() method to create tables based on the new models.

Usage:
    python migrate_service_module.py

Requirements:
    - .env file with DATABASE_URL configured
    - All dependencies installed (Flask, SQLAlchemy, etc.)
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path to allow app import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app
from app import create_app, db

def run_migration():
    """Run the database migration to create Service Module tables."""
    
    print("=" * 60)
    print("Service Module - Database Migration")
    print("=" * 60)
    print()
    
    # Check if DATABASE_URL is set
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: DATABASE_URL environment variable not set.")
        print("   Please create a .env file with your database connection string.")
        sys.exit(1)
    
    print(f"✓ Database URL found: {database_url[:30]}...")
    print()
    
    # Create Flask app
    print("Creating Flask application context...")
    app = create_app()
    
    with app.app_context():
        print("✓ Application context created")
        print()
        
        # Import models to ensure they're registered
        print("Importing models...")
        from models import Vehicle, ServiceCatalog, WorkOrder, WorkOrderLineItem, User
        print("✓ Service Module models imported")
        print()
        
        # Check if tables already exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        service_tables = ['ASP_vehicles', 'ASP_service_catalog', 'ASP_work_orders', 'ASP_work_order_line_items']
        existing_service_tables = [t for t in service_tables if t in existing_tables]

        if existing_service_tables:
            print("⚠️  WARNING: Some Service Module tables already exist:")
            for table in existing_service_tables:
                print(f"   - {table}")
            print()
            response = input("Do you want to continue? This will NOT drop existing tables. (y/n): ")
            if response.lower() != 'y':
                print("Migration cancelled.")
                sys.exit(0)
            print()
        
        # Create all tables
        print("Creating database tables...")
        try:
            # db.create_all() will only create tables that don't already exist.
            db.create_all()
            print("✓ Database tables for Service Module created successfully!")
            print()
            
            # Verify tables were created
            inspector = inspect(db.engine)
            current_tables = inspector.get_table_names()
            
            print("Verifying table creation:")
            all_found = True
            for table in service_tables:
                if table in current_tables:
                    print(f"   ✓ {table}")
                else:
                    print(f"   ❌ {table} - NOT FOUND")
                    all_found = False
            print()
            
            if all_found:
                print("=" * 60)
                print("✅ Migration completed successfully!")
                print("=" * 60)
            else:
                print("=" * 60)
                print("❌ Migration finished, but some tables were not created.")
                print("=" * 60)
            
        except Exception as e:
            print(f"❌ ERROR during migration: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    run_migration()