import math
from decimal import Decimal, ROUND_HALF_UP
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError, OperationalError, DataError
from extensions import db, limiter
from flask_limiter.util import get_remote_address
from models import Order, Product
from utils.decorators import roles_required
from utils.geo import parse_coord, is_in_sri_lanka
from services.distance import get_driving_distance_km
from services.pricing import calculate_delivery_fee, calculate_order_totals
from config import MAX_DELIVERY_KM

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')


def get_user_rate_limit_key():
    """Rate limit key based on authenticated user ID or client IP."""
    if current_user.is_authenticated:
        return f"user:{current_user.id}"
    return get_remote_address()


@orders_bp.route('/')
@login_required
def index():
    if current_user.role == 'buyer':
        orders = Order.query.filter_by(buyer_id=current_user.id).order_by(Order.created_at.desc()).all()
    else:
        orders = Order.query.join(Product).filter(
            Product.farmer_id == current_user.id
        ).order_by(Order.created_at.desc()).all()
    return render_template('orders/index.html', orders=orders)


@orders_bp.route('/quote', methods=['POST'])
@login_required
@limiter.limit("20 per minute", key_func=get_user_rate_limit_key)
def get_quote():
    """Calculate a live price quote including distance and delivery fee."""
    if current_user.role != 'buyer':
        return jsonify({'error': 'Only buyers can request delivery price quotes.'}), 403

    data = request.get_json(silent=True) or request.form or {}
    product_id = data.get('product_id')
    if not product_id:
        return jsonify({'error': 'product_id is required.'}), 400

    try:
        product_id = int(product_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid product_id.'}), 400

    product = Product.query.filter_by(id=product_id, is_deleted=False).first()
    if not product:
        return jsonify({'error': 'Product not found.'}), 404

    if not product.is_available or (product.quantity_kg is not None and product.quantity_kg <= 0):
        return jsonify({'error': 'This product is currently out of stock.'}), 422

    raw_qty = data.get('quantity') if data.get('quantity') is not None else data.get('quantity_kg')
    if raw_qty is None:
        return jsonify({'error': 'quantity is required.'}), 400

    try:
        qty_dec = Decimal(str(raw_qty))
        if qty_dec <= Decimal('0'):
            return jsonify({'error': 'Quantity must be greater than zero.'}), 400
    except Exception:
        return jsonify({'error': 'Invalid quantity value.'}), 400

    if product.quantity_kg is not None and qty_dec > Decimal(str(product.quantity_kg)):
        return jsonify({
            'error': f'Requested quantity ({qty_dec:g} kg) exceeds available stock ({product.quantity_kg:g} kg).'
        }), 422

    price_dec = Decimal(str(product.price_per_kg))
    items_total = (qty_dec * price_dec).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    fulfillment_type = str(data.get('fulfillment_type', 'pickup')).strip().lower()
    if fulfillment_type not in ('pickup', 'delivery'):
        return jsonify({'error': "Invalid fulfillment_type. Must be 'pickup' or 'delivery'."}), 400

    if fulfillment_type == 'pickup':
        totals = calculate_order_totals(items_total, Decimal('0.00'))
        return jsonify({
            'items_total': float(totals['items_total']),
            'distance_km': None,
            'distance_source': None,
            'delivery_fee': 0.0,
            'grand_total': float(totals['grand_total']),
            'currency': 'LKR',
            'message': "Pickup from farmer's harvest collection point."
        }), 200

    # Fulfillment is delivery
    if not product.offers_delivery:
        return jsonify({'error': 'Delivery is not offered for this product. Please choose pickup.'}), 422

    farmer = product.farmer
    if not farmer or farmer.latitude is None or farmer.longitude is None:
        return jsonify({'error': 'Farmer has not set a pickup location pin. Delivery is unavailable.'}), 422

    delivery_lat = data.get('delivery_lat')
    delivery_lng = data.get('delivery_lng')
    p_lat = parse_coord(delivery_lat)
    p_lng = parse_coord(delivery_lng)

    if p_lat is None or p_lng is None:
        return jsonify({'error': 'Valid delivery latitude and longitude are required.'}), 400

    if not is_in_sri_lanka(p_lat, p_lng):
        return jsonify({'error': 'Delivery location must be within Sri Lanka bounds.'}), 422

    try:
        dist_km, dist_source = get_driving_distance_km(farmer.latitude, farmer.longitude, p_lat, p_lng)
    except ValueError as err:
        return jsonify({'error': str(err)}), 422

    if dist_km > MAX_DELIVERY_KM:
        return jsonify({
            'error': f'Delivery distance ({dist_km} km) exceeds maximum allowable radius ({MAX_DELIVERY_KM} km).'
        }), 422

    try:
        delivery_fee = calculate_delivery_fee(dist_km)
    except ValueError as err:
        return jsonify({'error': str(err)}), 422

    totals = calculate_order_totals(items_total, delivery_fee)

    message = (
        "Calculated via Google Routes."
        if dist_source == 'google'
        else "Estimated driving distance and fee based on direct route."
    )

    return jsonify({
        'items_total': float(totals['items_total']),
        'distance_km': float(dist_km),
        'distance_source': dist_source,
        'delivery_fee': float(totals['delivery_fee']),
        'grand_total': float(totals['grand_total']),
        'currency': 'LKR',
        'message': message
    }), 200


@orders_bp.route('/place/<int:product_id>', methods=['GET', 'POST'])
@roles_required('buyer')
def place_order(product_id):
    product = Product.query.filter_by(id=product_id, is_available=True, is_deleted=False).first_or_404()
    if product.farmer_id == current_user.id:
        flash("You can't order your own product.", 'error')
        return redirect(url_for('marketplace.product_detail', product_id=product_id))

    if request.method == 'POST':
        # Unit-level safety checks on quantity
        raw_quantity = request.form.get('quantity_kg', '')
        try:
            quantity_kg = float(raw_quantity)
            if math.isnan(quantity_kg) or math.isinf(quantity_kg):
                raise ValueError("Non-finite quantity")
        except (ValueError, TypeError):
            flash('Invalid quantity. Please enter a valid number.', 'error')
            return render_template('orders/place_order.html', product=product)

        if quantity_kg <= 0:
            flash('Quantity must be greater than zero.', 'error')
            return render_template('orders/place_order.html', product=product)

        fulfillment_type = request.form.get('fulfillment_type', 'pickup').strip().lower()
        if fulfillment_type not in ('pickup', 'delivery'):
            fulfillment_type = 'pickup'

        delivery_address = request.form.get('delivery_address', '').strip()
        notes = request.form.get('notes', '').strip()

        try:
            # Lock the product row with with_for_update() inside this transaction
            locked_product = Product.query.filter_by(id=product_id).with_for_update().populate_existing().first()
            if not locked_product or locked_product.is_deleted or not locked_product.is_available:
                flash('This product is no longer available.', 'error')
                return redirect(url_for('marketplace.index'))

            if locked_product.farmer_id == current_user.id:
                flash("You can't order your own product.", 'error')
                return redirect(url_for('marketplace.product_detail', product_id=product_id))

            if quantity_kg > locked_product.quantity_kg:
                flash(f'Stock changed: only {locked_product.quantity_kg:g} kg available. Please retry.', 'error')
                return render_template('orders/place_order.html', product=locked_product)

            items_total = (Decimal(str(quantity_kg)) * Decimal(str(locked_product.price_per_kg))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            delivery_lat = None
            delivery_lng = None
            distance_km = None
            distance_source = None
            delivery_fee = Decimal('0.00')

            if fulfillment_type == 'delivery':
                if not locked_product.offers_delivery:
                    flash('Delivery is not offered for this product. Please choose pickup.', 'error')
                    return render_template('orders/place_order.html', product=locked_product)

                if not locked_product.farmer or locked_product.farmer.latitude is None or locked_product.farmer.longitude is None:
                    flash('Farmer pickup location is missing. Delivery unavailable.', 'error')
                    return render_template('orders/place_order.html', product=locked_product)

                delivery_address = request.form.get('delivery_address', '').strip()
                if not delivery_address:
                    flash('Delivery address is required for delivery.', 'error')
                    return render_template('orders/place_order.html', product=locked_product)

                raw_lat = request.form.get('delivery_lat')
                raw_lng = request.form.get('delivery_lng')
                p_lat = parse_coord(raw_lat)
                p_lng = parse_coord(raw_lng)

                if p_lat is None or p_lng is None or not is_in_sri_lanka(p_lat, p_lng):
                    flash('Valid delivery location within Sri Lanka is required.', 'error')
                    return render_template('orders/place_order.html', product=locked_product)

                dist_km, dist_source = get_driving_distance_km(locked_product.farmer.latitude, locked_product.farmer.longitude, p_lat, p_lng)
                if dist_km > MAX_DELIVERY_KM:
                    flash(f'Delivery distance ({dist_km} km) exceeds maximum delivery radius ({MAX_DELIVERY_KM} km).', 'error')
                    return render_template('orders/place_order.html', product=locked_product)

                delivery_lat = p_lat
                delivery_lng = p_lng
                distance_km = dist_km
                distance_source = dist_source
                delivery_fee = calculate_delivery_fee(dist_km)
            else:
                delivery_address = None

            totals = calculate_order_totals(items_total, delivery_fee)
            total_price = totals['grand_total']

            order = Order(
                buyer_id=current_user.id,
                product_id=locked_product.id,
                quantity_kg=quantity_kg,
                total_price=total_price,
                fulfillment_type=fulfillment_type,
                delivery_lat=delivery_lat,
                delivery_lng=delivery_lng,
                distance_km=distance_km,
                distance_source=distance_source,
                items_total=items_total,
                delivery_fee=delivery_fee,
                delivery_address=delivery_address,
                notes=notes
            )
            locked_product.quantity_kg -= quantity_kg
            if locked_product.quantity_kg <= 0:
                locked_product.is_available = False

            db.session.add(order)
            db.session.commit()

            # TODO (Prompt 10): In-app notification to the farmer: new order placed
            flash(f'Order placed successfully! Total: LKR {total_price:,.2f}', 'success')
            return redirect(url_for('orders.order_detail', order_id=order.id))

        except (IntegrityError, OperationalError, DataError):
            db.session.rollback()
            flash('Stock changed, please retry.', 'error')
            return redirect(url_for('marketplace.product_detail', product_id=product_id))

    return render_template('orders/place_order.html', product=product)


@orders_bp.route('/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    # Privacy & Access Control: A user can only open their own orders (buyer)
    # or orders for their own products (farmer), or admin.
    if order.buyer_id != current_user.id and order.product.farmer_id != current_user.id and current_user.role != 'admin':
        abort(403)
    return render_template('orders/order_detail.html', order=order)


@orders_bp.route('/<int:order_id>/update-status', methods=['POST'])
@login_required
def update_status(order_id):
    order = Order.query.get_or_404(order_id)
    # Only the farmer who owns the product, or an admin
    if order.product.farmer_id != current_user.id and current_user.role != 'admin':
        abort(403)

    new_status = request.form.get('status', '').strip().lower()
    valid = ['confirmed', 'delivered', 'rejected']
    if new_status not in valid:
        flash('Invalid status.', 'error')
        return redirect(request.form.get('next') or url_for('orders.order_detail', order_id=order_id))

    current_status = order.status
    # State transitions:
    # pending -> confirmed, rejected
    # confirmed -> delivered
    # delivered, cancelled, rejected -> terminal
    if current_status == 'pending':
        if new_status not in ('confirmed', 'rejected'):
            flash(f'Cannot change order status from {current_status} to {new_status}.', 'error')
            return redirect(request.form.get('next') or url_for('orders.order_detail', order_id=order_id))
    elif current_status == 'confirmed':
        if new_status != 'delivered':
            flash(f'Cannot change order status from {current_status} to {new_status}.', 'error')
            return redirect(request.form.get('next') or url_for('orders.order_detail', order_id=order_id))
    else:
        flash(f'Order is already {current_status} and cannot be modified.', 'error')
        return redirect(request.form.get('next') or url_for('orders.order_detail', order_id=order_id))

    try:
        if new_status == 'rejected':
            reason = request.form.get('rejection_reason', '').strip()
            if len(reason) < 5:
                flash('Rejection reason must be at least 5 characters.', 'error')
                return redirect(request.form.get('next') or url_for('orders.order_detail', order_id=order_id))
            order.rejection_reason = reason
            order.status = 'rejected'
            product = Product.query.filter_by(id=order.product_id).with_for_update().populate_existing().first()
            if product:
                product.quantity_kg += order.quantity_kg
                if not product.is_deleted:
                    product.is_available = True
        elif new_status == 'confirmed':
            order.status = 'confirmed'
        elif new_status == 'delivered':
            order.status = 'delivered'

        db.session.commit()
        flash(f'Order #{order.id} updated to {order.status}.', 'success')
        return redirect(request.form.get('next') or url_for('orders.order_detail', order_id=order_id))
    except (IntegrityError, OperationalError, DataError):
        db.session.rollback()
        flash('Stock changed, please retry.', 'error')
        return redirect(request.form.get('next') or url_for('orders.order_detail', order_id=order_id))


@orders_bp.route('/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    # Only buyer (or admin) can cancel
    if order.buyer_id != current_user.id and current_user.role != 'admin':
        abort(403)

    if order.status != 'pending':
        flash('Only pending orders can be cancelled.', 'error')
        return redirect(url_for('orders.order_detail', order_id=order_id))

    try:
        order_locked = Order.query.filter_by(id=order_id).with_for_update().populate_existing().first()
        if not order_locked or order_locked.status != 'pending':
            flash('Only pending orders can be cancelled.', 'error')
            return redirect(url_for('orders.order_detail', order_id=order_id))

        product = Product.query.filter_by(id=order.product_id).with_for_update().populate_existing().first()
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('orders.order_detail', order_id=order_id))

        order_locked.status = 'cancelled'
        product.quantity_kg += order.quantity_kg
        # Cancelling an order restores stock and re-enables the product ONLY if it is not deleted.
        if not product.is_deleted:
            product.is_available = True

        db.session.commit()
        flash('Order cancelled.', 'info')
        return redirect(url_for('orders.index'))
    except (IntegrityError, OperationalError, DataError):
        db.session.rollback()
        flash('Stock changed, please retry.', 'error')
        return redirect(url_for('orders.order_detail', order_id=order_id))


@orders_bp.route('/<int:order_id>/pay', methods=['POST'])
@login_required
def initiate_payment(order_id):
    """Initiate a payment session and redirect buyer to the SimPay checkout."""
    from services.payments import create_payment_session
    payment, err = create_payment_session(order_id, current_user.id)
    if err or not payment:
        flash(err or 'Unable to initiate payment session.', 'danger')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    return redirect(url_for('gateway.checkout', txn_ref=payment.txn_ref))


@orders_bp.route('/payment-result/<txn_ref>', methods=['GET'])
@login_required
def payment_result(txn_ref: str):
    """
    Shop result page displaying the outcome of a payment.
    CRITICAL SECURITY: Reads payment status strictly from the database.
    Never trusts or parses any status parameters from the URL query string.
    """
    from models import Payment
    payment = Payment.query.filter_by(txn_ref=txn_ref).first_or_404()
    if payment.order.buyer_id != current_user.id and current_user.role != 'admin':
        abort(403)
    return render_template('orders/payment_result.html', payment=payment, order=payment.order)
