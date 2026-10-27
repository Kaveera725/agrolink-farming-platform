"""Integration and unit tests for order price quotes and delivery estimation."""
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from unittest.mock import patch
from flask_wtf.csrf import generate_csrf

from app import create_app
from extensions import db, limiter
from models import User, Product, Order


class TestOrderQuote(unittest.TestCase):
    """Test POST /orders/quote endpoint according to Task 8B requirements."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        # Reset rate limits between tests
        limiter.reset()

        self.cleanup_emails = [
            'farmer_quote_8b@example.com',
            'farmer_nopin_8b@example.com',
            'buyer_quote_8b@example.com',
            'buyer_rate_8b@example.com',
        ]
        self._cleanup_data()
        self._seed_data()

    def tearDown(self):
        self._cleanup_data()
        self.ctx.pop()

    def _cleanup_data(self):
        Order.query.filter(Order.delivery_address.like('%Test 8B%')).delete(synchronize_session=False)
        Product.query.filter(Product.name.like('%8B Produce%')).delete(synchronize_session=False)
        for email in self.cleanup_emails:
            u = User.query.filter_by(email=email).first()
            if u:
                db.session.delete(u)
        db.session.commit()

    def _seed_data(self):
        # 1. Farmer with pin and delivery offered
        self.farmer = User(
            name='Dambulla Farmer',
            email='farmer_quote_8b@example.com',
            role='farmer',
            phone='0771234567',
            location='Matale',
            latitude=Decimal('7.873100'),
            longitude=Decimal('80.771800'),
            address_text='Dambulla Dedicated Economic Centre',
            location_updated_at=datetime.now(timezone.utc)
        )
        self.farmer.set_password('Password123!')

        # 2. Farmer without pin
        self.farmer_nopin = User(
            name='No Pin Farmer',
            email='farmer_nopin_8b@example.com',
            role='farmer',
            phone='0777654321',
            location='Kandy',
            latitude=None,
            longitude=None,
            address_text=None,
            location_updated_at=None
        )
        self.farmer_nopin.set_password('Password123!')

        # 3. Buyer
        self.buyer = User(
            name='Colombo Buyer',
            email='buyer_quote_8b@example.com',
            role='buyer',
            phone='0779998888',
            location='Colombo',
            latitude=Decimal('6.927100'),
            longitude=Decimal('79.861200'),
            address_text='Colombo Port City',
            location_updated_at=datetime.now(timezone.utc)
        )
        self.buyer.set_password('Password123!')

        db.session.add_all([self.farmer, self.farmer_nopin, self.buyer])
        db.session.commit()

        # Product with delivery enabled (stock 100 kg, price 200/kg)
        self.product_delivery = Product(
            farmer_id=self.farmer.id,
            name='8B Produce Fresh Tomatoes',
            category='Vegetables',
            quantity_kg=100.0,
            price_per_kg=200.0,
            location='Matale',
            offers_delivery=True,
            is_available=True,
            is_deleted=False
        )

        # Product with delivery disabled
        self.product_no_delivery = Product(
            farmer_id=self.farmer.id,
            name='8B Produce Bulk Onions',
            category='Vegetables',
            quantity_kg=100.0,
            price_per_kg=150.0,
            location='Matale',
            offers_delivery=False,
            is_available=True,
            is_deleted=False
        )

        # Product belonging to farmer without pin
        self.product_farmer_nopin = Product(
            farmer_id=self.farmer_nopin.id,
            name='8B Produce Unpinned Potatoes',
            category='Roots & Tubers',
            quantity_kg=50.0,
            price_per_kg=180.0,
            location='Kandy',
            offers_delivery=True,
            is_available=True,
            is_deleted=False
        )

        db.session.add_all([self.product_delivery, self.product_no_delivery, self.product_farmer_nopin])
        db.session.commit()

    def _login(self, email, password='Password123!'):
        return self.client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)

    def test_quote_for_pickup(self):
        """Pickup fulfillment returns fee 0.0, no distance, and grand_total = items_total."""
        self._login('buyer_quote_8b@example.com')

        res = self.client.post('/orders/quote', json={
            'product_id': self.product_delivery.id,
            'quantity': 10,
            'fulfillment_type': 'pickup'
        })

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['items_total'], 2000.0)
        self.assertIsNone(data['distance_km'])
        self.assertIsNone(data['distance_source'])
        self.assertEqual(data['delivery_fee'], 0.0)
        self.assertEqual(data['grand_total'], 2000.0)
        self.assertEqual(data['currency'], 'LKR')

    @patch('blueprints.orders.routes.get_driving_distance_km')
    def test_quote_delivery_under_50km(self, mock_distance):
        """Delivery <= 50 km incurs base fee (Rs 5,000)."""
        mock_distance.return_value = (Decimal('30.00'), 'google')
        self._login('buyer_quote_8b@example.com')

        res = self.client.post('/orders/quote', json={
            'product_id': self.product_delivery.id,
            'quantity': 10,
            'fulfillment_type': 'delivery',
            'delivery_lat': 7.6,
            'delivery_lng': 80.6
        })

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['items_total'], 2000.0)
        self.assertEqual(data['distance_km'], 30.0)
        self.assertEqual(data['distance_source'], 'google')
        self.assertEqual(data['delivery_fee'], 5000.0)
        self.assertEqual(data['grand_total'], 7000.0)

    @patch('blueprints.orders.routes.get_driving_distance_km')
    def test_quote_delivery_over_50km(self, mock_distance):
        """Delivery > 50 km (e.g. 72.3 km) incurs base fee + 60 * 23 = Rs 6,380."""
        mock_distance.return_value = (Decimal('72.30'), 'google')
        self._login('buyer_quote_8b@example.com')

        res = self.client.post('/orders/quote', json={
            'product_id': self.product_delivery.id,
            'quantity': 10,
            'fulfillment_type': 'delivery',
            'delivery_lat': 7.29,
            'delivery_lng': 80.63
        })

        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['items_total'], 2000.0)
        self.assertEqual(data['distance_km'], 72.3)
        self.assertEqual(data['delivery_fee'], 6380.0)
        self.assertEqual(data['grand_total'], 8380.0)

    def test_quote_delivery_not_offered(self):
        """Product without delivery enabled returns 422 when requesting delivery."""
        self._login('buyer_quote_8b@example.com')

        res = self.client.post('/orders/quote', json={
            'product_id': self.product_no_delivery.id,
            'quantity': 10,
            'fulfillment_type': 'delivery',
            'delivery_lat': 7.29,
            'delivery_lng': 80.63
        })

        self.assertEqual(res.status_code, 422)
        data = res.get_json()
        self.assertIn('error', data)
        self.assertIn('not offered', data['error'].lower())

    def test_quote_farmer_without_pin(self):
        """Product whose farmer has no map pin returns 422 for delivery quote."""
        self._login('buyer_quote_8b@example.com')

        res = self.client.post('/orders/quote', json={
            'product_id': self.product_farmer_nopin.id,
            'quantity': 5,
            'fulfillment_type': 'delivery',
            'delivery_lat': 7.29,
            'delivery_lng': 80.63
        })

        self.assertEqual(res.status_code, 422)
        data = res.get_json()
        self.assertIn('error', data)
        self.assertIn('pickup location pin', data['error'].lower())

    def test_quote_quantity_above_stock(self):
        """Quantity exceeding available stock returns 422."""
        self._login('buyer_quote_8b@example.com')

        res = self.client.post('/orders/quote', json={
            'product_id': self.product_delivery.id,
            'quantity': 150,  # Max available is 100
            'fulfillment_type': 'pickup'
        })

        self.assertEqual(res.status_code, 422)
        data = res.get_json()
        self.assertIn('exceeds available stock', data['error'].lower())

    def test_quote_out_of_bounds_coordinates(self):
        """Coordinates outside Sri Lanka return 422."""
        self._login('buyer_quote_8b@example.com')

        res = self.client.post('/orders/quote', json={
            'product_id': self.product_delivery.id,
            'quantity': 5,
            'fulfillment_type': 'delivery',
            'delivery_lat': 51.5074,  # London
            'delivery_lng': -0.1278
        })

        self.assertEqual(res.status_code, 422)
        data = res.get_json()
        self.assertIn('sri lanka', data['error'].lower())

    def test_quote_farmer_role_forbidden(self):
        """Farmers attempting to access buyer quote endpoint receive 403 Forbidden."""
        self._login('farmer_quote_8b@example.com')

        res = self.client.post('/orders/quote', json={
            'product_id': self.product_delivery.id,
            'quantity': 5,
            'fulfillment_type': 'pickup'
        })

        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertIn('error', data)

    def test_quote_rate_limiting_present(self):
        """Rate limit enforces ~20 requests per minute per user."""
        self._login('buyer_quote_8b@example.com')

        # Run 20 requests
        for _ in range(20):
            res = self.client.post('/orders/quote', json={
                'product_id': self.product_delivery.id,
                'quantity': 1,
                'fulfillment_type': 'pickup'
            })
            self.assertEqual(res.status_code, 200)

        # 21st request should be throttled
        res_throttled = self.client.post('/orders/quote', json={
            'product_id': self.product_delivery.id,
            'quantity': 1,
            'fulfillment_type': 'pickup'
        })
        self.assertEqual(res_throttled.status_code, 429)

    def test_quote_csrf_required(self):
        """When CSRF is enabled, requests without X-CSRFToken header are rejected with 400."""
        import re
        csrf_app = create_app()
        csrf_app.config['TESTING'] = True
        csrf_app.config['WTF_CSRF_ENABLED'] = True
        c_client = csrf_app.test_client()

        # 1. Fetch login page to get CSRF token
        get_res = c_client.get('/auth/login')
        self.assertEqual(get_res.status_code, 200)
        html = get_res.data.decode('utf-8')
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(match)
        login_token = match.group(1)

        # 2. Login buyer with the CSRF token
        login_res = c_client.post('/auth/login', data={
            'email': 'buyer_quote_8b@example.com',
            'password': 'Password123!',
            'csrf_token': login_token
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        # 3. Request without CSRF token header should fail with 400
        res_no_csrf = c_client.post('/orders/quote', json={
            'product_id': self.product_delivery.id,
            'quantity': 5,
            'fulfillment_type': 'pickup'
        })
        self.assertEqual(res_no_csrf.status_code, 400)

        # 4. Fetch page to extract active session CSRF token from meta tag
        dash_res = c_client.get('/marketplace/')
        dash_html = dash_res.data.decode('utf-8')
        meta_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', dash_html)
        dash_token = meta_match.group(1) if meta_match else login_token

        res_with_csrf = c_client.post(
            '/orders/quote',
            headers={'X-CSRFToken': dash_token},
            json={
                'product_id': self.product_delivery.id,
                'quantity': 5,
                'fulfillment_type': 'pickup'
            }
        )
        self.assertEqual(res_with_csrf.status_code, 200)


if __name__ == '__main__':
    unittest.main()
