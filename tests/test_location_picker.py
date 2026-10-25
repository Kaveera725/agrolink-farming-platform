"""
Unit and integration tests for location picker, coordinate validation,
and location persistence across registration, profile, and dashboard.
"""
from decimal import Decimal
import unittest
from app import create_app
from extensions import db
from models import User


class TestLocationPicker(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        # Clean up test users if existing
        self.cleanup_emails = [
            'farmer_valid_pin@example.com',
            'farmer_nopin@example.com',
            'farmer_outofrange@example.com',
            'farmer_tampered@example.com',
            'buyer_nopin@example.com',
            'buyer_valid_pin@example.com',
            'profile_geo_farmer@example.com'
        ]
        self._cleanup_users()

    def tearDown(self):
        self._cleanup_users()
        self.ctx.pop()

    def _cleanup_users(self):
        for email in self.cleanup_emails:
            u = User.query.filter_by(email=email).first()
            if u:
                db.session.delete(u)
        db.session.commit()

    def test_farmer_registration_with_valid_pin_succeeds(self):
        """A farmer registering with a valid Sri Lankan pin is saved with location_updated_at."""
        res = self.client.post('/auth/register', data={
            'name': 'Valid Pin Farmer',
            'email': 'farmer_valid_pin@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'farmer',
            'whatsapp_number': '0771234567',
            'phone': '0112345678',
            'location': 'Kandy',
            'latitude': '7.290572',
            'longitude': '80.633726',
            'address_text': 'Peradeniya Road, Kandy'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        user = User.query.filter_by(email='farmer_valid_pin@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.latitude, Decimal('7.290572'))
        self.assertEqual(user.longitude, Decimal('80.633726'))
        self.assertEqual(user.address_text, 'Peradeniya Road, Kandy')
        self.assertIsNotNone(user.location_updated_at)

    def test_farmer_registration_without_pin_rejected(self):
        """A farmer attempting to register without a pin is rejected with a friendly message."""
        res = self.client.post('/auth/register', data={
            'name': 'No Pin Farmer',
            'email': 'farmer_nopin@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'farmer',
            'whatsapp_number': '0771234567',
            'location': 'Kandy',
            'latitude': '',
            'longitude': '',
            'address_text': ''
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Farmers must pin their farm location on the map', res.data)
        # Verify user was not created
        user = User.query.filter_by(email='farmer_nopin@example.com').first()
        self.assertIsNone(user)

    def test_farmer_registration_out_of_range_coords_rejected(self):
        """Coordinates outside Sri Lanka (e.g. lat 15.5) must be rejected."""
        res = self.client.post('/auth/register', data={
            'name': 'Out of Bounds Farmer',
            'email': 'farmer_outofrange@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'farmer',
            'whatsapp_number': '0771234567',
            'location': 'Kandy',
            'latitude': '15.500000',
            'longitude': '80.600000',
            'address_text': 'Outside Sri Lanka'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Location must be within Sri Lanka', res.data)
        user = User.query.filter_by(email='farmer_outofrange@example.com').first()
        self.assertIsNone(user)

    def test_tampered_hidden_fields_rejected(self):
        """Tampered non-numeric hidden coordinates must be rejected cleanly."""
        res = self.client.post('/auth/register', data={
            'name': 'Tampered Farmer',
            'email': 'farmer_tampered@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'farmer',
            'whatsapp_number': '0771234567',
            'location': 'Kandy',
            'latitude': 'DROP TABLE users;',
            'longitude': 'not-a-number',
            'address_text': 'Attack attempt'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Invalid coordinates provided', res.data)
        user = User.query.filter_by(email='farmer_tampered@example.com').first()
        self.assertIsNone(user)

    def test_buyer_registration_without_pin_succeeds(self):
        """Buyer registration without a pin succeeds with null coordinates."""
        res = self.client.post('/auth/register', data={
            'name': 'Pin-free Buyer',
            'email': 'buyer_nopin@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'buyer',
            'whatsapp_number': '0779876543',
            'location': 'Colombo',
            'latitude': '',
            'longitude': '',
            'address_text': ''
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        user = User.query.filter_by(email='buyer_nopin@example.com').first()
        self.assertIsNotNone(user)
        self.assertIsNone(user.latitude)
        self.assertIsNone(user.longitude)
        self.assertIsNone(user.address_text)
        self.assertIsNone(user.location_updated_at)

    def test_buyer_registration_with_valid_pin_succeeds(self):
        """Buyer registration with an optional pin succeeds and saves coordinates."""
        res = self.client.post('/auth/register', data={
            'name': 'Pinned Buyer',
            'email': 'buyer_valid_pin@example.com',
            'password': 'Password123!',
            'confirm_password': 'Password123!',
            'role': 'buyer',
            'whatsapp_number': '0779876543',
            'location': 'Colombo',
            'latitude': '6.927079',
            'longitude': '79.861244',
            'address_text': 'Galle Face Green, Colombo'
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        user = User.query.filter_by(email='buyer_valid_pin@example.com').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.latitude, Decimal('6.927079'))
        self.assertEqual(user.longitude, Decimal('79.861244'))
        self.assertEqual(user.address_text, 'Galle Face Green, Colombo')
        self.assertIsNotNone(user.location_updated_at)

    def test_profile_edit_and_overview_mini_map(self):
        """Editing profile to add a pin updates coordinates, timestamp, and profile overview."""
        user = User(
            name='Profile Farmer',
            email='profile_geo_farmer@example.com',
            role='farmer',
            whatsapp_number='+94771234567',
            location='Matale'
        )
        user.set_password('Password123!')
        db.session.add(user)
        db.session.commit()

        # Login
        self.client.post('/auth/login', data={
            'email': 'profile_geo_farmer@example.com',
            'password': 'Password123!'
        }, follow_redirects=True)

        # Before pin: Profile overview has Empty State
        view_res = self.client.get('/profile')
        self.assertEqual(view_res.status_code, 200)
        self.assertIn(b'No Location Pinned Yet', view_res.data)
        self.assertIn(b'Add location', view_res.data)

        # Edit profile to add pin
        edit_res = self.client.post('/profile/edit', data={
            'name': 'Profile Farmer',
            'whatsapp_number': '+94771234567',
            'location': 'Matale',
            'latitude': '7.467472',
            'longitude': '80.623428',
            'address_text': 'Aluvihare, Matale'
        }, follow_redirects=True)

        self.assertEqual(edit_res.status_code, 200)
        db.session.refresh(user)
        self.assertEqual(user.latitude, Decimal('7.467472'))
        self.assertEqual(user.longitude, Decimal('80.623428'))
        self.assertEqual(user.address_text, 'Aluvihare, Matale')
        self.assertIsNotNone(user.location_updated_at)

        # After pin: Profile overview renders mini-map and edit button
        view_res_after = self.client.get('/profile')
        self.assertEqual(view_res_after.status_code, 200)
        self.assertIn(b'profile-mini-map', view_res_after.data)
        self.assertIn(b'Edit location', view_res_after.data)
        self.assertIn(b'7.467472', view_res_after.data)
        self.assertIn(b'80.623428', view_res_after.data)

    def test_farmer_dashboard_banner_logic(self):
        """Farmer without a pin sees the dismissible banner; farmer with a pin does not."""
        user = User(
            name='Dashboard Farmer',
            email='profile_geo_farmer@example.com',
            role='farmer',
            whatsapp_number='+94771234567',
            location='Badulla'
        )
        user.set_password('Password123!')
        db.session.add(user)
        db.session.commit()

        self.client.post('/auth/login', data={
            'email': 'profile_geo_farmer@example.com',
            'password': 'Password123!'
        }, follow_redirects=True)

        # No pin -> Banner is visible
        dash_res = self.client.get('/dashboard/', follow_redirects=True)
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b'Add your farm location so buyers can find you', dash_res.data)

        # Add pin to farmer
        user.latitude = Decimal('6.993400')
        user.longitude = Decimal('81.055000')
        db.session.commit()

        # With pin -> Banner is absent
        dash_res_with_pin = self.client.get('/dashboard/', follow_redirects=True)
        self.assertEqual(dash_res_with_pin.status_code, 200)
        self.assertNotIn(b'Add your farm location so buyers can find you', dash_res_with_pin.data)
