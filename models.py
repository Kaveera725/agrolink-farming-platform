from extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user and not getattr(user, 'is_active', True):
        return None
    return user


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.Enum('farmer', 'buyer', 'admin', name='user_role'), nullable=False)
    phone = db.Column(db.String(20))
    whatsapp_number = db.Column(db.String(20), nullable=True)
    location = db.Column(db.String(120))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    crops = db.relationship('Crop', backref='farmer', lazy=True)
    products = db.relationship('Product', backref='farmer', lazy=True, foreign_keys='Product.farmer_id')
    orders_placed = db.relationship('Order', backref='buyer', lazy=True, foreign_keys='Order.buyer_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class Crop(db.Model):
    __tablename__ = 'crops'
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    crop_name = db.Column(db.String(100), nullable=False)
    crop_type = db.Column(db.String(50), nullable=False)
    quantity_kg = db.Column(db.Float, nullable=False)
    expected_harvest_date = db.Column(db.Date, nullable=False)
    field_location = db.Column(db.String(120))
    notes = db.Column(db.Text)
    status = db.Column(db.Enum('growing', 'ready', 'harvested', name='crop_status'), default='growing')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Crop {self.crop_name}>'


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    quantity_kg = db.Column(db.Float, nullable=False)
    price_per_kg = db.Column(db.Float, nullable=False)
    location = db.Column(db.String(120))
    image_url = db.Column(db.String(255))
    is_available = db.Column(db.Boolean, default=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='product', lazy=True)

    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_kg = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    status = db.Column(db.Enum('pending', 'confirmed', 'delivered', 'cancelled', name='order_status'), default='pending')
    delivery_address = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Order {self.id}>'


class MarketPrice(db.Model):
    __tablename__ = 'market_prices'
    id = db.Column(db.Integer, primary_key=True)
    crop_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    buying_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), default='per kg')
    market_location = db.Column(db.String(100), default='Colombo')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<MarketPrice {self.crop_name}>'