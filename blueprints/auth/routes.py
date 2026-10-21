from email_validator import validate_email, EmailNotValidError
from urllib.parse import urlsplit
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, limiter
from models import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def is_safe_url(target):
    if not target or not isinstance(target, str):
        return False
    if target.startswith('//') or target.startswith('\\\\'):
        return False
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return False
    return target.startswith('/')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form_data = {
        'name': '',
        'email': '',
        'role': 'farmer',
        'phone': '',
        'location': ''
    }

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        role = request.form.get('role', 'farmer')
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()

        form_data = {
            'name': name,
            'email': email,
            'role': role,
            'phone': phone,
            'location': location
        }

        if not name or not email or not password:
            flash('All required fields must be filled.', 'error')
            return render_template('auth/register.html', form_data=form_data)

        # Validate email format using email-validator
        try:
            valid_info = validate_email(email, check_deliverability=False)
            email = valid_info.normalized
            form_data['email'] = email
        except EmailNotValidError:
            flash('Please enter a valid email address.', 'error')
            return render_template('auth/register.html', form_data=form_data)

        # Enforce minimum 8-character password server-side
        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/register.html', form_data=form_data)

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html', form_data=form_data)

        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return render_template('auth/register.html', form_data=form_data)

        if role not in ('farmer', 'buyer'):
            flash('Invalid role selected.', 'error')
            return render_template('auth/register.html', form_data=form_data)

        user = User(name=name, email=email, role=role, phone=phone, location=location)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form_data=form_data)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            if not is_safe_url(next_page):
                next_page = url_for('dashboard.index')
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(next_page)
        flash('Invalid email or password.', 'error')
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))