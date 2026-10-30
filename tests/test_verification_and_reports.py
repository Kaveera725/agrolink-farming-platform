import io
import unittest
import uuid
from datetime import datetime, timedelta
from app import create_app
from extensions import db
from models import AdminAuditLog, AdminNote, Crop, ListingReport, MarketPrice, Order, Product, User, VerificationRequest


class TestVerificationAndReports(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.uid = uuid.uuid4().hex[:8]

        # Admin user
        self.admin = User(
            name=f"Admin {self.uid}",
            email=f"admin_{self.uid}@agrolink.lk",
            role="admin",
            phone="0771112222",
            whatsapp_number="+94771112222",
            is_active=True,
            must_change_password=False,
            session_version=1
        )
        self.admin.set_password("AdminStrongPass!2026")

        # Farmer user
        self.farmer = User(
            name=f"Farmer {self.uid}",
            email=f"farmer_{self.uid}@agrolink.lk",
            role="farmer",
            phone="0773334444",
            whatsapp_number="+94773334444",
            location="Nuwara Eliya",
            farm_name="Green Valley Farms",
            bio="Organic vegetable grower since 2018.",
            is_active=True,
            is_verified=False,
            must_change_password=False,
            session_version=1
        )
        self.farmer.set_password("FarmerPass!2026")

        # Buyer 1
        self.buyer1 = User(
            name=f"Buyer One {self.uid}",
            email=f"buyer1_{self.uid}@agrolink.lk",
            role="buyer",
            phone="0775556666",
            whatsapp_number="+94775556666",
            location="Colombo",
            is_active=True,
            must_change_password=False,
            session_version=1
        )
        self.buyer1.set_password("Buyer1Pass!2026")

        # Buyer 2
        self.buyer2 = User(
            name=f"Buyer Two {self.uid}",
            email=f"buyer2_{self.uid}@agrolink.lk",
            role="buyer",
            phone="0777778888",
            whatsapp_number="+94777778888",
            location="Gampaha",
            is_active=True,
            must_change_password=False,
            session_version=1
        )
        self.buyer2.set_password("Buyer2Pass!2026")

        # Buyer 3
        self.buyer3 = User(
            name=f"Buyer Three {self.uid}",
            email=f"buyer3_{self.uid}@agrolink.lk",
            role="buyer",
            phone="0779990000",
            whatsapp_number="+94779990000",
            location="Kandy",
            is_active=True,
            must_change_password=False,
            session_version=1
        )
        self.buyer3.set_password("Buyer3Pass!2026")

        db.session.add_all([self.admin, self.farmer, self.buyer1, self.buyer2, self.buyer3])
        db.session.commit()

        # Seed a test product
        self.product = Product(
            farmer_id=self.farmer.id,
            name=f"Fresh Organic Carrots {self.uid}",
            category="Vegetables",
            description="Crisp organic carrots harvested daily.",
            quantity_kg=100.0,
            price_per_kg=220.0,
            location="Nuwara Eliya",
            is_available=True,
            is_deleted=False
        )
        db.session.add(self.product)
        db.session.commit()

    def tearDown(self):
        ListingReport.query.filter(ListingReport.product_id == self.product.id).delete()
        VerificationRequest.query.filter(VerificationRequest.farmer_id == self.farmer.id).delete()
        AdminNote.query.filter(AdminNote.admin_id == self.admin.id).delete()
        AdminNote.query.filter(AdminNote.user_id.in_([self.admin.id, self.farmer.id, self.buyer1.id, self.buyer2.id, self.buyer3.id])).delete()
        Order.query.filter(Order.product_id == self.product.id).delete()
        Crop.query.filter(Crop.farmer_id == self.farmer.id).delete()
        Product.query.filter(Product.id == self.product.id).delete()
        db.session.commit()
        self.ctx.pop()

    def _login(self, email, password):
        self.client.get('/auth/logout', follow_redirects=True)
        return self.client.post('/auth/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    def test_verification_request_lifecycle(self):
        """Farmer can request verification, admin approves, and admin can revoke."""
        # 1. Farmer requests verification
        self._login(self.farmer.email, "FarmerPass!2026")
        res = self.client.post('/profile/request-verification', data={
            'farmer_note': 'Registered grower with 3 acres in Nuwara Eliya.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        req = VerificationRequest.query.filter_by(farmer_id=self.farmer.id).first()
        self.assertIsNotNone(req)
        self.assertEqual(req.status, 'pending')
        self.assertIn('Registered grower', req.farmer_note)

        # 2. Admin inspects verifications queue
        self._login(self.admin.email, "AdminStrongPass!2026")
        queue_res = self.client.get('/admin/verifications')
        self.assertEqual(queue_res.status_code, 200)
        self.assertIn(self.farmer.name, queue_res.get_data(as_text=True))

        # 3. Admin approves verification
        approve_res = self.client.post(f'/admin/verifications/{req.id}/approve', follow_redirects=True)
        self.assertEqual(approve_res.status_code, 200)

        # Verify DB state
        db.session.refresh(req)
        db.session.refresh(self.farmer)
        self.assertEqual(req.status, 'approved')
        self.assertTrue(self.farmer.is_verified)
        self.assertIsNotNone(self.farmer.verified_at)
        self.assertEqual(self.farmer.verified_by, self.admin.id)

        # 4. Admin revokes verification
        revoke_res = self.client.post(f'/admin/users/{self.farmer.id}/revoke-verification', data={
            'reason': 'Audit review failed'
        }, follow_redirects=True)
        self.assertEqual(revoke_res.status_code, 200)

        db.session.refresh(self.farmer)
        self.assertFalse(self.farmer.is_verified)

    def test_badge_shown_only_when_verified(self):
        """Verified badge appears on product detail and cards only when is_verified=True."""
        # Unverified farmer
        self.farmer.is_verified = False
        db.session.commit()

        res_unverified = self.client.get(f'/marketplace/{self.product.id}')
        html_unverified = res_unverified.get_data(as_text=True)
        self.assertNotIn('Verified AgroLink Farmer Partner', html_unverified)
        self.assertNotIn('<span>Verified</span>', html_unverified)

        # Verify farmer
        self.farmer.is_verified = True
        self.farmer.verified_at = datetime.utcnow()
        db.session.commit()

        res_verified = self.client.get(f'/marketplace/{self.product.id}')
        html_verified = res_verified.get_data(as_text=True)
        self.assertIn('Verified', html_verified)

    def test_duplicate_open_requests_blocked(self):
        """Farmer cannot submit a second verification request while one is pending."""
        self._login(self.farmer.email, "FarmerPass!2026")

        # First request
        res1 = self.client.post('/profile/request-verification', data={'farmer_note': 'First attempt'}, follow_redirects=True)
        self.assertEqual(res1.status_code, 200)

        # Second request while pending
        res2 = self.client.post('/profile/request-verification', data={'farmer_note': 'Duplicate attempt'}, follow_redirects=True)
        self.assertEqual(res2.status_code, 200)
        self.assertIn('already have a pending verification request', res2.get_data(as_text=True).lower())

        count = VerificationRequest.query.filter_by(farmer_id=self.farmer.id, status='pending').count()
        self.assertEqual(count, 1)

    def test_report_rules_own_listing_duplicates_rate_limit(self):
        """Farmer cannot report own listing; duplicate reports blocked; rate limiting enforces ~5/hr."""
        # 1. Farmer cannot report own listing
        self._login(self.farmer.email, "FarmerPass!2026")
        res_own = self.client.post(f'/marketplace/{self.product.id}/report', data={
            'reason': 'spam',
            'details': 'Trying to report my own crop'
        }, follow_redirects=True)
        self.assertIn('cannot report your own listing', res_own.get_data(as_text=True).lower())

        # 2. Buyer submits valid report
        self._login(self.buyer1.email, "Buyer1Pass!2026")
        res_report = self.client.post(f'/marketplace/{self.product.id}/report', data={
            'reason': 'misleading_price',
            'details': 'Listed price does not match market rate.'
        }, follow_redirects=True)
        self.assertEqual(res_report.status_code, 200)

        report = ListingReport.query.filter_by(product_id=self.product.id, reporter_id=self.buyer1.id).first()
        self.assertIsNotNone(report)
        self.assertEqual(report.status, 'open')

        # 3. Duplicate open report blocked
        res_dup = self.client.post(f'/marketplace/{self.product.id}/report', data={
            'reason': 'wrong_or_fake_photo',
            'details': 'Another report on same listing'
        }, follow_redirects=True)
        self.assertIn('already have an open report', res_dup.get_data(as_text=True).lower())

        # 4. Rate limit: seed 4 more reports in the last hour for buyer1 on other dummy products
        extra_products = []
        for i in range(4):
            p = Product(
                farmer_id=self.farmer.id,
                name=f"Extra Crop {i} {self.uid}",
                category="Vegetables",
                quantity_kg=50.0,
                price_per_kg=100.0,
                is_available=True,
                is_deleted=False
            )
            db.session.add(p)
            extra_products.append(p)
        db.session.commit()

        for p in extra_products:
            r = ListingReport(
                product_id=p.id,
                reporter_id=self.buyer1.id,
                reason='spam',
                status='open',
                created_at=datetime.utcnow()
            )
            db.session.add(r)
        db.session.commit()

        # Buyer1 now has 5 reports in the last hour. A 6th attempt must be rejected.
        target_prod = Product(
            farmer_id=self.farmer.id,
            name=f"Target 6th {self.uid}",
            category="Fruits",
            quantity_kg=20.0,
            price_per_kg=300.0,
            is_available=True,
            is_deleted=False
        )
        db.session.add(target_prod)
        db.session.commit()

        res_limit = self.client.post(f'/marketplace/{target_prod.id}/report', data={
            'reason': 'spam',
            'details': 'Attempting 6th report within 1 hour'
        }, follow_redirects=True)
        self.assertIn('maximum number of', res_limit.get_data(as_text=True).lower())

        # Clean up extra products
        for p in extra_products + [target_prod]:
            ListingReport.query.filter_by(product_id=p.id).delete()
            Product.query.filter_by(id=p.id).delete()
        db.session.commit()

    def test_three_report_flag_without_auto_hide(self):
        """When 3 distinct users submit open reports, listing is flagged 'Needs review' but NOT hidden automatically."""
        # Buyer 1 report
        db.session.add(ListingReport(product_id=self.product.id, reporter_id=self.buyer1.id, reason='misleading_price', status='open'))
        # Buyer 2 report
        db.session.add(ListingReport(product_id=self.product.id, reporter_id=self.buyer2.id, reason='spam', status='open'))
        # Buyer 3 report
        db.session.add(ListingReport(product_id=self.product.id, reporter_id=self.buyer3.id, reason='wrong_or_fake_photo', status='open'))
        db.session.commit()

        # Product is NOT auto-hidden
        db.session.refresh(self.product)
        self.assertTrue(self.product.is_available)
        self.assertIsNone(self.product.hidden_reason)

        # Admin queue highlights listing as Needs Review
        self._login(self.admin.email, "AdminStrongPass!2026")
        res = self.client.get('/admin/reports')
        html = res.get_data(as_text=True)
        self.assertIn('Needs Review', html)

    def test_hide_listing_removes_it_from_marketplace(self):
        """Admin hiding a reported listing sets moderation reason and resolves open reports."""
        report = ListingReport(product_id=self.product.id, reporter_id=self.buyer1.id, reason='prohibited_item', status='open')
        db.session.add(report)
        db.session.commit()

        self._login(self.admin.email, "AdminStrongPass!2026")
        res = self.client.post(f'/admin/reports/{report.id}/hide-listing', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db.session.refresh(self.product)
        db.session.refresh(report)

        self.assertFalse(self.product.is_available)
        self.assertEqual(self.product.hidden_reason, 'moderation')
        self.assertEqual(self.product.hidden_by, self.admin.id)
        self.assertEqual(report.status, 'resolved')

    def test_admin_cancel_restores_stock_exactly_once(self):
        """Admin cancelling an order restores stock to the product exactly once."""
        order = Order(
            buyer_id=self.buyer1.id,
            product_id=self.product.id,
            quantity_kg=25.0,
            total_price=5500.00,
            status='confirmed',
            fulfillment_type='pickup'
        )
        db.session.add(order)
        db.session.commit()

        initial_stock = self.product.quantity_kg  # 100

        self._login(self.admin.email, "AdminStrongPass!2026")

        # 1. Admin cancels with valid reason
        res1 = self.client.post(f'/admin/orders/{order.id}/cancel', data={
            'reason': 'Farmer unable to supply due to heavy weather; buyer agreed to refund'
        }, follow_redirects=True)
        self.assertEqual(res1.status_code, 200)

        db.session.refresh(order)
        db.session.refresh(self.product)
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(self.product.quantity_kg, initial_stock + 25.0)  # 125.0

        # 2. Duplicate cancel attempt is rejected
        res2 = self.client.post(f'/admin/orders/{order.id}/cancel', data={
            'reason': 'Trying to cancel again'
        }, follow_redirects=True)
        self.assertIn('cannot', res2.get_data(as_text=True).lower())

        db.session.refresh(self.product)
        self.assertEqual(self.product.quantity_kg, initial_stock + 25.0)  # Still 125.0, restored exactly once

    def test_mandatory_reasons(self):
        """Mandatory reasons are enforced on rejection, revocation, and order cancellation."""
        self._login(self.admin.email, "AdminStrongPass!2026")

        # 1. Reject verification without reason
        req = VerificationRequest(farmer_id=self.farmer.id, status='pending')
        db.session.add(req)
        db.session.commit()

        res_reject = self.client.post(f'/admin/verifications/{req.id}/reject', data={'admin_note': ''}, follow_redirects=True)
        self.assertIn('mandatory', res_reject.get_data(as_text=True).lower())

        # 2. Revoke verification without reason
        self.farmer.is_verified = True
        db.session.commit()
        res_revoke = self.client.post(f'/admin/users/{self.farmer.id}/revoke-verification', data={'reason': ''}, follow_redirects=True)
        self.assertIn('mandatory', res_revoke.get_data(as_text=True).lower())

        # 3. Cancel order without reason
        order = Order(buyer_id=self.buyer1.id, product_id=self.product.id, quantity_kg=10.0, total_price=2200.0, status='pending')
        db.session.add(order)
        db.session.commit()
        res_cancel = self.client.post(f'/admin/orders/{order.id}/cancel', data={'reason': '   '}, follow_redirects=True)
        self.assertIn('mandatory', res_cancel.get_data(as_text=True).lower())

    def test_non_admin_access_forbidden(self):
        """Non-admin users cannot access admin verifications, reports, or cancellation endpoints."""
        self._login(self.buyer1.email, "Buyer1Pass!2026")

        endpoints = [
            ('/admin/verifications', 'get'),
            ('/admin/reports', 'get'),
            ('/admin/crops', 'get'),
            ('/admin/orders/999/cancel', 'post'),
        ]

        for url, method in endpoints:
            if method == 'get':
                res = self.client.get(url)
            else:
                res = self.client.post(url, data={'reason': 'test reason'})
            self.assertEqual(res.status_code, 403, f"Expected 403 on {url} for non-admin")

    def test_reporter_identity_not_leaked_in_farmer_facing_pages(self):
        """Reporter email or name is never leaked in product detail or farmer views."""
        secret_email = f"whistleblower_{self.uid}@secret.lk"
        secret_reporter = User(
            name=f"Anonymous Reporter {self.uid}",
            email=secret_email,
            role="buyer",
            phone="0779998888",
            is_active=True
        )
        secret_reporter.set_password("Pass12345!")
        db.session.add(secret_reporter)
        db.session.commit()

        report = ListingReport(
            product_id=self.product.id,
            reporter_id=secret_reporter.id,
            reason='spam',
            details=f"Confidential Report Content {self.uid}",
            status='open'
        )
        db.session.add(report)
        db.session.commit()

        # Farmer views own product page
        self._login(self.farmer.email, "FarmerPass!2026")
        res = self.client.get(f'/marketplace/{self.product.id}')
        html = res.get_data(as_text=True)

        self.assertNotIn(secret_email, html)
        self.assertNotIn(secret_reporter.name, html)
        self.assertNotIn(f"Confidential Report Content {self.uid}", html)

        # Clean up secret reporter report
        ListingReport.query.filter_by(id=report.id).delete()
        db.session.commit()
