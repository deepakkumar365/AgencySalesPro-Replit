#!/usr/bin/env python
"""Verify all endpoints referenced in templates exist in the app."""

import sys
import os
import re

# Set up environment
os.environ['FLASK_ENV'] = 'testing'
os.environ['SESSION_SECRET'] = 'test-secret'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from app import create_app

def extract_endpoints_from_template(template_path):
    """Extract all url_for endpoints from a template file."""
    endpoints = set()
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Find all url_for calls
            matches = re.findall(r"url_for\(['\"]([^'\"]+)['\"]", content)
            endpoints.update(matches)
    except Exception as e:
        print(f"Error reading {template_path}: {e}")
    
    return endpoints

def get_available_endpoints(app):
    """Get all available endpoints from Flask app."""
    endpoints = set()
    with app.app_context():
        for rule in app.url_map.iter_rules():
            endpoints.add(rule.endpoint)
    return endpoints

def main():
    """Main verification function."""
    app = create_app()
    
    print("=" * 60)
    print("Endpoint Verification Report")
    print("=" * 60)
    
    # Get template endpoints
    template_file = 'templates/base.html'
    if not os.path.exists(template_file):
        print(f"ERROR: Template file not found: {template_file}")
        return False
    
    template_endpoints = extract_endpoints_from_template(template_file)
    print(f"\n✓ Found {len(template_endpoints)} unique endpoints in templates")
    
    # Get available endpoints
    available_endpoints = get_available_endpoints(app)
    print(f"✓ Found {len(available_endpoints)} available endpoints in app")
    
    # Check for missing endpoints
    missing = template_endpoints - available_endpoints
    
    if missing:
        print(f"\n✗ MISSING ENDPOINTS ({len(missing)}):")
        for endpoint in sorted(missing):
            print(f"  - {endpoint}")
        return False
    else:
        print(f"\n✓ All template endpoints are available!")
        print(f"\nEndpoints used in templates:")
        for endpoint in sorted(template_endpoints):
            print(f"  ✓ {endpoint}")
        return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)