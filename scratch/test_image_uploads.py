import sys
import os
import io
import unittest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models import User, Product
from utils.uploads import save_uploaded_image, delete_uploaded_image


class TestImageUploads(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        # Farmer user for uploads
        self.farmer = User.query.filter_by(email='farmer_upload_test@example.com').first()
        if not self.farmer:
            self.farmer = User(
                name='Farmer Upload Tester',
                email='farmer_upload_test@example.com',
                role='farmer',
                whatsapp_number='+94771112233'
            )
            self.farmer.set_password('Password123')
            db.session.add(self.farmer)
            db.session.commit()

        self.created_files = []

    def tearDown(self):
        # Cleanup any test-generated files on disk
        for path in self.created_files:
            if os.path.isfile(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        self.ctx.pop()

    def _create_dummy_image(self, width=1600, height=1200, format='JPEG', color='green'):
        """Creates an in-memory image using Pillow."""
        img = Image.new('RGB', (width, height), color=color)
        buf = io.BytesIO()
        img.save(buf, format=format)
        buf.seek(0)
        return buf

    def login_farmer(self):
        return self.client.post('/auth/login', data={
            'email': 'farmer_upload_test@example.com',
            'password': 'Password123'
        }, follow_redirects=True)

    def test_upload_valid_image_and_resizing(self):
        """Test uploading a valid wide image (1600px) is resized to 1200px and 400px thumb."""
        self.login_farmer()

        img_buf = self._create_dummy_image(width=1600, height=1200, format='JPEG')
        data = {
            'name': 'Crisp Green Cabbage',
            'category': 'Vegetables',
            'quantity_kg': '150',
            'price_per_kg': '120',
            'location': 'Nuwara Eliya',
            'description': 'Farm fresh high quality cabbage',
            'image': (img_buf, 'fresh_cabbage.jpg', 'image/jpeg')
        }

        res = self.client.post('/marketplace/list', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Check product in DB
        product = Product.query.filter_by(name='Crisp Green Cabbage', farmer_id=self.farmer.id).order_by(Product.id.desc()).first()
        self.assertIsNotNone(product)
        self.assertIsNotNone(product.image_url)
        self.assertTrue(product.image_url.startswith('/static/uploads/products/'))
        self.assertTrue(product.image_url.endswith('.jpg'))

        # Check files on disk
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        main_disk_path = os.path.join(project_root, product.image_url.lstrip('/'))
        base, ext = os.path.splitext(main_disk_path)
        thumb_disk_path = f"{base}_thumb{ext}"

        self.created_files.extend([main_disk_path, thumb_disk_path])
        self.assertTrue(os.path.isfile(main_disk_path), f"Main image not found at {main_disk_path}")
        self.assertTrue(os.path.isfile(thumb_disk_path), f"Thumbnail not found at {thumb_disk_path}")

        # Check dimensions with Pillow
        with Image.open(main_disk_path) as saved_main:
            self.assertLessEqual(saved_main.width, 1200)
            self.assertEqual(saved_main.width, 1200)  # resized from 1600 to max 1200
        with Image.open(thumb_disk_path) as saved_thumb:
            self.assertEqual(saved_thumb.width, 400)  # thumbnail width 400

        # Check product properties
        self.assertEqual(product.display_image_url, product.image_url)
        self.assertTrue(product.thumbnail_url.endswith('_thumb.jpg'))

    def test_upload_fake_image_rejected(self):
        """Test uploading a fake .jpg (plain text file) is rejected by server-side Pillow verification."""
        self.login_farmer()

        fake_bytes = io.BytesIO(b"This is just ASCII text pretending to be a JPG picture.")
        data = {
            'name': 'Fake Tomato Listing',
            'category': 'Vegetables',
            'quantity_kg': '50',
            'price_per_kg': '80',
            'image': (fake_bytes, 'fake_photo.jpg', 'image/jpeg')
        }

        res = self.client.post('/marketplace/list', data=data, content_type='multipart/form-data', follow_redirects=True)
        content = res.get_data(as_text=True)
        self.assertIn('Invalid image file', content)

        # Ensure product was not created with fake image
        product = Product.query.filter_by(name='Fake Tomato Listing').first()
        self.assertIsNone(product)

    def test_upload_oversized_file_rejected(self):
        """Test uploading a file larger than 5 MB is rejected."""
        self.login_farmer()

        # Create 5.5 MB payload
        large_bytes = io.BytesIO(b"0" * (5500000))
        data = {
            'name': 'Oversized Pumpkin',
            'category': 'Vegetables',
            'quantity_kg': '50',
            'price_per_kg': '80',
            'image': (large_bytes, 'huge_image.jpg', 'image/jpeg')
        }

        res = self.client.post('/marketplace/list', data=data, content_type='multipart/form-data', follow_redirects=True)
        content = res.get_data(as_text=True)

        # Either caught by MAX_CONTENT_LENGTH (413 page/message) or utility size check
        self.assertTrue(
            res.status_code == 413 or 'File size exceeds' in content or 'File Too Large' in content or '5 MB' in content,
            f"Expected 5 MB rejection, got status {res.status_code}"
        )

    def test_replace_image_and_delete_old_file(self):
        """Test that updating a product with a new image deletes the previous file from disk."""
        self.login_farmer()

        # 1. Create product with initial image
        img_buf1 = self._create_dummy_image(width=800, height=600, color='red')
        data1 = {
            'name': 'Red Tomatoes',
            'category': 'Vegetables',
            'quantity_kg': '100',
            'price_per_kg': '200',
            'image': (img_buf1, 'tomato1.jpg', 'image/jpeg')
        }
        self.client.post('/marketplace/list', data=data1, content_type='multipart/form-data', follow_redirects=True)
        product = Product.query.filter_by(name='Red Tomatoes', farmer_id=self.farmer.id).first()
        self.assertIsNotNone(product)

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        old_main_path = os.path.join(project_root, product.image_url.lstrip('/'))
        base, ext = os.path.splitext(old_main_path)
        old_thumb_path = f"{base}_thumb{ext}"
        self.assertTrue(os.path.isfile(old_main_path))
        self.assertTrue(os.path.isfile(old_thumb_path))

        # 2. Update with new image
        img_buf2 = self._create_dummy_image(width=800, height=600, color='blue')
        data2 = {
            'name': 'Ripe Blue Tomatoes',
            'category': 'Vegetables',
            'quantity_kg': '100',
            'price_per_kg': '200',
            'is_available': 'on',
            'image': (img_buf2, 'tomato2.png', 'image/png')
        }
        res = self.client.post(f'/marketplace/product/{product.id}/edit', data=data2, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db.session.refresh(product)
        new_main_path = os.path.join(project_root, product.image_url.lstrip('/'))
        new_base, new_ext = os.path.splitext(new_main_path)
        new_thumb_path = f"{new_base}_thumb{new_ext}"
        self.created_files.extend([new_main_path, new_thumb_path])

        # Old file should be deleted from disk
        self.assertFalse(os.path.isfile(old_main_path), "Old main image was not deleted from disk")
        self.assertFalse(os.path.isfile(old_thumb_path), "Old thumbnail was not deleted from disk")

        # New file should exist
        self.assertTrue(os.path.isfile(new_main_path))
        self.assertTrue(os.path.isfile(new_thumb_path))

    def test_fallback_to_category_stock_image_when_no_upload(self):
        """Test that products created without an image fall back to the category stock image."""
        self.login_farmer()

        data = {
            'name': 'Golden Mangoes',
            'category': 'Fruits',
            'quantity_kg': '60',
            'price_per_kg': '350'
        }
        self.client.post('/marketplace/list', data=data, content_type='multipart/form-data', follow_redirects=True)
        product = Product.query.filter_by(name='Golden Mangoes', farmer_id=self.farmer.id).first()
        self.assertIsNotNone(product)

        # Image url should match Fruits category stock image
        self.assertIn('photo-1490474418585', product.display_image_url)
        self.assertIn('photo-1490474418585', product.thumbnail_url)

    def test_optional_profile_photo_upload(self):
        """Test optional profile photo upload using the reusable upload helper."""
        self.login_farmer()

        avatar_buf = self._create_dummy_image(width=500, height=500, color='orange')
        data = {
            'name': 'Farmer Upload Tester',
            'whatsapp_number': '+94771112233',
            'profile_image': (avatar_buf, 'avatar.jpg', 'image/jpeg')
        }
        res = self.client.post('/profile/edit', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db.session.refresh(self.farmer)
        self.assertIsNotNone(self.farmer.profile_image_url)
        self.assertTrue(self.farmer.profile_image_url.startswith('/static/uploads/profiles/'))

        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        avatar_path = os.path.join(project_root, self.farmer.profile_image_url.lstrip('/'))
        self.created_files.append(avatar_path)
        self.assertTrue(os.path.isfile(avatar_path))


if __name__ == '__main__':
    unittest.main()
