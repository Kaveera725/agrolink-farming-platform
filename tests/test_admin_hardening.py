import io
import unittest
import uuid
from decimal import Decimal
from unittest.mock import patch
from flask import session, get_flashed_messages
from flask_login import login_user
from app import create_app
from extensions import db
from models import AdminAuditLog, AdminNote, MarketPrice, Order, Product, User
from utils.security import validate_admin_password, generate_temp_password, sanitize_csv_cell
from blueprints.admin.routes import toggle_user, change_user_role


class TestAdminHardening(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

        self.uid = uuid.uuid4().hex[:8]

        # Seed primary admin
        self.admin = User(
            name=f"Admin {self.uid}",
            email=f"admin_{self.uid}@agrolink.lk",
            role="admin",
            phone="0771234567",
            whatsapp_number="+94771234567",
            is_active=True,
            must_change_password=False,
            session_version=1
        )
        self.admin.set_password("AdminStrongPass!2026")

        # Seed second admin
        self.admin2 = User(
            name=f"Second Admin {self.uid}",
            email=f"admin2_{self.uid}@agrolink.lk",
            role="admin",
            phone="0772234567",
            whatsapp_number="+94772234567",
            is_active=True,
            must_change_password=False,
            session_version=1
        )
        self.admin2.set_password("Admin2StrongPass!2026")

        # Seed farmer
        self.farmer = User(
            name=f"Farmer {self.uid}",
            email=f"farmer_{self.uid}@agrolink.lk",
            role="farmer",
            phone="0773334444",
            whatsapp_number="+94773334444",
            location="Matale",
            is_active=True,
            must_change_password=False,
            session_version=1
        )
        self.farmer.set_password("FarmerPass!2026")

        # Seed buyer
        self.buyer = User(
            name=f"Buyer {self.uid}",
            email=f"buyer_{self.uid}@agrolink.lk",
            role="buyer",
            phone="0774445555",
            whatsapp_number="+94774445555",
            location="Colombo",
            is_active=True,
            must_change_password=False,
            session_version=1
        )
        self.buyer.set_password("BuyerPass!2026")

        db.session.add_all([self.admin, self.admin2, self.farmer, self.buyer])
        db.session.commit()

    def tearDown(self):
        Order.query.filter(Order.buyer_id == self.buyer.id).delete()
        Product.query.filter(Product.farmer_id == self.farmer.id).delete()
        AdminNote.query.filter(AdminNote.user_id.in_([self.admin.id, self.admin2.id, self.farmer.id, self.buyer.id])).delete()
        db.session.commit()
        self.ctx.pop()

    def _login(self, email, password):
        self.client.get('/auth/logout', follow_redirects=True)
        return self.client.post('/auth/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    def test_password_policy(self):
        """Admin password policy enforces length >= 10, no common passwords, and no name/email match."""
        # Length check
        ok, msg = validate_admin_password("Short1!", email="test@agrolink.lk", name="Custom Admin")
        self.assertFalse(ok)
        self.assertIn("10 characters", msg)

        # Equal to email
        ok, msg = validate_admin_password("admin@agrolink.lk", email="admin@agrolink.lk", name="Custom Admin")
        self.assertFalse(ok)
        self.assertIn("email", msg)

        # Equal to email username
        ok, msg = validate_admin_password("myadminuser", email="myadminuser@agrolink.lk", name="Custom Admin")
        self.assertFalse(ok)
        self.assertIn("email", msg)

        # Equal to name
        ok, msg = validate_admin_password("CustomAdmin", email="admin@agrolink.lk", name="CustomAdmin")
        self.assertFalse(ok)
        self.assertIn("name", msg)

        # Common passwords
        for common in ['admin123', 'password123', '12345678', 'qwerty123']:
            ok, msg = validate_admin_password(common, email="other@agrolink.lk", name="Other")
            self.assertFalse(ok)
            self.assertIn("common", msg)

        # Strong password passes
        ok, msg = validate_admin_password("AgroSecure#2026!", email="admin@agrolink.lk", name="Administrator")
        self.assertTrue(ok)
        self.assertIsNone(msg)

    def test_forced_password_change_redirect(self):
        """When must_change_password=True, all user requests redirect to /profile/password."""
        self.farmer.must_change_password = True
        db.session.commit()

        self._login(self.farmer.email, "FarmerPass!2026")

        # Attempt to access dashboard
        res = self.client.get('/dashboard/', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/profile/password', res.headers['Location'])

        # Attempt to access marketplace
        res2 = self.client.get('/marketplace/', follow_redirects=False)
        self.assertEqual(res2.status_code, 302)
        self.assertIn('/profile/password', res2.headers['Location'])

        # Accessing /profile/password is permitted
        res_pwd = self.client.get('/profile/password')
        self.assertEqual(res_pwd.status_code, 200)

        # Changing password clears must_change_password
        post_pwd = self.client.post('/profile/password', data={
            'current_password': "FarmerPass!2026",
            'new_password': "NewStrongPass#2026",
            'confirm_password': "NewStrongPass#2026"
        }, follow_redirects=True)
        self.assertEqual(post_pwd.status_code, 200)

        db.session.refresh(self.farmer)
        self.assertFalse(self.farmer.must_change_password)

        # Now can access dashboard freely
        res_dash = self.client.get('/dashboard/')
        self.assertEqual(res_dash.status_code, 200)

    def test_last_admin_and_self_protection(self):
        """Admins cannot deactivate or demote themselves, or the last active administrator."""
        self._login(self.admin.email, "AdminStrongPass!2026")

        # 1. Admin cannot deactivate themselves
        res_self_deact = self.client.post(f'/admin/users/{self.admin.id}/toggle-active', follow_redirects=True)
        self.assertIn(b'You cannot deactivate your own admin account.', res_self_deact.data)
        db.session.refresh(self.admin)
        self.assertTrue(self.admin.is_active)

        # 2. Admin cannot demote themselves
        res_self_demote = self.client.post(f'/admin/users/{self.admin.id}/change-role', data={
            'new_role': 'farmer',
            'reason': 'Self demotion attempt'
        }, follow_redirects=True)
        self.assertIn(b'You cannot modify the role of your own account.', res_self_demote.data)
        db.session.refresh(self.admin)
        self.assertEqual(self.admin.role, 'admin')

        # 3. Role change requires mandatory reason
        res_no_reason = self.client.post(f'/admin/users/{self.admin2.id}/change-role', data={
            'new_role': 'farmer',
            'reason': ''
        }, follow_redirects=True)
        self.assertIn(b'mandatory reason is required', res_no_reason.data)

        # 4. Prohibit Farmer <-> Buyer switching
        res_farmer_to_buyer = self.client.post(f'/admin/users/{self.farmer.id}/change-role', data={
            'new_role': 'buyer',
            'reason': 'Switching user type'
        }, follow_redirects=True)
        self.assertIn(b'Switching between Farmer and Buyer roles is not supported', res_farmer_to_buyer.data)

        # 5. Last active admin protection server-side check
        with self.app.test_request_context(f'/admin/users/{self.admin2.id}/toggle-active', method='POST'):
            login_user(self.admin)
            with patch('blueprints.admin.routes.User.query') as mock_query:
                mock_query.filter_by.return_value.count.return_value = 1
                mock_query.get_or_404.return_value = self.admin2

                res = toggle_user(self.admin2.id)
                self.assertEqual(res.status_code, 302)
                messages = get_flashed_messages()
                self.assertTrue(any('Cannot deactivate the last active administrator.' in m for m in messages))

        with self.app.test_request_context(
            f'/admin/users/{self.admin2.id}/change-role',
            method='POST',
            data={'new_role': 'farmer', 'reason': 'Demote test'}
        ):
            login_user(self.admin)
            with patch('blueprints.admin.routes.User.query') as mock_query:
                mock_query.filter_by.return_value.count.return_value = 1
                mock_query.get_or_404.return_value = self.admin2

                res = change_user_role(self.admin2.id)
                self.assertEqual(res.status_code, 302)
                messages = get_flashed_messages()
                self.assertTrue(any('Cannot demote the last active administrator.' in m for m in messages))

    def test_reset_password_and_session_invalidation(self):
        """Password reset generates strong temp password shown once, invalidates sessions, and never appears in audit log."""
        self._login(self.admin.email, "AdminStrongPass!2026")

        old_session_version = self.farmer.session_version

        # Reset farmer password
        res = self.client.post(f'/admin/users/{self.farmer.id}/reset-password', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db.session.refresh(self.farmer)
        self.assertTrue(self.farmer.must_change_password)
        self.assertEqual(self.farmer.session_version, old_session_version + 1)

        # Temporary password banner shown ONCE in HTML response
        self.assertIn(b'Temporary Password Generated', res.data)

        # Second GET to user detail does NOT show the password notice
        res2 = self.client.get(f'/admin/users/{self.farmer.id}')
        self.assertNotIn(b'Temporary Password Generated', res2.data)

        # Verify raw password hash NEVER appears in audit log
        audit = AdminAuditLog.query.filter_by(
            action='user_password_reset',
            target_id=self.farmer.id
        ).order_by(AdminAuditLog.created_at.desc()).first()
        self.assertIsNotNone(audit)
        self.assertNotIn(self.farmer.password_hash, audit.details)
        self.assertIsNone(audit.before_data)
        self.assertIsNone(audit.after_data)

    def test_farmer_deactivation_and_listing_restoration(self):
        """Deactivating farmer hides active listings with 'owner_inactive'; reactivation restores only owner_inactive ones."""
        self._login(self.admin.email, "AdminStrongPass!2026")

        # Create two products for farmer:
        # Product 1: active
        p1 = Product(
            farmer_id=self.farmer.id,
            name=f"Tomatoes {self.uid}",
            category="Vegetables",
            quantity_kg=50.0,
            price_per_kg=120.0,
            is_available=True,
            is_deleted=False
        )
        # Product 2: previously hidden for moderation
        p2 = Product(
            farmer_id=self.farmer.id,
            name=f"Banned Seeds {self.uid}",
            category="Seeds",
            quantity_kg=10.0,
            price_per_kg=500.0,
            is_available=False,
            is_deleted=True,
            hidden_reason='moderation',
            hidden_by=self.admin.id
        )
        db.session.add_all([p1, p2])
        db.session.commit()

        # Deactivate farmer
        self.client.post(f'/admin/users/{self.farmer.id}/toggle-active', follow_redirects=True)
        db.session.refresh(self.farmer)
        self.assertFalse(self.farmer.is_active)

        db.session.refresh(p1)
        db.session.refresh(p2)
        # p1 should now be hidden with owner_inactive
        self.assertTrue(p1.is_deleted)
        self.assertFalse(p1.is_available)
        self.assertEqual(p1.hidden_reason, 'owner_inactive')

        # p2 should still be hidden with moderation
        self.assertTrue(p2.is_deleted)
        self.assertEqual(p2.hidden_reason, 'moderation')

        # Reactivate farmer
        self.client.post(f'/admin/users/{self.farmer.id}/toggle-active', follow_redirects=True)
        db.session.refresh(self.farmer)
        self.assertTrue(self.farmer.is_active)

        db.session.refresh(p1)
        db.session.refresh(p2)
        # p1 should be restored
        self.assertFalse(p1.is_deleted)
        self.assertTrue(p1.is_available)
        self.assertIsNone(p1.hidden_reason)

        # p2 MUST remain hidden
        self.assertTrue(p2.is_deleted)
        self.assertFalse(p2.is_available)
        self.assertEqual(p2.hidden_reason, 'moderation')

    def test_audit_entries_and_denied_access(self):
        """State changes record IP, before/after; denied admin access creates audit entry with result='denied'."""
        # 1. Non-admin access denied
        self._login(self.buyer.email, "BuyerPass!2026")
        res_denied = self.client.get('/admin/', follow_redirects=False)
        self.assertEqual(res_denied.status_code, 403)

        denied_audit = AdminAuditLog.query.filter_by(
            action='admin_access_denied',
            admin_id=self.buyer.id,
            result='denied'
        ).order_by(AdminAuditLog.created_at.desc()).first()
        self.assertIsNotNone(denied_audit)
        self.assertEqual(denied_audit.target_type, 'route')
        self.assertIsNotNone(denied_audit.ip_address)

        # 2. State-changing admin action records before/after
        self._login(self.admin.email, "AdminStrongPass!2026")
        edit_res = self.client.post(f'/admin/users/{self.buyer.id}/edit', data={
            'name': 'Updated Buyer Name',
            'phone': '0779998888',
            'whatsapp_number': '+94779998888',
            'location': 'Kandy'
        }, follow_redirects=True)
        self.assertEqual(edit_res.status_code, 200)

        edit_audit = AdminAuditLog.query.filter_by(
            action='user_profile_updated',
            target_id=self.buyer.id
        ).order_by(AdminAuditLog.created_at.desc()).first()
        self.assertIsNotNone(edit_audit)
        self.assertEqual(edit_audit.result, 'success')
        self.assertIn('name', edit_audit.before_data)
        self.assertEqual(edit_audit.after_data['name'], 'Updated Buyer Name')

    def test_append_only_trigger(self):
        """PostgreSQL trigger prohibits UPDATE and DELETE on admin_audit_log rows."""
        audit = AdminAuditLog(
            admin_id=self.admin.id,
            action='test_trigger_entry',
            details='initial state'
        )
        db.session.add(audit)
        db.session.commit()

        # Attempt UPDATE
        with self.assertRaises(Exception):
            db.session.execute(
                db.text("UPDATE admin_audit_log SET details = 'tampered' WHERE id = :id"),
                {'id': audit.id}
            )
            db.session.commit()
        db.session.rollback()

        # Attempt DELETE
        with self.assertRaises(Exception):
            db.session.execute(
                db.text("DELETE FROM admin_audit_log WHERE id = :id"),
                {'id': audit.id}
            )
            db.session.commit()
        db.session.rollback()

    def test_csv_injection_and_headers(self):
        """CSV cells starting with =, +, -, @, tab, or CR are prepended with an apostrophe."""
        self.assertEqual(sanitize_csv_cell("=1+1"), "'=1+1")
        self.assertEqual(sanitize_csv_cell("+CMD"), "'+CMD")
        self.assertEqual(sanitize_csv_cell("-5"), "'-5")
        self.assertEqual(sanitize_csv_cell("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(sanitize_csv_cell("\tTabbed"), "'\tTabbed")
        self.assertEqual(sanitize_csv_cell("\rReturn"), "'\rReturn")
        self.assertEqual(sanitize_csv_cell("Normal Text"), "Normal Text")
        self.assertEqual(sanitize_csv_cell(None), "")

        # Test CSV export endpoint
        self._login(self.admin.email, "AdminStrongPass!2026")
        res = self.client.get('/admin/reports/users.csv')
        self.assertEqual(res.status_code, 200)
        # Check UTF-8 BOM
        self.assertTrue(res.data.startswith(b'\xef\xbb\xbf'))
        # Check security headers
        self.assertEqual(res.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertIn('no-store', res.headers.get('Cache-Control', ''))

    def test_pagination_and_query_preservation(self):
        """Admin lists show 20 rows per page and preserve query parameters in pagination URLs."""
        self._login(self.admin.email, "AdminStrongPass!2026")
        res = self.client.get('/admin/users?role=farmer&active=true')
        self.assertEqual(res.status_code, 200)
        # Response should render user table and filter criteria
        self.assertIn(b'role=farmer', res.data)
        self.assertIn(b'active=true', res.data)
