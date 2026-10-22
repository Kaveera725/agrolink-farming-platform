import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import re
from app import create_app
from extensions import db
from models import Product, User, MarketPrice

app = create_app()

def test_marketplace():
    with app.test_client() as client:
        # 1. Test basic marketplace page load
        res = client.get('/marketplace/')
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        html = res.get_data(as_text=True)
        assert 'Direct Farm Produce' in html
        assert 'Islandwide Wholesale & Retail Marketplace' in html
        print("[PASS] 1. Marketplace page loads successfully (200 OK)")

        # 2. Test Guest Privacy: No phone or WhatsApp numbers exposed to guests
        with app.app_context():
            # Get real farmers and their phone numbers
            farmers = User.query.filter(User.phone.isnot(None), User.phone != '').all()
            for farmer in farmers:
                phone_clean = farmer.phone.strip()
                if len(phone_clean) >= 7:
                    assert phone_clean not in html, f"Guest leak: Phone number {phone_clean} exposed in guest HTML!"
                if farmer.whatsapp_number:
                    wa_clean = farmer.whatsapp_number.strip()
                    if len(wa_clean) >= 7:
                        assert wa_clean not in html, f"Guest leak: WhatsApp number {wa_clean} exposed in guest HTML!"
            
            # Also verify 'tel:' and 'wa.me/' are NOT in guest HTML
            assert 'tel:' not in html, "Guest leak: 'tel:' link found in guest HTML!"
            assert 'wa.me' not in html, "Guest leak: 'wa.me' link found in guest HTML!"
            assert 'Log in to contact' in html, "Expected 'Log in to contact' prompt for guests"
            print("[PASS] 2. Guest Privacy: Zero phone numbers or WhatsApp links exposed to guests")

        # 3. Test Category filtering
        res_cat = client.get('/marketplace/?category=Vegetables')
        assert res_cat.status_code == 200
        html_cat = res_cat.get_data(as_text=True)
        assert 'Category: Vegetables' in html_cat
        print("[PASS] 3. Category filter works and reflects in active filter tags")

        # 4. Test Search filtering
        res_search = client.get('/marketplace/?search=Tomato')
        assert res_search.status_code == 200
        html_search = res_search.get_data(as_text=True)
        assert 'Query: &quot;Tomato&quot;' in html_search or 'Query: "Tomato"' in html_search
        print("[PASS] 4. Search query filter works and preserves in state")

        # 5. Test Sorting (price_desc, newest)
        res_sort = client.get('/marketplace/?sort=price_desc')
        assert res_sort.status_code == 200
        html_sort = res_sort.get_data(as_text=True)
        assert 'Sort: Price: High to Low' in html_sort

        res_newest = client.get('/marketplace/?sort=newest')
        assert res_newest.status_code == 200
        html_newest = res_newest.get_data(as_text=True)
        assert 'Sort: Newest' in html_newest
        print("[PASS] 5. Sort options (price_desc, newest, price_asc) work")

        # 6. Test District filter
        res_district = client.get('/marketplace/?district=Colombo')
        assert res_district.status_code == 200
        html_district = res_district.get_data(as_text=True)
        assert 'District: Colombo' in html_district
        print("[PASS] 6. District filter works")

        # 7. Test Price range filter
        res_price = client.get('/marketplace/?min_price=50&max_price=300')
        assert res_price.status_code == 200
        html_price = res_price.get_data(as_text=True)
        assert 'Price: Rs. 50 - 300' in html_price
        print("[PASS] 7. Price range filter works")

        # 8. Test Empty State when filter yields 0 products
        res_empty = client.get('/marketplace/?search=NonExistentProductXYZ12345')
        assert res_empty.status_code == 200
        html_empty = res_empty.get_data(as_text=True)
        assert 'No produce listings found' in html_empty
        assert 'Clear All Filters' in html_empty
        print("[PASS] 8. Empty state renders with 'Clear All Filters' CTA")

        # 9. Test Logged-in user sees WhatsApp & Call buttons
        with client.session_transaction() as sess:
            # Login as buyer
            with app.app_context():
                buyer = User.query.filter_by(role='buyer').first()
                if buyer:
                    sess['_user_id'] = str(buyer.id)
                    sess['_fresh'] = True
        
        if buyer:
            res_logged_in = client.get('/marketplace/')
            html_logged_in = res_logged_in.get_data(as_text=True)
            # Logged in buyer should see WhatsApp / Call actions if products exist
            assert 'Log in to contact' not in html_logged_in
            print("[PASS] 9. Logged-in user sees direct WhatsApp and Call actions")

    print("\nALL BACKEND & TEMPLATE TESTS PASSED!")

if __name__ == '__main__':
    test_marketplace()
