import string
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from decimal import Decimal
from flask import current_app

from extensions import db
from models import Order, Payment, User
from services.gateway_security import verify_signature


def generate_txn_ref() -> str:
    """Generate a unique transaction reference formatted as 'SP-' + 12 uppercase chars."""
    charset = string.ascii_uppercase + string.digits
    for _ in range(10):
        code = ''.join(secrets.choice(charset) for _ in range(12))
        txn_ref = f"SP-{code}"
        if not Payment.query.filter_by(txn_ref=txn_ref).first():
            return txn_ref
    # Extremely unlikely fallback
    return f"SP-{secrets.token_hex(6).upper()}"


def create_payment_session(
    order_id: int,
    buyer_id: int
) -> Tuple[Optional[Payment], Optional[str]]:
    """
    Create a new payment session for an order, enforcing buyer ownership,
    order status, and maximum payment attempts.
    """
    order = Order.query.get(order_id)
    if not order:
        return None, "Order not found."

    if order.buyer_id != buyer_id:
        return None, "You do not have permission to pay for this order."

    if order.status in ('cancelled', 'rejected'):
        return None, f"Cannot pay for an order that is {order.status}."

    if getattr(order, 'payment_status', 'unpaid') == 'paid':
        return None, "This order has already been paid."

    max_attempts = current_app.config.get('MAX_PAYMENT_ATTEMPTS_PER_ORDER', 5)
    existing_payments = Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).all()

    # Check for an active unexpired initiated session
    now = datetime.utcnow()
    for p in existing_payments:
        if p.status == 'initiated' and p.expires_at > now:
            return p, None

    # Count total non-initiated attempts (or completed/failed attempts)
    if len(existing_payments) >= max_attempts:
        return None, f"Maximum payment attempts reached for this order ({max_attempts}). Please contact support."

    # Mark any stale initiated payments as expired
    for p in existing_payments:
        if p.status == 'initiated' and p.expires_at <= now:
            p.status = 'expired'
            p.failure_reason = "Payment session expired."

    session_minutes = current_app.config.get('PAYMENT_SESSION_MINUTES', 15)
    expires_at = now + timedelta(minutes=session_minutes)
    txn_ref = generate_txn_ref()

    amount = Decimal(str(order.total_price))
    payment = Payment(
        order_id=order.id,
        amount=amount,
        method='card',
        status='initiated',
        txn_ref=txn_ref,
        expires_at=expires_at
    )
    db.session.add(payment)

    # Set order payment_status to pending while in flight
    if hasattr(order, 'payment_status') and order.payment_status == 'unpaid':
        order.payment_status = 'pending'

    db.session.commit()
    return payment, None


def handle_gateway_result(payload: Dict[str, Any], signature: str) -> Dict[str, Any]:
    """
    Process the simulated gateway callback/webhook securely:
    1. Verify HMAC-SHA256 signature and timestamp freshness.
    2. Lock payment row with FOR UPDATE.
    3. Ensure idempotency (duplicate deliveries return without altering status).
    4. Record the final payment status and card details.
       (Note: Wallet credits and full order delivery updates are handled in 12B).
    """
    # 1. Signature & Replay Verification
    if not verify_signature(payload, signature):
        return {
            'success': False,
            'error': 'Invalid signature or expired payload.',
            'code': 'invalid_signature'
        }

    txn_ref = payload.get('txn_ref')
    if not txn_ref:
        return {
            'success': False,
            'error': 'Missing txn_ref in payload.',
            'code': 'missing_txn_ref'
        }

    # 2. Lock payment row with with_for_update()
    payment = Payment.query.filter_by(txn_ref=txn_ref).with_for_update().first()
    if not payment:
        return {
            'success': False,
            'error': f"Payment session with reference '{txn_ref}' was not found.",
            'code': 'not_found'
        }

    # 3. Idempotency Check: if already completed, do nothing
    if payment.status in ('success', 'failed', 'expired', 'refunded'):
        return {
            'success': True,
            'payment': payment,
            'already_processed': True,
            'status': payment.status
        }

    # 4. Check for session expiry at decision time
    now = datetime.utcnow()
    target_status = payload.get('status')
    if payment.expires_at < now and target_status != 'expired':
        payment.status = 'expired'
        payment.failure_reason = "Payment session expired prior to completion."
        payment.completed_at = now
        db.session.commit()
        return {
            'success': True,
            'payment': payment,
            'already_processed': False,
            'status': 'expired'
        }

    # Record the final payment status
    payment.status = target_status or 'failed'
    payment.failure_reason = payload.get('failure_reason')
    if payload.get('card_brand'):
        payment.card_brand = str(payload.get('card_brand'))[:20]
    if payload.get('card_last4'):
        payment.card_last4 = str(payload.get('card_last4'))[:4]
    payment.completed_at = now

    db.session.commit()

    return {
        'success': True,
        'payment': payment,
        'already_processed': False,
        'status': payment.status
    }
