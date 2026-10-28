from flask import Blueprint, render_template, request
from datetime import datetime
from extensions import db
from models import MarketPrice, Product

prices_bp = Blueprint('prices', __name__, url_prefix='/prices')


def seed_market_prices():
    if MarketPrice.query.count() > 0:
        return
    seed_data = [
        ('Tomato', 'Vegetables', 85, 120),
        ('Carrot', 'Vegetables', 60, 95),
        ('Cabbage', 'Vegetables', 45, 75),
        ('Beans', 'Vegetables', 110, 160),
        ('Brinjal', 'Vegetables', 70, 105),
        ('Leeks', 'Vegetables', 130, 180),
        ('Pumpkin', 'Vegetables', 40, 65),
        ('Cucumber', 'Vegetables', 55, 85),
        ('Banana', 'Fruits', 65, 100),
        ('Mango', 'Fruits', 120, 180),
        ('Pineapple', 'Fruits', 80, 130),
        ('Papaya', 'Fruits', 55, 90),
        ('Avocado', 'Fruits', 150, 220),
        ('Rice (Samba)', 'Grains & Rice', 95, 135),
        ('Rice (Nadu)', 'Grains & Rice', 85, 120),
        ('Maize', 'Grains & Rice', 55, 80),
        ('Red Chilli', 'Spices', 700, 950),
        ('Turmeric', 'Spices', 450, 650),
        ('Ginger', 'Spices', 300, 480),
        ('Garlic', 'Spices', 350, 520),
        ('Lentils', 'Pulses', 170, 240),
        ('Chickpeas', 'Pulses', 190, 270),
        ('Sweet Potato', 'Roots & Tubers', 70, 110),
        ('Cassava', 'Roots & Tubers', 40, 65),
        ('Potato', 'Roots & Tubers', 80, 120),
    ]
    for name, category, buy, sell in seed_data:
        mp = MarketPrice(crop_name=name, category=category,
                         buying_price=buy, selling_price=sell)
        db.session.add(mp)
    db.session.commit()


def find_market_price(product_name, market_dict):
    if not product_name:
        return None
    name = product_name.lower().strip()
    if name in market_dict:
        return market_dict[name]
    for crop_name, mp in market_dict.items():
        if crop_name in name or name in crop_name:
            return mp
    return None


@prices_bp.route('/')
def index():
    prices = MarketPrice.query.all()
    products = Product.query.filter_by(is_available=True, is_deleted=False).all()

    # Get last updated timestamp
    last_price = MarketPrice.query.order_by(MarketPrice.updated_at.desc()).first()
    last_updated = last_price.updated_at if (last_price and last_price.updated_at) else datetime.utcnow()

    # Group market prices
    categories = sorted(set(p.category for p in prices))
    grouped = {cat: [p for p in prices if p.category == cat] for cat in categories}

    # Market lookup
    market_dict = {p.crop_name.lower().strip(): p for p in prices}

    # SELLER MAP (group products by category, sorted cheapest first)
    raw_seller_map = {}
    for product in products:
        cat = product.category
        if cat not in raw_seller_map:
            raw_seller_map[cat] = []
        raw_seller_map[cat].append(product)

    seller_map = {}
    for cat in sorted(raw_seller_map.keys()):
        raw_seller_map[cat].sort(key=lambda x: x.price_per_kg)
        seller_map[cat] = []
        for p in raw_seller_map[cat]:
            market = find_market_price(p.name, market_dict)
            if market:
                market_price = market.selling_price
                buying_price = market.buying_price
                diff = round(market_price - p.price_per_kg, 2)
                saving_pct = round((diff / market_price) * 100) if diff > 0 else 0
            else:
                market_price = None
                buying_price = None
                diff = None
                saving_pct = None

            seller_map[cat].append({
                "product": p,
                "market_price": market_price,
                "buying_price": buying_price,
                "diff": diff,
                "saving_pct": saving_pct
            })

    best_deals = []
    seen_products = set()

    # Build best deals (farmer listing priced lower than retail market selling price)
    for product in products:
        market = find_market_price(product.name, market_dict)

        if market and product.price_per_kg < market.selling_price:
            if product.id not in seen_products:
                seen_products.add(product.id)
                diff = round(market.selling_price - product.price_per_kg, 2)
                saving_pct = round((diff / market.selling_price) * 100)
                best_deals.append({
                    "product": product,
                    "product_name": product.name,
                    "category": product.category,
                    "seller": product.farmer.name if product.farmer else "Verified Farmer",
                    "seller_location": product.location or (product.farmer.location if product.farmer else "") or "Sri Lanka",
                    "price": product.price_per_kg,
                    "market_price": market.selling_price,
                    "buying_price": market.buying_price,
                    "saving": diff,
                    "saving_pct": saving_pct,
                    "product_id": product.id,
                    "thumbnail_url": product.thumbnail_url or product.display_image_url,
                    "quantity_kg": product.quantity_kg
                })

    best_deals.sort(key=lambda x: x['saving'], reverse=True)

    return render_template(
        'prices/index.html',
        grouped=grouped,
        categories=categories,
        seller_map=seller_map,
        best_deals=best_deals,
        last_updated=last_updated,
        prices=prices
    )


def get_price_suggestion(product_name):
    market = MarketPrice.query.filter_by(crop_name=product_name).first()

    if not market:
        return None

    suggested = round((market.buying_price + market.selling_price) / 2, 2)

    return {
        "min_price": market.buying_price,
        "max_price": market.selling_price,
        "suggested_price": suggested
    }


@prices_bp.route('/bids')
def bids():
    sort = request.args.get('sort', 'price_asc').strip().lower()
    selected_category = request.args.get('category', 'all').strip()
    search = request.args.get('q', '').strip()

    products_query = Product.query.filter_by(is_available=True, is_deleted=False)
    if selected_category and selected_category != 'all':
        products_query = products_query.filter(Product.category == selected_category)
    if search:
        products_query = products_query.filter(
            Product.name.ilike(f'%{search}%') | Product.category.ilike(f'%{search}%')
        )

    products = products_query.all()

    # Fetch all market prices and build lookup dict
    market_prices = MarketPrice.query.all()
    market_dict = {mp.crop_name.lower().strip(): mp for mp in market_prices}
    categories = sorted(set(mp.category for mp in market_prices))

    # Enrich products with market data
    for p in products:
        m = find_market_price(p.name, market_dict)
        p.market_benchmark = m
        p.market_price = m.selling_price if m else None
        p.buying_price = m.buying_price if m else None
        if p.market_price:
            p.diff = round(p.market_price - p.price_per_kg, 2)
            p.saving_pct = round((p.diff / p.market_price) * 100) if p.diff > 0 else 0
        else:
            p.diff = None
            p.saving_pct = 0

    # Sort products
    if sort == 'highest_savings':
        products.sort(key=lambda p: (p.diff is None, -(p.diff or 0), p.price_per_kg))
    elif sort == 'price_desc':
        products.sort(key=lambda p: -p.price_per_kg)
    elif sort == 'name_asc':
        products.sort(key=lambda p: p.name.lower())
    else:  # price_asc (default)
        products.sort(key=lambda p: p.price_per_kg)

    # Group by category
    grouped = {}
    for p in products:
        cat = p.category
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(p)

    cheapest_map = {}
    for cat, items in grouped.items():
        cheapest_map[cat] = min(items, key=lambda x: x.price_per_kg) if items else None

    return render_template(
        "prices/bids.html",
        products=products,
        grouped=grouped,
        cheapest_map=cheapest_map,
        market_dict=market_dict,
        categories=categories,
        selected_category=selected_category,
        search=search,
        selected_sort=sort,
        total_listings=len(products)
    )