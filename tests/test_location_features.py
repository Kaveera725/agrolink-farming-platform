"""
Integration and unit tests for Task 7C:
- Haversine distance & formatting against known Sri Lankan cities (Colombo to Kandy ~94 km).
- Farmer dashboard location update endpoint (/dashboard/update-location):
  auth required, farmer role only, CSRF protection, Sri Lanka bounds validation.
- Nearest sorting in marketplace (closest first, unpinned farmers last).
- Privacy rules:
  - Guest page source never contains coordinates (marketplace and product detail).
  - Buyer's pin visible only to the farmer of that order on order detail page.
  - Marketplace pages never expose raw coordinates.
  - Marketplace does not load Google Maps JS.
"""
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from flask_wtf.csrf import generate_csrf
from app import create_app
from extensions import db
from models import User, Product, Order
from utils.geo import haversine_km, format_distance_km, is_in_sri_lanka


class TestLocationFeatures(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.cleanup_emails = [
            'farmer_colombo_7c@example.com',
            'farmer_kandy_7c@example.com',
            'farmer_nopin_7c@example.com',
            'buyer_colombo_7c@example.com',
            'buyer_nopin_7c@example.com',
            'other_farmer_7c@example.com'
        ]
        self._cleanup_data()
        self._seed_data()

    def tearDown(self):
        self._cleanup_data()
        self.ctx.pop()

    def _cleanup_data(self):
        Order.query.filter(Order.delivery_address.like('%Test 7C%')).delete(synchronize_session=False)
        Product.query.filter(Product.name.like('%7C Produce%')).delete(synchronize_session=False)
        for email in self.cleanup_emails:
            u = User.query.filter_by(email=email).first()
            if u:
                db.session.delete(u)
        db.session.commit()

    def _seed_data(self):
        # 1. Farmer in Colombo (lat 6.9271, lng 79.8612)
        self.farmer_colombo = User(
            name='Colombo Farmer',
            email='farmer_colombo_7c@example.com',
            role='farmer',
            phone='0771111111',
            location='Colombo',
            latitude=Decimal('6.927100'),
            longitude=Decimal('79.861200'),
            address_text='Pettah Market, Colombo',
            location_updated_at=datetime.now(timezone.utc)
        )
        self.farmer_colombo.set_password('Password123!')

        # 2. Farmer in Kandy (lat 7.2906, lng 80.6337)
        self.farmer_kandy = User(
            name='Kandy Farmer',
            email='farmer_kandy_7c@example.com',
            role='farmer',
            phone='0772222222',
            location='Kandy',
            latitude=Decimal('7.290600'),
            longitude=Decimal('80.633700'),
            address_text='Peradeniya Road, Kandy',
            location_updated_at=datetime.now(timezone.utc)
        )
        self.farmer_kandy.set_password('Password123!')

        # 3. Farmer without pin
        self.farmer_nopin = User(
            name='No Pin Farmer',
            email='farmer_nopin_7c@example.com',
            role='farmer',
            phone='0773333333',
            location='Anuradhapura',
            latitude=None,
            longitude=None,
            address_text=None,
            location_updated_at=None
        )
        self.farmer_nopin.set_password('Password123!')

        # 4. Buyer in Colombo (lat 6.9319, lng 79.8478 - ~1.6 km from Pettah)
        self.buyer_colombo = User(
            name='Colombo Buyer',
            email='buyer_colombo_7c@example.com',
            role='buyer',
            phone='0774444444',
            location='Colombo',
            latitude=Decimal('6.931900'),
            longitude=Decimal('79.847800'),
            address_text='Fort, Colombo',
            location_updated_at=datetime.now(timezone.utc)
        )
        self.buyer_colombo.set_password('Password123!')

        # 5. Buyer without pin
        self.buyer_nopin = User(
            name='No Pin Buyer',
            email='buyer_nopin_7c@example.com',
            role='buyer',
            phone='0775555555',
            location='Galle',
            latitude=None,
            longitude=None,
            address_text=None,
            location_updated_at=None
        )
        self.buyer_nopin.set_password('Password123!')

        # 6. Another farmer (to test order privacy)
        self.other_farmer = User(
            name='Other Farmer',
            email='other_farmer_7c@example.com',
            role='farmer',
            phone='0776666666',
            location='Kurunegala',
            latitude=Decimal('7.486300'),
            longitude=Decimal('80.362300'),
            address_text='Dambulla Road, Kurunegala',
            location_updated_at=datetime.now(timezone.utc)
        )
        self.other_farmer.set_password('Password123!')

        db.session.add_all([
            self.farmer_colombo,
            self.farmer_kandy,
            self.farmer_nopin,
            self.buyer_colombo,
            self.buyer_nopin,
            self.other_farmer
        ])
        db.session.commit()

        # Seed products for each farmer
        self.p_colombo = Product(
            farmer_id=self.farmer_colombo.id,
            name='7C Produce Colombo Cabbage',
            category='Vegetables',
            quantity_kg=100.0,
            price_per_kg=150.0,
            location='Colombo',
            is_available=True,
            is_deleted=False
        )
        self.p_kandy = Product(
            farmer_id=self.farmer_kandy.id,
            name='7C Produce Kandy Carrots',
            category='Vegetables',
            quantity_kg=100.0,
            price_per_kg=160.0,
            location='Kandy',
            is_available=True,
            is_deleted=False
        )
        self.p_nopin = Product(
            farmer_id=self.farmer_nopin.id,
            name='7C Produce Anuradhapura Rice',
            category='Grains & Rice',
            quantity_kg=100.0,
            price_per_kg=140.0,
            location='Anuradhapura',
            is_available=True,
            is_deleted=False
        )
        db.session.add_all([self.p_colombo, self.p_kandy, self.p_nopin])
        db.session.commit()

    def _login(self, email, password='Password123!'):
        self.client.get('/auth/logout', follow_redirects=True)
        return self.client.post('/auth/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    # ──────────────────────────────────────────────────────────────────────────
    # 1. HAVERSINE & DISTANCE FORMATTING TESTS
    # ──────────────────────────────────────────────────────────────────────────
    def test_haversine_colombo_to_kandy(self):
        """Colombo (6.9271, 79.8612) to Kandy (7.2906, 80.6337) is approx 94 km."""
        dist = haversine_km(6.9271, 79.8612, 7.2906, 80.6337)
        self.assertAlmostEqual(dist, 94.34, delta=1.5)
        self.assertEqual(round(dist), 94)

    def test_distance_formatting_rules(self):
        """Under 10 km has 1 decimal place; 10 km and above shows nearest whole km."""
        self.assertEqual(format_distance_km(0.52), "0.5 km")
        self.assertEqual(format_distance_km(4.24), "4.2 km")
        self.assertEqual(format_distance_km(9.88), "9.9 km")
        self.assertEqual(format_distance_km(10.0), "10 km")
        self.assertEqual(format_distance_km(12.4), "12 km")
        self.assertEqual(format_distance_km(94.335), "94 km")
        self.assertIsNone(format_distance_km(None))

    # ──────────────────────────────────────────────────────────────────────────
    # 2. FARMER UPDATE LOCATION ENDPOINT TESTS
    # ──────────────────────────────────────────────────────────────────────────
    def test_update_location_requires_authentication(self):
        """Unauthenticated requests to /dashboard/update-location are redirected."""
        res = self.client.post('/dashboard/update-location', json={
            'latitude': 6.9271,
            'longitude': 79.8612
        })
        self.assertEqual(res.status_code, 302)

    def test_update_location_requires_farmer_role(self):
        """Buyers are forbidden (403) from accessing /dashboard/update-location."""
        self._login('buyer_colombo_7c@example.com')
        res = self.client.post('/dashboard/update-location', json={
            'latitude': 6.9271,
            'longitude': 79.8612
        })
        self.assertEqual(res.status_code, 403)

    def test_update_location_bounds_validation(self):
        """Coordinates outside Sri Lanka are rejected with HTTP 400."""
        self._login('farmer_colombo_7c@example.com')
        # Out-of-bounds latitude (e.g. London 51.5)
        res = self.client.post('/dashboard/update-location', json={
            'latitude': 51.5074,
            'longitude': -0.1278
        })
        self.assertEqual(res.status_code, 400)
        data = res.get_json()
        self.assertFalse(data.get('success'))
        self.assertIn('within Sri Lanka', data.get('error', ''))

    def test_update_location_valid_update_succeeds(self):
        """Valid Sri Lanka coordinates update farmer location and location_updated_at."""
        self._login('farmer_colombo_7c@example.com')
        res = self.client.post('/dashboard/update-location', json={
            'latitude': 6.9350,
            'longitude': 79.8500
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('time_ago', data)

        farmer = User.query.filter_by(email='farmer_colombo_7c@example.com').first()
        self.assertAlmostEqual(float(farmer.latitude), 6.9350, places=4)
        self.assertAlmostEqual(float(farmer.longitude), 79.8500, places=4)
        self.assertIsNotNone(farmer.location_updated_at)

    def test_update_location_csrf_enforcement(self):
        """When CSRF is enabled, requests without valid CSRF header are rejected."""
        import re
        csrf_app = create_app()
        csrf_app.config['TESTING'] = True
        csrf_app.config['WTF_CSRF_ENABLED'] = True
        c_client = csrf_app.test_client()

        # 1. Fetch login page to initialize session and extract CSRF token
        get_res = c_client.get('/auth/login')
        self.assertEqual(get_res.status_code, 200)
        html = get_res.data.decode('utf-8')
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        self.assertIsNotNone(match, "CSRF token must be present in login form")
        token = match.group(1)

        # 2. Login farmer with the CSRF token
        login_res = c_client.post('/auth/login', data={
            'email': 'farmer_colombo_7c@example.com',
            'password': 'Password123!',
            'csrf_token': token
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        # 3. Attempt POST without X-CSRFToken header -> should be 400 Bad Request
        res_no_token = c_client.post('/dashboard/update-location', json={
            'latitude': 6.9271,
            'longitude': 79.8612
        })
        self.assertEqual(res_no_token.status_code, 400)

        # 4. Fetch dashboard or use token in header -> should be 200 OK
        dash_res = c_client.get('/dashboard/')
        dash_html = dash_res.data.decode('utf-8')
        meta_match = re.search(r'<meta name="csrf-token" content="([^"]+)"', dash_html)
        dash_token = meta_match.group(1) if meta_match else token

        res_with_token = c_client.post(
            '/dashboard/update-location',
            json={'latitude': 6.9271, 'longitude': 79.8612},
            headers={'X-CSRFToken': dash_token}
        )
        self.assertEqual(res_with_token.status_code, 200)
        self.assertTrue(res_with_token.get_json().get('success'))

    # ──────────────────────────────────────────────────────────────────────────
    # 3. MARKETPLACE NEAREST FIRST SORTING TESTS
    # ──────────────────────────────────────────────────────────────────────────
    def test_nearest_sorting_for_buyer_with_pin(self):
        """A buyer in Colombo sorting by nearest sees Colombo product first, Kandy second, unpinned last."""
        self._login('buyer_colombo_7c@example.com')
        res = self.client.get('/marketplace/?sort=nearest&search=7C+Produce')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # Colombo product should appear before Kandy product
        pos_colombo = html.find('7C Produce Colombo Cabbage')
        pos_kandy = html.find('7C Produce Kandy Carrots')
        pos_nopin = html.find('7C Produce Anuradhapura Rice')

        self.assertNotEqual(pos_colombo, -1)
        self.assertNotEqual(pos_kandy, -1)
        self.assertNotEqual(pos_nopin, -1)

        self.assertLess(pos_colombo, pos_kandy, "Colombo product must appear before Kandy product")
        self.assertLess(pos_kandy, pos_nopin, "Kandy product must appear before unpinned farmer product")

    def test_nearest_sorting_for_user_without_pin(self):
        """A user without pin sorting by nearest sees pinned farmers first and unpinned farmers last."""
        self._login('buyer_nopin_7c@example.com')
        res = self.client.get('/marketplace/?sort=nearest&search=7C+Produce')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        pos_colombo = html.find('7C Produce Colombo Cabbage')
        pos_kandy = html.find('7C Produce Kandy Carrots')
        pos_nopin = html.find('7C Produce Anuradhapura Rice')

        self.assertLess(pos_colombo, pos_nopin)
        self.assertLess(pos_kandy, pos_nopin)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. PRIVACY RULES TESTS
    # ──────────────────────────────────────────────────────────────────────────
    def test_guest_cannot_see_coordinates_in_marketplace_html(self):
        """Unauthenticated guests never see raw coordinates in marketplace page source."""
        res = self.client.get('/marketplace/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # Neither latitude nor longitude nor raw coordinate numbers should be present
        self.assertNotIn('79.8612', html)
        self.assertNotIn('80.6337', html)
        self.assertNotIn('latitude', html)
        self.assertNotIn('longitude', html)

    def test_guest_cannot_see_coordinates_in_product_detail_html(self):
        """Guests viewing product detail see district and login prompt, with NO coordinates in HTML source."""
        res = self.client.get(f'/marketplace/product/{self.p_colombo.id}')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        self.assertIn('Log in to see the map', html)
        self.assertIn('Colombo', html)
        # Verify strict absence of coordinates
        self.assertNotIn('79.8612', html)
        self.assertNotIn('6.9271', html)
        self.assertNotIn('maps.google.com', html)

    def test_marketplace_never_exposes_raw_coordinates_to_buyer(self):
        """Marketplace cards show rounded distance ('approx. X km away'), never coordinates."""
        self._login('buyer_colombo_7c@example.com')
        res = self.client.get('/marketplace/?search=7C+Produce')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        self.assertIn('approx.', html)
        self.assertIn('km away', html)
        self.assertNotIn('6.9271', html)
        self.assertNotIn('79.8612', html)

    def test_buyer_without_pin_sees_set_location_prompt(self):
        """Authenticated buyers without pin see 'Set your location to see distances' link."""
        self._login('buyer_nopin_7c@example.com')
        res = self.client.get('/marketplace/?search=7C+Produce')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        self.assertIn('Set your location to see distances', html)

    def test_marketplace_page_does_not_load_maps_js(self):
        """Cost & performance rule: marketplace listing must not load maps-loader.js or maps script."""
        res = self.client.get('/marketplace/')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        self.assertNotIn('maps-loader.js', html)
        self.assertNotIn('maps.googleapis.com', html)

    def test_order_buyer_pin_visible_only_to_order_farmer(self):
        """Buyer's pin on order detail is visible ONLY to the farmer of that order."""
        # Create an order placed by buyer_colombo for p_colombo
        order = Order(
            buyer_id=self.buyer_colombo.id,
            product_id=self.p_colombo.id,
            quantity_kg=10.0,
            total_price=1500.0,
            delivery_address='Test 7C Order Delivery Address',
            status='pending'
        )
        db.session.add(order)
        db.session.commit()

        # 1. View order as the seller farmer (farmer_colombo)
        self._login('farmer_colombo_7c@example.com')
        res_farmer = self.client.get(f'/orders/{order.id}')
        self.assertEqual(res_farmer.status_code, 200)
        html_farmer = res_farmer.data.decode('utf-8')
        # Farmer should see buyer's delivery pin
        self.assertIn('Buyer Delivery Pin', html_farmer)
        self.assertIn(str(self.buyer_colombo.latitude), html_farmer)

        # 2. View order as the buyer (buyer_colombo)
        self._login('buyer_colombo_7c@example.com')
        res_buyer = self.client.get(f'/orders/{order.id}')
        self.assertEqual(res_buyer.status_code, 200)
        html_buyer = res_buyer.data.decode('utf-8')
        # Buyer sees the farmer's pin, but buyer's card does NOT leak raw Buyer Delivery Pin section
        self.assertNotIn('Buyer Delivery Pin', html_buyer)
        self.assertIn('Farm Pin Location', html_buyer)

        # 3. View order as another farmer (other_farmer)
        self._login('other_farmer_7c@example.com')
        res_other = self.client.get(f'/orders/{order.id}')
        # Should be access denied (redirects to orders.index)
        self.assertEqual(res_other.status_code, 302)


if __name__ == '__main__':
    unittest.main()
