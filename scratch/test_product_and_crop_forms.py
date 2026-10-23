import sys
import os
import unittest
from datetime import date, timedelta

# Add workspace root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models import User, Product, Crop, MarketPrice

app = create_app()

class TestProductAndCropForms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

        with app.app_context():
            # Find or create a farmer user
            farmer = User.query.filter_by(role='farmer').first()
            if not farmer:
                farmer = User(
                    name="Test Farmer John",
                    email="farmer_tester@agrolink.lk",
                    phone="0771234567",
                    role="farmer",
                    district="Nuwara Eliya",
                    location="Nuwara Eliya Farm"
                )
                farmer.set_password("AgroPass123!")
                db.session.add(farmer)
                db.session.commit()
            cls.farmer_id = farmer.id

            # Find or create a sample product
            product = Product.query.filter_by(farmer_id=farmer.id, is_deleted=False).first()
            if not product:
                product = Product(
                    farmer_id=farmer.id,
                    name="Nuwara Eliya Carrots",
                    category="Vegetables",
                    quantity_kg=250.0,
                    price_per_kg=140.0,
                    location="Nuwara Eliya",
                    description="Crisp grade-A fresh carrots washed and sorted.",
                    is_available=True,
                    is_deleted=False
                )
                db.session.add(product)
                db.session.commit()
            cls.product_id = product.id

            # Find or create a sample crop
            crop = Crop.query.filter_by(farmer_id=farmer.id).first()
            if not crop:
                crop = Crop(
                    farmer_id=farmer.id,
                    crop_name="Crisp Green Beans",
                    crop_type="Vegetables",
                    quantity_kg=400.0,
                    expected_harvest_date=date.today() + timedelta(days=21),
                    field_location="Plot 4 - Ridge A",
                    notes="Drip irrigation with organic bio-fertilizer.",
                    status="growing"
                )
                db.session.add(crop)
                db.session.commit()
            cls.crop_id = crop.id
            cls.crop_name = crop.crop_name

            # Ensure market price benchmark exists
            mp = MarketPrice.query.filter_by(crop_name="Carrots").first()
            if not mp:
                mp = MarketPrice(
                    crop_name="Carrots",
                    category="Vegetables",
                    buying_price=110.0,
                    selling_price=165.0,
                    unit="per kg",
                    market_location="Dambulla"
                )
                db.session.add(mp)
                db.session.commit()

    def login_farmer(self):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.farmer_id)
            sess['_fresh'] = True

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Product Form GET Checks
    # ─────────────────────────────────────────────────────────────────────────
    def test_01_product_form_get_features(self):
        self.login_farmer()
        res = self.client.get('/marketplace/list')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # 1. Two-column desktop layout & Grouped sections
        self.assertIn('lg:grid-cols-12', html)
        self.assertIn('Basic Info', html)
        self.assertIn('Pricing &amp; Stock', html)
        self.assertIn('Location &amp; Logistics', html)
        self.assertIn('Produce Photo', html)

        # 2. Fields: Category icon chips, Price prefix/suffix, Quantity stepper, live char counter, district datalist
        self.assertIn('category-chip', html)
        self.assertIn('LKR', html)
        self.assertIn('/ kg', html)
        self.assertIn('qty-increment-btn', html)
        self.assertIn('qty-decrement-btn', html)
        self.assertIn('id="desc-char-counter"', html)
        self.assertIn('id="districts-list"', html)
        self.assertIn('<option value="Nuwara Eliya">', html)

        # 3. Image uploader: dropzone states, default photo note
        self.assertIn('id="drop-zone"', html)
        self.assertIn('id="dropzone-idle-state"', html)
        self.assertIn('id="dropzone-preview-state"', html)
        self.assertIn('id="dropzone-error-box"', html)
        self.assertIn('If you skip this, a default category photo is used', html)

        # 4. Price hint slot & Benchmark data
        self.assertIn('id="price-hint-slot"', html)
        self.assertIn('id="market-price-hint"', html)
        self.assertIn('market-prices-json', html)

        # 5. Hidden "Offer delivery" switch component slot
        self.assertIn('id="offer-delivery-slot"', html)
        self.assertIn('data-feature="offer-delivery"', html)
        self.assertIn('hidden', html)

        # 6. Mobile sticky bottom bar & form actions
        self.assertIn('id="mobile-action-bar"', html)
        self.assertIn('id="mobile-submit-btn"', html)
        self.assertIn('beforeunload', html)
        print("[PASS] 1. Product form GET contains all required layout, fields, dropzone, and mobile bar")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Product Form Server-side Error Re-render Value Preservation
    # ─────────────────────────────────────────────────────────────────────────
    def test_02_product_form_error_preserves_values(self):
        self.login_farmer()
        # Submit invalid data (price <= 0 triggers validation error in routes.py)
        payload = {
            'name': 'Special Keeri Samba Rice',
            'category': 'Grains & Rice',
            'location': 'Polonnaruwa Central',
            'quantity_kg': '1500',
            'price_per_kg': '-10', # Invalid price
            'description': 'Premium organic harvest aged 6 months.'
        }
        res = self.client.post('/marketplace/list', data=payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Values should be preserved in re-rendered form
        self.assertIn('value="Special Keeri Samba Rice"', html)
        self.assertIn('value="Polonnaruwa Central"', html)
        self.assertIn('value="1500"', html)
        self.assertIn('Premium organic harvest aged 6 months.', html)
        print("[PASS] 2. Product form preserves all values on server-side validation error re-render")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Crop Form GET Checks
    # ─────────────────────────────────────────────────────────────────────────
    def test_03_crop_form_get_features(self):
        self.login_farmer()
        res = self.client.get('/dashboard/crops/add')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Crop type as chips
        self.assertIn('crop-type-chip', html)
        self.assertIn('data-crop-type="Vegetables"', html)

        # Status as segmented control with icons
        self.assertIn('segmented-btn', html)
        self.assertIn('data-status-val="growing"', html)
        self.assertIn('data-status-val="ready"', html)
        self.assertIn('data-status-val="harvested"', html)

        # Quantity with kg suffix
        self.assertIn('id="crop_quantity"', html)
        self.assertIn('kg', html)

        # Native date input with live countdown helper
        self.assertIn('type="date"', html)
        self.assertIn('id="expected_harvest_date"', html)
        self.assertIn('id="harvest-countdown-box"', html)
        print("[PASS] 3. Crop form GET contains chips, segmented control, kg suffix, and harvest date countdown helper")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Crop Form Edit & Delete confirm_dialog
    # ─────────────────────────────────────────────────────────────────────────
    def test_04_crop_form_edit_and_delete_confirm_dialog(self):
        self.login_farmer()
        res = self.client.get(f'/dashboard/crops/{self.crop_id}/edit')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Prepopulated values
        self.assertIn(f'value="{self.crop_name}"', html)

        # Delete uses accessible confirm_dialog modal
        self.assertIn('id="delete-crop-modal"', html)
        self.assertIn('role="dialog"', html)
        self.assertIn('aria-modal="true"', html)
        self.assertIn('Delete Crop Record?', html)
        self.assertIn(f'/dashboard/crops/{self.crop_id}/delete', html)
        print("[PASS] 4. Crop edit form renders accessible confirm_dialog for delete action")

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Crop Form Server-side Error Value Preservation
    # ─────────────────────────────────────────────────────────────────────────
    def test_05_crop_form_error_preserves_values(self):
        self.login_farmer()
        # Submit invalid quantity to trigger error in routes.py
        payload = {
            'crop_name': 'Heenati Rice Organic',
            'crop_type': 'Grains & Rice',
            'quantity_kg': 'invalid-qty',
            'expected_harvest_date': '2026-12-01',
            'field_location': 'South Field 3',
            'notes': 'Organic heirloom seeds.',
            'status': 'ready'
        }
        res = self.client.post('/dashboard/crops/add', data=payload, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Crop name and other fields should be preserved in re-rendered form
        self.assertIn('value="Heenati Rice Organic"', html)
        self.assertIn('value="South Field 3"', html)
        self.assertIn('Organic heirloom seeds.', html)
        print("[PASS] 5. Crop form preserves all values on server-side validation error re-render")

if __name__ == '__main__':
    unittest.main()
