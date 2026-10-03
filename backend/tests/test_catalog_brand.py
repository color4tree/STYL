import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main
from scripts.migrate_catalog_brands import migrate_catalogs, migrate_items


class CatalogBrandTests(unittest.TestCase):
    # SYS-024: optional brand across both catalog contracts and public surfaces.
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.paths = {kind: self.root / f"{kind}.json" for kind in ("products", "accessories")}
        for path in self.paths.values():
            path.write_text("[]", encoding="utf-8")
        replacement = patch.multiple(
            main, DATA_PATH=self.paths["products"], ACCESSORIES_PATH=self.paths["accessories"],
            HERO_PATH=self.root / "hero.json", UPLOAD_PATH=self.root / "uploads", ADMIN_TOKEN="brand-fixture",
        )
        replacement.start()
        self.addCleanup(replacement.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer brand-fixture"}
        self.payload = {"name": "Rack", "category": "Strength", "prices": {"CAD": 25, "USD": 20}, "publicationStatus": "published"}

    def create(self, kind, **fields):
        response = self.client.post(f"/api/{kind}", headers=self.headers, json={**self.payload, **fields})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["item"]

    def test_create_update_omit_clear_and_reload(self) -> None:
        for kind, path in self.paths.items():
            item = self.create(kind, brand="  STYL  ")
            self.assertEqual(item["brand"], "STYL")
            for fields, expected in (({}, "STYL"), ({"brand": " Acme "}, "Acme"), ({"brand": ""}, None),
                                     ({"brand": "STYL"}, "STYL"), ({"brand": " \t "}, None),
                                     ({"brand": "STYL"}, "STYL"), ({"brand": None}, None),
                                     ({"brand": "B" * 200}, "B" * 200)):
                response = self.client.put(f"/api/{kind}/{item['id']}", headers=self.headers, json={**self.payload, **fields})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["item"]["brand"], expected)
                self.assertEqual(json.loads(path.read_bytes())[0]["brand"], expected)
                admin = self.client.get(f"/api/admin/{kind}", headers=self.headers).json()["items"][0]
                self.assertEqual(admin["brand"], expected)
                self.assertEqual(admin["name"], "Rack")
                if kind == "products":
                    self.assertEqual(admin["slug"], item["slug"])

    def test_invalid_brand_rejected_without_write(self) -> None:
        for kind, path in self.paths.items():
            item = self.create(kind, brand="STYL")
            before = path.read_bytes()
            for brand in ("x" * 201, 123, True, [], {}):
                for method, url in (("post", f"/api/{kind}"), ("put", f"/api/{kind}/{item['id']}")):
                    response = getattr(self.client, method)(url, headers=self.headers, json={**self.payload, "brand": brand})
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual(path.read_bytes(), before)

    def test_legacy_reads_and_omitted_updates_do_not_infer_brand(self) -> None:
        for kind, path in self.paths.items():
            item = self.create(kind, name="STYL legacy rack")
            self.assertNotIn("brand", item)
            before = path.read_bytes()
            self.client.get(f"/api/{kind}")
            self.client.get(f"/api/admin/{kind}", headers=self.headers)
            self.assertEqual(path.read_bytes(), before)
            response = self.client.put(f"/api/{kind}/{item['id']}", headers=self.headers, json={**self.payload, "name": item["name"]})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("brand", response.json()["item"])
            self.assertEqual(response.json()["item"]["name"], "STYL legacy rack")

    def test_public_brand_respects_market_visibility_and_privacy(self) -> None:
        for kind in self.paths:
            item = self.create(kind, brand="STYL", provenance={"notes": "PRIVATE-BRAND-SOURCE"})
            hidden = self.create(kind, name="Hidden", brand="HIDDEN", publicationStatus="draft")
            missing = self.create(kind, name="No price", brand="MISSING", prices={"CAD": None, "USD": None})
            detail = f"/api/{kind}/{item.get('slug', item['id'])}"
            for currency in ("CAD", "USD"):
                with patch.object(main, "resolve_market", return_value={"currency": currency, "countryCode": "CA" if currency == "CAD" else "US", "locationStatus": "located"}):
                    for url in (f"/api/{kind}", detail, "/api/catalog/selection"):
                        response = self.client.get(url)
                        self.assertEqual(response.status_code, 200, response.text)
                        body = response.json()
                        rows = [body["item"]] if "item" in body else body["items"]
                        public = next(row for row in rows if row["id"] == item["id"])
                        if url == "/api/catalog/selection":
                            self.assertNotIn("brand", public)
                            self.assertNotIn("category", public)
                        else:
                            self.assertEqual(public["brand"], "STYL")
                        self.assertEqual(public["price"], self.payload["prices"][currency])
                        self.assertNotIn("provenance", public)
                        self.assertNotIn("prices", public)
                        self.assertNotIn("PRIVATE-BRAND-SOURCE", response.text)
                        self.assertNotIn(hidden["id"], [row["id"] for row in rows])
                        self.assertNotIn(missing["id"], [row["id"] for row in rows])
                        self.assertIn("no-store", response.headers["cache-control"])


class CatalogBrandMigrationTests(unittest.TestCase):
    # DATA-001: explicit, idempotent, backed-up migration, never on reads.
    def test_prefix_only_and_all_unrelated_fields_preserved(self) -> None:
        for name in ("STYL Rack", "STYL - Rack", "styl: Rack", "STYL\u2014Rack"):
            original = {"id": 3, "slug": "styl-rack", "name": name, "prices": {"CAD": 5}, "photos": ["image"], "provenance": {"notes": "fixture"}}
            result, count = migrate_items([original])
            self.assertEqual(count, 1)
            self.assertEqual(result, [{**original, "name": "Rack", "brand": "STYL"}])
            self.assertEqual(original["name"], name)
            self.assertEqual(migrate_items(result), (result, 0))
        for name in ("Rack STYL", "STYLish Rack", "STYL123", "Rack"):
            item = {"name": name, "brand": "Acme"}
            self.assertEqual(migrate_items([item]), ([item], 0))

    def test_empty_titles_conflicts_and_invalid_catalog_fail_explicitly(self) -> None:
        for items in ({}, [None], [{"name": 1}], [{"name": "STYL"}], [{"name": "STYL - "}],
                      [{"name": "STYL Rack", "brand": "Acme"}], [{"name": "STYL Rack", "brand": 1}]):
            with self.assertRaises(ValueError):
                migrate_items(items)

    def test_dry_run_backups_apply_and_second_run_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            originals = {}
            for name in ("products.json", "accessories.json"):
                originals[name] = b'[{"id": 1, "name": "STYL Rack", "slug": "styl-rack", "extra": [1]}]'
                (root / name).write_bytes(originals[name])
            counts = {"products.json": 1, "accessories.json": 1}
            self.assertEqual(migrate_catalogs(root), counts)
            for name, original in originals.items():
                self.assertEqual((root / name).read_bytes(), original)
            self.assertEqual(migrate_catalogs(root, root / "backup"), counts)
            for name, original in originals.items():
                self.assertEqual((root / "backup" / name).read_bytes(), original)
                self.assertEqual(json.loads((root / name).read_bytes()), [{**json.loads(original)[0], "name": "Rack", "brand": "STYL"}])
            saved = {name: (root / name).read_bytes() for name in originals}
            self.assertEqual(migrate_catalogs(root, root / "unused"), {"products.json": 0, "accessories.json": 0})
            self.assertFalse((root / "unused").exists())
            for name in originals:
                self.assertEqual((root / name).read_bytes(), saved[name])

    def test_invalid_second_file_or_backup_failure_leaves_catalog_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            product = root / "products.json"
            product.write_text('[{"name":"STYL Rack"}]', encoding="utf-8")
            accessory = root / "accessories.json"
            accessory.write_text('[{"name":"STYL"}]', encoding="utf-8")
            before = product.read_bytes()
            with self.assertRaises(ValueError):
                migrate_catalogs(root, root / "backup")
            self.assertEqual(product.read_bytes(), before)
            self.assertFalse((root / "backup").exists())
            accessory.write_text("[]", encoding="utf-8")
            with patch("scripts.migrate_catalog_brands.Path.mkdir", side_effect=PermissionError("fixture")):
                with self.assertRaises(PermissionError):
                    migrate_catalogs(root, root / "backup")
            self.assertEqual(product.read_bytes(), before)
