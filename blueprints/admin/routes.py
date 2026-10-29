import csv
import io
from collections import Counter
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import func

from extensions import db
from models import AdminAuditLog, MarketPrice, Order, Product, User
from utils.decorators import roles_required

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _audit(action, target_type=None, target_id=None, details=None):
    db.session.add(AdminAuditLog(
        admin_id=current_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    ))


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


def _filtered_orders():
    query = Order.query.order_by(Order.created_at.desc())
    status = request.args.get('status', '').strip()
    start, end = _date_range()
    if status:
        query = query.filter(Order.status == status)
    if start:
        query = query.filter(Order.created_at >= start)
    if end:
        query = query.filter(Order.created_at < end)
    return query


@admin_bp.before_request
@roles_required('admin')
def require_admin():
    pass


@admin_bp.route('/')
def dashboard():
    since = datetime.utcnow() - timedelta(days=29)
    orders = Order.query.order_by(Order.created_at.desc()).all()
    daily = Counter(order.created_at.date().isoformat() for order in orders if order.created_at and order.created_at >= since)
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
    return render_template('admin/dashboard.html', totals=totals, status_counts=status_counts,
                           recent_orders=orders[:8], registrations=registrations,
                           chart_labels=chart_labels, chart_values=chart_values)


@admin_bp.route('/users')
def users():
    query = User.query.order_by(User.created_at.desc())
    search = request.args.get('q', '').strip()
    role = request.args.get('role', '').strip()
    active = request.args.get('active', '').strip()
    if search:
        query = query.filter(User.name.ilike(f'%{search}%') | User.email.ilike(f'%{search}%'))
    if role:
        query = query.filter(User.role == role)
    if active in ('true', 'false'):
        query = query.filter(User.is_active == (active == 'true'))
    return render_template('admin/users.html', users=query.all(), search=search, role=role, active=active)


@admin_bp.route('/users/<int:user_id>')
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('admin/user_detail.html', user=user,
                           listings=Product.query.filter_by(farmer_id=user.id).order_by(Product.created_at.desc()).all(),
                           orders=Order.query.filter_by(buyer_id=user.id).order_by(Order.created_at.desc()).all())


@admin_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own admin account.', 'error')
        return redirect(request.referrer or url_for('admin.users'))
    user.is_active = not user.is_active
    _audit('user_status_changed', 'user', user.id, f'is_active={user.is_active}')
    db.session.commit()
    flash(f'{user.name} is now {"active" if user.is_active else "inactive"}.', 'success')
    return redirect(request.referrer or url_for('admin.users'))


@admin_bp.route('/listings')
def listings():
    query = Product.query.order_by(Product.created_at.desc())
    search = request.args.get('q', '').strip()
    if search:
        query = query.join(User).filter(Product.name.ilike(f'%{search}%') | User.name.ilike(f'%{search}%'))
    return render_template('admin/listings.html', listings=query.all(), search=search)


@admin_bp.route('/listings/<int:product_id>/toggle', methods=['POST'])
def toggle_listing(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_deleted = not product.is_deleted
    if product.is_deleted:
        product.is_available = False
    _audit('listing_moderation', 'product', product.id, f'is_deleted={product.is_deleted}')
    db.session.commit()
    flash(f'Listing {"hidden" if product.is_deleted else "restored"}.', 'success')
    return redirect(request.referrer or url_for('admin.listings'))


@admin_bp.route('/orders')
def orders():
    return render_template('admin/orders.html', orders=_filtered_orders().all(), status=request.args.get('status', ''),
                           start=request.args.get('start', ''), end=request.args.get('end', ''))


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
            return render_template('admin/prices.html', prices=MarketPrice.query.order_by(MarketPrice.crop_name).all(), editing=editing)
        price = MarketPrice.query.get(request.form.get('id', type=int)) if request.form.get('id') else MarketPrice()
        price.crop_name = request.form.get('crop_name', '').strip()
        price.category = request.form.get('category', '').strip()
        price.buying_price = buying
        price.selling_price = selling
        price.unit = request.form.get('unit', 'per kg').strip() or 'per kg'
        price.market_location = request.form.get('market_location', 'Colombo').strip() or 'Colombo'
        if not price.crop_name or not price.category:
            flash('Crop name and category are required.', 'error')
            return render_template('admin/prices.html', prices=MarketPrice.query.order_by(MarketPrice.crop_name).all(), editing=price)
        db.session.add(price)
        db.session.flush()
        _audit('market_price_saved', 'market_price', price.id, price.crop_name)
        db.session.commit()
        flash('Market price saved.', 'success')
        return redirect(url_for('admin.prices'))
    return render_template('admin/prices.html', prices=MarketPrice.query.order_by(MarketPrice.crop_name).all(), editing=editing)


@admin_bp.route('/prices/<int:price_id>/delete', methods=['POST'])
def delete_price(price_id):
    price = MarketPrice.query.get_or_404(price_id)
    _audit('market_price_deleted', 'market_price', price.id, price.crop_name)
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
    output = io.StringIO()
    writer = csv.writer(output)
    if report_type == 'users':
        query = User.query.order_by(User.created_at.desc())
        if start: query = query.filter(User.created_at >= start)
        if end: query = query.filter(User.created_at < end)
        writer.writerow(['id', 'name', 'email', 'role', 'active', 'created_at'])
        for user in query.all(): writer.writerow([user.id, user.name, user.email, user.role, user.is_active, user.created_at])
    elif report_type == 'orders':
        writer.writerow(['id', 'buyer', 'product', 'status', 'items_total', 'delivery_fee', 'total_price', 'created_at'])
        for order in _filtered_orders().all(): writer.writerow([order.id, order.buyer.name, order.product.name, order.status, order.items_total, order.delivery_fee, order.total_price, order.created_at])
    elif report_type == 'sales':
        query = _filtered_orders()
        rows = query.all()
        writer.writerow(['metric', 'value'])
        writer.writerow(['orders', len(rows)])
        writer.writerow(['sales_total', sum((Decimal(str(row.total_price or 0)) for row in rows), Decimal('0'))])
        writer.writerow(['delivery_fees', sum((Decimal(str(row.delivery_fee or 0)) for row in rows), Decimal('0'))])
    else:
        return 'Unknown report', 404
    _audit('report_exported', 'report', None, report_type)
    db.session.commit()
    return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename=agrolink-{report_type}.csv'})


@admin_bp.route('/activity')
def activity():
    logs = AdminAuditLog.query.order_by(AdminAuditLog.created_at.desc()).limit(200).all()
    return render_template('admin/activity.html', logs=logs)