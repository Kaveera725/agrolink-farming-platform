import os
import sys
import subprocess
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from models import User, Product, Order

app = create_app()
edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
os.makedirs('ui-review/before', exist_ok=True)

with app.app_context():
    farmer = User.query.filter_by(role='farmer').first()
    buyer = User.query.filter_by(role='buyer').first()
    product = Product.query.filter_by(is_available=True, is_deleted=False).first()
    order = Order.query.first()

    pages = [
        ('home', None, '/'),
        ('marketplace', None, '/marketplace/'),
        ('prices', None, '/prices/'),
        ('bids', None, '/prices/bids'),
        ('login', None, '/auth/login'),
        ('register', None, '/auth/register'),
    ]
    if product:
        pages.append(('product_detail', None, f'/marketplace/product/{product.id}'))
    if farmer:
        pages.append(('farmer_dashboard', farmer, '/dashboard/'))
        pages.append(('farmer_crops', farmer, '/dashboard/crops'))
        pages.append(('farmer_orders', farmer, '/orders/'))
        pages.append(('farmer_profile', farmer, '/profile/'))
    if buyer:
        pages.append(('buyer_dashboard', buyer, '/dashboard/'))
        if order:
            pages.append(('order_detail', buyer, f'/orders/{order.id}'))

    for name, user, path in pages:
        c = app.test_client()
        if user:
            with c.session_transaction() as sess:
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True
        resp = c.get(path)
        if resp.status_code == 200:
            # Prepare HTML
            html_content = resp.data.decode('utf-8', errors='ignore')
            # Fix relative static URLs so local HTML renders styles and category SVGs properly
            html_content = html_content.replace('/static/', 'http://127.0.0.1:5000/static/')
            
            html_path = os.path.abspath(f'ui-review/before/{name}.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            file_url = 'file:///' + html_path.replace('\\', '/')
            img_375 = os.path.abspath(f'ui-review/before/{name}_375px.png')
            img_1280 = os.path.abspath(f'ui-review/before/{name}_1280px.png')

            subprocess.run([edge, '--headless', '--disable-gpu', f'--screenshot={img_375}', '--window-size=375,812', file_url], capture_output=True)
            subprocess.run([edge, '--headless', '--disable-gpu', f'--screenshot={img_1280}', '--window-size=1280,900', file_url], capture_output=True)

            print(f"Captured {name:<18} -> 375px: {os.path.exists(img_375)} ({os.path.getsize(img_375) if os.path.exists(img_375) else 0} B) | 1280px: {os.path.exists(img_1280)} ({os.path.getsize(img_1280) if os.path.exists(img_1280) else 0} B)")

print("\nAll baseline screenshots generated successfully!")
