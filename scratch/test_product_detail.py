import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from extensions import db
from models import Product, User, MarketPrice

app = create_app()

def test_product_detail():
    with app.app_context():
        # Get or create test farmer 1 (owner) and farmer 2 (other)
        farmer_owner = User.query.filter_by(role='farmer').first()
        assert farmer_owner, "Need at least one farmer"
        if not farmer_owner.phone:
            farmer_owner.phone = '0771234567'
            db.session.commit()

        farmer_other = User.query.filter(User.role == 'farmer', User.id != farmer_owner.id).first()
        if not farmer_other:
            farmer_other = User(
                name='Other Farmer',
                email='other_farmer@test.com',
                role='farmer',
                phone='0779998877',
                location='Kandy'
            )
            farmer_other.set_password('password123')
            db.session.add(farmer_other)
            db.session.commit()

        # Get or create buyer
        buyer = User.query.filter_by(role='buyer').first()
        if not buyer:
            buyer = User(
                name='Test Buyer',
                email='buyer_test@test.com',
                role='buyer',
                phone='0712223344',
                location='Colombo'
            )
            buyer.set_password('password123')
            db.session.add(buyer)
            db.session.commit()

        # Get an active product belonging to farmer_owner
        product = Product.query.filter_by(farmer_id=farmer_owner.id, is_available=True, is_deleted=False).first()
        if not product:
            product = Product(
                farmer_id=farmer_owner.id,
                name='Organic Red Tomato',
                category='Vegetables',
                description='Juicy field-harvested tomatoes',
                quantity_kg=120.0,
                price_per_kg=120.0,
                location='Matale',
                is_available=True,
                is_deleted=False
            )
            db.session.add(product)
            db.session.commit()

        product_id = product.id
        owner_id = farmer_owner.id
        other_farmer_id = farmer_other.id
        buyer_id = buyer.id

    with app.test_client() as client:
        # ── Test 1: Guest State & Privacy ──────────────────────────────────
        res_guest = client.get(f'/marketplace/product/{product_id}')
        assert res_guest.status_code == 200, f"Expected 200, got {res_guest.status_code}"
        html_guest = res_guest.get_data(as_text=True)

        assert 'Marketplace' in html_guest
        assert product.category in html_guest
        assert 'Click to zoom' in html_guest
        assert 'image-lightbox' in html_guest
        assert 'farmer_map' in html_guest
        assert 'Log in to Order' in html_guest
        assert 'Log in to reveal farmer contact information' in html_guest

        # Privacy check: No phone or whatsapp numbers leaked to guests
        if farmer_owner.phone:
            assert farmer_owner.phone not in html_guest
        assert 'tel:' not in html_guest
        assert 'wa.me' not in html_guest
        print("[PASS] 1. Guest state: Clean breadcrumbs, lightbox modal, login CTAs, and ZERO phone leaks")

        # ── Test 2: Authenticated Buyer State ──────────────────────────────
        with client.session_transaction() as sess:
            sess['_user_id'] = str(buyer_id)
            sess['_fresh'] = True

        res_buyer = client.get(f'/marketplace/product/{product_id}')
        assert res_buyer.status_code == 200
        html_buyer = res_buyer.get_data(as_text=True)

        assert 'Order Now' in html_buyer
        assert f'/orders/place/{product_id}' in html_buyer or f'/orders/place_order/{product_id}' in html_buyer or f'product_id={product_id}' in html_buyer
        # Authenticated buyer sees contact buttons
        assert 'Contact on WhatsApp' in html_buyer or 'Call Farmer' in html_buyer
        print("[PASS] 2. Buyer state: 'Order Now' button and farmer contact buttons present")

        # ── Test 3: Owner Farmer State ─────────────────────────────────────
        with client.session_transaction() as sess:
            sess['_user_id'] = str(owner_id)
            sess['_fresh'] = True

        res_owner = client.get(f'/marketplace/product/{product_id}')
        assert res_owner.status_code == 200
        html_owner = res_owner.get_data(as_text=True)

        assert 'You are viewing your own listed crop' in html_owner
        assert 'Edit Listing' in html_owner
        assert f'/marketplace/product/{product_id}/edit' in html_owner
        assert 'Remove' in html_owner
        assert 'delete-confirm-modal' in html_owner
        assert f'/marketplace/product/{product_id}/delete' in html_owner
        print("[PASS] 3. Owner farmer state: Edit Listing and Remove buttons with confirmation dialog")

        # ── Test 4: Different Farmer State ─────────────────────────────────
        with client.session_transaction() as sess:
            sess['_user_id'] = str(other_farmer_id)
            sess['_fresh'] = True

        res_other = client.get(f'/marketplace/product/{product_id}')
        assert res_other.status_code == 200
        html_other = res_other.get_data(as_text=True)

        assert 'Only buyers can place orders' in html_other
        assert 'Edit Listing' not in html_other
        print("[PASS] 4. Different farmer state: Quiet note 'Only buyers can place orders' shown")

        # ── Test 5: Out of Stock State ─────────────────────────────────────
        with app.app_context():
            # Temporarily mark product as out of stock
            p_obj = Product.query.get(product_id)
            orig_qty = p_obj.quantity_kg
            orig_avail = p_obj.is_available
            p_obj.quantity_kg = 0
            p_obj.is_available = False
            db.session.commit()

        # Check buyer viewing out of stock item
        with client.session_transaction() as sess:
            sess['_user_id'] = str(buyer_id)
            sess['_fresh'] = True

        res_oos = client.get(f'/marketplace/product/{product_id}')
        html_oos = res_oos.get_data(as_text=True)
        assert 'Currently Out of Stock' in html_oos
        assert 'The grower has depleted available stock for this listing' in html_oos
        print("[PASS] 5. Out of stock state: Disabled button with clear explanation shown")

        # Restore original qty
        with app.app_context():
            p_obj = Product.query.get(product_id)
            p_obj.quantity_kg = orig_qty
            p_obj.is_available = orig_avail
            db.session.commit()

    print("\nALL PRODUCT DETAIL ACCEPTANCE TESTS PASSED!")

if __name__ == '__main__':
    test_product_detail()
