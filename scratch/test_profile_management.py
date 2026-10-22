import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
from app import create_app
from extensions import db
from models import User, Product

class TestProfileManagement(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False  # disable CSRF for testing convenience
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        # Find or create a test farmer
        self.farmer = User.query.filter_by(email='test_farmer_profile@example.com').first()
        if not self.farmer:
            self.farmer = User(
                name='Farmer Kamal',
                email='test_farmer_profile@example.com',
                role='farmer'
            )
            db.session.add(self.farmer)

        self.farmer.name = 'Farmer Kamal'
        self.farmer.role = 'farmer'
        self.farmer.whatsapp_number = '+94771234567'
        self.farmer.phone = '+94112345678'
        self.farmer.location = 'Kandy'
        self.farmer.farm_name = 'Kamal Organic Farm'
        self.farmer.bio = 'Growing high-grade organic vegetables.'
        self.farmer.set_password('FarmerPass123')
        db.session.commit()

        # Find or create a test buyer
        self.buyer = User.query.filter_by(email='test_buyer_profile@example.com').first()
        if not self.buyer:
            self.buyer = User(
                name='Buyer Nimal',
                email='test_buyer_profile@example.com',
                role='buyer',
                whatsapp_number='+94779876543',
                location='Colombo'
            )
            self.buyer.set_password('BuyerPass123')
            db.session.add(self.buyer)
            db.session.commit()

    def tearDown(self):
        # We can keep or clean test data
        self.ctx.pop()

    def login(self, email, password):
        return self.client.post('/auth/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    def logout(self):
        return self.client.get('/auth/logout', follow_redirects=True)

    def test_buyer_profile_view_and_edit(self):
        self.login('test_buyer_profile@example.com', 'BuyerPass123')
        res = self.client.get('/profile')
        self.assertEqual(res.status_code, 200)
        content = res.get_data(as_text=True)
        self.assertIn('Buyer Nimal', content)
        self.assertIn('test_buyer_profile@example.com', content)
        self.assertIn('Read-only', content)
        self.assertIn('map-location-placeholder', content)

        # Buyer edit
        res = self.client.post('/profile/edit', data={
            'name': 'Buyer Nimal Gunawardena',
            'whatsapp_number': '0779876543',
            'location': 'Kaduwela, Colombo'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        content = res.get_data(as_text=True)
        self.assertIn('Profile updated successfully!', content)
        self.assertIn('Buyer Nimal Gunawardena', content)
        self.assertIn('+94779876543', content)

        db.session.refresh(self.buyer)
        self.assertEqual(self.buyer.name, 'Buyer Nimal Gunawardena')
        self.assertEqual(self.buyer.whatsapp_number, '+94779876543')

    def test_profile_requires_login(self):
        res = self.client.get('/profile', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/auth/login', res.headers.get('Location', ''))

    def test_farmer_profile_view(self):
        self.login('test_farmer_profile@example.com', 'FarmerPass123')
        res = self.client.get('/profile')
        self.assertEqual(res.status_code, 200)
        content = res.get_data(as_text=True)
        self.assertIn('Farmer Kamal', content)
        self.assertIn('test_farmer_profile@example.com', content)
        self.assertIn('Read-only', content)
        self.assertIn('Kamal Organic Farm', content)
        self.assertIn('Growing high-grade organic vegetables', content)
        self.assertIn('map-location-placeholder', content)
        self.assertIn('Map Location Placeholder', content)
        self.assertIn('My Profile', content)

    def test_profile_edit_and_validation(self):
        self.login('test_farmer_profile@example.com', 'FarmerPass123')

        # 1. Invalid WhatsApp number (not Sri Lankan format)
        res = self.client.post('/profile/edit', data={
            'name': 'Farmer Kamal Updated',
            'whatsapp_number': '12345',  # invalid
            'location': 'Nuwara Eliya',
            'farm_name': 'Highland Harvest',
            'bio': 'Highland tea and carrots.'
        }, follow_redirects=True)
        content = res.get_data(as_text=True)
        self.assertIn('Please enter a valid Sri Lankan phone number', content)

        # 2. Valid edit with E.164 normalization
        res = self.client.post('/profile/edit', data={
            'name': 'Farmer Kamal Perera',
            'whatsapp_number': '071 234 5678',  # should be normalized to +94712345678
            'phone': '011 555 1234',            # should be normalized to +94115551234
            'location': 'Nuwara Eliya',
            'farm_name': 'Highland Green Estate',
            'bio': 'Premium organic carrots, leeks, and cabbage.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        content = res.get_data(as_text=True)
        self.assertIn('Profile updated successfully!', content)
        self.assertIn('Farmer Kamal Perera', content)
        self.assertIn('+94712345678', content)
        self.assertIn('Highland Green Estate', content)

        # Check in DB
        db.session.refresh(self.farmer)
        self.assertEqual(self.farmer.name, 'Farmer Kamal Perera')
        self.assertEqual(self.farmer.whatsapp_number, '+94712345678')
        self.assertEqual(self.farmer.phone, '+94115551234')
        self.assertEqual(self.farmer.location, 'Nuwara Eliya')
        self.assertEqual(self.farmer.farm_name, 'Highland Green Estate')

        # 3. Email is read-only and cannot be altered
        old_email = self.farmer.email
        self.client.post('/profile/edit', data={
            'name': 'Farmer Kamal Perera',
            'email': 'hacker@example.com',
            'whatsapp_number': '0712345678',
            'location': 'Nuwara Eliya'
        }, follow_redirects=True)
        db.session.refresh(self.farmer)
        self.assertEqual(self.farmer.email, old_email)

    def test_password_change(self):
        self.login('test_farmer_profile@example.com', 'FarmerPass123')

        # 1. Wrong current password
        res = self.client.post('/profile/password', data={
            'current_password': 'WrongPassword123',
            'new_password': 'BrandNewPass123',
            'confirm_password': 'BrandNewPass123'
        }, follow_redirects=True)
        content = res.get_data(as_text=True)
        self.assertIn('Current password is incorrect.', content)

        # 2. Too short new password (< 8 chars)
        res = self.client.post('/profile/password', data={
            'current_password': 'FarmerPass123',
            'new_password': 'short',
            'confirm_password': 'short'
        }, follow_redirects=True)
        content = res.get_data(as_text=True)
        self.assertIn('New password must be at least 8 characters long.', content)

        # 3. Confirmation mismatch
        res = self.client.post('/profile/password', data={
            'current_password': 'FarmerPass123',
            'new_password': 'BrandNewPass123',
            'confirm_password': 'DifferentPass123'
        }, follow_redirects=True)
        content = res.get_data(as_text=True)
        self.assertIn('New password and confirmation do not match.', content)

        # 4. Successful password change
        res = self.client.post('/profile/password', data={
            'current_password': 'FarmerPass123',
            'new_password': 'BrandNewPass123',
            'confirm_password': 'BrandNewPass123'
        }, follow_redirects=True)
        content = res.get_data(as_text=True)
        self.assertIn('Password changed successfully!', content)

        # Verify login with new password
        self.logout()
        login_res = self.login('test_farmer_profile@example.com', 'BrandNewPass123')
        self.assertEqual(login_res.status_code, 200)

        # Revert password for clean test runs
        self.farmer.set_password('FarmerPass123')
        db.session.commit()

    def test_product_detail_farmer_card_does_not_leak_email(self):
        # Create a test product if needed
        product = Product.query.filter_by(farmer_id=self.farmer.id).first()
        if not product:
            product = Product(
                farmer_id=self.farmer.id,
                name='Organic Carrots',
                category='Vegetables',
                description='Freshly harvested hill country carrots',
                quantity_kg=100.0,
                price_per_kg=250.0,
                location='Nuwara Eliya',
                image_url='https://images.unsplash.com/photo-1598170845058-32b9d6a5da37?w=500',
                is_available=True,
                is_deleted=False
            )
            db.session.add(product)
            db.session.commit()

        res = self.client.get(f'/marketplace/product/{product.id}')
        self.assertEqual(res.status_code, 200)
        content = res.get_data(as_text=True)

        # Farmer public details should be present
        self.assertIn(self.farmer.name, content)
        self.assertIn(self.farmer.farm_name, content)
        self.assertIn('active listing', content)
        self.assertIn('District / Location', content)
        self.assertIn('Member Since', content)

        # Private data MUST NOT be leaked
        self.assertNotIn('test_farmer_profile@example.com', content)

if __name__ == '__main__':
    unittest.main()
