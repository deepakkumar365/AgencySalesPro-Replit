from flask import render_template, redirect, url_for, flash, session, request
from werkzeug.security import check_password_hash
from models import User, ActivityLog
from app import db

# Use the auth blueprint defined in __init__.py
from . import auth_bp


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Username and password are required', 'error')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Your account is inactive. Please contact an administrator.', 'error')
                return redirect(url_for('auth.login'))

            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['agency_id'] = user.agency_id
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Minimal placeholder to satisfy url_for('auth.register') references
    if request.method == 'POST':
        flash('Registration is currently disabled. Please contact the administrator.', 'warning')
        return redirect(url_for('auth.login'))
    return render_template('auth/register.html')