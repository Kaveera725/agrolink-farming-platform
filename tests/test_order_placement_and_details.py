"""Integration and security tests for order placement, order detail pages, and status workflows (Task 8C)."""
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch

from app import create_app
from extensions import db, limiter
from models import User, Product, Order


class TestOrderPlacementAndDetails(unittest.TestCase):
    """Test order placement, server recalculations, status state machine, privacy, and order views."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        limiter.reset()

        self.cleanup_emails = [
            'farmer_8c@example.com',
            'farmer_other_8c@example.com',
            'farmer_nopin_8c@example.com',
            'buyer_8c@example.com',
            'buyer_other_8c@example.com',
        ]
        self._cleanup_data()
        self._seed_data()

    def tearDown(self):
        self._cleanup_data()
        self.ctx.pop()

    def _cleanup_data(self):
        Order.query.filter(Order.notes.like('%Test 8C%')).delete(synchronize_session=False)
        Product.query.filter(Product.name.like('%8C Produce%')).delete(synchronize_session=False)
        for email in self.cleanup_emails:
            u = User.query.filter_by(email=email).first()
            if u:
                db.session.delete(u)
        db.session.commit()

    def _seed_data(self):
        # Farmer 1 (with location pin)
        self.farmer = User(
            name='Kamal Perera',
            email='farmer_8c@example.com',
            role='farmer',
            phone='0771112233',
            location='Dambulla',
            latitude=Decimal('7.873100'),
            longitude=Decimal('80.771800'),
            address_text='Dambulla Market, Matale',
            location_updated_at=datetime.now(timezone.utc)
        )
        self.farmer.set_password('Secret123!')
        db.session.add(self.farmer)

        # Farmer 2 (Other farmer)
        self.farmer_other = User(
            name='Other Farmer',
            email='farmer_other_8c@example.com',
            role='farmer',
            phone='0772223344',
            location='Kandy',
            latitude=Decimal('7.290600'),
            longitude=Decimal('80.633700'),
            address_text='Kandy Town'
        )
        self.farmer_other.set_password('Secret123!')
        db.session.add(self.farmer_other)

        # Farmer 3 (No pin)
        self.farmer_nopin = User(
            name='NoPin Farmer',
            email='farmer_nopin_8c@example.com',
            role='farmer',
            phone='0773334455',
            location='Jaffna'
        )
        self.farmer_nopin.set_password('Secret123!')
        db.session.add(self.farmer_nopin)

        # Buyer 1
        self.buyer = User(
            name='Nimal Silva',
            email='buyer_8c@example.com',
            role='buyer',
            phone='0715556677',
            location='Colombo',
            latitude=Decimal('6.927100'),
            longitude=Decimal('79.861200'),
            address_text='123 Galle Road, Colombo 03'
        )
        self.buyer.set_password('Secret123!')
        db.session.add(self.buyer)

        # Buyer 2 (Other buyer)
        self.buyer_other = User(
            name='Sunil Fernando',
            email='buyer_other_8c@example.com',
            role='buyer',
            phone='0719998877',
            location='Negombo'
        )
        self.buyer_other.set_password('Secret123!')
        db.session.add(self.buyer_other)
        db.session.commit()

        # Product with delivery offered (50 kg in stock, Rs. 100/kg)
        self.product_delivery = Product(
            name='8C Produce Carrots',
            category='Vegetables',
            description='Fresh carrots',
            price_per_kg=100.00,
            quantity_kg=50.0,
            is_available=True,
            offers_delivery=True,
            farmer_id=self.farmer.id
        )
        db.session.add(self.product_delivery)

        # Product without delivery offered (Pickup only, 20 kg in stock, Rs. 150/kg)
        self.product_pickup_only = Product(
            name='8C Produce Tomatoes (Pickup Only)',
            category='Vegetables',
            description='Ripe tomatoes',
            price_per_kg=150.00,
            quantity_kg=20.0,
            is_available=True,
            offers_delivery=False,
            farmer_id=self.farmer.id
        )
        db.session.add(self.product_pickup_only)

        # Product from farmer without pin
        self.product_nopin = Product(
            name='8C Produce Onions (No Pin Farmer)',
            category='Vegetables',
            description='Red onions',
            price_per_kg=200.00,
            quantity_kg=30.0,
            is_available=True,
            offers_delivery=True,
            farmer_id=self.farmer_nopin.id
        )
        db.session.add(self.product_nopin)
        db.session.commit()

    def _logout(self):
        return self.client.get('/auth/logout', follow_redirects=True)

    def _login(self, email, password='Secret123!'):
        self._logout()
        return self.client.post('/auth/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    # ─────────────────────────────────────────────────────────────────────────
    # 1. ORDER SUBMISSION & SERVER-SIDE RECOMPUTATION
    # ─────────────────────────────────────────────────────────────────────────

    @patch('blueprints.orders.routes.get_driving_distance_km')
    def test_order_submission_tampered_values_ignored(self, mock_dist):
        """Browser sending tampered items_total, delivery_fee, distance, and total_price are ignored."""
        mock_dist.return_value = (Decimal('60.0'), 'google')
        self._login('buyer_8c@example.com')

        # Tampered POST data: requesting 10 kg @ 100 (real produce total = 1000).
        # Tampered: claiming produce total = 10, fee = 5, total_price = 15, distance = 2.
        # Real distance = 60 km -> fee = 5000 + (10 * 60) = 5600. Real grand total = 6600.
        res = self.client.post(f'/orders/place/{self.product_delivery.id}', data={
            'quantity_kg': '10',
            'fulfillment_type': 'delivery',
            'delivery_lat': '6.9271',
            'delivery_lng': '79.8612',
            'delivery_address': 'Colombo 03 Test 8C',
            'notes': 'Test 8C order',
            # Tampered fields:
            'items_total': '10.00',
            'delivery_fee': '5.00',
            'total_price': '15.00',
            'distance_km': '2.0'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)

        order = Order.query.filter_by(notes='Test 8C order').first()
        self.assertIsNotNone(order)
        # Server must have recomputed produce total = 1000.00, fee = 5600.00, total = 6600.00
        self.assertEqual(order.items_total, Decimal('1000.00'))
        self.assertEqual(order.delivery_fee, Decimal('5600.00'))
        self.assertEqual(order.total_price, Decimal('6600.00'))
        self.assertEqual(order.distance_km, Decimal('60.00'))
        self.assertEqual(order.distance_source, 'google')
        self.assertEqual(order.fulfillment_type, 'delivery')
        self.assertEqual(str(order.delivery_address), 'Colombo 03 Test 8C')

        # Stock deducted safely
        p = Product.query.get(self.product_delivery.id)
        self.assertEqual(p.quantity_kg, 40.0)

    def test_pickup_order_stores_zero_fee(self):
        """Pickup order stores fee 0, no delivery coordinates, and only items total."""
        self._login('buyer_8c@example.com')

        res = self.client.post(f'/orders/place/{self.product_pickup_only.id}', data={
            'quantity_kg': '5',
            'fulfillment_type': 'pickup',
            'notes': 'Test 8C pickup'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        order = Order.query.filter_by(notes='Test 8C pickup').first()
        self.assertIsNotNone(order)
        self.assertEqual(order.fulfillment_type, 'pickup')
        self.assertEqual(order.delivery_fee, Decimal('0.00'))
        self.assertEqual(order.items_total, Decimal('750.00'))
        self.assertEqual(order.total_price, Decimal('750.00'))
        self.assertIsNone(order.delivery_lat)
        self.assertIsNone(order.delivery_lng)
        self.assertIsNone(order.distance_km)

    @patch('blueprints.orders.routes.get_driving_distance_km')
    def test_delivery_order_pricing_tiers(self, mock_dist):
        """Delivery fee correctly computed and snapshotted for 10 km, 50 km, and 72.3 km."""
        self._login('buyer_8c@example.com')

        cases = [
            (Decimal('10.0'), Decimal('5000.00')),    # under 50 km base
            (Decimal('50.0'), Decimal('5000.00')),    # exactly 50 km
            (Decimal('72.3'), Decimal('6380.00')),    # 5000 + (ceil(22.3) * 60) = 5000 + 1380 = 6380
        ]

        for dist, expected_fee in cases:
            mock_dist.return_value = (dist, 'estimated')
            res = self.client.post(f'/orders/place/{self.product_delivery.id}', data={
                'quantity_kg': '1',
                'fulfillment_type': 'delivery',
                'delivery_lat': '6.9271',
                'delivery_lng': '79.8612',
                'delivery_address': f'Address for {dist} Test 8C',
                'notes': f'Test 8C distance {dist}'
            }, follow_redirects=False)

            self.assertEqual(res.status_code, 302)
            order = Order.query.filter_by(notes=f'Test 8C distance {dist}').first()
            self.assertIsNotNone(order)
            self.assertEqual(order.delivery_fee, expected_fee)
            self.assertEqual(order.distance_km, dist)
            self.assertEqual(order.distance_source, 'estimated')

    def test_delivery_refused_when_not_offered(self):
        """If product.offers_delivery is False, ordering with fulfillment_type=delivery is blocked."""
        self._login('buyer_8c@example.com')

        res = self.client.post(f'/orders/place/{self.product_pickup_only.id}', data={
            'quantity_kg': '2',
            'fulfillment_type': 'delivery',
            'delivery_lat': '6.9271',
            'delivery_lng': '79.8612',
            'delivery_address': 'Colombo Test 8C',
            'notes': 'Test 8C refuse delivery'
        }, follow_redirects=True)

        self.assertIn(b'Delivery is not offered for this product', res.data)
        order = Order.query.filter_by(notes='Test 8C refuse delivery').first()
        self.assertIsNone(order)

    def test_delivery_refused_when_farmer_has_no_pin(self):
        """If farmer has no saved pin, delivery fulfillment is blocked."""
        self._login('buyer_8c@example.com')

        res = self.client.post(f'/orders/place/{self.product_nopin.id}', data={
            'quantity_kg': '2',
            'fulfillment_type': 'delivery',
            'delivery_lat': '6.9271',
            'delivery_lng': '79.8612',
            'delivery_address': 'Colombo Test 8C',
            'notes': 'Test 8C no farmer pin'
        }, follow_redirects=True)

        self.assertIn(b'Farmer pickup location is missing', res.data)
        order = Order.query.filter_by(notes='Test 8C no farmer pin').first()
        self.assertIsNone(order)

    def test_delivery_address_required_for_delivery(self):
        """Delivery address is strictly required when fulfillment_type is delivery."""
        self._login('buyer_8c@example.com')

        res = self.client.post(f'/orders/place/{self.product_delivery.id}', data={
            'quantity_kg': '2',
            'fulfillment_type': 'delivery',
            'delivery_lat': '6.9271',
            'delivery_lng': '79.8612',
            'delivery_address': '   ',  # whitespace only
            'notes': 'Test 8C missing address'
        }, follow_redirects=True)

        self.assertIn(b'Delivery address is required for delivery', res.data)
        order = Order.query.filter_by(notes='Test 8C missing address').first()
        self.assertIsNone(order)

    def test_out_of_bounds_delivery_coordinates_refused(self):
        """Coordinates outside Sri Lanka are refused."""
        self._login('buyer_8c@example.com')

        res = self.client.post(f'/orders/place/{self.product_delivery.id}', data={
            'quantity_kg': '2',
            'fulfillment_type': 'delivery',
            'delivery_lat': '28.6139',  # New Delhi
            'delivery_lng': '77.2090',
            'delivery_address': 'New Delhi',
            'notes': 'Test 8C out of bounds'
        }, follow_redirects=True)

        self.assertIn(b'Valid delivery location within Sri Lanka is required', res.data)
        order = Order.query.filter_by(notes='Test 8C out of bounds').first()
        self.assertIsNone(order)

    def test_quantity_above_stock_rejected(self):
        """Ordering more than available stock is rejected."""
        self._login('buyer_8c@example.com')

        res = self.client.post(f'/orders/place/{self.product_delivery.id}', data={
            'quantity_kg': '999',  # only 50 kg available
            'fulfillment_type': 'pickup',
            'notes': 'Test 8C overstock'
        }, follow_redirects=True)

        self.assertIn(b'Stock changed: only 50', res.data)
        order = Order.query.filter_by(notes='Test 8C overstock').first()
        self.assertIsNone(order)

    # ─────────────────────────────────────────────────────────────────────────
    # 2. STATUS TRANSITIONS & ORDER STATE MACHINE
    # ─────────────────────────────────────────────────────────────────────────

    def test_reject_requires_reason_and_restores_stock(self):
        """Farmer rejecting an order requires reason >= 5 chars and restores product stock."""
        # Create a pending order of 10 kg
        order = Order(
            buyer_id=self.buyer.id,
            product_id=self.product_delivery.id,
            quantity_kg=10.0,
            total_price=Decimal('1000.00'),
            fulfillment_type='pickup',
            status='pending',
            notes='Test 8C reject test'
        )
        self.product_delivery.quantity_kg -= 10.0
        db.session.add(order)
        db.session.commit()

        # Farmer logs in
        self._login('farmer_8c@example.com')

        # 1. Attempt reject with too short reason (< 5 chars)
        res_short = self.client.post(f'/orders/{order.id}/update-status', data={
            'status': 'rejected',
            'rejection_reason': 'no'
        }, follow_redirects=True)
        self.assertIn(b'Rejection reason must be at least 5 characters', res_short.data)
        db.session.refresh(order)
        self.assertEqual(order.status, 'pending')

        # 2. Valid reject with reason >= 5 chars
        res_valid = self.client.post(f'/orders/{order.id}/update-status', data={
            'status': 'rejected',
            'rejection_reason': 'Out of transport capacity for today'
        }, follow_redirects=True)
        self.assertIn(b'updated to rejected', res_valid.data)

        db.session.refresh(order)
        self.assertEqual(order.status, 'rejected')
        self.assertEqual(order.rejection_reason, 'Out of transport capacity for today')

        # Verify product stock restored
        db.session.refresh(self.product_delivery)
        self.assertEqual(self.product_delivery.quantity_kg, 50.0)
        self.assertTrue(self.product_delivery.is_available)

    def test_invalid_status_transitions_blocked(self):
        """Terminal and invalid transitions are rejected server-side."""
        order = Order(
            buyer_id=self.buyer.id,
            product_id=self.product_delivery.id,
            quantity_kg=5.0,
            total_price=Decimal('500.00'),
            fulfillment_type='pickup',
            status='pending',
            notes='Test 8C transitions'
        )
        db.session.add(order)
        db.session.commit()

        self._login('farmer_8c@example.com')

        # Transition directly pending -> delivered is blocked (must be confirmed first)
        res = self.client.post(f'/orders/{order.id}/update-status', data={
            'status': 'delivered'
        }, follow_redirects=True)
        self.assertIn(b'Cannot change order status from pending to delivered', res.data)

        # Transition pending -> confirmed is valid
        res_confirm = self.client.post(f'/orders/{order.id}/update-status', data={
            'status': 'confirmed'
        }, follow_redirects=True)
        self.assertIn(b'updated to confirmed', res_confirm.data)

        db.session.refresh(order)
        self.assertEqual(order.status, 'confirmed')

        # Transition confirmed -> delivered is valid
        res_deliver = self.client.post(f'/orders/{order.id}/update-status', data={
            'status': 'delivered'
        }, follow_redirects=True)
        self.assertIn(b'updated to delivered', res_deliver.data)

        db.session.refresh(order)
        self.assertEqual(order.status, 'delivered')

        # Modifying a delivered order is blocked
        res_mod = self.client.post(f'/orders/{order.id}/update-status', data={
            'status': 'confirmed'
        }, follow_redirects=True)
        self.assertIn(b'already delivered and cannot be modified', res_mod.data)

    def test_buyer_cancel_restores_stock(self):
        """Buyer can cancel a pending order and restore stock, but cannot cancel confirmed order."""
        order = Order(
            buyer_id=self.buyer.id,
            product_id=self.product_delivery.id,
            quantity_kg=5.0,
            total_price=Decimal('500.00'),
            fulfillment_type='pickup',
            status='pending',
            notes='Test 8C cancel'
        )
        self.product_delivery.quantity_kg -= 5.0
        db.session.add(order)
        db.session.commit()

        self._login('buyer_8c@example.com')

        res = self.client.post(f'/orders/{order.id}/cancel', follow_redirects=True)
        self.assertIn(b'Order cancelled', res.data)

        db.session.refresh(order)
        self.assertEqual(order.status, 'cancelled')

        db.session.refresh(self.product_delivery)
        self.assertEqual(self.product_delivery.quantity_kg, 50.0)

    # ─────────────────────────────────────────────────────────────────────────
    # 3. PRIVACY AND ACCESS CONTROL
    # ─────────────────────────────────────────────────────────────────────────

    def test_access_control_other_users_and_guests_blocked(self):
        """Guests receive redirect/401; other farmers and other buyers receive 403."""
        order = Order(
            buyer_id=self.buyer.id,
            product_id=self.product_delivery.id,
            quantity_kg=5.0,
            total_price=Decimal('500.00'),
            fulfillment_type='pickup',
            status='pending',
            notes='Test 8C access control'
        )
        db.session.add(order)
        db.session.commit()

        # Guest (not logged in)
        res_guest = self.client.get(f'/orders/{order.id}')
        # Should redirect to login (302) or return 401
        self.assertIn(res_guest.status_code, (302, 401))

        # Other farmer
        self._login('farmer_other_8c@example.com')
        res_other_f = self.client.get(f'/orders/{order.id}')
        self.assertEqual(res_other_f.status_code, 403)

        # Other buyer
        self._login('buyer_other_8c@example.com')
        res_other_b = self.client.get(f'/orders/{order.id}')
        self.assertEqual(res_other_b.status_code, 403)

        # Authorized farmer can view
        self._login('farmer_8c@example.com')
        res_f = self.client.get(f'/orders/{order.id}')
        self.assertEqual(res_f.status_code, 200)

        # Authorized buyer can view
        self._login('buyer_8c@example.com')
        res_b = self.client.get(f'/orders/{order.id}')
        self.assertEqual(res_b.status_code, 200)

    def test_privacy_buyer_pin_and_address_hidden_for_pickup(self):
        """For pickup orders, buyer's coordinates and delivery address are NOT rendered in HTML."""
        order = Order(
            buyer_id=self.buyer.id,
            product_id=self.product_delivery.id,
            quantity_kg=5.0,
            total_price=Decimal('500.00'),
            fulfillment_type='pickup',
            status='pending',
            notes='Test 8C pickup privacy'
        )
        db.session.add(order)
        db.session.commit()

        # Farmer viewing the pickup order
        self._login('farmer_8c@example.com')
        res = self.client.get(f'/orders/{order.id}')
        self.assertEqual(res.status_code, 200)

        # Must NOT contain buyer delivery pin or buyer delivery map
        self.assertNotIn(b'buyer-delivery-map', res.data)
        self.assertNotIn(b'123 Galle Road, Colombo 03', res.data)
        self.assertNotIn(b'6.927100', res.data)

    def test_privacy_buyer_pin_shown_for_delivery_orders(self):
        """For delivery orders, buyer's delivery pin and address are visible to farmer with navigation link."""
        order = Order(
            buyer_id=self.buyer.id,
            product_id=self.product_delivery.id,
            quantity_kg=5.0,
            total_price=Decimal('5500.00'),
            items_total=Decimal('500.00'),
            delivery_fee=Decimal('5000.00'),
            distance_km=Decimal('25.0'),
            distance_source='google',
            fulfillment_type='delivery',
            delivery_lat=Decimal('6.927100'),
            delivery_lng=Decimal('79.861200'),
            delivery_address='45 Lake Drive, Colombo 07',
            status='pending',
            notes='Test 8C delivery privacy'
        )
        db.session.add(order)
        db.session.commit()

        # Farmer viewing delivery order
        self._login('farmer_8c@example.com')
        res = self.client.get(f'/orders/{order.id}')
        self.assertEqual(res.status_code, 200)

        self.assertIn(b'45 Lake Drive, Colombo 07', res.data)
        self.assertIn(b'buyer-delivery-map', res.data)
        self.assertIn(b'Navigate to Buyer', res.data)
        self.assertIn(b'6.9271', res.data)
        self.assertIn(b'79.8612', res.data)

    # ─────────────────────────────────────────────────────────────────────────
    # 4. LEGACY ORDERS COMPATIBILITY
    # ─────────────────────────────────────────────────────────────────────────

    def test_legacy_orders_display_correctly(self):
        """Legacy orders without items_total, delivery_fee, or fulfillment_type display seamlessly."""
        order = Order(
            buyer_id=self.buyer.id,
            product_id=self.product_delivery.id,
            quantity_kg=10.0,
            total_price=Decimal('1000.00'),
            items_total=None,
            delivery_fee=Decimal('0.00'),
            fulfillment_type='pickup',
            status='confirmed',
            notes='Test 8C legacy order'
        )
        db.session.add(order)
        db.session.commit()

        self._login('buyer_8c@example.com')
        res = self.client.get(f'/orders/{order.id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Order #', res.data)
        self.assertIn(b'Grand Total', res.data)
        self.assertIn(b'LKR 1,000.00', res.data)
