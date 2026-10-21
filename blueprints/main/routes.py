from flask import Blueprint, render_template
from models import Product, MarketPrice

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def home():
    featured_products = Product.query.filter_by(is_available=True, is_deleted=False).order_by(Product.created_at.desc()).limit(8).all()
    sample_prices = MarketPrice.query.limit(6).all()
    return render_template('main/index.html', featured_products=featured_products, sample_prices=sample_prices)