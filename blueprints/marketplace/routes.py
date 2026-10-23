import math
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import Product, User, MarketPrice
from utils.decorators import roles_required
from utils.uploads import save_uploaded_image, delete_uploaded_image
from blueprints.profile.routes import SRI_LANKAN_DISTRICTS

marketplace_bp = Blueprint('marketplace', __name__, url_prefix='/marketplace')

CATEGORIES = ['Vegetables', 'Fruits', 'Grains & Rice', 'Spices', 'Pulses', 'Roots & Tubers', 'Other']

PRODUCT_IMAGES = {
    'Vegetables': '/static/images/categories/vegetables.svg',
    'Fruits': '/static/images/categories/fruits.svg',
    'Grains & Rice': '/static/images/categories/grains.svg',
    'Spices': '/static/images/categories/spices.svg',
    'Pulses': '/static/images/categories/pulses.svg',
    'Roots & Tubers': '/static/images/categories/roots.svg',
    'Other': '/static/images/categories/other.svg',
}


def annotate_product_deals(products):
    """Enrich products with live market benchmark comparisons and deal flags."""
    try:
        market_prices = MarketPrice.query.all()
        market_dict = {mp.crop_name.lower().strip(): mp for mp in market_prices}
    except Exception:
        market_dict = {}

    def get_market_price_for(product_name):
        if not product_name:
            return None
        pname = product_name.lower().strip()
        if pname in market_dict:
            return market_dict[pname]
        for cname, mp in market_dict.items():
            if cname in pname or pname in cname:
                return mp
        return None

    for p in products:
        mp = get_market_price_for(p.name)
        p.market_benchmark = mp
        p.below_market_pct = None
        p.is_deal = False
        p.is_low_stock = bool(p.quantity_kg is not None and p.quantity_kg <= 50)

        if mp and mp.selling_price and mp.selling_price > 0:
            if p.price_per_kg and p.price_per_kg < mp.selling_price:
                diff = mp.selling_price - p.price_per_kg
                pct = round((diff / mp.selling_price) * 100)
                if pct > 0:
                    p.below_market_pct = pct
                    p.is_deal = (pct >= 5 or p.price_per_kg < 100)
        elif p.price_per_kg and p.price_per_kg < 100:
            p.is_deal = True


@marketplace_bp.route('/')
def index():
    category = request.args.get('category', '').strip()
    search = request.args.get('search', '').strip()
    sort = request.args.get('sort', 'price_asc').strip()
    district = request.args.get('district', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()
    availability = request.args.get('availability', '').strip()

    # BUG-008: Hide deleted products from marketplace
    query = Product.query.filter_by(is_available=True, is_deleted=False)

    if category:
        query = query.filter_by(category=category)

    if search:
        query = query.filter(Product.name.ilike(f'%{search}%'))

    if district:
        query = query.join(User, Product.farmer_id == User.id).filter(
            db.or_(
                Product.location.ilike(f'%{district}%'),
                User.location.ilike(f'%{district}%')
            )
        )

    if min_price:
        try:
            min_val = float(min_price)
            query = query.filter(Product.price_per_kg >= min_val)
        except ValueError:
            pass

    if max_price:
        try:
            max_val = float(max_price)
            query = query.filter(Product.price_per_kg <= max_val)
        except ValueError:
            pass

    if availability == 'in_stock':
        query = query.filter(Product.quantity_kg > 0)

    # Sort options: price_asc (default, lowest first), price_desc (highest first), newest
    if sort in ('price_desc', 'price_high_low'):
        query = query.order_by(Product.price_per_kg.desc())
    elif sort == 'newest':
        query = query.order_by(Product.created_at.desc(), Product.id.desc())
    else:
        sort = 'price_asc'
        query = query.order_by(Product.price_per_kg.asc())

    products = query.all()
    annotate_product_deals(products)

    return render_template(
        'marketplace/index.html',
        products=products,
        categories=CATEGORIES,
        selected_category=category,
        search=search,
        sort=sort,
        district=district,
        districts=SRI_LANKAN_DISTRICTS,
        min_price=min_price,
        max_price=max_price,
        availability=availability
    )


@marketplace_bp.route('/product/<int:product_id>')
def product_detail(product_id):
    # BUG-008: Hide deleted products from product detail view
    product = Product.query.filter_by(id=product_id, is_deleted=False).first_or_404()
    related = Product.query.filter(
        Product.category == product.category,
        Product.id != product.id,
        Product.is_available == True,
        Product.is_deleted == False
    ).limit(4).all()
    annotate_product_deals([product] + related)
    return render_template('marketplace/product_detail.html', product=product, related=related)


def _render_product_form(product=None):
    try:
        market_prices = MarketPrice.query.all()
    except Exception:
        market_prices = []
    return render_template('marketplace/product_form.html',
                           categories=CATEGORIES,
                           product=product,
                           districts=SRI_LANKAN_DISTRICTS,
                           market_prices=market_prices)


@marketplace_bp.route('/list', methods=['GET', 'POST'])
@roles_required('farmer')
def list_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        try:
            quantity_kg = float(request.form.get('quantity_kg', 0))
            price_per_kg = float(request.form.get('price_per_kg', 0))
            if math.isnan(quantity_kg) or math.isinf(quantity_kg) or math.isnan(price_per_kg) or math.isinf(price_per_kg):
                raise ValueError("Non-finite quantity or price")
        except (ValueError, TypeError):
            flash('Invalid quantity or price.', 'error')
            return _render_product_form(product=None)

        if not name or not category or quantity_kg <= 0 or price_per_kg <= 0:
            flash('All required fields must be filled correctly. Quantity and price must be greater than zero.', 'error')
            return _render_product_form(product=None)

        # Handle product image upload with fallback to category stock image
        uploaded_file = request.files.get('image')
        image_url = None
        if uploaded_file and uploaded_file.filename:
            main_url, thumb_url, err = save_uploaded_image(uploaded_file, folder='products', max_width=1200, thumb_width=400)
            if err:
                flash(err, 'error')
                return _render_product_form(product=None)
            image_url = main_url
        else:
            image_url = PRODUCT_IMAGES.get(category, PRODUCT_IMAGES['Other'])

        product = Product(farmer_id=current_user.id, name=name, category=category,
                          description=description, quantity_kg=quantity_kg,
                          price_per_kg=price_per_kg, location=location, image_url=image_url,
                          is_available=True, is_deleted=False)
        db.session.add(product)
        db.session.commit()
        flash('Product listed successfully!', 'success')
        return redirect(url_for('marketplace.index'))
    return _render_product_form(product=None)


@marketplace_bp.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
@roles_required('farmer')
def edit_product(product_id):
    product = Product.query.filter_by(id=product_id, farmer_id=current_user.id, is_deleted=False).first_or_404()
    if request.method == 'POST':
        old_category = product.category
        new_category = request.form.get('category', product.category).strip()
        name = request.form.get('name', product.name).strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        is_available = request.form.get('is_available') == 'on'
        try:
            quantity_kg = float(request.form.get('quantity_kg', product.quantity_kg))
            price_per_kg = float(request.form.get('price_per_kg', product.price_per_kg))
            if math.isnan(quantity_kg) or math.isinf(quantity_kg) or math.isnan(price_per_kg) or math.isinf(price_per_kg):
                raise ValueError("Non-finite quantity or price")
        except (ValueError, TypeError):
            flash('Invalid quantity or price.', 'error')
            return _render_product_form(product=product)

        if not name or not new_category or quantity_kg < 0 or price_per_kg <= 0:
            flash('Invalid input. Quantity cannot be negative and price must be greater than zero.', 'error')
            return _render_product_form(product=product)

        # Handle image replacement
        uploaded_file = request.files.get('image')
        if uploaded_file and uploaded_file.filename:
            main_url, thumb_url, err = save_uploaded_image(uploaded_file, folder='products', max_width=1200, thumb_width=400)
            if err:
                flash(err, 'error')
                return _render_product_form(product=product)
            # Delete old image from disk if it was a custom upload
            delete_uploaded_image(product.image_url)
            product.image_url = main_url
        else:
            # BUG-010: Do not overwrite product.image_url on edit unless it is empty or the category changed
            # (and only update stock image if it wasn't a custom upload).
            is_custom_upload = product.image_url and product.image_url.startswith('/static/uploads/')
            if not product.image_url or (old_category != new_category and not is_custom_upload):
                product.image_url = PRODUCT_IMAGES.get(new_category, PRODUCT_IMAGES.get('Other'))

        product.name = name
        product.description = description
        product.location = location
        product.quantity_kg = quantity_kg
        product.price_per_kg = price_per_kg

        # Separate out-of-stock from deleted/disabled: quantity 0 cannot be active
        if quantity_kg == 0:
            product.is_available = False
        else:
            product.is_available = is_available

        product.category = new_category

        db.session.commit()
        flash('Product updated!', 'success')
        return redirect(url_for('dashboard.index'))
    return _render_product_form(product=product)



@marketplace_bp.route('/product/<int:product_id>/delete', methods=['POST'])
@roles_required('farmer')
def delete_product(product_id):
    # BUG-008: Farmer "delete" sets is_deleted = True and is_available = False
    product = Product.query.filter_by(id=product_id, farmer_id=current_user.id, is_deleted=False).first_or_404()
    product.is_deleted = True
    product.is_available = False
    db.session.commit()
    flash('Product removed from listing.', 'info')
    return redirect(url_for('dashboard.index'))