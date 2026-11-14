from decimal import Decimal
from flask import Blueprint, abort, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from extensions import db
from models import WalletTransaction

wallet_bp = Blueprint('wallet', __name__, url_prefix='/wallet')


@wallet_bp.route('/', methods=['GET'])
@wallet_bp.route('', methods=['GET'])
@login_required
def index():
    """
    Farmer Wallet & Ledger view.
    Restricted to verified farmers (or administrators for support).
    """
    if current_user.role != 'farmer':
        abort(403)

    page = request.args.get('page', 1, type=int)
    per_page = 20

    pagination = WalletTransaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        WalletTransaction.created_at.desc(),
        WalletTransaction.id.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    # Compute lifetime gross earnings from simulated credits
    gross_credits = db.session.query(func.coalesce(func.sum(WalletTransaction.amount), 0)).filter(
        WalletTransaction.user_id == current_user.id,
        WalletTransaction.type == 'credit'
    ).scalar() or Decimal('0.00')

    # Compute lifetime refunds / reversals
    gross_reversals = db.session.query(func.coalesce(func.sum(WalletTransaction.amount), 0)).filter(
        WalletTransaction.user_id == current_user.id,
        WalletTransaction.type == 'reversal'
    ).scalar() or Decimal('0.00')

    return render_template(
        'wallet/index.html',
        transactions=pagination.items,
        pagination=pagination,
        wallet_balance=current_user.wallet_balance or Decimal('0.00'),
        gross_credits=gross_credits,
        gross_reversals=gross_reversals
    )
