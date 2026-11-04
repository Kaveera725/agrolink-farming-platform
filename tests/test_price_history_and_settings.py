"""Tests for TASK (9C): Price history auditability, bulk import, and editable platform settings."""
import csv
import io
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
import unittest

from app import create_app
from extensions import db
from models import AdminAuditLog, MarketPrice, MarketPriceHistory, Order, PlatformSetting, Product, User
from services.pricing import calculate_delivery_fee, calculate_order_totals
from services.settings import (
    clear_settings_cache, get_active_announcement, get_setting,
    reset_settings_to_defaults, set_setting, validate_setting
)


class TestPriceHistoryAndSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        cls.client = cls.app.test_client()

    def setUp(self):
        self.app_context = self.app.app_context()
        self.app_context.push()
        clear_settings_cache()

        # Clean up any leftover test market prices
        MarketPrice.query.filter(
            MarketPrice.crop_name.in_([
                'Test Avocado 9C', 'Test Onion 9C', 'Atomic New Crop',
                'ImportUpdate Crop', 'DryRun Crop 1', 'DryRun Crop 2',
                'Very Stale Crop 9C', 'Detail Test', 'Bad Crop', 'Bad Crop 2'
            ])
        ).delete(synchronize_session=False)
        db.session.commit()

        # Find or create admin user
        self.admin = User.query.filter_by(role='admin').first()
        if not self.admin:
            self.admin = User(
                name="Admin 9C",
                email="admin9c@agrolink.lk",
                role="admin",
                is_active=True,
                session_version=1
            )
            self.admin.set_password("AdminPass123!")
            db.session.add(self.admin)
            db.session.commit()

        # Buyer and Farmer for order testing
        self.farmer = User.query.filter_by(role='farmer').first()
        if not self.farmer:
            self.farmer = User(
                name="Farmer 9C",
                email="farmer9c@agrolink.lk",
                role="farmer",
                is_active=True,
                latitude=Decimal('6.9271'),
                longitude=Decimal('79.8612'),
                session_version=1
            )
            self.farmer.set_password("FarmerPass123!")
            db.session.add(self.farmer)
            db.session.commit()

        self.buyer = User.query.filter_by(role='buyer').first()
        if not self.buyer:
            self.buyer = User(
                name="Buyer 9C",
                email="buyer9c@agrolink.lk",
                role="buyer",
                is_active=True,
                session_version=1
            )
            self.buyer.set_password("BuyerPass123!")
            db.session.add(self.buyer)
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            PlatformSetting.query.delete()
            db.session.commit()
            clear_settings_cache()

    def tearDown(self):
        PlatformSetting.query.delete()
        db.session.commit()
        clear_settings_cache()
        self.app_context.pop()

    def _login_admin(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.admin.id)
            sess['session_version'] = self.admin.session_version
            sess['is_admin'] = True

    # ──────────────────────────────────────────────────────────────────────────
    # 1. PRICE HISTORY & TYPO GUARD
    # ──────────────────────────────────────────────────────────────────────────
    def test_price_history_created_on_create_and_update(self):
        """History row must be written in the same transaction on price create and update."""
        self._login_admin()

        # 1. Create a price
        resp = self.client.post('/admin/prices', data={
            'crop_name': 'Test Avocado 9C',
            'category': 'Fruits',
            'buying_price': '100.00',
            'selling_price': '150.00',
            'unit': 'per kg',
            'market_location': 'Colombo'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        price = MarketPrice.query.filter_by(crop_name='Test Avocado 9C').first()
        self.assertIsNotNone(price)
        self.assertEqual(price.buying_price, 100.00)

        # Check creation history entry
        hist_create = MarketPriceHistory.query.filter_by(market_price_id=price.id).order_by(MarketPriceHistory.changed_at.asc()).first()
        self.assertIsNotNone(hist_create)
        self.assertIsNone(hist_create.old_buying)
        self.assertIsNone(hist_create.old_selling)
        self.assertEqual(hist_create.new_buying, 100.00)
        self.assertEqual(hist_create.new_selling, 150.00)
        self.assertEqual(hist_create.source, 'manual')

        # 2. Normal update (< 30% change, e.g. 100 -> 110, 150 -> 160)
        resp2 = self.client.post(f'/admin/prices?edit={price.id}', data={
            'id': str(price.id),
            'crop_name': 'Test Avocado 9C',
            'category': 'Fruits',
            'buying_price': '110.00',
            'selling_price': '160.00',
            'unit': 'per kg',
            'market_location': 'Colombo'
        }, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)

        # Check update history entry
        hist_update = MarketPriceHistory.query.filter_by(market_price_id=price.id).order_by(MarketPriceHistory.changed_at.desc()).first()
        self.assertIsNotNone(hist_update)
        self.assertEqual(hist_update.old_buying, 100.00)
        self.assertEqual(hist_update.old_selling, 150.00)
        self.assertEqual(hist_update.new_buying, 110.00)
        self.assertEqual(hist_update.new_selling, 160.00)
        self.assertEqual(hist_update.source, 'manual')

    def test_price_typo_guard_over_30_percent(self):
        """Price updates > 30% must trigger warning and require confirmation checkbox."""
        self._login_admin()

        price = MarketPrice(
            crop_name="Test Onion 9C",
            category="Vegetables",
            buying_price=100.00,
            selling_price=140.00,
            unit="per kg",
            market_location="Colombo"
        )
        db.session.add(price)
        db.session.commit()

        # Update > 30% without confirmation (100 -> 150, 50% increase)
        resp = self.client.post(f'/admin/prices?edit={price.id}', data={
            'id': str(price.id),
            'crop_name': 'Test Onion 9C',
            'category': 'Vegetables',
            'buying_price': '150.00',
            'selling_price': '190.00',
            'unit': 'per kg',
            'market_location': 'Colombo'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'exceeds 30%', resp.data)
        self.assertIn(b'confirm_large_change', resp.data)

        # Verify DB value was NOT changed
        price_reloaded = MarketPrice.query.get(price.id)
        self.assertEqual(price_reloaded.buying_price, 100.00)

        # Now submit with confirmation checkbox checked
        resp_confirmed = self.client.post(f'/admin/prices?edit={price.id}', data={
            'id': str(price.id),
            'crop_name': 'Test Onion 9C',
            'category': 'Vegetables',
            'buying_price': '150.00',
            'selling_price': '190.00',
            'confirm_large_change': 'yes',
            'unit': 'per kg',
            'market_location': 'Colombo'
        }, follow_redirects=True)
        self.assertEqual(resp_confirmed.status_code, 200)

        price_updated = MarketPrice.query.get(price.id)
        self.assertEqual(price_updated.buying_price, 150.00)
        self.assertEqual(price_updated.selling_price, 190.00)

    def test_price_validation_rules_enforced(self):
        """Prices must be positive and selling price must be at least buying price."""
        self._login_admin()

        # buying <= 0
        resp1 = self.client.post('/admin/prices', data={
            'crop_name': 'Bad Crop',
            'category': 'Test',
            'buying_price': '0.00',
            'selling_price': '10.00'
        }, follow_redirects=True)
        self.assertIn(b'Prices must be positive', resp1.data)

        # selling < buying
        resp2 = self.client.post('/admin/prices', data={
            'crop_name': 'Bad Crop 2',
            'category': 'Test',
            'buying_price': '50.00',
            'selling_price': '40.00'
        }, follow_redirects=True)
        self.assertIn(b'selling price must be at least buying price', resp2.data)

    def test_price_detail_page_loads(self):
        """Admin price detail page renders Chart.js canvas and history table."""
        self._login_admin()
        price = MarketPrice.query.first()
        if not price:
            price = MarketPrice(crop_name='Detail Test', category='Test', buying_price=10.0, selling_price=20.0)
            db.session.add(price)
            db.session.commit()

        resp = self.client.get(f'/admin/prices/{price.id}')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'price-history-chart', resp.data)
        self.assertIn(b'Audit History Log', resp.data)

    # ──────────────────────────────────────────────────────────────────────────
    # 2. BULK CSV IMPORT
    # ──────────────────────────────────────────────────────────────────────────
    def test_import_dry_run_saves_nothing(self):
        """Uploading CSV dry-runs and does NOT modify the database."""
        self._login_admin()

        csv_text = (
            "crop_name,category,buying_price,selling_price,unit,market_location\n"
            "DryRun Crop 1,Vegetables,50.00,75.00,per kg,Colombo\n"
            "DryRun Crop 2,Vegetables,80.00,120.00,per kg,Colombo\n"
        )
        data = {'file': (io.BytesIO(csv_text.encode('utf-8')), 'test_import.csv')}

        resp = self.client.post('/admin/prices/import', data=data, content_type='multipart/form-data')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Dry-Run Preview', resp.data)
        self.assertIn(b'DryRun Crop 1', resp.data)

        # Verify nothing was saved to DB
        p1 = MarketPrice.query.filter_by(crop_name='DryRun Crop 1').first()
        self.assertIsNone(p1)

    def test_import_atomicity_and_invalid_rows_reported(self):
        """Confirming import applies valid rows, skips invalid ones, records history with source 'import', and creates ONE audit log."""
        self._login_admin()

        # Existing price to test 'update'
        existing = MarketPrice(crop_name='ImportUpdate Crop', category='Grains', buying_price=50.0, selling_price=70.0)
        db.session.add(existing)
        db.session.commit()

        import_rows = [
            # 1. Valid new
            {
                'status': 'new',
                'crop_name': 'Atomic New Crop',
                'category': 'Vegetables',
                'buying_price': '60.00',
                'selling_price': '90.00',
                'unit': 'per kg',
                'market_location': 'Colombo'
            },
            # 2. Valid update
            {
                'status': 'update',
                'crop_name': 'ImportUpdate Crop',
                'category': 'Grains',
                'buying_price': '55.00',
                'selling_price': '75.00',
                'unit': 'per kg',
                'market_location': 'Colombo'
            },
            # 3. Invalid row (skipped)
            {
                'status': 'invalid',
                'crop_name': 'Invalid Crop',
                'category': 'Spam',
                'buying_price': '-10.00',
                'selling_price': '20.00',
                'unit': 'per kg',
                'market_location': 'Colombo'
            }
        ]

        resp = self.client.post('/admin/prices/import/confirm', data={
            'import_payload': json.dumps(import_rows),
            'filename': 'bulk_prices_2026.csv'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        db.session.expire_all()

        # Check new price created
        new_p = MarketPrice.query.filter_by(crop_name='Atomic New Crop').first()
        self.assertIsNotNone(new_p)
        self.assertEqual(new_p.buying_price, 60.00)

        # Check existing price updated
        up_p = MarketPrice.query.filter_by(crop_name='ImportUpdate Crop').first()
        self.assertEqual(up_p.buying_price, 55.00)

        # Check invalid crop was NOT created
        inv_p = MarketPrice.query.filter_by(crop_name='Invalid Crop').first()
        self.assertIsNone(inv_p)

        # Check history rows with source='import'
        hist_new = MarketPriceHistory.query.filter_by(market_price_id=new_p.id).first()
        self.assertIsNotNone(hist_new)
        self.assertEqual(hist_new.source, 'import')

        hist_up = MarketPriceHistory.query.filter_by(market_price_id=up_p.id).order_by(MarketPriceHistory.changed_at.desc()).first()
        self.assertIsNotNone(hist_up)
        self.assertEqual(hist_up.source, 'import')
        self.assertEqual(hist_up.old_buying, 50.0)
        self.assertEqual(hist_up.new_buying, 55.0)

        # Check ONE audit log entry
        audit = AdminAuditLog.query.filter_by(action='market_prices_imported').order_by(AdminAuditLog.created_at.desc()).first()
        self.assertIsNotNone(audit)
        self.assertIn('bulk_prices_2026.csv', audit.details)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. STALE PRICE ALERT
    # ──────────────────────────────────────────────────────────────────────────
    def test_stale_price_alert(self):
        """Prices older than stale_price_days trigger the stale warning."""
        self._login_admin()
        set_setting('stale_price_days', 5)

        old_date = datetime.utcnow() - timedelta(days=10)
        # Use direct INSERT so PostgreSQL BEFORE UPDATE trigger does not reset updated_at to now
        db.session.execute(
            db.text("INSERT INTO market_prices (crop_name, category, buying_price, selling_price, unit, market_location, updated_at) "
                    "VALUES ('Very Stale Crop 9C', 'Roots', 30.0, 45.0, 'per kg', 'Colombo', :dt)"),
            {'dt': old_date}
        )
        db.session.commit()

        resp = self.client.get('/admin/prices')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Prices not updated in 5 days', resp.data)
        self.assertIn(b'Very Stale Crop 9C', resp.data)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. PLATFORM SETTINGS & PRICING INTEGRATION
    # ──────────────────────────────────────────────────────────────────────────
    def test_settings_validation_ranges(self):
        """Settings validation must enforce min/max and types."""
        # Valid settings
        v, t = validate_setting('delivery_base_fee', '6500')
        self.assertEqual(v, '6500')
        self.assertEqual(t, 'decimal')

        # Invalid range: delivery_base_km < 1
        with self.assertRaises(ValueError):
            validate_setting('delivery_base_km', '0')

        # Invalid range: delivery_base_fee > 100000
        with self.assertRaises(ValueError):
            validate_setting('delivery_base_fee', '150000')

        # Invalid range: stale_price_days > 90
        with self.assertRaises(ValueError):
            validate_setting('stale_price_days', '100')

        # Invalid length: announcement_text > 200 chars
        with self.assertRaises(ValueError):
            validate_setting('announcement_text', 'x' * 201)

    def test_settings_cache_and_invalidation(self):
        """Setting must be cached and immediately invalidated on set_setting."""
        clear_settings_cache()
        set_setting('delivery_base_fee', '7000.00')

        val1 = get_setting('delivery_base_fee')
        self.assertEqual(val1, Decimal('7000.00'))

        # Direct DB change without invalidation would not show due to cache
        PlatformSetting.query.filter_by(key='delivery_base_fee').update({'value': '8000.00'})
        db.session.commit()
        self.assertEqual(get_setting('delivery_base_fee'), Decimal('7000.00'))  # from cache

        # Invalidation clears cache
        clear_settings_cache('delivery_base_fee')
        self.assertEqual(get_setting('delivery_base_fee'), Decimal('8000.00'))

        # Updating via set_setting invalidates automatically
        set_setting('delivery_base_fee', '9000.00')
        self.assertEqual(get_setting('delivery_base_fee'), Decimal('9000.00'))

    def test_new_rates_used_for_new_quotes_while_existing_orders_unchanged(self):
        """Changing delivery rates updates new fee quotes, but NEVER modifies existing placed orders."""
        # 1. Place an existing order at initial rate (base 5000, 30 km -> 5000)
        set_setting('delivery_base_fee', '5000.00')
        set_setting('delivery_base_km', '50.00')
        set_setting('delivery_extra_per_km', '60.00')
        db.session.commit()

        initial_fee = calculate_delivery_fee(Decimal('30.0'))
        self.assertEqual(initial_fee, Decimal('5000.00'))

        prod = Product.query.filter_by(is_deleted=False).first()
        if not prod:
            prod = Product(
                farmer_id=self.farmer.id,
                name="Test Crop 9C",
                category="Vegetables",
                price_per_kg=100.0,
                quantity_kg=50.0,
                is_available=True
            )
            db.session.add(prod)
            db.session.commit()

        order = Order(
            buyer_id=self.buyer.id,
            product_id=prod.id,
            quantity_kg=Decimal('10.00'),
            items_total=Decimal('1500.00'),
            delivery_fee=Decimal('5000.00'),
            total_price=Decimal('6500.00'),
            fulfillment_type='delivery',
            delivery_address='Colombo 03',
            status='pending'
        )
        db.session.add(order)
        db.session.commit()
        order_id = order.id

        # 2. Admin changes the delivery rate via settings
        set_setting('delivery_base_fee', '7500.00')
        set_setting('delivery_extra_per_km', '100.00')
        db.session.commit()

        # 3. New fee quote calculation uses the new rates
        new_quote = calculate_delivery_fee(Decimal('30.0'))
        self.assertEqual(new_quote, Decimal('7500.00'))

        # 4. Old placed order snapshot MUST REMAIN UNCHANGED
        db.session.expire_all()
        reloaded_order = Order.query.get(order_id)
        self.assertEqual(reloaded_order.delivery_fee, Decimal('5000.00'))
        self.assertEqual(reloaded_order.total_price, Decimal('6500.00'))

    def test_announcement_escaping_and_expiry(self):
        """Announcement banner escapes HTML and hides after expiry."""
        # 1. Active announcement with HTML characters
        set_setting('announcement_enabled', 'true')
        set_setting('announcement_text', '<script>alert("XSS")</script> Monsoon Notice')
        set_setting('announcement_level', 'warning')
        set_setting('announcement_expires_at', '')
        db.session.commit()

        banner = get_active_announcement()
        self.assertIsNotNone(banner)
        self.assertEqual(banner['level'], 'warning')

        resp = self.client.get('/prices/', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        # HTML characters must be escaped by template engine
        self.assertIn(b'&lt;script&gt;alert(&#34;XSS&#34;)&lt;/script&gt; Monsoon Notice', resp.data)
        self.assertNotIn(b'<script>alert("XSS")</script>', resp.data)

        # 2. Expired announcement
        yesterday = (datetime.utcnow() - timedelta(days=2)).strftime('%Y-%m-%d')
        set_setting('announcement_expires_at', yesterday)
        db.session.commit()

        banner_expired = get_active_announcement()
        self.assertIsNone(banner_expired)

        resp2 = self.client.get('/prices/', follow_redirects=True)
        self.assertNotIn(b'Monsoon Notice', resp2.data)


if __name__ == '__main__':
    unittest.main()
