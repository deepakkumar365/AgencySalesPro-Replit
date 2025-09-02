#!/bin/bash
# Render deployment startup script

# Set environment variables with defaults
export FLASK_ENV=${FLASK_ENV:-production}
export PORT=${PORT:-5000}

# Create database tables if they don't exist
python -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database tables created successfully')
"

# Start the application with gunicorn
exec gunicorn --config gunicorn.conf.py main:app