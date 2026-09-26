import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main


class CatalogContractTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        paths = {
            "DATA_PATH": root / "products.json",
            "ACCESSORIES_PATH": root / "accessories.json",
            "HERO_PATH": root / "hero.json",
            "UPLOAD_PATH": root / "uploads",
            "ADMIN_TOKEN": "catalog-test-token",
        }
        paths["UPLOAD_PATH"].mkdir()
        for name, value in paths.items():
            replacement = patch.object(main, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.client = TestClient(main.app)
        self.headers = {"Authorization": "Bearer catalog-test-token"}
        self.payload = {"name": "Test item", "category": "Handle", "price": 19.95}

    def create(self, endpoint: str, **fields: object) -> dict:
        response = self.client.post(f"/api/{endpoint}", headers=self.headers, json={**self.payload, **fields})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["item"]

    def test_cent_prices_and_names_validate_on_create_and_update(self) -> None:
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint)
            url = f"/api/{endpoint}/{item['id']}"
            for fields in ({"name": ""}, {"name": " \t "}, {"price": -1}, {"price": 19.951}, {"price": "NaN"}, {"price": "Infinity"}, {"price": "1e309"}, {"price": "9999999999999999.99"}):
                with self.subTest(endpoint=endpoint, fields=fields):
                    body = {**self.payload, **fields}
                    self.assertEqual(self.client.post(f"/api/{endpoint}", json=body, headers=self.headers).status_code, 422)
                    self.assertEqual(self.client.put(url, json=body, headers=self.headers).status_code, 422)
            for price in (0, 19, 19.5, 19.95, "19.950"):
                response = self.client.put(url, json={**self.payload, "price": price}, headers=self.headers)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIsInstance(response.json()["item"]["price"], (int, float))
                self.assertEqual(response.json()["item"]["price"], float(price))
            stored = self.client.get(f"/api/{endpoint}").json()["items"]
            self.assertEqual(next(entry for entry in stored if entry["id"] == item["id"])["price"], 19.95)

    def test_accessory_details_preserve_omitted_fields_and_clear_explicit_values(self) -> None:
        fields = {
            "shortDescription": " Pair of handles ", "description": " Detailed description ",
            "features": [" Comfortable ", "", " Steel "], "included": " Two handles ",
            "sellingUnit": "Pair", "packageQuantity": 2, "colourOptions": " Black ",
        }
        item = self.create("accessories", **fields)
        self.assertEqual(item["shortDescription"], "Pair of handles")
        self.assertEqual(item["features"], ["Comfortable", "Steel"])
        self.assertEqual(item["sellingUnit"], "Pair")
        self.assertEqual(item["packageQuantity"], 2)
        url = f"/api/accessories/{item['id']}"
        updated = self.client.put(url, headers=self.headers, json={**self.payload, "price": 29.99})
        self.assertEqual(updated.status_code, 200, updated.text)
        for field in fields:
            self.assertEqual(updated.json()["item"][field], item[field])
        for invalid in ({"packageQuantity": 0}, {"packageQuantity": 1.5}, {"sellingUnit": "Dozen"}):
            self.assertEqual(self.client.put(url, headers=self.headers, json={**self.payload, **invalid}).status_code, 422)
        blank = {field: "" for field in fields}
        blank.update(features=[], packageQuantity=None)
        cleared = self.client.put(url, headers=self.headers, json={**self.payload, **blank})
        self.assertEqual(cleared.status_code, 200, cleared.text)
        for field, value in blank.items():
            self.assertEqual(cleared.json()["item"][field], value)

    def test_provenance_is_admin_only_and_survives_legacy_updates(self) -> None:
        provenance = {
            "sourceType": "Marketplace", "marketplaceUrl": "https://example.com/listing/123",
            "listingId": "123", "capturedDate": "2026-09-25", "notes": "Private source ambiguity",
        }
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint, provenance=provenance)
            admin_url = f"/api/admin/{endpoint}"
            self.assertEqual(self.client.get(admin_url).status_code, 401)
            self.assertEqual(self.client.get(admin_url, headers={"Authorization": "Bearer incorrect"}).status_code, 401)
            admin_items = self.client.get(admin_url, headers=self.headers).json()["items"]
            self.assertEqual(next(entry for entry in admin_items if entry["id"] == item["id"])["provenance"], provenance)
            public = self.client.get(f"/api/{endpoint}").json()
            self.assertNotIn("provenance", json.dumps(public))
            self.assertNotIn(provenance["notes"], json.dumps(public))
            if endpoint == "products":
                self.assertNotIn("provenance", self.client.get(f"/api/products/{item['slug']}").json()["item"])
            url = f"/api/{endpoint}/{item['id']}"
            updated = self.client.put(url, json=self.payload, headers=self.headers)
            self.assertEqual(updated.json()["item"]["provenance"], provenance)
            for invalid in ({"capturedDate": "2026-02-30"}, {"marketplaceUrl": "javascript:alert(1)"}):
                self.assertEqual(self.client.put(url, json={**self.payload, "provenance": invalid}, headers=self.headers).status_code, 422)
            cleared = self.client.put(url, json={**self.payload, "provenance": {}}, headers=self.headers)
            self.assertEqual(cleared.json()["item"]["provenance"], main.ProvenancePayload().model_dump())

    def test_categories_share_a_canonical_source_and_keep_legacy_values(self) -> None:
        items = main.load_accessories()
        items[0]["category"] = "  Legacy   Attachments "
        main.write_json_list(main.ACCESSORIES_PATH, items)
        self.assertEqual(self.client.get("/api/admin/categories").status_code, 401)
        categories = self.client.get("/api/admin/categories", headers=self.headers).json()["items"]
        self.assertIn("Legacy Attachments", categories)
        self.assertEqual(len({value.casefold() for value in categories}), len(categories))
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint, category="  hAnDlE  ")
            self.assertEqual(item["category"], "Handle")
            legacy = self.create(endpoint, category="legacy attachments")
            self.assertEqual(legacy["category"], "Legacy Attachments")
            response = self.client.post(f"/api/{endpoint}", headers=self.headers, json={**self.payload, "category": "Invented category"})
            self.assertEqual(response.status_code, 422)
            self.assertIn("existing catalog category", response.json()["detail"])

    def test_media_limit_applies_to_both_catalogs_without_partial_saves(self) -> None:
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint, photos=["/images/cover.jpg"])
            response = self.client.put(
                f"/api/{endpoint}/{item['id']}", headers=self.headers,
                json={**self.payload, "photos": [f"/images/{index}.jpg" for index in range(13)]},
            )
            self.assertEqual(response.status_code, 422)
            saved = self.client.get(f"/api/{endpoint}").json()["items"]
            self.assertEqual(next(entry for entry in saved if entry["id"] == item["id"])["photos"], ["/images/cover.jpg"])

    def test_image_size_boundary_and_unsupported_type(self) -> None:
        self.assertEqual(main.MAX_IMAGE_SIZE, 8 * 1024 * 1024)
        accepted = self.client.post(
            "/api/uploads/product-image", headers=self.headers,
            files={"image": ("boundary.jpg", b"x" * main.MAX_IMAGE_SIZE, "image/jpeg")},
        )
        self.assertEqual(accepted.status_code, 200)
        rejected = self.client.post(
            "/api/uploads/product-image", headers=self.headers,
            files={"image": ("oversized.jpg", b"x" * (main.MAX_IMAGE_SIZE + 1), "image/jpeg")},
        )
        self.assertEqual(rejected.status_code, 413)
        unsupported = self.client.post(
            "/api/uploads/product-image", headers=self.headers,
            files={"image": ("file.txt", b"text", "text/plain")},
        )
        self.assertEqual(unsupported.status_code, 415)
        self.assertEqual(len(list(main.UPLOAD_PATH.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
