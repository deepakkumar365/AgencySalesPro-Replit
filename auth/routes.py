from flask import render_template, redirect, url_for, flash, session, request
from werkzeug.security import check_password_hash, generate_password_hash
from models import User, ActivityLog, Agency
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

            if user.role == 'agency_manager':
                return redirect(url_for('agency_manager.dashboard'))
            elif user.role == 'agency_admin':
                return redirect(url_for('inventory.dashboard'))
                
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
    # Only super_admin and agency_manager can register new users
    if session.get('role') not in ['super_admin', 'agency_manager']:
        flash('You do not have permission to register new users.', 'error')
        return redirect(url_for('index'))

    if request.method == 'POST':
        # Collect form data
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        role = request.form.get('role')
        agency_id = request.form.get('agency_id')

        # Basic validation
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('auth.register'))

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'error')
            return redirect(url_for('auth.register'))

        # Check for existing user
        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'error')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'error')
            return redirect(url_for('auth.register'))

        # Create new user
        new_user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            agency_id=agency_id if agency_id else None,
            is_active=True
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash(f'User {username} registered successfully!', 'success')
        return redirect(url_for('super_admin.manage_users'))

    # For GET request, provide agencies for the dropdown
    agencies = []
    if session.get('role') == 'super_admin':
        agencies = Agency.query.order_by(Agency.name).all()
    elif session.get('role') == 'agency_manager':
        agencies = Agency.query.filter_by(agency_manager_id=session.get('user_id')).order_by(Agency.name).all()

    return render_template('auth/register.html', agencies=agencies)