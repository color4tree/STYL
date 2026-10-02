"""SUP-025: approved service Q&A works independently of product assignments."""

import asyncio
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app import analytics, knowledge, main, records_archive, support, support_ai


class GeneralKnowledgeFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="styl-general-knowledge-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.products = self.root / "products.json"
        self.products.write_text("[]")
        accessories = self.root / "accessories.json"
        accessories.write_text("[]")
        for replacement in (
            patch.dict(os.environ, {
                "STYL_SUPPORT_ENABLED": "true", "STYL_SUPPORT_ENVIRONMENT": "test",
                "STYL_SUPPORT_PROVIDER": "mock", "STYL_SUPPORT_MODEL": "mock",
                "STYL_SUPPORT_DB": str(self.root / "support.sqlite3"),
                "STYL_ANALYTICS_DB": str(self.root / "analytics.sqlite3"), "STYL_ANALYTICS_ENVIRONMENT": "test",
                "STYL_KNOWLEDGE_DIR": str(self.root / "knowledge"),
                "STYL_RECORDS_DIR": str(self.root / "records"), "STYL_WEBSITE_LOG_DIR": "",
                "OPENAI_API_KEY": "", "GEMINI_API_KEY": "",
            }),
            patch.multiple(main, DATA_PATH=self.products, ACCESSORIES_PATH=accessories,
                           INQUIRIES_PATH=self.root / "inquiries", UPLOAD_PATH=self.root / "uploads",
                           ADMIN_TOKEN="general-qa-test-only"),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        with analytics.get_store().connection():
            pass
        with support.rate_lock:
            support.rate_windows.clear()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.admin = {"Authorization": "Bearer general-qa-test-only"}
        self.base = "/api/admin/support/knowledge"
        self.document = b"Customer service Q&A\n\nStandard delivery takes five business days.\n"
        created = self.client.post("/api/support/conversations", json={})
        self.assertEqual(created.status_code, 201, created.text)
        value = created.json()
        self.url = "/api/support/conversations/" + value["conversation"]["id"]
        self.guest = {"Authorization": "Bearer " + value["token"]}

    def source(self, identifier: str) -> dict:
        response = self.client.get(self.base, headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        return next(row for row in response.json()["sources"] if row["id"] == identifier)

    def upload_review(self) -> dict:
        response = self.client.post(self.base + "/documents", headers=self.admin,
                                    data={"title": "Customer service FAQ", "scope": "general", "itemRefs": "[]"},
                                    files={"file": ("faq.txt", self.document, "text/plain")})
        self.assertEqual(response.status_code, 201, response.text)
        uploaded = response.json()
        self.assertEqual(uploaded["scope"], "general")
        self.assertEqual(uploaded["itemRefs"], [])
        self.assertEqual(uploaded["bytes"], len(self.document))
        config = self.client.get(self.base, headers=self.admin).json()
        queued = self.client.post(self.base + f"/sources/{uploaded['id']}/extract", headers=self.admin, json={
            "expectedRevision": uploaded["revision"], "acknowledgeExternalProcessing": True,
            "expectedRouteFingerprint": config["routeFingerprint"],
        })
        self.assertEqual(queued.status_code, 200, queued.text)
        self.assertTrue(asyncio.run(knowledge.process_one()))
        reviewed = self.source(uploaded["id"])
        self.assertEqual(reviewed["state"], "review")
        return reviewed

    def approve(self, source: dict) -> dict:
        response = self.client.post(self.base + f"/sources/{source['id']}/review", headers=self.admin, json={
            "expectedRevision": source["revision"], "decision": "approve",
            "facts": [{"text": "Standard delivery takes five business days.", "topic": "customer_service", "location": "FAQ, delivery"}],
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def ask(self, question: str = "How long does standard delivery take?") -> dict:
        sent = self.client.post(self.url + "/messages", headers=self.guest, json={
            "clientMessageId": uuid4().hex, "text": question,
        })
        self.assertEqual(sent.status_code, 200, sent.text)
        self.assertTrue(asyncio.run(support.process_one()))
        return self.client.get(self.url, headers=self.guest).json()

    def test_general_faq_needs_no_products_and_only_approved_facts_answer(self) -> None:
        reviewed = self.upload_review()
        self.assertEqual(knowledge.approved_general_facts(), [])
        unanswered = self.ask()
        self.assertEqual(unanswered["messages"][-1]["role"], "system")
        self.approve(reviewed)
        answered = self.ask()
        self.assertEqual(answered["messages"][-1]["role"], "assistant")
        self.assertIn("five business days", answered["messages"][-1]["text"])
        self.assertIn("Customer service FAQ", answered["messages"][-1]["text"])
        self.assertEqual(answered["messages"][-1]["references"], [])
        self.assertTrue(answered["needsHuman"])

    def test_general_scope_disable_prevents_policy_answer(self) -> None:
        self.approve(self.upload_review())
        config = self.client.get("/api/admin/support/config", headers=self.admin).json()
        changed = self.client.put("/api/admin/support/config", headers=self.admin, json={
            "enabled": True, "allowedTopics": ["products", "pricing", "compatibility"], "expectedRevision": config["revision"],
        })
        self.assertEqual(changed.status_code, 200, changed.text)
        thread = self.ask()
        self.assertEqual(thread["messages"][-1]["role"], "system")
        self.assertNotIn("five business days", thread["messages"][-1]["text"])

    def test_policy_revision_change_during_answer_is_fenced(self) -> None:
        approved = self.approve(self.upload_review())
        original = support_ai.respond

        async def changed(**payload):
            result = await original(**payload)
            response = self.client.put(self.base + f"/sources/{approved['id']}/assignment", headers=self.admin,
                                       json={"scope": "general", "itemRefs": [], "expectedRevision": approved["revision"]})
            self.assertEqual(response.status_code, 200, response.text)
            return result

        with patch.object(support_ai, "respond", side_effect=changed):
            thread = self.ask()
        self.assertEqual(thread["messages"][-1]["role"], "system")
        self.assertNotIn("five business days", thread["messages"][-1]["text"])
        admin_thread = self.client.get(self.url.replace("/api/support/", "/api/admin/support/"), headers=self.admin).json()
        self.assertEqual(admin_thread["reason"], "knowledge_changed")

    def test_general_text_and_metadata_restore_in_private_archive(self) -> None:
        approved = self.approve(self.upload_review())
        created = self.client.post("/api/admin/records/archives", headers=self.admin)
        self.assertEqual(created.status_code, 201, created.text)
        archive = created.json()
        downloaded = self.client.get(f"/api/admin/records/archives/{archive['id']}/download", headers=self.admin)
        self.assertEqual(downloaded.status_code, 200)
        saved = self.root / "backup.zip"
        saved.write_bytes(downloaded.content)
        destination = self.root / "restored"
        records_archive.restore_archive(saved, destination)
        blobs = list((destination / "knowledge").glob("*.txt"))
        self.assertEqual(len(blobs), 1)
        self.assertEqual(blobs[0].read_bytes(), self.document)
        with closing(sqlite3.connect(destination / "support.sqlite3")) as database:
            row = database.execute("SELECT sourceScope,state FROM knowledge_sources WHERE id=?", (approved["id"],)).fetchone()
            self.assertEqual(row, ("general", "approved"))

    def test_general_policy_does_not_depend_on_stale_detail_page_context(self) -> None:
        self.approve(self.upload_review())
        sent = self.client.post(self.url + "/messages", headers=self.guest, json={
            "clientMessageId": uuid4().hex, "text": "How long does standard delivery take?", "itemRef": "product:99999",
        })
        self.assertEqual(sent.status_code, 200, sent.text)
        self.assertTrue(asyncio.run(support.process_one()))
        thread = self.client.get(self.url, headers=self.guest).json()
        self.assertEqual(thread["messages"][-1]["role"], "assistant")
        self.assertIn("five business days", thread["messages"][-1]["text"])

    def test_unavailable_catalog_media_has_explicit_metadata_not_an_invalid_library(self) -> None:
        self.products.write_text(json.dumps([{
            "id": 1, "slug": "missing-source", "name": "Synthetic Missing Source", "category": "Racks",
            "publicationStatus": "published", "prices": {"CAD": 100, "USD": 80},
            "photos": ["/api/uploads/missing-fixture.png"], "image": "/api/uploads/missing-fixture.png",
        }]))
        response = self.client.post(self.base + "/catalog-sync", headers=self.admin, json={})
        self.assertEqual(response.status_code, 200, response.text)
        sources = response.json()["sources"]
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["format"], "unknown")
        self.assertEqual(sources[0]["bytes"], 0)
        self.assertTrue(sources[0]["error"])


class ServiceScopeMigrationTests(unittest.TestCase):
    def test_message_budget_override_is_test_only_and_bounded(self) -> None:
        with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "test", "STYL_SUPPORT_MESSAGE_LIMIT": "500"}):
            self.assertEqual(support.message_limit(), 500)
            for environment in ("local", "production"):
                with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": environment}):
                    self.assertEqual(support.message_limit(), 120)
            for invalid in ("0", "1001", "unlimited", "-1"):
                with patch.dict(os.environ, {"STYL_SUPPORT_MESSAGE_LIMIT": invalid}):
                    with self.assertRaises(ValueError):
                        support.message_limit()

    def test_default_scope_extends_but_disabled_and_customized_choices_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory(prefix="styl-service-scope-") as temporary:
            for label, enabled, topics, expected in (
                ("default", 1, ["products", "pricing", "compatibility"], list(support.TOPICS)),
                ("disabled", 0, ["products", "pricing", "compatibility"], list(support.TOPICS)),
                ("custom", 1, ["pricing"], ["pricing"]),
            ):
                path = Path(temporary) / f"{label}.sqlite3"
                with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "test"}):
                    store = support.SupportStore(path)
                    with store.connection() as db:
                        db.execute("UPDATE settings SET enabled=?,allowed_topics=?,revision=4", (enabled, json.dumps(topics)))
                        db.execute("PRAGMA user_version=2")
                    with store.connection() as db:
                        row = db.execute("SELECT * FROM settings").fetchone()
                        self.assertEqual(json.loads(row["allowed_topics"]), expected)
                        self.assertEqual(row["enabled"], enabled)
                        self.assertEqual(row["revision"], 5 if label != "custom" else 4)
                    with store.connection() as db:
                        self.assertEqual(db.execute("SELECT revision FROM settings").fetchone()[0], 5 if label != "custom" else 4)
