"""
Comprehensive test suite verifying failure handling across the delivery feature.
Ensures friendly error messages and status codes (never 500):
1. Routes API down (graceful fallback to estimated)
2. Missing server key (graceful fallback to estimated)
3. Invalid coordinates (friendly validation error)
4. Delivery requested for product not offering delivery (friendly error)
5. Farmer without saved location pin (friendly error linking to profile)
6. Quantity above available stock (friendly error)
"""
import unittest
from unittest.mock import patch
import requests
from decimal import Decimal

from app import create_app
from extensions import db
from models import User, Product, Order
from services.distance import get_driving_distance_km

class TestDeliveryFailures(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

        self.ctx = self.app.app_context()
        self.ctx.push()

        # Seed test users
        self.farmer_with_pin = User(
            name="Farmer Pin Test",
            email="farmer_pin_test@agrolink.lk",
            phone="0771112222",
            role="farmer",
            location="Colombo",
            latitude=6.9271,
            longitude=79.8612
        )
        self.farmer_with_pin.set_password("password123")

        self.farmer_no_pin = User(
            name="Farmer No Pin Test",
            email="farmer_nopin_test@agrolink.lk",
            phone="0773334444",
            role="farmer",
            location="Kandy",
            latitude=None,
            longitude=None
        )
        self.farmer_no_pin.set_password("password123")

        self.buyer = User(
            name="Buyer Test",
            email="buyer_fail_test@agrolink.lk",
            phone="0775556666",
            role="buyer",
            location="Colombo"
        )
        self.buyer.set_password("password123")

        db.session.add_all([self.farmer_with_pin, self.farmer_no_pin, self.buyer])
        db.session.commit()

        # Seed test products
        self.prod_delivery = Product(
            farmer_id=self.farmer_with_pin.id,
            name="Delivery Carrots",
            category="vegetables",
            price_per_kg=250.0,
            quantity_kg=20.0,
            offers_delivery=True,
            is_available=True
        )

        self.prod_no_delivery = Product(
            farmer_id=self.farmer_with_pin.id,
            name="Pickup Only Cabbage",
            category="vegetables",
            price_per_kg=150.0,
            quantity_kg=30.0,
            offers_delivery=False,
            is_available=True
        )

        self.prod_farmer_no_pin = Product(
            farmer_id=self.farmer_no_pin.id,
            name="Leeks No Farmer Pin",
            category="vegetables",
            price_per_kg=200.0,
            quantity_kg=25.0,
            offers_delivery=True,
            is_available=True
        )

        db.session.add_all([self.prod_delivery, self.prod_no_delivery, self.prod_farmer_no_pin])
        db.session.commit()

    def tearDown(self):
        Order.query.filter(Order.buyer_id == self.buyer.id).delete()
        Product.query.filter(Product.farmer_id.in_([self.farmer_with_pin.id, self.farmer_no_pin.id])).delete()
        User.query.filter(User.id.in_([self.farmer_with_pin.id, self.farmer_no_pin.id, self.buyer.id])).delete()
        db.session.commit()
        self.ctx.pop()

    def _login_buyer(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.buyer.id)
            sess['_fresh'] = True

    # 1. Routes API Down -> Graceful fallback to estimated
    def test_routes_api_down_fallback(self):
        """When Routes API raises RequestException or returns 500, distance gracefully falls back to estimated."""
        with patch('requests.post', side_effect=requests.RequestException("Google Routes API connection error")):
            dist, source = get_driving_distance_km(6.9271, 79.8612, 6.8400, 79.8700)
            self.assertEqual(source, "estimated")
            self.assertGreater(dist, 0)

        self._login_buyer()
        with patch('requests.post', side_effect=requests.RequestException("Google Routes API timeout")):
            res = self.client.post('/orders/quote', json={
                'product_id': self.prod_delivery.id,
                'quantity': 5,
                'fulfillment_type': 'delivery',
                'delivery_lat': 6.8400,
                'delivery_lng': 79.8700
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data['distance_source'], 'estimated')
            self.assertIn('Estimated', data['message'])

    # 2. Missing Server Key -> Graceful fallback to estimated
    def test_missing_server_key_fallback(self):
        """When GOOGLE_MAPS_SERVER_KEY is missing or empty, distance falls back without error."""
        with patch('services.distance.get_server_key', return_value=''):
            dist, source = get_driving_distance_km(6.9271, 79.8612, 6.8400, 79.8700)
            self.assertEqual(source, "estimated")
            self.assertGreater(dist, 0)

        self._login_buyer()
        with patch('services.distance.get_server_key', return_value=''):
            res = self.client.post('/orders/quote', json={
                'product_id': self.prod_delivery.id,
                'quantity': 5,
                'fulfillment_type': 'delivery',
                'delivery_lat': 6.8400,
                'delivery_lng': 79.8700
            })
            self.assertEqual(res.status_code, 200)
            data = res.get_json()
            self.assertEqual(data['distance_source'], 'estimated')

    # 3. Invalid Coordinates -> Friendly message, never 500
    def test_invalid_coordinates_handled_friendly(self):
        """Invalid coordinates (non-numeric, outside bounds, null) return 400/422 with friendly message."""
        self._login_buyer()
        
        # Outside Sri Lanka (London coords)
        res_outside = self.client.post('/orders/quote', json={
            'product_id': self.prod_delivery.id,
            'quantity': 5,
            'fulfillment_type': 'delivery',
            'delivery_lat': 51.5074,
            'delivery_lng': -0.1278
        })
        self.assertEqual(res_outside.status_code, 422)
        self.assertIn('Sri Lanka', res_outside.get_json()['error'])

        # Garbage string coords
        res_str = self.client.post('/orders/quote', json={
            'product_id': self.prod_delivery.id,
            'quantity': 5,
            'fulfillment_type': 'delivery',
            'delivery_lat': "invalid_lat",
            'delivery_lng': "invalid_lng"
        })
        self.assertEqual(res_str.status_code, 400)
        self.assertIn('Valid delivery latitude', res_str.get_json()['error'])

        # Missing coords on order placement
        res_place = self.client.post(f'/orders/place/{self.prod_delivery.id}', data={
            'quantity_kg': '5',
            'fulfillment_type': 'delivery',
            'delivery_address': 'Some road',
            'delivery_lat': '',
            'delivery_lng': ''
        }, follow_redirects=True)
        self.assertEqual(res_place.status_code, 200)
        self.assertIn(b'Valid delivery location within Sri Lanka is required', res_place.data)

    # 4. Delivery for product that doesn't offer it -> Friendly message, never 500
    def test_product_not_offering_delivery_handled_friendly(self):
        """Requesting delivery on product with offers_delivery=False returns friendly error."""
        self._login_buyer()
        
        # Quote endpoint
        res = self.client.post('/orders/quote', json={
            'product_id': self.prod_no_delivery.id,
            'quantity': 5,
            'fulfillment_type': 'delivery',
            'delivery_lat': 6.8400,
            'delivery_lng': 79.8700
        })
        self.assertEqual(res.status_code, 422)
        self.assertIn('Delivery is not offered for this product', res.get_json()['error'])

        # Place order endpoint
        res_place = self.client.post(f'/orders/place/{self.prod_no_delivery.id}', data={
            'quantity_kg': '5',
            'fulfillment_type': 'delivery',
            'delivery_address': 'Colombo Address',
            'delivery_lat': '6.8400',
            'delivery_lng': '79.8700'
        }, follow_redirects=True)
        self.assertEqual(res_place.status_code, 200)
        self.assertIn(b'Delivery is not offered for this product', res_place.data)

    # 5. Farmer without pin -> Friendly message, never 500
    def test_farmer_without_pin_handled_friendly(self):
        """If farmer lacks saved pin, quote and place order return friendly message."""
        self._login_buyer()

        # Quote endpoint
        res = self.client.post('/orders/quote', json={
            'product_id': self.prod_farmer_no_pin.id,
            'quantity': 5,
            'fulfillment_type': 'delivery',
            'delivery_lat': 6.8400,
            'delivery_lng': 79.8700
        })
        self.assertEqual(res.status_code, 422)
        self.assertIn('Farmer has not set a pickup location pin', res.get_json()['error'])

        # Place order endpoint
        res_place = self.client.post(f'/orders/place/{self.prod_farmer_no_pin.id}', data={
            'quantity_kg': '5',
            'fulfillment_type': 'delivery',
            'delivery_address': 'Colombo Address',
            'delivery_lat': '6.8400',
            'delivery_lng': '79.8700'
        }, follow_redirects=True)
        self.assertEqual(res_place.status_code, 200)
        self.assertIn(b'Farmer pickup location is missing', res_place.data)

    # 6. Quantity above stock -> Friendly message, never 500
    def test_quantity_above_stock_handled_friendly(self):
        """Requesting quantity greater than available stock returns friendly error."""
        self._login_buyer()

        # Quote endpoint
        res = self.client.post('/orders/quote', json={
            'product_id': self.prod_delivery.id,
            'quantity': 999,
            'fulfillment_type': 'delivery',
            'delivery_lat': 6.8400,
            'delivery_lng': 79.8700
        })
        self.assertEqual(res.status_code, 422)
        self.assertIn('exceeds available stock', res.get_json()['error'])

        # Place order endpoint
        res_place = self.client.post(f'/orders/place/{self.prod_delivery.id}', data={
            'quantity_kg': '999',
            'fulfillment_type': 'delivery',
            'delivery_address': 'Colombo Address',
            'delivery_lat': '6.8400',
            'delivery_lng': '79.8700'
        }, follow_redirects=True)
        self.assertEqual(res_place.status_code, 200)
        self.assertIn(b'Stock changed: only 20 kg available', res_place.data)


if __name__ == '__main__':
    unittest.main()
