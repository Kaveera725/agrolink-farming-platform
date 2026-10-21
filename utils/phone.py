"""
Phone number normalization and validation utilities for Sri Lankan numbers.
E.164 format: +94XXXXXXXXX
"""
import re
from typing import Optional, Tuple


def normalize_phone_number(raw_number: Optional[str]) -> Optional[str]:
    """
    Normalizes a Sri Lankan phone number into E.164 format (+94XXXXXXXXX).
    Examples:
        '0771234567'    -> '+94771234567'
        '077 123 4567'  -> '+94771234567'
        '+94 77 1234567'-> '+94771234567'
        '94771234567'   -> '+94771234567'
        '0094771234567' -> '+94771234567'
        '771234567'     -> '+94771234567'

    Returns:
        Normalized E.164 string if valid pattern, otherwise None.
    """
    if not raw_number or not isinstance(raw_number, str):
        return None

    # Remove all whitespace, hyphens, parentheses, and dots
    cleaned = re.sub(r'[\s\-\(\)\.]+', '', raw_number.strip())

    if not cleaned:
        return None

    # Handle international prefixes
    if cleaned.startswith('+94'):
        digits = cleaned[3:]
    elif cleaned.startswith('0094'):
        digits = cleaned[4:]
    elif cleaned.startswith('94') and len(cleaned) == 11:
        digits = cleaned[2:]
    elif cleaned.startswith('0') and len(cleaned) == 10:
        digits = cleaned[1:]
    elif len(cleaned) == 9 and cleaned[0] in '123456789':
        digits = cleaned
    else:
        return None

    # Sri Lankan subscriber numbers must be exactly 9 digits, starting with 1-9
    # (Typically 7X for mobile/WhatsApp)
    if re.fullmatch(r'[1-9]\d{8}', digits):
        return f"+94{digits}"

    return None


def validate_sl_phone(raw_number: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validates and normalizes a Sri Lankan phone number.

    Returns:
        (is_valid, normalized_number, error_message)
    """
    if not raw_number or not raw_number.strip():
        return False, None, "Phone number is required."

    normalized = normalize_phone_number(raw_number)
    if not normalized:
        return False, None, "Please enter a valid Sri Lankan phone number (e.g. 077 123 4567 or +94771234567)."

    return True, normalized, None
