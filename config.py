import os
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from project root before Config class reads values
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)


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

    @classmethod
    def init_app(cls, app):
        """Read and refresh environment values dynamically at app creation time."""
        app.config['GOOGLE_MAPS_BROWSER_KEY'] = os.getenv('GOOGLE_MAPS_BROWSER_KEY', '').strip()
        app.config['GOOGLE_MAPS_MAP_ID'] = os.getenv('GOOGLE_MAPS_MAP_ID', '').strip()

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
