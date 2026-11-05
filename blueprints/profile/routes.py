from datetime import datetime
from flask import abort, Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from extensions import db
from models import VerificationRequest, DataRequest
from utils.phone import validate_sl_phone, normalize_phone_number
from utils.uploads import save_uploaded_image, delete_uploaded_image
from utils.geo import parse_coord, is_in_sri_lanka
from utils.security import validate_admin_password

profile_bp = Blueprint('profile', __name__, url_prefix='/profile')

SRI_LANKAN_DISTRICTS = [
    "Ampara", "Anuradhapura", "Badulla", "Batticaloa", "Colombo",
    "Galle", "Gampaha", "Hambantota", "Jaffna", "Kalutara",
    "Kandy", "Kegalle", "Kilinochchi", "Kurunegala", "Mannar",
    "Matale", "Matara", "Monaragala", "Mullaitivu", "Nuwara Eliya",
    "Polonnaruwa", "Puttalam", "Ratnapura", "Trincomalee", "Vavuniya"
]


@profile_bp.route('/')
@profile_bp.route('')
@login_required
def view():
    """View the current user's profile."""
    latest_verification_request = None
    if current_user.role == 'farmer':
        latest_verification_request = VerificationRequest.query.filter_by(
            farmer_id=current_user.id
        ).order_by(VerificationRequest.created_at.desc()).first()
    data_requests = DataRequest.query.filter_by(
        user_id=current_user.id
    ).order_by(DataRequest.created_at.desc()).all()
    return render_template(
        'profile/view.html',
        user=current_user,
        latest_verification_request=latest_verification_request,
        data_requests=data_requests
    )


@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    """Edit current user's profile details."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        whatsapp_number = request.form.get('whatsapp_number', '').strip()
        location = request.form.get('location', '').strip()
        latitude_raw = request.form.get('latitude', '').strip()
        longitude_raw = request.form.get('longitude', '').strip()
        address_text = request.form.get('address_text', '').strip()
        farm_name = request.form.get('farm_name', '').strip() if current_user.role == 'farmer' else None
        bio = request.form.get('bio', '').strip() if current_user.role == 'farmer' else None

        # Server-side validation
        if not name:
            flash('Name is required.', 'error')
            return render_template(
                'profile/edit.html',
                user=current_user,
                districts=SRI_LANKAN_DISTRICTS,
                form_data=request.form
            )

        if len(name) > 120:
            flash('Name must be 120 characters or fewer.', 'error')
            return render_template(
                'profile/edit.html',
                user=current_user,
                districts=SRI_LANKAN_DISTRICTS,
                form_data=request.form
            )

        # Validate WhatsApp number (required, Sri Lankan E.164)
        is_valid_wa, normalized_wa, wa_err = validate_sl_phone(whatsapp_number)
        if not is_valid_wa:
            flash(wa_err or 'Please enter a valid Sri Lankan WhatsApp number.', 'error')
            return render_template(
                'profile/edit.html',
                user=current_user,
                districts=SRI_LANKAN_DISTRICTS,
                form_data=request.form
            )

        # Validate and normalize phone number if provided (optional)
        normalized_ph = None
        if phone:
            normalized_ph = normalize_phone_number(phone)
            if not normalized_ph:
                flash('Please enter a valid Sri Lankan phone number (e.g. 077 123 4567 or +94771234567).', 'error')
                return render_template(
                    'profile/edit.html',
                    user=current_user,
                    districts=SRI_LANKAN_DISTRICTS,
                    form_data=request.form
                )

        if location and len(location) > 120:
            flash('Location must be 120 characters or fewer.', 'error')
            return render_template(
                'profile/edit.html',
                user=current_user,
                districts=SRI_LANKAN_DISTRICTS,
                form_data=request.form
            )

        # Coordinate validation (utils/geo.py)
        parsed_lat = None
        parsed_lng = None
        has_new_coords = False

        if latitude_raw or longitude_raw:
            if not latitude_raw or not longitude_raw:
                flash('Please provide both latitude and longitude or select a location on the map.', 'error')
                return render_template(
                    'profile/edit.html',
                    user=current_user,
                    districts=SRI_LANKAN_DISTRICTS,
                    form_data=request.form
                )

            parsed_lat = parse_coord(latitude_raw)
            parsed_lng = parse_coord(longitude_raw)
            if parsed_lat is None or parsed_lng is None:
                flash('Invalid coordinates provided. Please select a valid location on the map.', 'error')
                return render_template(
                    'profile/edit.html',
                    user=current_user,
                    districts=SRI_LANKAN_DISTRICTS,
                    form_data=request.form
                )

            if not is_in_sri_lanka(parsed_lat, parsed_lng):
                flash('Location must be within Sri Lanka (latitude 5.8-9.9, longitude 79.4-82.0).', 'error')
                return render_template(
                    'profile/edit.html',
                    user=current_user,
                    districts=SRI_LANKAN_DISTRICTS,
                    form_data=request.form
                )

            has_new_coords = True

        if current_user.role == 'farmer':
            if farm_name and len(farm_name) > 120:
                flash('Farm name must be 120 characters or fewer.', 'error')
                return render_template(
                    'profile/edit.html',
                    user=current_user,
                    districts=SRI_LANKAN_DISTRICTS,
                    form_data=request.form
                )
            if bio and len(bio) > 1000:
                flash('Bio must be 1000 characters or fewer.', 'error')
                return render_template(
                    'profile/edit.html',
                    user=current_user,
                    districts=SRI_LANKAN_DISTRICTS,
                    form_data=request.form
                )

        # Apply updates
        current_user.name = name
        current_user.whatsapp_number = normalized_wa
        current_user.phone = normalized_ph
        current_user.location = location or None

        if has_new_coords:
            # Check if lat/lng changed to update timestamp
            coords_changed = (
                current_user.latitude != parsed_lat or
                current_user.longitude != parsed_lng
            )
            current_user.latitude = parsed_lat
            current_user.longitude = parsed_lng
            current_user.address_text = address_text or None
            if coords_changed:
                current_user.location_updated_at = datetime.utcnow()
        elif address_text:
            current_user.address_text = address_text

        if current_user.role == 'farmer':
            current_user.farm_name = farm_name or None
            current_user.bio = bio or None

        # Handle optional profile photo upload
        profile_photo = request.files.get('profile_image')
        if profile_photo and profile_photo.filename:
            main_url, thumb_url, err = save_uploaded_image(
                profile_photo,
                folder='profiles',
                max_width=800,
                thumb_width=200
            )
            if err:
                flash(err, 'error')
                return render_template(
                    'profile/edit.html',
                    user=current_user,
                    districts=SRI_LANKAN_DISTRICTS,
                    form_data=request.form
                )
            if current_user.profile_image_url:
                delete_uploaded_image(current_user.profile_image_url)
            current_user.profile_image_url = main_url

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile.view'))

    return render_template(
        'profile/edit.html',
        user=current_user,
        districts=SRI_LANKAN_DISTRICTS,
        form_data=None
    )


@profile_bp.route('/password', methods=['GET', 'POST'])
@login_required
def password():
    """Change current user's password."""
    if request.method == 'POST':
        current_pwd = request.form.get('current_password', '')
        new_pwd = request.form.get('new_password', '')
        confirm_pwd = request.form.get('confirm_password', '')

        if not current_pwd or not new_pwd or not confirm_pwd:
            flash('All password fields are required.', 'error')
            return render_template('profile/password.html')

        if not current_user.check_password(current_pwd):
            flash('Current password is incorrect.', 'error')
            return render_template('profile/password.html')

        if current_user.role == 'admin':
            is_valid, err_msg = validate_admin_password(new_pwd, email=current_user.email, name=current_user.name)
            if not is_valid:
                flash(err_msg, 'error')
                return render_template('profile/password.html')
        else:
            if len(new_pwd) < 8:
                flash('New password must be at least 8 characters long.', 'error')
                return render_template('profile/password.html')

        if new_pwd != confirm_pwd:
            flash('New password and confirmation do not match.', 'error')
            return render_template('profile/password.html')

        if current_pwd == new_pwd:
            flash('New password cannot be the same as your current password.', 'warning')
            return render_template('profile/password.html')

        current_user.set_password(new_pwd)
        current_user.must_change_password = False
        current_user.session_version = (current_user.session_version or 1) + 1
        session['session_version'] = current_user.session_version
        db.session.commit()
        flash('Password changed successfully!', 'success')
        return redirect(url_for('profile.view'))

    return render_template('profile/password.html')


@profile_bp.route('/request-verification', methods=['POST'])
@login_required
def request_verification():
    if current_user.role != 'farmer':
        abort(403)

    if current_user.is_verified:
        flash('Your farmer profile is already verified.', 'info')
        return redirect(url_for('profile.view'))

    # One open request per farmer
    existing_pending = VerificationRequest.query.filter_by(
        farmer_id=current_user.id,
        status='pending'
    ).first()

    if existing_pending:
        flash('You already have a pending verification request under review.', 'warning')
        return redirect(url_for('profile.view'))

    farmer_note = request.form.get('farmer_note', '').strip()
    req = VerificationRequest(
        farmer_id=current_user.id,
        status='pending',
        farmer_note=farmer_note if farmer_note else None
    )
    db.session.add(req)
    db.session.commit()

    flash('Verification request submitted successfully! An administrator will review your profile.', 'success')
    return redirect(url_for('profile.view'))


@profile_bp.route('/data-request', methods=['POST'])
@login_required
def create_data_request():
    req_type = request.form.get('type', '').strip().lower()
    if req_type not in ('export', 'deletion'):
        flash('Invalid data request type.', 'error')
        return redirect(url_for('profile.view'))

    # One open request per type
    existing_open = DataRequest.query.filter_by(
        user_id=current_user.id,
        type=req_type,
        status='open'
    ).first()

    if existing_open:
        flash(f'You already have an open {req_type} request under review.', 'warning')
        return redirect(url_for('profile.view'))

    req = DataRequest(
        user_id=current_user.id,
        type=req_type,
        status='open'
    )
    db.session.add(req)
    db.session.commit()

    if req_type == 'export':
        flash('Personal data export requested (Sri Lanka PDPA 2022). An administrator will generate your portable JSON archive.', 'success')
    else:
        flash('Account deletion requested. An administrator will verify that all active orders are settled before anonymizing your data.', 'success')

    return redirect(url_for('profile.view'))

