#!/usr/bin/env python
"""
Verification script for Job Accounting Module
Checks imports and basic syntax without running the app
"""

import sys
import py_compile
import os

def verify_file(filepath):
    """Verify a Python file compiles without errors"""
    try:
        py_compile.compile(filepath, doraise=True)
        print(f"✅ {os.path.basename(filepath)} - OK")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ {os.path.basename(filepath)} - ERROR")
        print(f"   {e}")
        return False

def main():
    print("=" * 60)
    print("Job Accounting Module - Verification")
    print("=" * 60)
    print()
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    files_to_check = [
        os.path.join(base_path, 'job_accounting', '__init__.py'),
        os.path.join(base_path, 'job_accounting', 'routes.py'),
        os.path.join(base_path, 'migrate_job_accounting.py'),
        os.path.join(base_path, 'create_sample_jobs.py'),
    ]
    
    print("Checking Python files for syntax errors...")
    print()
    
    all_ok = True
    for filepath in files_to_check:
        if os.path.exists(filepath):
            if not verify_file(filepath):
                all_ok = False
        else:
            print(f"⚠️  {os.path.basename(filepath)} - NOT FOUND")
            all_ok = False
    
    print()
    print("=" * 60)
    
    if all_ok:
        print("✅ All checks passed! Module is ready.")
        print()
        print("Next steps:")
        print("1. Run: python migrate_job_accounting.py")
        print("2. (Optional) Run: python create_sample_jobs.py")
        print("3. Start the app and navigate to /job-accounting/dashboard")
        return 0
    else:
        print("❌ Some checks failed. Please review the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())