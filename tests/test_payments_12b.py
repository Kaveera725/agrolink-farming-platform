import time
import unittest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from app import create_app
from extensions import db
from models import AdminAuditLog, Order, Payment, Product, User, WalletTransaction
from services.gateway_security import sign_payload
from services.payments import (
    create_payment_session,
    expire_stale_payments,
    handle_gateway_result,
    refund_payment,
)


class TestPayments12B(unittest.TestCase):
    """
    Comprehensive verification of Task 12B deliverables:
    - Buyer 'Pay now' permission matrix, status validation, and DB-driven pricing
    - Single-transaction wallet credit and duplicate callback idempotency
    - Payment failure and retry lifecycle
    - Lazy and batch session expiry
    - Administrative refunds, wallet reversal, and negative balance handling
    - Cancellation and rejection guards on paid orders
    - Receipt access control and printable invoice generation
    - Farmer wallet page permissions and ledger display
    - Admin payments registry, refund controls, and CSV export injection safety
    """

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['PAYMENT_GATEWAY_SECRET'] = 'unit-test-12b-secret-2026'
        self.app.config['MAX_PAYMENT_ATTEMPTS_PER_ORDER'] = 5
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.uid = uuid.uuid4().hex[:8]

        # 1. Seed Farmer
        self.farmer = User(
            name=f"Farmer {self.uid}",
            email=f"farmer_{self.uid}@agrolink.lk",
            role="farmer",
            phone="0771000010",
            whatsapp_number="+94771000010",
            location="Dambulla",
            wallet_balance=Decimal('0.00'),
            is_active=True,
            session_version=1
        )
        self.farmer.set_password("FarmerPass!2026")

        # 2. Seed Buyer 1 (Order owner)
        self.buyer = User(
            name=f"Buyer {self.uid}",
            email=f"buyer_{self.uid}@agrolink.lk",
            role="buyer",
            phone="0771000011",
            whatsapp_number="+94771000011",
            location="Colombo",
            is_active=True,
            session_version=1
        )
        self.buyer.set_password("BuyerPass!2026")

        # 3. Seed Buyer 2 (Non-owner)
        self.other_buyer = User(
            name=f"Other Buyer {self.uid}",
            email=f"other_{self.uid}@agrolink.lk",
            role="buyer",
            phone="0771000012",
            whatsapp_number="+94771000012",
            location="Galle",
            is_active=True,
            session_version=1
        )
        self.other_buyer.set_password("OtherPass!2026")

        # 4. Seed Admin
        self.admin = User(
            name=f"Admin {self.uid}",
            email=f"admin_{self.uid}@agrolink.lk",
            role="admin",
            phone="0771000013",
            is_active=True,
            session_version=1
        )
        self.admin.set_password("AdminPass!2026")

        db.session.add_all([self.farmer, self.buyer, self.other_buyer, self.admin])
        db.session.commit()

        # Seed Product
        self.product = Product(
            farmer_id=self.farmer.id,
            name=f"Keeri Samba {self.uid}",
            category="Grains & Rice",
            description="Polonnaruwa Harvest",
            price_per_kg=220.00,
            quantity_kg=100.0,
            is_available=True
        )
        db.session.add(self.product)
        db.session.commit()

        # Seed Order (confirmed by default)
        self.order = Order(
            buyer_id=self.buyer.id,
            product_id=self.product.id,
            quantity_kg=20.0,
            items_total=Decimal('4400.00'),
            delivery_fee=Decimal('350.00'),
            total_price=Decimal('4750.00'),
            status='confirmed',
            payment_status='unpaid',
            fulfillment_type='delivery',
            delivery_address='No 45, Galle Road, Colombo 03'
        )
        db.session.add(self.order)
        db.session.commit()

    def tearDown(self):
        WalletTransaction.query.filter(WalletTransaction.user_id.in_([self.farmer.id, self.buyer.id, self.other_buyer.id])).delete()
        Payment.query.filter(Payment.order_id == self.order.id).delete()
        Order.query.filter(Order.id == self.order.id).delete()
        Product.query.filter(Product.id == self.product.id).delete()
        db.session.commit()
        db.session.remove()
        self.ctx.pop()

    def _login(self, email, password):
        self.client.get('/auth/logout', follow_redirects=True)
        return self.client.post('/auth/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    # ── 1. Buyer Pay Now Permission Matrix ──────────────────────────────────
    def test_pay_now_permission_matrix(self):
        """
        Verify that POST /orders/<id>/pay is strictly limited to the buyer owner,
        and only when status is confirmed/delivered and payment_status is unpaid/failed.
        """
        # A. Guest -> redirects to login
        res = self.client.post(f"/orders/{self.order.id}/pay")
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.headers.get('Location', ''))

        # B. Non-owner buyer -> 403 Forbidden
        self._login(self.other_buyer.email, "OtherPass!2026")
        res = self.client.post(f"/orders/{self.order.id}/pay")
        self.assertEqual(res.status_code, 403)

        # C. Farmer -> 403 Forbidden
        self._login(self.farmer.email, "FarmerPass!2026")
        res = self.client.post(f"/orders/{self.order.id}/pay")
        self.assertEqual(res.status_code, 403)

        # D. Admin -> 403 Forbidden (Only buyer can initiate buyer checkout)
        self._login(self.admin.email, "AdminPass!2026")
        res = self.client.post(f"/orders/{self.order.id}/pay")
        self.assertEqual(res.status_code, 403)

        # E. Order status pending (unconfirmed) -> blocked
        self._login(self.buyer.email, "BuyerPass!2026")
        self.order.status = 'pending'
        db.session.commit()
        res = self.client.post(f"/orders/{self.order.id}/pay", follow_redirects=True)
        self.assertIn(b"Order must be confirmed by the farmer", res.data)

        # F. Order status rejected -> blocked
        self.order.status = 'rejected'
        db.session.commit()
        res = self.client.post(f"/orders/{self.order.id}/pay", follow_redirects=True)
        self.assertIn(b"Cannot pay for an order that is rejected", res.data)

        # G. Order status cancelled -> blocked
        self.order.status = 'cancelled'
        db.session.commit()
        res = self.client.post(f"/orders/{self.order.id}/pay", follow_redirects=True)
        self.assertIn(b"Cannot pay for an order that is cancelled", res.data)

        # H. Already paid order -> blocked
        self.order.status = 'confirmed'
        self.order.payment_status = 'paid'
        db.session.commit()
        res = self.client.post(f"/orders/{self.order.id}/pay", follow_redirects=True)
        self.assertIn(b"already been paid", res.data)

        # I. Valid Confirmed + Unpaid -> Redirects to SimPay Checkout
        self.order.payment_status = 'unpaid'
        db.session.commit()
        res = self.client.post(f"/orders/{self.order.id}/pay")
        self.assertEqual(res.status_code, 302)
        self.assertIn('/gateway/checkout/SP-', res.headers.get('Location', ''))

        # Check DB state: Order payment status updated to pending
        db.session.refresh(self.order)
        self.assertEqual(self.order.payment_status, 'pending')

        # J. Delivered + Unpaid -> Also allowed to pay
        self.order.status = 'delivered'
        self.order.payment_status = 'unpaid'
        db.session.commit()
        res2 = self.client.post(f"/orders/{self.order.id}/pay")
        self.assertEqual(res2.status_code, 302)
        self.assertIn('/gateway/checkout/SP-', res2.headers.get('Location', ''))

    # ── 2. Amount Taken From Database ────────────────────────────────────────
    def test_pay_now_amount_from_db(self):
        """Amount is strictly taken from DB order.total_price; client parameters are ignored."""
        self._login(self.buyer.email, "BuyerPass!2026")
        # Attempt to inject a cheap amount via POST data
        self.client.post(f"/orders/{self.order.id}/pay", data={'amount': '1.00'})

        payment = Payment.query.filter_by(order_id=self.order.id).first()
        self.assertIsNotNone(payment)
        # Must match order.total_price (Rs. 4,750.00), not Rs. 1.00
        self.assertEqual(payment.amount, Decimal('4750.00'))

    # ── 3. Single-Transaction Wallet Credit & Idempotency ─────────────────────
    def test_payment_success_credits_farmer_wallet_once(self):
        """
        Payment success atomically:
        - Sets payment.status = 'success'
        - Sets order.payment_status = 'paid'
        - Credits farmer's wallet_balance by grand total (items + delivery fee)
        - Appends WalletTransaction(type='credit')
        - Duplicate delivery never credits wallet twice
        """
        payment, err = create_payment_session(self.order.id, self.buyer.id)
        self.assertIsNone(err)

        payload = {
            'txn_ref': payment.txn_ref,
            'order_id': payment.order_id,
            'amount': str(payment.amount),
            'status': 'success',
            'card_brand': 'Visa',
            'card_last4': '4242',
            'timestamp': int(time.time())
        }
        sig = sign_payload(payload, secret=self.app.config['PAYMENT_GATEWAY_SECRET'])

        # First execution -> Process payment & credit wallet
        res1 = handle_gateway_result(payload, sig)
        self.assertTrue(res1['success'])
        self.assertFalse(res1['already_processed'])

        db.session.refresh(payment)
        db.session.refresh(self.order)
        db.session.refresh(self.farmer)

        self.assertEqual(payment.status, 'success')
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(self.farmer.wallet_balance, Decimal('4750.00'))

        # Verify ledger row
        ledger_txs = WalletTransaction.query.filter_by(order_id=self.order.id).all()
        self.assertEqual(len(ledger_txs), 1)
        self.assertEqual(ledger_txs[0].type, 'credit')
        self.assertEqual(ledger_txs[0].amount, Decimal('4750.00'))
        self.assertEqual(ledger_txs[0].balance_after, Decimal('4750.00'))

        # Second duplicate execution -> Idempotent, balance remains 4750.00
        res2 = handle_gateway_result(payload, sig)
        self.assertTrue(res2['success'])
        self.assertTrue(res2['already_processed'])

        db.session.refresh(self.farmer)
        self.assertEqual(self.farmer.wallet_balance, Decimal('4750.00'))
        self.assertEqual(WalletTransaction.query.filter_by(order_id=self.order.id).count(), 1)

    # ── 4. Payment Failure & Retry Flow ──────────────────────────────────────
    def test_payment_failure_retry_success(self):
        """Failed payment marks status failed and allows buyer to retry and succeed."""
        self._login(self.buyer.email, "BuyerPass!2026")

        # 1. Initiate session
        self.client.post(f"/orders/{self.order.id}/pay")
        payment = Payment.query.filter_by(order_id=self.order.id).first()

        # 2. Checkout with declining test card
        self.client.post(f"/gateway/checkout/{payment.txn_ref}", data={
            'cardholder_name': 'Test Buyer',
            'card_number': '4000 0000 0000 0002',
            'expiry': '12/28',
            'cvv': '123'
        }, follow_redirects=True)

        db.session.refresh(payment)
        db.session.refresh(self.order)
        self.assertEqual(payment.status, 'failed')
        self.assertEqual(self.order.payment_status, 'failed')
        self.assertEqual(self.farmer.wallet_balance, Decimal('0.00'))

        # 3. Buyer clicks 'Try again' -> POST /orders/<id>/pay
        res_retry = self.client.post(f"/orders/{self.order.id}/pay")
        self.assertEqual(res_retry.status_code, 302)

        # Active or new payment session created
        payment2 = Payment.query.filter_by(order_id=self.order.id, status='initiated').first()
        self.assertIsNotNone(payment2)

        # 4. Checkout with successful test card
        self.client.post(f"/gateway/checkout/{payment2.txn_ref}", data={
            'cardholder_name': 'Test Buyer',
            'card_number': '4242 4242 4242 4242',
            'expiry': '12/28',
            'cvv': '123'
        }, follow_redirects=True)

        db.session.refresh(payment2)
        db.session.refresh(self.order)
        db.session.refresh(self.farmer)

        self.assertEqual(payment2.status, 'success')
        self.assertEqual(self.order.payment_status, 'paid')
        self.assertEqual(self.farmer.wallet_balance, Decimal('4750.00'))

    # ── 5. Stale Payment Expiry ──────────────────────────────────────────────
    def test_expired_session_resets_order_unpaid(self):
        """expire_stale_payments marks old initiated payments as expired and resets order to unpaid."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        # Force expiration timestamp into the past
        payment.expires_at = datetime.utcnow() - timedelta(minutes=20)
        db.session.commit()

        expired_count = expire_stale_payments()
        self.assertGreaterEqual(expired_count, 1)

        db.session.refresh(payment)
        db.session.refresh(self.order)
        self.assertEqual(payment.status, 'expired')
        self.assertEqual(self.order.payment_status, 'unpaid')

    # ── 6. Admin Refund & Negative Balance Handling ──────────────────────────
    def test_admin_refund_reverses_wallet_credit(self):
        """
        Admin refund:
        - payment.status = 'refunded', order.payment_status = 'refunded'
        - Debits farmer wallet (allows negative balance)
        - Creates WalletTransaction(type='reversal')
        - Logs AdminAuditLog
        """
        # First complete a payment
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        payload = {
            'txn_ref': payment.txn_ref,
            'order_id': payment.order_id,
            'amount': str(payment.amount),
            'status': 'success',
            'timestamp': int(time.time())
        }
        sig = sign_payload(payload, secret=self.app.config['PAYMENT_GATEWAY_SECRET'])
        handle_gateway_result(payload, sig)

        # Now simulate farmer having withdrawn funds (balance = 1000.00)
        self.farmer.wallet_balance = Decimal('1000.00')
        db.session.commit()

        # Non-admin attempting refund -> 403
        self._login(self.buyer.email, "BuyerPass!2026")
        res_fail = self.client.post(f"/admin/payments/{payment.id}/refund", data={'reason': 'Buyer cancelled'})
        self.assertEqual(res_fail.status_code, 403)

        # Admin calling without reason -> flashed error
        self._login(self.admin.email, "AdminPass!2026")
        res_no_reason = self.client.post(f"/admin/payments/{payment.id}/refund", data={'reason': ''}, follow_redirects=True)
        self.assertIn(b"mandatory refund reason", res_no_reason.data)

        # Admin refund with valid reason
        res_refund = self.client.post(f"/admin/payments/{payment.id}/refund", data={
            'reason': 'Produce spoiled during transport'
        }, follow_redirects=True)
        self.assertEqual(res_refund.status_code, 200)

        db.session.refresh(payment)
        db.session.refresh(self.order)
        db.session.refresh(self.farmer)

        self.assertEqual(payment.status, 'refunded')
        self.assertEqual(self.order.payment_status, 'refunded')
        # 1000.00 - 4750.00 = -3750.00 (allowed negative balance)
        self.assertEqual(self.farmer.wallet_balance, Decimal('-3750.00'))

        # Verify reversal transaction
        reversal_tx = WalletTransaction.query.filter_by(order_id=self.order.id, type='reversal').first()
        self.assertIsNotNone(reversal_tx)
        self.assertEqual(reversal_tx.amount, Decimal('4750.00'))
        self.assertEqual(reversal_tx.balance_after, Decimal('-3750.00'))
        self.assertIn("Produce spoiled during transport", reversal_tx.description)

        # Verify audit log
        audit = AdminAuditLog.query.filter_by(action='refund_payment', target_id=payment.id).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.admin_id, self.admin.id)

    # ── 7. Order Cancellation & Rejection Guards on Paid Orders ──────────────
    def test_buyer_cannot_cancel_paid_order(self):
        """Buyer cannot cancel an order that has already been paid."""
        self.order.payment_status = 'paid'
        db.session.commit()

        self._login(self.buyer.email, "BuyerPass!2026")
        res = self.client.post(f"/orders/{self.order.id}/cancel", data={'reason': 'No longer needed'}, follow_redirects=True)

        db.session.refresh(self.order)
        self.assertNotEqual(self.order.status, 'cancelled')
        self.assertEqual(self.order.status, 'confirmed')
        self.assertIn(b"Cannot cancel an order that has already been paid", res.data)

    def test_farmer_cannot_reject_paid_order(self):
        """Farmer cannot reject an order that has already been paid."""
        self.order.payment_status = 'paid'
        db.session.commit()

        self._login(self.farmer.email, "FarmerPass!2026")
        res = self.client.post(f"/orders/{self.order.id}/update-status", data={'status': 'rejected'}, follow_redirects=True)

        db.session.refresh(self.order)
        self.assertNotEqual(self.order.status, 'rejected')
        self.assertEqual(self.order.status, 'confirmed')
        self.assertIn(b"Cannot reject an order that has already been paid", res.data)

    # ── 8. Official Receipt Access Control ───────────────────────────────────
    def test_receipt_access_control(self):
        """
        Receipt access:
        - Buyer owner, farmer seller, admin: 200 OK
        - Other buyer: 403 Forbidden
        - Guest: 302 login
        - Unpaid order: blocked
        """
        # A. Unpaid order -> blocked
        self.order.payment_status = 'unpaid'
        db.session.commit()
        self._login(self.buyer.email, "BuyerPass!2026")
        res_unpaid = self.client.get(f"/orders/{self.order.id}/receipt", follow_redirects=True)
        self.assertIn(b"paid orders", res_unpaid.data.lower())

        # Mark paid with mock payment record
        self.order.payment_status = 'paid'
        payment = Payment(
            order_id=self.order.id,
            amount=self.order.total_price,
            method='card',
            status='success',
            txn_ref='SP-RECEIPT1234',
            card_brand='Visa',
            card_last4='4242',
            expires_at=datetime.utcnow() + timedelta(minutes=15),
            completed_at=datetime.utcnow()
        )
        db.session.add(payment)
        db.session.commit()

        # B. Buyer owner -> 200 OK
        self._login(self.buyer.email, "BuyerPass!2026")
        res_buyer = self.client.get(f"/orders/{self.order.id}/receipt")
        self.assertEqual(res_buyer.status_code, 200)
        self.assertIn(b"INV-", res_buyer.data)
        self.assertIn(b"SIMULATED PAYMENT", res_buyer.data)
        self.assertIn(b"4,750.00", res_buyer.data)

        # C. Farmer seller -> 200 OK
        self._login(self.farmer.email, "FarmerPass!2026")
        res_farmer = self.client.get(f"/orders/{self.order.id}/receipt")
        self.assertEqual(res_farmer.status_code, 200)

        # D. Admin -> 200 OK
        self._login(self.admin.email, "AdminPass!2026")
        res_admin = self.client.get(f"/orders/{self.order.id}/receipt")
        self.assertEqual(res_admin.status_code, 200)

        # E. Other buyer -> 403 Forbidden
        self._login(self.other_buyer.email, "OtherPass!2026")
        res_other = self.client.get(f"/orders/{self.order.id}/receipt")
        self.assertEqual(res_other.status_code, 403)

        # F. Guest -> 302
        self.client.get('/auth/logout', follow_redirects=True)
        res_guest = self.client.get(f"/orders/{self.order.id}/receipt")
        self.assertEqual(res_guest.status_code, 302)

    # ── 9. Farmer Wallet Access Control ──────────────────────────────────────
    def test_wallet_access_control(self):
        """
        /wallet view is strictly for farmers:
        - Farmer: 200 OK with balance, ledger, and simulated notice
        - Buyer: 403 Forbidden
        - Guest: 302 login
        """
        # A. Farmer -> 200 OK
        self._login(self.farmer.email, "FarmerPass!2026")
        res_farmer = self.client.get("/wallet")
        self.assertEqual(res_farmer.status_code, 200)
        self.assertIn(b"Farmer Financial Ledger", res_farmer.data)
        self.assertIn(b"Balance is simulated", res_farmer.data)

        # B. Buyer -> 403 Forbidden
        self._login(self.buyer.email, "BuyerPass!2026")
        res_buyer = self.client.get("/wallet")
        self.assertEqual(res_buyer.status_code, 403)

        # C. Guest -> 302
        self.client.get('/auth/logout', follow_redirects=True)
        res_guest = self.client.get("/wallet")
        self.assertEqual(res_guest.status_code, 302)

    # ── 10. Admin Payments Access & CSV Safety ───────────────────────────────
    def test_admin_payments_access_and_csv_safety(self):
        """
        Admin payments registry:
        - Non-admin -> 403 Forbidden
        - Admin -> 200 OK
        - Admin CSV export -> UTF-8 BOM, sanitized formulas
        """
        # Create a payment with dangerous formula in card brand/failure reason
        payment = Payment(
            order_id=self.order.id,
            amount=Decimal('500.00'),
            method='card',
            status='failed',
            txn_ref='SP-INJECT9999',
            card_brand='=cmd|/c calc!A0',
            card_last4='1234',
            failure_reason='+@dangerous_formula',
            expires_at=datetime.utcnow() + timedelta(minutes=15)
        )
        db.session.add(payment)
        db.session.commit()

        # Non-admin -> 403
        self._login(self.buyer.email, "BuyerPass!2026")
        self.assertEqual(self.client.get("/admin/payments").status_code, 403)
        self.assertEqual(self.client.get("/admin/payments/export").status_code, 403)

        # Admin -> 200 OK
        self._login(self.admin.email, "AdminPass!2026")
        res_list = self.client.get("/admin/payments")
        self.assertEqual(res_list.status_code, 200)
        self.assertIn(b"Simulated Gateway Ledger", res_list.data)

        # Detail view -> 200 OK
        res_detail = self.client.get(f"/admin/payments/{payment.id}")
        self.assertEqual(res_detail.status_code, 200)

        # CSV Export -> UTF-8 BOM and formula sanitization
        res_csv = self.client.get("/admin/payments/export")
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, 'text/csv')
        self.assertIn('text/csv', res_csv.content_type)

        csv_content = res_csv.data.decode('utf-8')
        # Check UTF-8 BOM
        self.assertTrue(csv_content.startswith('\ufeff'))

        # Check sanitized formulas (leading apostrophe added)
        self.assertIn("'=cmd|/c calc!A0", csv_content)
        self.assertIn("'+@dangerous_formula", csv_content)

        # Check audit log written
        audit = AdminAuditLog.query.filter_by(action='export_payments_csv', admin_id=self.admin.id).order_by(AdminAuditLog.id.desc()).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.admin_id, self.admin.id)


if __name__ == '__main__':
    unittest.main()
