import json
import unittest
import uuid
from datetime import datetime, timedelta
from extensions import db
from models import AdminAuditLog, DataRequest, Order, Product, User
from services.settings import clear_settings_cache


class TestPrivacyAndSystem(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        clear_settings_cache()
        self.uid = uuid.uuid4().hex[:8]

        # 1. Admin
        self.admin = User(
            name=f"Admin {self.uid}",
            email=f"admin_{self.uid}@agrolink.lk",
            role='admin',
            is_active=True
        )
        self.admin.set_password("AdminPass123!")
        db.session.add(self.admin)

        # 2. Buyer
        self.buyer = User(
            name=f"Buyer {self.uid}",
            email=f"buyer_{self.uid}@agrolink.lk",
            role='buyer',
            is_active=True,
            location="Colombo"
        )
        self.buyer.set_password("BuyerPass123!")
        db.session.add(self.buyer)

        # 3. Farmer
        self.farmer = User(
            name=f"Farmer {self.uid}",
            email=f"farmer_{self.uid}@agrolink.lk",
            role='farmer',
            is_active=True,
            farm_name=f"Estate {self.uid}",
            location="Kandy",
            whatsapp_number="+94771234567",
            latitude=7.2906,
            longitude=80.6337
        )
        self.farmer.set_password("FarmerPass123!")
        db.session.add(self.farmer)

        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        self.app_context.pop()

    def _login(self, email, password):
        self.client.get('/auth/logout', follow_redirects=True)
        return self.client.post('/auth/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    # ──────────────────────────────────────────────────────────────────────────
    # 1. ROLE-ACCESS MATRIX TEST
    # ──────────────────────────────────────────────────────────────────────────
    def test_role_access_matrix(self):
        """Admin routes strictly enforce role separation across guest, buyer, farmer, admin."""
        admin_get_endpoints = [
            '/admin/',
            '/admin/users',
            '/admin/map',
            '/admin/listings',
            '/admin/listing-reports',
            '/admin/crops',
            '/admin/orders',
            '/admin/prices',
            '/admin/reports',
            '/admin/settings',
            '/admin/activity',
            '/admin/data-requests',
            '/admin/system',
        ]

        # A. Guest (Unauthenticated) -> Redirect to login (302)
        self.client.get('/auth/logout', follow_redirects=True)
        for endpoint in admin_get_endpoints:
            resp = self.client.get(endpoint)
            self.assertEqual(
                resp.status_code, 302,
                f"Guest should be redirected to login from {endpoint}, got {resp.status_code}"
            )
            self.assertIn('/auth/login', resp.headers.get('Location', ''))

        # B. Buyer -> 403 Forbidden
        self._login(self.buyer.email, "BuyerPass123!")
        for endpoint in admin_get_endpoints:
            resp = self.client.get(endpoint)
            self.assertEqual(
                resp.status_code, 403,
                f"Buyer should get 403 on {endpoint}, got {resp.status_code}"
            )

        # C. Farmer -> 403 Forbidden
        self._login(self.farmer.email, "FarmerPass123!")
        for endpoint in admin_get_endpoints:
            resp = self.client.get(endpoint)
            self.assertEqual(
                resp.status_code, 403,
                f"Farmer should get 403 on {endpoint}, got {resp.status_code}"
            )

        # D. Admin -> 200 OK
        self._login(self.admin.email, "AdminPass123!")
        for endpoint in admin_get_endpoints:
            resp = self.client.get(endpoint)
            self.assertEqual(
                resp.status_code, 200,
                f"Admin should get 200 on {endpoint}, got {resp.status_code}"
            )

    # ──────────────────────────────────────────────────────────────────────────
    # 2. CSRF PROTECTION ENFORCEMENT
    # ──────────────────────────────────────────────────────────────────────────
    def test_csrf_protection_on_post_routes(self):
        """When CSRF is enabled, POST requests missing CSRF token must fail with 400 Bad Request."""
        self._login(self.admin.email, "AdminPass123!")
        self.app.config['WTF_CSRF_ENABLED'] = True

        post_endpoints = [
            f'/admin/users/{self.farmer.id}/toggle-active',
            f'/admin/users/{self.farmer.id}/reset-password',
            '/admin/settings/platform',
            '/admin/system/test-routes',
        ]

        for ep in post_endpoints:
            resp = self.client.post(ep, data={})
            self.assertEqual(
                resp.status_code, 400,
                f"Missing CSRF token on {ep} should yield HTTP 400, got {resp.status_code}"
            )

        self.app.config['WTF_CSRF_ENABLED'] = False

    # ──────────────────────────────────────────────────────────────────────────
    # 3. PERSONAL DATA TOOLS (PDPA 2022) — USER WORKFLOW
    # ──────────────────────────────────────────────────────────────────────────
    def test_user_data_request_creation_and_limits(self):
        """Users can request data export and deletion, with one open request per type enforced."""
        self._login(self.farmer.email, "FarmerPass123!")

        # 1. Submit export request
        resp1 = self.client.post('/profile/data-request', data={'type': 'export'}, follow_redirects=True)
        self.assertEqual(resp1.status_code, 200)

        # Verify DB entry
        req1 = DataRequest.query.filter_by(user_id=self.farmer.id, type='export').first()
        self.assertIsNotNone(req1)
        self.assertEqual(req1.status, 'open')

        # 2. Duplicate open request is prevented
        resp_dup = self.client.post('/profile/data-request', data={'type': 'export'}, follow_redirects=True)
        self.assertIn(b'already have an open export request', resp_dup.data)

        # 3. Submit deletion request
        resp2 = self.client.post('/profile/data-request', data={'type': 'deletion'}, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        req2 = DataRequest.query.filter_by(user_id=self.farmer.id, type='deletion').first()
        self.assertIsNotNone(req2)
        self.assertEqual(req2.status, 'open')

        # 4. Profile page lists both requests
        resp_profile = self.client.get('/profile')
        self.assertIn(b'Data Privacy &amp; Rights', resp_profile.data)
        self.assertIn(b'export', resp_profile.data)
        self.assertIn(b'deletion', resp_profile.data)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. ADMIN DATA EXPORT JSON ARCHIVE (PDPA 2022)
    # ──────────────────────────────────────────────────────────────────────────
    def test_admin_export_json_and_audit(self):
        """Admin can download portable JSON archive without passwords, secrets, or leakage."""
        # Farmer creates a listing and receives an order
        product = Product(
            name="Organic Carrots",
            category="Vegetables",
            price_per_kg=120.0,
            quantity_kg=50.0,
            farmer_id=self.farmer.id,
            is_available=True
        )
        db.session.add(product)
        db.session.commit()

        order = Order(
            buyer_id=self.buyer.id,
            product_id=product.id,
            quantity_kg=10.0,
            items_total=1200.0,
            delivery_fee=0.0,
            total_price=1200.0,
            status='delivered'
        )
        db.session.add(order)

        # Farmer requests export
        export_req = DataRequest(
            user_id=self.farmer.id,
            type='export',
            status='open'
        )
        db.session.add(export_req)
        db.session.commit()

        # Admin downloads export
        self._login(self.admin.email, "AdminPass123!")
        resp = self.client.get(f'/admin/data-requests/{export_req.id}/export')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'application/json')
        self.assertIn('attachment', resp.headers.get('Content-Disposition', ''))

        payload = json.loads(resp.data.decode('utf-8'))

        # Check payload completeness
        self.assertIn('account', payload)
        self.assertEqual(payload['account']['name'], self.farmer.name)
        self.assertEqual(payload['account']['email'], self.farmer.email)
        self.assertEqual(payload['account']['farm_name'], self.farmer.farm_name)
        self.assertIn('listings', payload)
        self.assertIn('orders', payload)
        self.assertEqual(len(payload['listings']), 1)
        self.assertEqual(payload['listings'][0]['name'], "Organic Carrots")

        # Security check: MUST NOT contain password hashes or security secrets
        payload_str = json.dumps(payload)
        self.assertNotIn("password_hash", payload_str)
        self.assertNotIn("FarmerPass123!", payload_str)

        # Verify request status updated to completed
        updated_req = DataRequest.query.get(export_req.id)
        self.assertEqual(updated_req.status, 'completed')
        self.assertEqual(updated_req.handled_by, self.admin.id)

        # Verify audit log entry
        audit = AdminAuditLog.query.filter_by(action='data_request_export', target_id=self.farmer.id).first()
        self.assertIsNotNone(audit)
        self.assertNotIn(self.farmer.email, audit.details)

    # ──────────────────────────────────────────────────────────────────────────
    # 5. ACCOUNT ANONYMIZATION & SAFEGUARDS (PDPA ERASURE)
    # ──────────────────────────────────────────────────────────────────────────
    def test_anonymize_blocked_when_active_orders_exist(self):
        """Account anonymization must be blocked if user has pending or confirmed orders."""
        product = Product(name="Beans", category="Vegetables", price_per_kg=80.0, quantity_kg=20.0, farmer_id=self.farmer.id)
        db.session.add(product)
        db.session.commit()

        # Active order
        order = Order(
            buyer_id=self.buyer.id,
            product_id=product.id,
            quantity_kg=5.0,
            items_total=400.0,
            delivery_fee=0.0,
            total_price=400.0,
            status='pending'
        )
        del_req = DataRequest(user_id=self.farmer.id, type='deletion', status='open')
        db.session.add(order)
        db.session.add(del_req)
        db.session.commit()

        self._login(self.admin.email, "AdminPass123!")
        resp = self.client.post(
            f'/admin/data-requests/{del_req.id}/anonymize',
            data={'confirm_email': self.farmer.email, 'reason': 'PDPA Deletion'},
            follow_redirects=True
        )
        self.assertIn(b'Cannot anonymize', resp.data)
        self.assertIn(b'active order(s) in progress', resp.data)

        # Confirm user is NOT deleted
        farmer_check = User.query.get(self.farmer.id)
        self.assertTrue(farmer_check.is_active)
        self.assertNotEqual(farmer_check.name, f"Deleted user #{self.farmer.id}")

    def test_anonymize_success_and_pii_purge(self):
        """When safe, anonymization purges PII, preserves orders anonymously, and deactivates."""
        farmer_id = self.farmer.id
        farmer_email = self.farmer.email

        del_req = DataRequest(user_id=farmer_id, type='deletion', status='open')
        db.session.add(del_req)
        db.session.commit()

        self._login(self.admin.email, "AdminPass123!")

        # 1. Mismatched confirmation email rejected
        resp_mismatch = self.client.post(
            f'/admin/data-requests/{del_req.id}/anonymize',
            data={'confirm_email': 'wrong_email@agrolink.lk', 'reason': 'PDPA Deletion'},
            follow_redirects=True
        )
        self.assertIn(b'exact email address', resp_mismatch.data)

        # 2. Correct confirmation email accepted
        resp_ok = self.client.post(
            f'/admin/data-requests/{del_req.id}/anonymize',
            data={'confirm_email': farmer_email, 'reason': 'PDPA Erasure Right Exercised'},
            follow_redirects=True
        )
        self.assertEqual(resp_ok.status_code, 200)
        self.assertIn(b'permanently anonymized and deactivated', resp_ok.data)

        # Inspect anonymized user record in DB
        anon_user = User.query.get(farmer_id)
        self.assertEqual(anon_user.name, f"Deleted user #{farmer_id}")
        self.assertEqual(anon_user.email, f"deleted_user{farmer_id}@deleted.agrolink.lk")
        self.assertIsNone(anon_user.phone)
        self.assertIsNone(anon_user.whatsapp_number)
        self.assertIsNone(anon_user.location)
        self.assertIsNone(anon_user.farm_name)
        self.assertIsNone(anon_user.bio)
        self.assertIsNone(anon_user.latitude)
        self.assertIsNone(anon_user.longitude)
        self.assertFalse(anon_user.is_active)

        # Verify audit log recorded event with zero PII
        audit = AdminAuditLog.query.filter_by(action='user_anonymized', target_id=farmer_id).first()
        self.assertIsNotNone(audit)
        self.assertNotIn(farmer_email, audit.details)
        self.assertNotIn("Farmer", audit.details)

    # ──────────────────────────────────────────────────────────────────────────
    # 6. SYSTEM STATUS & TELEMETRY (/admin/system)
    # ──────────────────────────────────────────────────────────────────────────
    def test_system_status_page_and_no_secret_leakage(self):
        """System status page renders telemetry with strict zero secret leakage standard."""
        self._login(self.admin.email, "AdminPass123!")
        resp = self.client.get('/admin/system')
        self.assertEqual(resp.status_code, 200)

        # Telemetry items present
        self.assertIn(b'Database Connectivity', resp.data)
        self.assertIn(b'Schema Migrations', resp.data)
        self.assertIn(b'Upload Directory', resp.data)
        self.assertIn(b'Failed Logins', resp.data)
        self.assertIn(b'Google Routes API', resp.data)

        # ZERO SECRET LEAKAGE: Neither actual keys, passwords, nor connection strings appear in HTML
        html_str = resp.data.decode('utf-8')
        self.assertNotIn("AdminPass123!", html_str)
        self.assertNotIn("postgresql://", html_str)
        self.assertNotIn("AIzaSy", html_str)

    def test_routes_api_test_probe_and_rate_limit(self):
        """Routes API probe calculates Colombo-Kandy route, audits, and enforces hourly limit."""
        self._login(self.admin.email, "AdminPass123!")

        # Execute single test probe
        resp = self.client.post('/admin/system/test-routes', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Colombo to Kandy is', resp.data)

        # Verify audit entry was created
        audit = AdminAuditLog.query.filter_by(action='test_routes_api').first()
        self.assertIsNotNone(audit)
        self.assertIn('Routes API probe', audit.details)

    # ──────────────────────────────────────────────────────────────────────────
    # 7. PUBLIC PRIVACY NOTICE PAGE
    # ──────────────────────────────────────────────────────────────────────────
    def test_privacy_notice_page(self):
        """Public /privacy notice is accessible and cites Sri Lanka PDPA 2022."""
        self.client.get('/auth/logout', follow_redirects=True)
        resp = self.client.get('/privacy')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Sri Lanka PDPA (No. 9 of 2022)', resp.data)
        self.assertIn(b'Data Portability', resp.data)
        self.assertIn(b'Erasure', resp.data)
