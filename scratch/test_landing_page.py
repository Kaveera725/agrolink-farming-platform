import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import app
from models import User

app_instance = app.create_app()

with app_instance.test_client() as client:
    # 1. Guest View
    r = client.get('/')
    assert r.status_code == 200, f'Guest GET / failed with {r.status_code}'
    html = r.data.decode('utf-8')

    # Hero verification
    assert 'Fresh from Sri Lankan Farms' in html, 'Hero headline missing'
    assert 'Direct to Your Doorstep' in html, 'Hero headline part 2 missing'
    assert 'Browse fresh produce' in html, 'Guest primary CTA missing'
    assert "I'm a farmer: start selling" in html, 'Guest secondary CTA missing'

    # Trust strip verification
    assert 'Registered Farmers' in html, 'Trust strip farmers label missing'
    assert 'Active Produce Listings' in html, 'Trust strip listings label missing'
    assert 'Delivered Orders' in html, 'Trust strip orders label missing'
    assert 'Districts Covered' in html, 'Trust strip districts label missing'

    # Category tiles verification
    assert 'Explore Harvest Categories' in html, 'Categories section missing'
    assert 'Vegetables' in html and 'Fruits' in html and ('Grains &amp; Rice' in html or 'Grains' in html), 'Categories missing'

    # How it works verification
    assert 'How AgroLink Works' in html, 'How it works heading missing'
    assert 'For Buyers' in html and 'For Farmers' in html, 'How it works tabs missing'
    assert 'Browse &amp; Compare' in html or 'Browse & Compare' in html, 'Step 1 missing'

    # Fresh listings verification
    assert 'Fresh Harvests Just Listed' in html, 'Fresh listings heading missing'
    assert 'fresh-listings-slider' in html, 'Fresh listings slider ID missing'

    # Market price snapshot verification
    assert 'Current Market Price Snapshot' in html, 'Price snapshot heading missing'
    assert 'Wholesale Buying' in html and 'Retail Selling' in html, 'Price table columns missing'
    assert 'See all prices' in html, 'See all prices link missing'

    # Benefits band verification
    assert 'Why Trade Directly on AgroLink?' in html, 'Benefits heading missing'
    assert 'No Middlemen' in html, 'Benefit 1 missing'
    assert 'Fair Market Prices' in html, 'Benefit 2 missing'
    assert 'WhatsApp Contact' in html, 'Benefit 3 missing'
    assert 'Direct Delivery' in html, 'Benefit 4 missing'

    # Final CTA verification
    assert 'Ready to Experience Fair Agricultural Trade?' in html, 'Final CTA missing'
    print('PASS: Guest landing page verified successfully with all 8 sections!')

    # 2. Farmer Logged-in View
    with app_instance.app_context():
        farmer = User.query.filter_by(role='farmer').first()
        buyer = User.query.filter_by(role='buyer').first()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(farmer.id)
        sess['_fresh'] = True
    r = client.get('/')
    assert r.status_code == 200, f'Farmer GET / failed with {r.status_code}'
    html_farmer = r.data.decode('utf-8')
    assert 'Continue to your dashboard' in html_farmer, 'Farmer dashboard shortcut CTA missing'
    assert "I'm a farmer: start selling" not in html_farmer, 'Guest CTA should not appear for logged-in farmer'
    print('PASS: Farmer logged-in view displays dashboard shortcut!')

    # 3. Buyer Logged-in View
    with client.session_transaction() as sess:
        sess['_user_id'] = str(buyer.id)
        sess['_fresh'] = True
    r = client.get('/')
    assert r.status_code == 200, f'Buyer GET / failed with {r.status_code}'
    html_buyer = r.data.decode('utf-8')
    assert 'Continue to your dashboard' in html_buyer, 'Buyer dashboard shortcut CTA missing'
    print('PASS: Buyer logged-in view displays dashboard shortcut!')

print('\nALL LANDING PAGE TESTS PASSED!')
