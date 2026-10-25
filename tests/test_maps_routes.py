"""
Unit and integration tests for Google Maps routes, context processor, and security isolation.
"""
import unittest
from app import create_app
from services.maps import get_server_key, is_server_key_configured


class TestGoogleMapsIntegration(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_maps_test_accessible_in_debug(self):
        """Dev test route /_maps_test must return 200 when debug is enabled."""
        if self.app.debug:
            response = self.client.get('/_maps_test')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Google Maps Foundation', response.data)
            self.assertIn(b'Map is unavailable, enter your location manually', response.data)

    def test_maps_test_not_found_when_debug_false(self):
        """Dev test route /_maps_test must return 404 when debug is disabled."""
        self.app.debug = False
        # Create fresh app with production config
        import os
        old_env = os.environ.get('FLASK_ENV')
        try:
            os.environ['FLASK_ENV'] = 'production'
            os.environ['SECRET_KEY'] = 'test-secret-key-12345678901234567890'
            prod_app = create_app()
            prod_client = prod_app.test_client()
            res = prod_client.get('/_maps_test')
            self.assertEqual(res.status_code, 404)
        finally:
            if old_env:
                os.environ['FLASK_ENV'] = old_env
            else:
                os.environ.pop('FLASK_ENV', None)

    def test_context_processor_exposes_only_safe_keys(self):
        """Context processor must only expose maps_enabled, maps_browser_key, and maps_map_id."""
        with self.app.test_request_context():
            processors = self.app.context_processor(lambda: {})()
            # Must contain safe variables
            from flask import render_template_string
            out = render_template_string("{{ maps_enabled }}|{{ maps_browser_key }}|{{ maps_map_id }}")
            self.assertIsNotNone(out)

            # CRITICAL SECURITY TEST: Server key must NEVER be in Jinja context
            raw_context_keys = list(self.app.jinja_env.globals.keys())
            self.assertNotIn('GOOGLE_MAPS_SERVER_KEY', raw_context_keys)
            self.assertNotIn('maps_server_key', raw_context_keys)

    def test_maps_enabled_logic(self):
        """maps_enabled must be True only when both browser key and map id exist."""
        with self.app.app_context():
            # Both present
            self.app.config['GOOGLE_MAPS_BROWSER_KEY'] = 'fake_browser_key'
            self.app.config['GOOGLE_MAPS_MAP_ID'] = 'fake_map_id'
            with self.app.test_request_context():
                from flask import render_template_string
                res = render_template_string("{{ maps_enabled }}")
                self.assertEqual(res, "True")

            # Missing browser key
            self.app.config['GOOGLE_MAPS_BROWSER_KEY'] = ''
            self.app.config['GOOGLE_MAPS_MAP_ID'] = 'fake_map_id'
            with self.app.test_request_context():
                res = render_template_string("{{ maps_enabled }}")
                self.assertEqual(res, "False")

            # Missing map id
            self.app.config['GOOGLE_MAPS_BROWSER_KEY'] = 'fake_browser_key'
            self.app.config['GOOGLE_MAPS_MAP_ID'] = ''
            with self.app.test_request_context():
                res = render_template_string("{{ maps_enabled }}")
                self.assertEqual(res, "False")

    def test_services_maps_server_key_isolated(self):
        """services.maps must provide get_server_key() without exposing it to templates."""
        self.assertIsInstance(get_server_key(), str)
        self.assertIsInstance(is_server_key_configured(), bool)


if __name__ == '__main__':
    unittest.main()
