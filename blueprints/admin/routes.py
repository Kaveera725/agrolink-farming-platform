import csv
import io
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal

from flask import (
    Blueprint, Response, current_app, flash, redirect,
    render_template, request, session, url_for, stream_with_context
)
from flask_login import current_user, logout_user
from sqlalchemy import func

from extensions import db
from models import AdminAuditLog, AdminNote, Crop, ListingReport, MarketPrice, MarketPriceHistory, Order, PlatformSetting, Product, User, VerificationRequest
from services.settings import (
    SETTINGS_SCHEMA, get_setting, set_setting, clear_settings_cache,
    reset_settings_to_defaults, validate_setting
)
from services.notifications import notify_order_cancelled_by_admin
from utils.decorators import roles_required
from utils.phone import normalize_phone_number, validate_sl_phone
from utils.security import generate_temp_password, sanitize_csv_cell

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.context_processor
def admin_nav_counts():
    """Supply real-time pending counters to admin sidebar."""
    try:
        pending_verifications = VerificationRequest.query.filter_by(status='pending').count()
    except Exception:
        pending_verifications = 0
    try:
        open_reports = ListingReport.query.filter(ListingReport.status.in_(['open', 'reviewing'])).count()
    except Exception:
        open_reports = 0
    return {
        'admin_pending_verifications_count': pending_verifications,
        'admin_open_reports_count': open_reports,
    }



def _audit(action, target_type=None, target_id=None, details=None, before_data=None, after_data=None, result='success'):
    """Log an administrative action with IP, user agent, and before/after state."""
    try:
        log = AdminAuditLog(
            admin_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string[:255] if request.user_agent else None,
            before_data=before_data,
            after_data=after_data,
            result=result,
        )
        db.session.add(log)
        return log
    except Exception:
        return None


def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d') if value else None
    except ValueError:
        return None


def _date_range():
    start = _parse_date(request.args.get('start'))
    end = _parse_date(request.args.get('end'))
    if end:
        end += timedelta(days=1)
    return start, end


@admin_bp.before_request
@roles_required('admin')
def admin_security_check():
    """Enforce idle timeout of 30 minutes for administrator sessions."""
    now_ts = datetime.utcnow().timestamp()
    timeout_mins = current_app.config.get('ADMIN_SESSION_TIMEOUT_MINUTES', 30)
    timeout_secs = timeout_mins * 60
    last_activity = session.get('admin_last_activity')
    if last_activity and (now_ts - last_activity > timeout_secs):
        session.pop('admin_last_activity', None)
        logout_user()
        flash('Your admin session has expired due to 30 minutes of inactivity. Please log in again.', 'warning')
        return redirect(url_for('auth.login', next=request.path))
    session['admin_last_activity'] = now_ts


@admin_bp.after_request
def set_admin_headers(response):
    """Prevent browser caching of sensitive administrator screens."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response


@admin_bp.route('/')
@admin_bp.route('')
@admin_bp.route('/dashboard')
def dashboard():
    since = datetime.utcnow() - timedelta(days=29)
    orders = Order.query.order_by(Order.created_at.desc()).all()
    daily = Counter(
        order.created_at.date().isoformat()
        for order in orders
        if order.created_at and order.created_at >= since
    )
    chart_labels = [(since + timedelta(days=index)).date().isoformat() for index in range(30)]
    chart_values = [daily[label] for label in chart_labels]
    totals = {
        'users': User.query.count(),
        'farmers': User.query.filter_by(role='farmer').count(),
        'buyers': User.query.filter_by(role='buyer').count(),
        'admins': User.query.filter_by(role='admin').count(),
        'active_listings': Product.query.filter_by(is_available=True, is_deleted=False).count(),
        'orders': Order.query.count(),
        'order_value': db.session.query(func.coalesce(func.sum(Order.total_price), 0)).scalar(),
        'delivery_fees': db.session.query(func.coalesce(func.sum(Order.delivery_fee), 0)).scalar(),
    }
    status_counts = Counter(order.status for order in orders)
    registrations = User.query.order_by(User.created_at.desc()).limit(8).all()
    stale_days = get_setting('stale_price_days', default=7)
    stale_cutoff = datetime.utcnow() - timedelta(days=stale_days)
    stale_prices = MarketPrice.query.filter(MarketPrice.updated_at < stale_cutoff).order_by(MarketPrice.updated_at.asc()).all()

    return render_template(
        'admin/dashboard.html',
        totals=totals,
        status_counts=status_counts,
        recent_orders=orders[:8],
        registrations=registrations,
        chart_labels=chart_labels,
        chart_values=chart_values,
        stale_prices=stale_prices,
        stale_days=stale_days
    )


@admin_bp.route('/users')
def users():
    query = User.query
    search = request.args.get('q', '').strip()
    role = request.args.get('role', '').strip()
    active = request.args.get('active', '').strip()
    sort = request.args.get('sort', 'created_at').strip()
    direction = request.args.get('direction', 'desc').strip()
    page = request.args.get('page', 1, type=int)

    if search:
        query = query.filter(User.name.ilike(f'%{search}%') | User.email.ilike(f'%{search}%'))
    if role:
        query = query.filter(User.role == role)
    if active in ('true', 'false'):
        query = query.filter(User.is_active == (active == 'true'))

    # Sortable columns
    sort_cols = {
        'name': User.name,
        'email': User.email,
        'role': User.role,
        'is_active': User.is_active,
        'created_at': User.created_at,
    }
    sort_column = sort_cols.get(sort, User.created_at)
    if direction == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=20, error_out=False)

    return render_template(
        'admin/users.html',
        pagination=pagination,
        users=pagination.items,
        search=search,
        role=role,
        active=active,
        sort=sort,
        direction=direction
    )


@admin_bp.route('/users/<int:user_id>')
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    # Check pending/confirmed orders count for farmer warning
    pending_orders_count = Order.query.join(Product).filter(
        Product.farmer_id == user.id,
        Order.status.in_(['pending', 'confirmed'])
    ).count() if user.role == 'farmer' else 0

    temp_password_notice = session.pop('temp_password_notice', None)

    return render_template(
        'admin/user_detail.html',
        user=user,
        pending_orders_count=pending_orders_count,
        temp_password_notice=temp_password_notice,
        admin_notes=user.admin_notes,
        listings=Product.query.filter_by(farmer_id=user.id).order_by(Product.created_at.desc()).all(),
        orders=Order.query.filter_by(buyer_id=user.id).order_by(Order.created_at.desc()).all()
    )


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)

    # Self-protection
    if user.id == current_user.id:
        flash('You cannot deactivate your own admin account.', 'error')
        return redirect(request.referrer or url_for('admin.users'))

    if user.is_active:
        # Last-admin protection
        if user.role == 'admin':
            active_admins = User.query.filter_by(role='admin', is_active=True).count()
            if active_admins <= 1:
                flash('Cannot deactivate the last active administrator.', 'error')
                return redirect(request.referrer or url_for('admin.users'))

        user.is_active = False
        # Hide active listings with 'owner_inactive'
        if user.role == 'farmer':
            active_prods = Product.query.filter_by(farmer_id=user.id, is_deleted=False).all()
            for prod in active_prods:
                prod.is_deleted = True
                prod.is_available = False
                prod.hidden_reason = 'owner_inactive'
                prod.hidden_by = current_user.id

        _audit(
            'user_deactivated', 'user', user.id,
            f"Deactivated user {user.email}",
            before_data={'is_active': True},
            after_data={'is_active': False}
        )
        db.session.commit()
        flash(f'{user.name} has been deactivated. Active listings have been hidden automatically.', 'success')
    else:
        user.is_active = True
        # Reactivating farmer restores ONLY listings hidden with 'owner_inactive'
        if user.role == 'farmer':
            inactive_prods = Product.query.filter_by(farmer_id=user.id, hidden_reason='owner_inactive').all()
            for prod in inactive_prods:
                prod.is_deleted = False
                prod.is_available = True
                prod.hidden_reason = None
                prod.hidden_by = None

        _audit(
            'user_reactivated', 'user', user.id,
            f"Reactivated user {user.email}",
            before_data={'is_active': False},
            after_data={'is_active': True}
        )
        db.session.commit()
        flash(f'{user.name} has been reactivated. Listings hidden due to inactive owner have been restored.', 'success')

    return redirect(request.referrer or url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    name = request.form.get('name', '').strip()
    phone = request.form.get('phone', '').strip()
    whatsapp = request.form.get('whatsapp_number', '').strip()
    district = request.form.get('location', '').strip()

    if not name:
        flash('User name is required.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user.id))

    if len(name) > 120:
        flash('Name must be 120 characters or fewer.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user.id))

    is_valid_wa, norm_wa, wa_err = validate_sl_phone(whatsapp)
    if not is_valid_wa:
        flash(wa_err or 'Please enter a valid Sri Lankan WhatsApp number.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user.id))

    norm_phone = None
    if phone:
        norm_phone = normalize_phone_number(phone)
        if not norm_phone:
            flash('Please enter a valid Sri Lankan phone number.', 'error')
            return redirect(url_for('admin.user_detail', user_id=user.id))

    before_data = {
        'name': user.name,
        'phone': user.phone,
        'whatsapp_number': user.whatsapp_number,
        'location': user.location
    }
    after_data = {
        'name': name,
        'phone': norm_phone,
        'whatsapp_number': norm_wa,
        'location': district
    }

    user.name = name
    user.phone = norm_phone
    user.whatsapp_number = norm_wa
    user.location = district

    _audit(
        'user_profile_updated', 'user', user.id,
        f"Admin updated profile details for {user.email}",
        before_data=before_data,
        after_data=after_data
    )
    db.session.commit()
    flash(f'Profile updated successfully for {user.name}.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user.id))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
def reset_user_password(user_id):
    user = User.query.get_or_404(user_id)
    temp_pwd = generate_temp_password(14)
    user.set_password(temp_pwd)
    user.must_change_password = True
    user.session_version = (user.session_version or 1) + 1

    # Temporary password is never logged and never stored in plain text
    _audit(
        'user_password_reset', 'user', user.id,
        f"Admin initiated temporary password reset for {user.email}"
    )
    db.session.commit()

    # Shown ONCE to the administrator
    session['temp_password_notice'] = {
        'user_id': user.id,
        'user_name': user.name,
        'user_email': user.email,
        'temp_password': temp_pwd
    }
    flash(f"Temporary password generated for {user.name}.", 'success')
    return redirect(url_for('admin.user_detail', user_id=user.id))


@admin_bp.route('/users/<int:user_id>/change-role', methods=['POST'])
def change_user_role(user_id):
    user = User.query.get_or_404(user_id)
    new_role = request.form.get('new_role', '').strip().lower()
    reason = request.form.get('reason', '').strip()

    # Self-protection
    if user.id == current_user.id:
        flash('You cannot modify the role of your own account.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user.id))

    # Mandatory reason
    if not reason:
        flash('A mandatory reason is required to change user roles.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user.id))

    # Farmer <-> Buyer switching is not supported due to data implications
    if (user.role == 'farmer' and new_role == 'buyer') or (user.role == 'buyer' and new_role == 'farmer'):
        flash('Switching between Farmer and Buyer roles is not supported due to data implications.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user.id))

    if new_role not in ('admin', 'farmer', 'buyer'):
        flash('Invalid role specified.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user.id))

    if new_role == user.role:
        flash('User already has this role.', 'info')
        return redirect(url_for('admin.user_detail', user_id=user.id))

    # Demoting last active admin protection
    if user.role == 'admin' and new_role != 'admin':
        if user.is_active:
            active_admins = User.query.filter_by(role='admin', is_active=True).count()
            if active_admins <= 1:
                flash('Cannot demote the last active administrator.', 'error')
                return redirect(url_for('admin.user_detail', user_id=user.id))

    old_role = user.role
    user.role = new_role
    # Invalidate user's existing sessions
    user.session_version = (user.session_version or 1) + 1

    _audit(
        'user_role_changed', 'user', user.id,
        f"Role changed from {old_role} to {new_role}. Reason: {reason}",
        before_data={'role': old_role},
        after_data={'role': new_role, 'reason': reason}
    )
    db.session.commit()
    flash(f"Role updated successfully for {user.name} from {old_role} to {new_role}.", 'success')
    return redirect(url_for('admin.user_detail', user_id=user.id))


@admin_bp.route('/users/<int:user_id>/notes', methods=['POST'])
def add_admin_note(user_id):
    user = User.query.get_or_404(user_id)
    note_content = request.form.get('note', '').strip()
    if not note_content:
        flash('Note content cannot be empty.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user.id))

    note = AdminNote(
        user_id=user.id,
        admin_id=current_user.id,
        note=note_content
    )
    db.session.add(note)
    _audit(
        'admin_note_added', 'user', user.id,
        f"Internal admin note recorded for {user.email}"
    )
    db.session.commit()
    flash('Admin note saved.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user.id))


@admin_bp.route('/listings')
def listings():
    query = Product.query
    search = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'created_at').strip()
    direction = request.args.get('direction', 'desc').strip()
    page = request.args.get('page', 1, type=int)

    if search:
        query = query.join(User, Product.farmer_id == User.id).filter(
            Product.name.ilike(f'%{search}%') | User.name.ilike(f'%{search}%')
        )

    sort_cols = {
        'name': Product.name,
        'category': Product.category,
        'price': Product.price_per_kg,
        'created_at': Product.created_at,
    }
    sort_column = sort_cols.get(sort, Product.created_at)
    if direction == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=20, error_out=False)

    return render_template(
        'admin/listings.html',
        pagination=pagination,
        listings=pagination.items,
        search=search,
        sort=sort,
        direction=direction
    )


@admin_bp.route('/listings/<int:product_id>/toggle', methods=['POST'])
def toggle_listing(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_deleted = not product.is_deleted
    if product.is_deleted:
        product.is_available = False
        product.hidden_reason = 'moderation'
        product.hidden_by = current_user.id
    else:
        product.is_available = True
        product.hidden_reason = None
        product.hidden_by = None

    _audit(
        'listing_moderation', 'product', product.id,
        f"Listing {product.id} ({product.name}) {'hidden for moderation' if product.is_deleted else 'restored'}",
        before_data={'is_deleted': not product.is_deleted},
        after_data={'is_deleted': product.is_deleted, 'hidden_reason': product.hidden_reason}
    )
    db.session.commit()
    flash(f'Listing {"hidden for moderation" if product.is_deleted else "restored"}.', 'success')
    return redirect(request.referrer or url_for('admin.listings'))


def _filtered_orders_query():
    query = Order.query
    status = request.args.get('status', '').strip()
    start, end = _date_range()
    search = request.args.get('q', '').strip()

    if status:
        query = query.filter(Order.status == status)
    if start:
        query = query.filter(Order.created_at >= start)
    if end:
        query = query.filter(Order.created_at < end)
    if search:
        query = query.join(User, Order.buyer_id == User.id).join(Product, Order.product_id == Product.id).filter(
            User.name.ilike(f'%{search}%') | Product.name.ilike(f'%{search}%')
        )
    return query


@admin_bp.route('/orders')
def orders():
    query = _filtered_orders_query()
    sort = request.args.get('sort', 'created_at').strip()
    direction = request.args.get('direction', 'desc').strip()
    page = request.args.get('page', 1, type=int)

    sort_cols = {
        'id': Order.id,
        'total_price': Order.total_price,
        'status': Order.status,
        'created_at': Order.created_at,
    }
    sort_column = sort_cols.get(sort, Order.created_at)
    if direction == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=20, error_out=False)

    return render_template(
        'admin/orders.html',
        pagination=pagination,
        orders=pagination.items,
        status=request.args.get('status', ''),
        start=request.args.get('start', ''),
        end=request.args.get('end', ''),
        search=request.args.get('q', ''),
        sort=sort,
        direction=direction
    )


@admin_bp.route('/orders/<int:order_id>')
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    notes = AdminNote.query.filter_by(order_id=order.id).order_by(AdminNote.created_at.desc()).all()
    can_cancel = order.status in ('pending', 'confirmed')
    return render_template('admin/order_detail.html', order=order, notes=notes, can_cancel=can_cancel)


@admin_bp.route('/orders/<int:order_id>/notes', methods=['POST'])
def add_order_note(order_id):
    order = Order.query.get_or_404(order_id)
    note_text = request.form.get('note', '').strip()
    if not note_text:
        flash('Note cannot be empty.', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    note = AdminNote(
        order_id=order.id,
        user_id=order.buyer_id,
        admin_id=current_user.id,
        note=note_text
    )
    db.session.add(note)
    _audit('admin_note_added_order', 'order', order.id, f"Added internal note to order #{order.id}")
    db.session.commit()
    flash('Internal note saved.', 'success')
    return redirect(url_for('admin.order_detail', order_id=order_id))


@admin_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)

    # Server-side transition validation
    if order.status in ('delivered', 'cancelled', 'rejected'):
        flash(f'Cannot cancel order #{order.id} because it is already {order.status}.', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    reason = request.form.get('reason', '').strip()
    if not reason or len(reason) < 5:
        flash('A cancellation reason of at least 5 characters is mandatory.', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))

    try:
        # Row-level locking identical to normal order cancel flow
        order_locked = Order.query.filter_by(id=order_id).with_for_update().populate_existing().first()
        if not order_locked or order_locked.status in ('delivered', 'cancelled', 'rejected'):
            flash('Order state has changed and can no longer be cancelled.', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))

        product = Product.query.filter_by(id=order_locked.product_id).with_for_update().populate_existing().first()
        if not product:
            flash('Associated product record not found.', 'error')
            return redirect(url_for('admin.order_detail', order_id=order_id))

        old_status = order_locked.status
        order_locked.status = 'cancelled'
        order_locked.rejection_reason = f"Cancelled by admin: {reason}"

        # Restore product stock under same rules
        product.quantity_kg += order_locked.quantity_kg
        if not product.is_deleted:
            product.is_available = True

        # Internal note documenting intervention
        note = AdminNote(
            order_id=order_locked.id,
            user_id=order_locked.buyer_id,
            admin_id=current_user.id,
            note=f"Order cancelled by admin ({current_user.name}). Reason: {reason}"
        )
        db.session.add(note)

        _audit(
            'order_cancelled_by_admin', 'order', order_locked.id,
            f"Admin cancelled order #{order_locked.id}. Reason: {reason}",
            before_data={'status': old_status},
            after_data={'status': 'cancelled', 'reason': reason}
        )

        db.session.commit()

        # Notification hook for buyer and farmer
        try:
            notify_order_cancelled_by_admin(order_locked, reason, current_user)
        except Exception:
            pass

        flash(f'Order #{order_locked.id} has been cancelled by administrator. Stock ({order_locked.quantity_kg} kg) restored.', 'success')
        return redirect(url_for('admin.order_detail', order_id=order_id))
    except Exception as e:
        db.session.rollback()
        flash('Could not cancel order due to a database lock conflict. Please retry.', 'error')
        return redirect(url_for('admin.order_detail', order_id=order_id))


def _sanitize_csv_cell_import(val):
    if not val:
        return ''
    s = str(val).strip()
    if s.startswith(('=', '+', '-', '@', '\t', '\r')):
        try:
            float(s)
        except ValueError:
            s = s.lstrip('=+@- \t\r\n')
    return s


@admin_bp.route('/prices', methods=['GET', 'POST'])
def prices():
    editing = None
    edit_id = request.args.get('edit', type=int)
    require_confirm = request.args.get('require_confirm') == '1'
    if edit_id:
        editing = MarketPrice.query.get_or_404(edit_id)

    stale_days = get_setting('stale_price_days', default=7)
    stale_cutoff = datetime.utcnow() - timedelta(days=stale_days)
    stale_prices = MarketPrice.query.filter(MarketPrice.updated_at < stale_cutoff).order_by(MarketPrice.updated_at.asc()).all()

    if request.method == 'POST':
        try:
            buying = float(request.form.get('buying_price', ''))
            selling = float(request.form.get('selling_price', ''))
            if buying <= 0 or selling < buying:
                raise ValueError
        except (ValueError, TypeError):
            flash('Prices must be positive, and selling price must be at least buying price.', 'error')
            return redirect(url_for('admin.prices', edit=edit_id) if edit_id else url_for('admin.prices'))

        price = MarketPrice.query.get(request.form.get('id', type=int)) if request.form.get('id') else MarketPrice()
        is_new = price.id is None
        old_buying = price.buying_price if not is_new else None
        old_selling = price.selling_price if not is_new else None

        # Typo guard: if updating existing price and change exceeds 30%, require confirmation
        if not is_new and old_buying and old_selling:
            buying_diff = abs(buying - old_buying) / old_buying
            selling_diff = abs(selling - old_selling) / old_selling
            confirmed = request.form.get('confirm_large_change') in ('yes', '1', 'true', 'on')
            if (buying_diff > 0.30 or selling_diff > 0.30) and not confirmed:
                flash(
                    f'Warning: Price change exceeds 30% (buying changed {buying_diff*100:.1f}%, selling changed {selling_diff*100:.1f}%). Please confirm to apply this change.',
                    'warning'
                )
                query = MarketPrice.query.order_by(MarketPrice.crop_name.asc())
                pagination = query.paginate(page=1, per_page=20, error_out=False)
                return render_template(
                    'admin/prices.html',
                    pagination=pagination,
                    prices=pagination.items,
                    editing=price,
                    stale_prices=stale_prices,
                    stale_days=stale_days,
                    require_confirm=True,
                    pending_buying=buying,
                    pending_selling=selling,
                    search='',
                    sort='crop_name',
                    direction='asc'
                )

        before_data = {
            'crop_name': price.crop_name,
            'category': price.category,
            'buying_price': price.buying_price,
            'selling_price': price.selling_price,
            'unit': price.unit,
            'market_location': price.market_location
        } if not is_new else None

        price.crop_name = request.form.get('crop_name', '').strip()
        price.category = request.form.get('category', '').strip()
        price.buying_price = buying
        price.selling_price = selling
        price.unit = request.form.get('unit', 'per kg').strip() or 'per kg'
        price.market_location = request.form.get('market_location', 'Colombo').strip() or 'Colombo'
        price.updated_at = datetime.utcnow()

        if not price.crop_name or not price.category:
            flash('Crop name and category are required.', 'error')
            return redirect(url_for('admin.prices', edit=edit_id) if edit_id else url_for('admin.prices'))

        db.session.add(price)
        db.session.flush()

        # Write history row inside the same transaction
        history_entry = MarketPriceHistory(
            market_price_id=price.id,
            old_buying=old_buying,
            old_selling=old_selling,
            new_buying=price.buying_price,
            new_selling=price.selling_price,
            changed_by=current_user.id if current_user.is_authenticated else None,
            changed_at=datetime.utcnow(),
            source='manual'
        )
        db.session.add(history_entry)

        after_data = {
            'crop_name': price.crop_name,
            'category': price.category,
            'buying_price': price.buying_price,
            'selling_price': price.selling_price,
            'unit': price.unit,
            'market_location': price.market_location
        }

        _audit(
            'market_price_saved', 'market_price', price.id,
            f"{'Created' if is_new else 'Updated'} price for {price.crop_name}",
            before_data=before_data,
            after_data=after_data
        )
        db.session.commit()
        flash('Market price saved.', 'success')
        return redirect(url_for('admin.prices'))

    query = MarketPrice.query
    search = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'crop_name').strip()
    direction = request.args.get('direction', 'asc').strip()
    page = request.args.get('page', 1, type=int)

    if search:
        query = query.filter(MarketPrice.crop_name.ilike(f'%{search}%') | MarketPrice.category.ilike(f'%{search}%'))

    sort_cols = {
        'crop_name': MarketPrice.crop_name,
        'category': MarketPrice.category,
        'buying_price': MarketPrice.buying_price,
        'selling_price': MarketPrice.selling_price,
        'market_location': MarketPrice.market_location,
        'updated_at': MarketPrice.updated_at,
    }
    sort_column = sort_cols.get(sort, MarketPrice.crop_name)
    if direction == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=20, error_out=False)

    return render_template(
        'admin/prices.html',
        pagination=pagination,
        prices=pagination.items,
        editing=editing,
        stale_prices=stale_prices,
        stale_days=stale_days,
        require_confirm=require_confirm,
        search=search,
        sort=sort,
        direction=direction
    )


@admin_bp.route('/prices/<int:price_id>', endpoint='price_detail')
def price_detail(price_id):
    price = MarketPrice.query.get_or_404(price_id)
    history = MarketPriceHistory.query.filter_by(market_price_id=price.id).order_by(MarketPriceHistory.changed_at.desc()).all()

    cutoff_90 = datetime.utcnow() - timedelta(days=90)
    chart_points = [h for h in reversed(history) if h.changed_at >= cutoff_90]
    if len(chart_points) < 2 and history:
        chart_points = list(reversed(history))

    if not chart_points:
        pt_date = price.updated_at or datetime.utcnow()
        chart_labels = [pt_date.strftime('%b %d %H:%M')]
        chart_buying = [round(price.buying_price, 2)]
        chart_selling = [round(price.selling_price, 2)]
    else:
        chart_labels = [h.changed_at.strftime('%b %d %H:%M') for h in chart_points]
        chart_buying = [round(h.new_buying, 2) for h in chart_points]
        chart_selling = [round(h.new_selling, 2) for h in chart_points]

    return render_template(
        'admin/price_detail.html',
        price=price,
        history=history,
        chart_labels=chart_labels,
        chart_buying=chart_buying,
        chart_selling=chart_selling
    )


@admin_bp.route('/prices/import/template', endpoint='import_prices_template')
def import_prices_template():
    csv_content = (
        "crop_name,category,buying_price,selling_price,unit,market_location\n"
        "Tomato,Vegetables,85.00,120.00,per kg,Colombo\n"
        "Carrot,Vegetables,60.00,95.00,per kg,Colombo\n"
        "Red Onion,Vegetables,220.00,280.00,per kg,Dambulla\n"
    )
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=market_prices_template.csv"}
    )


@admin_bp.route('/prices/import', endpoint='import_prices', methods=['GET', 'POST'])
def import_prices():
    if request.method == 'GET':
        return render_template('admin/prices_import.html', preview=None)

    file = request.files.get('file')
    if not file or not file.filename:
        flash('Please select a CSV file to upload.', 'error')
        return redirect(url_for('admin.import_prices'))

    if not file.filename.lower().endswith('.csv'):
        flash('Only CSV files (.csv) are supported.', 'error')
        return redirect(url_for('admin.import_prices'))

    content_bytes = file.read()
    if len(content_bytes) > 1 * 1024 * 1024:
        flash('File size exceeds 1 MB limit.', 'error')
        return redirect(url_for('admin.import_prices'))

    try:
        text_content = content_bytes.decode('utf-8')
    except UnicodeDecodeError:
        flash('File encoding must be UTF-8.', 'error')
        return redirect(url_for('admin.import_prices'))

    reader = csv.DictReader(io.StringIO(text_content))
    fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]
    required_cols = {'crop_name', 'category', 'buying_price', 'selling_price'}
    if not required_cols.issubset(set(fieldnames)):
        missing = required_cols - set(fieldnames)
        flash(f'Missing required CSV columns: {", ".join(missing)}', 'error')
        return redirect(url_for('admin.import_prices'))

    rows = list(reader)
    if len(rows) > 500:
        flash('CSV contains more than 500 rows (maximum allowed is 500).', 'error')
        return redirect(url_for('admin.import_prices'))

    all_prices = MarketPrice.query.all()
    price_map = {p.crop_name.strip().lower(): p for p in all_prices}

    preview_rows = []
    counts = {'new': 0, 'update': 0, 'unchanged': 0, 'invalid': 0}

    for idx, row in enumerate(rows, start=1):
        crop_name = _sanitize_csv_cell_import(row.get('crop_name', ''))
        category = _sanitize_csv_cell_import(row.get('category', ''))
        unit = _sanitize_csv_cell_import(row.get('unit', '')) or 'per kg'
        location = _sanitize_csv_cell_import(row.get('market_location', '')) or 'Colombo'
        raw_buying = row.get('buying_price', '')
        raw_selling = row.get('selling_price', '')

        row_info = {
            'line': idx,
            'crop_name': crop_name,
            'category': category,
            'unit': unit,
            'market_location': location,
            'raw_buying': raw_buying,
            'raw_selling': raw_selling,
            'buying_price': None,
            'selling_price': None,
            'status': 'invalid',
            'reason': None,
            'warning_30': False,
            'existing_buying': None,
            'existing_selling': None
        }

        if not crop_name or not category:
            row_info['reason'] = 'Missing crop name or category'
            counts['invalid'] += 1
            preview_rows.append(row_info)
            continue

        try:
            b_val = float(raw_buying)
            s_val = float(raw_selling)
            if b_val <= 0:
                row_info['reason'] = 'Buying price must be positive (> 0)'
                counts['invalid'] += 1
                preview_rows.append(row_info)
                continue
            if s_val < b_val:
                row_info['reason'] = 'Selling price must be >= buying price'
                counts['invalid'] += 1
                preview_rows.append(row_info)
                continue
            row_info['buying_price'] = b_val
            row_info['selling_price'] = s_val
        except (ValueError, TypeError):
            row_info['reason'] = 'Prices must be valid numbers'
            counts['invalid'] += 1
            preview_rows.append(row_info)
            continue

        existing = price_map.get(crop_name.lower())
        if not existing:
            row_info['status'] = 'new'
            counts['new'] += 1
        else:
            row_info['existing_buying'] = existing.buying_price
            row_info['existing_selling'] = existing.selling_price
            if (round(existing.buying_price, 2) == round(b_val, 2) and
                round(existing.selling_price, 2) == round(s_val, 2) and
                existing.category == category and
                existing.market_location == location):
                row_info['status'] = 'unchanged'
                counts['unchanged'] += 1
            else:
                row_info['status'] = 'update'
                counts['update'] += 1
                b_diff = abs(b_val - existing.buying_price) / existing.buying_price if existing.buying_price else 0
                s_diff = abs(s_val - existing.selling_price) / existing.selling_price if existing.selling_price else 0
                if b_diff > 0.30 or s_diff > 0.30:
                    row_info['warning_30'] = True
                    row_info['reason'] = f'Price change > 30% (buying changed {b_diff*100:.0f}%, selling changed {s_diff*100:.0f}%)'

        preview_rows.append(row_info)

    import json
    return render_template(
        'admin/prices_import.html',
        preview=preview_rows,
        counts=counts,
        filename=file.filename,
        payload_json=json.dumps(preview_rows)
    )


@admin_bp.route('/prices/import/confirm', endpoint='confirm_import_prices', methods=['POST'])
def confirm_import_prices():
    import json
    payload_raw = request.form.get('import_payload', '')
    filename = request.form.get('filename', 'uploaded.csv')
    if not payload_raw:
        flash('No import data provided.', 'error')
        return redirect(url_for('admin.import_prices'))

    try:
        rows = json.loads(payload_raw)
    except Exception:
        flash('Invalid import payload.', 'error')
        return redirect(url_for('admin.import_prices'))

    applied_new = 0
    applied_update = 0
    unchanged_count = 0
    skipped_invalid = 0

    try:
        with db.session.begin_nested():
            for row in rows:
                status = row.get('status')
                if status == 'invalid':
                    skipped_invalid += 1
                    continue
                elif status == 'unchanged':
                    unchanged_count += 1
                    continue

                crop_name = _sanitize_csv_cell_import(row.get('crop_name', ''))
                category = _sanitize_csv_cell_import(row.get('category', ''))
                unit = _sanitize_csv_cell_import(row.get('unit', '')) or 'per kg'
                location = _sanitize_csv_cell_import(row.get('market_location', '')) or 'Colombo'
                buying = float(row['buying_price'])
                selling = float(row['selling_price'])

                price = MarketPrice.query.filter(func.lower(MarketPrice.crop_name) == crop_name.lower()).first()
                if not price:
                    price = MarketPrice(
                        crop_name=crop_name,
                        category=category,
                        buying_price=buying,
                        selling_price=selling,
                        unit=unit,
                        market_location=location,
                        updated_at=datetime.utcnow()
                    )
                    db.session.add(price)
                    db.session.flush()

                    history = MarketPriceHistory(
                        market_price_id=price.id,
                        old_buying=None,
                        old_selling=None,
                        new_buying=buying,
                        new_selling=selling,
                        changed_by=current_user.id if current_user.is_authenticated else None,
                        changed_at=datetime.utcnow(),
                        source='import'
                    )
                    db.session.add(history)
                    applied_new += 1
                else:
                    old_b = price.buying_price
                    old_s = price.selling_price
                    price.crop_name = crop_name
                    price.category = category
                    price.buying_price = buying
                    price.selling_price = selling
                    price.unit = unit
                    price.market_location = location
                    price.updated_at = datetime.utcnow()

                    history = MarketPriceHistory(
                        market_price_id=price.id,
                        old_buying=old_b,
                        old_selling=old_s,
                        new_buying=buying,
                        new_selling=selling,
                        changed_by=current_user.id if current_user.is_authenticated else None,
                        changed_at=datetime.utcnow(),
                        source='import'
                    )
                    db.session.add(history)
                    applied_update += 1

            _audit(
                action='market_prices_imported',
                target_type='market_prices',
                details=f"Imported {applied_new + applied_update} prices ({applied_new} new, {applied_update} updated, {unchanged_count} unchanged, {skipped_invalid} invalid skipped) from {filename}",
                after_data={'new': applied_new, 'updated': applied_update, 'unchanged': unchanged_count, 'skipped': skipped_invalid, 'filename': filename}
            )

        db.session.commit()
        flash(
            f"Successfully applied bulk import: {applied_new} new, {applied_update} updated. {skipped_invalid} invalid rows skipped.",
            'success'
        )
    except Exception as exc:
        db.session.rollback()
        flash(f'Import failed and was rolled back: {exc}', 'error')

    return redirect(url_for('admin.prices'))


@admin_bp.route('/prices/<int:price_id>/delete', methods=['POST'])
def delete_price(price_id):
    price = MarketPrice.query.get_or_404(price_id)
    crop_name = price.crop_name
    _audit(
        'market_price_deleted', 'market_price', price.id,
        f"Deleted price reference for {crop_name}",
        before_data={'crop_name': crop_name, 'buying_price': price.buying_price, 'selling_price': price.selling_price}
    )
    db.session.delete(price)
    db.session.commit()
    flash('Market price deleted.', 'success')
    return redirect(url_for('admin.prices'))


@admin_bp.route('/settings', endpoint='settings', methods=['GET', 'POST'])
@admin_bp.route('/settings/platform', endpoint='platform_settings', methods=['GET', 'POST'])
def platform_settings():
    if request.method == 'POST':
        before_data = {}
        after_data = {}
        errors = []

        for key, schema in SETTINGS_SCHEMA.items():
            curr_val = get_setting(key)
            before_data[key] = str(curr_val) if curr_val is not None else ''

            if schema.get('type') == 'bool':
                new_val = 'true' if request.form.get(key) in ('1', 'true', 'on', 'yes') else 'false'
            else:
                new_val = request.form.get(key, '').strip()

            try:
                val_str, val_type = validate_setting(key, new_val)
                after_data[key] = val_str
            except ValueError as e:
                errors.append(str(e))

        if errors:
            for err in errors:
                flash(err, 'error')
            return redirect(url_for('admin.settings'))

        changed_keys = []
        for key in SETTINGS_SCHEMA.keys():
            if before_data.get(key) != after_data.get(key):
                set_setting(key, after_data[key], user_id=current_user.id)
                changed_keys.append(key)

        if changed_keys:
            _audit(
                action='settings_updated',
                target_type='platform_settings',
                details=f"Updated platform settings: {', '.join(changed_keys)}",
                before_data={k: before_data[k] for k in changed_keys},
                after_data={k: after_data[k] for k in changed_keys}
            )
            db.session.commit()
            clear_settings_cache()
            flash('Platform settings updated successfully.', 'success')
        else:
            flash('No settings changes were made.', 'info')

        return redirect(url_for('admin.settings'))

    grouped_settings = {}
    for key, schema in SETTINGS_SCHEMA.items():
        cat = schema.get('category', 'General')
        if cat not in grouped_settings:
            grouped_settings[cat] = []
        curr_val = get_setting(key)
        def_val = schema.get('default')
        grouped_settings[cat].append({
            'key': key,
            'schema': schema,
            'current_value': curr_val,
            'default_value': def_val,
        })

    return render_template('admin/settings.html', grouped_settings=grouped_settings)


@admin_bp.route('/settings/reset', endpoint='settings_reset', methods=['POST'])
def reset_platform_settings():
    before_data = {row.key: row.value for row in PlatformSetting.query.all()}
    PlatformSetting.query.delete()
    _audit(
        action='settings_reset',
        target_type='platform_settings',
        details='Reset all platform settings to system defaults',
        before_data=before_data
    )
    db.session.commit()
    clear_settings_cache()
    flash('Platform settings have been reset to defaults.', 'success')
    return redirect(url_for('admin.settings'))


@admin_bp.route('/exports')
def exports():
    return render_template('admin/reports.html', start=request.args.get('start', ''), end=request.args.get('end', ''))


# ─── 2. LISTING REPORTS ROUTES ──────────────────────────────────────────────
@admin_bp.route('/reports', endpoint='reports')
@admin_bp.route('/listing-reports', endpoint='listing_reports')
def listing_reports():
    status = request.args.get('status', 'open').strip().lower()
    reason = request.args.get('reason', '').strip()
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    query = ListingReport.query.join(Product, ListingReport.product_id == Product.id).join(User, Product.farmer_id == User.id)

    if status and status != 'all':
        query = query.filter(ListingReport.status == status)

    if reason:
        query = query.filter(ListingReport.reason == reason)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Product.name.ilike(search_pattern)) |
            (User.name.ilike(search_pattern)) |
            (User.email.ilike(search_pattern))
        )

    query = query.order_by(ListingReport.created_at.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)

    # Compute distinct reporters per product to flag "Needs review" (3+ distinct reporters)
    needs_review_product_ids = set()
    open_subq = db.session.query(
        ListingReport.product_id,
        func.count(func.distinct(ListingReport.reporter_id)).label('reporter_count')
    ).filter(ListingReport.status.in_(['open', 'reviewing'])).group_by(ListingReport.product_id).all()

    for pid, count in open_subq:
        if count >= 3:
            needs_review_product_ids.add(pid)

    counts = {
        'open': ListingReport.query.filter_by(status='open').count(),
        'reviewing': ListingReport.query.filter_by(status='reviewing').count(),
        'resolved': ListingReport.query.filter_by(status='resolved').count(),
        'dismissed': ListingReport.query.filter_by(status='dismissed').count(),
        'total': ListingReport.query.count(),
    }

    return render_template(
        'admin/reports_queue.html',
        reports=pagination.items,
        pagination=pagination,
        counts=counts,
        status=status,
        reason=reason,
        search=search,
        needs_review_product_ids=needs_review_product_ids
    )


@admin_bp.route('/reports/<int:report_id>')
@admin_bp.route('/listing-reports/<int:report_id>')
def listing_report_detail(report_id):
    report = ListingReport.query.get_or_404(report_id)

    # Automatically move from open to reviewing when opened by admin
    if report.status == 'open':
        report.status = 'reviewing'
        db.session.commit()

    product = report.product
    farmer = product.farmer

    # All reports on this listing
    all_listing_reports = ListingReport.query.filter_by(product_id=product.id).order_by(ListingReport.created_at.desc()).all()
    distinct_reporters_count = len(set(r.reporter_id for r in all_listing_reports if r.status in ('open', 'reviewing')))
    needs_review = distinct_reporters_count >= 3

    # History of earlier reports on this farmer's other listings
    farmer_history_reports = ListingReport.query.join(Product).filter(
        Product.farmer_id == farmer.id,
        ListingReport.product_id != product.id
    ).order_by(ListingReport.created_at.desc()).limit(15).all()

    # Admin notes on this farmer
    farmer_notes = AdminNote.query.filter_by(user_id=farmer.id).order_by(AdminNote.created_at.desc()).all()

    return render_template(
        'admin/report_detail.html',
        report=report,
        product=product,
        farmer=farmer,
        all_listing_reports=all_listing_reports,
        distinct_reporters_count=distinct_reporters_count,
        needs_review=needs_review,
        farmer_history_reports=farmer_history_reports,
        farmer_notes=farmer_notes
    )


@admin_bp.route('/reports/<int:report_id>/hide-listing', methods=['POST'])
def hide_listing_from_report(report_id):
    report = ListingReport.query.get_or_404(report_id)
    product = report.product

    before_data = {'is_available': product.is_available, 'hidden_reason': product.hidden_reason}
    product.is_available = False
    product.hidden_reason = 'moderation'
    product.hidden_by = current_user.id

    # Resolve all open/reviewing reports on this product
    active_reports = ListingReport.query.filter(
        ListingReport.product_id == product.id,
        ListingReport.status.in_(['open', 'reviewing'])
    ).all()

    for r in active_reports:
        r.status = 'resolved'
        r.resolution_note = 'Listing hidden by administrator due to moderation'
        r.handled_by = current_user.id
        r.handled_at = datetime.utcnow()

    _audit(
        'listing_hidden_moderation', 'product', product.id,
        f"Admin hid listing '{product.name}' (moderation from report #{report.id})",
        before_data=before_data,
        after_data={'is_available': False, 'hidden_reason': 'moderation'}
    )
    db.session.commit()
    flash(f"Listing '{product.name}' hidden from marketplace. Open reports resolved.", 'success')
    return redirect(url_for('admin.listing_report_detail', report_id=report.id))


@admin_bp.route('/reports/<int:report_id>/dismiss', methods=['POST'])
def dismiss_listing_report(report_id):
    report = ListingReport.query.get_or_404(report_id)
    report.status = 'dismissed'
    report.handled_by = current_user.id
    report.handled_at = datetime.utcnow()

    _audit('listing_report_dismissed', 'listing_report', report.id, f"Dismissed report #{report.id} on '{report.product.name}'")
    db.session.commit()
    flash(f"Report #{report.id} dismissed.", 'info')
    return redirect(url_for('admin.listing_report_detail', report_id=report.id))


@admin_bp.route('/reports/<int:report_id>/resolve', methods=['POST'])
def resolve_listing_report(report_id):
    report = ListingReport.query.get_or_404(report_id)
    note = request.form.get('resolution_note', '').strip()
    if not note:
        note = 'Resolved by administrator'

    report.status = 'resolved'
    report.resolution_note = note
    report.handled_by = current_user.id
    report.handled_at = datetime.utcnow()

    _audit('listing_report_resolved', 'listing_report', report.id, f"Resolved report #{report.id}: {note}")
    db.session.commit()
    flash(f"Report #{report.id} marked as resolved.", 'success')
    return redirect(url_for('admin.listing_report_detail', report_id=report.id))


@admin_bp.route('/reports/<int:report_id>/note', methods=['POST'])
def add_report_farmer_note(report_id):
    report = ListingReport.query.get_or_404(report_id)
    farmer_id = report.product.farmer_id
    note_text = request.form.get('note', '').strip()
    if not note_text:
        flash('Note cannot be empty.', 'error')
        return redirect(url_for('admin.listing_report_detail', report_id=report.id))

    note = AdminNote(
        user_id=farmer_id,
        admin_id=current_user.id,
        note=f"[Regarding Report #{report.id} on '{report.product.name}'] {note_text}"
    )
    db.session.add(note)
    _audit('admin_note_added', 'user', farmer_id, f"Added internal admin note from report #{report.id}")
    db.session.commit()
    flash('Internal note added for farmer.', 'success')
    return redirect(url_for('admin.listing_report_detail', report_id=report.id))


@admin_bp.route('/reports/<report_type>.csv')
def report_csv(report_type):
    start, end = _date_range()
    filtered_orders_q = _filtered_orders_query()

    def stream_rows():
        # UTF-8 BOM so Excel opens Sinhala and Tamil characters correctly
        yield '\ufeff'

        out = io.StringIO()
        writer = csv.writer(out)

        if report_type == 'users':
            writer.writerow([sanitize_csv_cell(h) for h in ['id', 'name', 'email', 'role', 'active', 'created_at']])
            yield out.getvalue()
            query = User.query.order_by(User.created_at.desc())
            if start: query = query.filter(User.created_at >= start)
            if end: query = query.filter(User.created_at < end)
            count = 0
            for u in query.yield_per(1000):
                count += 1
                if count > 50000:
                    out = io.StringIO()
                    writer = csv.writer(out)
                    writer.writerow(["EXPORT CAPPED AT 50,000 ROWS", ""])
                    yield out.getvalue()
                    break
                out = io.StringIO()
                writer = csv.writer(out)
                writer.writerow([sanitize_csv_cell(val) for val in [u.id, u.name, u.email, u.role, u.is_active, u.created_at]])
                yield out.getvalue()

        elif report_type == 'orders':
            writer.writerow([sanitize_csv_cell(h) for h in ['id', 'buyer', 'product', 'status', 'items_total', 'delivery_fee', 'total_price', 'created_at']])
            yield out.getvalue()
            query = filtered_orders_q.order_by(Order.created_at.desc())
            count = 0
            for o in query.yield_per(1000):
                count += 1
                if count > 50000:
                    out = io.StringIO()
                    writer = csv.writer(out)
                    writer.writerow(["EXPORT CAPPED AT 50,000 ROWS", ""])
                    yield out.getvalue()
                    break
                out = io.StringIO()
                writer = csv.writer(out)
                writer.writerow([sanitize_csv_cell(val) for val in [
                    o.id,
                    o.buyer.name if o.buyer else '',
                    o.product.name if o.product else '',
                    o.status,
                    o.items_total,
                    o.delivery_fee,
                    o.total_price,
                    o.created_at
                ]])
                yield out.getvalue()

        elif report_type == 'sales':
            writer.writerow([sanitize_csv_cell(h) for h in ['metric', 'value']])
            yield out.getvalue()
            query = filtered_orders_q
            orders_list = query.all()
            total_orders = len(orders_list)
            sales_sum = sum((Decimal(str(r.total_price or 0)) for r in orders_list), Decimal('0'))
            fees_sum = sum((Decimal(str(r.delivery_fee or 0)) for r in orders_list), Decimal('0'))

            for row in [
                ['orders', total_orders],
                ['sales_total', sales_sum],
                ['delivery_fees', fees_sum]
            ]:
                out = io.StringIO()
                writer = csv.writer(out)
                writer.writerow([sanitize_csv_cell(c) for c in row])
                yield out.getvalue()
        else:
            return

    if report_type not in ('users', 'orders', 'sales'):
        return 'Unknown report', 404

    _audit('report_exported', 'report', None, report_type)
    db.session.commit()

    return Response(
        stream_with_context(stream_rows()),
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename=agrolink-{report_type}.csv',
            'X-Content-Type-Options': 'nosniff',
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache'
        }
    )


@admin_bp.route('/activity')
def activity():
    query = AdminAuditLog.query
    search = request.args.get('q', '').strip()
    action = request.args.get('action', '').strip()
    result = request.args.get('result', '').strip()
    admin_id = request.args.get('admin_id', type=int)
    start, end = _date_range()
    sort = request.args.get('sort', 'created_at').strip()
    direction = request.args.get('direction', 'desc').strip()
    page = request.args.get('page', 1, type=int)

    if search:
        query = query.filter(
            AdminAuditLog.details.ilike(f'%{search}%') |
            AdminAuditLog.target_type.ilike(f'%{search}%') |
            AdminAuditLog.action.ilike(f'%{search}%')
        )
    if action:
        query = query.filter(AdminAuditLog.action == action)
    if result:
        query = query.filter(AdminAuditLog.result == result)
    if admin_id:
        query = query.filter(AdminAuditLog.admin_id == admin_id)
    if start:
        query = query.filter(AdminAuditLog.created_at >= start)
    if end:
        query = query.filter(AdminAuditLog.created_at < end)

    sort_cols = {
        'created_at': AdminAuditLog.created_at,
        'action': AdminAuditLog.action,
        'result': AdminAuditLog.result,
    }
    sort_column = sort_cols.get(sort, AdminAuditLog.created_at)
    if direction == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    pagination = query.paginate(page=page, per_page=20, error_out=False)

    # Distinct actions and admins for dropdown filters
    admins = User.query.filter_by(role='admin').order_by(User.name).all()
    actions = [r[0] for r in db.session.query(AdminAuditLog.action).distinct().order_by(AdminAuditLog.action).all()]

    return render_template(
        'admin/activity.html',
        pagination=pagination,
        logs=pagination.items,
        search=search,
        action=action,
        result=result,
        admin_id=admin_id,
        admins=admins,
        actions=actions,
        start=request.args.get('start', ''),
        end=request.args.get('end', ''),
        sort=sort,
        direction=direction
    )


# ─── 1. FARMER VERIFICATION ROUTES ──────────────────────────────────────────
@admin_bp.route('/verifications')
def verifications():
    status = request.args.get('status', 'pending').strip().lower()
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    query = VerificationRequest.query.join(User, VerificationRequest.farmer_id == User.id)

    if status and status != 'all':
        query = query.filter(VerificationRequest.status == status)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (User.name.ilike(search_pattern)) |
            (User.email.ilike(search_pattern)) |
            (User.farm_name.ilike(search_pattern))
        )

    query = query.order_by(VerificationRequest.created_at.desc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)

    counts = {
        'pending': VerificationRequest.query.filter_by(status='pending').count(),
        'approved': VerificationRequest.query.filter_by(status='approved').count(),
        'rejected': VerificationRequest.query.filter_by(status='rejected').count(),
        'total': VerificationRequest.query.count(),
    }

    # Attach checklist facts to each request
    for req in pagination.items:
        farmer = req.farmer
        req.has_map_pin = bool(farmer.latitude is not None and farmer.longitude is not None)
        req.has_whatsapp = bool(farmer.whatsapp_number)
        req.has_farm_name = bool(farmer.farm_name)
        req.has_bio = bool(farmer.bio)
        req.has_photo = bool(farmer.profile_image_url)
        req.active_listings_count = farmer.active_products_count
        req.account_age_days = (datetime.utcnow() - farmer.created_at).days if farmer.created_at else 0

    return render_template(
        'admin/verifications.html',
        requests=pagination.items,
        pagination=pagination,
        counts=counts,
        status=status,
        search=search
    )


@admin_bp.route('/verifications/<int:request_id>/approve', methods=['POST'])
def approve_verification(request_id):
    req = VerificationRequest.query.get_or_404(request_id)
    farmer = req.farmer

    before_data = {'is_verified': farmer.is_verified, 'request_status': req.status}
    req.status = 'approved'
    req.decided_at = datetime.utcnow()
    req.decided_by = current_user.id

    farmer.is_verified = True
    farmer.verified_at = datetime.utcnow()
    farmer.verified_by = current_user.id

    _audit(
        'farmer_verification_approved', 'user', farmer.id,
        f"Approved verification request #{req.id} for farmer {farmer.name} ({farmer.email})",
        before_data=before_data,
        after_data={'is_verified': True, 'request_status': 'approved'}
    )
    db.session.commit()
    flash(f"Farmer '{farmer.name}' is now verified! Verified badge will be shown on listings.", 'success')
    return redirect(url_for('admin.verifications'))


@admin_bp.route('/verifications/<int:request_id>/reject', methods=['POST'])
def reject_verification(request_id):
    req = VerificationRequest.query.get_or_404(request_id)
    farmer = req.farmer

    reason = request.form.get('admin_note', '').strip()
    if not reason:
        flash('A rejection reason is mandatory and will be shown to the farmer.', 'error')
        return redirect(url_for('admin.verifications'))

    before_data = {'request_status': req.status}
    req.status = 'rejected'
    req.admin_note = reason
    req.decided_at = datetime.utcnow()
    req.decided_by = current_user.id

    _audit(
        'farmer_verification_rejected', 'user', farmer.id,
        f"Rejected verification request #{req.id} for farmer {farmer.name}. Reason: {reason}",
        before_data=before_data,
        after_data={'request_status': 'rejected', 'reason': reason}
    )
    db.session.commit()
    flash(f"Verification request #{req.id} rejected.", 'info')
    return redirect(url_for('admin.verifications'))


@admin_bp.route('/users/<int:user_id>/revoke-verification', methods=['POST'])
def revoke_verification(user_id):
    user = User.query.get_or_404(user_id)
    if not user.is_verified:
        flash(f"User '{user.name}' is not currently verified.", 'error')
        return redirect(request.referrer or url_for('admin.verifications'))

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('A reason for revoking verification is mandatory.', 'error')
        return redirect(request.referrer or url_for('admin.verifications'))

    before_data = {'is_verified': True}
    user.is_verified = False
    user.verified_at = None
    user.verified_by = None

    note = AdminNote(
        user_id=user.id,
        admin_id=current_user.id,
        note=f"Farmer verification revoked by administrator ({current_user.name}). Reason: {reason}"
    )
    db.session.add(note)

    _audit(
        'farmer_verification_revoked', 'user', user.id,
        f"Revoked verification for farmer {user.name}. Reason: {reason}",
        before_data=before_data,
        after_data={'is_verified': False, 'reason': reason}
    )
    db.session.commit()
    flash(f"Verification revoked for '{user.name}'.", 'warning')
    return redirect(request.referrer or url_for('admin.verifications'))


# ─── 4. CROPS OVERVIEW ROUTE (READ-ONLY) ────────────────────────────────────
@admin_bp.route('/crops')
def crops():
    status = request.args.get('status', 'all').strip().lower()
    district = request.args.get('district', '').strip()
    category = request.args.get('category', '').strip()
    harvest_due = request.args.get('harvest_due', '').strip()
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Crop.query.join(User, Crop.farmer_id == User.id)

    today = datetime.utcnow().date()
    in_14_days = today + timedelta(days=14)

    if status and status != 'all':
        query = query.filter(Crop.status == status)

    if district:
        query = query.filter(
            (User.location.ilike(f"%{district}%")) |
            (Crop.field_location.ilike(f"%{district}%"))
        )

    if category:
        query = query.filter(Crop.crop_type.ilike(f"%{category}%"))

    if harvest_due == '1':
        query = query.filter(Crop.expected_harvest_date >= today, Crop.expected_harvest_date <= in_14_days)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Crop.crop_name.ilike(search_pattern)) |
            (User.name.ilike(search_pattern))
        )

    # Sort by expected harvest date ascending
    query = query.order_by(Crop.expected_harvest_date.asc())
    pagination = query.paginate(page=page, per_page=20, error_out=False)

    # Summary cards calculations across entire crops table
    total_qty_scalar = db.session.query(func.coalesce(func.sum(Crop.quantity_kg), 0)).scalar()
    growing_qty_scalar = db.session.query(func.coalesce(func.sum(Crop.quantity_kg), 0)).filter(Crop.status == 'growing').scalar()
    ready_qty_scalar = db.session.query(func.coalesce(func.sum(Crop.quantity_kg), 0)).filter(Crop.status == 'ready').scalar()
    due_14_qty_scalar = db.session.query(func.coalesce(func.sum(Crop.quantity_kg), 0)).filter(
        Crop.expected_harvest_date >= today,
        Crop.expected_harvest_date <= in_14_days
    ).scalar()

    # Total expected quantity by crop (top 5 crops by quantity)
    crop_breakdown = db.session.query(
        Crop.crop_name,
        func.sum(Crop.quantity_kg).label('total_kg')
    ).group_by(Crop.crop_name).order_by(func.sum(Crop.quantity_kg).desc()).limit(5).all()

    # Get available crop categories and districts for filter dropdowns
    categories = [r[0] for r in db.session.query(Crop.crop_type).distinct().order_by(Crop.crop_type).all() if r[0]]
    districts = [r[0] for r in db.session.query(User.location).filter(User.role == 'farmer').distinct().order_by(User.location).all() if r[0]]

    return render_template(
        'admin/crops.html',
        crops=pagination.items,
        pagination=pagination,
        status=status,
        district=district,
        category=category,
        harvest_due=harvest_due,
        search=search,
        total_qty=total_qty_scalar,
        growing_qty=growing_qty_scalar,
        ready_qty=ready_qty_scalar,
        due_14_qty=due_14_qty_scalar,
        crop_breakdown=crop_breakdown,
        categories=categories,
        districts=districts,
        today=today
    )
