from flask import Flask
from dotenv import load_dotenv
import os
import secrets
import warnings

from extensions import db, login_manager, csrf

load_dotenv()

def create_app():
    app = Flask(__name__)

    env = os.getenv('FLASK_ENV', os.getenv('ENV', 'development')).lower()
    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        if env == 'production':
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable is required in production mode."
            )
        secret_key = secrets.token_hex(32)
        warnings.warn(
            "Insecure configuration: SECRET_KEY is not set. Generated a temporary random key for development.",
            UserWarning,
            stacklevel=2
        )

    app.config['SECRET_KEY'] = secret_key
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URL',
        'postgresql://agrolink_db_user:agrolink_db_user_password@localhost:5432/agrolink_db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # Import Blueprints
    from blueprints.auth.routes import auth_bp
    from blueprints.dashboard.routes import dashboard_bp
    from blueprints.marketplace.routes import marketplace_bp
    from blueprints.orders.routes import orders_bp
    from blueprints.prices.routes import prices_bp
    from blueprints.main.routes import main_bp

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(prices_bp)
    app.register_blueprint(main_bp)

    # Create DB & Seed
    with app.app_context():
        db.create_all()

        from blueprints.prices.routes import seed_market_prices
        seed_market_prices()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)