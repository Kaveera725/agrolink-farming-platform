from flask import (
    Blueprint,
    abort,
    jsonify,
    render_template,
    request,
)
from flask_login import current_user, login_required

from extensions import csrf
from models import Payment
from services.payments import handle_gateway_result

payments_bp = Blueprint('payments', __name__, url_prefix='/payments')


@payments_bp.route('/webhook', methods=['POST'])
@csrf.exempt
def gateway_webhook():
    """
    SimPay external payment webhook endpoint.
    Exempt from standard CSRF form tokens, secured via HMAC-SHA256 signature verification.
    """
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        return jsonify({'error': 'Malformed or missing JSON body.'}), 400

    # Signature may be provided in HTTP header X-Signature or payload dictionary
    signature = request.headers.get('X-Signature') or data.get('signature')
    payload = data.get('payload') or {k: v for k, v in data.items() if k != 'signature'}

    if not signature:
        return jsonify({'error': 'Missing signature in X-Signature header or JSON body.'}), 400

    result = handle_gateway_result(payload, signature)
    if not result.get('success'):
        return jsonify({'error': result.get('error', 'Webhook processing failed.')}), 400

    return jsonify({
        'status': 'received',
        'txn_ref': payload.get('txn_ref'),
        'payment_status': result.get('status'),
        'already_processed': result.get('already_processed', False)
    }), 200


@payments_bp.route('/result/<txn_ref>', methods=['GET'])
@login_required
def payment_result(txn_ref: str):
    """
    Shop result page displaying the outcome of a payment.
    CRITICAL SECURITY: Reads payment status strictly from the database.
    Never trusts or parses any status parameters from the URL query string.
    """
    payment = Payment.query.filter_by(txn_ref=txn_ref).first_or_404()

    # Ownership check: Only the buyer who owns the order (or an admin) can view
    if payment.order.buyer_id != current_user.id and current_user.role != 'admin':
        abort(403)

    return render_template('orders/payment_result.html', payment=payment, order=payment.order)

