import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

from app import main


class CatalogOrderTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="styl-order-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.products = [
            {"id": 1, "slug": "featured", "name": "Featured", "category": "Racks", "featured": True, "prices": {"CAD": 10, "USD": 8}, "image": "", "photos": [], "provenance": {"notes": "Keep private"}},
            {"id": 2, "slug": "manual-first", "name": "Manual first", "category": "Racks", "featured": False, "prices": {"CAD": 20, "USD": 16}, "image": "", "photos": [], "customField": {"keep": True}},
            {"id": 3, "slug": "us-only", "name": "US only", "category": "Racks", "prices": {"CAD": None, "USD": 7}, "image": "", "photos": []},
            {"id": 4, "slug": "draft", "name": "Draft", "category": "Racks", "prices": {"CAD": 50, "USD": 40}, "publicationStatus": "draft", "image": "", "photos": []},
        ]
        self.accessories = [
            {"id": 1001, "name": "First pair", "category": "Handle", "price": 10, "currency": "CAD", "sellingUnit": "Pair", "packageQuantity": 2},
            {"id": 1002, "name": "Second pair", "category": "Handle", "price": 20, "currency": "CAD", "provenance": {"notes": "Keep accessory source"}},
        ]
        self.paths = {"products": self.root / "products.json", "accessories": self.root / "accessories.json"}
        self.paths["products"].write_text(json.dumps(self.products), encoding="utf-8")
        self.paths["accessories"].write_text(json.dumps(self.accessories), encoding="utf-8")
        hero = self.root / "hero.json"
        hero.write_text(json.dumps({"tag": "", "number": "", "eyebrow": "", "title": "", "image": ""}))
        (self.root / "uploads").mkdir()
        (self.root / "images").mkdir()
        for card in main.DEFAULT_ENGINEERING.items:
            image = self.root / card.image.removeprefix("/")
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"engineering default fixture")
        settings = patch.multiple(
            main, DATA_PATH=self.paths["products"], ACCESSORIES_PATH=self.paths["accessories"],
            HERO_PATH=hero, UPLOAD_PATH=self.root / "uploads", PUBLIC_IMAGE_PATH=self.root / "images",
            ADMIN_TOKEN="order-test-token",
        )
        settings.start()
        self.addCleanup(settings.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer order-test-token"}

    def move(self, catalog: str, ids: list[int], expected: list[int]):
        return self.client.put(f"/api/admin/{catalog}/order", headers=self.headers, json={"ids": ids, "expectedIds": expected})

    def test_sys019_order_is_private_and_strictly_validated(self) -> None:
        body = {"ids": [2, 1, 3, 4], "expectedIds": [1, 2, 3, 4]}
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            self.assertEqual(self.client.put("/api/admin/products/order", headers=headers, json=body).status_code, 401)
        with patch.object(main, "ADMIN_TOKEN", ""):
            self.assertEqual(self.client.put("/api/admin/products/order", headers=self.headers, json=body).status_code, 503)
        for ids in ([2, 2, 3, 4], [1, 2, 3], [1, 2, 3, 5], [True, 2, 3, 4], [1.0, 2, 3, 4]):
            with self.subTest(ids=ids):
                response = self.client.put("/api/admin/products/order", headers=self.headers, json={"ids": ids, "expectedIds": [1, 2, 3, 4]})
                self.assertEqual(response.status_code, 422)
        self.assertEqual(json.loads(self.paths["products"].read_text()), self.products)

    def test_sys019_both_catalogs_preserve_every_record_field(self) -> None:
        for catalog, expected, order, original in (
            ("products", [1, 2, 3, 4], [2, 4, 3, 1], self.products),
            ("accessories", [1001, 1002], [1002, 1001], self.accessories),
        ):
            with self.subTest(catalog=catalog):
                response = self.move(catalog, order, expected)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["ids"], order)
                self.assertIn("no-store", response.headers["cache-control"])
                stored = json.loads(self.paths[catalog].read_text())
                self.assertEqual([item["id"] for item in stored], order)
                self.assertEqual({item["id"]: item for item in stored}, {item["id"]: item for item in original})
                self.assertEqual([item["id"] for item in self.client.get(f"/api/admin/{catalog}", headers=self.headers).json()["items"]], order)

    def test_sys019_public_markets_filter_without_reordering_remaining_items(self) -> None:
        self.assertEqual(self.move("products", [2, 4, 3, 1], [1, 2, 3, 4]).status_code, 200)
        for currency, expected in (("CAD", [2, 1]), ("USD", [2, 3, 1])):
            with patch.object(main, "resolve_market", return_value={"currency": currency, "countryCode": "CA" if currency == "CAD" else "US", "locationStatus": "located"}):
                response = self.client.get("/api/products")
                self.assertEqual([item["id"] for item in response.json()["items"]], expected)

    def test_sys019_stale_order_or_item_set_conflict_does_not_overwrite(self) -> None:
        self.assertEqual(self.move("products", [2, 1, 3, 4], [1, 2, 3, 4]).status_code, 200)
        saved = self.paths["products"].read_bytes()
        self.assertEqual(self.move("products", [4, 3, 2, 1], [1, 2, 3, 4]).status_code, 409)
        self.assertEqual(self.paths["products"].read_bytes(), saved)
        latest = json.loads(saved)
        latest.append({"id": 5, "name": "Another saved item"})
        self.paths["products"].write_text(json.dumps(latest))
        self.assertEqual(self.move("products", [1, 2, 3, 4], [2, 1, 3, 4]).status_code, 409)
        self.assertEqual(len(json.loads(self.paths["products"].read_text())), 5)

    def test_sys019_concurrent_metadata_edit_is_preserved(self) -> None:
        self.products[0]["name"] = "Edited elsewhere"
        self.paths["products"].write_text(json.dumps(self.products))
        self.assertEqual(self.move("products", [2, 1, 3, 4], [1, 2, 3, 4]).status_code, 200)
        self.assertEqual(json.loads(self.paths["products"].read_text())[1]["name"], "Edited elsewhere")

    def test_sys019_corrupt_or_missing_data_never_seeds_a_catalog(self) -> None:
        self.paths["products"].write_text("{broken")
        self.assertEqual(self.move("products", [], []).status_code, 503)
        self.assertEqual(self.paths["products"].read_text(), "{broken")
        self.paths["products"].unlink()
        self.assertEqual(self.move("products", [], []).status_code, 503)
        self.assertFalse(self.paths["products"].exists())

    def test_sys019_write_failure_and_no_op_preserve_data(self) -> None:
        original = self.paths["products"].read_bytes()
        with patch.object(main, "write_json_list", side_effect=OSError("Synthetic disk failure")):
            self.assertEqual(self.move("products", [2, 1, 3, 4], [1, 2, 3, 4]).status_code, 503)
        self.assertEqual(self.paths["products"].read_bytes(), original)
        with patch.object(main, "write_json_list") as write:
            self.assertEqual(self.move("products", [1, 2, 3, 4], [1, 2, 3, 4]).status_code, 200)
            write.assert_not_called()

    def test_sys019_backup_preserves_the_saved_order(self) -> None:
        self.assertEqual(self.move("products", [2, 4, 3, 1], [1, 2, 3, 4]).status_code, 200)
        response = self.client.get("/api/admin/catalog-backup", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text if response.status_code != 200 else "")
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual([item["id"] for item in json.loads(archive.read("data/products.json"))], [2, 4, 3, 1])


if __name__ == "__main__":
    unittest.main()
