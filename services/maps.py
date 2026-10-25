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


def is_placeholder_value(val: str) -> bool:
    """
    Detect obvious placeholder values in API credentials.
    Returns True for strings starting with 'your_', ending with '...', or containing 'paste'.
    """
    if not val or not isinstance(val, str):
        return False
    v = val.strip().lower()
    return v.startswith("your_") or v.endswith("...") or ("paste" in v)


def test_geocoding_api(server_key: str = None) -> tuple:
    """
    Make a single test call to the Geocoding API for 'Kandy, Sri Lanka' using the SERVER key.
    Returns (status, error_message).
    CRITICAL SECURITY RULE: Never logs, prints, or exposes the API key or request URL.
    """
    key = server_key if server_key is not None else get_server_key()
    if not key:
        return ("MISSING_KEY", "GOOGLE_MAPS_SERVER_KEY is not configured.")
    if is_placeholder_value(key):
        return ("PLACEHOLDER_KEY", "GOOGLE_MAPS_SERVER_KEY contains a placeholder value.")

    import json
    import urllib.parse
    import urllib.request

    query = urllib.parse.urlencode({
        "address": "Kandy, Sri Lanka",
        "key": key
    })
    endpoint = f"https://maps.googleapis.com/maps/api/geocode/json?{query}"

    req = urllib.request.Request(
        endpoint,
        headers={"User-Agent": "AgroLink-Diagnostics/1.0"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            status = data.get("status", "UNKNOWN")
            error_message = data.get("error_message", "")
            return (status, error_message)
    except Exception as err:
        return ("REQUEST_FAILED", f"Network or HTTP error: {type(err).__name__}")

