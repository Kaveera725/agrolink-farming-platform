from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from utils.phone import validate_sl_phone, normalize_phone_number

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
    return render_template('profile/view.html', user=current_user)


@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    """Edit current user's profile details."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        whatsapp_number = request.form.get('whatsapp_number', '').strip()
        location = request.form.get('location', '').strip()
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

        if current_user.role == 'farmer':
            current_user.farm_name = farm_name or None
            current_user.bio = bio or None

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
        db.session.commit()
        flash('Password changed successfully!', 'success')
        return redirect(url_for('profile.view'))

    return render_template('profile/password.html')
