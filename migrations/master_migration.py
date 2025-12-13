#!/usr/bin/env python3
"""
Master Migration Runner - Consolidates all database migrations
Follows best practices: error handling, logging, idempotency, and ethical data handling

Author: Development Team
Purpose: Execute all pending migrations in proper sequence with full rollback support
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Optional
from contextlib import contextmanager

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from extensions import db
from app import create_app
from models import Role, Permission, RolePermission, MenuItem, User

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

def setup_logging():
    """Configure logging with both file and console output"""
    log_dir = Path(__file__).parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Create file handler which logs even debug messages
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.INFO)
    
    # Create console handler with a higher log level
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    
    # Create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    # Add the handlers to the logger
    # Check if handlers already exist to avoid duplicates if re-imported
    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)
    
    return logger

logger = setup_logging()


# ============================================================================
# CONTEXT MANAGERS FOR TRANSACTION HANDLING
# ============================================================================

@contextmanager
def migration_transaction():
    """
    Context manager for safe transaction handling with automatic rollback on errors
    Ensures data integrity following ethical database practices
    """
    try:
        yield
        db.session.commit()
        logger.info("✓ Transaction committed successfully")
    except Exception as e:
        db.session.rollback()
        logger.error(f"✗ Transaction failed. Rolling back all changes: {str(e)}")
        raise


# ============================================================================
# SCHEMA MIGRATIONS (Tables and Columns)
# ============================================================================

class SchemaMigrations:
    """Handles all database schema changes with idempotency checks"""
    
    @staticmethod
    def check_column_exists(table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            query = f"""
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = '{table_name}' AND column_name = '{column_name}'
            """
            result = db.session.execute(db.text(query)).fetchone()
            return result is not None
        except Exception as e:
            logger.warning(f"Could not check column existence: {str(e)}")
            return False
    
    @staticmethod
    def check_table_exists(table_name: str) -> bool:
        """Check if a table exists"""
        try:
            query = f"""
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = '{table_name}'
            """
            result = db.session.execute(db.text(query)).fetchone()
            return result is not None
        except Exception as e:
            logger.warning(f"Could not check table existence: {str(e)}")
            return False

    @staticmethod
    def create_rbac_tables():
        """Create RBAC-related tables if they don't exist"""
        logger.info("▶ Creating RBAC schema tables...")
        
        with migration_transaction():
            # Create ASP_roles table
            if not SchemaMigrations.check_table_exists('ASP_roles'):
                logger.info("  Creating ASP_roles table...")
                db.session.execute(db.text("""
                    CREATE TABLE "ASP_roles" (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(50) UNIQUE NOT NULL,
                        description TEXT,
                        is_system BOOLEAN DEFAULT FALSE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                logger.info("  ✓ ASP_roles table created")
            else:
                logger.info("  ⊘ ASP_roles table already exists")
            
            # Create ASP_permissions table
            if not SchemaMigrations.check_table_exists('ASP_permissions'):
                logger.info("  Creating ASP_permissions table...")
                db.session.execute(db.text("""
                    CREATE TABLE "ASP_permissions" (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) UNIQUE NOT NULL,
                        code VARCHAR(100) UNIQUE NOT NULL,
                        description TEXT,
                        category VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                logger.info("  ✓ ASP_permissions table created")
            else:
                logger.info("  ⊘ ASP_permissions table already exists")
            
            # Create ASP_role_permissions table
            if not SchemaMigrations.check_table_exists('ASP_role_permissions'):
                logger.info("  Creating ASP_role_permissions table...")
                db.session.execute(db.text("""
                    CREATE TABLE "ASP_role_permissions" (
                        id SERIAL PRIMARY KEY,
                        role_id INTEGER NOT NULL REFERENCES "ASP_roles"(id) ON DELETE CASCADE,
                        permission_id INTEGER NOT NULL REFERENCES "ASP_permissions"(id) ON DELETE CASCADE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_role_permission UNIQUE (role_id, permission_id)
                    )
                """))
                logger.info("  ✓ ASP_role_permissions table created")
            else:
                logger.info("  ⊘ ASP_role_permissions table already exists")
            
            # Create ASP_menu_items table
            if not SchemaMigrations.check_table_exists('ASP_menu_items'):
                logger.info("  Creating ASP_menu_items table...")
                db.session.execute(db.text("""
                    CREATE TABLE "ASP_menu_items" (
                        id SERIAL PRIMARY KEY,
                        parent_id INTEGER REFERENCES "ASP_menu_items"(id) ON DELETE CASCADE,
                        name VARCHAR(100) NOT NULL,
                        url VARCHAR(255),
                        icon VARCHAR(50),
                        order_index INTEGER DEFAULT 0,
                        required_permission_code VARCHAR(100) REFERENCES "ASP_permissions"(code) ON DELETE SET NULL,
                        dashboard_for_role VARCHAR(50),
                        is_active BOOLEAN DEFAULT TRUE
                    )
                """))
                logger.info("  ✓ ASP_menu_items table created")
            else:
                logger.info("  ⊘ ASP_menu_items table already exists")

    @staticmethod
    def add_role_id_column_to_users():
        """Add role_id column to ASP_users if it doesn't exist"""
        logger.info("▶ Adding role_id column to ASP_users...")
        
        if SchemaMigrations.check_column_exists('ASP_users', 'role_id'):
            logger.info("  ⊘ role_id column already exists in ASP_users")
            return
        
        with migration_transaction():
            logger.info("  Adding role_id column...")
            db.session.execute(db.text("""
                ALTER TABLE "ASP_users" 
                ADD COLUMN role_id INTEGER REFERENCES "ASP_roles"(id) ON DELETE SET NULL
            """))
            
            logger.info("  Creating index for role_id...")
            db.session.execute(db.text("""
                CREATE INDEX idx_users_role_id ON "ASP_users"(role_id)
            """))
            
            logger.info("  ✓ role_id column and index created")

    @staticmethod
    def migrate_quantity_types():
        """
        Migrate quantity columns from INTEGER to NUMERIC
        Ensures consistency with models.py definitions
        """
        logger.info("▶ Migrating quantity columns to NUMERIC types...")
        
        migrations = [
            # table, column, type
            ('ASP_order_items', 'quantity', 'NUMERIC(10, 3)'),
            ('ASP_purchase_order_items', 'quantity_ordered', 'NUMERIC(10, 2)'),
            ('ASP_purchase_order_items', 'quantity_received', 'NUMERIC(10, 2)'),
            ('ASP_invoice_items', 'quantity', 'NUMERIC(10, 3)'),
            ('ASP_delivery_challan_items', 'quantity', 'NUMERIC(10, 3)')
        ]
        
        with migration_transaction():
            count = 0
            for table, column, type_def in migrations:
                # Check if table exists first
                if not SchemaMigrations.check_table_exists(table):
                    continue
                
                # We blindly alter type - Postgres handles this gracefully if valid cast exists
                # Using 'USING column::type' clause to ensure proper casting
                logger.info(f"  Migrating {table}.{column} to {type_def}...")
                
                # Check current type first to avoid unnecessary alters (optimization)
                # But simple ALTER is fine too.
                try:
                    db.session.execute(db.text(f"""
                        ALTER TABLE "{table}" 
                        ALTER COLUMN {column} TYPE {type_def}
                    """))
                    count += 1
                except Exception as e:
                    logger.warning(f"  ⚠ Could not migrate {table}.{column}: {e}")
            
            logger.info(f"  ✓ Quantity type migrations executed for {count} columns")


    @staticmethod
    def add_product_name_column_to_purchase_order_items():
        """Add product_name column to ASP_purchase_order_items if missing"""
        if SchemaMigrations.check_column_exists('ASP_purchase_order_items', 'product_name'):
            logger.info("  ⊘ product_name column already exists in ASP_purchase_order_items")
            return
        logger.info("▶ Adding product_name column to ASP_purchase_order_items...")
        with migration_transaction():
            db.session.execute(db.text(
                """
                ALTER TABLE \"ASP_purchase_order_items\" 
                ADD COLUMN product_name VARCHAR(150)
                """
            ))
            logger.info("  ✓ product_name column added to ASP_purchase_order_items")

# ============================================================================
# DATA MIGRATIONS (Populate tables with seed data)
# ============================================================================

class DataMigrations:
    """Handles all data population and updates"""
    
    @staticmethod
    def populate_system_roles():
        """
        Populate system roles following ethical practices:
        - Idempotent: Won't create duplicates
        - Documented: Each role has clear description
        - Auditable: Uses created_at timestamp
        """
        logger.info("▶ Populating system roles...")
        
        with migration_transaction():
            roles_data = [
                {
                    'name': 'super_admin',
                    'description': 'Full Tenant/Agency/User Management (view-only), no Inventory/Sales/Reports/Forecasting',
                    'is_system': True
                },
                {
                    'name': 'support',
                    'description': 'Full access to all features (support team)',
                    'is_system': True
                },
                {
                    'name': 'agency_manager',
                    'description': 'Full control within managed agencies, View-only Tenant Management',
                    'is_system': True
                },
                {
                    'name': 'agency_admin',
                    'description': 'Full agency operations, Limited Agency/Payment Config management',
                    'is_system': True
                },
                {
                    'name': 'staff',
                    'description': 'Operational role - Full Inventory/Sales, View Forecasting, Limited Reports',
                    'is_system': True
                },
                {
                    'name': 'salesperson',
                    'description': 'Sales-focused - manage orders, view inventory',
                    'is_system': True
                },
                {
                    'name': 'pos_user',
                    'description': 'POS terminal user - access POS, billing, basic orders',
                    'is_system': True
                },
                {
                    'name': 'accountant',
                    'description': 'Finance role - View Inventory/Sales, Full Reports, View Payment Config',
                    'is_system': True
                }
            ]
            
            created_count = 0
            for role_data in roles_data:
                existing_role = Role.query.filter_by(name=role_data['name']).first()
                
                if existing_role:
                    logger.info(f"  ⊘ Role '{role_data['name']}' already exists")
                else:
                    role = Role(**role_data)
                    db.session.add(role)
                    created_count += 1
                    logger.info(f"  + Created role: {role_data['name']}")
            
            logger.info(f"  ✓ System roles populated ({created_count} new roles created)")
    
    @staticmethod
    def populate_permissions():
        """
        Populate system permissions with proper categorization
        Follows principle of least privilege and clear permission semantics
        """
        logger.info("▶ Populating system permissions...")
        
        with migration_transaction():
            permissions_data = [
                # Agency Permissions
                {'name': 'Manage Agencies', 'code': 'agency.manage', 'category': 'Agency'},
                {'name': 'View Agencies', 'code': 'agency.view', 'category': 'Agency'},
                
                # User Permissions
                {'name': 'Manage Users', 'code': 'user.manage', 'category': 'User'},
                {'name': 'View Users', 'code': 'user.view', 'category': 'User'},
                
                # Inventory Permissions
                {'name': 'Manage Inventory', 'code': 'inventory.manage', 'category': 'Inventory'},
                {'name': 'View Inventory', 'code': 'inventory.view', 'category': 'Inventory'},
                
                # Billing Permissions
                {'name': 'Manage Billing', 'code': 'billing.manage', 'category': 'Billing'},
                {'name': 'View Billing', 'code': 'billing.view', 'category': 'Billing'},
                {'name': 'View Billing Dashboard', 'code': 'billing.view_dashboard', 'category': 'Billing'},
                
                # Report Permissions
                {'name': 'Manage Reports', 'code': 'report.manage', 'category': 'Report'},
                {'name': 'View Reports', 'code': 'report.view', 'category': 'Report'},
                
                # Order Permissions
                {'name': 'Manage Orders', 'code': 'order.manage', 'category': 'Order'},
                {'name': 'View Orders', 'code': 'order.view', 'category': 'Order'},
                
                # Customer Permissions
                {'name': 'Manage Customers', 'code': 'customer.manage', 'category': 'Customer'},
                {'name': 'View Customers', 'code': 'customer.view', 'category': 'Customer'},
                
                # Location Permissions
                {'name': 'Manage Locations', 'code': 'location.manage', 'category': 'Location'},
                {'name': 'View Locations', 'code': 'location.view', 'category': 'Location'},
                
                # POS Permissions
                {'name': 'Access POS', 'code': 'pos.access', 'category': 'POS'},
                
                # Forecasting Permissions
                {'name': 'View Forecasting', 'code': 'forecasting.view', 'category': 'Forecasting'},
                
                # Role Permissions
                {'name': 'Manage Roles', 'code': 'role.manage', 'category': 'Role'},
                
                # System Permissions
                {'name': 'View All Data', 'code': 'system.view_all_data', 'category': 'System'},
            ]
            
            created_count = 0
            for perm_data in permissions_data:
                existing_perm = Permission.query.filter_by(code=perm_data['code']).first()
                
                if existing_perm:
                    logger.info(f"  ⊘ Permission '{perm_data['code']}' already exists")
                else:
                    perm = Permission(**perm_data)
                    db.session.add(perm)
                    created_count += 1
                    logger.info(f"  + Created permission: {perm_data['code']}")
            
            logger.info(f"  ✓ Permissions populated ({created_count} new permissions created)")
    
    @staticmethod
    def assign_permissions_to_roles():
        """
        Assign permissions to roles following principle of least privilege
        Each role gets only the permissions it needs
        """
        logger.info("▶ Assigning permissions to roles...")
        
        with migration_transaction():
            # Build lookup dictionaries for efficient access
            roles_dict = {role.name: role for role in Role.query.all()}
            perms_dict = {perm.code: perm for perm in Permission.query.all()}
            
            # Define role-permission mapping with minimum required permissions
            role_permissions_map = {
                'super_admin': [
                    'agency.manage', 'agency.view', 'user.view', 'system.view_all_data',
                    'billing.view', 'role.manage', 'customer.manage', 'location.manage'
                ],
                'support': [
                    'agency.manage', 'agency.view', 'user.manage', 'user.view', 'system.view_all_data',
                    'pos.access', 'inventory.manage', 'inventory.view', 'billing.manage', 'billing.view',
                    'report.manage', 'report.view', 'role.manage', 'order.manage', 'customer.manage',
                    'location.manage', 'forecasting.view'
                ],
                'agency_manager': [
                    'agency.manage', 'user.manage', 'user.view', 'inventory.manage', 'inventory.view',
                    'billing.view', 'report.view', 'order.manage', 'customer.manage', 'location.manage',
                    'forecasting.view'
                ],
                'agency_admin': [
                    'user.manage', 'user.view', 'inventory.manage', 'inventory.view',
                    'billing.manage', 'billing.view', 'report.view', 'order.manage',
                    'customer.manage', 'location.manage', 'forecasting.view'
                ],
                'staff': [
                    'inventory.manage', 'inventory.view', 'pos.access', 'order.manage',
                    'customer.view', 'location.view', 'forecasting.view'
                ],
                'salesperson': [
                    'order.manage', 'customer.manage', 'inventory.view', 'location.view'
                ],
                'pos_user': [
                    'pos.access', 'inventory.view', 'order.manage', 'billing.manage',
                    'customer.view', 'location.view'
                ],
                'accountant': [
                    'inventory.view', 'billing.view', 'report.manage', 'report.view',
                    'order.view', 'customer.view'
                ]
            }
            
            assigned_count = 0
            for role_name, perm_codes in role_permissions_map.items():
                role = roles_dict.get(role_name)
                if not role:
                    logger.warning(f"  ⚠ Role '{role_name}' not found, skipping permission assignment")
                    continue
                
                for code in perm_codes:
                    perm = perms_dict.get(code)
                    if not perm:
                        logger.warning(f"  ⚠ Permission '{code}' not found for role '{role_name}'")
                        continue
                    
                    # Check if permission is already assigned (avoid duplicates)
                    existing = RolePermission.query.filter_by(
                        role_id=role.id,
                        permission_id=perm.id
                    ).first()
                    
                    if not existing:
                        role.permissions.append(perm)
                        assigned_count += 1
                        logger.info(f"  + Assigned {code} to {role_name}")
            
            logger.info(f"  ✓ Permissions assigned ({assigned_count} new assignments)")
    
    @staticmethod
    def update_existing_users_role_ids():
        """
        Update existing users with role_id based on their legacy role string
        Follows ethical data handling: preserves existing user data while adding new relationships
        """
        logger.info("▶ Updating existing users with role_id...")
        
        with migration_transaction():
            # Build role lookup dictionary
            roles_dict = {role.name: role.id for role in Role.query.all()}
            
            users_to_update = User.query.filter(
                User.role_id.is_(None),
                User.role.isnot(None)
            ).all()
            
            updated_count = 0
            for user in users_to_update:
                if user.role in roles_dict:
                    user.role_id = roles_dict[user.role]
                    updated_count += 1
                    logger.info(f"  + Updated user '{user.username}' with role_id for role '{user.role}'")
                else:
                    logger.warning(f"  ⚠ User '{user.username}' has unknown role '{user.role}'")
            
            logger.info(f"  ✓ User role_ids updated ({updated_count} users updated)")


# ============================================================================
# MIGRATION ORCHESTRATION
# ============================================================================

class MigrationRunner:
    """
    Main migration orchestrator following best practices:
    - Transaction management with rollback on failure
    - Idempotent operations (safe to run multiple times)
    - Comprehensive logging for audit trail
    - Clear status reporting
    """
    
    def __init__(self):
        self.app = None
        self.start_time = None
        self.end_time = None
        self.errors: List[Tuple[str, str]] = []
    
    def initialize(self):
        """Initialize Flask app context"""
        logger.info("=" * 80)
        logger.info("MASTER MIGRATION RUNNER - Starting")
        logger.info("=" * 80)
        logger.info("")
        
        self.app = create_app()
        self.start_time = datetime.now()
    
    def run_all_migrations(self) -> bool:
        """Execute all migrations in proper sequence"""
        try:
            with self.app.app_context():
                logger.info("Step 0/4: Ensuring base tables exist (db.create_all)...")
                db.create_all()
                logger.info("  ✓ Base tables verified/created")
                logger.info("")

                logger.info("Step 1/4: Creating RBAC schema tables...")
                SchemaMigrations.create_rbac_tables()
                
                logger.info("")
                logger.info("Step 2/4: Schema Updates (Columns & Types)...")
                SchemaMigrations.add_role_id_column_to_users()
                SchemaMigrations.migrate_quantity_types()
                SchemaMigrations.add_product_name_column_to_purchase_order_items()
                
                logger.info("")
                logger.info("Step 3/4: Populating system data...")
                DataMigrations.populate_system_roles()
                DataMigrations.populate_permissions()
                DataMigrations.assign_permissions_to_roles()
                
                logger.info("")
                logger.info("Step 4/4: Updating existing users...")
                DataMigrations.update_existing_users_role_ids()
                
                self.end_time = datetime.now()
                return True
        
        except Exception as e:
            self.end_time = datetime.now()
            error_msg = f"Migration failed: {str(e)}"
            logger.error(f"✗ {error_msg}")
            self.errors.append(("Migration Execution", str(e)))
            return False
    
    def print_summary(self):
        """Print migration execution summary"""
        duration = (self.end_time - self.start_time).total_seconds()
        
        logger.info("")
        logger.info("=" * 80)
        
        if not self.errors:
            logger.info("✓ MIGRATION COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info("")
            logger.info("📋 Migration Summary:")
            logger.info("  ✓ RBAC schema tables created/verified")
            logger.info("  ✓ role_id column added to ASP_users")
            logger.info("  ✓ System roles populated")
            logger.info("  ✓ System permissions populated")
            logger.info("  ✓ Role-permission assignments completed")
            logger.info("  ✓ Existing users updated with role_ids")
            logger.info("")
            logger.info("🚀 Next Steps:")
            logger.info("  1. Restart your Flask application")
            logger.info("  2. Test login functionality")
            logger.info("  3. Verify user roles are properly assigned")
            logger.info("  4. Check application logs for any warnings")
        else:
            logger.error("✗ MIGRATION FAILED")
            logger.error("=" * 80)
            logger.error(f"Duration: {duration:.2f} seconds")
            logger.error("")
            logger.error("Errors encountered:")
            for step, error in self.errors:
                logger.error(f"  [{step}] {error}")
        
        logger.info("=" * 80)
        logger.info(f"Log file saved to: {Path(__file__).parent / 'logs'}")
        logger.info("")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main entry point with proper exit code handling"""
    try:
        runner = MigrationRunner()
        runner.initialize()
        
        success = runner.run_all_migrations()
        runner.print_summary()
        
        return 0 if success else 1
    
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())