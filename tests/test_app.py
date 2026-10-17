import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app as inventory_app


class InventoryAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.products_path = Path(self.temp_dir.name) / "products.json"
        self.sales_path = Path(self.temp_dir.name) / "sales.json"
        self.products_path.write_text(
            json.dumps(
                [
                    {
                        "product_id": "PRD-1",
                        "name": "Test Mouse",
                        "category": "Electronics",
                        "price": 10.0,
                        "quantity": 5,
                        "low_stock_threshold": 2,
                    }
                ]
            ),
            encoding="utf-8",
        )
        self.sales_path.write_text("[]", encoding="utf-8")
        self.products_patch = patch.object(inventory_app, "PRODUCTS_FILE", self.products_path)
        self.sales_patch = patch.object(inventory_app, "SALES_FILE", self.sales_path)
        self.products_patch.start()
        self.sales_patch.start()
        inventory_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = inventory_app.app.test_client()

    def tearDown(self):
        self.products_patch.stop()
        self.sales_patch.stop()
        self.temp_dir.cleanup()

    def csrf_token(self):
        page = self.client.get("/products/new")
        return re.search(
            rb'name="csrf_token" value="([^"]+)"', page.data
        ).group(1).decode()

    def post_form(self, url, data):
        return self.client.post(url, data={"csrf_token": self.csrf_token(), **data})

    def read_products(self):
        return json.loads(self.products_path.read_text(encoding="utf-8"))

    def test_product_create_edit_restock_and_delete(self):
        created = self.post_form(
            "/products/new",
            {
                "name": "Desk Lamp",
                "category": "Home",
                "price": "20",
                "quantity": "3",
                "low_stock_threshold": "1",
            },
        )
        self.assertEqual(created.status_code, 302)
        products = self.read_products()
        lamp = next(item for item in products if item["name"] == "Desk Lamp")

        edited = self.post_form(
            f"/products/{lamp['product_id']}/edit",
            {
                "name": "Modern Desk Lamp",
                "category": "Home",
                "price": "22.50",
                "quantity": "99",
                "low_stock_threshold": "2",
            },
        )
        self.assertEqual(edited.status_code, 302)
        lamp = next(item for item in self.read_products() if item["product_id"] == lamp["product_id"])
        self.assertEqual(lamp["quantity"], 3)
        self.assertEqual(lamp["price"], 22.5)

        restocked = self.post_form(
            f"/products/{lamp['product_id']}/restock", {"amount": "4"}
        )
        self.assertEqual(restocked.status_code, 302)
        self.assertEqual(
            next(item for item in self.read_products() if item["product_id"] == lamp["product_id"])[
                "quantity"
            ],
            7,
        )

        deleted = self.post_form(f"/products/{lamp['product_id']}/delete", {})
        self.assertEqual(deleted.status_code, 302)
        self.assertFalse(any(item["product_id"] == lamp["product_id"] for item in self.read_products()))

    def test_checkout_updates_stock_and_rejects_oversell(self):
        sold = self.post_form(
            "/checkout", {"product_id": "PRD-1", "quantity": "2"}
        )
        self.assertEqual(sold.status_code, 302)
        sale = json.loads(self.sales_path.read_text(encoding="utf-8"))[0]
        self.assertEqual(sale["total"], 20.0)
        self.assertTrue(sale["order_id"].startswith("ORD-"))
        self.assertEqual(self.read_products()[0]["quantity"], 3)

        oversell = self.post_form(
            "/checkout", {"product_id": "PRD-1", "quantity": "4"}
        )
        self.assertEqual(oversell.status_code, 400)
        self.assertEqual(self.read_products()[0]["quantity"], 3)
        self.assertEqual(len(json.loads(self.sales_path.read_text(encoding="utf-8"))), 1)

    def test_dashboard_revenue_and_csv_export(self):
        self.post_form("/checkout", {"product_id": "PRD-1", "quantity": "2"})
        dashboard = self.client.get("/")
        self.assertIn(b"$20.00", dashboard.data)

        export = self.client.get("/sales/export.csv")
        self.assertEqual(export.status_code, 200)
        self.assertIn("text/csv", export.content_type)
        self.assertIn(b"Test Mouse", export.data)
        self.assertIn(b"Order ID", export.data)

    def test_corrupt_json_is_reported_without_overwriting_file(self):
        original = b'{"not": valid'
        self.products_path.write_bytes(original)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"could not be read as valid JSON", response.data)
        self.assertEqual(self.products_path.read_bytes(), original)

    def test_invalid_utf8_json_is_reported_without_overwriting_file(self):
        original = b"\xff\xfe"
        self.products_path.write_bytes(original)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 500)
        self.assertIn(b"could not be read as valid JSON", response.data)
        self.assertEqual(self.products_path.read_bytes(), original)

    def test_product_search_and_category_filter(self):
        response = self.client.get("/products?search=mouse&category=Electronics")
        self.assertIn(b"Test Mouse", response.data)
        filtered = self.client.get("/products?search=mouse&category=Stationery")
        self.assertIn(b"No matching products", filtered.data)

    def test_invalid_form_and_missing_csrf_token_do_not_change_data(self):
        invalid_product = self.post_form(
            "/products/new",
            {
                "name": "Bad Price",
                "category": "Test",
                "price": "-1",
                "quantity": "1",
                "low_stock_threshold": "1",
            },
        )
        self.assertEqual(invalid_product.status_code, 400)
        self.assertEqual(len(self.read_products()), 1)

        no_csrf = self.client.post(
            "/products/PRD-1/restock", data={"amount": "4"}
        )
        self.assertEqual(no_csrf.status_code, 400)
        self.assertEqual(self.read_products()[0]["quantity"], 5)


if __name__ == "__main__":
    unittest.main()
