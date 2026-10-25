"""
Google Maps Server-Side Service for AgroLink.

CRITICAL SECURITY RULE:
The GOOGLE_MAPS_SERVER_KEY is used exclusively for server-to-server Google Maps API
calls (such as server-side geocoding, reverse geocoding, distance matrix calculations).
It must NEVER be exposed to templates, Jinja context processors, frontend JavaScript,
or any client-facing response payload.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from project root
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)


def get_server_key() -> str:
    """Return the server-side Google Maps API key directly from environment."""
    return os.getenv('GOOGLE_MAPS_SERVER_KEY', '').strip()


def is_server_key_configured() -> bool:
    """Check if the server-side Google Maps API key is configured."""
    return bool(get_server_key())

