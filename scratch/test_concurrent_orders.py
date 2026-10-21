import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import threading
import time
from app import create_app
from extensions import db
from models import User, Product, Order

def login_client(app, email, password="Password123"):
    client = app.test_client()
    client.get('/auth/logout')
    resp = client.post('/auth/login', data={'email': email, 'password': password})
    assert resp.status_code == 302, f"Expected 302 login redirect, got {resp.status_code}"
    return client

def run_tests():
    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['RATELIMIT_ENABLED'] = False
    with app.app_context():
        # Setup test users
        farmer = User.query.filter_by(email="test_farmer_concurrency@agrolink.lk").first()
        if not farmer:
            farmer = User(name="Test Farmer", email="test_farmer_concurrency@agrolink.lk", role="farmer", is_active=True, whatsapp_number="+94771112233")
            farmer.set_password("Password123")
            db.session.add(farmer)

        buyer1 = User.query.filter_by(email="test_buyer1_concurrency@agrolink.lk").first()
        if not buyer1:
            buyer1 = User(name="Test Buyer 1", email="test_buyer1_concurrency@agrolink.lk", role="buyer", is_active=True, whatsapp_number="+94772223344")
            buyer1.set_password("Password123")
            db.session.add(buyer1)

        buyer2 = User.query.filter_by(email="test_buyer2_concurrency@agrolink.lk").first()
        if not buyer2:
            buyer2 = User(name="Test Buyer 2", email="test_buyer2_concurrency@agrolink.lk", role="buyer", is_active=True, whatsapp_number="+94773334455")
            buyer2.set_password("Password123")
            db.session.add(buyer2)

        db.session.commit()

        print("\n--- TEST 1: Unit-level quantity safety checks ---")
        client1 = login_client(app, buyer1.email)

        # Create a test product
        p_safe = Product(
            farmer_id=farmer.id,
            name="Safety Check Carrots",
            category="Vegetables",
            quantity_kg=20.0,
            price_per_kg=150.0,
            image_url="https://example.com/carrot.jpg",
            is_available=True,
            is_deleted=False
        )
        db.session.add(p_safe)
        db.session.commit()
        safe_pid = p_safe.id

        # Negative quantity
        resp = client1.post(f'/orders/place/{safe_pid}', data={'quantity_kg': '-5', 'delivery_address': 'Colombo'})
        assert resp.status_code == 200
        assert b"Quantity must be greater than zero." in resp.data
        print(" [PASS] Negative quantity rejected.")

        # Zero quantity
        resp = client1.post(f'/orders/place/{safe_pid}', data={'quantity_kg': '0', 'delivery_address': 'Colombo'})
        assert resp.status_code == 200
        assert b"Quantity must be greater than zero." in resp.data
        print(" [PASS] Zero quantity rejected.")

        # Non-numeric
        resp = client1.post(f'/orders/place/{safe_pid}', data={'quantity_kg': 'five_kg', 'delivery_address': 'Colombo'})
        assert resp.status_code == 200
        assert b"Invalid quantity. Please enter a valid number." in resp.data
        print(" [PASS] Non-numeric input rejected.")

        # NaN / inf
        resp = client1.post(f'/orders/place/{safe_pid}', data={'quantity_kg': 'nan', 'delivery_address': 'Colombo'})
        assert resp.status_code == 200
        assert b"Invalid quantity. Please enter a valid number." in resp.data
        print(" [PASS] NaN input rejected.")

        # Quantity > stock
        resp = client1.post(f'/orders/place/{safe_pid}', data={'quantity_kg': '25', 'delivery_address': 'Colombo'})
        assert resp.status_code == 200
        assert b"Stock changed: only 20 kg available" in resp.data
        print(" [PASS] Quantity exceeding stock rejected.")


        print("\n--- TEST 2: BUG-010 Image preservation on edit ---")
        farmer_client = login_client(app, farmer.email)

        custom_img = "https://custom-domain.com/my-unique-photo.jpg"
        p_edit = Product(
            farmer_id=farmer.id,
            name="Edit Test Beans",
            category="Vegetables",
            quantity_kg=50.0,
            price_per_kg=200.0,
            image_url=custom_img,
            is_available=True,
            is_deleted=False
        )
        db.session.add(p_edit)
        db.session.commit()
        edit_pid = p_edit.id

        # Edit details without changing category
        resp = farmer_client.post(f'/marketplace/product/{edit_pid}/edit', data={
            'name': 'Edit Test Beans Renamed',
            'category': 'Vegetables', # same
            'quantity_kg': '45',
            'price_per_kg': '210',
            'is_available': 'on',
            'description': 'Updated',
            'location': 'Kandy'
        })
        assert resp.status_code == 302
        assert resp.headers.get('Location') == '/dashboard/'
        db.session.refresh(p_edit)
        assert p_edit.image_url == custom_img, f"Expected {custom_img}, got {p_edit.image_url}"
        print(" [PASS] image_url preserved when category unchanged.")

        # Edit with changed category
        resp2 = farmer_client.post(f'/marketplace/product/{edit_pid}/edit', data={
            'name': 'Edit Test Beans Now Fruits',
            'category': 'Fruits', # changed!
            'quantity_kg': '45',
            'price_per_kg': '210',
            'is_available': 'on',
            'description': 'Updated',
            'location': 'Kandy'
        })
        assert resp2.status_code == 302
        db.session.commit()
        db.session.refresh(p_edit)
        assert p_edit.image_url != custom_img and "photo-1490474418585" in p_edit.image_url
        print(" [PASS] image_url updated when category changed.")


        print("\n--- TEST 3: BUG-008 Soft delete & cancellation stock restore ---")
        p_del = Product(
            farmer_id=farmer.id,
            name="Delete & Restore Test Leeks",
            category="Vegetables",
            quantity_kg=15.0,
            price_per_kg=120.0,
            image_url="https://example.com/leeks.jpg",
            is_available=True,
            is_deleted=False
        )
        db.session.add(p_del)
        db.session.commit()
        del_pid = p_del.id

        # Buyer places order for 15 kg (all stock)
        client1 = login_client(app, buyer1.email)
        resp = client1.post(f'/orders/place/{del_pid}', data={'quantity_kg': '15', 'delivery_address': 'Colombo'}, follow_redirects=True)
        assert resp.status_code == 200
        db.session.commit()
        p_del = db.session.get(Product, del_pid)
        assert p_del.quantity_kg == 0
        assert p_del.is_available is False
        assert p_del.is_deleted is False

        # Get the placed order
        order = Order.query.filter_by(product_id=del_pid).first()
        assert order is not None
        order_id = order.id

        # Farmer deletes the product
        farmer_client = login_client(app, farmer.email)
        resp = farmer_client.post(f'/marketplace/product/{del_pid}/delete', follow_redirects=True)
        assert resp.status_code == 200
        db.session.commit()
        p_del = db.session.get(Product, del_pid)
        assert p_del.is_deleted is True
        assert p_del.is_available is False
        print(" [PASS] Farmer delete sets is_deleted=True, is_available=False.")

        # Deleted product hidden from marketplace
        resp = client1.get('/marketplace/')
        assert b"Delete & Restore Test Leeks" not in resp.data
        print(" [PASS] Deleted product hidden from marketplace listing.")

        # Deleted product direct detail returns 404
        resp = client1.get(f'/marketplace/product/{del_pid}')
        assert resp.status_code == 404
        print(" [PASS] Direct detail access to deleted product returns 404.")

        # Order history still visible and displays product info
        client1 = login_client(app, buyer1.email)
        resp = client1.get(f'/orders/{order_id}')
        assert resp.status_code == 200
        assert b"Delete &amp; Restore Test Leeks" in resp.data or b"Delete & Restore Test Leeks" in resp.data
        assert b"Archived Listing" in resp.data
        print(" [PASS] Deleted product still visible in old order history.")

        # Buyer cancels order on DELETED product: stock restored, but is_available remains FALSE!
        client1 = login_client(app, buyer1.email)
        resp = client1.post(f'/orders/{order_id}/cancel', follow_redirects=True)
        assert resp.status_code == 200
        db.session.commit()
        p_del = db.session.get(Product, del_pid)
        assert p_del.quantity_kg == 15.0
        assert p_del.is_available is False, "Cancelled order on deleted product must NOT re-enable is_available!"
        print(" [PASS] Cancelling order on deleted product restores stock but leaves is_available=False.")

        # Now test cancelling an order on a NON-DELETED product: restores stock and sets is_available=True!
        p_active = Product(
            farmer_id=farmer.id,
            name="Active Cancel Test Spinach",
            category="Vegetables",
            quantity_kg=10.0,
            price_per_kg=90.0,
            image_url="https://example.com/spinach.jpg",
            is_available=True,
            is_deleted=False
        )
        db.session.add(p_active)
        db.session.commit()
        act_pid = p_active.id

        # Buy all 10 kg
        client1 = login_client(app, buyer1.email)
        resp = client1.post(f'/orders/place/{act_pid}', data={'quantity_kg': '10', 'delivery_address': 'Colombo'}, follow_redirects=True)
        db.session.commit()
        p_active = db.session.get(Product, act_pid)
        assert p_active.quantity_kg == 0
        assert p_active.is_available is False
        order_act = Order.query.filter_by(product_id=act_pid).first()

        # Cancel order
        client1 = login_client(app, buyer1.email)
        resp = client1.post(f'/orders/{order_act.id}/cancel', follow_redirects=True)
        db.session.commit()
        p_active = db.session.get(Product, act_pid)
        assert p_active.quantity_kg == 10.0
        assert p_active.is_available is True, "Cancelled order on active product MUST re-enable is_available!"
        print(" [PASS] Cancelling order on active product restores stock and sets is_available=True.")


        print("\n--- TEST 4: BUG-003 Concurrent orders with with_for_update() ---")
        p_conc = Product(
            farmer_id=farmer.id,
            name="Concurrent Race Papaya",
            category="Fruits",
            quantity_kg=10.0, # Exactly 10 kg in stock
            price_per_kg=120.0,
            image_url="https://example.com/papaya.jpg",
            is_available=True,
            is_deleted=False
        )
        db.session.add(p_conc)
        db.session.commit()
        conc_pid = p_conc.id

        results = []
        barrier = threading.Barrier(2)

        def attempt_order(buyer_email, thread_name):
            thread_app = create_app()
            thread_app.config['WTF_CSRF_ENABLED'] = False
            thread_app.config['RATELIMIT_ENABLED'] = False
            with thread_app.app_context():
                c = login_client(thread_app, buyer_email)

                # Wait for both threads to hit barrier simultaneously
                barrier.wait()
                start_t = time.time()
                resp = c.post(f'/orders/place/{conc_pid}', data={
                    'quantity_kg': '10',
                    'delivery_address': f'Address from {thread_name}'
                }, follow_redirects=True)
                duration = time.time() - start_t
                status = resp.status_code
                body = resp.get_data(as_text=True)

                success = "Order placed successfully" in body
                stock_changed = "Stock changed" in body or "no longer available" in body

                results.append({
                    'thread': thread_name,
                    'status': status,
                    'success': success,
                    'stock_changed': stock_changed,
                    'duration': duration,
                    'body_snippet': body[:200]
                })

        t1 = threading.Thread(target=attempt_order, args=(buyer1.email, "Buyer-1"))
        t2 = threading.Thread(target=attempt_order, args=(buyer2.email, "Buyer-2"))

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        print(f" Thread 1 result: Success={results[0]['success']}, StockChanged={results[0]['stock_changed']}, HTTP={results[0]['status']}")
        print(f" Thread 2 result: Success={results[1]['success']}, StockChanged={results[1]['stock_changed']}, HTTP={results[1]['status']}")

        success_count = sum(1 for r in results if r['success'])
        stock_changed_count = sum(1 for r in results if r['stock_changed'])

        assert success_count == 1, f"Expected exactly 1 order to succeed, got {success_count}"
        assert stock_changed_count == 1, f"Expected exactly 1 order to receive stock changed message, got {stock_changed_count}"

        db.session.refresh(p_conc)
        assert p_conc.quantity_kg == 0, f"Expected final stock to be 0, got {p_conc.quantity_kg}"
        assert p_conc.is_available is False, "Expected product to be marked unavailable"

        # Check total orders created for this product
        conc_orders = Order.query.filter_by(product_id=conc_pid).all()
        assert len(conc_orders) == 1, f"Expected 1 order created in DB, got {len(conc_orders)}"
        print(" [PASS] Concurrency lock verified: Exactly 1 succeeded, 1 safely rejected with friendly message, 0 stock left.")

        print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY! [SUCCESS]")

if __name__ == '__main__':
    run_tests()
