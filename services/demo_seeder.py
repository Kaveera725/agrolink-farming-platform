"""Demo data seeder for AgroLink Admin Testing and Demonstration.

CLI Command:
    flask seed-admin-demo [--clear]

Generates ~300 users, ~200 products, and ~800 orders across the last 6 months.
All demo data is isolated and tagged with '@demo.agrolink.lk' emails so it can
be cleanly purged at any time.
"""
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from extensions import db
from models import User, Product, Order, MarketPrice, MarketPriceHistory

SRI_LANKA_LOCATIONS = [
    {"district": "Colombo", "lat": 6.9271, "lng": 79.8612},
    {"district": "Gampaha", "lat": 7.0840, "lng": 79.9939},
    {"district": "Kalutara", "lat": 6.5854, "lng": 79.9607},
    {"district": "Kandy", "lat": 7.2906, "lng": 80.6337},
    {"district": "Matale", "lat": 7.4675, "lng": 80.6234},
    {"district": "Nuwara Eliya", "lat": 6.9497, "lng": 80.7891},
    {"district": "Galle", "lat": 6.0535, "lng": 80.2210},
    {"district": "Matara", "lat": 5.9549, "lng": 80.5550},
    {"district": "Hambantota", "lat": 6.1429, "lng": 81.1212},
    {"district": "Jaffna", "lat": 9.6615, "lng": 80.0255},
    {"district": "Kilinochchi", "lat": 9.3803, "lng": 80.3770},
    {"district": "Kurunegala", "lat": 7.4818, "lng": 80.3609},
    {"district": "Puttalam", "lat": 8.0408, "lng": 79.8394},
    {"district": "Anuradhapura", "lat": 8.3114, "lng": 80.4037},
    {"district": "Polonnaruwa", "lat": 7.9403, "lng": 81.0188},
    {"district": "Badulla", "lat": 6.9934, "lng": 81.0550},
    {"district": "Monaragala", "lat": 6.8728, "lng": 81.3507},
    {"district": "Ratnapura", "lat": 6.7056, "lng": 80.3847},
    {"district": "Kegalle", "lat": 7.2513, "lng": 80.3464},
]

FIRST_NAMES = [
    "Sunil", "Nimal", "Kamal", "Priyantha", "Anura", "Bandara", "Sarath", "Mahinda",
    "Chaminda", "Dinesh", "Kasun", "Saman", "Pradeep", "Nuwan", "Rohan", "Lalith",
    "Dilshan", "Chathura", "Kavinda", "Thilina", "Mahesh", "Roshan", "Upul", "Jayantha",
    "Kumara", "Sanjeewa", "Ranjith", "Indika", "Ruwan", "Ashan", "Niroshan", "Suresh"
]

LAST_NAMES = [
    "Perera", "Fernando", "Silva", "Jayasinghe", "Dissanayake", "Wickramasinghe",
    "Senanayake", "Gunasekara", "Rajapaksha", "Bandara", "Herath", "Karunaratne",
    "Ranasinghe", "Alwis", "Weerasinghe", "Mendis", "Fonseka", "Abeysekara",
    "Ratnayake", "Wijesinghe", "Liyanage", "Samaraweera", "Amarasinghe", "Nanayakkara"
]

CROPS = [
    ("Red Onion", "Vegetables", 220.0, 320.0),
    ("Big Onion", "Vegetables", 140.0, 200.0),
    ("Tomato", "Vegetables", 90.0, 160.0),
    ("Carrot", "Vegetables", 120.0, 210.0),
    ("Green Chilli", "Vegetables", 300.0, 480.0),
    ("Leeks", "Vegetables", 110.0, 180.0),
    ("Cabbage", "Vegetables", 80.0, 140.0),
    ("Pumpkin", "Vegetables", 70.0, 120.0),
    ("Beans", "Vegetables", 160.0, 260.0),
    ("Brinjal", "Vegetables", 100.0, 170.0),
    ("Potato", "Vegetables", 150.0, 230.0),
    ("Banana (Cavendish)", "Fruits", 130.0, 200.0),
    ("Papaya", "Fruits", 80.0, 150.0),
    ("Pineapple", "Fruits", 140.0, 240.0),
    ("Mango (Karthakolomban)", "Fruits", 250.0, 420.0),
    ("Watermelon", "Fruits", 60.0, 110.0),
    ("Avocado", "Fruits", 180.0, 310.0),
    ("Samba Rice", "Grains", 190.0, 240.0),
    ("Nadu Rice", "Grains", 175.0, 220.0),
    ("Keeri Samba Rice", "Grains", 240.0, 310.0),
    ("Maize", "Grains", 110.0, 170.0),
    ("Kurakkan", "Grains", 210.0, 320.0),
    ("Black Pepper", "Spices", 1200.0, 1750.0),
    ("Ceylon Cinnamon", "Spices", 2500.0, 3800.0),
    ("Cloves", "Spices", 1800.0, 2600.0),
    ("Cardamom", "Spices", 4500.0, 6800.0),
    ("Ginger", "Spices", 650.0, 950.0),
    ("Turmeric", "Spices", 750.0, 1100.0),
]


def clear_demo_data():
    """Purge all generated demo records cleanly."""
    demo_users = User.query.filter(User.email.like('%@demo.agrolink.lk')).all()
    if not demo_users:
        return 0, 0, 0

    user_ids = [u.id for u in demo_users]

    # Delete related orders
    orders_deleted = Order.query.filter(
        (Order.buyer_id.in_(user_ids)) | (Order.notes.like('%[DEMO_SEED]%'))
    ).delete(synchronize_session=False)

    # Delete related products
    products_deleted = Product.query.filter(
        Product.farmer_id.in_(user_ids)
    ).delete(synchronize_session=False)

    # Delete users
    users_deleted = User.query.filter(
        User.id.in_(user_ids)
    ).delete(synchronize_session=False)

    db.session.commit()
    return users_deleted, products_deleted, orders_deleted


def seed_demo_data(total_users=300, total_products=200, total_orders=800):
    """Seed realistic marketplace demo records spread across the last 6 months."""
    now = datetime.utcnow()
    hashed_pass = generate_password_hash("DemoSecret2026!")

    # 1. Create Users (~120 farmers, ~175 buyers, ~5 admins)
    num_farmers = int(total_users * 0.40)
    num_buyers = total_users - num_farmers - 5
    num_admins = 5

    created_farmers = []
    created_buyers = []

    for i in range(num_farmers):
        loc = random.choice(SRI_LANKA_LOCATIONS)
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        # Random location offset for realistic map clustering
        lat_offset = random.uniform(-0.06, 0.06)
        lng_offset = random.uniform(-0.06, 0.06)
        has_pin = random.random() > 0.08  # ~8% without pin to test alert panel
        reg_days_ago = random.randint(1, 180)
        reg_date = now - timedelta(days=reg_days_ago, hours=random.randint(0, 23))
        is_verified = random.random() > 0.45

        farmer = User(
            name=f"{fname} {lname}",
            email=f"farmer_{i+1:03d}_{reg_days_ago}@demo.agrolink.lk",
            password_hash=hashed_pass,
            role='farmer',
            phone=f"077{random.randint(1000000, 9999999)}",
            whatsapp_number=f"+9477{random.randint(1000000, 9999999)}",
            location=loc["district"],
            farm_name=f"{lname} Organic Farm",
            bio=f"Fresh agricultural harvests from {loc['district']}.",
            latitude=round(loc["lat"] + lat_offset, 6) if has_pin else None,
            longitude=round(loc["lng"] + lng_offset, 6) if has_pin else None,
            address_text=f"No. {random.randint(10, 250)}, Farm Road, {loc['district']}",
            is_active=True,
            is_verified=is_verified,
            verified_at=reg_date + timedelta(days=2) if is_verified else None,
            created_at=reg_date
        )
        db.session.add(farmer)
        created_farmers.append(farmer)

    for i in range(num_buyers):
        loc = random.choice(SRI_LANKA_LOCATIONS)
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        reg_days_ago = random.randint(1, 180)
        reg_date = now - timedelta(days=reg_days_ago, hours=random.randint(0, 23))

        buyer = User(
            name=f"{fname} {lname}",
            email=f"buyer_{i+1:03d}_{reg_days_ago}@demo.agrolink.lk",
            password_hash=hashed_pass,
            role='buyer',
            phone=f"071{random.randint(1000000, 9999999)}",
            location=loc["district"],
            latitude=round(loc["lat"], 6),
            longitude=round(loc["lng"], 6),
            address_text=f"{loc['district']} Wholesale Market",
            is_active=True,
            created_at=reg_date
        )
        db.session.add(buyer)
        created_buyers.append(buyer)

    for i in range(num_admins):
        admin = User(
            name=f"Demo Admin {i+1}",
            email=f"admin_{i+1}@demo.agrolink.lk",
            password_hash=hashed_pass,
            role='admin',
            location="Colombo",
            is_active=True,
            created_at=now - timedelta(days=180)
        )
        db.session.add(admin)

    db.session.commit()

    # 2. Create Products (~200)
    created_products = []
    for i in range(total_products):
        farmer = random.choice(created_farmers)
        crop_name, cat, min_p, max_p = random.choice(CROPS)
        qty = round(random.uniform(20.0, 600.0), 1)
        price = round(random.uniform(min_p, max_p), 2)
        prod_date = max(farmer.created_at, now - timedelta(days=random.randint(1, 150)))

        prod = Product(
            farmer_id=farmer.id,
            name=crop_name,
            category=cat,
            description=f"Freshly harvested {crop_name} direct from {farmer.location}.",
            quantity_kg=qty,
            price_per_kg=price,
            location=farmer.location,
            is_available=True,
            is_deleted=False,
            offers_delivery=(random.random() > 0.3),
            created_at=prod_date
        )
        db.session.add(prod)
        created_products.append(prod)

    db.session.commit()

    # 3. Create Orders (~800)
    STATUS_WEIGHTS = [
        ('delivered', 0.60),
        ('confirmed', 0.15),
        ('pending', 0.10),
        ('cancelled', 0.10),
        ('rejected', 0.05),
    ]
    statuses = [s for s, w in STATUS_WEIGHTS]
    weights = [w for s, w in STATUS_WEIGHTS]

    for i in range(total_orders):
        buyer = random.choice(created_buyers)
        prod = random.choice(created_products)
        order_days_ago = random.randint(0, 160)
        order_date = now - timedelta(days=order_days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
        if order_date < prod.created_at:
            order_date = prod.created_at + timedelta(hours=random.randint(1, 48))

        st = random.choices(statuses, weights=weights)[0]
        qty = round(random.uniform(5.0, 80.0), 1)
        items_total = round(qty * prod.price_per_kg, 2)
        fulfillment = 'delivery' if random.random() > 0.4 else 'pickup'
        delivery_fee = round(random.uniform(400.0, 1800.0), 2) if fulfillment == 'delivery' else 0.0
        total_price = items_total + delivery_fee

        order = Order(
            buyer_id=buyer.id,
            product_id=prod.id,
            quantity_kg=qty,
            items_total=items_total,
            delivery_fee=delivery_fee,
            total_price=total_price,
            status=st,
            fulfillment_type=fulfillment,
            delivery_address=f"Delivery to {buyer.location}" if fulfillment == 'delivery' else None,
            notes="[DEMO_SEED] Generated for admin dashboard demo testing",
            created_at=order_date,
            updated_at=order_date + timedelta(hours=random.randint(2, 24))
        )
        db.session.add(order)

    db.session.commit()
    return len(created_farmers) + len(created_buyers) + num_admins, len(created_products), total_orders

