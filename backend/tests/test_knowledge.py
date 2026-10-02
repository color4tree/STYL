"""KNOW-001..012: private source versions, reviewed facts, bounded extraction and recovery."""

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from contextlib import closing
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
from threading import Event
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
from imageio_ffmpeg import get_ffmpeg_exe
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app import knowledge, knowledge_extract as extraction, main, support


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jk1sAAAAASUVORK5CYII=")
FACT = {"text": "The synthetic frame is steel.", "topic": "products", "location": "Image, frame label"}
BASE = "/api/admin/support/knowledge"


def pdf(pages: int = 2) -> bytes:
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    for number in range(1, pages + 1):
        page = writer.add_blank_page(width=200, height=200)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)}),
        })
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 100 Td (Synthetic feature on page {number}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class KnowledgeFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[2] / ".styl-runtime" / ("knowledge-test-" + uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.uploads, self.images = self.root / "uploads", self.root / "images"
        self.uploads.mkdir()
        self.images.mkdir()
        (self.uploads / "fixture.png").write_bytes(PNG)
        self.products = [{
            "id": 1, "slug": "synthetic-rack", "name": "Synthetic rack", "category": "Racks",
            "publicationStatus": "published", "prices": {"CAD": 120, "USD": 90},
            "image": "/api/uploads/fixture.png", "photos": ["/api/uploads/fixture.png"],
            "provenance": {"internalNotes": "PRIVATE_CATALOG_SENTINEL"}, "secretFutureField": "DO_NOT_EXTRACT",
        }, {
            "id": 2, "slug": "draft", "name": "PRIVATE_DRAFT", "category": "Racks",
            "publicationStatus": "draft", "prices": {"CAD": 15, "USD": 10},
            "image": "/api/uploads/draft-only.png",
        }, {
            "id": 3, "slug": "canada", "name": "Canada item", "category": "Racks",
            "publicationStatus": "published", "prices": {"CAD": 30, "USD": None},
            "image": "/images/canada.png",
        }, {
            "id": 4, "slug": "unpriced", "name": "PRIVATE_UNPRICED", "category": "Racks",
            "publicationStatus": "published", "prices": {"CAD": None, "USD": None},
            "image": "/api/uploads/unpriced-only.png",
        }]
        self.accessories = [{
            "id": 1001, "name": "Synthetic handle", "category": "Handles",
            "publicationStatus": "published", "prices": {"CAD": None, "USD": 12},
            "image": "/api/uploads/fixture.png",
        }]
        (self.images / "canada.png").write_bytes(PNG)
        for replacement in (
            patch.dict(os.environ, {
                "STYL_SUPPORT_DB": str(self.root / "support.sqlite3"),
                "STYL_ANALYTICS_DB": str(self.root / "analytics.sqlite3"),
                "STYL_KNOWLEDGE_DIR": str(self.root / "knowledge"),
                "STYL_SUPPORT_ENABLED": "true", "STYL_SUPPORT_ENVIRONMENT": "test",
                "STYL_SUPPORT_PROVIDER": "gemini", "STYL_SUPPORT_MODEL": "gemini-3.5-flash",
                "STYL_KNOWLEDGE_PROVIDER": "openai", "STYL_KNOWLEDGE_MODEL": "gpt-6-luna",
                "STYL_KNOWLEDGE_VIDEO_PROVIDER": "gemini", "STYL_KNOWLEDGE_VIDEO_MODEL": "gemini-3.8-flash",
                "GEMINI_API_KEY": "synthetic-test-key-not-a-secret",
                "OPENAI_API_KEY": "synthetic-test-key-not-a-secret",
            }),
            patch.object(main, "ADMIN_TOKEN", "synthetic-admin-token"),
            patch.object(main, "UPLOAD_PATH", self.uploads),
            patch.object(main, "PUBLIC_IMAGE_PATH", self.images),
            patch.object(main, "load_products", side_effect=lambda: deepcopy(self.products)),
            patch.object(main, "load_accessories", side_effect=lambda: deepcopy(self.accessories)),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        app = FastAPI()
        app.include_router(knowledge.make_router(main.require_admin))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.admin = {"Authorization": "Bearer synthetic-admin-token"}

    def catalog(self, currency: str = "CAD") -> list[dict]:
        return support.public_catalog({"currency": currency, "countryCode": "CA", "locationStatus": "located"})

    def sync(self) -> dict:
        response = self.client.post(BASE + "/catalog-sync", json={}, headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def source(self) -> dict:
        return next(source for source in self.sync()["sources"] if "product:1" in source["itemRefs"])

    def upload(self, data: bytes = PNG, filename: str = "facts.png", mime: str = "image/png",
               refs: list | None = None, title: str = "Synthetic source", scope: str = "products") -> httpx.Response:
        return self.client.post(BASE + "/documents", headers=self.admin,
                                files={"file": (filename, data, mime)},
                                data={"title": title, "itemRefs": json.dumps(["product:1"] if refs is None else refs),
                                      "scope": scope})

    def route_fingerprint(self) -> str:
        response = self.client.get(BASE, headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["routeFingerprint"]

    def queue(self, source: dict) -> dict:
        response = self.client.post(BASE + f"/sources/{source['id']}/extract", headers=self.admin,
                                    json={"expectedRevision": source["revision"], "acknowledgeExternalProcessing": True,
                                          "expectedRouteFingerprint": self.route_fingerprint()})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def get(self, identifier: str) -> dict:
        response = self.client.get(BASE, headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        return next(source for source in response.json()["sources"] if source["id"] == identifier)

    def extracted(self, source: dict | None = None) -> dict:
        source = source or self.source()
        self.queue(source)
        with patch.object(extraction, "extract", return_value=extraction.ExtractionResult([FACT.copy()], [])) as provider:
            self.assertTrue(asyncio.run(knowledge.process_one()))
            provider.assert_called_once()
            self.assertNotIn("PRIVATE", str(provider.call_args))
        return self.get(source["id"])

    def review(self, source: dict, *, decision: str = "approve", facts=None) -> httpx.Response:
        body = {"expectedRevision": source["revision"], "decision": decision}
        if facts is not None:
            body["facts"] = facts
        return self.client.post(BASE + f"/sources/{source['id']}/review", headers=self.admin, json=body)

    def generated(self, facts: list | None = None, finish: str = "STOP") -> httpx.Response:
        return httpx.Response(200, json={
            "status": "completed" if finish == "STOP" else "incomplete",
            "output": [{"type": "message", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": json.dumps({
                            "facts": [FACT] if facts is None else facts, "warnings": [],
                        })}]}],
            "candidates": [{"finishReason": finish, "content": {"parts": [{
                "text": json.dumps({"facts": [FACT] if facts is None else facts, "warnings": []}),
            }]}}],
        })

    def provider(self, handler):
        real_client = httpx.Client
        return patch.object(extraction.httpx, "Client", side_effect=lambda **kwargs: real_client(
            **kwargs, transport=httpx.MockTransport(handler),
        ))


class KnowledgeTests(KnowledgeFixture):
    def test_know_001_auth_feature_gate_and_no_private_paths(self) -> None:
        for method, suffix, kwargs in (
            ("GET", "", {}), ("POST", "/catalog-sync", {"json": {}}),
            ("POST", "/extract-pending", {"json": {"acknowledgeExternalProcessing": True}}),
            ("POST", "/documents", {"files": {"file": ("x.png", PNG, "image/png")}}),
            ("GET", "/sources/" + "a" * 32 + "/file", {}),
        ):
            response = self.client.request(method, BASE + suffix, **kwargs)
            self.assertEqual(response.status_code, 401, response.text)
            self.assertIn("no-store", response.headers["cache-control"])
        self.assertFalse(support.configured_path().exists())
        with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "production"}):
            self.assertEqual(self.client.get(BASE, headers=self.admin).status_code, 404)
            self.assertFalse(asyncio.run(knowledge.process_one()))
        result = self.sync()
        rendered = json.dumps(result)
        for secret in ("blob_name", "source_hash", "catalog_path", "source_key", str(self.root),
                       "PRIVATE_CATALOG_SENTINEL", "PRIVATE_DRAFT", "PRIVATE_UNPRICED", "DO_NOT_EXTRACT"):
            self.assertNotIn(secret, rendered)

    def test_know_002_sync_union_deduplicates_bytes_and_never_sends_provider(self) -> None:
        with patch.object(extraction, "extract") as provider:
            index = self.sync()
            self.assertEqual(len(index["sources"]), 2)
            self.assertEqual({item["ref"] for item in index["items"]}, {"product:1", "product:3", "accessory:1001"})
            source = next(source for source in index["sources"] if "product:1" in source["itemRefs"])
            self.assertEqual(source["itemRefs"], ["accessory:1001", "product:1"])
            self.assertEqual(source["state"], "pending")
            self.assertEqual(self.sync()["sources"], index["sources"])
            self.assertFalse(asyncio.run(knowledge.process_one()))
            provider.assert_not_called()
        blobs = list(knowledge.configured_directory().iterdir())
        self.assertEqual(len(blobs), 1)
        self.assertTrue(knowledge.BLOB_NAME.fullmatch(blobs[0].name))
        self.assertEqual(blobs[0].read_bytes(), PNG)

    def test_know_003_upload_validation_sizes_scope_and_private_download(self) -> None:
        for refs in ([], ["product:2"], ["product:4"], ["product:999"], ["supplier:1"], [1]):
            self.assertEqual(self.upload(refs=refs).status_code, 422)
        for data, filename, mime in (
            (b"not an image", "facts.png", "image/png"), (PNG, "facts.png", "application/pdf"),
            (b"<script>bad</script>", "facts.html", "text/html"),
        ):
            self.assertIn(self.upload(data, filename, mime).status_code, (415, 422))
        with patch.object(extraction, "IMAGE_BYTES", 16), patch.dict(knowledge.LIMITS, {"imageBytes": 16}):
            self.assertEqual(self.upload().status_code, 413)
        result = self.upload(filename="../../facts.png")
        self.assertEqual(result.status_code, 201, result.text)
        source = result.json()
        self.assertEqual(source["kind"], "image")
        self.assertEqual(source["state"], "pending")
        self.assertFalse(knowledge.approved_facts(self.catalog()))
        response = self.client.get(BASE + f"/sources/{source['id']}/file", headers=self.admin)
        self.assertEqual(response.content, PNG)
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["content-type"], "application/octet-stream")
        self.assertEqual(self.client.get(BASE + f"/sources/{source['id']}/file").status_code, 401)

    def test_know_004_acknowledgement_review_and_revision_cas(self) -> None:
        source = self.source()
        for ack in ({}, {"acknowledgeExternalProcessing": False}):
            response = self.client.post(BASE + f"/sources/{source['id']}/extract", headers=self.admin,
                                        json={"expectedRevision": source["revision"], **ack})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.review(source, facts=[FACT]).status_code, 409)
        extracted = self.extracted(source)
        self.assertEqual(extracted["state"], "review")
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.assertEqual(self.review(source).status_code, 409)
        approved = self.review(extracted)
        self.assertEqual(approved.status_code, 200, approved.text)
        facts = knowledge.approved_facts(self.catalog())
        self.assertEqual(set(facts), {"product:1"})
        self.assertEqual(facts["product:1"][0]["text"], FACT["text"])
        self.assertEqual(facts["product:1"][0]["sourceHash"], hashlib.sha256(PNG).hexdigest())
        self.assertEqual(set(facts["product:1"][0]),
                         {"text", "topic", "location", "sourceId", "sourceName", "sourceHash", "revision"})
        rejected = self.review(approved.json(), decision="reject")
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})

    def test_know_004_forbidden_facts_future_fields_and_manual_failed_review(self) -> None:
        source = self.extracted()
        for text in ("Price is USD 99", "MSRP 140", "Costs $20", "Contact person@example.com",
                     "Supplier secret is abc", "See https://example.com", "internal notes: test",
                     "Customer telephone: +1 555 123 4567"):
            response = self.review(source, facts=[{**FACT, "text": text}])
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.review(source, facts=[{**FACT, "futurePrivateField": "secret"}]).status_code, 422)
        self.assertEqual(self.review(source, facts=[]).status_code, 422)
        self.assertEqual(self.review(source, facts=[{**FACT, "topic": "pricing"}]).status_code, 422)
        compatible = {"text": "Manufacturer explicitly lists Synthetic rack only.",
                      "topic": "compatibility", "location": "Page 1, compatibility label"}
        self.assertEqual(self.review(source, facts=[compatible]).status_code, 200)
        self.assertEqual(knowledge.approved_facts(self.catalog())["product:1"][0]["topic"], "compatibility")

    def test_know_005_source_byte_changes_exclude_before_sync_and_preserve_original(self) -> None:
        source = self.extracted()
        approved = self.review(source).json()
        original = next(knowledge.configured_directory().iterdir())
        self.assertTrue(knowledge.approved_facts(self.catalog()))
        changed = PNG[:-12] + b"changed" + PNG[-12:]
        (self.uploads / "fixture.png").write_bytes(changed)
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        synced = self.sync()
        current = next(item for item in synced["sources"] if item["id"] == source["id"])
        self.assertEqual(current["state"], "stale")
        self.assertGreater(current["revision"], approved["revision"])
        self.assertEqual(original.read_bytes(), PNG)
        self.assertEqual(len(list(knowledge.configured_directory().iterdir())), 2)
        self.assertEqual(self.review(approved).status_code, 409)
        with knowledge._connection() as db:
            versions = db.execute("SELECT snapshot FROM knowledge_versions WHERE source_id=?", (source["id"],)).fetchall()
            self.assertTrue(any(json.loads(row[0])["source_hash"] == hashlib.sha256(PNG).hexdigest() for row in versions))

    def test_know_005_unpublish_remove_reassign_and_blob_tamper_exclude(self) -> None:
        source = self.extracted()
        approved = self.review(source).json()
        self.products[0]["publicationStatus"] = "draft"
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.products[0]["publicationStatus"] = "published"
        self.products[0]["image"] = ""
        self.products[0]["photos"] = []
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.products[0]["image"] = "/api/uploads/fixture.png"
        response = self.client.put(BASE + f"/sources/{source['id']}/assignment", headers=self.admin,
                                   json={"expectedRevision": approved["revision"], "itemRefs": ["accessory:1001"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["state"], "stale")
        self.assertFalse(response.json()["facts"])
        self.assertEqual(knowledge.approved_facts(self.catalog("USD")), {})
        original = next(knowledge.configured_directory().iterdir())
        original.write_bytes(b"corrupt")
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.assertEqual(self.client.get(BASE + f"/sources/{source['id']}/file", headers=self.admin).status_code, 409)

    def test_know_005_missing_media_sync_idempotent_and_restoration_invalidates(self) -> None:
        source = self.extracted()
        self.assertEqual(self.review(source).status_code, 200)
        (self.uploads / "fixture.png").unlink()
        first = next(item for item in self.sync()["sources"] if item["id"] == source["id"])
        second = next(item for item in self.sync()["sources"] if item["id"] == source["id"])
        self.assertEqual(first, second)
        self.assertEqual(first["state"], "failed")
        (self.uploads / "fixture.png").write_bytes(PNG)
        restored = next(item for item in self.sync()["sources"] if item["id"] == source["id"])
        self.assertEqual(restored["state"], "stale")
        self.assertIsNone(restored["error"])
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})

    def test_know_005_reused_catalog_ids_preserve_old_stale_source_and_process_new_url(self) -> None:
        original = self.source()
        original_id = original["id"]
        (self.uploads / "next-fixture.png").write_bytes(PNG)
        # Mirrors successive E2E fixtures: delete/recreate highest IDs, identical
        # image bytes, but a newly allocated public upload URL.
        self.products[0].update(name="Replacement fixture", image="/api/uploads/next-fixture.png",
                                photos=["/api/uploads/next-fixture.png"])
        self.accessories[0].update(name="Replacement accessory", image="/api/uploads/next-fixture.png")
        index = self.sync()
        matches = [source for source in index["sources"]
                   if source["origin"] == "catalog" and "product:1" in source["itemRefs"]]
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]["id"], original_id)
        self.assertEqual(matches[0]["state"], "stale")
        current = next(source for source in matches if source["state"] == "pending")
        self.assertNotEqual(current["id"], original_id)
        response = self.client.post(BASE + "/extract-pending", headers=self.admin,
                                    json={"acknowledgeExternalProcessing": True,
                                          "expectedRouteFingerprint": index["routeFingerprint"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.get(original_id)["state"], "stale")
        self.assertEqual(self.get(current["id"])["state"], "queued")
        with patch.object(extraction, "extract", return_value=extraction.ExtractionResult([FACT], [])):
            for _ in range(3):
                if not asyncio.run(knowledge.process_one()):
                    break
        self.assertEqual(self.get(original_id)["state"], "stale")
        self.assertEqual(self.get(current["id"])["state"], "review")
        self.assertEqual(len(list(knowledge.configured_directory().iterdir())), 1)

    def test_know_005_delete_guard_invalidates_manual_before_delete_and_blocks_reused_ids(self) -> None:
        source = self.upload(refs=["product:1", "accessory:1001"]).json()
        approved = self.review(self.extracted(source)).json()
        self.assertTrue(knowledge.approved_facts(self.catalog()))
        previous_files = {path.name: path.read_bytes() for path in knowledge.configured_directory().iterdir()}
        with knowledge.catalog_delete_guard("product:1"):
            self.assertTrue(main.CATALOG_LOCK.locked())
            db = sqlite3.connect(support.configured_path().as_uri() + "?mode=ro", uri=True)
            try:
                row = db.execute("SELECT state,facts,revision,item_refs FROM knowledge_sources WHERE id=?",
                                 (source["id"],)).fetchone()
                self.assertEqual(row[0], "stale")
                self.assertEqual(row[1], "[]")
                self.assertGreater(row[2], approved["revision"])
                self.assertEqual(json.loads(row[3]), ["accessory:1001", "product:1"])
                self.assertIsNotNone(db.execute("SELECT 1 FROM knowledge_versions WHERE source_id=? AND revision=?",
                                               (source["id"], approved["revision"])).fetchone())
            finally:
                db.close()
            self.products.pop(0)
        replacement = {"id": 1, "slug": "unrelated-machine", "name": "Unrelated machine", "category": "Racks",
                       "publicationStatus": "published", "prices": {"CAD": 999, "USD": 800}}
        self.products.append(replacement)
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.assertEqual(knowledge.approved_facts(self.catalog("USD")), {})
        self.sync()
        current = self.get(source["id"])
        self.assertEqual(current["state"], "stale")
        self.assertEqual(self.review(approved).status_code, 409)
        self.assertEqual(self.review(current, facts=[FACT]).status_code, 409)
        response = self.client.post(BASE + f"/sources/{source['id']}/extract", headers=self.admin,
                                    json={"expectedRevision": current["revision"], "acknowledgeExternalProcessing": True,
                                          "expectedRouteFingerprint": self.route_fingerprint()})
        self.assertEqual(response.status_code, 409)
        self.assertEqual({path.name: path.read_bytes() for path in knowledge.configured_directory().iterdir()},
                         previous_files)
        reassigned = self.client.put(BASE + f"/sources/{source['id']}/assignment", headers=self.admin,
                                     json={"expectedRevision": current["revision"], "itemRefs": ["accessory:1001"]})
        self.assertEqual(reassigned.status_code, 200, reassigned.text)
        self.assertEqual(self.review(self.extracted(reassigned.json())).status_code, 200)
        self.assertEqual(set(knowledge.approved_facts(self.catalog("USD"))), {"accessory:1001"})

    def test_know_005_out_of_band_replacement_invalidates_document_identity_readonly(self) -> None:
        source = self.upload().json()
        self.assertEqual(self.review(self.extracted(source)).status_code, 200)
        self.products[0]["prices"]["CAD"] = 777
        self.assertTrue(knowledge.approved_facts(self.catalog()))
        self.products[0]["name"] = "An unrelated replacement reusing the same numeric ID"
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.sync()
        current = self.get(source["id"])
        self.assertEqual(current["state"], "stale")
        self.assertEqual(current["facts"], [])

    def test_know_005_legacy_document_without_identity_fails_closed_until_reassigned(self) -> None:
        source = self.upload().json()
        self.assertEqual(self.review(self.extracted(source)).status_code, 200)
        with knowledge._connection() as db:
            db.execute("ALTER TABLE knowledge_sources DROP COLUMN item_identities")
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.sync()
        current = self.get(source["id"])
        self.assertEqual(current["state"], "stale")
        with knowledge._connection() as db:
            self.assertEqual(knowledge._source(db, source["id"])["item_identities"], "{}")

    def test_know_005_delete_guard_commits_before_yield_and_fences_concurrent_approval(self) -> None:
        source = self.upload().json()
        approved = self.review(self.extracted(source)).json()
        started = Event()

        def concurrent_review():
            started.set()
            return self.review(approved)

        with ThreadPoolExecutor(max_workers=1) as pool:
            with knowledge.catalog_delete_guard("product:1"):
                future = pool.submit(concurrent_review)
                self.assertTrue(started.wait(timeout=5))
                with self.assertRaises(FutureTimeoutError):
                    future.result(timeout=0.1)
                self.products.pop(0)
            self.assertEqual(future.result(timeout=5).status_code, 409)
        self.assertFalse(main.CATALOG_LOCK.locked())
        self.assertEqual(self.get(source["id"])["state"], "stale")

    def test_know_005_delete_guard_legacy_no_storage_creation_and_failure_is_private(self) -> None:
        with knowledge.catalog_delete_guard("product:1"):
            self.assertTrue(main.CATALOG_LOCK.locked())
            self.assertFalse(support.configured_path().exists())
        with support.get_store().connection():
            pass
        with knowledge.catalog_delete_guard("product:1"):
            self.assertTrue(main.CATALOG_LOCK.locked())
        with closing(sqlite3.connect(support.configured_path())) as db:
            self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name='knowledge_sources'").fetchone())
        source = self.upload().json()
        with patch.object(knowledge, "_update", side_effect=sqlite3.OperationalError("PRIVATE_DATABASE_DETAIL")):
            with self.assertRaises(knowledge.HTTPException) as failure:
                with knowledge.catalog_delete_guard("product:1"):
                    self.fail("A failed durable invalidation must not permit catalog deletion")
        self.assertEqual(failure.exception.status_code, 503)
        self.assertNotIn("PRIVATE_DATABASE_DETAIL", failure.exception.detail)
        self.assertIn("no-store", failure.exception.headers["Cache-Control"])
        self.assertFalse(main.CATALOG_LOCK.locked())
        self.assertEqual(self.get(source["id"])["state"], "pending")

    def test_know_006_readonly_inside_write_transaction_and_absent_db(self) -> None:
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})
        self.assertFalse(support.configured_path().exists())
        source = self.extracted()
        self.assertEqual(self.review(source).status_code, 200)
        with support.get_store().connection() as db:
            db.execute("UPDATE settings SET revision=revision+1 WHERE id=1")
            with patch.object(support, "get_store", side_effect=AssertionError("Read-only path must not open a store")):
                with ThreadPoolExecutor(max_workers=1) as pool:
                    facts = pool.submit(knowledge.approved_facts, self.catalog()).result(timeout=2)
            self.assertEqual(facts["product:1"][0]["text"], FACT["text"])
        # A knowledge table initialization must not commit unrelated changes.
        with self.assertRaises(RuntimeError):
            with knowledge._connection() as db:
                db.execute("UPDATE settings SET revision=77")
                raise RuntimeError("rollback")
        with support.get_store().connection() as db:
            self.assertNotEqual(db.execute("SELECT revision FROM settings").fetchone()[0], 77)

    def test_know_007_queued_restart_interrupted_jobs_and_no_auto_requeue(self) -> None:
        source = self.source()
        self.queue(source)
        self.assertEqual(knowledge.recover_interrupted(), 0)
        job = knowledge._claim()
        self.assertEqual(job["state"], "processing")
        self.assertIsNone(knowledge._claim())
        self.assertEqual(knowledge.recover_interrupted(), 1)
        paused = self.get(source["id"])
        self.assertEqual(paused["state"], "paused")
        with patch.object(extraction, "extract") as provider:
            self.assertFalse(asyncio.run(knowledge.process_one()))
            provider.assert_not_called()
        self.queue(paused)
        with patch.object(extraction, "extract", return_value=extraction.ExtractionResult([FACT], [])):
            self.assertTrue(asyncio.run(knowledge.process_one()))
        self.assertEqual(self.get(source["id"])["state"], "review")

    def test_know_007_running_job_cannot_overwrite_new_assignment(self) -> None:
        source = self.upload().json()
        self.queue(source)
        job = knowledge._claim()
        entered, release = Event(), Event()

        def provider(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=10))
            return extraction.ExtractionResult([FACT], [])

        with patch.object(extraction, "extract", side_effect=provider), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(knowledge._process, job)
            self.assertTrue(entered.wait(timeout=5))
            response = self.client.put(BASE + f"/sources/{source['id']}/assignment", headers=self.admin,
                                       json={"expectedRevision": job["revision"], "itemRefs": ["product:3"]})
            release.set()
            self.assertEqual(response.status_code, 200, response.text)
            future.result(timeout=10)
        current = self.get(source["id"])
        self.assertEqual(current["itemRefs"], ["product:3"])
        self.assertEqual(current["state"], "stale")
        self.assertEqual(current["facts"], [])

    def test_know_007_cancellation_waits_for_cleanup_and_pauses_without_publication(self) -> None:
        source = self.upload().json()
        self.queue(source)
        entered, cleaned = Event(), Event()

        def provider(path, kind, **options):
            entered.set()
            try:
                deadline = datetime.now() + timedelta(seconds=5)
                while not options["cancelled"]():
                    if datetime.now() > deadline:
                        self.fail("Worker did not signal cancellation")
                    cleaned.wait(0.01)
                extraction._check_cancelled(options["cancelled"])
            finally:
                cleaned.set()

        async def cancel():
            task = asyncio.create_task(knowledge.process_one())
            self.assertTrue(await asyncio.to_thread(entered.wait, 5))
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(cleaned.is_set())

        with patch.object(extraction, "extract", side_effect=provider):
            asyncio.run(cancel())
        current = self.get(source["id"])
        self.assertEqual(current["state"], "paused")
        self.assertIsNone(current["retryAt"])
        self.assertEqual(current["facts"], [])
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})

    def test_know_008_quota_pauses_bounded_backoff_explicit_retry(self) -> None:
        source = self.source()
        self.queue(source)
        with patch.object(extraction, "extract", side_effect=extraction.ExtractionError(
            "Provider quota exceeded. No paid upgrade.", retryable=True, retry_after=99999,
        )) as provider:
            self.assertTrue(asyncio.run(knowledge.process_one()))
            for _ in range(3):
                self.assertFalse(asyncio.run(knowledge.process_one()))
            provider.assert_called_once()
        paused = self.get(source["id"])
        self.assertEqual(paused["state"], "paused")
        self.assertIsNotNone(paused["retryAt"])
        response = self.client.post(BASE + f"/sources/{source['id']}/extract", headers=self.admin,
                                    json={"expectedRevision": paused["revision"], "acknowledgeExternalProcessing": True,
                                          "expectedRouteFingerprint": self.route_fingerprint()})
        self.assertEqual(response.status_code, 429)

    def test_know_008_provider_cooldown_is_shared_durable_and_does_not_attempt_next_source(self) -> None:
        for status in (429, 503):
            with self.subTest(status=status):
                first = self.upload(title=f"Synthetic first {status}").json()
                second = self.upload(title=f"Synthetic second {status}").json()
                self.queue(first)
                self.queue(second)
                with patch.object(extraction, "extract", side_effect=extraction.ExtractionError(
                    f"Provider {status}", retryable=True, retry_after=3600,
                )) as provider:
                    self.assertTrue(asyncio.run(knowledge.process_one()))
                    self.assertFalse(asyncio.run(knowledge.process_one()))
                    self.assertFalse(asyncio.run(knowledge.process_one()))
                    provider.assert_called_once()
                paused = self.get(first["id"])
                self.assertEqual(paused["state"], "paused")
                self.assertEqual(self.get(second["id"])["state"], "queued")
                with knowledge._connection() as db:
                    cooldown = db.execute("SELECT provider,model,retry_at FROM knowledge_provider_cooldowns").fetchone()
                    self.assertEqual(cooldown["provider"], "openai")
                    self.assertEqual(cooldown["retry_at"], paused["retryAt"])
                    second_row = knowledge._source(db, second["id"])
                    self.assertEqual(second_row["attempts"], 0)
                self.assertEqual(knowledge.recover_interrupted(), 0)
                self.assertFalse(asyncio.run(knowledge.process_one()))
                later = (datetime.fromisoformat(paused["retryAt"]) + timedelta(seconds=1)).isoformat()
                with patch.object(support, "now", return_value=later), \
                        patch.object(extraction, "extract", return_value=extraction.ExtractionResult([FACT], [])) as provider:
                    self.assertTrue(asyncio.run(knowledge.process_one()))
                    provider.assert_called_once()
                self.assertEqual(self.get(second["id"])["state"], "review")
                self.assertEqual(self.get(first["id"])["state"], "paused")
                with knowledge._connection() as db:
                    db.execute("DELETE FROM knowledge_provider_cooldowns")

    def test_know_008_cooldown_rechecked_after_claim_and_before_external_upload(self) -> None:
        for stage in ("after_claim", "before_upload"):
            with self.subTest(stage=stage):
                source = self.upload(title=f"Synthetic {stage}").json()
                self.queue(source)
                job = knowledge._claim()
                retry_at = (datetime.fromisoformat(support.now()) + timedelta(hours=1)).isoformat()
                if stage == "after_claim":
                    knowledge._pause_provider(job["provider"], job["model"], retry_at)
                    with patch.object(extraction, "extract") as provider:
                        knowledge._process(job)
                        provider.assert_not_called()
                else:
                    def before_upload(path, kind, **options):
                        knowledge._pause_provider(job["provider"], job["model"], retry_at)
                        options["cancelled"]()
                        self.fail("Provider upload should be prevented by the cooldown checkpoint")

                    with patch.object(extraction, "extract", side_effect=before_upload):
                        knowledge._process(job)
                current = self.get(source["id"])
                self.assertEqual(current["state"], "queued")
                self.assertEqual(current["retryAt"], retry_at)
                with knowledge._connection() as db:
                    self.assertEqual(knowledge._source(db, source["id"])["attempts"], 0)
                    db.execute("DELETE FROM knowledge_provider_cooldowns")
                    # Keep this intentionally deferred job out of the next subcase.
                    db.execute("UPDATE knowledge_sources SET state='paused' WHERE id=?", (source["id"],))

    def test_know_008_quota_still_pauses_provider_when_source_revision_changed(self) -> None:
        first, second = self.upload().json(), self.upload().json()
        self.queue(first)
        self.queue(second)

        def invalidate_then_limit(path, kind, **options):
            with knowledge.catalog_delete_guard("product:1"):
                pass
            raise extraction.ExtractionError("Quota limit", retryable=True, retry_after=3600)

        with patch.object(extraction, "extract", side_effect=invalidate_then_limit) as provider:
            self.assertTrue(asyncio.run(knowledge.process_one()))
            self.assertFalse(asyncio.run(knowledge.process_one()))
            provider.assert_called_once()
        self.assertEqual(self.get(first["id"])["state"], "stale")
        with knowledge._connection() as db:
            self.assertIsNotNone(knowledge._cooldown(db, *extraction.provider_settings("image")))

    def test_know_009_external_paths_missing_sources_and_unsupported_are_visible(self) -> None:
        self.products[0]["photos"] += ["https://example.invalid/customer.png", "/api/uploads/../secret.png",
                                      "/images/missing.png", "/images/diagram.svg"]
        (self.images / "diagram.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"></svg>', encoding="utf-8")
        result = self.sync()
        self.assertEqual(len(result["sources"]), 6)
        self.assertEqual(sum(source["state"] == "failed" for source in result["sources"]), 3)
        self.assertTrue(any("not fetched" in warning for warning in result["warnings"]))
        svg = next(source for source in result["sources"] if source["name"].endswith("diagram.svg"))
        self.queue(svg)
        self.assertTrue(asyncio.run(knowledge.process_one()))
        self.assertIn("SVG", self.get(svg["id"])["error"])
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})

    def test_know_009_symlink_and_public_directory_denied(self) -> None:
        public = Path(main.__file__).resolve().parents[2] / "frontend" / "public" / "knowledge"
        with patch.dict(os.environ, {"STYL_KNOWLEDGE_DIR": str(public)}):
            with self.assertRaises(ValueError):
                knowledge.configured_directory()
        with patch.dict(os.environ, {"STYL_KNOWLEDGE_DIR": "relative"}):
            with self.assertRaises(ValueError):
                knowledge.configured_directory()
        with patch.object(Path, "is_symlink", return_value=True):
            with self.assertRaises(ValueError):
                knowledge.configured_directory()
            with self.assertRaises(ValueError):
                knowledge._catalog_path("/api/uploads/fixture.png")

    def test_know_010_native_pdf_all_pages_and_page_limit(self) -> None:
        response = self.upload(pdf(7), "manual.pdf", "application/pdf")
        self.assertEqual(response.status_code, 201, response.text)
        with knowledge._connection() as db:
            path = knowledge._blob_path(knowledge._source(db, response.json()["id"])["blob_name"])
        with self.provider(lambda request: self.generated()):
            result = extraction.extract(path, "pdf")
        text = "\n".join(fact["text"] for fact in result.facts)
        for number in range(1, 8):
            self.assertIn(f"Synthetic feature on page {number}", text)
        self.assertEqual(len(result.facts), 9)  # Seven native chunks plus two visual groups.
        with patch.object(extraction, "MAX_PAGES", 1):
            response = self.upload(pdf(2), "manual.pdf", "application/pdf")
            self.assertEqual(response.status_code, 422)
            self.assertIn("no pages", response.json()["detail"])

    def test_know_010_scanned_pdf_visual_facts_and_incomplete_output_rejected(self) -> None:
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        output = io.BytesIO()
        writer.write(output)
        response = self.upload(output.getvalue(), "scan.pdf", "application/pdf")
        self.assertEqual(response.status_code, 201)
        with knowledge._connection() as db:
            path = knowledge._blob_path(knowledge._source(db, response.json()["id"])["blob_name"])
        with self.provider(lambda request: self.generated()):
            self.assertEqual(extraction.extract(path, "pdf").facts, [FACT])
        with self.provider(lambda request: self.generated(finish="MAX_TOKENS")):
            with self.assertRaisesRegex(extraction.ExtractionError, "incomplete"):
                extraction.extract(path, "pdf")

    def test_know_010_mock_provider_is_local_only_and_never_constructs_http_client(self) -> None:
        source = self.upload(pdf(2), "synthetic.pdf", "application/pdf").json()
        with patch.dict(os.environ, {"STYL_SUPPORT_PROVIDER": "mock"}), \
                patch.object(extraction.httpx, "Client", side_effect=AssertionError("No mock provider network")):
            self.queue(source)
            self.assertTrue(asyncio.run(knowledge.process_one()))
            current = self.get(source["id"])
            self.assertEqual(current["state"], "review")
            self.assertEqual(len(current["facts"]), 3)
            self.assertEqual(current["facts"][-1]["text"],
                             "Synthetic test-only media fact. An administrator must review this draft.")
            self.assertEqual(knowledge.approved_facts(self.catalog()), {})
            self.assertEqual(self.review(current).status_code, 200)
            with knowledge._connection() as db:
                path = knowledge._blob_path(knowledge._source(db, source["id"])["blob_name"])
            with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "production"}):
                with self.assertRaisesRegex(extraction.ExtractionError, "configuration"):
                    extraction.extract(path, "pdf")

    def test_know_011_openai_fixed_endpoint_no_redirects_and_status_backoff(self) -> None:
        path = self.uploads / "fixture.png"
        for status in (429, 503):
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(status, headers={"retry-after": "90000"}, json={"error": "SENSITIVE_PROVIDER_DETAIL"})

            with self.provider(handler), patch.object(extraction, "_decode_image", return_value=(PNG, "image/png")):
                with self.assertRaises(extraction.ExtractionError) as failure:
                    extraction.extract(path, "image")
            self.assertTrue(failure.exception.retryable)
            self.assertEqual(failure.exception.retry_after, 3600)
            self.assertNotIn("SENSITIVE_PROVIDER_DETAIL", str(failure.exception))
            self.assertEqual(len(calls), 1)
            self.assertEqual(str(calls[0].url), extraction.OPENAI_URL)
            self.assertNotIn("synthetic-test-key", str(calls[0].url))
        with self.provider(lambda request: httpx.Response(302, headers={"location": "https://example.invalid"})), \
                patch.object(extraction, "_decode_image", return_value=(PNG, "image/png")):
            with self.assertRaises(extraction.ExtractionError):
                extraction.extract(path, "image")

    def test_know_011_valid_png_decodes_before_provider_request(self) -> None:
        path = self.uploads / "synthetic-valid.png"
        subprocess.run([get_ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "color=c=black:s=16x16:d=1", "-frames:v", "1",
                        "-update", "1", str(path)], check=True, capture_output=True, timeout=30)
        with self.provider(lambda request: self.generated()):
            self.assertEqual(extraction.extract(path, "image").facts, [FACT])

    def test_know_011_video_entire_fixture_files_api_and_cleanup(self) -> None:
        path = self.uploads / "clip.mp4"
        subprocess.run([get_ffmpeg_exe(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "color=c=black:s=16x16:d=1", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", str(path)], check=True, capture_output=True, timeout=30)
        calls, tracked, removed = [], [], []

        def handler(request):
            calls.append(request)
            self.assertEqual(request.url.host, "generativelanguage.googleapis.com")
            self.assertEqual(request.headers["x-goog-api-key"], "synthetic-test-key-not-a-secret")
            self.assertNotIn("authorization", request.headers)
            if request.method == "DELETE":
                return httpx.Response(200, json={})
            if request.url.path == "/upload/v1beta/files":
                if not request.url.query:
                    return httpx.Response(200, headers={"x-goog-upload-url":
                                                       extraction.HOST + "/upload/v1beta/files?upload_id=synthetic"})
                self.assertEqual(path.read_bytes(), request.content)
                return httpx.Response(200, json={"file": {
                    "name": "files/synthetic-clip", "state": "ACTIVE", "mimeType": "video/mp4",
                    "uri": "https://evil.invalid/ignored",
                }})
            return self.generated(facts=[{**FACT, "location": "00:00:01, end frame"}])

        with self.provider(handler):
            result = extraction.extract(path, "video", track=tracked.append, untrack=removed.append)
        self.assertEqual(result.facts[0]["location"], "00:00:01, end frame")
        self.assertEqual(tracked, ["files/synthetic-clip"])
        self.assertEqual(removed, tracked)
        self.assertEqual([call.method for call in calls], ["POST", "POST", "POST", "DELETE"])
        self.assertEqual(calls[2].url.path, "/v1beta/models/gemini-3.8-flash:generateContent")
        request = json.loads(calls[2].content)
        self.assertEqual(request["contents"][0]["parts"][1]["fileData"]["fileUri"],
                         extraction.HOST + "/v1beta/files/synthetic-clip")

    def test_know_011_video_files_api_surfaces_cleanup_failure(self) -> None:
        path = self.root / "synthetic.mp4"
        path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32)
        calls, tracked, removed = [], [], []

        def handler(request):
            calls.append(request)
            if request.method == "DELETE":
                return httpx.Response(503, json={})
            if request.url.path == "/upload/v1beta/files":
                if not request.url.query:
                    return httpx.Response(200, headers={"x-goog-upload-url":
                                                       extraction.HOST + "/upload/v1beta/files?upload_id=video"})
                return httpx.Response(200, json={"file": {"name": "files/synthetic-video", "state": "ACTIVE"}})
            return self.generated()

        with self.provider(handler), patch.object(extraction, "_video"):
            result = extraction.extract(path, "video", track=tracked.append, untrack=removed.append)
        self.assertEqual(tracked, ["files/synthetic-video"])
        self.assertFalse(removed)
        self.assertTrue(any("cleanup failed" in warning for warning in result.warnings))
        self.assertEqual(len(calls), 4)

    def test_know_011_provider_upload_redirect_or_unknown_host_never_receives_media(self) -> None:
        path = self.root / "synthetic.mp4"
        path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32)
        for location in ("http://generativelanguage.googleapis.com/upload/v1beta/files?x=1",
                         "https://evil.invalid/upload/v1beta/files?x=1",
                         "https://generativelanguage.googleapis.com:443/upload/v1beta/files?x=1",
                         "https://generativelanguage.googleapis.com/unknown?x=1"):
            calls = []

            def handler(request):
                calls.append(request)
                return httpx.Response(200, headers={"x-goog-upload-url": location})

            with self.provider(handler), patch.object(extraction, "_video"):
                with self.assertRaisesRegex(extraction.ExtractionError, "endpoint"):
                    extraction.extract(path, "video")
            self.assertEqual(len(calls), 1)
            self.assertNotIn(b"ftyp", calls[0].content)

    def test_know_012_bulk_queue_acknowledgement_and_durable_blob_limit(self) -> None:
        index = self.sync()
        with patch.object(knowledge, "MAX_PRIVATE_BYTES", len(PNG)):
            changed = PNG[:-12] + b"different" + PNG[-12:]
            response = self.upload(changed)
            self.assertEqual(response.status_code, 413, response.text)
        response = self.client.post(BASE + "/extract-pending", headers=self.admin, json={})
        self.assertEqual(response.status_code, 422)
        response = self.client.post(BASE + "/extract-pending", headers=self.admin,
                                    json={"acknowledgeExternalProcessing": True,
                                          "expectedRouteFingerprint": index["routeFingerprint"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(all(source["state"] == "queued" for source in response.json()["sources"]))
        self.assertEqual(len(response.json()["sources"]), len(index["sources"]))
        self.assertEqual(len(list(knowledge.configured_directory().iterdir())), 1)

    def test_know_012_remote_cleanup_failure_durable_and_bounded(self) -> None:
        source = self.source()
        knowledge._track(source["id"], source["revision"], "files/synthetic-orphan")
        with patch.object(extraction, "cleanup_file", side_effect=extraction.ExtractionError("cleanup failed")) as cleanup:
            self.assertTrue(asyncio.run(knowledge.process_one()))
            self.assertFalse(asyncio.run(knowledge.process_one()))
            cleanup.assert_called_once()
        self.assertIn("cleanup failed", self.get(source["id"])["error"])
        with knowledge._connection() as db:
            row = db.execute("SELECT * FROM knowledge_uploads").fetchone()
            self.assertEqual(row["attempts"], 1)
            self.assertIsNotNone(row["retry_at"])
            db.execute("UPDATE knowledge_uploads SET attempts=3,retry_at=NULL")
        with patch.object(extraction, "cleanup_file") as cleanup:
            self.assertFalse(asyncio.run(knowledge.process_one()))
            cleanup.assert_not_called()

    def test_know_012_capacity_and_no_implicit_deletion(self) -> None:
        self.sync()
        with patch.object(knowledge, "MAX_SOURCES", 2):
            self.assertEqual(self.upload().status_code, 413)
        self.products.clear()
        self.accessories.clear()
        result = self.sync()
        self.assertEqual(len(result["sources"]), 2)
        self.assertTrue(all(source["state"] == "stale" for source in result["sources"]))
        self.assertEqual(len(list(knowledge.configured_directory().iterdir())), 1)
        self.assertEqual(knowledge.approved_facts(self.catalog()), {})

    def test_know_012_blob_published_before_database_commit_with_no_partial_blob_files(self) -> None:
        replace = os.replace
        observed = []

        def publish(source, destination):
            directory = knowledge.configured_directory()
            self.assertNotEqual(source.parent, directory)
            self.assertTrue(all(knowledge.BLOB_NAME.fullmatch(path.name) for path in directory.iterdir()))
            replace(source, destination)
            self.assertTrue(destination.is_file())
            db = sqlite3.connect(support.configured_path().as_uri() + "?mode=ro", uri=True)
            try:
                exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='knowledge_sources'").fetchone()
                self.assertFalse(exists and db.execute("SELECT 1 FROM knowledge_sources").fetchone())
            finally:
                db.close()
            observed.append(destination.name)

        with patch.object(knowledge.os, "replace", side_effect=publish):
            response = self.upload()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(len(observed), 1)
        self.assertFalse(list(self.root.glob(".knowledge-*.pending")))

    def test_know_012_backup_names_readonly_legacy_and_all_historical_versions(self) -> None:
        legacy = sqlite3.connect(":memory:")
        try:
            legacy.execute("PRAGMA query_only=ON")
            self.assertEqual(knowledge.backup_blob_names(legacy), set())
        finally:
            legacy.close()
        source = self.source()
        old_name = hashlib.sha256(PNG).hexdigest() + ".png"
        changed = PNG[:-12] + b"version two" + PNG[-12:]
        (self.uploads / "fixture.png").write_bytes(changed)
        self.sync()
        new_name = hashlib.sha256(changed).hexdigest() + ".png"
        db = sqlite3.connect(support.configured_path().as_uri() + "?mode=ro", uri=True)
        try:
            db.execute("PRAGMA query_only=ON")
            self.assertEqual(knowledge.backup_blob_names(db), {old_name, new_name})
        finally:
            db.close()
        with knowledge._connection() as writable:
            row = writable.execute("SELECT snapshot,revision FROM knowledge_versions WHERE source_id=?",
                                   (source["id"],)).fetchone()
            snapshot = json.loads(row["snapshot"])
            snapshot["blob_name"] = "../private.json"
            writable.execute("UPDATE knowledge_versions SET snapshot=? WHERE source_id=? AND revision=?",
                             (json.dumps(snapshot), source["id"], row["revision"]))
            with self.assertRaisesRegex(ValueError, "historical"):
                knowledge.backup_blob_names(writable)


if __name__ == "__main__":
    unittest.main()
