#!/usr/bin/env python3
"""
Migration Executor - Simple CLI to run database migrations
Execute all pending migrations with a single command

Usage:
    python run_migrations.py
    python run_migrations.py --help
"""

import sys
import argparse
from pathlib import Path

# Force UTF-8 encoding for stdout/stderr to handle emojis on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Add migrations to path
sys.path.insert(0, str(Path(__file__).parent))

from migrations.master_migration import MigrationRunner, logger


def print_header():
    """Print welcome header"""
    print("\n" + "=" * 80)
    print("🗄️  AgencySalesPro - Database Migration Runner")
    print("=" * 80 + "\n")


def print_instructions():
    """Print pre-migration instructions"""
    print("📋 IMPORTANT BEFORE PROCEEDING:")
    print("-" * 80)
    print("1. ✓ Ensure your DATABASE_URL environment variable is set")
    print("2. ✓ Backup your database before running migrations")
    print("3. ✓ Ensure no other processes are modifying the database")
    print("4. ✓ Review the migration log afterwards")
    print("-" * 80 + "\n")


def confirm_migration():
    """Ask user for confirmation before running migration"""
    print("Ready to execute migrations?")
    response = input("Type 'YES' to proceed or 'NO' to cancel: ").strip().upper()
    return response == 'YES'


def run_migrations():
    """Execute migrations"""
    print_header()
    print_instructions()
    
    if not confirm_migration():
        print("❌ Migration cancelled by user.")
        return 1
    
    print("🔄 Executing migrations...\n")
    
    runner = MigrationRunner()
    runner.initialize()
    
    success = runner.run_all_migrations()
    runner.print_summary()
    
    return 0 if success else 1


def show_help():
    """Show help message"""
    print_header()
    print("USAGE:")
    print("  python run_migrations.py          Run all pending migrations")
    print("  python run_migrations.py --help   Show this help message")
    print("  python run_migrations.py --dry    Show what would be migrated (dry-run)")
    print("\n")
    print("MIGRATION STEPS:")
    print("  1. Creates RBAC schema tables (roles, permissions, etc.)")
    print("  2. Adds role_id column to ASP_users table")
    print("  3. Populates system roles and permissions")
    print("  4. Assigns permissions to roles")
    print("  5. Updates existing users with role_ids")
    print("\n")
    print("LOG FILES:")
    print(f"  Location: {Path(__file__).parent / 'migrations' / 'logs'}")
    print("\n")


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description='AgencySalesPro Database Migration Runner',
        add_help=False
    )
    parser.add_argument('--help', action='store_true', help='Show help message')
    parser.add_argument('--dry', action='store_true', help='Dry-run (show what would be migrated)')
    
    args = parser.parse_args()
    
    if args.help:
        show_help()
        return 0
    
    if args.dry:
        print_header()
        print("🔍 DRY-RUN MODE: Showing migration plan (no changes will be made)\n")
        print("MIGRATION PLAN:")
        print("  1. ✓ Create/Verify RBAC schema tables")
        print("     - ASP_roles")
        print("     - ASP_permissions")
        print("     - ASP_role_permissions")
        print("     - ASP_menu_items")
        print("")
        print("  2. ✓ Add role_id column to ASP_users (if not exists)")
        print("     - Add column with FK to ASP_roles")
        print("     - Create index for performance")
        print("")
        print("  3. ✓ Populate system data")
        print("     - Insert 8 system roles")
        print("     - Insert 21 system permissions")
        print("     - Assign permissions to roles")
        print("")
        print("  4. ✓ Update existing users")
        print("     - Link users to roles via role_id")
        print("")
        print("Run without --dry flag to execute: python run_migrations.py")
        print("=" * 80 + "\n")
        return 0
    
    try:
        return run_migrations()
    except KeyboardInterrupt:
        print("\n⚠️  Migration interrupted by user.")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())