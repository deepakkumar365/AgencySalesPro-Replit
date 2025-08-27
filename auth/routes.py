from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from app import db
from models import User, Agency, ActivityLog
from auth import auth_bp
from utils.decorators import log_activity

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(username=username, is_active=True).first()
        
        if user and user.check_password(password):
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Set session
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['agency_id'] = user.agency_id
            
            # Log activity
            log = ActivityLog(
                user_id=user.id,
                action='login',
                description=f'User {user.username} logged in',
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Login successful!', 'success')
            
            # Redirect based on role
            if user.role == 'super_admin':
                return redirect(url_for('super_admin.dashboard'))
            else:
                return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        agency_id = request.form.get('agency_id')
        role = request.form.get('role', 'staff')
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('All required fields must be filled', 'error')
            return render_template('auth/register.html', agencies=Agency.query.filter_by(is_active=True).all())
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/register.html', agencies=Agency.query.filter_by(is_active=True).all())
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('auth/register.html', agencies=Agency.query.filter_by(is_active=True).all())
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return render_template('auth/register.html', agencies=Agency.query.filter_by(is_active=True).all())
        
        # Check permissions
        current_user_id = session.get('user_id')
        if current_user_id:
            current_user = User.query.get(current_user_id)
            if current_user.role not in ['super_admin', 'agency_admin']:
                flash('You do not have permission to register users', 'error')
                return redirect(url_for('index'))
        
        # Create user
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            agency_id=agency_id,
            is_active=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('User registered successfully!', 'success')
        return redirect(url_for('auth.login'))
    
    agencies = Agency.query.filter_by(is_active=True).all()
    return render_template('auth/register.html', agencies=agencies)

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        # Log activity
        log = ActivityLog(
            user_id=user_id,
            action='logout',
            description=f'User logged out',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(log)
        db.session.commit()
    
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/api/token', methods=['POST'])
def get_token():
    """API endpoint for JWT token generation"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user = User.query.filter_by(username=username, is_active=True).first()
    
    if user and user.check_password(password):
        access_token = create_access_token(identity=user.id)
        refresh_token = create_refresh_token(identity=user.id)
        
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'agency_id': user.agency_id
            }
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

@auth_bp.route('/api/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """API endpoint for JWT token refresh"""
    current_user_id = get_jwt_identity()
    access_token = create_access_token(identity=current_user_id)
    return jsonify({'access_token': access_token})
