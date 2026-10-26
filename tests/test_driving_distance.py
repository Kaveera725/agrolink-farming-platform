"""Unit tests for driving distance calculation service using mocked requests."""
import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal
import requests

from services.distance import get_driving_distance_km, clear_distance_cache
from config import ROUTE_FALLBACK_FACTOR
from utils.geo import haversine_km


class TestDrivingDistance(unittest.TestCase):
    """Test get_driving_distance_km with various Google Routes API scenarios."""

    def setUp(self):
        clear_distance_cache()
        self.colombo = (Decimal("6.9271"), Decimal("79.8612"))
        self.kandy = (Decimal("7.2906"), Decimal("80.6337"))

    def tearDown(self):
        clear_distance_cache()

    @patch("services.distance.get_server_key", return_value="AIzaSyTestValidServerKey")
    @patch("services.distance.requests.post")
    def test_routes_api_success(self, mock_post, mock_key):
        """Successful Google Routes API response returns driving distance in km (google)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"routes": [{"distanceMeters": 121184}]}
        mock_post.return_value = mock_response

        dist, source = get_driving_distance_km(
            self.colombo[0], self.colombo[1],
            self.kandy[0], self.kandy[1]
        )

        self.assertEqual(dist, Decimal("121.18"))
        self.assertEqual(source, "google")
        mock_post.assert_called_once()

        # Check call arguments
        call_kwargs = mock_post.call_args[1]
        self.assertIn("X-Goog-Api-Key", call_kwargs["headers"])
        self.assertEqual(call_kwargs["headers"]["X-Goog-FieldMask"], "routes.distanceMeters")
        self.assertEqual(call_kwargs["json"]["travelMode"], "DRIVE")

    @patch("services.distance.get_server_key", return_value="AIzaSyTestValidServerKey")
    @patch("services.distance.requests.post")
    def test_routes_api_403_error_fallback(self, mock_post, mock_key):
        """API error 403 falls back to haversine * factor without raising."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = '{"error": {"code": 403, "message": "Method not allowed"}}'
        mock_post.return_value = mock_response

        dist, source = get_driving_distance_km(
            self.colombo[0], self.colombo[1],
            self.kandy[0], self.kandy[1]
        )

        expected_est = (Decimal(str(haversine_km(self.colombo[0], self.colombo[1], self.kandy[0], self.kandy[1]))) * ROUTE_FALLBACK_FACTOR).quantize(Decimal("0.01"))
        self.assertEqual(dist, expected_est)
        self.assertEqual(source, "estimated")

    @patch("services.distance.get_server_key", return_value="AIzaSyTestValidServerKey")
    @patch("services.distance.requests.post")
    def test_routes_api_timeout_fallback(self, mock_post, mock_key):
        """Request timeout falls back to haversine * factor without raising."""
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        dist, source = get_driving_distance_km(
            self.colombo[0], self.colombo[1],
            self.kandy[0], self.kandy[1]
        )

        expected_est = (Decimal(str(haversine_km(self.colombo[0], self.colombo[1], self.kandy[0], self.kandy[1]))) * ROUTE_FALLBACK_FACTOR).quantize(Decimal("0.01"))
        self.assertEqual(dist, expected_est)
        self.assertEqual(source, "estimated")

    @patch("services.distance.get_server_key", return_value="AIzaSyTestValidServerKey")
    @patch("services.distance.requests.post")
    def test_routes_api_empty_routes_fallback(self, mock_post, mock_key):
        """Response with empty routes array falls back to estimated."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"routes": []}
        mock_post.return_value = mock_response

        dist, source = get_driving_distance_km(
            self.colombo[0], self.colombo[1],
            self.kandy[0], self.kandy[1]
        )

        expected_est = (Decimal(str(haversine_km(self.colombo[0], self.colombo[1], self.kandy[0], self.kandy[1]))) * ROUTE_FALLBACK_FACTOR).quantize(Decimal("0.01"))
        self.assertEqual(dist, expected_est)
        self.assertEqual(source, "estimated")

    @patch("services.distance.get_server_key", return_value="")
    @patch("services.distance.requests.post")
    def test_missing_server_key_fallback(self, mock_post, mock_key):
        """Missing server key immediately falls back to estimated without calling Google."""
        dist, source = get_driving_distance_km(
            self.colombo[0], self.colombo[1],
            self.kandy[0], self.kandy[1]
        )

        expected_est = (Decimal(str(haversine_km(self.colombo[0], self.colombo[1], self.kandy[0], self.kandy[1]))) * ROUTE_FALLBACK_FACTOR).quantize(Decimal("0.01"))
        self.assertEqual(dist, expected_est)
        self.assertEqual(source, "estimated")
        mock_post.assert_not_called()

    @patch("services.distance.get_server_key", return_value="AIzaSyTestValidServerKey")
    @patch("services.distance.requests.post")
    def test_cache_hit_avoids_repeated_http_request(self, mock_post, mock_key):
        """A second call with coordinates rounded to 4 decimals hits the cache without HTTP call."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"routes": [{"distanceMeters": 121184}]}
        mock_post.return_value = mock_response

        # Call 1: HTTP request is made
        dist1, source1 = get_driving_distance_km(
            self.colombo[0], self.colombo[1],
            self.kandy[0], self.kandy[1]
        )
        self.assertEqual(dist1, Decimal("121.18"))
        self.assertEqual(source1, "google")
        self.assertEqual(mock_post.call_count, 1)

        # Call 2 with identical/nearly identical coords within 4 decimals
        dist2, source2 = get_driving_distance_km(
            Decimal("6.927101"), Decimal("79.861201"),
            Decimal("7.290601"), Decimal("80.633701")
        )
        self.assertEqual(dist2, Decimal("121.18"))
        self.assertEqual(source2, "google")
        # Ensure requests.post was NOT called a second time
        self.assertEqual(mock_post.call_count, 1)

    def test_out_of_bounds_raises_value_error(self):
        """Coordinates outside Sri Lanka bounds raise ValueError before calling API."""
        # Origin outside Sri Lanka (e.g. London: 51.5, -0.1)
        with self.assertRaises(ValueError):
            get_driving_distance_km(51.5, -0.1, self.kandy[0], self.kandy[1])

        # Destination outside Sri Lanka
        with self.assertRaises(ValueError):
            get_driving_distance_km(self.colombo[0], self.colombo[1], 12.0, 75.0)

        # Invalid/None coords
        with self.assertRaises(ValueError):
            get_driving_distance_km(None, self.colombo[1], self.kandy[0], self.kandy[1])


if __name__ == "__main__":
    unittest.main()
