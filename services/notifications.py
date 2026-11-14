"""Notifications service for AgroLink.

Provides dispatch hooks for user alerts, transactional messages, and administrative interventions.
"""
import logging

logger = logging.getLogger(__name__)


def notify_order_cancelled_by_admin(order, reason, admin):
    """
    Hook called when an administrator cancels an active order.
    Notifies both buyer and farmer regarding the cancellation and reason.

    TODO: Integrate with external SMS / WhatsApp gateway (e.g. Twilio or local LK gateway)
          and transactional email provider to send immediate alerts to:
          1. Buyer: order.buyer.email / order.buyer.phone
          2. Farmer: order.product.farmer.email / order.product.farmer.phone
    """
    buyer_name = order.buyer.name if order.buyer else f"Buyer #{order.buyer_id}"
    farmer_name = order.product.farmer.name if (order.product and order.product.farmer) else "Farmer"
    product_name = order.product.name if order.product else "Crop"

    logger.info(
        f"[Notification] Order #{order.id} cancelled by Admin {admin.name} ({admin.email}). "
        f"Reason: '{reason}'. Alerting buyer {buyer_name} and farmer {farmer_name} for product '{product_name}'."
    )
    return True


def notify_payment_success(order, payment):
    """
    STUB: Hook called when a simulated payment succeeds.
    Logs successful payment alert. Full WhatsApp notification dispatch is implemented in Task 12C.
    """
    logger.info(
        f"[Payment Notification] SUCCESS: Order #{order.id} payment confirmed via {payment.method} "
        f"(Txn: {payment.txn_ref}, Amount: Rs. {payment.amount}). "
        f"Buyer: {order.buyer_id}, Farmer: {order.product.farmer_id if order.product else 'N/A'}."
    )
    return True


def notify_payment_failed(order, payment):
    """
    STUB: Hook called when a simulated payment fails.
    Logs payment failure alert. Full WhatsApp notification dispatch is implemented in Task 12C.
    """
    logger.info(
        f"[Payment Notification] FAILED: Order #{order.id} payment failed via {payment.method} "
        f"(Txn: {payment.txn_ref}, Reason: {payment.failure_reason}). "
        f"Buyer: {order.buyer_id}."
    )
    return True


