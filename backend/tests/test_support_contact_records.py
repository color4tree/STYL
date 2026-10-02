"""SUP-019: private follow-up contacts are backed up and never sent to the model."""

import asyncio
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import analytics, main, records_archive, support


class ContactRecordsTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="styl-private-contact-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        products = self.root / "products.json"
        accessories = self.root / "accessories.json"
        products.write_text(json.dumps([{
            "id": 1, "slug": "synthetic-bench", "name": "STYL Synthetic Bench", "category": "Benches",
            "prices": {"CAD": 100, "USD": 80}, "publicationStatus": "published",
            "weight": "10 kg", "description": "Synthetic fixture.",
        }]))
        accessories.write_text("[]")
        for replacement in (
            patch.dict(os.environ, {
                "STYL_SUPPORT_ENABLED": "true", "STYL_SUPPORT_ENVIRONMENT": "test",
                "STYL_SUPPORT_PROVIDER": "mock", "STYL_SUPPORT_MODEL": "mock",
                "STYL_SUPPORT_DB": str(self.root / "support.sqlite3"),
                "STYL_ANALYTICS_DB": str(self.root / "analytics.sqlite3"),
                "STYL_ANALYTICS_ENVIRONMENT": "test", "STYL_KNOWLEDGE_DIR": str(self.root / "knowledge"),
                "STYL_RECORDS_DIR": str(self.root / "records"), "STYL_WEBSITE_LOG_DIR": "",
            }),
            patch.multiple(main, DATA_PATH=products, ACCESSORIES_PATH=accessories,
                           INQUIRIES_PATH=self.root / "inquiries", ADMIN_TOKEN="contact-records-test-only"),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        with analytics.get_store().connection():
            pass
        with support.rate_lock:
            support.rate_windows.clear()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.admin = {"Authorization": "Bearer contact-records-test-only"}
        created = self.client.post("/api/support/conversations", json={}).json()
        self.identifier = created["conversation"]["id"]
        self.url = "/api/support/conversations/" + self.identifier
        self.admin_url = "/api/admin/support/conversations/" + self.identifier
        self.guest = {"Authorization": "Bearer " + created["token"]}
        saved = self.client.put(self.url + "/contact", headers=self.guest, json={
            "name": "Synthetic Contact", "email": "synthetic-contact@example.com", "expectedRevision": 0,
        })
        self.assertEqual(saved.status_code, 200, saved.text)

    def close(self) -> None:
        thread = self.client.get(self.admin_url, headers=self.admin).json()
        response = self.client.post(self.admin_url + "/action", headers=self.admin,
                                    json={"action": "close", "expectedRevision": thread["revision"]})
        self.assertEqual(response.status_code, 200, response.text)

    def verified_backup(self) -> tuple[dict, bytes]:
        created = self.client.post("/api/admin/records/archives", headers=self.admin)
        self.assertEqual(created.status_code, 201, created.text)
        archive = created.json()
        downloaded = self.client.get(f"/api/admin/records/archives/{archive['id']}/download", headers=self.admin)
        self.assertEqual(downloaded.status_code, 200)
        verified = self.client.post(f"/api/admin/records/archives/{archive['id']}/verify",
                                    headers=self.admin, content=downloaded.content)
        self.assertEqual(verified.status_code, 200, verified.text)
        return archive, downloaded.content

    def remove(self, archive: dict):
        return self.client.post(f"/api/admin/records/archives/{archive['id']}/remove", headers=self.admin,
                                json={"confirmation": "REMOVE " + archive["id"], "categories": ["support"]})

    def test_contact_is_separate_from_transcripts_jobs_and_restores_from_private_backup(self) -> None:
        sent = self.client.post(self.url + "/messages", headers=self.guest,
                                json={"clientMessageId": "safe-question", "text": "What is the price of STYL Synthetic Bench?"})
        self.assertEqual(sent.status_code, 200)
        self.assertTrue(asyncio.run(support.process_one()))
        with support.get_store().connection() as database:
            for table, fields in (("messages", "text,response_json"), ("jobs", "payload")):
                contents = str([tuple(row) for row in database.execute(f"SELECT {fields} FROM {table}")])
                self.assertNotIn("Synthetic Contact", contents)
                self.assertNotIn("synthetic-contact@example.com", contents)
        archive, contents = self.verified_backup()
        path = self.root / "downloaded.zip"
        path.write_bytes(contents)
        destination = self.root / "restored"
        records_archive.restore_archive(path, destination)
        with closing(sqlite3.connect(destination / "support.sqlite3")) as database:
            self.assertEqual(database.execute("SELECT name,email FROM conversation_contacts").fetchone(),
                             ("Synthetic Contact", "synthetic-contact@example.com"))
        self.assertIsNotNone(archive["id"])

    def test_closed_contact_cascades_only_with_unchanged_verified_thread(self) -> None:
        self.close()
        archive, _contents = self.verified_backup()
        response = self.remove(archive)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["removal"]["supportConversations"], 1)
        with support.get_store().connection() as database:
            self.assertEqual(database.execute("SELECT count(*) FROM conversation_contacts").fetchone()[0], 0)

    def test_contact_changed_after_snapshot_preserves_the_entire_thread(self) -> None:
        self.close()
        archive, _contents = self.verified_backup()
        with support.get_store().connection() as database:
            database.execute("UPDATE conversation_contacts SET email='changed@example.com',revision=revision+1 WHERE conversation_id=?", (self.identifier,))
        response = self.remove(archive)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["removal"]["supportConversations"], 0)
        with support.get_store().connection() as database:
            self.assertEqual(database.execute("SELECT email FROM conversation_contacts").fetchone()[0], "changed@example.com")


if __name__ == "__main__":
    unittest.main()
