import sys
import os
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from extensions import db
from models import User, Product, Crop, Order, MarketPrice

app = create_app()

class TestDashboards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        cls.client = app.test_client()

        with app.app_context():
            # 1. Farmer with data
            farmer = User.query.filter_by(role='farmer').first()
            if not farmer:
                farmer = User(
                    name="Nimal Perera",
                    email="nimal_test@agrolink.lk",
                    phone="0771234567",
                    role="farmer",
                    district="Kandy",
                    location="Kandy Farm"
                )
                farmer.set_password("password123")
                db.session.add(farmer)
                db.session.commit()
            cls.farmer_id = farmer.id

            # 2. Empty farmer (no listings, no crops, no orders)
            empty_farmer = User.query.filter_by(email="empty_farmer@agrolink.lk").first()
            if not empty_farmer:
                empty_farmer = User(
                    name="Empty Farmer Sunil",
                    email="empty_farmer@agrolink.lk",
                    phone="0771112233",
                    role="farmer",
                    location="Matale"
                )
                empty_farmer.set_password("password123")
                db.session.add(empty_farmer)
                db.session.commit()
            cls.empty_farmer_id = empty_farmer.id

            # 3. Buyer with data
            buyer = User.query.filter_by(role='buyer').first()
            if not buyer:
                buyer = User(
                    name="Kamal Buyer",
                    email="kamal_buyer@agrolink.lk",
                    phone="0777654321",
                    role="buyer",
                    location="Colombo"
                )
                buyer.set_password("password123")
                db.session.add(buyer)
                db.session.commit()
            cls.buyer_id = buyer.id

            # 4. Empty buyer (no orders)
            empty_buyer = User.query.filter_by(email="empty_buyer@agrolink.lk").first()
            if not empty_buyer:
                empty_buyer = User(
                    name="Empty Buyer Nuwan",
                    email="empty_buyer@agrolink.lk",
                    phone="0779991122",
                    role="buyer",
                    location="Gampaha"
                )
                empty_buyer.set_password("password123")
                db.session.add(empty_buyer)
                db.session.commit()
            cls.empty_buyer_id = empty_buyer.id

            # Ensure farmer has product, crops (including overdue), and a pending order
            product = Product.query.filter_by(farmer_id=farmer.id, is_deleted=False).first()
            if not product:
                product = Product(
                    farmer_id=farmer.id,
                    name="Kandy Leeks",
                    category="Vegetables",
                    quantity_kg=120.0,
                    price_per_kg=85.0,
                    location="Kandy",
                    is_available=True,
                    is_deleted=False
                )
                db.session.add(product)
                db.session.commit()
            cls.product_id = product.id
            cls.product_name = product.name

            # Overdue crop
            overdue_crop = Crop.query.filter_by(farmer_id=farmer.id, crop_name="Overdue Radish").first()
            if not overdue_crop:
                overdue_crop = Crop(
                    farmer_id=farmer.id,
                    crop_name="Overdue Radish",
                    crop_type="Vegetables",
                    quantity_kg=300.0,
                    expected_harvest_date=date.today() - timedelta(days=4),
                    status="growing"
                )
                db.session.add(overdue_crop)
                db.session.commit()

            # Normal crop
            normal_crop = Crop.query.filter_by(farmer_id=farmer.id, crop_name="Fresh Keeri Samba").first()
            if not normal_crop:
                normal_crop = Crop(
                    farmer_id=farmer.id,
                    crop_name="Fresh Keeri Samba",
                    crop_type="Grains & Rice",
                    quantity_kg=800.0,
                    expected_harvest_date=date.today() + timedelta(days=14),
                    status="growing"
                )
                db.session.add(normal_crop)
                db.session.commit()

            # Pending Order for farmer from buyer
            pending_order = Order.query.filter_by(product_id=product.id, status='pending').first()
            if not pending_order:
                pending_order = Order(
                    buyer_id=buyer.id,
                    product_id=product.id,
                    quantity_kg=40.0,
                    total_price=3400.0,
                    status='pending',
                    delivery_address='Colombo 07 Commercial Hub'
                )
                db.session.add(pending_order)
                db.session.commit()
            cls.pending_order_id = pending_order.id

    def login_as(self, user_id):
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user_id)
            sess['_fresh'] = True

    # ─────────────────────────────────────────────────────────────────────────
    # 1. Farmer Dashboard with Data
    # ─────────────────────────────────────────────────────────────────────────
    def test_01_farmer_dashboard_with_data(self):
        self.login_as(self.farmer_id)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # 1. Greeting header & quick actions row
        self.assertTrue('Good morning' in html or 'Good afternoon' in html or 'Good evening' in html)
        self.assertIn('Add Listing', html)
        self.assertIn('Add Crop', html)
        self.assertIn('View Orders', html)
        self.assertIn('Update Location', html)

        # 2. KPI stat cards: Revenue, Active listings, Pending orders (gold highlight), Active crops
        self.assertIn('Total Revenue', html)
        self.assertIn('Active Listings', html)
        self.assertIn('Pending Orders', html)
        self.assertIn('bg-amber-50', html) # Gold-pale highlight for pending > 0
        self.assertIn('Active Crops', html)
        self.assertIn('grid-cols-2 lg:grid-cols-4', html) # 2x2 grid on mobile

        # 3. Needs your action panel
        self.assertIn('Needs Your Action', html)
        self.assertIn(self.product_name, html)
        self.assertIn('Confirm', html)

        self.assertIn('Reject', html)
        self.assertIn('reject-order-modal', html)

        # 4. Crop tracker: 3 columns, mobile tabs, overdue badge
        self.assertIn('Crop Cycle Tracker', html)
        self.assertIn('col-growing', html)
        self.assertIn('col-ready', html)
        self.assertIn('col-harvested', html)
        self.assertIn('crop-tab-btn', html)
        self.assertIn('overdue', html)

        # 5. My listings: stock bar, status badge, edit/remove actions
        self.assertIn('My Marketplace Produce Listings', html)
        self.assertIn('role="progressbar"', html)
        self.assertIn('Edit', html)
        self.assertIn('Remove', html)
        self.assertIn('delete-listing-modal', html)
        print("[PASS] 1. Farmer dashboard with data renders all 6 core requirements flawlessly")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Farmer Dashboard Empty States
    # ─────────────────────────────────────────────────────────────────────────
    def test_02_farmer_dashboard_empty_states(self):
        self.login_as(self.empty_farmer_id)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Empty state for pending orders
        self.assertIn('All caught up!', html)

        # Empty state for crops
        self.assertIn('No crops logged in tracker', html)
        self.assertIn('+ Log Your First Crop', html)

        # Empty state for listings
        self.assertIn('No produce listed for sale yet', html)
        self.assertIn('+ Create First Listing', html)
        print("[PASS] 2. Farmer dashboard renders clear, meaningful empty states with CTAs")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. Buyer Dashboard with Data
    # ─────────────────────────────────────────────────────────────────────────
    def test_03_buyer_dashboard_with_data(self):
        self.login_as(self.buyer_id)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # 7. Greeting & 3 KPI cards
        self.assertTrue('Good morning' in html or 'Good afternoon' in html or 'Good evening' in html)
        self.assertIn('Total Spent', html)
        self.assertIn('Active Orders', html)
        self.assertIn('Completed Orders', html)

        # 8. Active orders with stepper & reserved pay now spot
        self.assertIn('Active Orders in Progress', html)
        self.assertIn('Pending', html)
        self.assertIn('Confirmed', html)
        self.assertIn('Delivered', html)
        self.assertIn('Pay now', html) # Reserved spot

        # 9. Best deals today & Collapsible order history
        self.assertIn('Best Deals Today', html)
        self.assertIn('Compare Market Prices', html)
        self.assertIn('Browse Marketplace', html)
        self.assertIn('<details', html) # Collapsible order history
        self.assertIn('Purchase Order History', html)
        print("[PASS] 3. Buyer dashboard with data renders all requirements (stepper, deals, collapsible history)")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Buyer Dashboard Empty States
    # ─────────────────────────────────────────────────────────────────────────
    def test_04_buyer_dashboard_empty_states(self):
        self.login_as(self.empty_buyer_id)
        res = self.client.get('/dashboard/')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Empty state for active orders
        self.assertIn('No active orders in progress', html)
        self.assertIn('Browse Produce Catalog', html)

        # Empty state in past order history
        self.assertIn('No past or fulfilled orders recorded yet.', html)
        print("[PASS] 4. Buyer dashboard renders friendly empty states with CTAs")

if __name__ == '__main__':
    unittest.main()
