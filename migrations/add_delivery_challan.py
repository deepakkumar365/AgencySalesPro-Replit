"""
Migration script to add DeliveryChallan table
Run this script to create the delivery_challans table in the database
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import create_app, db
from models import DeliveryChallan

def migrate():
    """Create the DeliveryChallan table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Create the table
            db.create_all()
            print("✓ DeliveryChallan table created successfully!")
            
            # Verify table exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'ASP_delivery_challans' in tables:
                print("✓ Table 'ASP_delivery_challans' verified in database")
                
                # Show table columns
                columns = inspector.get_columns('ASP_delivery_challans')
                print("\nTable columns:")
                for col in columns:
                    print(f"  - {col['name']}: {col['type']}")
            else:
                print("✗ Table 'ASP_delivery_challans' not found in database")
                
        except Exception as e:
            print(f"✗ Error creating table: {str(e)}")
            raise

if __name__ == '__main__':
    migrate()