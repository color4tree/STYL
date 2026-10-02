"""Catalog fact/revision coverage: SYS-008/009/010/012/017/018/019."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import catalog_backup, catalog_schema, main


class PromotedCatalogValidationTests(unittest.TestCase):
    def test_revision_or_facts_cannot_bypass_strict_fields_by_omitting_schema_version(self):
        for metadata in ({"expectedRevision": "a" * 64}, {"catalogFacts": None}):
            with self.subTest(metadata=metadata):
                with self.assertRaises(ValidationError):
                    main.ProductPayload.model_validate({
                        "name": "Synthetic", "category": "Racks", **metadata, "misspelledFacts": {},
                    })


def reviewed_facts() -> dict:
    return catalog_schema.CatalogFacts.model_validate({
        "schemaVersion": 1,
        "reviewed": True,
        "options": {"colors": ["Black", "Red"], "sizes": ["34 mm", "36 mm"], "finish": "Satin", "note": "Descriptive, not selectable variants."},
        "measurements": [
            {"kind": "weight", "scope": "product", "amount": "28.000000000000000001", "unit": "kg", "qualifier": "approximate", "note": "Merchant-listed product mass, not capacity."},
            {"kind": "width", "scope": "smith_bar", "amount": "2200", "unit": "mm", "qualifier": "nominal"},
        ],
        "materials": [{"component": "frame", "value": "Steel"}],
        "interfaces": [{
            "kind": "socket_drive", "role": "requires",
            "constraints": [{"attribute": "driveSize", "operator": "listed", "value": "1/2", "unit": "in"}],
            "limitations": "Exact fit is unverified.",
        }],
        "components": [
            {"name": "Socket", "quantity": 1, "status": "included"},
            {"name": "Driver", "quantity": None, "status": "excluded"},
            {"name": "Hardware", "quantity": None, "status": "unknown"},
        ],
        "packageNote": "One chosen size, not both sizes.",
    }).model_dump()


class CatalogSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[2] / ".styl-runtime" / "catalog-schema-tests" / uuid4().hex
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.uploads = self.root / "uploads"
        self.images = self.root / "images"
        self.uploads.mkdir()
        self.images.mkdir()
        (self.uploads / "original.png").write_bytes(b"original fixture image")
        (self.uploads / "latest.png").write_bytes(b"latest fixture image")
        (self.images / "fixture.svg").write_text("<svg/>", encoding="utf-8")
        self.paths = {"products": self.root / "products.json", "accessories": self.root / "accessories.json"}
        for path in self.paths.values():
            path.write_text("[]", encoding="utf-8")
        hero = main.DEFAULT_HERO.model_dump()
        hero["image"] = "/images/fixture.svg"
        for card in hero["engineering"]["items"]:
            card["image"] = "/images/fixture.svg"
        hero_path = self.root / "hero.json"
        hero_path.write_text(json.dumps(hero), encoding="utf-8")
        replacements = patch.multiple(
            main, DATA_PATH=self.paths["products"], ACCESSORIES_PATH=self.paths["accessories"],
            HERO_PATH=hero_path, UPLOAD_PATH=self.uploads, PUBLIC_IMAGE_PATH=self.images,
            ADMIN_TOKEN="isolated-schema-token",
        )
        replacements.start()
        self.addCleanup(replacements.stop)
        market = patch.object(main, "resolve_market", return_value={
            "countryCode": "US", "currency": "USD", "locationStatus": "located",
        })
        market.start()
        self.addCleanup(market.stop)
        support_path = patch.object(main.support, "configured_path", return_value=self.root / "absent-support.sqlite3")
        support_path.start()
        self.addCleanup(support_path.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer isolated-schema-token"}
        self.payload = {
            "name": "Fixture item", "category": "Handle", "price": 19.95, "currency": "USD",
            "publicationStatus": "published", "photos": ["/api/uploads/original.png"],
        }

    def create(self, endpoint: str, **fields: object) -> dict:
        response = self.client.post(f"/api/{endpoint}", json={**self.payload, **fields}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["item"]

    def update(self, endpoint: str, item: dict, **fields: object):
        return self.client.put(
            f"/api/{endpoint}/{item['id']}",
            json={"name": item["name"], "category": item["category"], "expectedRevision": item["revision"], **fields},
            headers=self.headers,
        )

    def raw(self, endpoint: str, identifier: int) -> dict:
        return next(item for item in json.loads(self.paths[endpoint].read_text(encoding="utf-8")) if item["id"] == identifier)

    def legacy(self, endpoint: str) -> dict:
        item = {
            "id": 17 if endpoint == "products" else 1017, "slug": "legacy-fixture",
            "name": "Legacy", "category": "Handle", "price": 19.95, "currency": "USD",
            "image": "/api/uploads/original.png", "photos": ["/api/uploads/original.png"],
            "dimensions": "  Original × dimensions\n", "weight": "  Approx. 28 kg ",
            "material": "  Steel ", "colourOptions": " black / red ",
            "shortDescription": " Original short ", "description": " Original long\n",
            "features": ["  Original feature "], "notes": " Original public use ",
            "compatibility": {**main.CompatibilityPayload().model_dump(), "uprightSize": "  3 in / 75 mm  "},
            "provenance": {"notes": "PRIVATE-SOURCE-MARKER", "listingId": "private-listing"},
            "internalAudit": {"marker": "PRIVATE-RAW-MARKER"},
        }
        self.paths[endpoint].write_text(json.dumps([item], indent=3, ensure_ascii=False), encoding="utf-8")
        return main.admin_catalog_item(item)

    def test_legacy_get_is_read_only_and_revision_is_raw_not_transient(self) -> None:
        for endpoint in self.paths:
            item = self.legacy(endpoint)
            before = self.paths[endpoint].read_bytes()
            admin = self.client.get(f"/api/admin/{endpoint}", headers=self.headers).json()["items"][0]
            self.assertEqual(admin["schemaVersion"], 1)
            self.assertEqual(admin["revision"], catalog_schema.catalog_revision(self.raw(endpoint, item["id"])))
            self.assertRegex(admin["revision"], r"^[0-9a-f]{64}$")
            self.client.get(f"/api/{endpoint}")
            self.client.get("/api/catalog/selection")
            self.assertEqual(before, self.paths[endpoint].read_bytes())
            self.assertNotIn("schemaVersion", self.raw(endpoint, item["id"]))
            self.assertNotEqual(admin["revision"], catalog_schema.catalog_revision(admin))

    def test_revision_ignores_record_key_order_but_detects_private_changes(self) -> None:
        raw = {"id": 1, "prices": {"CAD": 1, "USD": 2}, "provenance": {"notes": "a"}}
        reordered = {"provenance": {"notes": "a"}, "prices": {"USD": 2, "CAD": 1}, "id": 1}
        self.assertEqual(catalog_schema.catalog_revision(raw), catalog_schema.catalog_revision(reordered))
        reordered["provenance"]["notes"] = "b"
        self.assertNotEqual(catalog_schema.catalog_revision(raw), catalog_schema.catalog_revision(reordered))

    def test_schema2_create_defaults_and_revision_are_not_persisted_as_hash(self) -> None:
        for endpoint in self.paths:
            item = self.create(endpoint, schemaVersion=2)
            self.assertEqual(item["schemaVersion"], 2)
            self.assertIsNone(item["catalogFacts"])
            raw = self.raw(endpoint, item["id"])
            self.assertEqual(item["revision"], catalog_schema.catalog_revision(raw))
            self.assertNotIn("revision", raw)
            self.assertNotIn("expectedRevision", raw)
            self.assertNotIn("catalogFactsReviewedAt", raw)

    def test_reviewed_roundtrip_is_exact_and_not_commercial_variant_behavior(self) -> None:
        for endpoint in self.paths:
            selling = {"sellingUnit": "Each", "packageQuantity": 1} if endpoint == "accessories" else {}
            item = self.create(endpoint, catalogFacts=reviewed_facts(), **selling)
            self.assertEqual(item["schemaVersion"], 2)
            self.assertEqual(item["catalogFacts"], reviewed_facts())
            self.assertIsNotNone(datetime.fromisoformat(item["catalogFactsReviewedAt"]).tzinfo)
            public = self.client.get(f"/api/{endpoint}").json()["items"][0]
            self.assertEqual(public["catalogFacts"], reviewed_facts())
            self.assertEqual(public["price"], 19.95)
            self.assertNotIn("variants", public)
            self.assertNotIn("catalogFactsReviewedAt", public)
            self.assertNotIn("revision", public)
            detail = f"/api/products/{item['slug']}" if endpoint == "products" else f"/api/accessories/{item['id']}"
            self.assertEqual(self.client.get(detail).json()["item"]["catalogFacts"], reviewed_facts())
        selection = self.client.get("/api/catalog/selection").json()["items"]
        self.assertEqual(len(selection), 2)
        self.assertTrue(all("catalogFacts" not in item and item["price"] == 19.95 for item in selection))

    def test_unreviewed_facts_and_all_private_markers_are_absent_publicly(self) -> None:
        facts = {**reviewed_facts(), "reviewed": False, "packageNote": "UNREVIEWED-MARKER"}
        for endpoint in self.paths:
            item = self.create(endpoint, catalogFacts=facts, provenance={"notes": "PRIVATE-SOURCE-MARKER"})
            self.assertEqual(item["catalogFacts"], facts)
            self.assertIsNone(item["catalogFactsReviewedAt"])
            public = self.client.get(f"/api/{endpoint}").text
            self.assertNotIn("UNREVIEWED-MARKER", public)
            self.assertNotIn("PRIVATE-SOURCE-MARKER", public)
            self.assertNotIn("catalogFacts", public)

    def test_public_projection_fails_closed_for_unknown_restored_metadata(self) -> None:
        item = self.legacy("products")
        raw = self.raw("products", item["id"])
        raw["catalogFacts"] = {**reviewed_facts(), "privateProvenance": "PRIVATE-EXTENSION-MARKER"}
        raw["compatibility"]["sourceUrl"] = "PRIVATE-COMPATIBILITY-MARKER"
        self.paths["products"].write_text(json.dumps([raw]), encoding="utf-8")
        before = self.paths["products"].read_bytes()
        public = self.client.get("/api/products").text
        self.assertNotIn("PRIVATE", public)
        self.assertNotIn("catalogFacts", public)
        self.assertIsNone(catalog_schema.public_catalog_facts(raw))
        self.assertEqual(before, self.paths["products"].read_bytes())

    def test_legacy_fact_paths_remain_public_with_nested_private_keys_excluded(self) -> None:
        legacy_facts = {
            "brand": "Example Brand", "aliases": ["Example bench", "Synthetic alias"],
            "materialParts": {"frame": "Steel", "handle": "Rubber"},
            "colourParts": {"frame": "Black"}, "colorParts": {"handles": "Red"},
            "finish": " Powder coated ", "colorOptions": ["Black", "Red"],
            "capacity": {"safeLoad": "250 kg"}, "safeLoad": "250 kg", "ownWeight": "28 kg",
            "resistance": {"stacks": ["90 kg", "90 kg"], "increments": "2.5 kg"},
            "weightStacks": ["90 kg", "90 kg"], "weightIncrements": "2.5 kg",
            "dimensions": {"length": "120 cm", "width": "60 cm", "height": "45 cm", "depth": "15 cm"},
            "length": "120 cm", "width": "60 cm", "height": "45 cm", "depth": "15 cm",
            "includes": ["One bench", "One pin"], "components": ["Frame", "Handle"],
            "saleUnit": "Each", "sku": "SYNTHETIC-READ-ONLY",
            "compatibility": {
                "uprightSize": "75 mm", "holeDiameter": "25 mm", "holeSpacing": "50 mm",
                "pinDiameter": "25 mm", "pinLength": "100 mm", "pinDimensions": "25 × 100 mm",
                "models": "Example rack", "limitations": "Exact fit unverified", "requiredDepth": "75 mm",
            },
            "compat": {"pinDiameter": "25 mm", "requiredDepth": "75 mm"},
        }
        for endpoint in self.paths:
            item = self.legacy(endpoint)
            raw = {**self.raw(endpoint, item["id"]), **deepcopy(legacy_facts)}
            raw["catalogFacts"] = {"reviewed": False, "packageNote": "PRIVATE-TYPED-DRAFT"}
            for field in ("capacity", "resistance", "dimensions", "compatibility", "compat", "materialParts", "colourParts", "colorParts"):
                raw[field]["privateNotes"] = {"sourceUrl": "PRIVATE-NESTED-SOURCE"}
            self.paths[endpoint].write_text(json.dumps([raw]), encoding="utf-8")
            before = self.paths[endpoint].read_bytes()
            public = self.client.get(f"/api/{endpoint}").json()["items"][0]
            for key, value in legacy_facts.items():
                self.assertEqual(public[key], value, key)
            self.assertEqual(public["materialParts"]["handle"], "Rubber")
            self.assertNotIn("PRIVATE", json.dumps(public))
            self.assertNotIn("catalogFacts", public)
            self.assertNotIn("provenance", public)
            detail = f"/api/products/{item['slug']}" if endpoint == "products" else f"/api/accessories/{item['id']}"
            self.assertEqual(self.client.get(detail).json()["item"]["materialParts"]["handle"], "Rubber")
            selection = self.client.get("/api/catalog/selection").json()
            self.assertNotIn("PRIVATE", json.dumps(selection))
            self.assertEqual(before, self.paths[endpoint].read_bytes())

    def test_legacy_fact_leaf_guards_reject_arbitrary_objects_and_invalid_values(self) -> None:
        raw = {
            "materialParts": {"handle": "Rubber", "frame": {"sourceUrl": "PRIVATE"}, "unknownPart": "PRIVATE"},
            "capacity": {"safeLoad": {"value": "250 kg", "privateNotes": "PRIVATE"}},
            "resistance": {"stacks": ["90 kg", {"privateNotes": "PRIVATE"}], "increments": "2.5 kg"},
            "dimensions": {"length": float("nan"), "width": True, "height": "45 cm", "depth": float("inf")},
            "compatibility": {"pinDiameter": "25 mm", "sourceUrl": "PRIVATE"},
            "brand": {"privateNotes": "PRIVATE"}, "aliases": ["Alias", {"privateNotes": "PRIVATE"}],
            "components": ["Pin", {"sourceUrl": "PRIVATE"}], "finish": "x" * 16001,
            "ownWeight": "28 kg\u202e", "safeLoad": 10**100, "weightStacks": ["1 kg"] * 65,
            "privateSource": "PRIVATE", "catalogFacts": {"reviewed": False, "packageNote": "PRIVATE"},
        }
        result = catalog_schema.public_legacy_catalog_fields(raw)
        self.assertEqual(result, {
            "materialParts": {"handle": "Rubber"}, "resistance": {"increments": "2.5 kg"},
            "dimensions": {"height": "45 cm"}, "compatibility": {"pinDiameter": "25 mm"},
        })
        self.assertNotIn("PRIVATE", json.dumps(result))
        self.assertEqual(raw["materialParts"]["frame"], {"sourceUrl": "PRIVATE"})

    def test_unknown_keys_rejected_at_every_extension_level(self) -> None:
        invalid = [
            {"privateProvenance": "secret"}, {"options": {"stock": 9}},
            {"measurements": [{**reviewed_facts()["measurements"][0], "sourceUrl": "private"}]},
            {"materials": [{"component": "frame", "value": "steel", "cost": 2}]},
            {"interfaces": [{**reviewed_facts()["interfaces"][0], "verifiedPairs": []}]},
            {"interfaces": [{"kind": "rack_mount", "role": "requires", "constraints": [{"attribute": "holeDiameter", "operator": "eq", "value": "1", "evidence": "private"}]}]},
            {"components": [{"name": "Pin", "status": "included", "price": 5}]},
            {"prices": {"USD": 1}}, {"variants": []}, {"stockStatus": "In stock"},
        ]
        for endpoint in self.paths:
            item = self.create(endpoint, schemaVersion=2)
            for facts in invalid:
                with self.subTest(endpoint=endpoint, facts=facts):
                    before = self.paths[endpoint].read_bytes()
                    self.assertEqual(self.update(endpoint, item, catalogFacts=facts).status_code, 422)
                    self.assertEqual(before, self.paths[endpoint].read_bytes())

    def test_wrong_shapes_and_nested_null_are_not_silently_ignored(self) -> None:
        invalid = [[], "", 1, False]
        invalid += [{field: None} for field in ("options", "measurements", "materials", "interfaces", "components")]
        invalid += [{"options": {"colors": None}}, {"options": {"sizes": "34,36"}}, {"reviewed": "true"}, {"reviewed": 1}, {"schemaVersion": True}, {"schemaVersion": "1"}, {"schemaVersion": 2}]
        invalid += [{"measurements": {}}, {"interfaces": [{"kind": "rack_mount", "role": "requires", "constraints": None}]}]
        for value in invalid:
            with self.subTest(value=value):
                response = self.client.post("/api/products", json={**self.payload, "catalogFacts": value}, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.paths["products"].read_text(encoding="utf-8"), "[]")

    def test_measurement_decimal_strings_reject_nonfinite_coercion_and_wrong_units(self) -> None:
        invalid_amounts = ["0", "-1", "NaN", "Infinity", "1e3", "1e309", " 1", "1 ", ".5", "1.", "9" * 65, 1, 1.5, True, None]
        measurement = {"kind": "weight", "scope": "product", "amount": "0.000000000000000000000000000001", "unit": "kg"}
        for amount in invalid_amounts:
            with self.subTest(amount=amount):
                with self.assertRaises(ValidationError):
                    catalog_schema.CatalogMeasurement.model_validate({**measurement, "amount": amount})
        self.assertEqual(catalog_schema.CatalogMeasurement.model_validate(measurement).amount, measurement["amount"])
        for kind in ("weight", "load_capacity", "resistance", "increment"):
            for unit in ("mm", "cm", "m", "in", "ft"):
                with self.subTest(kind=kind, unit=unit), self.assertRaises(ValidationError):
                    catalog_schema.CatalogMeasurement.model_validate({**measurement, "kind": kind, "unit": unit})
        for kind in ("length", "width", "height", "depth", "diameter"):
            for unit in ("kg", "lb"):
                with self.subTest(kind=kind, unit=unit), self.assertRaises(ValidationError):
                    catalog_schema.CatalogMeasurement.model_validate({**measurement, "kind": kind, "unit": unit})
        response = self.client.post("/api/products", json={**self.payload, "catalogFacts": {"measurements": [{**measurement, "unit": "mm"}]}}, headers=self.headers)
        self.assertEqual(response.status_code, 422)

    def test_array_bounds_and_text_bounds_accept_exact_limit_reject_overflow(self) -> None:
        facts = reviewed_facts()
        for field, maximum in (("measurements", 64), ("materials", 32), ("interfaces", 16), ("components", 64)):
            with self.subTest(field=field):
                values = [deepcopy(facts[field][0]) for _ in range(maximum)]
                catalog_schema.CatalogFacts.model_validate({field: values})
                with self.assertRaises(ValidationError):
                    catalog_schema.CatalogFacts.model_validate({field: values + [values[0]]})
        for field in ("colors", "sizes"):
            catalog_schema.CatalogFacts.model_validate({"options": {field: [str(index).zfill(100) for index in range(24)]}})
            for values in ([str(index) for index in range(25)], ["a" * 101]):
                with self.assertRaises(ValidationError):
                    catalog_schema.CatalogFacts.model_validate({"options": {field: values}})
        interface = facts["interfaces"][0]
        constraints = interface["constraints"] * 24
        catalog_schema.CatalogInterface.model_validate({**interface, "constraints": constraints})
        with self.assertRaises(ValidationError):
            catalog_schema.CatalogInterface.model_validate({**interface, "constraints": constraints + constraints[:1]})
        for model, raw, field, maximum in (
            (catalog_schema.CatalogFacts, {}, "packageNote", 4000),
            (catalog_schema.CatalogOptions, {}, "finish", 300),
            (catalog_schema.CatalogOptions, {}, "note", 2000),
            (catalog_schema.CatalogMeasurement, facts["measurements"][0], "note", 2000),
            (catalog_schema.CatalogMaterial, facts["materials"][0], "component", 300),
            (catalog_schema.CatalogMaterial, facts["materials"][0], "value", 300),
            (catalog_schema.CatalogConstraint, interface["constraints"][0], "value", 300),
            (catalog_schema.CatalogInterface, interface, "limitations", 2000),
            (catalog_schema.CatalogComponent, facts["components"][0], "name", 300),
        ):
            with self.subTest(model=model.__name__, field=field):
                model.model_validate({**raw, field: "x" * maximum})
                with self.assertRaises(ValidationError):
                    model.model_validate({**raw, field: "x" * (maximum + 1)})

    def test_component_quantity_and_domain_enums_are_strict(self) -> None:
        component = {"name": "Pin", "status": "unknown"}
        for quantity in (None, 1, 1_000_000):
            self.assertEqual(catalog_schema.CatalogComponent.model_validate({**component, "quantity": quantity}).quantity, quantity)
        for quantity in (0, -1, 1.5, True, "2", 1_000_001):
            with self.assertRaises(ValidationError):
                catalog_schema.CatalogComponent.model_validate({**component, "quantity": quantity})
        facts = reviewed_facts()
        for model, raw, field, invalid in (
            (catalog_schema.CatalogMeasurement, facts["measurements"][0], "scope", "unspecified"),
            (catalog_schema.CatalogMeasurement, facts["measurements"][0], "qualifier", "tested"),
            (catalog_schema.CatalogMeasurement, facts["measurements"][0], "kind", "price"),
            (catalog_schema.CatalogInterface, facts["interfaces"][0], "kind", "universal"),
            (catalog_schema.CatalogInterface, facts["interfaces"][0], "role", "verified"),
            (catalog_schema.CatalogConstraint, facts["interfaces"][0]["constraints"][0], "attribute", "privateSource"),
            (catalog_schema.CatalogConstraint, facts["interfaces"][0]["constraints"][0], "operator", "fits"),
            (catalog_schema.CatalogConstraint, facts["interfaces"][0]["constraints"][0], "unit", "kg"),
            (catalog_schema.CatalogComponent, component, "status", "in stock"),
        ):
            with self.subTest(field=field, invalid=invalid), self.assertRaises(ValidationError):
                model.model_validate({**raw, field: invalid})

    def test_omission_preserves_whole_metadata_null_clears_and_empty_lists_replace(self) -> None:
        for endpoint in self.paths:
            item = self.create(endpoint, catalogFacts=reviewed_facts())
            updated = self.update(endpoint, item, name="Renamed").json()["item"]
            self.assertEqual(updated["catalogFacts"], item["catalogFacts"])
            self.assertEqual(updated["catalogFactsReviewedAt"], item["catalogFactsReviewedAt"])
            empty = self.update(endpoint, updated, catalogFacts={"reviewed": False, "measurements": []}).json()["item"]
            self.assertEqual(empty["catalogFacts"], catalog_schema.CatalogFacts().model_dump())
            self.assertIsNone(empty["catalogFactsReviewedAt"])
            cleared = self.update(endpoint, empty, catalogFacts=None).json()["item"]
            self.assertIsNone(cleared["catalogFacts"])
            self.assertIsNone(cleared["catalogFactsReviewedAt"])
            preserved = self.update(endpoint, cleared, name="Rename again").json()["item"]
            self.assertIsNone(preserved["catalogFacts"])
            self.assertNotIn("catalogFacts", self.client.get(f"/api/{endpoint}").json()["items"][0])

    def test_review_timestamp_changes_only_for_explicit_new_approval(self) -> None:
        first_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        second_time = datetime(2026, 2, 1, tzinfo=timezone.utc)
        with patch.object(catalog_schema, "datetime") as clock:
            clock.now.return_value = first_time
            item = self.create("products", catalogFacts=reviewed_facts())
            self.assertEqual(item["catalogFactsReviewedAt"], first_time.isoformat())
            clock.now.return_value = second_time
            unchanged = self.update("products", item, catalogFacts=reviewed_facts()).json()["item"]
            self.assertEqual(unchanged["catalogFactsReviewedAt"], first_time.isoformat())
            changed = self.update("products", unchanged, catalogFacts={**reviewed_facts(), "packageNote": "New reviewed note"}).json()["item"]
            self.assertEqual(changed["catalogFactsReviewedAt"], second_time.isoformat())
            draft = self.update("products", changed, catalogFacts={"packageNote": "Unapproved draft"}).json()["item"]
            self.assertFalse(draft["catalogFacts"]["reviewed"])
            self.assertIsNone(draft["catalogFactsReviewedAt"])

    def test_client_review_timestamps_rejected_without_writes_or_private_promotion(self) -> None:
        for endpoint in self.paths:
            item = self.create(endpoint, provenance={"notes": json.dumps(reviewed_facts())})
            self.assertNotIn("catalogFacts", item)
            self.assertNotIn("catalogFacts", self.client.get(f"/api/{endpoint}").json()["items"][0])
            before = self.paths[endpoint].read_bytes()
            self.assertEqual(self.update(endpoint, item, catalogFactsReviewedAt="2000-01-01T00:00:00Z", catalogFacts=reviewed_facts()).status_code, 422)
            self.assertEqual(before, self.paths[endpoint].read_bytes())
            self.assertEqual(self.client.post(f"/api/{endpoint}", json={**self.payload, "catalogFactsReviewedAt": None}, headers=self.headers).status_code, 422)

    def test_metadata_edits_require_revision_even_for_legacy_records(self) -> None:
        for endpoint in self.paths:
            item = self.legacy(endpoint)
            before = self.paths[endpoint].read_bytes()
            for fields in ({"catalogFacts": None}, {"catalogFacts": {}}, {"catalogFacts": reviewed_facts()}, {"schemaVersion": 2}):
                response = self.client.put(f"/api/{endpoint}/{item['id']}", json={"name": item["name"], "category": item["category"], **fields}, headers=self.headers)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(before, self.paths[endpoint].read_bytes())
            response = self.update(endpoint, item, catalogFacts=reviewed_facts())
            self.assertEqual(response.status_code, 200, response.text)

    def test_legacy_tokenless_save_works_until_a_tokened_save_promotes_record(self) -> None:
        for endpoint in self.paths:
            item = self.legacy(endpoint)
            legacy_body = {"name": item["name"], "category": item["category"]}
            response = self.client.put(f"/api/{endpoint}/{item['id']}", json=legacy_body, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["item"]["schemaVersion"], 1)
            promoted = self.update(endpoint, response.json()["item"]).json()["item"]
            self.assertEqual(promoted["schemaVersion"], 2)
            before = self.paths[endpoint].read_bytes()
            for body in (legacy_body, {**legacy_body, "schemaVersion": 1}):
                self.assertEqual(self.client.put(f"/api/{endpoint}/{item['id']}", json=body, headers=self.headers).status_code, 409)
            self.assertEqual(before, self.paths[endpoint].read_bytes())
            self.assertEqual(self.update(endpoint, promoted, schemaVersion=1).json()["item"]["schemaVersion"], 2)

    def test_typed_edit_preserves_legacy_raw_fields_and_unknown_private_fields(self) -> None:
        fields = ("dimensions", "weight", "material", "colourOptions", "shortDescription", "description", "features", "compatibility", "notes", "provenance", "internalAudit", "price", "currency")
        for endpoint in self.paths:
            item = self.legacy(endpoint)
            before = self.raw(endpoint, item["id"])
            response = self.update(endpoint, item, catalogFacts=reviewed_facts())
            self.assertEqual(response.status_code, 200, response.text)
            after = self.raw(endpoint, item["id"])
            for field in fields:
                self.assertEqual(after[field], before[field], field)
            same_legacy = {field: after[field] for field in ("dimensions", "weight", "material", "colourOptions", "compatibility")}
            unchanged = self.update(endpoint, response.json()["item"], **same_legacy)
            self.assertEqual(unchanged.status_code, 200, unchanged.text)
            for field in same_legacy:
                self.assertEqual(self.raw(endpoint, item["id"])[field], before[field], field)
            self.assertNotIn("PRIVATE", self.client.get(f"/api/{endpoint}").text)

    def test_stale_writes_preserve_latest_prices_media_provenance_and_bytes(self) -> None:
        for endpoint in self.paths:
            original = self.create(endpoint, schemaVersion=2)
            winner = self.update(
                endpoint, original, prices={"USD": "29.95", "CAD": "39.95"},
                photos=["/api/uploads/latest.png"], provenance={"notes": "LATEST-PRIVATE"},
                catalogFacts=reviewed_facts(),
            )
            self.assertEqual(winner.status_code, 200, winner.text)
            before = self.paths[endpoint].read_bytes()
            with patch.object(main, "delete_catalog_images") as delete_media:
                loser = self.update(endpoint, original, price=1, photos=[], provenance={"notes": "STALE"}, catalogFacts=None)
                self.assertEqual(loser.status_code, 409, loser.text)
                delete_media.assert_not_called()
            self.assertEqual(before, self.paths[endpoint].read_bytes())
            raw = self.raw(endpoint, original["id"])
            self.assertEqual(raw["prices"], {"CAD": 39.95, "USD": 29.95})
            self.assertEqual(raw["provenance"]["notes"], "LATEST-PRIVATE")
            self.assertEqual(raw["photos"], ["/api/uploads/latest.png"])
            self.assertTrue((self.uploads / "latest.png").exists())

    def test_parallel_writers_with_same_revision_have_exactly_one_winner(self) -> None:
        for endpoint in self.paths:
            item = self.create(endpoint, schemaVersion=2)
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(self.update, endpoint, item, prices={"USD": price}) for price in ("21.01", "22.02")]
                responses = [future.result(timeout=10) for future in futures]
            self.assertEqual(sorted(response.status_code for response in responses), [200, 409])
            winner = next(response.json()["item"] for response in responses if response.status_code == 200)
            self.assertEqual(self.raw(endpoint, item["id"])["prices"], winner["prices"])
            self.assertEqual(catalog_schema.catalog_revision(self.raw(endpoint, item["id"])), winner["revision"])

    def test_invalid_and_mismatched_revision_tokens_do_not_write(self) -> None:
        item = self.create("products", schemaVersion=2)
        before = self.paths["products"].read_bytes()
        for token in ("a" * 63, "a" * 65, "g" * 64, "A" * 64, 123):
            with self.subTest(token=token):
                self.assertEqual(self.update("products", item, expectedRevision=token).status_code, 422)
        self.assertEqual(self.update("products", item, expectedRevision="0" * 64).status_code, 409)
        self.assertEqual(self.update("products", item, expectedRevision=None).status_code, 409)
        self.assertEqual(before, self.paths["products"].read_bytes())

    def test_record_schema_versions_are_validated(self) -> None:
        for version in (0, 3, True, "2", None):
            response = self.client.post("/api/products", json={**self.payload, "schemaVersion": version}, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)

    def test_stale_delete_rejects_before_knowledge_guard_or_media_deletion(self) -> None:
        for endpoint in self.paths:
            item = self.create(endpoint, schemaVersion=2)
            url = f"/api/{endpoint}/{item['id']}"
            before = self.paths[endpoint].read_bytes()
            with patch.object(main.knowledge, "catalog_delete_guard") as guard, patch.object(main, "delete_catalog_images") as media:
                for params in ({}, {"expectedRevision": "0" * 64}):
                    self.assertEqual(self.client.delete(url, headers=self.headers, params=params).status_code, 409)
                guard.assert_not_called()
                media.assert_not_called()
            self.assertEqual(before, self.paths[endpoint].read_bytes())
            with patch.object(main.knowledge, "catalog_delete_guard", wraps=main.knowledge.catalog_delete_guard) as guard:
                deleted = self.client.delete(url, headers=self.headers, params={"expectedRevision": item["revision"]})
                self.assertEqual(deleted.status_code, 200, deleted.text)
                guard.assert_called_once_with(f"{'product' if endpoint == 'products' else 'accessory'}:{item['id']}")

    def test_legacy_delete_accepts_no_token_but_rejects_supplied_stale_token(self) -> None:
        for endpoint in self.paths:
            item = self.legacy(endpoint)
            url = f"/api/{endpoint}/{item['id']}"
            self.assertEqual(self.client.delete(url, headers=self.headers, params={"expectedRevision": "0" * 64}).status_code, 409)
            self.assertEqual(self.client.delete(url, headers=self.headers, params={"expectedRevision": "malformed"}).status_code, 422)
            self.assertEqual(self.client.delete(url, headers=self.headers).status_code, 200)

    def test_knowledge_invalidation_failure_blocks_valid_delete(self) -> None:
        item = self.create("products", schemaVersion=2)
        before = self.paths["products"].read_bytes()
        with patch.object(main.knowledge, "catalog_delete_guard", side_effect=main.HTTPException(503, "Blocked knowledge storage")):
            response = self.client.delete(f"/api/products/{item['id']}", headers=self.headers, params={"expectedRevision": item["revision"]})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(before, self.paths["products"].read_bytes())
        self.assertTrue((self.uploads / "original.png").exists())

    def test_archive_restore_preserves_raw_typed_metadata_revision_and_private_values(self) -> None:
        for endpoint in self.paths:
            self.create(endpoint, catalogFacts=reviewed_facts(), provenance={"notes": "PRIVATE-BACKUP"})
        output = io.BytesIO()
        before = {name: path.read_bytes() for name, path in self.paths.items()}
        catalog_backup.create_archive(
            output, products_path=main.DATA_PATH, accessories_path=main.ACCESSORIES_PATH,
            hero_path=main.HERO_PATH, uploads_path=self.uploads, images_path=self.images,
            default_hero=main.DEFAULT_HERO.model_dump(), app_version=main.app.version,
        )
        archive = self.root / "facts.zip"
        archive.write_bytes(output.getvalue())
        restored = self.root / "restored"
        catalog_backup.restore_archive(archive, restored)
        for name, source in before.items():
            self.assertEqual((restored / "data" / f"{name}.json").read_bytes(), source)
            raw = json.loads(source)[0]
            recovered = json.loads((restored / "data" / f"{name}.json").read_bytes())[0]
            self.assertEqual(catalog_schema.catalog_revision(raw), catalog_schema.catalog_revision(recovered))
            self.assertEqual(catalog_schema.public_catalog_facts(recovered), reviewed_facts())
            self.assertEqual(self.paths[name].read_bytes(), source)

    def test_atomic_write_failure_preserves_original_and_cleans_unique_staging(self) -> None:
        path = self.paths["products"]
        before = path.read_bytes()
        for target in ("replace", "fsync"):
            with self.subTest(target=target):
                patcher = patch.object(Path, "replace", side_effect=OSError("Fixture replace failure")) if target == "replace" else patch.object(main.os, "fsync", side_effect=OSError("Fixture sync failure"))
                with patcher, self.assertRaises(OSError):
                    main.write_json_list(path, [{"id": 9}])
                self.assertEqual(before, path.read_bytes())
                self.assertEqual(list(self.root.glob(".*.tmp")), [])
        main.write_json_list(path, [{"id": 9}])
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [{"id": 9}])

    def test_save_failure_never_deletes_media_or_changes_persistent_revision(self) -> None:
        item = self.create("products", schemaVersion=2)
        before = self.paths["products"].read_bytes()
        with patch.object(main, "save_products", side_effect=OSError("Fixture write failure")), patch.object(main, "delete_catalog_images") as media:
            with self.assertRaises(OSError):
                self.update("products", item, photos=[])
            media.assert_not_called()
        self.assertEqual(before, self.paths["products"].read_bytes())
        self.assertTrue((self.uploads / "original.png").exists())

    def test_directory_sync_failure_warns_without_reporting_committed_write_as_failed(self) -> None:
        path = self.paths["products"]
        for operation in ("open", "fsync"):
            with self.subTest(operation=operation), patch.object(main, "os") as os_calls:
                os_calls.name = "posix"
                os_calls.O_RDONLY = 0
                os_calls.open.return_value = 123
                if operation == "open":
                    os_calls.open.side_effect = OSError("PRIVATE-DIRECTORY-DETAIL")
                else:
                    os_calls.fsync.side_effect = [None, OSError("PRIVATE-DIRECTORY-DETAIL")]
                with self.assertLogs(main.logger, level="WARNING") as logs:
                    main.write_json_list(path, [{"id": 9, "description": "PRIVATE-PAYLOAD"}])
                self.assertEqual(len(logs.records), 1)
                self.assertEqual(
                    logs.records[0].getMessage(),
                    "JSON replacement committed, but directory synchronization failed; crash durability is not confirmed.",
                )
                self.assertIsNone(logs.records[0].exc_info)
                self.assertEqual(logs.records[0].args, ())
                self.assertNotIn("PRIVATE", "\n".join(logs.output))
                if operation == "open":
                    os_calls.close.assert_not_called()
                else:
                    os_calls.close.assert_called_once_with(123)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), [{"id": 9, "description": "PRIVATE-PAYLOAD"}])
            self.assertEqual(list(self.root.glob(".*.tmp")), [])

    def test_metadata_only_and_unchanged_full_form_preserve_legacy_product_copy_exactly(self) -> None:
        for full_form in (False, True):
            with self.subTest(full_form=full_form):
                item = self.legacy("products")
                before = self.raw("products", item["id"])
                submitted = {key: value for key, value in before.items() if key in main.ProductPayload.model_fields} if full_form else {}
                response = self.update("products", item, **{**submitted, "schemaVersion": 2, "catalogFacts": reviewed_facts()})
                self.assertEqual(response.status_code, 200, response.text)
                after = self.raw("products", item["id"])
                for field in ("shortDescription", "description", "features"):
                    self.assertEqual(after[field], before[field], field)
                edited = self.update(
                    "products", response.json()["item"], shortDescription=" Updated short ",
                    description=" Updated long\n", features=[" Updated feature ", "", "  "],
                )
                self.assertEqual(edited.status_code, 200, edited.text)
                self.assertEqual(edited.json()["item"]["shortDescription"], "Updated short")
                self.assertEqual(edited.json()["item"]["description"], "Updated long")
                self.assertEqual(edited.json()["item"]["features"], ["Updated feature"])

    def test_invalid_reviewed_metadata_warns_without_private_payload_or_exception(self) -> None:
        raw = {
            "id": "PRIVATE-IDENTITY",
            "provenance": {"notes": "PRIVATE-SOURCE"},
            "catalogFacts": {**reviewed_facts(), "privateField": "PRIVATE-FACT"},
        }
        with self.assertLogs(catalog_schema.logger, level="WARNING") as logs:
            self.assertIsNone(catalog_schema.public_catalog_facts(raw))
        self.assertEqual(len(logs.records), 1)
        self.assertEqual(
            logs.records[0].getMessage(),
            "Reviewed catalog facts failed validation and were omitted from the public projection.",
        )
        self.assertIsNone(logs.records[0].exc_info)
        self.assertEqual(logs.records[0].args, ())
        self.assertNotIn("PRIVATE", "\n".join(logs.output))
        self.assertNotIn("privateField", "\n".join(logs.output))
        with self.assertNoLogs(catalog_schema.logger, level="WARNING"):
            self.assertIsNone(catalog_schema.public_catalog_facts({}))
            self.assertIsNone(catalog_schema.public_catalog_facts({"catalogFacts": None}))
            self.assertIsNone(catalog_schema.public_catalog_facts({"catalogFacts": {"reviewed": False, "privateField": "private"}}))
            self.assertEqual(catalog_schema.public_catalog_facts({"catalogFacts": reviewed_facts()}), reviewed_facts())

    def test_fact_text_trims_without_touching_exact_amount_or_legacy_values(self) -> None:
        facts = reviewed_facts()
        facts["options"] = {"colors": [" Black ", " Red "], "sizes": [" 34 mm ", " 36 mm "], "finish": " Satin ", "note": " A note "}
        facts["materials"] = [{"component": " frame ", "value": " Steel "}]
        facts["measurements"][0]["note"] = " Merchant note "
        facts["measurements"][0]["kind"] = " weight "
        facts["measurements"][0]["scope"] = " product "
        facts["measurements"][0]["unit"] = " kg "
        facts["interfaces"][0]["constraints"][0]["value"] = " 1/2 "
        facts["interfaces"][0]["limitations"] = " Confirm exact fit "
        facts["components"][0]["name"] = " Socket "
        facts["packageNote"] = " One unit "
        item = self.legacy("products")
        before = self.raw("products", item["id"])
        response = self.update("products", item, catalogFacts=facts)
        self.assertEqual(response.status_code, 200, response.text)
        stored = response.json()["item"]["catalogFacts"]
        self.assertEqual(stored["options"], {"colors": ["Black", "Red"], "sizes": ["34 mm", "36 mm"], "finish": "Satin", "note": "A note"})
        self.assertEqual(stored["materials"], [{"component": "frame", "value": "Steel"}])
        self.assertEqual(stored["measurements"][0]["note"], "Merchant note")
        self.assertEqual(stored["measurements"][0]["kind"], "weight")
        self.assertEqual(stored["measurements"][0]["scope"], "product")
        self.assertEqual(stored["measurements"][0]["unit"], "kg")
        self.assertEqual(stored["measurements"][0]["amount"], facts["measurements"][0]["amount"])
        self.assertEqual(stored["interfaces"][0]["constraints"][0]["value"], "1/2")
        self.assertEqual(stored["interfaces"][0]["limitations"], "Confirm exact fit")
        self.assertEqual(stored["components"][0]["name"], "Socket")
        self.assertEqual(stored["packageNote"], "One unit")
        for field in ("dimensions", "weight", "material", "colourOptions", "description", "compatibility", "provenance"):
            self.assertEqual(self.raw("products", item["id"])[field], before[field], field)
        for amount in (" 1.25", "1.25 ", "\t1.25", "1.25\n"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                catalog_schema.CatalogMeasurement.model_validate({**reviewed_facts()["measurements"][0], "amount": amount})

    def test_control_characters_and_blank_required_fact_text_are_rejected(self) -> None:
        for character in ("\0", "\x1b", "\x7f", "\x85", "\u200b", "\u202e", "\ud800"):
            for facts in (
                {"packageNote": "Before" + character + "After"},
                {"options": {"colors": ["Black" + character]}},
                {"materials": [{"component": "Frame", "value": "Steel" + character}]},
                {"interfaces": [{"kind": "rack_mount", "role": "requires", "limitations": "Confirm" + character}]},
            ):
                with self.subTest(character=repr(character), facts=facts), self.assertRaises(ValidationError):
                    catalog_schema.CatalogFacts.model_validate(facts)
        for character in ("\t", "\r", "\n", "\r\n"):
            for facts in (
                {"options": {"colors": ["Black" + character]}},
                {"options": {"sizes": ["34 mm" + character]}},
                {"options": {"finish": "Satin" + character}},
                {"materials": [{"component": "Frame", "value": "Steel" + character}]},
                {"components": [{"name": "Pin" + character, "status": "unknown"}]},
                {"interfaces": [{"kind": "rack_mount" + character, "role": "requires"}]},
            ):
                with self.subTest(character=repr(character), facts=facts), self.assertRaises(ValidationError):
                    catalog_schema.CatalogFacts.model_validate(facts)
        for facts in (
            {"options": {"colors": ["   "]}},
            {"materials": [{"component": " ", "value": "Steel"}]},
            {"components": [{"name": " ", "status": "unknown"}]},
            {"interfaces": [{"kind": "rack_mount", "role": "requires", "constraints": [{"attribute": "holeDiameter", "operator": "listed", "value": " "}]}]},
        ):
            with self.assertRaises(ValidationError):
                catalog_schema.CatalogFacts.model_validate(facts)
        for endpoint in self.paths:
            item = self.create(endpoint, schemaVersion=2)
            before = self.paths[endpoint].read_bytes()
            response = self.update(endpoint, item, catalogFacts={"packageNote": "No\u202ebidi"})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(before, self.paths[endpoint].read_bytes())

    def test_public_prose_allows_line_breaks_and_tabs_without_changing_amounts(self) -> None:
        prose = "First line\nSecond line\r\n\tThird line"
        facts = reviewed_facts()
        facts["options"]["note"] = f" {prose} "
        facts["measurements"][0]["note"] = f" {prose} "
        facts["interfaces"][0]["limitations"] = f" {prose} "
        facts["packageNote"] = f" {prose} "
        for endpoint in self.paths:
            item = self.create(endpoint, schemaVersion=2, catalogFacts=facts)
            for stored in (item["catalogFacts"], self.raw(endpoint, item["id"])["catalogFacts"], self.client.get(f"/api/{endpoint}").json()["items"][0]["catalogFacts"]):
                self.assertEqual(stored["options"]["note"], prose)
                self.assertEqual(stored["measurements"][0]["note"], prose)
                self.assertEqual(stored["interfaces"][0]["limitations"], prose)
                self.assertEqual(stored["packageNote"], prose)
                self.assertEqual(stored["measurements"][0]["amount"], facts["measurements"][0]["amount"])

    def test_duplicate_options_reject_instead_of_deduplicating_or_persisting(self) -> None:
        for field in ("colors", "sizes"):
            for labels in (["Black", "Black"], ["Black", "black"], [" Black ", "BLACK"], ["Straße", "STRASSE"]):
                with self.subTest(field=field, labels=labels), self.assertRaises(ValidationError):
                    catalog_schema.CatalogFacts.model_validate({"options": {field: labels}})
        item = self.create("accessories", schemaVersion=2)
        before = self.paths["accessories"].read_bytes()
        response = self.update("accessories", item, catalogFacts={"options": {"sizes": ["34 mm", " 34 MM "]}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(before, self.paths["accessories"].read_bytes())

    def test_schema2_unknown_root_fields_reject_while_legacy_clients_remain_compatible(self) -> None:
        for endpoint in self.paths:
            for key in ("catalogFact", "privateSource", "variants", "revision", "missingPriceMarkets"):
                before = self.paths[endpoint].read_bytes()
                body = {**self.payload, "schemaVersion": 2, key: "PRIVATE-UNKNOWN"}
                response = self.client.post(f"/api/{endpoint}", json=body, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(before, self.paths[endpoint].read_bytes())
            item = self.create(endpoint, schemaVersion=2)
            before = self.paths[endpoint].read_bytes()
            self.assertEqual(self.update(endpoint, item, schemaVersion=2, catalogFact={}).status_code, 422)
            self.assertEqual(before, self.paths[endpoint].read_bytes())
            accepted = self.update(endpoint, item, schemaVersion=2, catalogFacts=reviewed_facts())
            self.assertEqual(accepted.status_code, 200, accepted.text)
            legacy = self.legacy(endpoint)
            response = self.client.put(
                f"/api/{endpoint}/{legacy['id']}",
                json={"name": legacy["name"], "category": legacy["category"], "schemaVersion": 1, "unusedLegacyKey": "PRIVATE-LEGACY"},
                headers=self.headers,
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotIn("unusedLegacyKey", self.raw(endpoint, legacy["id"]))
            self.assertNotIn("PRIVATE", self.client.get(f"/api/{endpoint}").text)


if __name__ == "__main__":
    unittest.main()
