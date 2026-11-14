import string
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple
from decimal import Decimal
from flask import current_app

from extensions import db
from models import AdminAuditLog, Order, Payment, User, WalletTransaction
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


def expire_stale_payments() -> int:
    """
    Find unfinalized 'initiated' payments past their expiration date and mark them 'expired'.
    Resets the corresponding order's payment_status back to 'unpaid' if no active session remains.
    Returns the count of expired sessions.
    """
    now = datetime.utcnow()
    stale_payments = Payment.query.filter(
        Payment.status == 'initiated',
        Payment.expires_at <= now
    ).all()

    if not stale_payments:
        return 0

    expired_count = 0
    for p in stale_payments:
        p.status = 'expired'
        p.failure_reason = "Payment session expired (15-minute limit)."
        expired_count += 1

        # Check if order has any other active initiated session
        if p.order and getattr(p.order, 'payment_status', None) == 'pending':
            other_active = Payment.query.filter(
                Payment.order_id == p.order_id,
                Payment.id != p.id,
                Payment.status == 'initiated',
                Payment.expires_at > now
            ).first()
            if not other_active:
                p.order.payment_status = 'unpaid'

    db.session.commit()
    return expired_count


def create_payment_session(
    order_id: int,
    buyer_id: int
) -> Tuple[Optional[Payment], Optional[str]]:
    """
    Create a new payment session for an order, enforcing buyer ownership,
    confirmed/delivered order status, and maximum payment attempts.
    """
    # Clean up stale sessions lazily
    expire_stale_payments()

    order = Order.query.get(order_id)
    if not order:
        return None, "Order not found."

    if order.buyer_id != buyer_id:
        return None, "You do not have permission to pay for this order."

    if order.status in ('cancelled', 'rejected'):
        return None, f"Cannot pay for an order that is {order.status}."

    if order.status not in ('confirmed', 'delivered'):
        return None, "Order must be confirmed by the farmer before payment can be made."

    if getattr(order, 'payment_status', 'unpaid') == 'paid':
        return None, "This order has already been paid."

    max_attempts = current_app.config.get('MAX_PAYMENT_ATTEMPTS_PER_ORDER', 5)
    existing_payments = Payment.query.filter_by(order_id=order.id).order_by(Payment.created_at.desc()).all()

    # Reuse an active unexpired initiated session if available
    now = datetime.utcnow()
    for p in existing_payments:
        if p.status == 'initiated' and p.expires_at > now:
            return p, None

    # Count completed/failed/expired attempts towards the limit
    if len(existing_payments) >= max_attempts:
        return None, f"Maximum payment attempts reached for this order ({max_attempts}). Please contact support."

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
    if hasattr(order, 'payment_status'):
        order.payment_status = 'pending'

    db.session.commit()
    return payment, None


def handle_gateway_result(payload: Dict[str, Any], signature: str) -> Dict[str, Any]:
    """
    Process the simulated gateway callback/webhook securely:
    1. Verify HMAC-SHA256 signature and timestamp freshness.
    2. Lock payment row with FOR UPDATE.
    3. Ensure idempotency (duplicate deliveries return without altering status).
    4. Verify amount matches order total and order is still in 'confirmed' or 'delivered' state.
    5. On SUCCESS, in ONE transaction:
       - Update payment.status = 'success', completed_at
       - Update order.payment_status = 'paid'
       - Lock farmer's user row and credit farmer's wallet_balance by order.total_price
       - Append an immutable WalletTransaction row ('credit')
    6. On FAILURE:
       - Update payment.status = 'failed' with failure_reason
       - Update order.payment_status = 'failed'
    7. Dispatch notification hooks in safe try/except.
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

    # 3. Idempotency Check: if already completed, do nothing (never credit wallet twice!)
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
        if payment.order and getattr(payment.order, 'payment_status', None) != 'paid':
            payment.order.payment_status = 'unpaid'
        db.session.commit()
        return {
            'success': True,
            'payment': payment,
            'already_processed': False,
            'status': 'expired'
        }

    # 5. Lock order row and validate amount and order status
    order = Order.query.filter_by(id=payment.order_id).with_for_update().first()
    if not order:
        return {
            'success': False,
            'error': f"Order #{payment.order_id} not found.",
            'code': 'order_not_found'
        }

    # Verify amount matches order total exactly
    payload_amount = Decimal(str(payload.get('amount', '0')))
    order_amount = Decimal(str(order.total_price))
    if payload_amount != order_amount:
        payment.status = 'failed'
        payment.failure_reason = f"Amount mismatch: received Rs. {payload_amount}, expected Rs. {order_amount}."
        order.payment_status = 'failed'
        payment.completed_at = now
        db.session.commit()
        return {
            'success': False,
            'error': payment.failure_reason,
            'code': 'amount_mismatch'
        }

    # Verify order is in payable state ('confirmed' or 'delivered')
    if order.status not in ('confirmed', 'delivered'):
        payment.status = 'failed'
        payment.failure_reason = f"Cannot process payment for order in '{order.status}' status."
        order.payment_status = 'failed'
        payment.completed_at = now
        db.session.commit()
        return {
            'success': False,
            'error': payment.failure_reason,
            'code': 'invalid_order_status'
        }

    # Record card metadata (never PAN or CVV)
    if payload.get('card_brand'):
        payment.card_brand = str(payload.get('card_brand'))[:20]
    if payload.get('card_last4'):
        payment.card_last4 = str(payload.get('card_last4'))[:4]
    payment.completed_at = now

    if target_status == 'success':
        # ── SUCCESS FLOW (Atomic in one transaction) ────────────────────────
        payment.status = 'success'
        payment.failure_reason = None
        order.payment_status = 'paid'

        # Credit farmer's wallet (including delivery fee as farmer handles transport)
        farmer_id = order.product.farmer_id if (order.product and order.product.farmer_id) else None
        if farmer_id:
            farmer = User.query.filter_by(id=farmer_id).with_for_update().first()
            if farmer:
                credit_amount = Decimal(str(order.total_price))
                curr_balance = Decimal(str(farmer.wallet_balance or '0.00'))
                new_balance = curr_balance + credit_amount
                farmer.wallet_balance = new_balance

                # Append immutable wallet transaction
                wallet_tx = WalletTransaction(
                    user_id=farmer.id,
                    order_id=order.id,
                    payment_id=payment.id,
                    type='credit',
                    amount=credit_amount,
                    balance_after=new_balance,
                    description=f"Payment received for Order #{order.id}"
                )
                db.session.add(wallet_tx)

        db.session.commit()

        # Safe notification dispatch
        try:
            from services.notifications import notify_payment_success
            notify_payment_success(order, payment)
        except Exception as e:
            current_app.logger.error(f"Error dispatching notify_payment_success: {e}")

        return {
            'success': True,
            'payment': payment,
            'already_processed': False,
            'status': 'success'
        }

    else:
        # ── FAILURE FLOW ────────────────────────────────────────────────────
        payment.status = 'failed'
        payment.failure_reason = payload.get('failure_reason') or 'Payment declined or not authorized.'
        order.payment_status = 'failed'
        db.session.commit()

        # Safe notification dispatch
        try:
            from services.notifications import notify_payment_failed
            notify_payment_failed(order, payment)
        except Exception as e:
            current_app.logger.error(f"Error dispatching notify_payment_failed: {e}")

        return {
            'success': True,
            'payment': payment,
            'already_processed': False,
            'status': 'failed'
        }


def refund_payment(
    payment: Payment,
    reason: str,
    admin_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Issue an administrative refund for a paid transaction:
    - Locks payment and order rows.
    - Sets payment.status = 'refunded' and order.payment_status = 'refunded'.
    - Debits the farmer's wallet with an append-only 'reversal' transaction
      (negative balance is permitted but flagged in admin view).
    - Writes an immutable AdminAuditLog entry.
    """
    if not payment:
        return {'success': False, 'error': 'Payment object is required.'}

    if not reason or not reason.strip():
        return {'success': False, 'error': 'A mandatory refund reason must be provided.'}

    # Lock payment
    p_locked = Payment.query.filter_by(id=payment.id).with_for_update().first()
    if not p_locked or p_locked.status != 'success':
        return {'success': False, 'error': f"Cannot refund payment with status '{getattr(p_locked, 'status', 'unknown')}'."}

    order = Order.query.filter_by(id=p_locked.order_id).with_for_update().first()
    if not order:
        return {'success': False, 'error': f"Order #{p_locked.order_id} not found."}

    farmer_id = order.product.farmer_id if (order.product and order.product.farmer_id) else None
    if not farmer_id:
        return {'success': False, 'error': "Order farmer not found."}

    farmer = User.query.filter_by(id=farmer_id).with_for_update().first()
    if not farmer:
        return {'success': False, 'error': "Farmer user account not found."}

    refund_amount = Decimal(str(p_locked.amount))
    current_balance = Decimal(str(farmer.wallet_balance or '0.00'))
    new_balance = current_balance - refund_amount

    # Update statuses
    p_locked.status = 'refunded'
    p_locked.failure_reason = f"Refunded: {reason.strip()}"
    order.payment_status = 'refunded'
    farmer.wallet_balance = new_balance

    # Append reversal wallet transaction
    wallet_tx = WalletTransaction(
        user_id=farmer.id,
        order_id=order.id,
        payment_id=p_locked.id,
        type='reversal',
        amount=refund_amount,
        balance_after=new_balance,
        description=f"Refund reversal for Order #{order.id}: {reason.strip()}"
    )
    db.session.add(wallet_tx)

    # Record Admin Audit Log
    if admin_id:
        audit = AdminAuditLog(
            admin_id=admin_id,
            action='refund_payment',
            target_type='payment',
            target_id=p_locked.id,
            before_data={
                'status': 'success',
                'order_payment_status': 'paid',
                'farmer_wallet_balance': str(current_balance)
            },
            after_data={
                'status': 'refunded',
                'order_payment_status': 'refunded',
                'farmer_wallet_balance': str(new_balance),
                'reason': reason.strip()
            },
            result='success'
        )
        db.session.add(audit)

    db.session.commit()

    return {
        'success': True,
        'payment': p_locked,
        'order': order,
        'refund_amount': refund_amount,
        'farmer_balance': new_balance
    }
