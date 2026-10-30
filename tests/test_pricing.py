import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from shopify.pricing import calculate_selling_price
from shopify.dashboard_json import load_dashboard_product_data, get_product_cost


class PricingTests(unittest.TestCase):
    def test_40_percent_markup(self):
        self.assertEqual(calculate_selling_price("500"), Decimal("700.00"))

    def test_rounds_to_two_decimal_places(self):
        self.assertEqual(calculate_selling_price("999.99"), Decimal("1399.99"))

    def test_rejects_missing_or_invalid_cost(self):
        for value in (None, "", "abc", "0", "-10"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_selling_price(value)

    def test_matches_dashboard_record_to_cloudinary_public_id(self):
        payload = {
            "products": [
                {"public_id": "catalog/item-a", "cost_price": 100},
                {"public_id": "catalog/item-b", "cost_price": 500},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dashboard.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            record = load_dashboard_product_data(
                {"public_id": "catalog/item-b", "url": "https://example.com/item-b.jpg"},
                path
            )
        self.assertEqual(get_product_cost(record), 500)


if __name__ == "__main__":
    unittest.main()
