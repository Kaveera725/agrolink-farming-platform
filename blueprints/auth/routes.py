from datetime import datetime
from email_validator import validate_email, EmailNotValidError
from urllib.parse import urlsplit
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, limiter
from models import User
from utils.phone import validate_sl_phone, normalize_phone_number
from utils.geo import parse_coord, is_in_sri_lanka

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
        'whatsapp_number': '',
        'phone': '',
        'location': '',
        'latitude': '',
        'longitude': '',
        'address_text': ''
    }

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        role = request.form.get('role', 'farmer')
        whatsapp_number = request.form.get('whatsapp_number', '').strip()
        phone = request.form.get('phone', '').strip()
        location = request.form.get('location', '').strip()
        latitude_raw = request.form.get('latitude', '').strip()
        longitude_raw = request.form.get('longitude', '').strip()
        address_text = request.form.get('address_text', '').strip()

        form_data = {
            'name': name,
            'email': email,
            'role': role,
            'whatsapp_number': whatsapp_number,
            'phone': phone,
            'location': location,
            'latitude': latitude_raw,
            'longitude': longitude_raw,
            'address_text': address_text
        }

        if not name or not email or not password or not whatsapp_number:
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

        # Validate WhatsApp number (required, Sri Lankan E.164)
        is_valid_wa, normalized_wa, wa_err = validate_sl_phone(whatsapp_number)
        if not is_valid_wa:
            flash(wa_err or 'Please enter a valid Sri Lankan WhatsApp number.', 'error')
            return render_template('auth/register.html', form_data=form_data)
        form_data['whatsapp_number'] = normalized_wa

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

        # Location coordinate validation (utils/geo.py)
        parsed_lat = None
        parsed_lng = None

        if role == 'farmer':
            # Farmers MUST have a pin at registration
            if not latitude_raw or not longitude_raw:
                flash('Farmers must pin their farm location on the map so buyers can find you.', 'error')
                return render_template('auth/register.html', form_data=form_data)

            parsed_lat = parse_coord(latitude_raw)
            parsed_lng = parse_coord(longitude_raw)
            if parsed_lat is None or parsed_lng is None:
                flash('Invalid coordinates provided. Please select a valid location on the map.', 'error')
                return render_template('auth/register.html', form_data=form_data)

            if not is_in_sri_lanka(parsed_lat, parsed_lng):
                flash('Location must be within Sri Lanka (latitude 5.8-9.9, longitude 79.4-82.0).', 'error')
                return render_template('auth/register.html', form_data=form_data)
        else:
            # Buyers may skip it at registration
            if latitude_raw or longitude_raw:
                if not latitude_raw or not longitude_raw:
                    flash('Please provide both latitude and longitude or select a location on the map.', 'error')
                    return render_template('auth/register.html', form_data=form_data)

                parsed_lat = parse_coord(latitude_raw)
                parsed_lng = parse_coord(longitude_raw)
                if parsed_lat is None or parsed_lng is None:
                    flash('Invalid coordinates provided. Please select a valid location on the map.', 'error')
                    return render_template('auth/register.html', form_data=form_data)

                if not is_in_sri_lanka(parsed_lat, parsed_lng):
                    flash('Location must be within Sri Lanka (latitude 5.8-9.9, longitude 79.4-82.0).', 'error')
                    return render_template('auth/register.html', form_data=form_data)

        # Normalize optional phone if provided
        normalized_ph = normalize_phone_number(phone) if phone else None

        user = User(
            name=name,
            email=email,
            role=role,
            phone=normalized_ph or phone or None,
            whatsapp_number=normalized_wa,
            location=location or (address_text if address_text else None),
            latitude=parsed_lat,
            longitude=parsed_lng,
            address_text=address_text or None,
            location_updated_at=datetime.utcnow() if parsed_lat is not None else None,
            is_active=True
        )
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
            if not getattr(user, 'is_active', True):
                flash('Your account has been deactivated. Please contact support.', 'error')
                return render_template('auth/login.html')
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