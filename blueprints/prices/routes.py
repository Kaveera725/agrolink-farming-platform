from flask import Blueprint, render_template
from extensions import db
from models import MarketPrice, Product

prices_bp = Blueprint('prices', __name__, url_prefix='/')


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
    products = Product.query.filter_by(is_available=True).all()

    # Group market prices
    categories = sorted(set(p.category for p in prices))
    grouped = {cat: [p for p in prices if p.category == cat] for cat in categories}

    # Market lookup
    market_dict = {p.crop_name.lower(): p for p in prices}

    # 🔥 SELLER MAP (group products by category, sorted cheapest first)
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
                diff = round(market_price - p.price_per_kg, 2)
            else:
                market_price = None
                diff = None

            seller_map[cat].append({
                "product": p,
                "market_price": market_price,
                "diff": diff
            })

    best_deals = []
    seen_products = set()

    # Build best deals (cheapest seller vs market)
    for product in products:
        market = find_market_price(product.name, market_dict)

        if market and product.price_per_kg < market.selling_price:
            if product.id not in seen_products:
                seen_products.add(product.id)
                best_deals.append({
                    "product_name": product.name,
                    "category": product.category,
                    "seller": product.farmer.name,
                    "price": product.price_per_kg,
                    "market_price": market.selling_price,
                    "saving": round(market.selling_price - product.price_per_kg, 2),
                    "product_id": product.id
                })

    best_deals.sort(key=lambda x: x['saving'], reverse=True)

    return render_template(
        'prices/index.html',
        grouped=grouped,
        categories=categories,
        seller_map=seller_map,
        best_deals=best_deals
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
    products = Product.query.filter_by(is_available=True)\
        .order_by(Product.category, Product.price_per_kg.asc())\
        .all()

    # Fetch all market prices and build a lookup dict
    market_prices = MarketPrice.query.all()
    market_dict = {mp.crop_name.lower(): mp for mp in market_prices}

    grouped = {}
    for p in products:
        cat = p.category
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(p)

    cheapest_map = {}
    for cat, items in grouped.items():
        cheapest_map[cat] = items[0] if items else None

    return render_template(
        "prices/bids.html",
        grouped=grouped,
        cheapest_map=cheapest_map,
        market_dict=market_dict   # pass market prices
    )