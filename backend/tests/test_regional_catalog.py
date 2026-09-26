import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main


class RegionalCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for key, value in {
            "DATA_PATH": root / "products.json", "ACCESSORIES_PATH": root / "accessories.json",
            "HERO_PATH": root / "hero.json", "UPLOAD_PATH": root / "uploads",
            "ADMIN_TOKEN": "regional-test",
        }.items():
            replacement = patch.object(main, key, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        main.UPLOAD_PATH.mkdir()
        self.client = TestClient(main.app)
        self.headers = {"Authorization": "Bearer regional-test"}
        self.payload = {"name": "Regional item", "category": "Handle", "prices": {"CAD": 4005.25, "USD": 4000.95}}

    def market(self, country):
        return patch.object(main, "resolve_market", return_value={
            "countryCode": country, "currency": "CAD" if country in ("CA", None) else "USD",
            "locationStatus": "located" if country else "unknown",
        })

    def create(self, endpoint, **fields):
        response = self.client.post(f"/api/{endpoint}", json={**self.payload, **fields}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["item"]

    def test_unknown_location_uses_cad_without_relabeling_usd_prices(self) -> None:
        # GEO-007: unresolved location remains unknown but selects the CAD market.
        market = self.client.get("/api/market")
        self.assertEqual(market.json(), {"countryCode": None, "currency": "CAD", "locationStatus": "unknown"})
        self.assertIn("no-store", market.headers["cache-control"])
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint, publicationStatus="published")
            usd_only = self.create(endpoint, name="USD only", prices={"CAD": None, "USD": 99}, publicationStatus="published")
            public = self.client.get(f"/api/{endpoint}").json()["items"]
            selected = next(row for row in public if row["id"] == item["id"])
            self.assertEqual((selected["currency"], selected["price"]), ("CAD", 4005.25))
            self.assertNotIn(usd_only["id"], [row["id"] for row in public])
            selection = self.client.get("/api/catalog/selection").json()["items"]
            self.assertNotIn(usd_only["id"], [row["id"] for row in selection])
            if endpoint == "products":
                self.assertEqual(self.client.get(f"/api/products/{usd_only['slug']}").status_code, 404)

    def test_country_prices_and_no_shared_cache_for_all_public_surfaces(self) -> None:
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint, publicationStatus="published", provenance={"capturedDate": "2026-09-26", "notes": "private"})
            for country, currency, expected in (("CA", "CAD", 4005.25), ("US", "USD", 4000.95), ("FR", "USD", 4000.95), (None, "CAD", 4005.25)):
                with self.subTest(endpoint=endpoint, country=country), self.market(country):
                    response = self.client.get(f"/api/{endpoint}")
                    self.assertIn("no-store", response.headers["cache-control"])
                    self.assertEqual(response.json()["market"]["currency"], currency)
                    public = next(row for row in response.json()["items"] if row["id"] == item["id"])
                    self.assertEqual(public["price"], expected)
                    self.assertEqual(public["currency"], currency)
                    self.assertNotIn("prices", public)
                    self.assertNotIn("provenance", public)
                    for url in ("/api/market", "/api/categories", "/api/catalog/selection"):
                        self.assertIn("no-store", self.client.get(url).headers["cache-control"])
                    if endpoint == "products":
                        detail = self.client.get(f"/api/products/{item['slug']}")
                        self.assertEqual(detail.json()["item"]["price"], expected)
                        self.assertIn("no-store", detail.headers["cache-control"])

    def test_missing_price_hides_item_and_admin_flags_it_without_conversion(self) -> None:
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint, prices={"CAD": None, "USD": 0}, publicationStatus="published")
            self.assertEqual(item["missingPriceMarkets"], ["CAD"])
            with self.market("CA"):
                public = self.client.get(f"/api/{endpoint}").json()["items"]
                self.assertNotIn(item["id"], [row["id"] for row in public])
                selection = self.client.get("/api/catalog/selection").json()["items"]
                self.assertNotIn(item["id"], [row["id"] for row in selection])
                if endpoint == "products":
                    response = self.client.get(f"/api/products/{item['slug']}")
                    self.assertEqual(response.status_code, 404)
                    self.assertIn("no-store", response.headers["cache-control"])
            with self.market("US"):
                public = self.client.get(f"/api/{endpoint}").json()["items"]
                self.assertEqual(next(row for row in public if row["id"] == item["id"])["price"], 0)
            admin = self.client.get(f"/api/admin/{endpoint}", headers=self.headers).json()["items"]
            self.assertEqual(next(row for row in admin if row["id"] == item["id"])["prices"], {"CAD": None, "USD": 0})

    def test_draft_default_publish_unpublish_and_legacy_publication_preservation(self) -> None:
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint)
            self.assertEqual(item["publicationStatus"], "draft")
            with self.market("US"):
                self.assertNotIn(item["id"], [row["id"] for row in self.client.get(f"/api/{endpoint}").json()["items"]])
                url = f"/api/{endpoint}/{item['id']}"
                published = self.client.put(url, headers=self.headers, json={**self.payload, "publicationStatus": "published"})
                self.assertEqual(published.status_code, 200)
                self.assertIn(item["id"], [row["id"] for row in self.client.get(f"/api/{endpoint}").json()["items"]])
                unpublished = self.client.put(url, headers=self.headers, json={**self.payload, "publicationStatus": "draft"})
                self.assertEqual(unpublished.status_code, 200)
                self.assertNotIn(item["id"], [row["id"] for row in self.client.get(f"/api/{endpoint}").json()["items"]])
        legacy = main.load_accessories()[0]
        self.assertNotIn("publicationStatus", legacy)
        updated = self.client.put(f"/api/accessories/{legacy['id']}", headers=self.headers, json={
            "name": legacy["name"], "category": legacy["category"], "prices": {"CAD": 45},
        })
        self.assertEqual(updated.json()["item"]["publicationStatus"], "published")
        self.assertEqual(updated.json()["item"]["prices"]["USD"], legacy["price"])

    def test_market_updates_preserve_other_market_and_reject_invalid_precision(self) -> None:
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint)
            url = f"/api/{endpoint}/{item['id']}"
            for value in (-1, "NaN", "Infinity", 19.999, "1e309"):
                response = self.client.put(url, headers=self.headers, json={**self.payload, "prices": {"CAD": value}})
                self.assertEqual(response.status_code, 422, response.text)
            changed = self.client.put(url, headers=self.headers, json={**self.payload, "prices": {"CAD": 45.5}}).json()["item"]
            self.assertEqual(changed["prices"], {"CAD": 45.5, "USD": 4000.95})
            cleared = self.client.put(url, headers=self.headers, json={**self.payload, "prices": {"CAD": None}}).json()["item"]
            self.assertIsNone(cleared["prices"]["CAD"])
            self.assertEqual(cleared["prices"]["USD"], 4000.95)

    def test_legacy_currency_price_maps_only_to_its_original_market(self) -> None:
        for currency in ("CAD", "USD"):
            item = {"id": 900, "name": "Legacy", "category": "Bench", "price": 19.95, "currency": currency}
            expected = {"CAD": None, "USD": None}
            expected[currency] = 19.95
            admin = main.admin_catalog_item(item)
            self.assertEqual(admin["prices"], expected)
            self.assertEqual(admin["category"], "Benches")
            self.assertEqual(item["category"], "Bench")
        categories = self.client.get("/api/admin/categories", headers=self.headers).json()["items"]
        self.assertIn("Benches", categories)
        self.assertNotIn("Bench", categories)
        for endpoint in ("products", "accessories"):
            self.assertEqual(self.create(endpoint, category=" bEnCh ")["category"], "Benches")

    def test_weight_and_date_roundtrip_preserved_and_private(self) -> None:
        for endpoint in ("products", "accessories"):
            item = self.create(endpoint, weight=" 35.5 kg ", provenance={"capturedDate": "2026-09-26", "notes": "Private"}, publicationStatus="published")
            self.assertEqual(item["weight"], "35.5 kg")
            url = f"/api/{endpoint}/{item['id']}"
            updated = self.client.put(url, headers=self.headers, json={**self.payload, "weight": "35.5 kg"})
            self.assertEqual(updated.json()["item"]["provenance"]["capturedDate"], "2026-09-26")
            disk = json.loads((main.DATA_PATH if endpoint == "products" else main.ACCESSORIES_PATH).read_text())
            self.assertEqual(next(row for row in disk if row["id"] == item["id"])["provenance"]["capturedDate"], "2026-09-26")
            with self.market("CA"):
                public = self.client.get(f"/api/{endpoint}")
                self.assertNotIn("capturedDate", public.text)
                self.assertNotIn("Private", public.text)

    def test_banner_restores_custom_content_and_never_exposes_legacy_price(self) -> None:
        banner = {"tag": "Signature", "number": "01", "eyebrow": "Training", "title": "Your space", "image": "/images/main.jpg"}
        main.HERO_PATH.write_text(json.dumps({**banner, "priceLabel": "CAD $9,999.00"}))
        for country in ("CA", "US", None):
            with self.market(country):
                response = self.client.get("/api/hero")
                self.assertIn("no-store", response.headers["cache-control"])
                self.assertEqual(response.json()["item"], banner)
                self.assertNotIn("9,999", response.text)
        self.assertEqual(self.client.get("/api/admin/hero", headers=self.headers).json()["item"], banner)
        self.assertIn("priceLabel", json.loads(main.HERO_PATH.read_text()))
        updated = {**banner, "title": "Independent banner"}
        self.assertEqual(self.client.put("/api/hero", headers=self.headers, json=updated).status_code, 200)
        self.assertEqual(json.loads(main.HERO_PATH.read_text()), updated)
        self.assertEqual(self.client.put("/api/hero", headers=self.headers, json={"priceLabel": "$123"}).status_code, 422)
        self.assertEqual(self.client.put("/api/hero", headers=self.headers, json={"catalog": "products", "productId": 1}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
