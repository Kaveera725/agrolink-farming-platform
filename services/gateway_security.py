import hmac
import hashlib
import json
import os
import time
from typing import Any, Dict, Optional
from flask import current_app, has_app_context


def get_gateway_secret(secret: Optional[str] = None) -> str:
    """Retrieve the payment gateway secret key from parameter, app config, or environment."""
    if secret:
        return secret

    if has_app_context():
        app_secret = current_app.config.get('PAYMENT_GATEWAY_SECRET')
        if app_secret:
            return app_secret

    from config import Config
    env_secret = getattr(Config, 'PAYMENT_GATEWAY_SECRET', None) or os.getenv('PAYMENT_GATEWAY_SECRET')
    if env_secret:
        return env_secret

    raise ValueError("PAYMENT_GATEWAY_SECRET is not configured.")


def canonical_json(payload: Dict[str, Any]) -> str:
    """Produce a canonical JSON string with sorted keys and compact delimiters."""
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str)


def sign_payload(payload: Dict[str, Any], secret: Optional[str] = None) -> str:
    """
    Generate an HMAC-SHA256 hex signature over the canonical JSON representation
    of the given payload dictionary.
    """
    effective_secret = get_gateway_secret(secret)
    canonical = canonical_json(payload)
    sig = hmac.new(
        effective_secret.encode('utf-8'),
        canonical.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return sig


def verify_signature(
    payload: Dict[str, Any],
    signature: str,
    secret: Optional[str] = None,
    max_age_seconds: int = 600
) -> bool:
    """
    Verify the HMAC-SHA256 signature of a payload.
    Enforces replay protection by rejecting payloads older than max_age_seconds (default 10 minutes)
    or timestamps unreasonably far in the future.
    """
    if not signature or not isinstance(signature, str):
        return False

    if not isinstance(payload, dict):
        return False

    # Replay protection via timestamp
    ts_val = payload.get('timestamp')
    if ts_val is None:
        return False

    try:
        ts = float(ts_val)
    except (ValueError, TypeError):
        return False

    now = time.time()
    # Reject if older than max_age_seconds (10 minutes)
    if (now - ts) > max_age_seconds:
        return False

    # Also reject if timestamp is more than 60 seconds into the future (clock drift tolerance)
    if (ts - now) > 60:
        return False

    try:
        expected_sig = sign_payload(payload, secret)
    except Exception:
        return False

    return hmac.compare_digest(signature, expected_sig)
