"""
Tests for the redesigned photo hero section on the AgroLink home page.
Verifies that hero text, pill badge, buttons (guest and authenticated),
the new photo markup, and unchanged downstream sections render properly.
"""
import unittest
from app import create_app
from extensions import db
from models import User


class TestHomeHero(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_home_returns_200(self):
        """Home page should return 200 OK."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_hero_headline_present(self):
        """Hero headline with two-tone styling must be present."""
        response = self.client.get('/')
        self.assertIn(b'Fresh from Sri Lankan Farms,', response.data)
        self.assertIn(b'Direct to Your Doorstep.', response.data)

    def test_hero_badge_pill_present(self):
        """Value pill badge must retain exact wording."""
        response = self.client.get('/')
        self.assertIn(b'Direct Farm-to-Buyer Trading in Sri Lanka', response.data)

    def test_hero_paragraph_present(self):
        """Introductory paragraph text must retain exact wording."""
        response = self.client.get('/')
        self.assertIn(b'Connecting verified local growers directly with commercial buyers', response.data)
        self.assertIn(b'transparent Pettah price benchmarks', response.data)

    def test_hero_guest_buttons_present(self):
        """Unauthenticated visitor sees guest CTAs."""
        response = self.client.get('/')
        self.assertIn(b'Browse fresh produce', response.data)
        self.assertIn(b"I'm a farmer: start selling", response.data)

    def test_hero_photo_markup_and_placeholder(self):
        """Hero photo must render as a picture element with webp and jpeg sources."""
        response = self.client.get('/')
        self.assertIn(b'farmer-greenhouse-640.webp', response.data)
        self.assertIn(b'farmer-greenhouse.jpeg', response.data)
        self.assertIn(b'Smiling farmer in a greenhouse checking her phone', response.data)
        self.assertIn(b'fetchpriority="high"', response.data)
        self.assertIn(b'hero-ambient-bg', response.data)

    def test_photo_card_text_unchanged(self):
        """Card title, subtitle, live network badge, and 3 stats must be present."""
        response = self.client.get('/')
        self.assertIn(b'Direct Sri Lankan Harvest', response.data)
        self.assertIn(b'Bypassing Middleman Distribution', response.data)
        self.assertIn(b'Live Network', response.data)
        self.assertIn(b'0%', response.data)
        self.assertIn(b'Broker Fees', response.data)
        self.assertIn(b'25', response.data)
        self.assertIn(b'Districts', response.data)
        self.assertIn(b'100%', response.data)
        self.assertIn(b'Direct Trade', response.data)

    def test_trust_strip_and_categories_still_present(self):
        """Sections downstream of the hero must remain untouched."""
        response = self.client.get('/')
        self.assertIn(b'Platform Live Metrics', response.data)
        self.assertIn(b'Explore Harvest Categories', response.data)
        self.assertIn(b'How AgroLink Works', response.data)

    def test_category_ampersand_not_double_escaped(self):
        """Category titles and descriptions must not render literal &amp; entities on screen."""
        response = self.client.get('/')
        html = response.data.decode('utf-8')
        self.assertNotIn('&amp;amp;', html)
        self.assertNotIn('Grains &amp;amp; Rice', html)
        self.assertNotIn('Roots &amp;amp; Tubers', html)

    def test_authenticated_user_sees_dashboard_button(self):
        """Authenticated user sees dashboard CTA instead of guest CTA."""
        with self.app.app_context():
            user = User.query.filter_by(role='farmer').first()
            if not user:
                user = User.query.first()
            if user:
                with self.client.session_transaction() as sess:
                    sess['_user_id'] = str(user.id)
                    sess['_fresh'] = True
                response = self.client.get('/')
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'Continue to your dashboard', response.data)
                self.assertIn(b'Browse Marketplace', response.data)


if __name__ == '__main__':
    unittest.main()
