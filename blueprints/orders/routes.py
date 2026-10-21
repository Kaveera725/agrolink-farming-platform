import math
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError, OperationalError, DataError
from extensions import db
from models import Order, Product
from utils.decorators import roles_required

orders_bp = Blueprint('orders', __name__, url_prefix='/orders')


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


@orders_bp.route('/place/<int:product_id>', methods=['GET', 'POST'])
@roles_required('buyer')
def place_order(product_id):
    if request.method == 'POST':
        # Unit-level safety checks on quantity
        raw_quantity = request.form.get('quantity_kg', '')
        try:
            quantity_kg = float(raw_quantity)
            if math.isnan(quantity_kg) or math.isinf(quantity_kg):
                raise ValueError("Non-finite quantity")
        except (ValueError, TypeError):
            product = Product.query.filter_by(id=product_id, is_available=True, is_deleted=False).first_or_404()
            flash('Invalid quantity. Please enter a valid number.', 'error')
            return render_template('orders/place_order.html', product=product)

        if quantity_kg <= 0:
            product = Product.query.filter_by(id=product_id, is_available=True, is_deleted=False).first_or_404()
            flash('Quantity must be greater than zero.', 'error')
            return render_template('orders/place_order.html', product=product)

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

            total_price = round(quantity_kg * locked_product.price_per_kg, 2)
            order = Order(
                buyer_id=current_user.id,
                product_id=locked_product.id,
                quantity_kg=quantity_kg,
                total_price=total_price,
                delivery_address=delivery_address,
                notes=notes
            )
            locked_product.quantity_kg -= quantity_kg
            if locked_product.quantity_kg <= 0:
                locked_product.is_available = False

            db.session.add(order)
            db.session.commit()
            flash(f'Order placed successfully! Total: LKR {total_price:,.2f}', 'success')
            return redirect(url_for('orders.order_detail', order_id=order.id))

        except (IntegrityError, OperationalError, DataError):
            db.session.rollback()
            flash('Stock changed, please retry.', 'error')
            return redirect(url_for('marketplace.product_detail', product_id=product_id))

    product = Product.query.filter_by(id=product_id, is_available=True, is_deleted=False).first_or_404()
    if product.farmer_id == current_user.id:
        flash("You can't order your own product.", 'error')
        return redirect(url_for('marketplace.product_detail', product_id=product_id))

    return render_template('orders/place_order.html', product=product)


@orders_bp.route('/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    if order.buyer_id != current_user.id and order.product.farmer_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('orders.index'))
    return render_template('orders/order_detail.html', order=order)


@orders_bp.route('/<int:order_id>/update-status', methods=['POST'])
@roles_required('farmer')
def update_status(order_id):
    order = Order.query.get_or_404(order_id)
    if order.product.farmer_id != current_user.id:
        flash('Only the farmer can update order status.', 'error')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    new_status = request.form.get('status', '')
    valid = ['pending', 'confirmed', 'delivered', 'cancelled']
    if new_status not in valid:
        flash('Invalid status.', 'error')
        return redirect(url_for('orders.order_detail', order_id=order_id))

    try:
        prev_status = order.status
        order.status = new_status
        if prev_status != 'cancelled' and new_status == 'cancelled':
            product = Product.query.filter_by(id=order.product_id).with_for_update().populate_existing().first()
            if product:
                product.quantity_kg += order.quantity_kg
                if not product.is_deleted:
                    product.is_available = True

        db.session.commit()
        flash(f'Order status updated to {new_status}.', 'success')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    except (IntegrityError, OperationalError, DataError):
        db.session.rollback()
        flash('Stock changed, please retry.', 'error')
        return redirect(url_for('orders.order_detail', order_id=order_id))


@orders_bp.route('/<int:order_id>/cancel', methods=['POST'])
@roles_required('buyer')
def cancel_order(order_id):
    try:
        order = Order.query.filter_by(id=order_id, buyer_id=current_user.id).with_for_update().populate_existing().first_or_404()
        if order.status not in ('pending',):
            flash('Only pending orders can be cancelled.', 'error')
            return redirect(url_for('orders.order_detail', order_id=order_id))

        product = Product.query.filter_by(id=order.product_id).with_for_update().populate_existing().first()
        if not product:
            flash('Product not found.', 'error')
            return redirect(url_for('orders.order_detail', order_id=order_id))

        order.status = 'cancelled'
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