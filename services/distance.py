"""Distance calculation and Google Routes API service for AgroLink."""
import logging
import time
import threading
from collections import OrderedDict
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple, Union, Optional
import requests
from flask import current_app, has_app_context

from config import ROUTE_FALLBACK_FACTOR, ROUTES_API_TIMEOUT_SECONDS
from services.maps import get_server_key, is_placeholder_value
from utils.geo import is_in_sri_lanka, haversine_km, parse_coord

logger = logging.getLogger(__name__)

ROUTES_API_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"


class DistanceCache:
    """Thread-safe in-process LRU cache with TTL for driving distances."""

    def __init__(self, maxsize: int = 1000, ttl_seconds: int = 86400):
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._cache = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple) -> Optional[Decimal]:
        with self._lock:
            if key not in self._cache:
                return None
            val, ts = self._cache[key]
            if time.time() - ts > self.ttl_seconds:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return val

    def set(self, key: tuple, value: Decimal) -> None:
        with self._lock:
            now = time.time()
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self.maxsize:
                self._cache.popitem(last=False)
            self._cache[key] = (value, now)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


_distance_cache = DistanceCache(maxsize=1000, ttl_seconds=86400)


def clear_distance_cache() -> None:
    """Clear the in-process distance cache (primarily for tests)."""
    _distance_cache.clear()


def _get_distance_config() -> Tuple[int, Decimal]:
    """Retrieve timeout and fallback factor from app config or defaults."""
    if has_app_context():
        timeout = int(current_app.config.get("ROUTES_API_TIMEOUT_SECONDS", ROUTES_API_TIMEOUT_SECONDS))
        factor = Decimal(str(current_app.config.get("ROUTE_FALLBACK_FACTOR", ROUTE_FALLBACK_FACTOR)))
        return timeout, factor
    return ROUTES_API_TIMEOUT_SECONDS, ROUTE_FALLBACK_FACTOR


def _calculate_estimated_distance(
    origin_lat: Union[float, Decimal, int, str],
    origin_lng: Union[float, Decimal, int, str],
    dest_lat: Union[float, Decimal, int, str],
    dest_lng: Union[float, Decimal, int, str],
    fallback_factor: Decimal,
) -> Decimal:
    """Calculate fallback driving distance using Haversine formula * ROUTE_FALLBACK_FACTOR."""
    direct_km = Decimal(str(haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)))
    est_km = (direct_km * fallback_factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return est_km


def get_driving_distance_km(
    origin_lat: Union[float, Decimal, int, str, None],
    origin_lng: Union[float, Decimal, int, str, None],
    dest_lat: Union[float, Decimal, int, str, None],
    dest_lng: Union[float, Decimal, int, str, None],
) -> Tuple[Decimal, str]:
    """Calculate driving distance between origin and destination coordinates.

    Uses Google Routes API computeRoutes (cheapest tier: routes.distanceMeters, DRIVE mode).
    Caches Google distance responses for 24 hours keyed by coordinates rounded to 4 decimals.
    Falls back to (haversine_km * ROUTE_FALLBACK_FACTOR) if the key is missing, or if the API
    errors, times out, or returns no routes.

    Args:
        origin_lat, origin_lng: Origin coordinates
        dest_lat, dest_lng: Destination coordinates

    Returns:
        (distance_km: Decimal, source: 'google' | 'estimated')

    Raises:
        ValueError: If origin or destination coordinates are outside Sri Lanka bounds.
    """
    p_olat = parse_coord(origin_lat)
    p_olng = parse_coord(origin_lng)
    p_dlat = parse_coord(dest_lat)
    p_dlng = parse_coord(dest_lng)

    if (
        p_olat is None
        or p_olng is None
        or p_dlat is None
        or p_dlng is None
        or not is_in_sri_lanka(p_olat, p_olng)
        or not is_in_sri_lanka(p_dlat, p_dlng)
    ):
        raise ValueError("Both origin and destination coordinates must be valid and within Sri Lanka bounds.")

    timeout, fallback_factor = _get_distance_config()

    # Cache key rounded to 4 decimal places (~11 meters precision)
    cache_key = (
        round(float(p_olat), 4),
        round(float(p_olng), 4),
        round(float(p_dlat), 4),
        round(float(p_dlng), 4),
    )

    cached_dist = _distance_cache.get(cache_key)
    if cached_dist is not None:
        return cached_dist, "google"

    server_key = get_server_key()
    if not server_key or is_placeholder_value(server_key):
        logger.warning("Google Maps server key is missing or contains placeholder. Falling back to estimated distance.")
        return _calculate_estimated_distance(p_olat, p_olng, p_dlat, p_dlng, fallback_factor), "estimated"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": server_key,
        "X-Goog-FieldMask": "routes.distanceMeters",
    }

    payload = {
        "origin": {
            "location": {
                "latLng": {
                    "latitude": float(p_olat),
                    "longitude": float(p_olng),
                }
            }
        },
        "destination": {
            "location": {
                "latLng": {
                    "latitude": float(p_dlat),
                    "longitude": float(p_dlng),
                }
            }
        },
        "travelMode": "DRIVE",
    }

    try:
        response = requests.post(
            ROUTES_API_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

        if response.status_code != 200:
            logger.warning(
                "Google Routes API returned status code %s. Falling back to estimated distance.",
                response.status_code,
            )
            return _calculate_estimated_distance(p_olat, p_olng, p_dlat, p_dlng, fallback_factor), "estimated"

        data = response.json()
        routes = data.get("routes", [])
        if not routes or not isinstance(routes, list):
            logger.warning("Google Routes API returned empty or invalid routes list. Falling back to estimated distance.")
            return _calculate_estimated_distance(p_olat, p_olng, p_dlat, p_dlng, fallback_factor), "estimated"

        distance_meters = routes[0].get("distanceMeters")
        if distance_meters is None:
            logger.warning("Google Routes API response missing distanceMeters. Falling back to estimated distance.")
            return _calculate_estimated_distance(p_olat, p_olng, p_dlat, p_dlng, fallback_factor), "estimated"

        meters_dec = Decimal(str(distance_meters))
        distance_km = (meters_dec / Decimal("1000")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Cache the successful Google distance
        _distance_cache.set(cache_key, distance_km)

        return distance_km, "google"

    except requests.exceptions.Timeout:
        logger.warning("Google Routes API request timed out (%ss). Falling back to estimated distance.", timeout)
        return _calculate_estimated_distance(p_olat, p_olng, p_dlat, p_dlng, fallback_factor), "estimated"
    except Exception as exc:
        logger.warning(
            "Google Routes API call failed (%s). Falling back to estimated distance.",
            type(exc).__name__,
        )
        return _calculate_estimated_distance(p_olat, p_olng, p_dlat, p_dlng, fallback_factor), "estimated"
