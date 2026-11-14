import time
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from flask_limiter.util import get_remote_address

from extensions import db, limiter
from models import Order, Payment
from services.gateway_security import sign_payload
from services.payments import handle_gateway_result

gateway_bp = Blueprint('gateway', __name__, url_prefix='/gateway')


def get_user_rate_limit_key() -> str:
    """Rate limit per authenticated user ID, falling back to client IP."""
    if current_user and current_user.is_authenticated:
        return f"user:{current_user.id}"
    return get_remote_address()


def validate_luhn(card_number: str) -> bool:
    """Validate card number using the standard Luhn checksum algorithm."""
    digits = [int(c) for c in card_number if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10 == 0


def validate_expiry(expiry_str: str) -> Tuple[bool, Optional[str]]:
    """Validate card expiry format and ensure it is not in the past."""
    cleaned = expiry_str.strip().replace(" ", "").replace("-", "/")
    parts = cleaned.split("/")
    if len(parts) != 2:
        return False, "Invalid expiry format. Use MM/YY."
    try:
        month = int(parts[0])
        year = int(parts[1])
    except ValueError:
        return False, "Expiry month and year must be digits."

    if month < 1 or month > 12:
        return False, "Expiry month must be between 01 and 12."

    if year < 100:
        year += 2000

    now = datetime.utcnow()
    # Card is valid through the entire end of the specified month
    if year < now.year or (year == now.year and month < now.month):
        return False, "Card has expired (check expiry date)."

    if year > now.year + 20:
        return False, "Expiry date is too far in the future."

    return True, None


def detect_card_brand(clean_number: str) -> str:
    """Detect card brand prefix without saving or logging card data."""
    if clean_number.startswith('4'):
        return 'Visa'
    elif clean_number.startswith(('51', '52', '53', '54', '55')) or (clean_number.startswith('2') and len(clean_number) >= 4 and 2221 <= int(clean_number[:4]) <= 2720):
        return 'Mastercard'
    elif clean_number.startswith(('34', '37')):
        return 'American Express'
    elif clean_number.startswith(('6011', '65')):
        return 'Discover'
    return 'Card'


TEST_CARD_RULES = {
    '4242424242424242': ('success', None),
    '4000000000000002': ('failed', 'Card declined by issuing bank'),
    '4000000000009995': ('failed', 'Insufficient funds in account'),
}


@gateway_bp.route('/checkout/<txn_ref>', methods=['GET'])
@login_required
def checkout(txn_ref: str):
    """
    SimPay simulated card payment checkout view.
    Enforces that only the buyer who owns the order can access the session.
    """
    payment = Payment.query.filter_by(txn_ref=txn_ref).first_or_404()

    # Session ownership verification: Buyer who owns the order only
    if payment.order.buyer_id != current_user.id or current_user.role != 'buyer':
        abort(403)

    now = datetime.utcnow()

    # If already finalized, show friendly completed screen
    if payment.status in ('success', 'failed', 'refunded'):
        return render_template('gateway/session_status.html', payment=payment, status_type='completed')

    # If expired, mark and show friendly expired screen
    if payment.expires_at <= now or payment.status == 'expired':
        if payment.status != 'expired':
            payment.status = 'expired'
            payment.failure_reason = "Payment session expired (15-minute limit)."
            db.session.commit()
        return render_template('gateway/session_status.html', payment=payment, status_type='expired')

    return render_template(
        'gateway/checkout.html',
        payment=payment,
        order=payment.order,
        now=now
    )


@gateway_bp.route('/checkout/<txn_ref>', methods=['POST'])
@login_required
@limiter.limit("10 per minute", key_func=get_user_rate_limit_key)
def process_checkout(txn_ref: str):
    """
    Process simulated payment submission:
    - Luhn check & expiry validation
    - Test card rule application
    - Never store or log full card numbers or CVV
    - Sign result payload with HMAC-SHA256 and deliver via handle_gateway_result
    - Redirect to shop result page
    """
    payment = Payment.query.filter_by(txn_ref=txn_ref).first_or_404()

    if payment.order.buyer_id != current_user.id or current_user.role != 'buyer':
        abort(403)

    now = datetime.utcnow()

    # Check if session is already completed
    if payment.status in ('success', 'failed', 'refunded'):
        return redirect(url_for('payments.payment_result', txn_ref=payment.txn_ref))

    # Check if session has expired
    if payment.expires_at <= now or payment.status == 'expired':
        if payment.status != 'expired':
            payment.status = 'expired'
            payment.failure_reason = "Payment session expired (15-minute limit)."
            db.session.commit()
        return render_template('gateway/session_status.html', payment=payment, status_type='expired')

    # Enforce attempt caps per order
    max_attempts = current_app.config.get('MAX_PAYMENT_ATTEMPTS_PER_ORDER', 5)
    total_attempts = Payment.query.filter_by(order_id=payment.order_id).count()
    if total_attempts > max_attempts:
        flash(f"Maximum payment attempts ({max_attempts}) reached for this order. Please contact support.", "danger")
        return render_template('gateway/session_status.html', payment=payment, status_type='capped')

    # Read form inputs
    cardholder_name = request.form.get('cardholder_name', '').strip()
    raw_card_number = request.form.get('card_number', '')
    raw_expiry = request.form.get('expiry', '')
    raw_cvv = request.form.get('cvv', '').strip()

    clean_card_number = ''.join(c for c in raw_card_number if c.isdigit())

    # Form Validation
    if not cardholder_name:
        flash("Cardholder name is required.", "danger")
        return render_template('gateway/checkout.html', payment=payment, order=payment.order, now=now), 400

    if not validate_luhn(clean_card_number):
        flash("Invalid card number. Checksum validation failed.", "danger")
        return render_template('gateway/checkout.html', payment=payment, order=payment.order, now=now), 400

    is_valid_exp, exp_err = validate_expiry(raw_expiry)
    if not is_valid_exp:
        flash(exp_err or "Invalid expiration date.", "danger")
        return render_template('gateway/checkout.html', payment=payment, order=payment.order, now=now), 400

    if not (len(raw_cvv) in (3, 4) and raw_cvv.isdigit()):
        flash("Invalid security code (CVV). Must be 3 or 4 digits.", "danger")
        return render_template('gateway/checkout.html', payment=payment, order=payment.order, now=now), 400

    # Determine simulated card outcome
    if clean_card_number in TEST_CARD_RULES:
        result_status, failure_reason = TEST_CARD_RULES[clean_card_number]
    else:
        result_status = 'failed'
        failure_reason = 'Card not accepted (use a test card)'

    card_brand = detect_card_brand(clean_card_number)
    card_last4 = clean_card_number[-4:]

    # Build signed result payload (NEVER includes full card number or CVV)
    payload = {
        'txn_ref': payment.txn_ref,
        'order_id': payment.order_id,
        'amount': str(payment.amount),
        'status': result_status,
        'failure_reason': failure_reason,
        'card_brand': card_brand,
        'card_last4': card_last4,
        'timestamp': int(time.time()),
    }

    signature = sign_payload(payload)

    # Deliver to shop service (locking row, idempotent check)
    handle_gateway_result(payload, signature)

    # Redirect to shop payment result page (reads strictly from database)
    return redirect(url_for('payments.payment_result', txn_ref=payment.txn_ref))

