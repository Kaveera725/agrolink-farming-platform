"""Platform settings service for AgroLink.

Provides cached access to dynamically configurable platform parameters with
graceful fallback to config.py constants and schema defaults.
"""
from datetime import datetime
from decimal import Decimal
import time
from typing import Any, Dict, Optional
from flask import current_app, has_app_context

# Cache storage: dict of key -> (value, expiry_timestamp)
_SETTINGS_CACHE: Dict[str, tuple[Any, float]] = {}
CACHE_TTL_SECONDS = 60
_ALL_LOADED_UNTIL = 0.0

SETTINGS_SCHEMA = {
    'delivery_base_fee': {
        'type': 'decimal',
        'default': Decimal('5000.00'),
        'min': 0,
        'max': 100000,
        'label': 'Delivery Base Fee (LKR)',
        'category': 'Delivery Rates',
        'description': 'Base flat fee charged for deliveries within the base radius.'
    },
    'delivery_base_km': {
        'type': 'decimal',
        'default': Decimal('50.00'),
        'min': 1,
        'max': 500,
        'label': 'Delivery Base Distance (km)',
        'category': 'Delivery Rates',
        'description': 'Maximum distance covered by the base delivery fee.'
    },
    'delivery_extra_per_km': {
        'type': 'decimal',
        'default': Decimal('60.00'),
        'min': 0,
        'max': 5000,
        'label': 'Delivery Extra Rate (LKR/km)',
        'category': 'Delivery Rates',
        'description': 'Additional rate charged per km for distances beyond the base distance.'
    },
    'max_delivery_km': {
        'type': 'decimal',
        'default': Decimal('300.00'),
        'min': 1,
        'max': 1000,
        'label': 'Maximum Delivery Distance (km)',
        'category': 'Delivery Rates',
        'description': 'Maximum allowable transport distance from farm collection point.'
    },
    'low_stock_kg': {
        'type': 'float',
        'default': 50.0,
        'min': 0,
        'max': 10000,
        'label': 'Low Stock Alert Threshold (kg)',
        'category': 'Marketplace & Inventory',
        'description': 'Produce items at or below this stock weight show a low-stock warning.'
    },
    'stale_price_days': {
        'type': 'int',
        'default': 7,
        'min': 1,
        'max': 90,
        'label': 'Stale Price Threshold (days)',
        'category': 'Reference Prices',
        'description': 'Market benchmark prices not updated within this number of days are flagged as stale.'
    },
    'announcement_enabled': {
        'type': 'bool',
        'default': False,
        'label': 'Enable Public Announcement Banner',
        'category': 'Announcement Banner',
        'description': 'Display a prominent banner across public marketplace and store pages.'
    },
    'announcement_text': {
        'type': 'str',
        'default': '',
        'max_length': 200,
        'label': 'Banner Announcement Text',
        'category': 'Announcement Banner',
        'description': 'Announcement text (max 200 chars). HTML will be escaped for security.'
    },
    'announcement_level': {
        'type': 'str',
        'default': 'info',
        'choices': ['info', 'warning'],
        'label': 'Banner Alert Style',
        'category': 'Announcement Banner',
        'description': 'Color scheme for the banner (Info or Warning).'
    },
    'announcement_expires_at': {
        'type': 'str',
        'default': '',
        'label': 'Banner Expiration Date / Time',
        'category': 'Announcement Banner',
        'description': 'Optional expiry date/time. Leave blank to display indefinitely.'
    },
}


def _cast_value(val_str: Optional[str], val_type: str) -> Any:
    """Cast a database text string to its appropriate Python type."""
    if val_str is None:
        return None
    val_type = (val_type or 'str').lower()
    if val_type in ('int', 'integer'):
        return int(float(val_str))
    elif val_type == 'float':
        return float(val_str)
    elif val_type == 'decimal':
        return Decimal(str(val_str))
    elif val_type in ('bool', 'boolean'):
        return str(val_str).strip().lower() in ('true', '1', 'yes', 'on', 't')
    return str(val_str)


def clear_settings_cache(key: Optional[str] = None) -> None:
    """Invalidate cached settings either globally or for a specific key."""
    global _ALL_LOADED_UNTIL
    _ALL_LOADED_UNTIL = 0.0
    if key:
        _SETTINGS_CACHE.pop(key, None)
    else:
        _SETTINGS_CACHE.clear()


def get_default_setting(key: str) -> Any:
    """Retrieve fallback default value for a key from config or schema."""
    import config
    schema = SETTINGS_SCHEMA.get(key)
    config_key = key.upper()

    if has_app_context() and config_key in current_app.config:
        cfg_val = current_app.config[config_key]
        if schema and schema.get('type') == 'decimal' and not isinstance(cfg_val, Decimal):
            return Decimal(str(cfg_val))
        return cfg_val

    if hasattr(config, config_key):
        cfg_val = getattr(config, config_key)
        if schema and schema.get('type') == 'decimal' and not isinstance(cfg_val, Decimal):
            return Decimal(str(cfg_val))
        return cfg_val

    if schema:
        return schema.get('default')

    return None


def get_setting(key: str, default: Any = None) -> Any:
    """Retrieve a setting value from cache, database, or fallback config.

    Cached for 60 seconds.
    """
    global _ALL_LOADED_UNTIL
    now = time.time()
    cached = _SETTINGS_CACHE.get(key)
    if cached is not None and cached[1] > now:
        return cached[0]

    # Preload all settings into cache in one query if cache is cold
    if now > _ALL_LOADED_UNTIL:
        try:
            from models import PlatformSetting
            all_rows = PlatformSetting.query.all()
            for r in all_rows:
                if r.value is not None:
                    _SETTINGS_CACHE[r.key] = (_cast_value(r.value, r.value_type), now + CACHE_TTL_SECONDS)
            _ALL_LOADED_UNTIL = now + CACHE_TTL_SECONDS
        except Exception:
            pass

    cached = _SETTINGS_CACHE.get(key)
    if cached is not None and cached[1] > now:
        return cached[0]

    fallback = get_default_setting(key)
    val = fallback if fallback is not None else default
    _SETTINGS_CACHE[key] = (val, now + CACHE_TTL_SECONDS)
    return val


def validate_setting(key: str, value: Any) -> tuple[Any, str]:
    """Validate a setting value against its schema rules.

    Returns:
        (coerced_value_as_str, value_type)
    Raises:
        ValueError if validation fails.
    """
    schema = SETTINGS_SCHEMA.get(key)
    if not schema:
        return str(value) if value is not None else '', 'str'

    val_type = schema.get('type', 'str')

    if val_type in ('int', 'integer'):
        try:
            num = int(value)
        except (ValueError, TypeError):
            raise ValueError(f"'{schema.get('label', key)}' must be an integer.")
        if 'min' in schema and num < schema['min']:
            raise ValueError(f"'{schema.get('label', key)}' must be at least {schema['min']}.")
        if 'max' in schema and num > schema['max']:
            raise ValueError(f"'{schema.get('label', key)}' must be at most {schema['max']}.")
        return str(num), 'int'

    elif val_type in ('float', 'decimal'):
        try:
            num = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"'{schema.get('label', key)}' must be a valid number.")
        if 'min' in schema and num < schema['min']:
            raise ValueError(f"'{schema.get('label', key)}' must be at least {schema['min']}.")
        if 'max' in schema and num > schema['max']:
            raise ValueError(f"'{schema.get('label', key)}' must be at most {schema['max']}.")
        return str(value).strip(), val_type

    elif val_type in ('bool', 'boolean'):
        b_val = str(value).strip().lower() in ('true', '1', 'yes', 'on', 't')
        return 'true' if b_val else 'false', 'bool'

    else:
        text_val = str(value or '').strip()
        if 'max_length' in schema and len(text_val) > schema['max_length']:
            raise ValueError(f"'{schema.get('label', key)}' cannot exceed {schema['max_length']} characters.")
        if 'choices' in schema and text_val not in schema['choices']:
            raise ValueError(f"'{schema.get('label', key)}' must be one of {', '.join(schema['choices'])}.")
        return text_val, 'str'


def set_setting(key: str, value: Any, user_id: Optional[int] = None) -> Any:
    """Validate, persist in database, and invalidate cache for key."""
    from extensions import db
    from models import PlatformSetting

    val_str, val_type = validate_setting(key, value)
    row = PlatformSetting.query.filter_by(key=key).first()
    if row is None:
        row = PlatformSetting(
            key=key,
            value=val_str,
            value_type=val_type,
            updated_by=user_id,
            updated_at=datetime.utcnow()
        )
        db.session.add(row)
    else:
        row.value = val_str
        row.value_type = val_type
        row.updated_by = user_id
        row.updated_at = datetime.utcnow()

    clear_settings_cache(key)
    return row


def reset_settings_to_defaults(user_id: Optional[int] = None) -> None:
    """Reset all platform settings to system default values."""
    from extensions import db
    from models import PlatformSetting
    PlatformSetting.query.delete()
    db.session.flush()
    clear_settings_cache()


def get_active_announcement() -> Optional[Dict[str, Any]]:
    """Return announcement banner details if currently active and unexpired."""
    enabled = get_setting('announcement_enabled', default=False)
    if not enabled:
        return None

    text = get_setting('announcement_text', default='').strip()
    if not text:
        return None

    expires_at_str = get_setting('announcement_expires_at', default='').strip()
    if expires_at_str:
        try:
            # Handle ISO string or date
            if 'T' in expires_at_str:
                exp_dt = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00')).replace(tzinfo=None)
            else:
                exp_dt = datetime.strptime(expires_at_str, '%Y-%m-%d')
                # Expire at end of that day
                exp_dt = exp_dt.replace(hour=23, minute=59, second=59)
            if datetime.utcnow() > exp_dt:
                return None
        except Exception:
            pass

    level = get_setting('announcement_level', default='info').lower()
    return {
        'text': text,
        'level': 'warning' if level == 'warning' else 'info',
        'expires_at': expires_at_str
    }
