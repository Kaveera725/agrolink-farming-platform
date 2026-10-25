"""
Google Maps Server-Side Service for AgroLink.

CRITICAL SECURITY RULE:
The GOOGLE_MAPS_SERVER_KEY is used exclusively for server-to-server Google Maps API
calls (such as server-side geocoding, reverse geocoding, distance matrix calculations).
It must NEVER be exposed to templates, Jinja context processors, frontend JavaScript,
or any client-facing response payload.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Server-only Google Maps API Key
GOOGLE_MAPS_SERVER_KEY = os.getenv('GOOGLE_MAPS_SERVER_KEY', '').strip()


def get_server_key() -> str:
    """Return the server-side Google Maps API key."""
    return GOOGLE_MAPS_SERVER_KEY


def is_server_key_configured() -> bool:
    """Check if the server-side Google Maps API key is configured."""
    return bool(GOOGLE_MAPS_SERVER_KEY)
