"""Unit tests for delivery pricing service."""
import unittest
from decimal import Decimal

from services.pricing import calculate_delivery_fee, calculate_order_totals
from config import (
    DELIVERY_BASE_FEE,
    DELIVERY_BASE_KM,
    DELIVERY_EXTRA_PER_KM,
    MAX_DELIVERY_KM,
)


class TestDeliveryPricing(unittest.TestCase):
    """Test calculate_delivery_fee and calculate_order_totals."""

    def test_fee_at_zero_km(self):
        """0 km should incur base fee."""
        fee = calculate_delivery_fee(0)
        self.assertEqual(fee, Decimal("5000"))

    def test_fee_at_ten_km(self):
        """10 km (<= 50 km) should incur base fee."""
        fee = calculate_delivery_fee(10)
        self.assertEqual(fee, Decimal("5000"))

    def test_fee_at_49_point_9_km(self):
        """49.9 km (<= 50 km) should incur base fee."""
        fee = calculate_delivery_fee(49.9)
        self.assertEqual(fee, Decimal("5000"))

    def test_fee_at_50_km(self):
        """50 km exactly should incur base fee."""
        fee = calculate_delivery_fee(50)
        self.assertEqual(fee, Decimal("5000"))

    def test_fee_rounding_half_up_boundary(self):
        """50.00 vs 50.001: 50.001 rounds to 50.00, incurring base fee."""
        fee_50_00 = calculate_delivery_fee("50.00")
        self.assertEqual(fee_50_00, Decimal("5000"))

        fee_50_001 = calculate_delivery_fee("50.001")
        self.assertEqual(fee_50_001, Decimal("5000"))

    def test_fee_at_50_point_01_km(self):
        """50.01 km: ceil(50.01 - 50) = 1 extra km -> 5000 + 60*1 = 5060."""
        fee = calculate_delivery_fee("50.01")
        self.assertEqual(fee, Decimal("5060"))

    def test_fee_at_50_point_1_km(self):
        """50.1 km: ceil(50.10 - 50) = 1 extra km -> 5000 + 60*1 = 5060."""
        fee = calculate_delivery_fee("50.1")
        self.assertEqual(fee, Decimal("5060"))

    def test_fee_at_72_point_3_km(self):
        """72.3 km: ceil(72.30 - 50) = 23 extra km -> 5000 + 60*23 = 6380."""
        fee = calculate_delivery_fee("72.3")
        self.assertEqual(fee, Decimal("6380"))

    def test_fee_at_115_km(self):
        """115 km: ceil(115 - 50) = 65 extra km -> 5000 + 60*65 = 8900."""
        fee = calculate_delivery_fee(115)
        self.assertEqual(fee, Decimal("8900"))

    def test_fee_at_max_distance(self):
        """At MAX_DELIVERY_KM (300 km): 5000 + 60*250 = 20000."""
        fee = calculate_delivery_fee(MAX_DELIVERY_KM)
        self.assertEqual(fee, Decimal("20000"))

    def test_fee_exceeding_max_distance(self):
        """Beyond MAX_DELIVERY_KM (e.g. 300.01) should raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_delivery_fee("300.01")
        with self.assertRaises(ValueError):
            calculate_delivery_fee(350)

    def test_fee_negative_distance(self):
        """Negative distances should raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_delivery_fee(-1)
        with self.assertRaises(ValueError):
            calculate_delivery_fee("-0.01")

    def test_fee_none_distance(self):
        """None distance should raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_delivery_fee(None)

    def test_calculate_order_totals_standard(self):
        """Order totals calculation: items_total + fee = grand_total."""
        totals = calculate_order_totals(Decimal("2500.50"), Decimal("5060.00"))
        self.assertEqual(totals["items_total"], Decimal("2500.50"))
        self.assertEqual(totals["delivery_fee"], Decimal("5060.00"))
        self.assertEqual(totals["grand_total"], Decimal("7560.50"))
        self.assertEqual(totals["total_price"], Decimal("7560.50"))

    def test_calculate_order_totals_default_zero_fee(self):
        """Default fee is 0 for pickup orders."""
        totals = calculate_order_totals(1000)
        self.assertEqual(totals["items_total"], Decimal("1000.00"))
        self.assertEqual(totals["delivery_fee"], Decimal("0.00"))
        self.assertEqual(totals["grand_total"], Decimal("1000.00"))

    def test_calculate_order_totals_invalid(self):
        """Negative values or None items_total should raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_order_totals(None)
        with self.assertRaises(ValueError):
            calculate_order_totals(-100)
        with self.assertRaises(ValueError):
            calculate_order_totals(100, -50)


if __name__ == "__main__":
    unittest.main()
