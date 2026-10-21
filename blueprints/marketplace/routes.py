from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import Product

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/marketplace')

CATEGORIES = ['Vegetables', 'Fruits', 'Grains & Rice', 'Spices', 'Pulses', 'Roots & Tubers', 'Other']

PRODUCT_IMAGES = {
    'Vegetables': 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=400&q=80',
    'Fruits': 'https://images.unsplash.com/photo-1490474418585-ba9bad8fd0ea?w=400&q=80',
    'Grains & Rice': 'https://images.unsplash.com/photo-1586201375761-83865001e31c?w=400&q=80',
    'Spices': 'https://images.unsplash.com/photo-1506368249639-73a05d6f6488?w=400&q=80',
    'Pulses': 'https://images.unsplash.com/photo-1515543904379-3d757afe72e4?w=400&q=80',
    'Roots & Tubers': 'https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=400&q=80',
    'Other': 'https://images.unsplash.com/photo-1464226184884-fa280b87c399?w=400&q=80',
}


@marketplace_bp.route('/')
def index():
    category = request.args.get('category', '')
    search = request.args.get('search', '').strip()

    query = Product.query.filter_by(is_available=True)

    if category:
        query = query.filter_by(category=category)

    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))

    # 🔥 IMPORTANT: SORT BY LOWEST PRICE FIRST
    products = query.order_by(Product.price_per_kg.asc()).all()

    return render_template(
        'marketplace/index.html',
        products=products,
        categories=CATEGORIES,
        selected_category=category,
        search=search
    )


@marketplace_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    related = Product.query.filter(
        Product.category == product.category,
        Product.id != product.id,
        Product.is_available == True
    ).limit(4).all()
    return render_template('marketplace/product_detail.html', product=product, related=related)


@marketplace_bp.route('/list', methods=['GET', 'POST'])
@login_required
def list_product():
    if current_user.role != 'farmer':
        flash('Only farmers can list products.', 'error')
        return redirect(url_for('marketplace.index'))
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        try:
            quantity_kg = float(request.form.get('quantity_kg', 0))
            price_per_kg = float(request.form.get('price_per_kg', 0))
        except (ValueError, TypeError):
            flash('Invalid quantity or price.', 'error')
            return render_template('marketplace/product_form.html', categories=CATEGORIES, product=None)

        if not name or not category or quantity_kg <= 0 or price_per_kg <= 0:
            flash('All required fields must be filled correctly.', 'error')
            return render_template('marketplace/product_form.html', categories=CATEGORIES, product=None)

        image_url = PRODUCT_IMAGES.get(category, PRODUCT_IMAGES['Other'])
        product = Product(farmer_id=current_user.id, name=name, category=category,
                          description=description, quantity_kg=quantity_kg,
                          price_per_kg=price_per_kg, location=location, image_url=image_url)
        db.session.add(product)
        db.session.commit()
        flash('Product listed successfully!', 'success')
        return redirect(url_for('marketplace.index'))
    return render_template('marketplace/product_form.html', categories=CATEGORIES, product=None)


@marketplace_bp.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    product = Product.query.filter_by(id=product_id, farmer_id=current_user.id).first_or_404()
    if request.method == 'POST':
        product.name = request.form.get('name', product.name).strip()
        product.category = request.form.get('category', product.category).strip()
        product.description = request.form.get('description', '').strip()
        product.location = request.form.get('location', '').strip()
        product.is_available = request.form.get('is_available') == 'on'
        try:
            product.quantity_kg = float(request.form.get('quantity_kg', product.quantity_kg))
            product.price_per_kg = float(request.form.get('price_per_kg', product.price_per_kg))
        except (ValueError, TypeError):
            flash('Invalid quantity or price.', 'error')
            return render_template('marketplace/product_form.html', categories=CATEGORIES, product=product)
        product.image_url = PRODUCT_IMAGES.get(product.category, PRODUCT_IMAGES['Other'])
        db.session.commit()
        flash('Product updated!', 'success')
        return redirect(url_for('dashboard.index'))
    return render_template('marketplace/product_form.html', categories=CATEGORIES, product=product)


@marketplace_bp.route('/product/<int:product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    product = Product.query.filter_by(id=product_id, farmer_id=current_user.id).first_or_404()
    product.is_available = False
    db.session.commit()
    flash('Product removed from listing.', 'info')
    return redirect(url_for('dashboard.index'))