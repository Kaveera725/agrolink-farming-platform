from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from models import Order, Product

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
@login_required
def place_order(product_id):
    if current_user.role != 'buyer':
        flash('Only buyers can place orders.', 'error')
        return redirect(url_for('marketplace.index'))
    product = Product.query.filter_by(id=product_id, is_available=True).first_or_404()
    if product.farmer_id == current_user.id:
        flash("You can't order your own product.", 'error')
        return redirect(url_for('marketplace.product_detail', product_id=product_id))

    if request.method == 'POST':
        try:
            quantity_kg = float(request.form.get('quantity_kg', 0))
        except (ValueError, TypeError):
            flash('Invalid quantity.', 'error')
            return render_template('orders/place_order.html', product=product)

        if quantity_kg <= 0:
            flash('Quantity must be greater than zero.', 'error')
            return render_template('orders/place_order.html', product=product)
        if quantity_kg > product.quantity_kg:
            flash(f'Only {product.quantity_kg} kg available.', 'error')
            return render_template('orders/place_order.html', product=product)

        delivery_address = request.form.get('delivery_address', '').strip()
        notes = request.form.get('notes', '').strip()
        total_price = round(quantity_kg * product.price_per_kg, 2)

        order = Order(buyer_id=current_user.id, product_id=product.id,
                      quantity_kg=quantity_kg, total_price=total_price,
                      delivery_address=delivery_address, notes=notes)
        product.quantity_kg -= quantity_kg
        if product.quantity_kg <= 0:
            product.is_available = False
        db.session.add(order)
        db.session.commit()
        flash(f'Order placed successfully! Total: LKR {total_price:,.2f}', 'success')
        return redirect(url_for('orders.order_detail', order_id=order.id))

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
@login_required
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
    order.status = new_status
    db.session.commit()
    flash(f'Order status updated to {new_status}.', 'success')
    return redirect(url_for('orders.order_detail', order_id=order_id))


@orders_bp.route('/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.filter_by(id=order_id, buyer_id=current_user.id).first_or_404()
    if order.status not in ('pending',):
        flash('Only pending orders can be cancelled.', 'error')
        return redirect(url_for('orders.order_detail', order_id=order_id))
    order.status = 'cancelled'
    order.product.quantity_kg += order.quantity_kg
    order.product.is_available = True
    db.session.commit()
    flash('Order cancelled.', 'info')
    return redirect(url_for('orders.index'))