#!/usr/bin/env python3
"""
Apply RBAC migration: Add role_id column to ASP_users table
and create RBAC-related tables (roles, permissions, etc.)
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from extensions import db
from app import create_app

def apply_migration():
    """Apply the RBAC migration"""
    app = create_app()
    
    with app.app_context():
        try:
            migration_sql = Path(__file__).parent / 'add_rbac_role_id_to_users.sql'
            
            with open(migration_sql, 'r') as f:
                sql_content = f.read()
            
            # Split by semicolons and execute each statement
            statements = [s.strip() for s in sql_content.split(';') if s.strip()]
            
            for i, statement in enumerate(statements, 1):
                print(f"\n[{i}/{len(statements)}] Executing migration step...")
                try:
                    db.session.execute(db.text(statement))
                    db.session.commit()
                    print(f"✓ Step {i} completed successfully")
                except Exception as e:
                    print(f"⚠ Step {i}: {str(e)}")
                    db.session.rollback()
            
            print("\n" + "="*60)
            print("✓ RBAC migration completed successfully!")
            print("="*60)
            print("\nNext steps:")
            print("1. Restart your Flask application")
            print("2. If using PostgreSQL, verify the new columns are present")
            print("3. Run populate_permissions.py to seed system permissions")
            
            return True
            
        except Exception as e:
            print(f"\n✗ Error during migration: {str(e)}")
            return False

if __name__ == '__main__':
    success = apply_migration()
    sys.exit(0 if success else 1)