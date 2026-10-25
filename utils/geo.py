"""
Geospatial and formatting utility functions for AgroLink.

Includes:
- haversine_km: Calculates great-circle distance between two coordinates in kilometers.
- format_distance_km: Formats distance in km (1 decimal under 10 km, otherwise nearest whole km).
- is_in_sri_lanka: Verifies if a given coordinate lies within the bounding box of Sri Lanka (lat 5.8 to 9.9, lng 79.4 to 82.0).
- parse_coord: Parses a coordinate input into a clean Decimal or returns None.
- time_ago: Formats a datetime into a human-readable relative time string (e.g., '5 minutes ago').
"""
import math
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Union

# Bounding box for Sri Lanka: Latitude 5.8 to 9.9, Longitude 79.4 to 82.0
SL_LAT_MIN = Decimal('5.8')
SL_LAT_MAX = Decimal('9.9')
SL_LNG_MIN = Decimal('79.4')
SL_LNG_MAX = Decimal('82.0')

EARTH_RADIUS_KM = 6371.0


def format_distance_km(dist_km: Optional[Union[float, Decimal, int]]) -> Optional[str]:
    """
    Formats a distance in km according to AgroLink display rules:
    - Under 10 km: 1 decimal place (e.g., '4.2 km')
    - 10 km and above: nearest whole km (e.g., '12 km', '94 km')
    Returns None if dist_km is None or invalid.
    """
    if dist_km is None:
        return None
    try:
        val = float(dist_km)
        if math.isnan(val) or math.isinf(val):
            return None
        if val < 0:
            val = 0.0
        if round(val, 1) < 10.0:
            return f"{val:.1f} km"
        return f"{round(val)} km"
    except (ValueError, TypeError):
        return None



def parse_coord(value: Any) -> Optional[Decimal]:
    """
    Parses a coordinate value (string, float, int, Decimal) into a Decimal.
    Returns None if the value is missing, empty, unparseable, or outside [-180, 180].
    """
    if value is None:
        return None

    try:
        if isinstance(value, (int, float)):
            if math.isnan(value) or math.isinf(value):
                return None
            coord = Decimal(str(value))
        elif isinstance(value, Decimal):
            coord = value
        elif isinstance(value, str):
            val_str = value.strip()
            if not val_str:
                return None
            coord = Decimal(val_str)
        else:
            return None

        # Geographical coordinate range check [-180, 180]
        if coord < Decimal('-180') or coord > Decimal('180'):
            return None

        return coord
    except (InvalidOperation, ValueError, TypeError):
        return None


def haversine_km(
    lat1: Union[float, Decimal, int, str],
    lng1: Union[float, Decimal, int, str],
    lat2: Union[float, Decimal, int, str],
    lng2: Union[float, Decimal, int, str]
) -> float:
    """
    Calculates the great-circle distance between two geographic coordinates in kilometers
    using the Haversine formula.

    Raises:
        ValueError: If any coordinate is invalid, outside valid ranges, or cannot be parsed.
    """
    p_lat1 = parse_coord(lat1)
    p_lng1 = parse_coord(lng1)
    p_lat2 = parse_coord(lat2)
    p_lng2 = parse_coord(lng2)

    if None in (p_lat1, p_lng1, p_lat2, p_lng2):
        raise ValueError("Invalid coordinates provided to haversine_km.")

    # Latitude must be within [-90, 90]
    if not (Decimal('-90') <= p_lat1 <= Decimal('90') and Decimal('-90') <= p_lat2 <= Decimal('90')):
        raise ValueError("Latitude must be between -90 and 90 degrees.")

    # Convert degrees to radians
    phi1 = math.radians(float(p_lat1))
    phi2 = math.radians(float(p_lat2))
    delta_phi = math.radians(float(p_lat2 - p_lat1))
    delta_lambda = math.radians(float(p_lng2 - p_lng1))

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)

    # Clamp a in [0, 1] to avoid float precision domain errors
    a = min(1.0, max(0.0, a))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return round(EARTH_RADIUS_KM * c, 4)


def is_in_sri_lanka(
    lat: Union[float, Decimal, int, str, None],
    lng: Union[float, Decimal, int, str, None]
) -> bool:
    """
    Returns True if the given coordinates fall within Sri Lanka's bounding box:
    Latitude: 5.8 to 9.9
    Longitude: 79.4 to 82.0
    """
    p_lat = parse_coord(lat)
    p_lng = parse_coord(lng)

    if p_lat is None or p_lng is None:
        return False

    return (SL_LAT_MIN <= p_lat <= SL_LAT_MAX) and (SL_LNG_MIN <= p_lng <= SL_LNG_MAX)


def time_ago(dt: Optional[datetime], now: Optional[datetime] = None) -> str:
    """
    Converts a datetime into a human-readable relative time string.
    Examples:
        'just now'
        '5 minutes ago'
        '1 hour ago'
        '2 hours ago'
        'yesterday'
        '3 days ago'
        '2 weeks ago'
        '1 month ago'
        '2 years ago'
    """
    if dt is None or not isinstance(dt, datetime):
        return ""

    if now is None:
        if dt.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.utcnow()
    else:
        # Align timezone-awareness if one is aware and one is naive
        if dt.tzinfo is not None and now.tzinfo is None:
            now = now.replace(tzinfo=dt.tzinfo)
        elif dt.tzinfo is None and now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)

    diff = now - dt
    total_seconds = int(diff.total_seconds())

    if total_seconds < 0 or total_seconds < 60:
        return "just now"

    minutes = total_seconds // 60
    if minutes == 1:
        return "1 minute ago"
    if minutes < 60:
        return f"{minutes} minutes ago"

    hours = minutes // 60
    if hours == 1:
        return "1 hour ago"
    if hours < 24:
        return f"{hours} hours ago"

    days = hours // 24
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"

    weeks = days // 7
    if weeks == 1:
        return "1 week ago"
    if weeks < 4:
        return f"{weeks} weeks ago"

    months = days // 30
    if months == 1:
        return "1 month ago"
    if months < 12:
        return f"{months} months ago"

    years = days // 365
    if years == 1:
        return "1 year ago"
    return f"{years} years ago"
