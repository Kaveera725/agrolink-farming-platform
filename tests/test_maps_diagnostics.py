"""
Unit and integration tests for Google Maps diagnostics, placeholder detection,
context processor behavior, and server key security isolation.
All external Google API calls are strictly mocked (no internet dependency).
"""
import io
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from app import create_app
from services.maps import (
    get_server_key,
    is_placeholder_value,
    is_server_key_configured,
    test_geocoding_api,
)


class TestMapsDiagnostics(unittest.TestCase):
    def setUp(self):
        self.app = create_app(debug=True)
        self.client = self.app.test_client()
        self.runner = self.app.test_cli_runner()

    # 1. Placeholder Detection Tests
    def test_is_placeholder_value_detected(self):
        """Must identify strings starting with your_, ending with ..., or containing paste."""
        # Starts with 'your_'
        self.assertTrue(is_placeholder_value("your_api_key_here"))
        self.assertTrue(is_placeholder_value("YOUR_BROWSER_KEY"))
        self.assertTrue(is_placeholder_value("your_map_id"))

        # Ends with '...'
        self.assertTrue(is_placeholder_value("AIzaSy..."))
        self.assertTrue(is_placeholder_value("map_id_..."))
        self.assertTrue(is_placeholder_value("key..."))

        # Contains 'paste' (case-insensitive)
        self.assertTrue(is_placeholder_value("paste_your_key_here"))
        self.assertTrue(is_placeholder_value("PASTE_KEY"))
        self.assertTrue(is_placeholder_value("please_paste_real_key"))

    def test_is_placeholder_value_negative(self):
        """Real looking or non-placeholder strings should return False."""
        self.assertFalse(is_placeholder_value("AIzaSyD-abc12345678901234567890"))
        self.assertFalse(is_placeholder_value("99887766554433221100"))
        self.assertFalse(is_placeholder_value(""))
        self.assertFalse(is_placeholder_value(None))
        self.assertFalse(is_placeholder_value(12345))

    # 2. Context Processor Tests: With and Without Values
    def test_context_processor_with_values(self):
        """When browser key and map id exist, maps_enabled must be True with credentials exposed."""
        with self.app.app_context():
            self.app.config['GOOGLE_MAPS_BROWSER_KEY'] = 'test_browser_key_abc'
            self.app.config['GOOGLE_MAPS_MAP_ID'] = 'test_map_id_123'

            with self.app.test_request_context():
                from flask import render_template_string
                rendered = render_template_string(
                    "enabled={{ maps_enabled }}|key={{ maps_browser_key }}|id={{ maps_map_id }}"
                )
                self.assertEqual(
                    rendered,
                    "enabled=True|key=test_browser_key_abc|id=test_map_id_123"
                )

    def test_context_processor_without_browser_key(self):
        """When browser key is missing, maps_enabled must be False and keys empty."""
        with self.app.app_context():
            self.app.config['GOOGLE_MAPS_BROWSER_KEY'] = ''
            self.app.config['GOOGLE_MAPS_MAP_ID'] = 'test_map_id_123'

            with self.app.test_request_context():
                from flask import render_template_string
                rendered = render_template_string(
                    "enabled={{ maps_enabled }}|key={{ maps_browser_key }}|id={{ maps_map_id }}"
                )
                self.assertEqual(rendered, "enabled=False|key=|id=")

    def test_context_processor_without_map_id(self):
        """When map id is missing, maps_enabled must be False and keys empty."""
        with self.app.app_context():
            self.app.config['GOOGLE_MAPS_BROWSER_KEY'] = 'test_browser_key_abc'
            self.app.config['GOOGLE_MAPS_MAP_ID'] = ''

            with self.app.test_request_context():
                from flask import render_template_string
                rendered = render_template_string(
                    "enabled={{ maps_enabled }}|key={{ maps_browser_key }}|id={{ maps_map_id }}"
                )
                self.assertEqual(rendered, "enabled=False|key=|id=")

    def test_context_processor_without_both(self):
        """When both are missing, maps_enabled must be False and keys empty."""
        with self.app.app_context():
            self.app.config['GOOGLE_MAPS_BROWSER_KEY'] = ''
            self.app.config['GOOGLE_MAPS_MAP_ID'] = ''

            with self.app.test_request_context():
                from flask import render_template_string
                rendered = render_template_string(
                    "enabled={{ maps_enabled }}|key={{ maps_browser_key }}|id={{ maps_map_id }}"
                )
                self.assertEqual(rendered, "enabled=False|key=|id=")

    # 3. Server Key Never Appears in Any Rendered Template Output
    def test_server_key_never_appears_in_rendered_templates(self):
        """CRITICAL SECURITY: Server key must NEVER leak in any template output."""
        canary_secret = "SUPER_SECRET_CANARY_KEY_XYZ_9876543210"
        with patch('services.maps.get_server_key', return_value=canary_secret):
            # Test /_maps_test route
            res_maps_test = self.client.get('/_maps_test')
            self.assertEqual(res_maps_test.status_code, 200)
            self.assertNotIn(canary_secret.encode('utf-8'), res_maps_test.data)

            # Test Home page
            res_home = self.client.get('/')
            self.assertEqual(res_home.status_code, 200)
            self.assertNotIn(canary_secret.encode('utf-8'), res_home.data)

            # Test Marketplace page
            res_market = self.client.get('/marketplace/')
            self.assertEqual(res_market.status_code, 200)
            self.assertNotIn(canary_secret.encode('utf-8'), res_market.data)

    # 4. Mocked Geocoding API Calls in test_geocoding_api
    @patch('urllib.request.urlopen')
    def test_geocoding_api_mocked_success(self, mock_urlopen):
        """Mock successful geocoding response from Google."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "OK",
            "results": [{"formatted_address": "Kandy, Sri Lanka"}]
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        status, error_message = test_geocoding_api(server_key="valid_mock_server_key_123")
        self.assertEqual(status, "OK")
        self.assertEqual(error_message, "")

    @patch('urllib.request.urlopen')
    def test_geocoding_api_mocked_denied(self, mock_urlopen):
        """Mock denied geocoding response from Google."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "status": "REQUEST_DENIED",
            "error_message": "The provided API key is invalid."
        }).encode('utf-8')
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        status, error_message = test_geocoding_api(server_key="invalid_mock_server_key_123")
        self.assertEqual(status, "REQUEST_DENIED")
        self.assertEqual(error_message, "The provided API key is invalid.")

    def test_geocoding_api_skipped_on_placeholder_or_missing(self):
        """Must skip call when key is missing or is placeholder."""
        status_missing, _ = test_geocoding_api(server_key="")
        self.assertEqual(status_missing, "MISSING_KEY")

        status_placeholder, _ = test_geocoding_api(server_key="your_server_key_here")
        self.assertEqual(status_placeholder, "PLACEHOLDER_KEY")

    # 5. CLI Command 'flask maps-check' with Mocked Geocoding
    @patch('services.maps.test_geocoding_api', return_value=("OK", ""))
    def test_flask_maps_check_cli_success(self, mock_test_geo):
        """Test flask maps-check CLI output formatting and referrer display."""
        result = self.runner.invoke(args=['maps-check'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("AgroLink Google Maps Configuration Diagnostic", result.output)
        self.assertIn("Environment Variables Status", result.output)
        self.assertIn("Geocoding API Server-Side Check:", result.output)
        self.assertIn("Status: OK", result.output)
        self.assertIn("http://localhost:5000/*", result.output)
        self.assertIn("http://127.0.0.1:5000/*", result.output)

    @patch('services.maps.test_geocoding_api', return_value=("REQUEST_DENIED", "The provided API key is invalid."))
    def test_flask_maps_check_cli_denied(self, mock_test_geo):
        """Test flask maps-check CLI reports REQUEST_DENIED with error message."""
        result = self.runner.invoke(args=['maps-check'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("REQUEST_DENIED - The provided API key is invalid.", result.output)


if __name__ == '__main__':
    unittest.main()
