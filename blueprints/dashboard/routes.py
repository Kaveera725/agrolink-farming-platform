from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Crop, Product, Order, User
from utils.decorators import roles_required
from utils.geo import parse_coord, is_in_sri_lanka, time_ago

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@login_required
def index():
    # Sri Lanka Local Time is UTC+5:30
    now_lk = datetime.utcnow() + timedelta(hours=5, minutes=30)
    if now_lk.hour < 12:
        greeting = "Good morning"
    elif now_lk.hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    today_date = now_lk.date()

    if current_user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == 'farmer':
        crops = Crop.query.filter_by(farmer_id=current_user.id).order_by(Crop.created_at.desc()).all()
        # Annotate crops with harvest countdown and overdue status
        for c in crops:
            if c.expected_harvest_date:
                diff = (c.expected_harvest_date - today_date).days
                c.days_remaining = diff
                c.is_overdue = (diff < 0 and c.status != 'harvested')
            else:
                c.days_remaining = None
                c.is_overdue = False

        products = Product.query.filter_by(farmer_id=current_user.id, is_deleted=False).order_by(Product.created_at.desc()).all()
        all_orders = Order.query.join(Product).filter(
            Product.farmer_id == current_user.id
        ).order_by(Order.created_at.desc()).all()
        pending_orders = [o for o in all_orders if o.status == 'pending']
        total_revenue = sum(
            o.total_price for o in all_orders if o.status not in ('cancelled', 'rejected')
        )
        return render_template('dashboard/farmer.html',
                               crops=crops, products=products,
                               orders=all_orders, pending_orders=pending_orders,
                               total_revenue=total_revenue, greeting=greeting,
                               today=today_date)
    else:
        all_orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
        active_orders = [o for o in all_orders if o.status in ('pending', 'confirmed')]
        completed_orders = [o for o in all_orders if o.status == 'delivered']
        past_orders = [o for o in all_orders if o.status in ('delivered', 'cancelled', 'rejected')]
        total_spent = sum(o.total_price for o in all_orders if o.status not in ('cancelled', 'rejected'))

        # Best deals today for buyer dashboard
        try:
            from blueprints.marketplace.routes import annotate_product_deals
            candidate_products = Product.query.filter_by(is_available=True, is_deleted=False).order_by(Product.created_at.desc()).limit(12).all()
            annotate_product_deals(candidate_products)
            best_deals = [p for p in candidate_products if getattr(p, 'is_deal', False)]
            if len(best_deals) < 4:
                seen_ids = {p.id for p in best_deals}
                for p in candidate_products:
                    if p.id not in seen_ids and len(best_deals) < 6:
                        best_deals.append(p)
        except Exception:
            best_deals = []

        return render_template('dashboard/buyer.html',
                               orders=all_orders, active_orders=active_orders,
                               completed_orders=completed_orders, past_orders=past_orders,
                               total_spent=total_spent, best_deals=best_deals,
                               greeting=greeting)



# ── CROP MANAGEMENT ──────────────────────────────────────────────────────────

@dashboard_bp.route('/crops')
@roles_required('farmer')
def crops():
    crops = Crop.query.filter_by(farmer_id=current_user.id).order_by(Crop.created_at.desc()).all()
    return render_template('dashboard/crops.html', crops=crops)


@dashboard_bp.route('/crops/add', methods=['GET', 'POST'])
@roles_required('farmer')
def add_crop():
    if request.method == 'POST':
        crop_name = request.form.get('crop_name', '').strip()
        crop_type = request.form.get('crop_type', '').strip()
        quantity_kg = request.form.get('quantity_kg', 0)
        harvest_date = request.form.get('expected_harvest_date', '')
        field_location = request.form.get('field_location', '').strip()
        notes = request.form.get('notes', '').strip()
        status = request.form.get('status', 'growing')

        if not crop_name or not crop_type or not harvest_date:
            flash('Crop name, type and harvest date are required.', 'error')
            return render_template('dashboard/crop_form.html', action='Add')
        try:
            harvest_date = date.fromisoformat(harvest_date)
            quantity_kg = float(quantity_kg)
        except (ValueError, TypeError):
            flash('Invalid date or quantity.', 'error')
            return render_template('dashboard/crop_form.html', action='Add')

        crop = Crop(farmer_id=current_user.id, crop_name=crop_name, crop_type=crop_type,
                    quantity_kg=quantity_kg, expected_harvest_date=harvest_date,
                    field_location=field_location, notes=notes, status=status)
        db.session.add(crop)
        db.session.commit()
        flash('Crop added successfully!', 'success')
        return redirect(url_for('dashboard.crops'))
    return render_template('dashboard/crop_form.html', action='Add', crop=None)


@dashboard_bp.route('/crops/<int:crop_id>/edit', methods=['GET', 'POST'])
@roles_required('farmer')
def edit_crop(crop_id):
    crop = Crop.query.filter_by(id=crop_id, farmer_id=current_user.id).first_or_404()
    if request.method == 'POST':
        crop.crop_name = request.form.get('crop_name', crop.crop_name).strip()
        crop.crop_type = request.form.get('crop_type', crop.crop_type).strip()
        crop.field_location = request.form.get('field_location', '').strip()
        crop.notes = request.form.get('notes', '').strip()
        crop.status = request.form.get('status', crop.status)
        try:
            crop.quantity_kg = float(request.form.get('quantity_kg', crop.quantity_kg))
            crop.expected_harvest_date = date.fromisoformat(request.form.get('expected_harvest_date'))
        except (ValueError, TypeError):
            flash('Invalid date or quantity.', 'error')
            return render_template('dashboard/crop_form.html', action='Edit', crop=crop)
        db.session.commit()
        flash('Crop updated successfully!', 'success')
        return redirect(url_for('dashboard.crops'))
    return render_template('dashboard/crop_form.html', action='Edit', crop=crop)


@dashboard_bp.route('/crops/<int:crop_id>/delete', methods=['POST'])
@roles_required('farmer')
def delete_crop(crop_id):
    crop = Crop.query.filter_by(id=crop_id, farmer_id=current_user.id).first_or_404()
    db.session.delete(crop)
    db.session.commit()
    flash('Crop deleted.', 'info')
    return redirect(url_for('dashboard.crops'))


@dashboard_bp.route('/update-location', methods=['POST'])
@login_required
def update_location():
    """
    Farmer-only endpoint to update geolocation coordinates.
    CSRF protected, validates Sri Lanka bounds, saves lat/lng,
    sets location_updated_at, and returns JSON.
    """
    if current_user.role != 'farmer':
        return jsonify({'success': False, 'error': 'Only farmers can update farm location.'}), 403

    data = request.get_json(silent=True) or request.form
    lat_val = data.get('latitude')
    lng_val = data.get('longitude')
    addr_val = data.get('address_text', '').strip() if data.get('address_text') else ''

    parsed_lat = parse_coord(lat_val)
    parsed_lng = parse_coord(lng_val)

    if parsed_lat is None or parsed_lng is None:
        return jsonify({'success': False, 'error': 'Invalid coordinates provided.'}), 400

    if not is_in_sri_lanka(parsed_lat, parsed_lng):
        return jsonify({'success': False, 'error': 'Location must be within Sri Lanka (latitude 5.8-9.9, longitude 79.4-82.0).'}), 400

    current_user.latitude = parsed_lat
    current_user.longitude = parsed_lng
    current_user.location_updated_at = datetime.utcnow()
    if addr_val:
        current_user.address_text = addr_val

    db.session.commit()

    rel_time = time_ago(current_user.location_updated_at)
    return jsonify({
        'success': True,
        'message': 'Your farm location has been updated successfully!',
        'latitude': float(current_user.latitude),
        'longitude': float(current_user.longitude),
        'time_ago': rel_time,
        'location_updated_at_ago': rel_time
    })