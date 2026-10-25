"""
Unit tests for geospatial utilities (utils/geo.py).
"""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from utils.geo import haversine_km, is_in_sri_lanka, parse_coord, time_ago


class TestParseCoord(unittest.TestCase):
    def test_parse_valid_strings(self):
        self.assertEqual(parse_coord("6.9271"), Decimal("6.9271"))
        self.assertEqual(parse_coord(" 80.7718 "), Decimal("80.7718"))
        self.assertEqual(parse_coord("-79.8612"), Decimal("-79.8612"))
        self.assertEqual(parse_coord("0"), Decimal("0"))

    def test_parse_numbers(self):
        self.assertEqual(parse_coord(7.8731), Decimal("7.8731"))
        self.assertEqual(parse_coord(80), Decimal("80"))
        self.assertEqual(parse_coord(Decimal("9.9")), Decimal("9.9"))

    def test_parse_invalid_values(self):
        self.assertIsNone(parse_coord(None))
        self.assertIsNone(parse_coord(""))
        self.assertIsNone(parse_coord("   "))
        self.assertIsNone(parse_coord("not-a-number"))
        self.assertIsNone(parse_coord([6.9271]))
        self.assertIsNone(parse_coord(float("nan")))
        self.assertIsNone(parse_coord(float("inf")))

    def test_parse_out_of_bounds(self):
        # Coordinates must be between -180 and 180
        self.assertIsNone(parse_coord("180.0001"))
        self.assertIsNone(parse_coord("-180.0001"))
        self.assertEqual(parse_coord("180"), Decimal("180"))
        self.assertEqual(parse_coord("-180"), Decimal("-180"))


class TestIsInSriLanka(unittest.TestCase):
    def test_major_sri_lankan_cities(self):
        # Colombo
        self.assertTrue(is_in_sri_lanka(6.9271, 79.8612))
        # Kandy
        self.assertTrue(is_in_sri_lanka(7.2906, 80.6337))
        # Jaffna
        self.assertTrue(is_in_sri_lanka(9.6615, 80.0255))
        # Dondra / Matara (Southern tip)
        self.assertTrue(is_in_sri_lanka(5.9248, 80.5878))
        # Batticaloa (Eastern coast)
        self.assertTrue(is_in_sri_lanka(7.7170, 81.7000))
        # Central point
        self.assertTrue(is_in_sri_lanka(7.8731, 80.7718))

    def test_boundary_edges(self):
        # Exact corners: lat 5.8 to 9.9, lng 79.4 to 82.0
        self.assertTrue(is_in_sri_lanka(5.8, 79.4))
        self.assertTrue(is_in_sri_lanka(9.9, 82.0))
        self.assertTrue(is_in_sri_lanka(5.8, 82.0))
        self.assertTrue(is_in_sri_lanka(9.9, 79.4))

        # Outside boundary by small epsilon
        self.assertFalse(is_in_sri_lanka(5.799, 80.0))
        self.assertFalse(is_in_sri_lanka(9.901, 80.0))
        self.assertFalse(is_in_sri_lanka(7.0, 79.399))
        self.assertFalse(is_in_sri_lanka(7.0, 82.001))

    def test_foreign_locations(self):
        # London
        self.assertFalse(is_in_sri_lanka(51.5074, -0.1278))
        # Chennai, India
        self.assertFalse(is_in_sri_lanka(13.0827, 80.2707))
        # Maldives
        self.assertFalse(is_in_sri_lanka(3.2028, 73.2207))

    def test_invalid_coords(self):
        self.assertFalse(is_in_sri_lanka(None, 80.0))
        self.assertFalse(is_in_sri_lanka("invalid", 80.0))
        self.assertFalse(is_in_sri_lanka(7.0, None))


class TestHaversineKm(unittest.TestCase):
    def test_same_point(self):
        dist = haversine_km(6.9271, 79.8612, 6.9271, 79.8612)
        self.assertEqual(dist, 0.0)

    def test_colombo_to_kandy(self):
        # Colombo ~6.9271, 79.8612; Kandy ~7.2906, 80.6337
        # Straight-line distance is ~95 to 105 km
        dist = haversine_km(6.9271, 79.8612, 7.2906, 80.6337)
        self.assertGreater(dist, 90.0)
        self.assertLess(dist, 110.0)

    def test_colombo_to_jaffna(self):
        # Colombo to Jaffna ~300 to 320 km
        dist = haversine_km(6.9271, 79.8612, 9.6615, 80.0255)
        self.assertGreater(dist, 290.0)
        self.assertLess(dist, 320.0)

    def test_string_and_decimal_inputs(self):
        dist1 = haversine_km("6.9271", "79.8612", "7.2906", "80.6337")
        dist2 = haversine_km(Decimal("6.9271"), Decimal("79.8612"), Decimal("7.2906"), Decimal("80.6337"))
        self.assertEqual(dist1, dist2)

    def test_invalid_inputs_raise_value_error(self):
        with self.assertRaises(ValueError):
            haversine_km(None, 79.8612, 7.2906, 80.6337)

        with self.assertRaises(ValueError):
            haversine_km("invalid", 79.8612, 7.2906, 80.6337)

        # Latitude > 90
        with self.assertRaises(ValueError):
            haversine_km(95.0, 79.8612, 7.2906, 80.6337)


class TestTimeAgo(unittest.TestCase):
    def test_none_input(self):
        self.assertEqual(time_ago(None), "")
        self.assertEqual(time_ago("not-a-dt"), "")

    def test_just_now(self):
        now = datetime(2026, 10, 25, 12, 0, 0)
        self.assertEqual(time_ago(now - timedelta(seconds=15), now=now), "just now")
        self.assertEqual(time_ago(now - timedelta(seconds=59), now=now), "just now")
        # Future date edge case
        self.assertEqual(time_ago(now + timedelta(seconds=10), now=now), "just now")

    def test_minutes_ago(self):
        now = datetime(2026, 10, 25, 12, 0, 0)
        self.assertEqual(time_ago(now - timedelta(minutes=1), now=now), "1 minute ago")
        self.assertEqual(time_ago(now - timedelta(minutes=5), now=now), "5 minutes ago")
        self.assertEqual(time_ago(now - timedelta(minutes=45), now=now), "45 minutes ago")

    def test_hours_ago(self):
        now = datetime(2026, 10, 25, 12, 0, 0)
        self.assertEqual(time_ago(now - timedelta(hours=1), now=now), "1 hour ago")
        self.assertEqual(time_ago(now - timedelta(hours=5), now=now), "5 hours ago")

    def test_days_and_weeks(self):
        now = datetime(2026, 10, 25, 12, 0, 0)
        self.assertEqual(time_ago(now - timedelta(days=1), now=now), "yesterday")
        self.assertEqual(time_ago(now - timedelta(days=3), now=now), "3 days ago")
        self.assertEqual(time_ago(now - timedelta(days=7), now=now), "1 week ago")
        self.assertEqual(time_ago(now - timedelta(days=14), now=now), "2 weeks ago")

    def test_months_and_years(self):
        now = datetime(2026, 10, 25, 12, 0, 0)
        self.assertEqual(time_ago(now - timedelta(days=32), now=now), "1 month ago")
        self.assertEqual(time_ago(now - timedelta(days=95), now=now), "3 months ago")
        self.assertEqual(time_ago(now - timedelta(days=370), now=now), "1 year ago")
        self.assertEqual(time_ago(now - timedelta(days=750), now=now), "2 years ago")

    def test_timezone_aware(self):
        now = datetime.now(timezone.utc)
        dt = now - timedelta(minutes=5)
        self.assertEqual(time_ago(dt, now=now), "5 minutes ago")


if __name__ == '__main__':
    unittest.main()
