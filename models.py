from extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.dialects import postgresql


@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user and not getattr(user, 'is_active', True):
        return None
    from flask import session
    session_v = session.get('session_version')
    if user and session_v is not None and session_v != getattr(user, 'session_version', 1):
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
    farm_name = db.Column(db.String(120), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    profile_image_url = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Numeric(9, 6), nullable=True)
    longitude = db.Column(db.Numeric(9, 6), nullable=True)
    address_text = db.Column(db.String(255), nullable=True)
    location_updated_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    session_version = db.Column(db.Integer, default=1, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    crops = db.relationship('Crop', backref='farmer', lazy=True)
    products = db.relationship('Product', backref='farmer', lazy=True, foreign_keys='Product.farmer_id')
    orders_placed = db.relationship('Order', backref='buyer', lazy=True, foreign_keys='Order.buyer_id')
    verification_requests = db.relationship('VerificationRequest', backref='farmer', lazy=True, foreign_keys='VerificationRequest.farmer_id', cascade='all, delete-orphan')
    listing_reports = db.relationship('ListingReport', backref='reporter', lazy=True, foreign_keys='ListingReport.reporter_id', cascade='all, delete-orphan')
    verified_by_user = db.relationship('User', foreign_keys=[verified_by], remote_side=[id], lazy=True)

    @property
    def active_products_count(self):
        return Product.query.filter_by(farmer_id=self.id, is_available=True, is_deleted=False).count()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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
    hidden_reason = db.Column(db.String(30), nullable=True)
    hidden_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    offers_delivery = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='product', lazy=True)
    reports = db.relationship('ListingReport', backref='product', lazy=True, foreign_keys='ListingReport.product_id', cascade='all, delete-orphan')
    hidden_by_user = db.relationship('User', foreign_keys=[hidden_by], lazy=True)

    @property
    def display_image_url(self):
        if self.image_url:
            return self.image_url
        from blueprints.marketplace.routes import PRODUCT_IMAGES
        return PRODUCT_IMAGES.get(self.category, PRODUCT_IMAGES.get('Other'))

    @property
    def thumbnail_url(self):
        if self.image_url:
            if '/static/uploads/' in self.image_url:
                import os
                base, ext = os.path.splitext(self.image_url)
                return f"{base}_thumb{ext}"
            return self.image_url
        from blueprints.marketplace.routes import PRODUCT_IMAGES
        return PRODUCT_IMAGES.get(self.category, PRODUCT_IMAGES.get('Other'))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<Product {self.name}>'


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_kg = db.Column(db.Float, nullable=False)
    total_price = db.Column(db.Numeric(12, 2), nullable=False)
    status = db.Column(db.Enum('pending', 'confirmed', 'delivered', 'cancelled', 'rejected', name='order_status'), default='pending')
    fulfillment_type = db.Column(db.Enum('pickup', 'delivery', name='fulfillment_type'), default='pickup', nullable=False)
    delivery_lat = db.Column(db.Numeric(9, 6), nullable=True)
    delivery_lng = db.Column(db.Numeric(9, 6), nullable=True)
    distance_km = db.Column(db.Numeric(8, 2), nullable=True)
    distance_source = db.Column(db.Enum('google', 'estimated', name='distance_source'), nullable=True)
    items_total = db.Column(db.Numeric(12, 2), nullable=True)
    delivery_fee = db.Column(db.Numeric(12, 2), default=0, nullable=False)
    rejection_reason = db.Column(db.String(255), nullable=True)
    delivery_address = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, **kwargs):
        if 'fulfillment_type' not in kwargs and kwargs.get('delivery_address'):
            kwargs['fulfillment_type'] = 'delivery'
        super().__init__(**kwargs)

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __repr__(self):
        return f'<MarketPrice {self.crop_name}>'


class AdminAuditLog(db.Model):
    __tablename__ = 'admin_audit_log'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(40), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    before_data = db.Column(db.JSON().with_variant(postgresql.JSONB, 'postgresql'), nullable=True)
    after_data = db.Column(db.JSON().with_variant(postgresql.JSONB, 'postgresql'), nullable=True)
    result = db.Column(db.String(20), default='success', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    admin = db.relationship('User', foreign_keys=[admin_id], backref=db.backref('admin_actions', lazy=True))


class AdminNote(db.Model):
    __tablename__ = 'admin_notes'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    admin = db.relationship('User', foreign_keys=[admin_id], backref=db.backref('notes_written', lazy=True))
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('admin_notes', lazy=True, order_by='AdminNote.created_at.desc()'))
    order = db.relationship('Order', foreign_keys=[order_id], backref=db.backref('admin_notes', lazy=True, order_by='AdminNote.created_at.desc()'))

    def __repr__(self):
        return f'<AdminNote {self.id} for User {self.user_id} Order {self.order_id}>'


class VerificationRequest(db.Model):
    __tablename__ = 'verification_requests'
    id = db.Column(db.Integer, primary_key=True)
    farmer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, approved, rejected
    farmer_note = db.Column(db.Text, nullable=True)
    admin_note = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_at = db.Column(db.DateTime, nullable=True)
    decided_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    decided_by_user = db.relationship('User', foreign_keys=[decided_by], lazy=True)

    def __repr__(self):
        return f'<VerificationRequest {self.id} farmer={self.farmer_id} status={self.status}>'


class ListingReport(db.Model):
    __tablename__ = 'listing_reports'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    reason = db.Column(db.String(50), nullable=False)  # misleading_price, wrong_or_fake_photo, prohibited_item, spam, other
    details = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='open', nullable=False)  # open, reviewing, resolved, dismissed
    resolution_note = db.Column(db.Text, nullable=True)
    handled_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    handled_at = db.Column(db.DateTime, nullable=True)

    handled_by_user = db.relationship('User', foreign_keys=[handled_by], lazy=True)

    def __repr__(self):
        return f'<ListingReport {self.id} product={self.product_id} reporter={self.reporter_id} status={self.status}>'

