#!/usr/bin/env python3
"""
Job Accounting Module Database Migration Script

This script creates the necessary database tables for the Job Accounting module.
It uses SQLAlchemy's create_all() method to create tables based on the models.

Usage:
    python migrate_job_accounting.py

Requirements:
    - .env file with DATABASE_URL configured
    - All dependencies installed (Flask, SQLAlchemy, etc.)
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the Flask app
from app import create_app, db

def run_migration():
    """Run the database migration to create Job Accounting tables."""
    
    print("=" * 60)
    print("Job Accounting Module - Database Migration")
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
        from models import Job, JobIncome, JobExpense
        print("✓ Job Accounting models imported")
        print()
        
        # Check if tables already exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        job_tables = ['ASP_jobs', 'ASP_job_income', 'ASP_job_expenses']
        existing_job_tables = [t for t in job_tables if t in existing_tables]
        
        if existing_job_tables:
            print("⚠️  WARNING: Some Job Accounting tables already exist:")
            for table in existing_job_tables:
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
            db.create_all()
            print("✓ Database tables created successfully!")
            print()
            
            # Verify tables were created
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            print("Verifying table creation:")
            for table in job_tables:
                if table in existing_tables:
                    print(f"   ✓ {table}")
                else:
                    print(f"   ❌ {table} - NOT FOUND")
            print()
            
            # Show table structure
            print("Table Structure Summary:")
            print("-" * 60)
            
            if 'ASP_jobs' in existing_tables:
                columns = inspector.get_columns('ASP_jobs')
                print(f"\nASP_jobs ({len(columns)} columns):")
                for col in columns:
                    print(f"   - {col['name']}: {col['type']}")
            
            if 'ASP_job_income' in existing_tables:
                columns = inspector.get_columns('ASP_job_income')
                print(f"\nASP_job_income ({len(columns)} columns):")
                for col in columns:
                    print(f"   - {col['name']}: {col['type']}")
            
            if 'ASP_job_expenses' in existing_tables:
                columns = inspector.get_columns('ASP_job_expenses')
                print(f"\nASP_job_expenses ({len(columns)} columns):")
                for col in columns:
                    print(f"   - {col['name']}: {col['type']}")
            
            print()
            print("=" * 60)
            print("✅ Migration completed successfully!")
            print("=" * 60)
            print()
            print("Next steps:")
            print("1. Start your Flask application")
            print("2. Navigate to /job-accounting/dashboard")
            print("3. Create your first job and start tracking income/expenses")
            print()
            
        except Exception as e:
            print(f"❌ ERROR during migration: {str(e)}")
            print()
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    run_migration()