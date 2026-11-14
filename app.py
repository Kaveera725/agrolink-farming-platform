from flask import Flask, render_template, request, redirect, url_for, flash
from pathlib import Path
from dotenv import load_dotenv
import os
import secrets
import warnings
import click

from extensions import db, login_manager, csrf, limiter, migrate
from config import Config

# Explicitly load .env from project root with override=False
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)


def create_app(debug=None):
    # Ensure fresh environment variables are loaded at app creation time
    load_dotenv(dotenv_path=env_path, override=False)

    app = Flask(__name__)
    if debug is not None:
        app.debug = debug
    else:
        app.debug = os.getenv('FLASK_DEBUG', '1' if os.getenv('FLASK_ENV') == 'development' else '0') in ('1', 'true', 'True')

    env = os.getenv('FLASK_ENV', os.getenv('ENV', 'development')).lower()
    if env == 'production':
        app.config.from_object('config.ProductionConfig')
    elif env == 'testing':
        app.config.from_object('config.TestingConfig')
    else:
        app.config.from_object('config.DevelopmentConfig')

    # Read values at app creation time
    Config.init_app(app)

    secret_key = app.config.get('SECRET_KEY')
    if not secret_key:
        if env == 'production':
            raise RuntimeError(
                "CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY environment variable is required in production mode."
            )
        secret_key = secrets.token_hex(32)
        app.config['SECRET_KEY'] = secret_key
        warnings.warn(
            "Insecure configuration: SECRET_KEY is not set. Generated a temporary random key for development.",
            UserWarning,
            stacklevel=2
        )

    # Register geo filters and template helpers
    from utils.geo import time_ago
    app.jinja_env.filters['time_ago'] = time_ago

    from services.settings import get_setting, get_active_announcement

    # Expose safe Google Maps credentials, platform settings and announcement banner
    @app.context_processor
    def inject_maps_config():
        browser_key = app.config.get('GOOGLE_MAPS_BROWSER_KEY', '').strip()
        map_id = app.config.get('GOOGLE_MAPS_MAP_ID', '').strip()
        maps_enabled = bool(browser_key and map_id)
        return {
            'maps_enabled': maps_enabled,
            'maps_browser_key': browser_key if maps_enabled else '',
            'maps_map_id': map_id if maps_enabled else '',
            'time_ago': time_ago,
            'get_setting': get_setting,
            'announcement_banner': get_active_announcement(),
        }

    # Startup diagnostic: Google Maps configuration presence (names only, never values)
    from services.maps import get_server_key
    browser_key_present = bool(app.config.get('GOOGLE_MAPS_BROWSER_KEY', '').strip())
    map_id_present = bool(app.config.get('GOOGLE_MAPS_MAP_ID', '').strip())
    server_key_present = bool(get_server_key())

    maps_status_line = (
        f"Google Maps config: "
        f"browser_key={'present' if browser_key_present else 'MISSING'}, "
        f"map_id={'present' if map_id_present else 'MISSING'}, "
        f"server_key={'present' if server_key_present else 'MISSING'}"
    )
    app.logger.info(maps_status_line)
    if app.debug:
        print(maps_status_line)

    if not (browser_key_present and map_id_present and server_key_present):
        maps_warning = "Add GOOGLE_MAPS_* to .env (not .env.example) and restart the app."
        app.logger.warning(maps_warning)
        if app.debug:
            print(f"WARNING: {maps_warning}")

    # Ensure static upload directories exist automatically at startup
    uploads_base = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(os.path.join(uploads_base, 'products'), exist_ok=True)
    os.makedirs(os.path.join(uploads_base, 'profiles'), exist_ok=True)

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

    @app.errorhandler(403)
    def forbidden_error(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(413)
    def request_entity_too_large(e):
        return render_template('errors/413.html'), 413

    @app.errorhandler(429)
    def ratelimit_error(e):
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    # Must change password enforcement before every request
    @app.before_request
    def enforce_must_change_password():
        from flask_login import current_user
        if current_user.is_authenticated and getattr(current_user, 'must_change_password', False):
            endpoint = request.endpoint or ''
            allowed_endpoints = {'profile.password', 'auth.logout', 'static'}
            if endpoint not in allowed_endpoints and not endpoint.startswith('static') and not request.path.startswith('/static/'):
                if request.is_json or request.path.endswith('/quote'):
                    return {'error': 'Password change required.'}, 403
                flash('You must change your password before continuing.', 'warning')
                return redirect(url_for('profile.password'))

    # Import Blueprints
    from blueprints.auth.routes import auth_bp
    from blueprints.dashboard.routes import dashboard_bp
    from blueprints.marketplace.routes import marketplace_bp
    from blueprints.orders.routes import orders_bp
    from blueprints.prices.routes import prices_bp
    from blueprints.main.routes import main_bp
    from blueprints.profile.routes import profile_bp
    from blueprints.admin.routes import admin_bp
    from blueprints.gateway.routes import gateway_bp
    from blueprints.payments.routes import payments_bp

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(marketplace_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(prices_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(gateway_bp)
    app.register_blueprint(payments_bp)

    # Dev-only routes and blueprints (only available when app.debug is true)
    if app.debug:
        from blueprints.styleguide.routes import styleguide_bp
        app.register_blueprint(styleguide_bp)

        @app.route('/_maps_test')
        def maps_test():
            """DEV-ONLY: Google Maps foundation diagnostics and interactive test bench."""
            browser_key = app.config.get('GOOGLE_MAPS_BROWSER_KEY', '').strip()
            map_id = app.config.get('GOOGLE_MAPS_MAP_ID', '').strip()
            return render_template(
                'dev/maps_test.html',
                has_browser_key=bool(browser_key),
                has_map_id=bool(map_id),
            )

    # CLI Commands
    @app.cli.command('create-admin')
    def create_admin_command():
        """Create an administrator user interactively."""
        from models import User
        from email_validator import validate_email, EmailNotValidError
        from utils.phone import normalize_phone_number
        from utils.security import validate_admin_password

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

        password = click.prompt("Admin Password (min 10 chars)", hide_input=True, confirmation_prompt=True)
        is_valid, err_msg = validate_admin_password(password, email=email, name=name)
        if not is_valid:
            click.echo(f"Error: {err_msg}", err=True)
            return

        admin = User(
            name=name,
            email=email,
            role='admin',
            phone=phone_input or None,
            whatsapp_number=whatsapp,
            is_active=True,
            must_change_password=False,
            session_version=1
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Admin user '{email}' created successfully.")

    @app.cli.command('maps-check')
    def maps_check_command():
        """Run diagnostics on Google Maps environment configuration and server reachability."""
        from services.maps import get_server_key, is_placeholder_value, test_geocoding_api

        click.echo("==================================================")
        click.echo(" AgroLink Google Maps Configuration Diagnostic    ")
        click.echo("==================================================")

        # (a) & (b) Check configuration variables
        vars_to_check = [
            ("GOOGLE_MAPS_BROWSER_KEY", app.config.get('GOOGLE_MAPS_BROWSER_KEY', '').strip()),
            ("GOOGLE_MAPS_MAP_ID", app.config.get('GOOGLE_MAPS_MAP_ID', '').strip()),
            ("GOOGLE_MAPS_SERVER_KEY", get_server_key()),
        ]

        click.echo("\n[1] Environment Variables Status:")
        for var_name, var_val in vars_to_check:
            if not var_val:
                click.echo(f"  * {var_name}: MISSING")
            elif is_placeholder_value(var_val):
                click.echo(f"  * {var_name}: placeholder, replace with real value (length: {len(var_val)})")
            else:
                click.echo(f"  * {var_name}: present (length: {len(var_val)})")

        # (c) Real Geocoding API check using SERVER key
        click.echo("\n[2] Geocoding API Server-Side Check:")
        status, err_msg = test_geocoding_api()
        if status == 'OK':
            click.echo("  * Status: OK (Kandy, Sri Lanka resolved successfully)")
        else:
            msg_suffix = f" - {err_msg}" if err_msg else ""
            click.echo(f"  * Status: {status}{msg_suffix}")

        # (d) Real Routes API check using SERVER key
        from services.maps import test_routes_api
        click.echo("\n[3] Routes API Server-Side Check (Colombo to Kandy):")
        r_status, r_dist_km, r_err_msg = test_routes_api()
        if r_status == 'OK':
            click.echo(f"  * Status: OK (Distance: {r_dist_km} km)")
        else:
            r_suffix = f" - {r_err_msg}" if r_err_msg else ""
            click.echo(f"  * Status: FAILED ({r_status}{r_suffix})")

        # (e) Exact browser-key referrers to allow
        click.echo("\n[4] Required HTTP Referrers for Browser Key:")
        click.echo("  In Google Cloud Console (Credentials -> Browser Key -> Website restrictions):")
        click.echo("  * http://localhost:5000/*")
        click.echo("  * http://127.0.0.1:5000/*")
        click.echo("==================================================\n")

    @app.cli.command('seed-admin-demo')
    @click.option('--clear', is_flag=True, default=False, help='Purge previously seeded demo records.')
    def seed_admin_demo_command(clear):
        """Seed ~300 users, ~200 products, ~800 orders for admin dashboard demonstration."""
        from services.demo_seeder import seed_demo_data, clear_demo_data
        if clear:
            click.echo("Purging demo records (@demo.agrolink.lk)...")
            u_del, p_del, o_del = clear_demo_data()
            click.echo(f"Purged: {u_del} users, {p_del} products, {o_del} orders.")
            return

        click.echo("Seeding admin demo records (~300 users, ~200 products, ~800 orders across 6 months)...")
        u_count, p_count, o_count = seed_demo_data()
        click.echo(f"Successfully seeded: {u_count} users, {p_count} products, {o_count} orders.")
        click.echo("To purge anytime, run: flask seed-admin-demo --clear")

    return app


if __name__ == '__main__':
    app = create_app(debug=True)
    app.run(debug=True)
