from flask import Flask, render_template
from dotenv import load_dotenv
import os
import secrets
import warnings
import click

from extensions import db, login_manager, csrf, limiter, migrate

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
    limiter.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    # Error handlers
    @app.errorhandler(400)
    def bad_request_error(e):
        return render_template('errors/400.html', error_description=getattr(e, 'description', None)), 400

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def ratelimit_error(e):
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # Import Blueprints
    from blueprints.auth.routes import auth_bp
    from blueprints.dashboard.routes import dashboard_bp
    from blueprints.marketplace.routes import marketplace_bp
    from blueprints.orders.routes import orders_bp
    from blueprints.prices.routes import prices_bp
    from blueprints.main.routes import main_bp
    from blueprints.profile.routes import profile_bp

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(prices_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(profile_bp)

    # CLI Commands
    @app.cli.command('seed-prices')
    def seed_prices_command():
        """Seed market price reference records into the database."""
        from models import MarketPrice
        from blueprints.prices.routes import seed_market_prices
        before_count = MarketPrice.query.count()
        seed_market_prices()
        after_count = MarketPrice.query.count()
        if after_count > before_count:
            click.echo(f"Successfully seeded {after_count - before_count} market prices.")
        else:
            click.echo("Market prices already seeded.")

    @app.cli.command('create-admin')
    def create_admin_command():
        """Create an administrator user interactively."""
        from models import User
        from email_validator import validate_email, EmailNotValidError
        from utils.phone import normalize_phone_number

        email = click.prompt("Admin Email", type=str).strip().lower()
        try:
            valid_info = validate_email(email, check_deliverability=False)
            email = valid_info.normalized
        except EmailNotValidError:
            click.echo("Error: Invalid email format.", err=True)
            return

        existing = User.query.filter_by(email=email).first()
        if existing:
            click.echo(f"Error: User with email '{email}' already exists.", err=True)
            return

        name = click.prompt("Admin Name", default="Administrator", type=str).strip()
        phone_input = click.prompt("WhatsApp / Phone (e.g. 0771234567, optional)", default="", type=str).strip()
        whatsapp = None
        if phone_input:
            whatsapp = normalize_phone_number(phone_input) or phone_input

        password = click.prompt("Password (min 8 chars)", hide_input=True, confirmation_prompt=True)
        if len(password) < 8:
            click.echo("Error: Password must be at least 8 characters long.", err=True)
            return

        admin = User(
            name=name,
            email=email,
            role='admin',
            phone=phone_input or None,
            whatsapp_number=whatsapp,
            is_active=True
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin user '{email}' created successfully.")

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)