from flask import render_template, redirect, url_for, flash, session, request

# Use the auth blueprint defined in __init__.py
from . import auth_bp


@auth_bp.route('/login', methods=['GET'])
def login():
    # Minimal placeholder to satisfy url_for('auth.login') references
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