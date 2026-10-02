"""SUP-013/SUP-014: approved media facts reach chat only while their source is current."""

import asyncio
import base64
from contextlib import closing
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

from app import analytics, knowledge, main, support, support_ai


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAACXBIWXMAAAABAAAAAQBPJcTWAAAAEElEQVR4nGNgGAWjYBTAAAADEAABPywr7AAAAABJRU5ErkJggg=="
)


class SupportKnowledgeTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="styl-reviewed-knowledge-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.uploads = self.root / "uploads"
        self.uploads.mkdir()
        self.products = self.root / "products.json"
        self.accessories = self.root / "accessories.json"
        self.products.write_text(json.dumps([{
            "id": 1, "slug": "synthetic-rack", "name": "Synthetic Rack", "category": "Racks",
            "prices": {"CAD": 100, "USD": 80}, "currency": "CAD", "price": 100,
            "publicationStatus": "published", "description": "A synthetic rack for isolated tests.",
            "photos": [], "image": "", "compatibility": {},
        }]))
        self.accessories.write_text("[]")
        for replacement in (
            patch.dict(os.environ, {
                "STYL_SUPPORT_ENABLED": "true", "STYL_SUPPORT_ENVIRONMENT": "test",
                "STYL_SUPPORT_PROVIDER": "mock", "STYL_SUPPORT_MODEL": "mock",
                "STYL_SUPPORT_DB": str(self.root / "support.sqlite3"),
                "STYL_ANALYTICS_DB": str(self.root / "analytics.sqlite3"),
                "STYL_ANALYTICS_ENVIRONMENT": "test",
                "STYL_KNOWLEDGE_DIR": str(self.root / "knowledge"),
                "STYL_RECORDS_DIR": str(self.root / "records"), "STYL_WEBSITE_LOG_DIR": "",
                "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "",
            }),
            patch.multiple(main, DATA_PATH=self.products, ACCESSORIES_PATH=self.accessories,
                           UPLOAD_PATH=self.uploads, INQUIRIES_PATH=self.root / "inquiries", ADMIN_TOKEN="knowledge-integration-only"),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        with analytics.get_store().connection():
            pass
        with support.rate_lock:
            support.rate_windows.clear()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.admin = {"Authorization": "Bearer knowledge-integration-only"}
        self.base = "/api/admin/support/knowledge"

    def upload(self) -> dict:
        response = self.client.post(self.base + "/documents", headers=self.admin,
                                    data={"title": "Reviewed rack diagram", "itemRefs": '["product:1"]'},
                                    files={"file": ("diagram.png", PNG, "image/png")})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def extract(self, source: dict) -> dict:
        configuration = self.client.get(self.base, headers=self.admin)
        self.assertEqual(configuration.status_code, 200, configuration.text)
        response = self.client.post(self.base + f"/sources/{source['id']}/extract", headers=self.admin,
                                    json={"expectedRevision": source["revision"], "acknowledgeExternalProcessing": True,
                                          "expectedRouteFingerprint": configuration.json()["routeFingerprint"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(asyncio.run(knowledge.process_one()))
        response = self.client.get(self.base, headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        result = next(row for row in response.json()["sources"] if row["id"] == source["id"])
        self.assertEqual(result["state"], "review")
        return result

    def approve(self, source: dict) -> dict:
        response = self.client.post(self.base + f"/sources/{source['id']}/review", headers=self.admin, json={
            "expectedRevision": source["revision"], "decision": "approve",
            "facts": [{"text": "The reviewed cradle uses a quarter-turn latch.", "topic": "products", "location": "Diagram, latch detail"}],
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def new_message(self) -> tuple[str, dict[str, str]]:
        created = self.client.post("/api/support/conversations", json={})
        self.assertEqual(created.status_code, 201, created.text)
        value = created.json()
        url = "/api/support/conversations/" + value["conversation"]["id"]
        headers = {"Authorization": "Bearer " + value["token"]}
        sent = self.client.post(url + "/messages", headers=headers, json={
            "clientMessageId": "question", "text": "Which latch is used by the Synthetic Rack cradle?",
        })
        self.assertEqual(sent.status_code, 200, sent.text)
        return url, headers

    def test_drafts_excluded_approved_sources_answered_with_attribution(self) -> None:
        source = self.extract(self.upload())
        market = {"countryCode": None, "currency": "CAD", "locationStatus": "unknown"}
        self.assertNotIn("approvedKnowledge", support.public_catalog(market)[0])
        self.approve(source)
        url, headers = self.new_message()
        self.assertTrue(asyncio.run(support.process_one()))
        conversation = self.client.get(url, headers=headers).json()
        self.assertEqual(conversation["state"], "ai")
        answer = conversation["messages"][-1]
        self.assertEqual(answer["role"], "assistant")
        self.assertIn("quarter-turn latch", answer["text"])
        self.assertIn("Reviewed rack diagram", answer["text"])
        self.assertIn("Diagram, latch detail", answer["text"])

    def test_approval_invalidated_during_response_cannot_publish_old_knowledge(self) -> None:
        source = self.approve(self.extract(self.upload()))
        url, headers = self.new_message()
        original = support_ai.respond

        async def changed(**payload):
            answer = await original(**payload)
            response = self.client.put(self.base + f"/sources/{source['id']}/assignment", headers=self.admin,
                                       json={"itemRefs": ["product:1"], "expectedRevision": source["revision"]})
            self.assertEqual(response.status_code, 200, response.text)
            return answer

        with patch.object(support_ai, "respond", side_effect=changed):
            self.assertTrue(asyncio.run(support.process_one()))
        conversation = self.client.get(url, headers=headers).json()
        self.assertEqual(conversation["state"], "waiting_human")
        self.assertIsNone(conversation["reason"])
        admin_thread = self.client.get(url.replace("/api/support/", "/api/admin/support/"), headers=self.admin).json()
        self.assertEqual(admin_thread["reason"], "catalog_changed")
        self.assertNotIn("quarter-turn latch", json.dumps(conversation["messages"]))

    def test_real_source_and_approval_tables_are_in_private_backup(self) -> None:
        source = self.approve(self.extract(self.upload()))
        response = self.client.post("/api/admin/records/archives", headers=self.admin)
        self.assertEqual(response.status_code, 201, response.text)
        value = response.json()
        self.assertEqual(value["counts"]["knowledgeFiles"], 1)
        downloaded = self.client.get(f"/api/admin/records/archives/{value['id']}/download", headers=self.admin)
        self.assertEqual(downloaded.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
            names = [name for name in archive.namelist() if name.startswith("knowledge/")]
            self.assertEqual(len(names), 1)
            self.assertEqual(archive.read(names[0]), PNG)
            snapshot = self.root / "snapshot.sqlite3"
            snapshot.write_bytes(archive.read("support.sqlite3"))
        with closing(sqlite3.connect(snapshot)) as database:
            self.assertEqual(database.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertIn(source["id"], "\n".join(database.iterdump()))
            self.assertIn("quarter-turn latch", "\n".join(database.iterdump()))

    def test_missing_referenced_source_cannot_be_disguised_as_complete_backup(self) -> None:
        self.approve(self.extract(self.upload()))
        blobs = list((self.root / "knowledge").iterdir())
        self.assertEqual(len(blobs), 1)
        blobs[0].unlink()
        response = self.client.post("/api/admin/records/archives", headers=self.admin)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("referenced knowledge source is missing", response.json()["detail"])

    def test_deleted_product_cannot_pass_approved_manual_to_a_reused_id(self) -> None:
        source = self.approve(self.extract(self.upload()))
        deleted = self.client.delete("/api/products/1", headers=self.admin)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        created = self.client.post("/api/products", headers=self.admin, json={
            "name": "Unrelated replacement bench", "category": "Benches", "publicationStatus": "published",
            "prices": {"CAD": 50, "USD": 40}, "photos": [],
        })
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()["item"]["id"], 1)
        catalog = support.public_catalog({"countryCode": None, "currency": "CAD", "locationStatus": "unknown"})
        self.assertNotIn("approvedKnowledge", catalog[0])
        listed = self.client.get(self.base, headers=self.admin).json()
        current = next(row for row in listed["sources"] if row["id"] == source["id"])
        self.assertEqual(current["state"], "stale")
        self.assertEqual(current["facts"], [])
        self.assertEqual(len(list((self.root / "knowledge").iterdir())), 1)
