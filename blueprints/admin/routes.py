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
from models import AdminAuditLog, AdminNote, MarketPrice, Order, Product, User
from utils.decorators import roles_required
from utils.phone import normalize_phone_number, validate_sl_phone
from utils.security import generate_temp_password, sanitize_csv_cell

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


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
    return render_template(
        'admin/dashboard.html',
        totals=totals,
        status_counts=status_counts,
        recent_orders=orders[:8],
        registrations=registrations,
        chart_labels=chart_labels,
        chart_values=chart_values
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
    return render_template('admin/order_detail.html', order=Order.query.get_or_404(order_id))


@admin_bp.route('/prices', methods=['GET', 'POST'])
def prices():
    editing = None
    edit_id = request.args.get('edit', type=int)
    if edit_id:
        editing = MarketPrice.query.get_or_404(edit_id)

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

        if not price.crop_name or not price.category:
            flash('Crop name and category are required.', 'error')
            return redirect(url_for('admin.prices', edit=edit_id) if edit_id else url_for('admin.prices'))

        db.session.add(price)
        db.session.flush()

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
        search=search,
        sort=sort,
        direction=direction
    )


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


@admin_bp.route('/reports')
def reports():
    return render_template('admin/reports.html', start=request.args.get('start', ''), end=request.args.get('end', ''))


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
