"""Delivery pricing service for AgroLink."""
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
from typing import Union, Optional, Dict, Any
from flask import current_app, has_app_context

from config import (
    DELIVERY_BASE_FEE,
    DELIVERY_BASE_KM,
    DELIVERY_EXTRA_PER_KM,
    MAX_DELIVERY_KM,
)


def _get_pricing_constants():
    """Retrieve delivery pricing configuration from app config or defaults."""
    if has_app_context():
        base_fee = Decimal(str(current_app.config.get('DELIVERY_BASE_FEE', DELIVERY_BASE_FEE)))
        base_km = Decimal(str(current_app.config.get('DELIVERY_BASE_KM', DELIVERY_BASE_KM)))
        extra_per_km = Decimal(str(current_app.config.get('DELIVERY_EXTRA_PER_KM', DELIVERY_EXTRA_PER_KM)))
        max_km = Decimal(str(current_app.config.get('MAX_DELIVERY_KM', MAX_DELIVERY_KM)))
        return base_fee, base_km, extra_per_km, max_km
    return DELIVERY_BASE_FEE, DELIVERY_BASE_KM, DELIVERY_EXTRA_PER_KM, MAX_DELIVERY_KM


def calculate_delivery_fee(distance_km: Union[Decimal, float, int, str, None]) -> Decimal:
    """Calculate the delivery fee for a given driving distance.

    Rules:
    - Distance must not be None or negative.
    - Distance is rounded to 2 decimal places using ROUND_HALF_UP before evaluating rules.
    - If distance <= DELIVERY_BASE_KM: base fee.
    - If distance > DELIVERY_BASE_KM: base fee + EXTRA_PER_KM * ceil(distance - BASE_KM).
    - If distance > MAX_DELIVERY_KM: raises ValueError.

    Returns:
        Decimal delivery fee.
    """
    if distance_km is None:
        raise ValueError("Delivery distance cannot be None.")

    try:
        dist_dec = Decimal(str(distance_km))
    except Exception as exc:
        raise ValueError(f"Invalid distance value: {distance_km}") from exc

    if dist_dec < Decimal("0"):
        raise ValueError(f"Delivery distance cannot be negative: {distance_km}")

    # Round distance to 2 decimal places using ROUND_HALF_UP before applying rules
    rounded_dist = dist_dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    base_fee, base_km, extra_per_km, max_km = _get_pricing_constants()

    if rounded_dist > max_km:
        raise ValueError(f"Delivery distance ({rounded_dist} km) exceeds maximum delivery distance of {max_km} km.")

    if rounded_dist <= base_km:
        return base_fee

    diff = rounded_dist - base_km
    ceil_km = diff.to_integral_value(rounding=ROUND_CEILING)
    return base_fee + (extra_per_km * ceil_km)


def calculate_order_totals(
    items_total: Union[Decimal, float, int, str, None],
    fee: Union[Decimal, float, int, str, None] = Decimal("0"),
) -> Dict[str, Decimal]:
    """Calculate items total, delivery fee, and grand total for an order.

    Args:
        items_total: Sum of item prices.
        fee: Delivery fee (defaults to 0).

    Returns:
        dict with keys: 'items_total', 'delivery_fee', 'grand_total', 'total_price'.
    """
    if items_total is None:
        raise ValueError("items_total cannot be None.")

    try:
        items_dec = Decimal(str(items_total)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise ValueError(f"Invalid items_total value: {items_total}") from exc

    if items_dec < Decimal("0"):
        raise ValueError(f"items_total cannot be negative: {items_total}")

    if fee is None:
        fee_dec = Decimal("0.00")
    else:
        try:
            fee_dec = Decimal(str(fee)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except Exception as exc:
            raise ValueError(f"Invalid delivery fee value: {fee}") from exc

    if fee_dec < Decimal("0"):
        raise ValueError(f"delivery_fee cannot be negative: {fee}")

    grand_total = items_dec + fee_dec

    return {
        "items_total": items_dec,
        "delivery_fee": fee_dec,
        "grand_total": grand_total,
        "total_price": grand_total,
    }
