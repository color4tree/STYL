import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main


class CatalogMsrpTests(unittest.TestCase):
    # SYS-004/010/017/019 and USR-003: independent optional MSRP and public detail.
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="msrp-fixture-", dir=Path(__file__).parent)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.paths = {catalog: self.root / f"{catalog}.json" for catalog in ("products", "accessories")}
        for path in self.paths.values():
            path.write_text("[]", encoding="utf-8")
        (self.root / "uploads").mkdir()
        replacement = patch.multiple(
            main, DATA_PATH=self.paths["products"], ACCESSORIES_PATH=self.paths["accessories"],
            HERO_PATH=self.root / "hero.json", UPLOAD_PATH=self.root / "uploads",
            ADMIN_TOKEN="msrp-fixture-token",
        )
        replacement.start()
        self.addCleanup(replacement.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer msrp-fixture-token"}
        self.payload = {
            "name": "Market item", "category": "Handle",
            "prices": {"CAD": 125.25, "USD": 90.50}, "publicationStatus": "published",
        }

    def market(self, country):
        return patch.object(main, "resolve_market", return_value={
            "countryCode": country, "currency": "CAD" if country in ("CA", None) else "USD",
            "locationStatus": "located" if country else "unknown",
        })

    def create(self, catalog, **fields):
        response = self.client.post(f"/api/{catalog}", headers=self.headers, json={**self.payload, **fields})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["item"]

    def update(self, catalog, item, **fields):
        response = self.client.put(
            f"/api/{catalog}/{item['id']}", headers=self.headers,
            json={"name": item["name"], "category": item["category"], **fields},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["item"]

    def detail_url(self, catalog, item):
        return f"/api/{catalog}/{item['slug'] if catalog == 'products' else item['id']}"

    def test_independent_msrps_on_lists_details_selection_and_admin(self) -> None:
        for catalog in self.paths:
            item = self.create(catalog, msrps={"CAD": 180.75, "USD": 110.95}, provenance={"notes": "PRIVATE-MSRP-SOURCE"})
            self.assertEqual(item["msrps"], {"CAD": 180.75, "USD": 110.95})
            for country, currency, amount, price in (
                ("CA", "CAD", 180.75, 125.25), ("US", "USD", 110.95, 90.50),
                ("FR", "USD", 110.95, 90.50), (None, "CAD", 180.75, 125.25),
            ):
                with self.subTest(catalog=catalog, country=country), self.market(country):
                    for url in (f"/api/{catalog}", self.detail_url(catalog, item), "/api/catalog/selection"):
                        response = self.client.get(url)
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertIn("private", response.headers["cache-control"])
                        self.assertIn("no-store", response.headers["cache-control"])
                        body = response.json()
                        public = body["item"] if "item" in body else next(row for row in body["items"] if row["id"] == item["id"])
                        self.assertEqual((public["currency"], public["msrp"], public["price"]), (currency, amount, price))
                        self.assertNotIn("msrps", public)
                        self.assertNotIn("prices", public)
                        self.assertNotIn("provenance", public)
                        self.assertNotIn("PRIVATE-MSRP-SOURCE", response.text)
            admin = self.client.get(f"/api/admin/{catalog}", headers=self.headers).json()["items"][-1]
            self.assertEqual(admin["msrps"], item["msrps"])
            self.assertEqual(admin["prices"], self.payload["prices"])
            for currency, cents in (("CAD", 12525), ("USD", 9050)):
                selected = next(row for row in main.analytics_catalog({"currency": currency}) if row["itemId"] == item["id"])
                self.assertEqual(selected["priceCents"], cents)
                self.assertNotIn("msrps", selected)
                self.assertNotIn("msrp", selected)

    def test_missing_zero_and_below_or_equal_msrp_are_valid_not_visibility_rules(self) -> None:
        for catalog in self.paths:
            for msrps, expected in (
                ({}, {"CAD": None, "USD": None}),
                ({"CAD": 0}, {"CAD": 0, "USD": None}),
                ({"USD": 125.25}, {"CAD": None, "USD": 125.25}),
                ({"CAD": 125.25, "USD": 80}, {"CAD": 125.25, "USD": 80}),
                ({"CAD": None, "USD": None}, {"CAD": None, "USD": None}),
            ):
                with self.subTest(catalog=catalog, msrps=msrps):
                    item = self.create(catalog, msrps=msrps)
                    self.assertEqual(item["msrps"], expected)
                    self.assertEqual(item["missingPriceMarkets"], [])
                    for country, currency in (("CA", "CAD"), ("US", "USD")):
                        with self.market(country):
                            public = self.client.get(self.detail_url(catalog, item)).json()["item"]
                            self.assertEqual(public["msrp"], expected[currency])
                            self.assertEqual(public["price"], self.payload["prices"][currency])

    def test_legacy_and_old_clients_do_not_invent_msrp_or_copy_markets(self) -> None:
        for catalog, identifier in (("products", 1), ("accessories", 1001)):
            legacy = {
                "id": identifier, "slug": "legacy", "name": "Legacy", "category": "Handle",
                "currency": "USD", "price": 42.25,
            }
            original = json.dumps([legacy], indent=4).encode()
            self.paths[catalog].write_bytes(original)
            admin = self.client.get(f"/api/admin/{catalog}", headers=self.headers).json()["items"][0]
            self.assertEqual(admin["msrps"], {"CAD": None, "USD": None})
            with self.market("US"):
                public = self.client.get(self.detail_url(catalog, legacy)).json()["item"]
                self.assertIsNone(public["msrp"])
                self.assertEqual(public["price"], 42.25)
            self.assertEqual(self.paths[catalog].read_bytes(), original)
            changed = self.update(catalog, legacy, prices={"CAD": 55})
            self.assertEqual(changed["msrps"], {"CAD": None, "USD": None})
            self.assertEqual(changed["prices"], {"CAD": 55, "USD": 42.25})
            self.assertNotIn("msrps", json.loads(self.paths[catalog].read_bytes())[0])
            new = self.create(catalog)
            self.assertEqual(new["msrps"], {"CAD": None, "USD": None})

    def test_partial_updates_omission_empty_object_and_clear_are_independent(self) -> None:
        for catalog in self.paths:
            item = self.create(catalog, msrps={"CAD": 200.25, "USD": 150.75})
            for fields, expected in (
                ({"msrps": {"CAD": 0}}, {"CAD": 0, "USD": 150.75}),
                ({"description": "Unrelated edit"}, {"CAD": 0, "USD": 150.75}),
                ({"msrps": {}}, {"CAD": 0, "USD": 150.75}),
                ({"msrps": {"CAD": None}}, {"CAD": None, "USD": 150.75}),
                ({"msrps": {"USD": "199.95"}}, {"CAD": None, "USD": 199.95}),
                ({"msrps": {"CAD": "250.00"}}, {"CAD": 250, "USD": 199.95}),
                ({"msrps": {"USD": None}}, {"CAD": 250, "USD": None}),
            ):
                changed = self.update(catalog, item, **fields)
                self.assertEqual(changed["msrps"], expected)
                self.assertEqual(changed["prices"], self.payload["prices"])
                self.assertEqual(json.loads(self.paths[catalog].read_bytes())[-1]["msrps"], expected)
                with TestClient(main.app) as reloaded:
                    saved = reloaded.get(f"/api/admin/{catalog}", headers=self.headers).json()["items"][-1]
                    self.assertEqual(saved["msrps"], expected)
            changed = self.update(catalog, item, prices={"CAD": 25})
            self.assertEqual(changed["msrps"], {"CAD": 250, "USD": None})
            self.assertEqual(changed["prices"], {"CAD": 25, "USD": 90.50})

    def test_invalid_msrp_values_and_shapes_reject_create_and_update_without_writes(self) -> None:
        invalid = [
            None, [], "", 30, True, {"EUR": 10}, {"cad": 10}, {"CAD": 30, "EUR": None},
            {"CAD": -0.01}, {"USD": "NaN"}, {"CAD": "Infinity"}, {"USD": "-Infinity"},
            {"CAD": 12.345}, {"USD": "19.999"}, {"CAD": "1e309"},
            {"USD": "9007199254740993"}, {"CAD": True}, {"USD": {}}, {"CAD": []}, {"USD": ""},
        ]
        for catalog in self.paths:
            item = self.create(catalog, msrps={"CAD": 180.75, "USD": 110.95})
            original = self.paths[catalog].read_bytes()
            for value in invalid:
                for method, url in (("POST", f"/api/{catalog}"), ("PUT", f"/api/{catalog}/{item['id']}")):
                    with self.subTest(catalog=catalog, method=method, value=value):
                        response = self.client.request(method, url, headers=self.headers, json={**self.payload, "msrps": value})
                        self.assertEqual(response.status_code, 422, response.text)
                        self.assertEqual(self.paths[catalog].read_bytes(), original)
            for value in ("NaN", "Infinity", "-Infinity", "1e309", "-1e309"):
                for method, url in (("POST", f"/api/{catalog}"), ("PUT", f"/api/{catalog}/{item['id']}")):
                    response = self.client.request(
                        method, url, headers={**self.headers, "Content-Type": "application/json"},
                        content=json.dumps(self.payload)[:-1] + ', "msrps": {"CAD": ' + value + '}}',
                    )
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual(self.paths[catalog].read_bytes(), original)

    def test_flat_msrp_never_controls_saved_or_selected_msrp(self) -> None:
        for catalog in self.paths:
            item = self.create(catalog, msrp=99999, msrps={"CAD": 180.75, "USD": 110.95})
            self.assertNotIn("msrp", json.loads(self.paths[catalog].read_bytes())[-1])
            changed = self.update(catalog, item, msrp=1, currency="USD")
            self.assertEqual(changed["msrps"], {"CAD": 180.75, "USD": 110.95})
            stored = json.loads(self.paths[catalog].read_bytes())
            stored[-1]["msrp"] = 88888
            self.paths[catalog].write_text(json.dumps(stored), encoding="utf-8")
            with self.market("CA"):
                public = self.client.get(self.detail_url(catalog, item)).json()["item"]
                self.assertEqual(public["msrp"], 180.75)
            old_client = self.create(catalog, msrp=99999)
            with self.market("US"):
                self.assertIsNone(self.client.get(self.detail_url(catalog, old_client)).json()["item"]["msrp"])

    def test_selling_price_alone_gates_lists_selection_and_both_details(self) -> None:
        for catalog in self.paths:
            unavailable = self.create(catalog, prices={"CAD": None, "USD": None}, msrps={"CAD": 1000, "USD": 2000})
            zero = self.create(catalog, name="Zero price", prices={"CAD": 0, "USD": 0})
            draft = self.create(catalog, name="Draft", msrps={"CAD": 1000, "USD": 2000}, publicationStatus="draft")
            for country in ("CA", "US"):
                with self.market(country):
                    for item in (unavailable, draft):
                        for url in (f"/api/{catalog}", "/api/catalog/selection"):
                            self.assertNotIn(item["id"], [row["id"] for row in self.client.get(url).json()["items"]])
                        response = self.client.get(self.detail_url(catalog, item))
                        self.assertEqual(response.status_code, 404)
                        self.assertIn("private", response.headers["cache-control"])
                        self.assertIn("no-store", response.headers["cache-control"])
                    for url in (f"/api/{catalog}", "/api/catalog/selection"):
                        selected = next(row for row in self.client.get(url).json()["items"] if row["id"] == zero["id"])
                        self.assertEqual(selected["price"], 0)
                        self.assertIsNone(selected["msrp"])
                    detail = self.client.get(self.detail_url(catalog, zero)).json()["item"]
                    self.assertEqual(detail["price"], 0)
                    self.assertIsNone(detail["msrp"])
                    accounting = main.analytics_catalog({"currency": "CAD" if country == "CA" else "USD"})
                    self.assertEqual(next(row for row in accounting if row["itemId"] == zero["id"])["priceCents"], 0)
                    self.assertNotIn(unavailable["id"], [row["itemId"] for row in accounting])
                    self.assertNotIn(draft["id"], [row["itemId"] for row in accounting])

    def test_msrps_do_not_bypass_admin_authentication(self) -> None:
        for catalog in self.paths:
            item = self.create(catalog, msrps={"CAD": 500, "USD": 400})
            original = self.paths[catalog].read_bytes()
            for headers in ({}, {"Authorization": "Bearer wrong-fixture-token"}):
                for method, url in (
                    ("GET", f"/api/admin/{catalog}"), ("POST", f"/api/{catalog}"),
                    ("PUT", f"/api/{catalog}/{item['id']}"),
                ):
                    response = self.client.request(method, url, headers=headers, json={**self.payload, "msrps": {"CAD": 1}})
                    self.assertEqual(response.status_code, 401)
                    self.assertNotIn("msrps", response.text)
            self.assertEqual(self.paths[catalog].read_bytes(), original)

    def test_accessory_detail_preserves_full_public_content_and_hides_provenance(self) -> None:
        fields = {
            "shortDescription": "Summary", "description": "Full description\nSecond line",
            "notes": "Public usage", "features": ["One", "Two"], "included": "Two handles",
            "sellingUnit": "Pair", "packageQuantity": 2, "dimensions": "10 cm", "material": "Steel",
            "weight": "2 kg", "colourOptions": "Black", "image": "/images/handle.svg",
            "photos": ["/images/handle.svg", "/images/handle-detail.svg"],
            "compatibility": {"uprightSize": "75 mm", "holeDiameter": "25 mm", "holeSpacing": "50 mm", "models": "Rack", "limitations": "Confirm fit"},
        }
        item = self.create("accessories", **fields, msrps={"CAD": 140.50, "USD": 105}, provenance={"notes": "PRIVATE-DETAIL"})
        with self.market("CA"):
            response = self.client.get(f"/api/accessories/{item['id']}")
            public = response.json()["item"]
            for key, value in fields.items():
                self.assertEqual(public[key], value)
            self.assertNotIn("PRIVATE-DETAIL", response.text)
            self.assertEqual(public["msrp"], 140.50)
            self.assertEqual(public["price"], 125.25)

    def test_accessory_detail_unknown_missing_market_and_invalid_ids(self) -> None:
        item = self.create("accessories", prices={"CAD": None, "USD": 0}, msrps={"CAD": 100})
        with self.market("CA"):
            for identifier in (item["id"], 999999):
                response = self.client.get(f"/api/accessories/{identifier}")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Accessory not found"})
                self.assertIn("no-store", response.headers["cache-control"])
        with self.market("US"):
            self.assertEqual(self.client.get(f"/api/accessories/{item['id']}").status_code, 200)
        for identifier in ("invalid", "1001.5", "0", "-1", "null"):
            response = self.client.get(f"/api/accessories/{identifier}")
            self.assertEqual(response.status_code, 422)

    def test_accessory_detail_market_cannot_be_selected_by_query_or_spoofed_headers(self) -> None:
        item = self.create("accessories", msrps={"CAD": 180.75, "USD": 110.95})
        response = self.client.get(
            f"/api/accessories/{item['id']}?currency=USD&country=US&msrp=1",
            headers={"X-Country-Code": "US", "CF-IPCountry": "US", "X-Forwarded-For": "8.8.8.8"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["market"], {"countryCode": None, "currency": "CAD", "locationStatus": "unknown"})
        self.assertEqual(response.json()["item"]["msrp"], 180.75)
        self.assertEqual(response.json()["item"]["price"], 125.25)

    def test_reads_noop_order_and_reordering_preserve_saved_msrp_and_legacy_shape(self) -> None:
        for catalog in self.paths:
            self.create(catalog, msrps={"CAD": 0, "USD": None})
            self.create(catalog)
            original = self.paths[catalog].read_bytes()
            records = json.loads(original)
            ids = [item["id"] for item in records]
            self.client.get(f"/api/{catalog}")
            self.client.get(f"/api/admin/{catalog}", headers=self.headers)
            self.client.get("/api/catalog/selection")
            response = self.client.put(
                f"/api/admin/{catalog}/order", headers=self.headers,
                json={"ids": ids, "expectedIds": ids},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(self.paths[catalog].read_bytes(), original)
            response = self.client.put(
                f"/api/admin/{catalog}/order", headers=self.headers,
                json={"ids": ids[::-1], "expectedIds": ids},
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(json.loads(self.paths[catalog].read_bytes()), records[::-1])


if __name__ == "__main__":
    unittest.main()
