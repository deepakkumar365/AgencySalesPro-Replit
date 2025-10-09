from flask import render_template, redirect, url_for, flash, session, request
from werkzeug.security import check_password_hash, generate_password_hash
from models import User, ActivityLog, Agency, Subscription
from extensions import db
from utils.email_service import email_service
import random
import string
from datetime import datetime, timedelta

# Use the auth blueprint defined in __init__.py
from . import auth_bp
from .utils import login_required


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
    if session.get('role') not in ['super_admin', 'agency_manager', 'agency_admin']:
        flash('You do not have permission to perform this action.', 'error')
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
        agencies = Agency.query.filter_by(manager_id=session.get('user_id')).order_by(Agency.name).all()
    elif session.get('role') == 'agency_admin':
        agencies = Agency.query.filter_by(id=session.get('agency_id')).all()

    return render_template('auth/register.html', agencies=agencies)

@auth_bp.route('/profile')
@login_required
def profile():
    """
    Displays a common user profile page with user details,
    recent activity, and subscription info for agency admins.
    """
    user_id = session.get('user_id')
    user = User.query.get_or_404(user_id)
    
    # Get the agency's subscription if the user belongs to an agency
    user_subscription = None
    if user.role == 'customer' and user.customer_rel:
        # For customers, find subscription via their customer record
        user_subscription = Subscription.query.filter_by(customer_id=user.customer_rel.id).first()
    elif user.agency_id:
        # For agency users, find subscription via their agency
        user_subscription = Subscription.query.filter_by(agency_id=user.agency_id).first()
    return render_template('auth/profile.html', 
                           user=user, 
                           subscription=user_subscription) # This was the issue, the variable name was correct. Let's check the template.


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    Forgot password page - sends OTP to user's email
    """
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Email is required', 'error')
            return redirect(url_for('auth.forgot_password'))
        
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate 6-digit OTP
            otp = ''.join(random.choices(string.digits, k=6))
            
            # Store OTP in session with expiry (10 minutes)
            session['reset_otp'] = otp
            session['reset_email'] = email
            session['otp_expiry'] = (datetime.now() + timedelta(minutes=10)).isoformat()
            
            # Send OTP via email
            email_sent = email_service.send_otp_email(
                to_email=email,
                otp=otp,
                user_name=user.full_name or user.username
            )
            
            if email_sent:
                flash('OTP has been sent to your email address.', 'success')
            else:
                # Fallback for development/testing when email is disabled
                flash(f'Email service not configured. OTP: {otp} (Valid for 10 minutes)', 'warning')
            
            return redirect(url_for('auth.reset_password'))
        else:
            # Don't reveal if email exists or not for security
            flash('If the email exists, an OTP has been sent.', 'info')
            return redirect(url_for('auth.forgot_password'))
    
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    """
    Reset password page - verifies OTP and allows password reset
    """
    if 'reset_email' not in session:
        flash('Please request a password reset first.', 'error')
        return redirect(url_for('auth.forgot_password'))
    
    # Check if OTP has expired
    if 'otp_expiry' in session:
        expiry = datetime.fromisoformat(session['otp_expiry'])
        if datetime.now() > expiry:
            session.pop('reset_otp', None)
            session.pop('reset_email', None)
            session.pop('otp_expiry', None)
            flash('OTP has expired. Please request a new one.', 'error')
            return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not otp or not new_password or not confirm_password:
            flash('All fields are required', 'error')
            return redirect(url_for('auth.reset_password'))
        
        if otp != session.get('reset_otp'):
            flash('Invalid OTP', 'error')
            return redirect(url_for('auth.reset_password'))
        
        if new_password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('auth.reset_password'))
        
        if len(new_password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return redirect(url_for('auth.reset_password'))
        
        # Update password
        user = User.query.filter_by(email=session['reset_email']).first()
        if user:
            user.set_password(new_password)
            db.session.commit()
            
            # Clear session data
            session.pop('reset_otp', None)
            session.pop('reset_email', None)
            session.pop('otp_expiry', None)
            
            flash('Password reset successfully! Please login with your new password.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('User not found', 'error')
            return redirect(url_for('auth.forgot_password'))
    
    return render_template('auth/reset_password.html', email=session.get('reset_email'))