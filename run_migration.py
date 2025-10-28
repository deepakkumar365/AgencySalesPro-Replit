#!/usr/bin/env python
"""
Script to run the role_id column migration
"""
import os
import sys
from dotenv import load_dotenv

# Must load env before importing app
load_dotenv()

# Import database connection AFTER loading env
from extensions import db
from app import create_app

def run_migration():
    """Execute the role_id migration"""
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sql_file = os.path.join(script_dir, 'fix_role_id_column.sql')
        
        with open(sql_file, 'r') as f:
            sql = f.read()
        
        # Execute the SQL
        db.session.execute(db.text(sql))
        db.session.commit()
        
        print("✅ Migration successful! role_id column has been restored.")
        return True
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        db.session.rollback()
        return False

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        success = run_migration()
        sys.exit(0 if success else 1)