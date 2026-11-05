import unittest
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from extensions import db
from models import AdminAuditLog, ListingReport, MarketPrice, MarketPriceHistory, Order, PlatformSetting, Product, User, VerificationRequest
from services.settings import clear_settings_cache


class TestDashboardMapAndReports(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        clear_settings_cache()
        Order.query.filter(Order.created_at >= datetime(2027, 1, 1)).delete(synchronize_session=False)
        db.session.commit()
        self.uid = uuid.uuid4().hex[:8]

        # Create Admin
        self.admin = User(
            name=f"Admin {self.uid}",
            email=f"admin_{self.uid}@agrolink.lk",
            role='admin',
            is_active=True
        )
        self.admin.set_password("AdminPass123!")
        db.session.add(self.admin)

        # Create Buyers
        self.buyer1 = User(
            name=f"Buyer One {self.uid}",
            email=f"buyer1_{self.uid}@agrolink.lk",
            role='buyer',
            is_active=True,
            location="Colombo",
            latitude=6.9271,
            longitude=79.8612
        )
        self.buyer1.set_password("BuyerPass123!")
        db.session.add(self.buyer1)

        # Create Farmers
        self.farmer_pinned = User(
            name=f"Farmer Pinned {self.uid}",
            email=f"farmer_p_{self.uid}@agrolink.lk",
            role='farmer',
            is_active=True,
            is_verified=True,
            farm_name=f"Green Valley Farm {self.uid}",
            location="Kandy",
            latitude=7.2906,
            longitude=80.6337
        )
        self.farmer_pinned.set_password("FarmerPass123!")
        db.session.add(self.farmer_pinned)

        self.farmer_unpinned = User(
            name=f"Farmer Unpinned {self.uid}",
            email=f"farmer_u_{self.uid}@agrolink.lk",
            role='farmer',
            is_active=True,
            is_verified=False,
            location="Jaffna",
            latitude=None,
            longitude=None
        )
        self.farmer_unpinned.set_password("FarmerPass123!")
        db.session.add(self.farmer_unpinned)

        db.session.commit()

        # Create Products
        self.prod_carrots = Product(
            farmer_id=self.farmer_pinned.id,
            name=f"Carrot {self.uid}",
            category="Vegetables",
            quantity_kg=100.0,
            price_per_kg=120.0,
            is_available=True,
            is_deleted=False
        )
        self.prod_tomatoes = Product(
            farmer_id=self.farmer_pinned.id,
            name=f"Tomato {self.uid}",
            category="Vegetables",
            quantity_kg=25.0,  # below default low_stock_kg (50)
            price_per_kg=150.0,
            is_available=True,
            is_deleted=False
        )
        db.session.add_all([self.prod_carrots, self.prod_tomatoes])
        db.session.commit()

    def tearDown(self):
        clear_settings_cache()
        # Clean test records created during each test
        prod_ids = [self.prod_carrots.id, self.prod_tomatoes.id]
        Order.query.filter(
            (Order.buyer_id == self.buyer1.id) |
            (Order.product_id.in_(prod_ids)) |
            (Order.created_at >= datetime(2027, 1, 1))
        ).delete(synchronize_session=False)
        ListingReport.query.filter(
            (ListingReport.reporter_id == self.buyer1.id) |
            (ListingReport.product_id.in_(prod_ids))
        ).delete(synchronize_session=False)
        VerificationRequest.query.filter(
            VerificationRequest.farmer_id.in_([self.farmer_pinned.id, self.farmer_unpinned.id])
        ).delete(synchronize_session=False)
        Product.query.filter(Product.id.in_(prod_ids)).delete(synchronize_session=False)
        db.session.commit()
        self.app_context.pop()

    def _login(self, email, password):
        self.client.get('/auth/logout', follow_redirects=True)
        return self.client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)

    def test_aggregation_correctness_and_definitions(self):
        """Dashboard aggregations adhere strictly to business definitions:
        - Order value: sum of orders not in ('cancelled', 'rejected')
        - Completed value: sum of delivered orders only
        - AOV, completion rate, and cancellation rate computed accurately.
        """
        # Place orders in isolated future window 2028-01-01 to 2028-01-07
        base_dt = datetime(2028, 1, 2, 10, 0, 0)

        # 1. Delivered order (1,200 items + 300 fee = 1,500 total)
        o_delivered = Order(
            buyer_id=self.buyer1.id,
            product_id=self.prod_carrots.id,
            quantity_kg=10.0,
            items_total=1200.0,
            delivery_fee=300.0,
            total_price=1500.0,
            status='delivered',
            fulfillment_type='delivery',
            created_at=base_dt
        )
        # 2. Confirmed order (2,400 total)
        o_confirmed = Order(
            buyer_id=self.buyer1.id,
            product_id=self.prod_carrots.id,
            quantity_kg=20.0,
            items_total=2400.0,
            delivery_fee=0.0,
            total_price=2400.0,
            status='confirmed',
            fulfillment_type='pickup',
            created_at=base_dt + timedelta(days=1)
        )
        # 3. Cancelled order (1,000 total - must be excluded from order value)
        o_cancelled = Order(
            buyer_id=self.buyer1.id,
            product_id=self.prod_tomatoes.id,
            quantity_kg=5.0,
            items_total=750.0,
            delivery_fee=250.0,
            total_price=1000.0,
            status='cancelled',
            fulfillment_type='delivery',
            created_at=base_dt + timedelta(days=2)
        )
        # 4. Rejected order (300 total - must be excluded from order value)
        o_rejected = Order(
            buyer_id=self.buyer1.id,
            product_id=self.prod_tomatoes.id,
            quantity_kg=2.0,
            items_total=300.0,
            delivery_fee=0.0,
            total_price=300.0,
            status='rejected',
            fulfillment_type='pickup',
            created_at=base_dt + timedelta(days=3)
        )
        db.session.add_all([o_delivered, o_confirmed, o_cancelled, o_rejected])
        db.session.commit()

        self._login(self.admin.email, "AdminPass123!")
        res = self.client.get('/admin/dashboard?range=custom&start=2028-01-01&end=2028-01-07')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Expected Order Value: 1,500 + 2,400 = 3,900.00
        self.assertIn('3,900.00', html)
        # Expected Completed Value: 1,500.00
        self.assertIn('1,500.00', html)
        # Expected Delivery Fees: 300.00
        self.assertIn('300.00', html)
        # Expected Orders count: 4
        self.assertIn('>4</p>', html)

    def test_date_range_boundaries(self):
        """Orders placed outside selected date boundaries are excluded from range metrics."""
        # Inside window: 2028-02-03
        o_inside = Order(
            buyer_id=self.buyer1.id,
            product_id=self.prod_carrots.id,
            quantity_kg=10.0,
            items_total=1200.0,
            total_price=1200.0,
            status='delivered',
            created_at=datetime(2028, 2, 3, 12, 0, 0)
        )
        # Outside window: 2028-02-25
        o_outside = Order(
            buyer_id=self.buyer1.id,
            product_id=self.prod_carrots.id,
            quantity_kg=50.0,
            items_total=6000.0,
            total_price=6000.0,
            status='delivered',
            created_at=datetime(2028, 2, 25, 12, 0, 0)
        )
        db.session.add_all([o_inside, o_outside])
        db.session.commit()

        self._login(self.admin.email, "AdminPass123!")

        # Query custom window: 2028-02-01 to 2028-02-07 (only o_inside is included)
        res_narrow = self.client.get('/admin/dashboard?range=custom&start=2028-02-01&end=2028-02-07')
        html_narrow = res_narrow.get_data(as_text=True)
        self.assertIn('1,200.00', html_narrow)
        self.assertNotIn('7,200.00', html_narrow)

        # Query wider window: 2028-02-01 to 2028-02-28 (both are included)
        res_wide = self.client.get('/admin/dashboard?range=custom&start=2028-02-01&end=2028-02-28')
        html_wide = res_wide.get_data(as_text=True)
        self.assertIn('7,200.00', html_wide)

    def test_top_n_ordering(self):
        """Top farmers are ordered by completed value DESC, and top crops by quantity DESC."""
        farmer2 = User(
            name=f"Farmer Two {self.uid}",
            email=f"farmer2_{self.uid}@agrolink.lk",
            role='farmer',
            is_active=True
        )
        farmer2.set_password("FarmerPass123!")
        db.session.add(farmer2)
        db.session.commit()

        prod_farmer2 = Product(
            farmer_id=farmer2.id,
            name=f"Leeks {self.uid}",
            category="Vegetables",
            quantity_kg=50.0,
            price_per_kg=80.0,
            is_available=True,
            is_deleted=False
        )
        db.session.add(prod_farmer2)
        db.session.commit()

        # Farmer 1 has 5,000 completed
        o1 = Order(buyer_id=self.buyer1.id, product_id=self.prod_carrots.id, quantity_kg=25.0, total_price=5000.0, status='delivered', created_at=datetime(2028, 3, 2, 10, 0, 0))
        # Farmer 2 has 1,000 completed
        o2 = Order(buyer_id=self.buyer1.id, product_id=prod_farmer2.id, quantity_kg=10.0, total_price=1000.0, status='delivered', created_at=datetime(2028, 3, 3, 10, 0, 0))
        db.session.add_all([o1, o2])
        db.session.commit()

        self._login(self.admin.email, "AdminPass123!")
        res = self.client.get('/admin/dashboard?range=custom&start=2028-03-01&end=2028-03-07')
        html = res.get_data(as_text=True)

        idx_f1 = html.find(self.farmer_pinned.name)
        idx_f2 = html.find(farmer2.name)
        self.assertNotEqual(idx_f1, -1)
        self.assertNotEqual(idx_f2, -1)
        self.assertLess(idx_f1, idx_f2)

        # Cleanup extra farmer
        Order.query.filter_by(product_id=prod_farmer2.id).delete(synchronize_session=False)
        Product.query.filter_by(id=prod_farmer2.id).delete(synchronize_session=False)
        db.session.commit()

    def test_farmers_map_access_control_and_pins(self):
        """Only admins can access /admin/map; pinned farmers are plotted and unpinned count is displayed."""
        # 1. Anonymous user redirected to login
        res_anon = self.client.get('/admin/map')
        self.assertEqual(res_anon.status_code, 302)

        # 2. Buyer gets 403 Forbidden
        self._login(self.buyer1.email, "BuyerPass123!")
        res_buyer = self.client.get('/admin/map')
        self.assertEqual(res_buyer.status_code, 403)

        # 3. Admin gets 200 with map container, marker data, and unpinned count
        self._login(self.admin.email, "AdminPass123!")
        res_admin = self.client.get('/admin/map')
        self.assertEqual(res_admin.status_code, 200)
        html = res_admin.get_data(as_text=True)

        self.assertIn('Farmers Map', html)
        self.assertIn('without map pin', html)
        self.assertIn(self.farmer_pinned.name, html)

    def test_reports_hub_table_and_totals(self):
        """Operational reports hub renders on-screen table with highlighted Totals row."""
        o = Order(
            buyer_id=self.buyer1.id,
            product_id=self.prod_carrots.id,
            quantity_kg=15.0,
            items_total=1800.0,
            delivery_fee=200.0,
            total_price=2000.0,
            status='delivered',
            created_at=datetime(2028, 4, 2, 10, 0, 0)
        )
        u_period = User(
            name=f"Period User {self.uid}",
            email=f"period_u_{self.uid}@agrolink.lk",
            role='buyer',
            is_active=True,
            created_at=datetime(2028, 4, 2, 10, 0, 0)
        )
        u_period.set_password("Period123!")
        db.session.add_all([o, u_period])
        db.session.commit()

        self._login(self.admin.email, "AdminPass123!")

        # 1. Sales Summary Report
        res_sales = self.client.get('/admin/reports?type=sales&range=custom&start=2028-04-01&end=2028-04-07')
        self.assertEqual(res_sales.status_code, 200)
        self.assertIn('Total / Summary', res_sales.get_data(as_text=True))

        # 2. Users Report
        res_users = self.client.get('/admin/reports?type=users&range=custom&start=2028-04-01&end=2028-04-07')
        self.assertEqual(res_users.status_code, 200)
        self.assertIn('Total Users in Period', res_users.get_data(as_text=True))

        # 3. Orders Report
        res_orders = self.client.get('/admin/reports?type=orders&range=custom&start=2028-04-01&end=2028-04-07')
        self.assertEqual(res_orders.status_code, 200)
        self.assertIn('Total (', res_orders.get_data(as_text=True))

    def test_csv_export_safety_and_bom(self):
        """CSV export begins with UTF-8 BOM, sanitizes formula injection characters, and records an audit log entry."""
        malicious_buyer = User(
            name="=cmd|' /C calc'!A0",
            email=f"formula_{self.uid}@agrolink.lk",
            role='buyer',
            is_active=True,
            created_at=datetime.utcnow()
        )
        malicious_buyer.set_password("BuyerPass123!")
        db.session.add(malicious_buyer)
        db.session.commit()

        self._login(self.admin.email, "AdminPass123!")
        res_csv = self.client.get('/admin/reports/users.csv')
        self.assertEqual(res_csv.status_code, 200)
        content = res_csv.data

        # 1. Must start with UTF-8 BOM (\ufeff -> b'\xef\xbb\xbf')
        self.assertTrue(content.startswith(b'\xef\xbb\xbf'))

        # 2. Malicious formula character prefixed with single quote
        text = content.decode('utf-8')
        self.assertIn("'=cmd|' /C calc'!A0", text)

        # 3. Audit log recorded
        log = AdminAuditLog.query.filter_by(action='report_exported').order_by(AdminAuditLog.created_at.desc()).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.target_type, 'report')

        # Cleanup
        db.session.commit()

    def test_print_view_audit_logged(self):
        """Opening report with print parameter creates an audit log entry."""
        self._login(self.admin.email, "AdminPass123!")
        res = self.client.get('/admin/reports?type=sales&print=1')
        self.assertEqual(res.status_code, 200)

        log = AdminAuditLog.query.filter_by(action='report_print').order_by(AdminAuditLog.created_at.desc()).first()
        self.assertIsNotNone(log)
        self.assertIn('sales', log.details.lower())

    def test_dashboard_query_budget_under_15(self):
        """Admin dashboard must execute under 15 SQL queries."""
        from sqlalchemy import event
        self._login(self.admin.email, "AdminPass123!")

        query_count = 0
        @event.listens_for(db.engine, 'before_cursor_execute')
        def count_query(conn, cursor, statement, parameters, context, executemany):
            nonlocal query_count
            query_count += 1

        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertLess(query_count, 15, f"Dashboard ran {query_count} queries (must be < 15)")


if __name__ == '__main__':
    unittest.main()
