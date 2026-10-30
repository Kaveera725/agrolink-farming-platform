import os
from decimal import Decimal
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from project root before Config class reads values
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

# Delivery pricing & routing configuration constants
DELIVERY_BASE_FEE = Decimal(os.getenv("DELIVERY_BASE_FEE", "5000"))
DELIVERY_BASE_KM = Decimal(os.getenv("DELIVERY_BASE_KM", "50"))
DELIVERY_EXTRA_PER_KM = Decimal(os.getenv("DELIVERY_EXTRA_PER_KM", "60"))
MAX_DELIVERY_KM = Decimal(os.getenv("MAX_DELIVERY_KM", "300"))
ROUTE_FALLBACK_FACTOR = Decimal(os.getenv("ROUTE_FALLBACK_FACTOR", "1.3"))
ROUTES_API_TIMEOUT_SECONDS = int(os.getenv("ROUTES_API_TIMEOUT_SECONDS", "5"))


class Config:
    """Base application configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://agrolink_db_user:agrolink_db_user_password@localhost:5432/agrolink_db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB maximum request / file size

    # Client-facing Google Maps Credentials (safe for templates and frontend JS)
    GOOGLE_MAPS_BROWSER_KEY = os.getenv('GOOGLE_MAPS_BROWSER_KEY', '').strip()
    GOOGLE_MAPS_MAP_ID = os.getenv('GOOGLE_MAPS_MAP_ID', '').strip()

    # Delivery pricing & routing configuration
    DELIVERY_BASE_FEE = DELIVERY_BASE_FEE
    DELIVERY_BASE_KM = DELIVERY_BASE_KM
    DELIVERY_EXTRA_PER_KM = DELIVERY_EXTRA_PER_KM
    MAX_DELIVERY_KM = MAX_DELIVERY_KM
    ROUTE_FALLBACK_FACTOR = ROUTE_FALLBACK_FACTOR
    ROUTES_API_TIMEOUT_SECONDS = ROUTES_API_TIMEOUT_SECONDS
    ADMIN_SESSION_TIMEOUT_MINUTES = int(os.getenv('ADMIN_SESSION_TIMEOUT_MINUTES', '30'))

    @classmethod
    def init_app(cls, app):
        """Read and refresh environment values dynamically at app creation time."""
        app.config['ADMIN_SESSION_TIMEOUT_MINUTES'] = int(os.getenv('ADMIN_SESSION_TIMEOUT_MINUTES', '30'))
        app.config['GOOGLE_MAPS_BROWSER_KEY'] = os.getenv('GOOGLE_MAPS_BROWSER_KEY', '').strip()
        app.config['GOOGLE_MAPS_MAP_ID'] = os.getenv('GOOGLE_MAPS_MAP_ID', '').strip()
        app.config['DELIVERY_BASE_FEE'] = Decimal(os.getenv("DELIVERY_BASE_FEE", "5000"))
        app.config['DELIVERY_BASE_KM'] = Decimal(os.getenv("DELIVERY_BASE_KM", "50"))
        app.config['DELIVERY_EXTRA_PER_KM'] = Decimal(os.getenv("DELIVERY_EXTRA_PER_KM", "60"))
        app.config['MAX_DELIVERY_KM'] = Decimal(os.getenv("MAX_DELIVERY_KM", "300"))
        app.config['ROUTE_FALLBACK_FACTOR'] = Decimal(os.getenv("ROUTE_FALLBACK_FACTOR", "1.3"))
        app.config['ROUTES_API_TIMEOUT_SECONDS'] = int(os.getenv("ROUTES_API_TIMEOUT_SECONDS", "5"))

    @property
    def MAPS_ENABLED(self) -> bool:
        """True only if both the browser key and map ID are configured."""
        return bool(self.GOOGLE_MAPS_BROWSER_KEY and self.GOOGLE_MAPS_MAP_ID)


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    DEBUG = True
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
