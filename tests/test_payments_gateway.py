import io
import time
import unittest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from app import create_app
from extensions import db
from models import Order, Payment, Product, User, WalletTransaction
from services.gateway_security import canonical_json, sign_payload, verify_signature
from services.payments import (
    create_payment_session,
    generate_txn_ref,
    handle_gateway_result,
)
from blueprints.gateway.routes import detect_card_brand, validate_expiry, validate_luhn


class TestGatewaySecurity(unittest.TestCase):
    """Test HMAC-SHA256 signing, canonical JSON, and replay protection."""

    def setUp(self):
        self.secret = "test-secret-key-abcdef123456"
        self.payload = {
            'txn_ref': 'SP-TEST12345678',
            'order_id': 42,
            'amount': '2500.00',
            'status': 'success',
            'timestamp': int(time.time()),
        }

    def test_canonical_json_sorting(self):
        """Canonical JSON guarantees sorted keys and compact delimiters."""
        d1 = {'b': 2, 'a': 1, 'c': {'y': 2, 'x': 1}}
        d2 = {'c': {'x': 1, 'y': 2}, 'a': 1, 'b': 2}
        self.assertEqual(canonical_json(d1), canonical_json(d2))
        self.assertIn('"a":1', canonical_json(d1))

    def test_signature_valid(self):
        """Valid HMAC-SHA256 signature passes verification."""
        sig = sign_payload(self.payload, secret=self.secret)
        self.assertTrue(verify_signature(self.payload, sig, secret=self.secret))

    def test_signature_invalid(self):
        """Corrupted signature string is rejected."""
        sig = sign_payload(self.payload, secret=self.secret)
        bad_sig = sig[:-4] + "0000"
        self.assertFalse(verify_signature(self.payload, bad_sig, secret=self.secret))

    def test_signature_tampered_payload(self):
        """Tampering with any payload attribute invalidates the signature."""
        sig = sign_payload(self.payload, secret=self.secret)
        tampered = dict(self.payload)
        tampered['amount'] = '100.00'
        self.assertFalse(verify_signature(tampered, sig, secret=self.secret))

        tampered_status = dict(self.payload)
        tampered_status['status'] = 'failed'
        self.assertFalse(verify_signature(tampered_status, sig, secret=self.secret))

    def test_signature_expired_timestamp_rejected(self):
        """Payloads older than 10 minutes (600 seconds) are rejected for replay protection."""
        old_payload = dict(self.payload)
        old_payload['timestamp'] = int(time.time()) - 605  # > 10 mins
        sig = sign_payload(old_payload, secret=self.secret)
        self.assertFalse(verify_signature(old_payload, sig, secret=self.secret, max_age_seconds=600))

    def test_signature_future_timestamp_rejected(self):
        """Timestamps unreasonably far in the future (> 60s) are rejected."""
        future_payload = dict(self.payload)
        future_payload['timestamp'] = int(time.time()) + 120
        sig = sign_payload(future_payload, secret=self.secret)
        self.assertFalse(verify_signature(future_payload, sig, secret=self.secret))

    def test_signature_missing_or_invalid_timestamp(self):
        """Missing or malformed timestamp fails verification immediately."""
        p_no_ts = dict(self.payload)
        del p_no_ts['timestamp']
        self.assertFalse(verify_signature(p_no_ts, "somesig", secret=self.secret))

        p_bad_ts = dict(self.payload)
        p_bad_ts['timestamp'] = 'not-a-timestamp'
        self.assertFalse(verify_signature(p_bad_ts, "somesig", secret=self.secret))


class TestCardValidationHelpers(unittest.TestCase):
    """Test card number Luhn algorithm, expiry parsing, and brand detection."""

    def test_luhn_validation(self):
        """Valid test cards pass Luhn; invalid checksums fail."""
        self.assertTrue(validate_luhn('4242424242424242'))
        self.assertTrue(validate_luhn('4000000000000002'))
        self.assertTrue(validate_luhn('4000000000009995'))

        # Checksum failure (last digit changed)
        self.assertFalse(validate_luhn('4242424242424243'))
        self.assertFalse(validate_luhn('12345'))
        self.assertFalse(validate_luhn('abcdef'))

    def test_expiry_validation(self):
        """Validate MM/YY format and future dates."""
        valid, err = validate_expiry('12/28')
        self.assertTrue(valid)
        self.assertIsNone(err)

        valid, err = validate_expiry('12/2028')
        self.assertTrue(valid)
        self.assertIsNone(err)

        # Past expiry
        valid, err = validate_expiry('01/20')
        self.assertFalse(valid)
        self.assertIn('expired', err.lower())

        # Invalid month
        valid, err = validate_expiry('13/28')
        self.assertFalse(valid)
        self.assertIn('month', err.lower())

        # Malformed
        valid, err = validate_expiry('invalid')
        self.assertFalse(valid)

    def test_brand_detection(self):
        """Verify card brand detection without saving full PAN."""
        self.assertEqual(detect_card_brand('4242424242424242'), 'Visa')
        self.assertEqual(detect_card_brand('5105105105105100'), 'Mastercard')
        self.assertEqual(detect_card_brand('378282246310005'), 'American Express')


class TestPaymentsGatewayIntegration(unittest.TestCase):
    """Integration test suite for payment models, SimPay checkout, and webhooks."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['PAYMENT_GATEWAY_SECRET'] = 'unit-test-gateway-secret-2026'
        self.app.config['MAX_PAYMENT_ATTEMPTS_PER_ORDER'] = 5
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.uid = uuid.uuid4().hex[:8]

        # Seed Farmer
        self.farmer = User(
            name=f"Farmer {self.uid}",
            email=f"farmer_{self.uid}@agrolink.lk",
            role="farmer",
            phone="0771000001",
            whatsapp_number="+94771000001",
            location="Dambulla",
            is_active=True,
            session_version=1
        )
        self.farmer.set_password("FarmerPass!2026")

        # Seed Buyer 1 (Order owner)
        self.buyer = User(
            name=f"Buyer {self.uid}",
            email=f"buyer_{self.uid}@agrolink.lk",
            role="buyer",
            phone="0771000002",
            whatsapp_number="+94771000002",
            location="Colombo",
            is_active=True,
            session_version=1
        )
        self.buyer.set_password("BuyerPass!2026")

        # Seed Buyer 2 (Non-owner)
        self.other_buyer = User(
            name=f"Other Buyer {self.uid}",
            email=f"other_{self.uid}@agrolink.lk",
            role="buyer",
            phone="0771000003",
            whatsapp_number="+94771000003",
            location="Kandy",
            is_active=True,
            session_version=1
        )
        self.other_buyer.set_password("OtherPass!2026")

        db.session.add_all([self.farmer, self.buyer, self.other_buyer])
        db.session.commit()

        # Seed Product
        self.product = Product(
            farmer_id=self.farmer.id,
            name=f"Carrots {self.uid}",
            category="Vegetables",
            description="Nuwara Eliya Fresh",
            price_per_kg=350.00,
            quantity_kg=50.0,
            is_available=True
        )
        db.session.add(self.product)
        db.session.commit()

        # Seed Order
        self.order = Order(
            buyer_id=self.buyer.id,
            product_id=self.product.id,
            quantity_kg=10.0,
            total_price=Decimal('3500.00'),
            status='pending',
            payment_status='unpaid',
            fulfillment_type='pickup'
        )
        db.session.add(self.order)
        db.session.commit()

    def tearDown(self):
        WalletTransaction.query.filter(WalletTransaction.user_id.in_([self.farmer.id, self.buyer.id, self.other_buyer.id])).delete()
        Payment.query.filter(Payment.order_id == self.order.id).delete()
        Order.query.filter(Order.id == self.order.id).delete()
        Product.query.filter(Product.id == self.product.id).delete()
        User.query.filter(User.id.in_([self.farmer.id, self.buyer.id, self.other_buyer.id])).delete()
        db.session.commit()
        db.session.remove()
        self.ctx.pop()

    def _login(self, email, password):
        self.client.get('/auth/logout', follow_redirects=True)
        return self.client.post('/auth/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    # ── 1. Session Creation & Ownership ─────────────────────────────────────
    def test_create_payment_session_success(self):
        """Create a payment session for an order, verifying 'initiated' status and 15-minute expiry."""
        payment, err = create_payment_session(self.order.id, self.buyer.id)
        self.assertIsNone(err)
        self.assertIsNotNone(payment)
        self.assertTrue(payment.txn_ref.startswith('SP-'))
        self.assertEqual(payment.status, 'initiated')
        self.assertEqual(payment.amount, Decimal('3500.00'))
        self.assertGreater(payment.expires_at, datetime.utcnow())

    def test_create_payment_session_wrong_user_blocked(self):
        """Non-owner buyer cannot create a payment session for someone else's order."""
        payment, err = create_payment_session(self.order.id, self.other_buyer.id)
        self.assertIsNone(payment)
        self.assertIn("permission", err.lower())

    def test_create_payment_session_cancelled_order_blocked(self):
        """Cannot create payment session for cancelled order."""
        self.order.status = 'cancelled'
        db.session.commit()
        payment, err = create_payment_session(self.order.id, self.buyer.id)
        self.assertIsNone(payment)
        self.assertIn("cancelled", err.lower())

    def test_session_ownership_checkout_access(self):
        """Buyer owner can view checkout; other buyers, farmers, and guests are blocked."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)

        # 1. Guest -> redirected to login
        res = self.client.get(f"/gateway/checkout/{payment.txn_ref}")
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.headers.get('Location', ''))

        # 2. Other Buyer -> 403 Forbidden
        self._login(self.other_buyer.email, "OtherPass!2026")
        res = self.client.get(f"/gateway/checkout/{payment.txn_ref}")
        self.assertEqual(res.status_code, 403)

        # 3. Farmer -> 403 Forbidden
        self._login(self.farmer.email, "FarmerPass!2026")
        res = self.client.get(f"/gateway/checkout/{payment.txn_ref}")
        self.assertEqual(res.status_code, 403)

        # 4. Buyer Owner -> 200 OK
        self._login(self.buyer.email, "BuyerPass!2026")
        res = self.client.get(f"/gateway/checkout/{payment.txn_ref}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"SIMULATED PAYMENT, NO REAL MONEY", res.data)
        self.assertIn(b"SimPay", res.data)
        self.assertIn(b"AgroLink", res.data)
        self.assertIn(b"3,500.00", res.data)

    # ── 2. Test Cards & Checkout Processing ─────────────────────────────────
    def test_checkout_test_card_success(self):
        """Test card 4242 4242 4242 4242 succeeds and sets status to 'success'."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        self._login(self.buyer.email, "BuyerPass!2026")

        res = self.client.post(f"/gateway/checkout/{payment.txn_ref}", data={
            'cardholder_name': 'Bandara Jayasuriya',
            'card_number': '4242 4242 4242 4242',
            'expiry': '12/28',
            'cvv': '123'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        # Check DB payment status
        db.session.refresh(payment)
        self.assertEqual(payment.status, 'success')
        self.assertEqual(payment.card_last4, '4242')
        self.assertEqual(payment.card_brand, 'Visa')
        self.assertIsNone(payment.failure_reason)
        self.assertIsNotNone(payment.completed_at)
        self.assertIn(b"Payment Successful", res.data)

    def test_checkout_test_card_declined(self):
        """Test card 4000 0000 0000 0002 is declined with correct failure reason."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        self._login(self.buyer.email, "BuyerPass!2026")

        res = self.client.post(f"/gateway/checkout/{payment.txn_ref}", data={
            'cardholder_name': 'Sunil Perera',
            'card_number': '4000 0000 0000 0002',
            'expiry': '12/28',
            'cvv': '123'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        db.session.refresh(payment)
        self.assertEqual(payment.status, 'failed')
        self.assertEqual(payment.failure_reason, 'Card declined by issuing bank')
        self.assertEqual(payment.card_last4, '0002')
        self.assertIn(b"Payment Failed", res.data)

    def test_checkout_test_card_insufficient_funds(self):
        """Test card 4000 0000 0000 9995 fails with insufficient funds."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        self._login(self.buyer.email, "BuyerPass!2026")

        res = self.client.post(f"/gateway/checkout/{payment.txn_ref}", data={
            'cardholder_name': 'Nimal Silva',
            'card_number': '4000 0000 0000 9995',
            'expiry': '12/28',
            'cvv': '123'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        db.session.refresh(payment)
        self.assertEqual(payment.status, 'failed')
        self.assertEqual(payment.failure_reason, 'Insufficient funds in account')
        self.assertEqual(payment.card_last4, '9995')

    def test_checkout_other_card_rejected(self):
        """Any other card number is rejected with 'Card not accepted (use a test card)'."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        self._login(self.buyer.email, "BuyerPass!2026")

        # 4111111111111111 is a valid Luhn Visa card but not one of the allowed test cards
        res = self.client.post(f"/gateway/checkout/{payment.txn_ref}", data={
            'cardholder_name': 'Random Cardholder',
            'card_number': '4111 1111 1111 1111',
            'expiry': '12/28',
            'cvv': '123'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        db.session.refresh(payment)
        self.assertEqual(payment.status, 'failed')
        self.assertEqual(payment.failure_reason, 'Card not accepted (use a test card)')

    def test_checkout_invalid_luhn_rejected(self):
        """Card number failing Luhn checksum is rejected on submit with a 400 error."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        self._login(self.buyer.email, "BuyerPass!2026")

        res = self.client.post(f"/gateway/checkout/{payment.txn_ref}", data={
            'cardholder_name': 'Test User',
            'card_number': '4242 4242 4242 4243',  # Bad checksum
            'expiry': '12/28',
            'cvv': '123'
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"Checksum validation failed", res.data)

    def test_checkout_expired_card_rejected(self):
        """Card with past expiry date is rejected with a 400 error."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        self._login(self.buyer.email, "BuyerPass!2026")

        res = self.client.post(f"/gateway/checkout/{payment.txn_ref}", data={
            'cardholder_name': 'Test User',
            'card_number': '4242 4242 4242 4242',
            'expiry': '01/20',  # Expired
            'cvv': '123'
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn(b"expired", res.data.lower())

    # ── 3. Expired & Completed Session Handling ──────────────────────────────
    def test_checkout_expired_session(self):
        """Expired session renders friendly expired screen and prevents payment submission."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        payment.expires_at = datetime.utcnow() - timedelta(minutes=5)
        db.session.commit()

        self._login(self.buyer.email, "BuyerPass!2026")

        # GET shows friendly expired page
        res = self.client.get(f"/gateway/checkout/{payment.txn_ref}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Payment Session Expired", res.data)

        # POST also blocks and renders expired status
        res_post = self.client.post(f"/gateway/checkout/{payment.txn_ref}", data={
            'cardholder_name': 'Test User',
            'card_number': '4242 4242 4242 4242',
            'expiry': '12/28',
            'cvv': '123'
        })
        self.assertIn(b"Payment Session Expired", res_post.data)

    def test_checkout_completed_session(self):
        """Completed session renders friendly already-finalized screen."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        payment.status = 'success'
        db.session.commit()

        self._login(self.buyer.email, "BuyerPass!2026")
        res = self.client.get(f"/gateway/checkout/{payment.txn_ref}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Payment Already Finalized", res.data)

    # ── 4. Card Data Protection (No PAN / CVV in Database) ───────────────────
    def test_no_card_data_in_database(self):
        """CRITICAL PRIVACY: PAN and CVV are never stored in database columns."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        self._login(self.buyer.email, "BuyerPass!2026")

        self.client.post(f"/gateway/checkout/{payment.txn_ref}", data={
            'cardholder_name': 'Bandara Jayasuriya',
            'card_number': '4242 4242 4242 4242',
            'expiry': '12/28',
            'cvv': '987'
        })

        db.session.refresh(payment)
        # Verify card_last4 is exactly 4 digits
        self.assertEqual(payment.card_last4, '4242')

        # Verify that payment table columns do NOT contain full PAN or CVV fields
        payment_cols = [c.name for c in Payment.__table__.columns]
        self.assertNotIn('pan', payment_cols)
        self.assertNotIn('card_number', payment_cols)
        self.assertNotIn('cvv', payment_cols)
        self.assertNotIn('security_code', payment_cols)

    # ── 5. Service Idempotency ───────────────────────────────────────────────
    def test_handle_gateway_result_idempotency(self):
        """Delivering the same txn_ref twice never changes status or creates duplicate records."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        payload = {
            'txn_ref': payment.txn_ref,
            'order_id': payment.order_id,
            'amount': str(payment.amount),
            'status': 'success',
            'failure_reason': None,
            'card_brand': 'Visa',
            'card_last4': '4242',
            'timestamp': int(time.time()),
        }
        sig = sign_payload(payload)

        # First call -> success
        res1 = handle_gateway_result(payload, sig)
        self.assertTrue(res1['success'])
        self.assertFalse(res1['already_processed'])
        self.assertEqual(res1['status'], 'success')

        # Second call -> idempotent return with already_processed: True
        res2 = handle_gateway_result(payload, sig)
        self.assertTrue(res2['success'])
        self.assertTrue(res2['already_processed'])
        self.assertEqual(res2['status'], 'success')

    # ── 6. Webhook Signature Security ────────────────────────────────────────
    def test_webhook_valid_signature(self):
        """POST /payments/webhook with valid HMAC-SHA256 signature succeeds (200 OK)."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        payload = {
            'txn_ref': payment.txn_ref,
            'order_id': payment.order_id,
            'amount': str(payment.amount),
            'status': 'success',
            'failure_reason': None,
            'card_brand': 'Visa',
            'card_last4': '4242',
            'timestamp': int(time.time()),
        }
        sig = sign_payload(payload)

        res = self.client.post(
            '/payments/webhook',
            json={'payload': payload, 'signature': sig},
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'received')
        self.assertEqual(data['payment_status'], 'success')

    def test_webhook_rejects_bad_signature(self):
        """POST /payments/webhook with bad signature returns 400 Bad Request."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        payload = {
            'txn_ref': payment.txn_ref,
            'order_id': payment.order_id,
            'amount': str(payment.amount),
            'status': 'success',
            'timestamp': int(time.time()),
        }
        bad_sig = "bad_signature_hex_value"

        res = self.client.post(
            '/payments/webhook',
            json={'payload': payload, 'signature': bad_sig},
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 400)

    # ── 7. Result Page Reads Status From Database Only ──────────────────────
    def test_result_page_reads_database_only(self):
        """Result page ignores URL spoofing and only trusts the database status."""
        payment, _ = create_payment_session(self.order.id, self.buyer.id)
        payment.status = 'failed'
        payment.failure_reason = 'Card declined by issuing bank'
        db.session.commit()

        self._login(self.buyer.email, "BuyerPass!2026")
        # Attempt to spoof success in the URL
        res = self.client.get(f"/orders/payment-result/{payment.txn_ref}?status=success")
        self.assertEqual(res.status_code, 200)
        # Must show Failed based on DB, not Success based on URL
        self.assertIn(b"Payment Failed", res.data)
        self.assertNotIn(b"Payment Successful", res.data)


if __name__ == '__main__':
    unittest.main()
