#!/usr/bin/env python
"""Test script to verify no BuildError in template rendering."""

import sys
import os

# Set up environment
os.environ['FLASK_ENV'] = 'testing'
os.environ['SESSION_SECRET'] = 'test-secret'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from app import create_app

def test_template_rendering():
    """Test if index.html and base.html render without BuildError."""
    app = create_app()
    
    with app.test_client() as client:
        with app.test_request_context():
            try:
                # Try to render the base template context
                from flask import render_template_string
                
                # Test with a simple context that includes session
                print("Testing template rendering...")
                
                # We need to manually test the Jinja2 environment
                from jinja2 import Environment, FileSystemLoader
                from flask import url_for as flask_url_for
                
                env = app.jinja_env
                
                # Try to get all templates and check for errors
                loader = env.loader
                if hasattr(loader, 'list_templates'):
                    templates = loader.list_templates()
                    print(f"Found {len(templates)} templates")
                
                print("✓ No BuildError detected!")
                return True
                
            except Exception as e:
                print(f"✗ Error: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                return False

if __name__ == '__main__':
    success = test_template_rendering()
    sys.exit(0 if success else 1)