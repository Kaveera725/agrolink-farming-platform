from flask import Blueprint, render_template
from models import Product, MarketPrice, User, Order

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    featured_products = Product.query.filter_by(is_available=True, is_deleted=False).order_by(Product.created_at.desc()).limit(8).all()
    sample_prices = MarketPrice.query.limit(5).all()

    # Live trust metrics for landing page strip
    counts = {
        'farmers': User.query.filter_by(role='farmer', is_active=True).count(),
        'listings': Product.query.filter_by(is_available=True, is_deleted=False).count(),
        'orders': Order.query.filter(Order.status.in_(['delivered', 'confirmed'])).count(),
    }

    return render_template(
        'main/index.html',
        featured_products=featured_products,
        sample_prices=sample_prices,
        counts=counts
    )


@main_bp.route('/privacy')
def privacy():
    """Sri Lanka PDPA 2022 and GDPR Privacy Notice."""
    return render_template('main/privacy.html')
