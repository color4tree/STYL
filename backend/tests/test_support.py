"""CS-001..020 / SUP-022: private support, question replies, contact capture and fenced AI jobs."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import main, support, support_ai


class SupportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[2] / ".styl-runtime" / ("support-test-" + uuid4().hex)
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.products = [{
            "id": 1, "slug": "synthetic-rack", "name": "Synthetic rack", "category": "Racks",
            "description": "Synthetic fixture", "features": ["Steel"], "publicationStatus": "published",
            "prices": {"CAD": 120, "USD": 90}, "msrps": {"CAD": 140, "USD": 110},
            "currency": "CAD", "price": 120, "sellingUnit": "each", "packageQuantity": 1,
            "specifications": {"material": "Steel", "weight": "30 kg"},
            "provenance": {"internalNotes": "PRIVATE_SYNTHETIC_NOTE"},
        }, {
            "id": 2, "slug": "synthetic-draft", "name": "PRIVATE_SYNTHETIC_DRAFT", "category": "Racks",
            "publicationStatus": "draft", "prices": {"CAD": 45, "USD": 40},
        }, {
            "id": 3, "slug": "synthetic-canada", "name": "Synthetic Canada", "category": "Racks",
            "publicationStatus": "published", "prices": {"CAD": 20, "USD": None},
        }]
        self.accessories = [{
            "id": 1001, "name": "Synthetic handle", "category": "Handle",
            "description": "Synthetic handle fixture", "prices": {"CAD": 12, "USD": 9},
            "publicationStatus": "published", "price": 12, "currency": "CAD",
            "compatibility": "Synthetic rack only", "provenance": {"notes": "PRIVATE_SYNTHETIC_NOTE"},
        }]
        self.market = {"countryCode": "US", "currency": "USD", "locationStatus": "located"}
        self.answer = SimpleNamespace(
            text="Synthetic rack costs USD 90.", references=("product:1",), needs_human=False,
            reason=None, topic="pricing", usage={"input_tokens": 5, "output_tokens": 8, "total_tokens": 13},
        )
        self.real_respond = support_ai.respond
        self.provider = AsyncMock(return_value=self.answer)
        for replacement in (
            patch.dict(os.environ, {
                "STYL_SUPPORT_ENABLED": "true", "STYL_SUPPORT_ENVIRONMENT": "test",
                "STYL_SUPPORT_PROVIDER": "mock", "STYL_SUPPORT_MODEL": "synthetic-model",
                "STYL_SUPPORT_DB": str(self.root / "support.sqlite3"),
                "STYL_SUPPORT_CREATE_LIMIT": "10",
                "STYL_ANALYTICS_DB": str(self.root / "analytics.sqlite3"),
            }),
            patch.object(main, "ADMIN_TOKEN", "support-test-admin"),
            patch.object(main, "load_products", side_effect=lambda: deepcopy(self.products)),
            patch.object(main, "load_accessories", side_effect=lambda: deepcopy(self.accessories)),
            patch.object(main, "resolve_market", side_effect=lambda request: dict(self.market)),
            patch.object(support_ai, "respond", self.provider),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        support.rate_windows.clear()
        self.addCleanup(support.rate_windows.clear)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.admin = {"Authorization": "Bearer support-test-admin"}
        self.base = "/api/support/conversations"
        self.admin_base = "/api/admin/support/conversations"

    def create(self) -> tuple[dict, dict[str, str]]:
        result = self.client.post(self.base, json={})
        self.assertEqual(result.status_code, 201, result.text)
        self.assertEqual(result.headers["cache-control"], "private, no-store")
        data = result.json()
        return data["conversation"], {"Authorization": "Bearer " + data["token"]}

    def send(self, conversation: dict, headers: dict, text: str = "What is the synthetic rack price?",
             client_id: str = "message-1", item_ref: str | None = "product:1"):
        body = {"clientMessageId": client_id, "text": text}
        if item_ref is not None:
            body["itemRef"] = item_ref
        return self.client.post(f"{self.base}/{conversation['id']}/messages", headers=headers, json=body)

    def get(self, conversation: dict, headers: dict) -> dict:
        result = self.client.get(f"{self.base}/{conversation['id']}", headers=headers)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def contact(self, conversation: dict, headers: dict, revision: int = 0,
                name: str = "Synthetic Customer", email: str = "synthetic@example.com"):
        return self.client.put(f"{self.base}/{conversation['id']}/contact", headers=headers, json={
            "name": name, "email": email, "expectedRevision": revision,
        })

    def action(self, conversation: dict, action: str):
        return self.client.post(f"{self.admin_base}/{conversation['id']}/action", headers=self.admin,
                                json={"action": action, "expectedRevision": conversation["revision"]})

    def reply(self, conversation: dict, target: str | None, text: str = "Synthetic team response",
              client_id: str = "human-1"):
        return self.client.post(f"{self.admin_base}/{conversation['id']}/messages", headers=self.admin, json={
            "text": text, "clientMessageId": client_id, "expectedRevision": conversation["revision"],
            "replyToMessageId": target,
            "expectedAnsweredBy": next((message.get("answeredBy") for message in conversation["messages"]
                                        if message["id"] == target), None),
        })

    def assert_private_reason(self, conversation: dict, expected: str | None) -> None:
        self.assertIsNone(conversation["reason"])
        result = self.client.get(f"{self.admin_base}/{conversation['id']}", headers=self.admin)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()["reason"], expected)
        inbox = self.client.get(self.admin_base, headers=self.admin).json()
        summary = next(item for item in inbox["items"] if item["id"] == conversation["id"])
        self.assertEqual(summary["reason"], expected)

    def settings(self) -> dict:
        result = self.client.get("/api/admin/support/config", headers=self.admin)
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def save_settings(self, enabled: bool, topics=None, revision=None):
        return self.client.put("/api/admin/support/config", headers=self.admin, json={
            "enabled": enabled, "allowedTopics": topics if topics is not None else list(support.TOPICS),
            "expectedRevision": self.settings()["revision"] if revision is None else revision,
        })

    def process(self) -> bool:
        return asyncio.run(support.process_one())

    def legacy_database(self) -> tuple[dict, dict[str, str], dict]:
        """Seed the pre-question-tracking schema, never the valuable local database."""
        identifier, empty_id, token = uuid4().hex, uuid4().hex, "a" * 43
        body = support.MessageInput(clientMessageId="legacy-message", text="First failed question")
        first_id, second_id, human_id = uuid4().hex, uuid4().hex, uuid4().hex
        timestamp = support.now()
        conversation = {
            "id": identifier, "state": "human", "revision": 7, "createdAt": timestamp,
            "updatedAt": timestamp, "currency": "USD", "needsHuman": True,
            "reason": "provider_unavailable", "processing": False,
            "messages": [{"id": first_id, "role": "customer", "text": body.text,
                          "createdAt": timestamp, "references": []}],
        }
        with closing(sqlite3.connect(support.configured_path())) as db:
            db.executescript("""
                CREATE TABLE settings(id INTEGER PRIMARY KEY,enabled INTEGER NOT NULL,
                    allowed_topics TEXT NOT NULL,revision INTEGER NOT NULL,environment TEXT NOT NULL);
                CREATE TABLE conversations(id TEXT PRIMARY KEY,token_hash TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,revision INTEGER NOT NULL,generation INTEGER NOT NULL,
                    created_at TEXT NOT NULL,updated_at TEXT NOT NULL,currency TEXT NOT NULL,
                    needs_human INTEGER NOT NULL,reason TEXT);
                CREATE TABLE messages(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL
                    REFERENCES conversations(id) ON DELETE CASCADE,role TEXT NOT NULL,text TEXT NOT NULL,
                    created_at TEXT NOT NULL,references_json TEXT NOT NULL,client_message_id TEXT,
                    request_hash TEXT,response_json TEXT,UNIQUE(conversation_id,role,client_message_id));
                CREATE TABLE jobs(id TEXT PRIMARY KEY,conversation_id TEXT NOT NULL
                    REFERENCES conversations(id) ON DELETE CASCADE,message_id TEXT NOT NULL
                    REFERENCES messages(id) ON DELETE CASCADE,generation INTEGER NOT NULL,
                    settings_revision INTEGER NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,
                    usage_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
            """)
            db.execute("INSERT INTO settings VALUES(1,1,?,0,'test')", (json.dumps(support.TOPICS),))
            db.execute("INSERT INTO conversations VALUES(?,?,?,?,?,?,?,?,?,?)", (
                identifier, hashlib.sha256(token.encode()).hexdigest(), "human", 7, 4,
                timestamp, timestamp, "USD", 1, "provider_unavailable",
            ))
            db.execute("INSERT INTO conversations VALUES(?,?,?,?,?,?,?,?,?,?)", (
                empty_id, hashlib.sha256(b"empty-synthetic-token").hexdigest(), "waiting_human", 2, 0,
                timestamp, timestamp, "USD", 1, "customer_request",
            ))
            for message_id, role, text in (
                (first_id, "customer", body.text), (second_id, "customer", "Second interrupted question"),
                (human_id, "human", "Legacy reply without a target"),
            ):
                db.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?,?,?)", (
                    message_id, identifier, role, text, timestamp, "[]",
                    body.clientMessageId if message_id == first_id else None,
                    support._fingerprint(body) if message_id == first_id else None,
                    json.dumps(conversation) if message_id == first_id else None,
                ))
            for message_id, status in ((first_id, "failed"), (second_id, "interrupted")):
                db.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)", (
                    uuid4().hex, identifier, message_id, 4, 0, status, '{"legacy":"payload"}',
                    '{"total_tokens":3}', timestamp, timestamp,
                ))
            original = {
                "messages": db.execute("SELECT * FROM messages ORDER BY rowid").fetchall(),
                "conversations": db.execute("SELECT * FROM conversations ORDER BY rowid").fetchall(),
                "jobs": db.execute("SELECT * FROM jobs ORDER BY rowid").fetchall(),
                "receipt": json.dumps(conversation), "body": body,
                "empty_id": empty_id, "first_id": first_id, "second_id": second_id, "human_id": human_id,
            }
            db.commit()
        return conversation, {"Authorization": "Bearer " + token}, original

    def test_default_flag_and_local_pilot_gate_do_not_create_storage(self) -> None:
        with patch.dict(os.environ, {"STYL_SUPPORT_ENABLED": "false"}):
            config = self.client.get("/api/support/config")
            self.assertFalse(config.json()["enabled"])
            self.assertFalse(config.json()["aiEnabled"])
            self.assertTrue(config.json()["localTestingOnly"])
            self.assertIn("synthetic", config.json()["notice"])
            self.assertEqual(self.client.post(self.base, json={}).status_code, 404)
            self.assertFalse(support.configured_path().exists())
        with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "production", "STYL_SUPPORT_PROVIDER": "gemini"}):
            self.assertFalse(self.client.get("/api/support/config").json()["enabled"])
            self.assertEqual(self.client.post(self.base, json={}).status_code, 404)
            self.assertFalse(self.process())
        self.provider.assert_not_called()

    def test_guest_tokens_are_isolated_hashed_and_never_returned_after_creation(self) -> None:
        first, first_headers = self.create()
        second, second_headers = self.create()
        for headers in ({}, second_headers, self.admin, {"Authorization": "Bearer wrong"}):
            for method, suffix, body in (
                ("GET", "", None), ("POST", "/messages", {"clientMessageId": "x", "text": "Synthetic"}),
                ("POST", "/handoff", {}),
            ):
                result = self.client.request(method, f"{self.base}/{first['id']}{suffix}", headers=headers, json=body)
                self.assertEqual(result.status_code, 404, result.text)
                self.assertIn("no-store", result.headers["cache-control"])
        self.send(first, first_headers)
        self.assertEqual(len(self.get(second, second_headers)["messages"]), 0)
        token = first_headers["Authorization"][7:]
        with support.get_store().connection() as db:
            row = db.execute("SELECT token_hash FROM conversations WHERE id=?", (first["id"],)).fetchone()
            self.assertEqual(row[0], hashlib.sha256(token.encode()).hexdigest())
            dump = "\n".join(db.iterdump())
            self.assertNotIn(token, dump)
            self.assertNotIn("testclient", dump)
        returned = json.dumps(self.get(first, first_headers))
        self.assertNotIn(token, returned)
        self.assertNotIn("token_hash", returned)
        self.assertNotIn("payload", returned)
        self.assertNotIn("request_hash", returned)

    def test_contact_save_update_and_lost_ack_retry_have_independent_revisions(self) -> None:
        conversation, headers = self.create()
        self.assertIsNone(conversation["contact"])
        saved = self.contact(conversation, headers, name="  合成 Customer  ", email=" synthetic@EXAMPLE.com ")
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.headers["cache-control"], "private, no-store")
        first = saved.json()
        self.assertEqual(first["messages"], [])
        self.assertEqual(first["revision"], 1)
        self.assertEqual(first["contact"], {
            "name": "合成 Customer", "email": "synthetic@example.com", "revision": 1,
            "updatedAt": first["updatedAt"],
        })
        self.assertEqual(self.contact(conversation, headers, name="合成 Customer").json(), first)
        self.assertEqual(self.contact(conversation, headers, revision=1, name="合成 Customer").json(), first)
        self.assertEqual(self.contact(conversation, headers, name="Different").status_code, 409)
        pending = self.send(conversation, headers).json()
        self.assertGreater(pending["revision"], first["revision"])
        changed = self.contact(conversation, headers, revision=1, name="Updated Customer")
        self.assertEqual(changed.status_code, 200, changed.text)
        current = changed.json()
        self.assertEqual(current["contact"]["revision"], 2)
        self.assertEqual(current["revision"], pending["revision"] + 1)
        self.assertTrue(current["processing"])
        self.assertEqual(current["messages"], pending["messages"])
        self.assertEqual(self.contact(conversation, headers, revision=1, name="Updated Customer").json(), current)
        self.assertEqual(self.contact(conversation, headers, revision=0, name="Updated Customer").status_code, 409)
        with support.get_store().connection() as db:
            self.assertEqual(db.execute("SELECT generation FROM conversations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT status FROM jobs").fetchone()[0], "queued")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM conversation_contacts").fetchone()[0], 1)
        self.assertTrue(self.process())
        self.assertEqual(self.get(conversation, headers)["contact"], current["contact"])

    def test_contact_concurrent_same_body_is_idempotent_and_different_body_conflicts(self) -> None:
        conversation, headers = self.create()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.contact(conversation, headers), range(2)))
        self.assertEqual([result.status_code for result in results], [200, 200])
        self.assertEqual(results[0].json(), results[1].json())
        with ThreadPoolExecutor(max_workers=2) as executor:
            changed = list(executor.map(
                lambda name: self.contact(conversation, headers, revision=1, name=name),
                ["Synthetic First", "Synthetic Second"],
            ))
        self.assertEqual(sorted(result.status_code for result in changed), [200, 409])
        current = self.get(conversation, headers)
        self.assertEqual(current["contact"]["revision"], 2)
        self.assertEqual(current["revision"], 2)

    def test_contact_auth_origin_feature_gate_and_admin_projection(self) -> None:
        conversation, headers = self.create()
        other, other_headers = self.create()
        for denied in ({}, other_headers, self.admin, {"Authorization": "Bearer invalid"}):
            result = self.contact(conversation, denied)
            self.assertEqual(result.status_code, 404, result.text)
            self.assertEqual(result.headers["cache-control"], "private, no-store")
        for origin in ("https://untrusted.example", "null"):
            result = self.contact(conversation, {**headers, "Origin": origin})
            self.assertEqual(result.status_code, 403, result.text)
            self.assertEqual(result.headers["cache-control"], "private, no-store")
        with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "production"}):
            self.assertEqual(self.contact(conversation, headers).status_code, 404)
        with patch.dict(os.environ, {"STYL_SUPPORT_ENABLED": "false"}):
            self.assertEqual(self.contact(conversation, headers).status_code, 404)
        saved = self.contact(conversation, {**headers, "Origin": "http://testserver"}).json()
        self.assertEqual(self.get(conversation, headers)["contact"], saved["contact"])
        self.assertIsNone(self.get(other, other_headers)["contact"])
        selected = self.client.get(f"{self.admin_base}/{conversation['id']}", headers=self.admin)
        self.assertEqual(selected.headers["cache-control"], "private, no-store")
        self.assertEqual(selected.json()["contact"], saved["contact"])
        inbox = self.client.get(self.admin_base, headers=self.admin)
        self.assertEqual(inbox.headers["cache-control"], "private, no-store")
        row = next(item for item in inbox.json()["items"] if item["id"] == conversation["id"])
        self.assertEqual(row["contactName"], "Synthetic Customer")
        self.assertNotIn("synthetic@example.com", inbox.text)
        self.assertEqual(self.client.get(f"{self.admin_base}/{conversation['id']}").status_code, 401)
        self.assertEqual(self.client.get(self.admin_base).status_code, 401)

    def test_contact_strict_validation_never_echoes_inputs_or_overwrites_saved_values(self) -> None:
        conversation, headers = self.create()
        first = self.contact(conversation, headers).json()
        valid = {"name": "PRIVATE_SYNTHETIC_NAME", "email": "private-synthetic@example.com", "expectedRevision": 1}
        invalid = [
            {"name": ""}, {"name": "   "}, {"name": "X" * 121}, {"name": "Synthetic\x00Name"},
            {"name": "Synthetic\nName"}, {"name": "Synthetic\tName"}, {"name": "Synthetic\x7fName"},
            {"name": "Synthetic\u0085Name"}, {"name": 5}, {"name": None},
            {"email": "not-an-address"}, {"email": "a@example.com,b@example.com"},
            {"email": "Name <a@example.com>"}, {"email": "a@example.com\nBcc: b@example.com"},
            {"email": "a@example.com;b@example.com"}, {"email": "a @example.com"},
            {"email": ["a@example.com"]}, {"email": None}, {"email": 5}, {"email": "a" * 255},
            {"expectedRevision": -1}, {"expectedRevision": "1"}, {"expectedRevision": True},
            {"expectedRevision": 1.0}, {"unexpected": "PRIVATE_EXTRA"},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                with self.assertNoLogs("app.support"):
                    result = self.client.put(f"{self.base}/{conversation['id']}/contact",
                                             headers=headers, json={**valid, **changes})
                self.assertEqual(result.status_code, 422, result.text)
                self.assertEqual(result.headers["cache-control"], "private, no-store")
                self.assertEqual(result.json(), {
                    "detail": "Invalid support request. Check the fields and message length.",
                })
        self.assertEqual(self.get(conversation, headers), first)
        email = "a" * 64 + "@" + ".".join(("b" * 63, "c" * 63, "d" * 57, "com"))
        self.assertEqual(len(email), 254)
        accepted = self.contact(conversation, headers, revision=1, name="合" * 120, email=email)
        self.assertEqual(accepted.status_code, 200, accepted.text)
        self.assertEqual(accepted.json()["contact"]["email"], email)
        self.assertEqual(self.contact(conversation, headers, revision=2, email=email + "x").status_code, 422)
        for body in ({}, {"name": "Synthetic"}, {"name": "Synthetic", "email": "a@example.com"}):
            self.assertEqual(self.client.put(f"{self.base}/{conversation['id']}/contact",
                                             headers=headers, json=body).status_code, 422)

    def test_contact_never_enters_messages_receipts_quotes_jobs_provider_analytics_or_email(self) -> None:
        conversation, headers = self.create()
        missing = self.send(conversation, headers, text="A synthetic unanswered question",
                            item_ref="product:999").json()
        with patch.object(main, "send_inquiry_email") as inquiry_mail, \
                patch.object(main.smtplib, "SMTP") as smtp, patch.object(main.smtplib, "SMTP_SSL") as smtp_ssl:
            with self.assertNoLogs("app.support"):
                saved = self.contact(conversation, headers, name="PRIVATE_CONTACT_MARKER",
                                     email="private-contact-marker@example.com").json()
                self.assertTrue(saved["needsHuman"])
                self.assertEqual(saved["messages"], missing["messages"])
                answered = self.reply(saved, saved["messages"][0]["id"]).json()
                self.assertFalse(answered["needsHuman"])
                self.assertEqual(answered["contact"], saved["contact"])
                self.assertEqual(self.reply(saved, saved["messages"][0]["id"]).json(), answered)
                sent = self.send(conversation, headers, client_id="after-contact").json()
                self.assertEqual(sent["contact"], saved["contact"])
                self.assertEqual(self.send(conversation, headers, client_id="after-contact").json(), sent)
                self.assertTrue(self.process())
                self.assertEqual(self.contact(conversation, headers, revision=1, name="Updated contact").status_code, 200)
            inquiry_mail.assert_not_called()
            smtp.assert_not_called()
            smtp_ssl.assert_not_called()
        serialized_provider = json.dumps(self.provider.call_args.kwargs)
        self.assertNotIn("PRIVATE_CONTACT_MARKER", serialized_provider)
        self.assertNotIn("private-contact-marker@example.com", serialized_provider)
        current = self.get(conversation, headers)
        self.assertEqual(current["messages"][2]["replyTo"]["text"], "A synthetic unanswered question")
        for marker in ("PRIVATE_CONTACT_MARKER", "private-contact-marker@example.com", "Updated contact"):
            self.assertNotIn(marker, json.dumps(current["messages"]))
        with support.get_store().connection() as db:
            for table in ("messages", "jobs", "conversations", "settings"):
                rows = json.dumps([dict(row) for row in db.execute(f"SELECT * FROM {table}")])
                for marker in ("PRIVATE_CONTACT_MARKER", "private-contact-marker@example.com", "Updated contact"):
                    self.assertNotIn(marker, rows)
        self.assertFalse((self.root / "analytics.sqlite3").exists())

    def test_contact_save_during_running_ai_does_not_fence_or_cancel_reply(self) -> None:
        async def scenario():
            conversation, headers = self.create()
            self.send(conversation, headers)
            started, release = asyncio.Event(), asyncio.Event()

            async def delayed(**kwargs):
                started.set()
                await release.wait()
                return self.answer

            self.provider.side_effect = delayed
            worker = asyncio.create_task(support.process_one())
            try:
                await asyncio.wait_for(started.wait(), 2)
                saved = self.contact(conversation, headers).json()
                self.assertTrue(saved["processing"])
                with support.get_store().connection() as db:
                    self.assertEqual(db.execute("SELECT generation FROM conversations").fetchone()[0], 1)
                    self.assertEqual(db.execute("SELECT status FROM jobs").fetchone()[0], "running")
                release.set()
                self.assertTrue(await worker)
                current = self.get(conversation, headers)
                self.assertEqual(current["messages"][-1]["role"], "assistant")
                self.assertEqual(current["contact"], saved["contact"])
            finally:
                release.set()
                await worker

        asyncio.run(scenario())

    def test_contact_commit_failure_is_private_atomic_and_retryable(self) -> None:
        conversation, headers = self.create()
        connect = sqlite3.connect

        class CommitFailure(sqlite3.Connection):
            def __exit__(self, *args):
                self.rollback()
                raise sqlite3.OperationalError("PRIVATE_CONTACT_MARKER private-contact-marker@example.com")

        with patch.object(support.sqlite3, "connect", side_effect=lambda *args, **kwargs: connect(
            *args, **kwargs, factory=CommitFailure
        )):
            with self.assertLogs("app.support", level="WARNING") as logged:
                result = self.contact(conversation, headers, name="PRIVATE_CONTACT_MARKER",
                                      email="private-contact-marker@example.com")
        self.assertEqual(result.status_code, 503, result.text)
        self.assertEqual(result.headers["cache-control"], "private, no-store")
        self.assertNotIn("PRIVATE_CONTACT_MARKER", result.text + " ".join(logged.output))
        self.assertNotIn("private-contact-marker@example.com", result.text + " ".join(logged.output))
        self.assertEqual(self.get(conversation, headers), conversation)
        saved = self.contact(conversation, headers)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["contact"]["revision"], 1)
        with patch.object(support.sqlite3, "connect", side_effect=lambda *args, **kwargs: connect(
            *args, **kwargs, factory=CommitFailure
        )):
            with self.assertLogs("app.support", level="WARNING"):
                result = self.contact(conversation, headers, revision=1, name="Replacement")
        self.assertEqual(result.status_code, 503)
        self.assertEqual(self.get(conversation, headers), saved.json())

    def test_contact_closed_threads_reject_updates_and_retries_without_age_expiry(self) -> None:
        conversation, headers = self.create()
        saved = self.contact(conversation, headers).json()
        with support.get_store().connection() as db:
            db.execute("UPDATE conversations SET created_at='2000-01-01T00:00:00+00:00'")
            db.execute("UPDATE conversation_contacts SET updated_at='2000-01-01T00:00:00+00:00'")
        self.assertEqual(self.get(conversation, headers)["contact"]["name"], "Synthetic Customer")
        changed = self.contact(conversation, headers, revision=1, name="Updated Customer").json()
        closed = self.action(changed, "close").json()
        self.assertEqual(closed["contact"], changed["contact"])
        for revision in (1, 2):
            result = self.contact(conversation, headers, revision=revision, name="Updated Customer")
            self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(self.get(conversation, headers), closed)
        with support.get_store().connection() as db:
            db.execute("DELETE FROM conversations WHERE id=?", (saved["id"],))
        with support.get_store().connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM conversation_contacts").fetchone()[0], 0)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_contact_scoped_rate_caps_and_global_rotating_address_cap_are_bounded(self) -> None:
        first, headers = self.create()
        for revision in range(10):
            result = self.contact(first, headers, revision=revision, name=f"Synthetic {revision}")
            self.assertEqual(result.status_code, 200, result.text)
        denied = self.contact(first, headers, revision=10, name="Over thread cap")
        self.assertEqual(denied.status_code, 429)
        self.assertEqual(denied.headers["cache-control"], "private, no-store")
        self.assertIn("retry-after", denied.headers)
        self.assertEqual(self.contact(first, headers, revision=9, name="Synthetic 9").status_code, 200)
        second, second_headers = self.create()
        self.assertEqual(self.contact(second, second_headers).status_code, 200)
        self.assertEqual(self.send(first, headers).status_code, 200)
        support.rate_windows.clear()
        for number in range(200):
            request = support.Request({"type": "http", "client": (f"synthetic-address-{number}", 80)})
            support._limit(request, "contact-global", 200, scope="global")
        result = self.contact(second, second_headers, revision=1, name="Changed synthetic")
        self.assertEqual(result.status_code, 429)
        self.assertEqual(self.get(second, second_headers)["contact"]["revision"], 1)
        self.assertLessEqual(len(support.rate_windows), 2048)
        self.assertTrue(all(re.fullmatch(r"[a-f0-9]{64}", key) for key in support.rate_windows))
        self.assertEqual(self.send(second, second_headers).status_code, 200)
        support.rate_windows.clear()
        request = support.Request({"type": "http", "client": ("testclient", 80)})
        for _ in range(30):
            support._limit(request, "contact", 30)
        result = self.contact(second, second_headers, revision=1, name="Changed synthetic")
        self.assertEqual(result.status_code, 429)
        self.assertEqual(self.get(second, second_headers)["contact"]["revision"], 1)

    def test_contact_survives_cold_restart_and_sqlite_backup_restore_with_quotes_unchanged(self) -> None:
        conversation, headers = self.create()
        pending = self.send(conversation, headers, item_ref="product:999").json()
        replied = self.reply(pending, pending["messages"][0]["id"]).json()
        saved = self.contact(conversation, headers).json()
        backup = self.root / "backup.sqlite3"
        restored = self.root / "restored.sqlite3"
        with closing(sqlite3.connect(support.configured_path())) as source, \
                closing(sqlite3.connect(backup)) as target:
            source.backup(target)
        shutil.copyfile(backup, restored)
        support.rate_windows.clear()
        with patch.dict(os.environ, {"STYL_SUPPORT_DB": str(restored)}):
            current = self.get(conversation, headers)
            self.assertEqual(current, saved)
            self.assertEqual(current["messages"], replied["messages"])
            self.assertEqual(self.contact(conversation, headers).json(), saved)
            with support.get_store().connection() as db:
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], support.SCHEMA_VERSION)

    def test_contact_v1_migration_preserves_resolved_flags_quotes_receipts_and_jobs(self) -> None:
        conversation, headers = self.create()
        self.send(conversation, headers)
        self.provider.side_effect = RuntimeError("Synthetic provider failure")
        self.process()
        failed = self.get(conversation, headers)
        answered = self.reply(failed, failed["messages"][0]["id"]).json()
        with support.get_store().connection() as db:
            # This v1 resolved state must not be reconsidered by the v0 backfill.
            db.execute("UPDATE messages SET answered_by_id=NULL WHERE role='customer'")
            db.execute("DROP TABLE conversation_contacts")
            db.execute("PRAGMA user_version=1")
            original = {table: [dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")]
                        for table in ("settings", "conversations", "messages", "jobs")}
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: self.get(conversation, headers), range(4)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertFalse(results[0]["needsHuman"])
        self.assertEqual(results[0]["needsHumanQuestions"], 0)
        self.assertIsNone(results[0]["contact"])
        self.assertEqual(results[0]["messages"][-1]["replyTo"], answered["messages"][-1]["replyTo"])
        with support.get_store().connection() as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], support.SCHEMA_VERSION)
            for table, rows in original.items():
                self.assertEqual([dict(row) for row in db.execute(f"SELECT * FROM {table} ORDER BY rowid")], rows)
        self.assertEqual(self.contact(conversation, headers).status_code, 200)

    def test_invalid_path_guards_and_admin_auth_matrix(self) -> None:
        identifier = "a" * 32
        for method, path, body in (
            ("GET", "/api/admin/support/config", None),
            ("PUT", "/api/admin/support/config", {"enabled": False, "allowedTopics": ["products"], "expectedRevision": 0}),
            ("GET", self.admin_base, None), ("GET", f"{self.admin_base}/{identifier}", None),
            ("POST", f"{self.admin_base}/{identifier}/action", {"action": "close", "expectedRevision": 0}),
            ("POST", f"{self.admin_base}/{identifier}/messages",
             {"text": "Synthetic", "clientMessageId": "test", "expectedRevision": 0}),
        ):
            for headers in ({}, {"Authorization": "Bearer wrong"}):
                self.assertEqual(self.client.request(method, path, headers=headers, json=body).status_code, 401)
        self.assertFalse(support.configured_path().exists())
        for identifier in ("not-an-id", "a" * 33, "ABC123"):
            self.assertEqual(self.client.get(f"{self.base}/{identifier}").status_code, 404)
            self.assertEqual(self.client.get(f"{self.admin_base}/{identifier}", headers=self.admin).status_code, 404)
        self.assertFalse(support.configured_path().exists())

    def test_current_public_market_projection_and_canonical_references(self) -> None:
        conversation, headers = self.create()
        self.assertEqual(conversation["currency"], "USD")
        sent = self.send(conversation, {**headers, "X-Currency": "CAD", "X-Forwarded-For": "203.0.113.2"})
        self.assertEqual(sent.status_code, 200, sent.text)
        self.assertTrue(self.process())
        payload = self.provider.call_args.kwargs
        self.assertEqual([item["ref"] for item in payload["catalog"]], ["product:1", "accessory:1001"])
        self.assertEqual(payload["item_ref"], "product:1")
        self.assertEqual(payload["messages"], [{"role": "user", "text": "What is the synthetic rack price?"}])
        public = main.public_catalog_item(self.products[0], self.market)
        projected = payload["catalog"][0]
        self.assertEqual({key: projected[key] for key in public}, public)
        self.assertEqual(projected["url"], "/products/synthetic-rack")
        self.assertEqual(payload["catalog"][1]["url"], "/accessories/1001")
        for forbidden in ("PRIVATE_SYNTHETIC", '"prices"', '"msrps"', '"provenance"'):
            self.assertNotIn(forbidden, json.dumps(payload))
        result = self.get(conversation, headers)
        self.assertFalse(result["processing"])
        self.assertEqual(result["messages"][-1]["references"], [
            {"type": "product", "id": 1, "url": "/products/synthetic-rack", "label": "Synthetic rack"},
        ])
        self.market.update(currency="CAD", countryCode="CA")
        self.products[0]["prices"]["CAD"] = 135
        self.send(conversation, headers, client_id="next")
        self.process()
        current = self.provider.call_args.kwargs["catalog"]
        self.assertEqual(current[0]["price"], 135)
        self.assertEqual(current[0]["msrp"], 140)
        self.assertEqual(current[0]["currency"], "CAD")
        self.assertEqual(self.get(conversation, headers)["currency"], "CAD")
        self.assertEqual([item["ref"] for item in current], ["product:1", "product:3", "accessory:1001"])

    def test_queued_job_refreshes_prices_before_provider_and_persists_current_evidence(self) -> None:
        conversation, headers = self.create()
        self.send(conversation, headers)
        self.products[0]["prices"]["USD"] = 95

        async def current_answer(**payload):
            answer = deepcopy(self.answer)
            item = next(item for item in payload["catalog"] if item["ref"] == "product:1")
            answer.text = f"Synthetic rack costs {item['currency']} {item['price']}."
            return answer

        self.provider.side_effect = current_answer
        self.process()
        self.assertEqual(self.provider.call_args.kwargs["catalog"][0]["price"], 95)
        result = self.get(conversation, headers)
        self.assertEqual(result["messages"][-1]["text"], "Synthetic rack costs USD 95.0.")
        self.assertEqual(result["state"], "ai")
        with support.get_store().connection() as db:
            evidence = json.loads(db.execute("SELECT payload FROM jobs").fetchone()[0])
            self.assertEqual(evidence["catalog"][0]["price"], 95)

    def test_real_local_greeting_with_products_disabled_needs_no_citations_or_handoff(self) -> None:
        self.assertEqual(self.save_settings(True, ["pricing"]).status_code, 200)
        conversation, headers = self.create()
        self.assertEqual(self.send(conversation, headers, "Hello", item_ref=None).status_code, 200)
        with patch.object(support_ai, "respond", self.real_respond), \
                patch.object(support_ai.MockProvider, "decide", new_callable=AsyncMock) as mock_provider, \
                patch.object(support_ai.GeminiProvider, "decide", new_callable=AsyncMock) as gemini:
            self.assertTrue(self.process())
        mock_provider.assert_not_called()
        gemini.assert_not_called()
        result = self.get(conversation, headers)
        self.assertEqual(result["state"], "ai")
        self.assertFalse(result["needsHuman"])
        self.assertFalse(result["processing"])
        self.assertIsNone(result["reason"])
        answer = result["messages"][-1]
        self.assertEqual(answer["role"], "assistant")
        self.assertEqual(answer["references"], [])
        self.assertEqual(answer["text"],
                         "Hello! I'm the STYL Assistant. How can I help you today?")

    def test_arbitrary_citation_free_provider_text_cannot_use_greeting_exception(self) -> None:
        self.save_settings(True, ["pricing"])
        conversation, headers = self.create()
        self.send(conversation, headers, "Hello", item_ref=None)
        self.answer.references = ()
        self.answer.text = "Every synthetic item is free; no citation is needed."
        self.process()
        result = self.get(conversation, headers)
        self.assertEqual(result["state"], "waiting_human")
        self.assert_private_reason(result, "missing_information")
        self.assertFalse(any(message["role"] == "assistant" for message in result["messages"]))
        self.assertNotIn("Every synthetic item is free", json.dumps(result))

    def test_greeting_text_cannot_bypass_fact_checks_for_nongreeting_question(self) -> None:
        self.save_settings(True, ["pricing"])
        conversation, headers = self.create()
        self.send(conversation, headers, "What is the synthetic rack price?", item_ref=None)
        self.answer.references = ()
        self.answer.text = "Hello! I can help with current market prices. Which item would you like to discuss?"
        self.process()
        result = self.get(conversation, headers)
        self.assertEqual(result["state"], "waiting_human")
        self.assert_private_reason(result, "missing_information")
        self.assertFalse(any(message["role"] == "assistant" for message in result["messages"]))

    def test_queued_item_becoming_draft_or_unpriced_never_reaches_provider(self) -> None:
        original = deepcopy(self.products[0])
        for change in ("draft", "unpriced"):
            with self.subTest(change=change):
                self.products[0] = deepcopy(original)
                conversation, headers = self.create()
                self.send(conversation, headers)
                if change == "draft":
                    self.products[0]["publicationStatus"] = "draft"
                else:
                    self.products[0]["prices"]["USD"] = None
                self.process()
                current = self.get(conversation, headers)
                self.assertEqual(current["state"], "waiting_human")
                self.assert_private_reason(current, "catalog_changed")
                self.assertFalse(current["processing"])
                self.assertFalse(any(message["role"] == "assistant" for message in current["messages"]))
        self.provider.assert_not_called()

    def test_queued_general_question_excludes_newly_drafted_catalog_items(self) -> None:
        conversation, headers = self.create()
        self.send(conversation, headers, "Tell me about the synthetic handle", item_ref=None)
        self.products[0]["publicationStatus"] = "draft"
        self.answer.references = ("accessory:1001",)
        self.answer.text = "Synthetic handle."
        self.answer.topic = "products"
        self.process()
        catalog = self.provider.call_args.kwargs["catalog"]
        self.assertEqual([item["ref"] for item in catalog], ["accessory:1001"])
        self.assertNotIn("/products/synthetic-rack", json.dumps(catalog))
        self.assertEqual(self.get(conversation, headers)["state"], "ai")

    def test_queued_catalog_outage_preserves_message_without_provider_request(self) -> None:
        conversation, headers = self.create()
        self.send(conversation, headers)
        with patch.object(main, "load_products", side_effect=HTTPException(503, "PRIVATE_SYNTHETIC_CATALOG_ERROR")):
            with self.assertLogs("app.support", level="WARNING") as logged:
                self.process()
        self.assertNotIn("PRIVATE_SYNTHETIC_CATALOG_ERROR", " ".join(logged.output))
        result = self.get(conversation, headers)
        self.assert_private_reason(result, "catalog_unavailable")
        self.assertTrue(result["needsHuman"])
        self.assertEqual(result["messages"][0]["role"], "customer")
        self.provider.assert_not_called()

    def test_catalog_changes_during_provider_await_suppress_stale_or_private_answers(self) -> None:
        original = deepcopy(self.products[0])

        async def scenario(change: str) -> None:
            self.products[0] = deepcopy(original)
            conversation, headers = self.create()
            self.send(conversation, headers)
            started, release = asyncio.Event(), asyncio.Event()

            async def delayed(**payload):
                self.assertEqual(payload["catalog"][0]["price"], 90)
                started.set()
                await release.wait()
                return self.answer

            self.provider.side_effect = delayed
            task = asyncio.create_task(support.process_one())
            try:
                await asyncio.wait_for(started.wait(), 2)
                with main.CATALOG_LOCK:
                    if change == "price":
                        self.products[0]["prices"]["USD"] = 95
                    elif change == "description":
                        self.products[0]["description"] = "Updated synthetic dimensions."
                    elif change == "draft":
                        self.products[0]["publicationStatus"] = "draft"
                    elif change == "unpriced":
                        self.products[0]["prices"]["USD"] = None
                if change == "unavailable":
                    with patch.object(main, "load_products", side_effect=OSError("PRIVATE_CATALOG_FAILURE")):
                        release.set()
                        await task
                else:
                    release.set()
                    await task
                result = self.get(conversation, headers)
                self.assertEqual(result["state"], "waiting_human")
                self.assert_private_reason(result, "catalog_unavailable" if change == "unavailable" else "catalog_changed")
                self.assertTrue(result["needsHuman"])
                self.assertFalse(result["processing"])
                self.assertFalse(any(message["role"] == "assistant" for message in result["messages"]))
                self.assertNotIn("USD 90", json.dumps(result))
                self.assertNotIn("PRIVATE_CATALOG_FAILURE", json.dumps(result))
            finally:
                release.set()
                await task

        for change in ("price", "description", "draft", "unpriced", "unavailable"):
            with self.subTest(change=change):
                asyncio.run(scenario(change))
        self.assertEqual(self.provider.await_count, 5)

    def test_message_idempotency_conflicts_and_single_pending_job(self) -> None:
        conversation, headers = self.create()
        original = self.send(conversation, headers)
        self.assertEqual(original.status_code, 200, original.text)
        self.assertEqual(self.send(conversation, headers).json(), original.json())
        self.assertEqual(self.send(conversation, headers, text="Different").status_code, 409)
        self.assertEqual(self.send(conversation, headers, item_ref="accessory:1001").status_code, 409)
        self.assertEqual(self.send(conversation, headers, client_id="overlap").status_code, 409)
        self.assertEqual(len(self.get(conversation, headers)["messages"]), 1)
        self.process()
        self.assertEqual(self.send(conversation, headers).json(), original.json())
        self.assertFalse(self.process())
        self.provider.assert_awaited_once()
        second, second_headers = self.create()
        self.assertEqual(self.send(second, second_headers).status_code, 200)
        self.assertEqual(len(self.get(conversation, headers)["messages"]), 2)

    def test_concurrent_retries_produce_one_message_and_one_job(self) -> None:
        conversation, headers = self.create()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.send(conversation, headers), range(2)))
        self.assertEqual([result.status_code for result in results], [200, 200])
        self.assertEqual(results[0].json(), results[1].json())
        with support.get_store().connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)
        self.process()
        self.provider.assert_awaited_once()

    def test_invalid_input_and_size_limits_preserve_records(self) -> None:
        conversation, headers = self.create()
        for body in (
            {"clientMessageId": "x", "text": ""}, {"clientMessageId": "x", "text": " \n "},
            {"clientMessageId": "x", "text": "x" * 2001}, {"clientMessageId": "", "text": "x"},
            {"clientMessageId": "x", "text": "x", "itemRef": "product:-1"},
            {"clientMessageId": "x", "text": "x", "currency": "CAD"},
            {"clientMessageId": "x", "text": "x", "role": "human"},
            {"clientMessageId": "x", "text": "x", "itemRef": "product:1/../../private"},
        ):
            result = self.client.post(f"{self.base}/{conversation['id']}/messages", headers=headers, json=body)
            self.assertEqual(result.status_code, 422)
            self.assertIn("no-store", result.headers["cache-control"])
            self.assertNotIn('"input"', result.text)
        result = self.client.post(f"{self.base}/{conversation['id']}/messages",
                                  headers=headers, content=b"x" * 16385)
        self.assertEqual(result.status_code, 413)
        self.assertEqual(self.get(conversation, headers)["messages"], [])
        self.assertEqual(self.send(conversation, headers, text="x" * 2000).status_code, 200)

    def test_missing_or_draft_context_and_unavailable_catalog_request_human_help(self) -> None:
        for item_ref in ("product:2", "product:3", "product:999"):
            conversation, headers = self.create()
            result = self.send(conversation, headers, text="What is the price?", item_ref=item_ref)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["state"], "waiting_human")
            self.assert_private_reason(result.json(), "missing_information")
            self.assertTrue(result.json()["needsHuman"])
            self.assertFalse(result.json()["processing"])
        conversation, headers = self.create()
        with patch.object(main, "load_products", side_effect=HTTPException(503, "synthetic catalog error")):
            result = self.send(conversation, headers)
        self.assertEqual(result.status_code, 200)
        self.assert_private_reason(result.json(), "catalog_unavailable")
        self.provider.assert_not_called()

    def test_settings_full_validation_cas_and_disabled_ai_still_saves_messages(self) -> None:
        original = self.settings()
        self.assertEqual(original["allowedTopics"], list(support.TOPICS))
        self.assertIsInstance(original["configured"], bool)
        self.assertEqual((original["provider"], original["model"]), ("mock", "synthetic-model"))
        self.assertNotIn("key", json.dumps(original).lower())
        self.assertEqual(self.save_settings(False, ["products"], original["revision"]).status_code, 200)
        self.assertEqual(self.save_settings(True, revision=original["revision"]).status_code, 409)
        for topics in (["medical"], ["products", "products"], []):
            self.assertEqual(self.save_settings(True, topics).status_code, 422)
        self.assertEqual(self.client.put("/api/admin/support/config", headers=self.admin,
                                        json={"enabled": True, "expectedRevision": 1}).status_code, 422)
        public = self.client.get("/api/support/config").json()
        self.assertTrue(public["enabled"])
        self.assertFalse(public["aiEnabled"])
        self.assertEqual(public["allowedTopics"], ["products"])
        conversation, headers = self.create()
        self.assert_private_reason(conversation, "ai_disabled")
        result = self.send(conversation, headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["state"], "waiting_human")
        self.assertEqual(result.json()["messages"][0]["role"], "customer")
        self.assert_private_reason(result.json(), "ai_disabled")
        self.assertFalse(self.process())
        self.provider.assert_not_called()
        self.assertEqual(self.action(result.json(), "resume_ai").status_code, 422)
        self.assertEqual(self.get(conversation, headers), result.json())
        self.assertEqual(self.save_settings(True).status_code, 200)
        self.assertTrue(self.send(conversation, headers, client_id="enabled-next").json()["processing"])
        self.assertTrue(self.process())
        current = self.get(conversation, headers)
        self.assertEqual(current["state"], "waiting_human")
        self.assertTrue(current["needsHuman"])
        self.assert_private_reason(current, "ai_disabled")
        self.assertEqual(current["messages"][-1]["role"], "assistant")
        self.provider.assert_awaited_once()

    def test_openai_provider_credentials_are_private_and_use_only_its_own_key(self) -> None:
        with patch.dict(os.environ, {
            "STYL_SUPPORT_PROVIDER": "openai", "STYL_SUPPORT_MODEL": "gpt-6-luna",
            "OPENAI_API_KEY": "", "GEMINI_API_KEY": "synthetic-other-provider-key",
        }):
            original = self.settings()
            self.assertEqual((original["provider"], original["model"]), ("openai", "gpt-6-luna"))
            self.assertFalse(original["configured"])
            with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-openai-config-key"}):
                configured = self.settings()
                self.assertTrue(configured["configured"])
                self.assertNotIn("synthetic-openai-config-key", json.dumps(configured))
                public = self.client.get("/api/support/config").json()
                self.assertEqual((public["provider"], public["model"]), ("openai", "gpt-6-luna"))
                self.assertNotIn("configured", public)
                self.assertNotIn("synthetic-openai-config-key", json.dumps(public))
        self.provider.assert_not_called()

    def test_team_reply_is_direct_idempotent_and_followups_keep_ai_without_takeover(self) -> None:
        conversation, headers = self.create()
        original = self.send(conversation, headers).json()
        question = original["messages"][0]
        for action in ("takeover", "resume_ai"):
            self.assertEqual(self.action(original, action).status_code, 422)
        self.assertEqual(self.reply({**original, "revision": original["revision"] + 1}, question["id"]).status_code, 409)
        result = self.reply(original, question["id"])
        self.assertEqual(result.status_code, 200, result.text)
        reply = result.json()
        self.assertEqual(reply["state"], "ai")
        self.assertFalse(reply["processing"])
        self.assertFalse(self.process())
        self.assertFalse(reply["needsHuman"])
        self.assertEqual(reply["needsHumanQuestions"], 0)
        self.assertIsNone(reply["reason"])
        self.assertEqual(reply["messages"][-1]["replyTo"], {"id": question["id"], "text": question["text"]})
        self.assertEqual(reply["messages"][0]["answeredBy"], reply["messages"][-1]["id"])
        self.assertEqual(self.reply(original, question["id"]).json(), reply)
        refreshed = self.get(conversation, headers)
        retry = self.reply(refreshed, question["id"])
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json(), reply)
        self.assertEqual(len([message for message in self.get(conversation, headers)["messages"]
                              if message["role"] == "human"]), 1)
        self.assertEqual(self.client.get(self.admin_base, headers=self.admin).json()["needsHumanCount"], 0)
        customer = self.send(conversation, headers, "Synthetic follow-up", "next").json()
        self.assertFalse(customer["needsHuman"])
        self.assertEqual(customer["state"], "ai")
        self.assertTrue(customer["processing"])
        inbox = self.client.get(self.admin_base, headers=self.admin).json()
        self.assertEqual(inbox["needsHumanCount"], 0)
        self.assertEqual(inbox["items"][0]["lastMessage"], "Synthetic follow-up")
        self.assertTrue(inbox["items"][0]["guestLabel"].startswith("Guest "))
        self.assertTrue(self.process())
        self.assertEqual(self.get(conversation, headers)["messages"][-1]["role"], "assistant")
        queued = self.send(conversation, headers, client_id="after-team").json()
        closed = self.action(queued, "close").json()
        self.assertEqual(closed["state"], "closed")
        self.assertEqual(self.send(closed, headers, client_id="after-close").status_code, 409)
        self.assertEqual(self.action(closed, "close").status_code, 409)
        self.assertEqual(self.reply(closed, question["id"], client_id="after-close").status_code, 409)
        self.assertFalse(self.process())
        self.provider.assert_awaited_once()

    def test_team_reply_requires_explicit_customer_target_and_valid_preconditions(self) -> None:
        conversation, headers = self.create()
        url = f"{self.admin_base}/{conversation['id']}/messages"
        body = {"text": "Synthetic", "clientMessageId": "h-1", "expectedRevision": 0}
        self.assertEqual(self.client.post(url, headers=self.admin, json=body).status_code, 422)
        body["replyToMessageId"] = None
        self.assertEqual(self.client.post(url, headers=self.admin, json=body).status_code, 200)
        body["text"] = "Different synthetic"
        self.assertEqual(self.client.post(url, headers=self.admin, json=body).status_code, 409)
        sent = self.send(conversation, headers).json()
        target = sent["messages"][-1]["id"]
        self.assertEqual(self.reply(sent, None).status_code, 422)
        other, other_headers = self.create()
        other_question = self.send(other, other_headers, "PRIVATE_OTHER_GUEST_QUESTION").json()["messages"][0]
        for invalid in (other_question["id"], uuid4().hex, sent["messages"][0]["id"]):
            result = self.reply(sent, invalid)
            self.assertEqual(result.status_code, 404)
            self.assertNotIn("PRIVATE_OTHER_GUEST_QUESTION", result.text)
        for forged in ({"replyTo": {"id": target, "text": "forged"}}, {"quotedText": "forged"},
                       {"replyToMessageId": 123}, {"replyToMessageId": ""}, {"itemRef": "product:1"},
                       {"expectedAnsweredBy": 123}, {"expectedAnsweredBy": "invalid"}):
            result = self.client.post(url, headers=self.admin, json={
                "text": "Synthetic", "clientMessageId": "human-1", "expectedRevision": sent["revision"],
                "replyToMessageId": target, **forged,
            })
            self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual(self.get(conversation, headers), sent)
        self.assertEqual(self.reply(sent, target).status_code, 200)
        current = self.get(conversation, headers)
        self.assertEqual(self.reply(current, other_question["id"]).status_code, 409)
        self.save_settings(False)
        disabled = self.send(conversation, headers, client_id="disabled-question").json()
        self.assertFalse(disabled["processing"])
        self.assertEqual(self.reply(disabled, disabled["messages"][-2]["id"], client_id="disabled-reply").status_code, 200)
        self.assertFalse(self.process())
        self.provider.assert_not_called()

    def test_question_precondition_allows_unrelated_activity_but_rejects_competing_answers(self) -> None:
        conversation, headers = self.create()
        draft = self.send(conversation, headers, "Older question for the team",
                          item_ref="product:999").json()
        target = draft["messages"][0]["id"]
        queued = self.send(conversation, headers, "Newer price question", client_id="newer-question").json()
        newer_target = queued["messages"][-1]["id"]
        self.assertTrue(self.process())
        current = self.get(conversation, headers)
        self.assertGreater(current["revision"], draft["revision"])
        result = self.reply(draft, target)
        self.assertEqual(result.status_code, 200, result.text)
        receipt = result.json()
        self.assertEqual(self.reply(draft, target, client_id="competing-team").status_code, 409)
        url = f"{self.admin_base}/{conversation['id']}/messages"
        missing_answer_precondition = {
            "text": "Follow-up team answer", "clientMessageId": "followup-team",
            "expectedRevision": receipt["revision"], "replyToMessageId": target,
        }
        self.assertEqual(self.client.post(url, headers=self.admin, json=missing_answer_precondition).status_code, 409)
        latest = self.get(conversation, headers)
        followup = self.reply(latest, target, text="Follow-up team answer", client_id="followup-team")
        self.assertEqual(followup.status_code, 200, followup.text)
        refreshed = self.get(conversation, headers)
        replay = self.reply(refreshed, target)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json(), receipt)
        self.assertEqual(self.reply(refreshed, newer_target).status_code, 409)
        self.assertEqual(len([message for message in refreshed["messages"] if message["role"] == "human"]), 2)
        future = {**refreshed, "revision": refreshed["revision"] + 1}
        self.assertEqual(self.reply(future, target, client_id="future-revision").status_code, 409)
        self.assertEqual(self.get(conversation, headers), refreshed)

    def test_concurrent_team_answers_compare_the_question_atomically(self) -> None:
        conversation, headers = self.create()
        draft = self.send(conversation, headers, item_ref="product:999").json()
        target = draft["messages"][0]["id"]
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda number: self.reply(
                draft, target, text=f"Team response {number}", client_id=f"team-{number}"), range(2)))
        self.assertEqual(sorted(result.status_code for result in results), [200, 409])
        current = self.get(conversation, headers)
        self.assertEqual(len([message for message in current["messages"] if message["role"] == "human"]), 1)
        self.assertFalse(current["needsHuman"])
        self.assertFalse(self.process())
        self.provider.assert_not_called()

    def test_two_failed_questions_reply_one_preserves_other_reason_quotes_and_privacy(self) -> None:
        conversation, headers = self.create()
        questions = []
        for number, reason in enumerate(("provider_unavailable", "missing_evidence")):
            sent = self.send(conversation, headers, f"Exact original question {number}?\n<customer words>",
                             client_id=f"failed-{number}").json()
            questions.append(sent["messages"][-1])
            answer = deepcopy(self.answer)
            answer.needs_human, answer.reason = True, reason
            self.provider.return_value = answer
            self.assertTrue(self.process())
        current = self.get(conversation, headers)
        self.assertEqual(current["needsHumanQuestions"], 2)
        self.assert_private_reason(current, "provider_unavailable")
        admin = self.client.get(f"{self.admin_base}/{conversation['id']}", headers=self.admin).json()
        pending = [message for message in admin["messages"] if message["needsHuman"]]
        self.assertEqual([message["id"] for message in pending], [question["id"] for question in questions])
        self.assertEqual([message["humanReason"] for message in pending], ["provider_unavailable", "missing_evidence"])
        self.assertTrue(all(message["answeredBy"] is None for message in pending))
        self.assertTrue(all(message["humanReason"] is None for message in current["messages"]))
        replied = self.reply(current, questions[0]["id"]).json()
        self.assertEqual(replied["needsHumanQuestions"], 1)
        self.assertTrue(replied["needsHuman"])
        self.assertEqual(replied["reason"], "missing_evidence")
        self.assertEqual(replied["messages"][-1]["replyTo"],
                         {"id": questions[0]["id"], "text": questions[0]["text"]})
        guest = self.get(conversation, headers)
        self.assert_private_reason(guest, "missing_evidence")
        self.assertNotIn("missing_evidence", json.dumps(guest))
        self.assertNotIn("provider_unavailable", json.dumps(guest))
        self.assertEqual(guest["messages"][-1]["replyTo"], replied["messages"][-1]["replyTo"])
        summary = self.client.get(self.admin_base, headers=self.admin).json()["items"][0]
        self.assertEqual(summary["needsHumanQuestions"], 1)
        self.assertEqual(summary["reason"], "missing_evidence")
        self.assertEqual(summary["lastMessage"], "Synthetic team response")
        self.provider.return_value = self.answer
        sent = self.send(conversation, headers, "New unrelated question", client_id="new-question").json()
        self.assertTrue(sent["processing"])
        self.assertTrue(self.process())
        current = self.get(conversation, headers)
        self.assertEqual(current["needsHumanQuestions"], 1)
        self.assert_private_reason(current, "missing_evidence")
        replied = self.reply(current, questions[1]["id"], client_id="human-2").json()
        self.assertEqual(replied["state"], "ai")
        self.assertEqual(replied["needsHumanQuestions"], 0)
        self.assertFalse(self.process())  # Neither old question is queued for replay.
        self.assertEqual(self.provider.await_count, 3)

    def test_provider_history_links_late_team_reply_without_changing_api_or_cross_guest_text(self) -> None:
        conversation, headers = self.create()
        first = self.send(conversation, headers, "Original J-cups question?\nExact text",
                          item_ref="product:999").json()["messages"][0]
        self.send(conversation, headers, "What is the bench price?", client_id="second-question")
        self.assertTrue(self.process())
        current = self.get(conversation, headers)
        replied = self.reply(current, first["id"], text="These J-cups fit the earlier item.").json()
        human = replied["messages"][-1]
        other, other_headers = self.create()
        other_question = self.send(other, other_headers, "PRIVATE_OTHER_GUEST_QUESTION",
                                   item_ref="product:999").json()["messages"][0]
        with support.get_store().connection() as db:
            support._append(db, conversation["id"], "human", "Legacy unlinked answer")
            support._append(db, conversation["id"], "human", "Legacy invalid link",
                            reply_to_id=other_question["id"])
        sent = self.send(conversation, headers, "What is its weight?", client_id="latest-question").json()
        self.assertTrue(self.process())
        history = self.provider.call_args.kwargs["messages"]
        self.assertIn({
            "role": "model",
            "text": f"Reply to earlier question: {first['text']}\nTeam reply: {human['text']}",
        }, history)
        self.assertIn({"role": "model", "text": "Legacy unlinked answer"}, history)
        self.assertIn({"role": "model", "text": "Legacy invalid link"}, history)
        self.assertEqual(history[-1], {"role": "user", "text": "What is its weight?"})
        self.assertNotIn("PRIVATE_OTHER_GUEST_QUESTION", json.dumps(history))
        guest = self.get(conversation, headers)
        self.assertNotIn("PRIVATE_OTHER_GUEST_QUESTION", json.dumps(guest))
        self.assertEqual(next(message for message in guest["messages"] if message["id"] == human["id"]), human)
        self.assertIsNone(next(message for message in guest["messages"] if message["text"] == "Legacy invalid link")["replyTo"])
        self.assertEqual(next(message for message in sent["messages"] if message["id"] == human["id"])["text"],
                         "These J-cups fit the earlier item.")
        with support.get_store().connection() as db:
            self.assertEqual(db.execute("SELECT text FROM messages WHERE id=?", (human["id"],)).fetchone()[0],
                             "These J-cups fit the earlier item.")

    def test_empty_handoff_transfers_to_first_question_or_is_resolved_by_team_greeting(self) -> None:
        conversation, headers = self.create()
        requested = self.client.post(f"{self.base}/{conversation['id']}/handoff", headers=headers, json={}).json()
        self.assertTrue(requested["needsHuman"])
        self.assertEqual(requested["needsHumanQuestions"], 0)
        greeted = self.reply(requested, None).json()
        self.assertEqual(greeted["state"], "ai")
        self.assertFalse(greeted["needsHuman"])
        self.assertIsNone(greeted["messages"][-1]["replyTo"])
        self.assertFalse(self.process())
        requested = self.client.post(f"{self.base}/{conversation['id']}/handoff", headers=headers, json={}).json()
        sent = self.send(conversation, headers).json()
        question = sent["messages"][-1]
        self.assertTrue(question["needsHuman"])
        self.assertIsNone(question["humanReason"])
        self.assertEqual(sent["needsHumanQuestions"], 1)
        self.assertTrue(sent["processing"])
        self.assertTrue(self.process())
        current = self.get(conversation, headers)
        self.assertTrue(current["needsHuman"])
        self.assertIsNone(next(message for message in current["messages"] if message["id"] == question["id"])["answeredBy"])
        self.assertEqual(self.reply(current, None, client_id="invalid-greeting").status_code, 422)
        replied = self.reply(current, question["id"], client_id="answer-question").json()
        self.assertFalse(replied["needsHuman"])
        self.assertEqual(replied["state"], "ai")
        self.assertTrue(self.send(conversation, headers, client_id="after-team").json()["processing"])
        self.assertTrue(self.process())

    def test_legacy_human_state_remains_ai_eligible_without_guessing_old_reply_links(self) -> None:
        conversation, headers = self.create()
        with support.get_store().connection() as db:
            support._append(db, conversation["id"], "customer", "Old synthetic question")
            support._append(db, conversation["id"], "human", "Unlinked legacy human answer")
            db.execute("UPDATE conversations SET state='human' WHERE id=?", (conversation["id"],))
        original = self.get(conversation, headers)
        self.assertIsNone(original["messages"][-1]["replyTo"])
        self.assertIsNone(original["messages"][0]["answeredBy"])
        self.assertFalse(self.process())
        current = self.send(conversation, headers, client_id="legacy-new-question").json()
        self.assertEqual(current["state"], "ai")
        self.assertTrue(current["processing"])
        self.assertTrue(self.process())
        current = self.get(conversation, headers)
        self.assertEqual(current["messages"][-1]["role"], "assistant")
        self.assertIsNone(current["messages"][1]["replyTo"])
        self.provider.assert_awaited_once()

    def test_concurrent_old_schema_reads_migrate_atomically_once_without_rewriting_history(self) -> None:
        conversation, headers, original = self.legacy_database()
        migration = support.SupportStore._migrate
        statements = []

        def checked_migration(db):
            self.assertTrue(db.in_transaction)
            with closing(sqlite3.connect(support.configured_path(), timeout=0)) as contender:
                with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                    contender.execute("BEGIN IMMEDIATE")
            db.set_trace_callback(statements.append)
            migration(db)

        with patch.object(support.SupportStore, "_migrate", staticmethod(checked_migration)):
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(lambda _: self.get(conversation, headers), range(4)))
        self.assertTrue(all(result == results[0] for result in results))
        self.assertEqual(sum(statement.startswith("ALTER TABLE") for statement in statements), 7)
        self.assertEqual(sum(statement == f"PRAGMA user_version={support.SCHEMA_VERSION}" for statement in statements), 1)
        guest = results[0]
        self.assertEqual(guest["revision"], 7)
        self.assertEqual(guest["needsHumanQuestions"], 2)
        self.assertTrue(all(message["humanReason"] is None for message in guest["messages"]))
        self.assertIsNone(guest["messages"][-1]["replyTo"])
        self.assertTrue(all(message["answeredBy"] is None for message in guest["messages"]))
        admin = self.client.get(f"{self.admin_base}/{conversation['id']}", headers=self.admin).json()
        self.assertEqual([message["humanReason"] for message in admin["messages"]],
                         ["needs_human", "interrupted", None])
        empty = self.client.get(f"{self.admin_base}/{original['empty_id']}", headers=self.admin).json()
        self.assertTrue(empty["needsHuman"])
        self.assertEqual(empty["needsHumanQuestions"], 0)
        self.assertEqual(empty["reason"], "customer_request")
        with support.get_store().connection() as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], support.SCHEMA_VERSION)
            self.assertEqual([tuple(row)[:9] for row in db.execute("SELECT * FROM messages ORDER BY rowid")],
                             original["messages"])
            self.assertEqual([tuple(row)[:10] for row in db.execute("SELECT * FROM conversations ORDER BY rowid")],
                             original["conversations"])
            self.assertEqual([tuple(row)[:10] for row in db.execute("SELECT * FROM jobs ORDER BY rowid")], original["jobs"])
            self.assertTrue(all(row["page_context_version"] is None and row["answer_plan_json"] is None
                                for row in db.execute("SELECT * FROM jobs")))
            stored = list(db.iterdump())
        self.assertEqual(self.get(conversation, headers), guest)
        replay = self.send(conversation, headers, original["body"].text, original["body"].clientMessageId, item_ref=None)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertIsNone(replay.json()["reason"])
        with support.get_store().connection() as db:
            self.assertEqual(list(db.iterdump()), stored)
            self.assertEqual(db.execute("SELECT response_json FROM messages WHERE id=?",
                                        (original["first_id"],)).fetchone()[0], original["receipt"])
        self.assertFalse(self.process())
        self.provider.assert_not_called()
        answered = self.reply(guest, original["first_id"]).json()
        self.assertEqual(answered["needsHumanQuestions"], 1)
        self.assertEqual(answered["reason"], "interrupted")
        self.assertTrue(self.send(conversation, headers, client_id="after-migration").json()["processing"])
        self.assertTrue(self.process())

    def test_failed_old_schema_migration_rolls_back_columns_flags_and_version(self) -> None:
        conversation, headers, original = self.legacy_database()
        migration = support.SupportStore._migrate

        def fail_migration(db):
            migration(db)
            raise sqlite3.OperationalError("synthetic migration failure")

        with patch.object(support.SupportStore, "_migrate", staticmethod(fail_migration)):
            result = self.client.get(f"{self.base}/{conversation['id']}", headers=headers)
        self.assertEqual(result.status_code, 503)
        with closing(sqlite3.connect(support.configured_path())) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
            self.assertNotIn("reply_to_id", [row[1] for row in db.execute("PRAGMA table_info(messages)")])
            self.assertNotIn("unlinked_human_reason", [row[1] for row in db.execute("PRAGMA table_info(conversations)")])
            self.assertEqual(db.execute("SELECT * FROM messages ORDER BY rowid").fetchall(), original["messages"])
        self.assertEqual(self.get(conversation, headers)["needsHumanQuestions"], 2)

    def test_guest_handoff_keeps_acknowledged_job_and_answers_followups_while_pending(self) -> None:
        conversation, headers = self.create()
        sent = self.send(conversation, headers).json()
        result = self.client.post(f"{self.base}/{conversation['id']}/handoff", headers=headers, json={})
        self.assertEqual(result.status_code, 200, result.text)
        handoff = result.json()
        self.assertGreater(handoff["revision"], sent["revision"])
        self.assertEqual(handoff["state"], "waiting_human")
        self.assertTrue(handoff["needsHuman"])
        self.assertTrue(handoff["processing"])
        self.assert_private_reason(handoff, "customer_request")
        self.assertEqual(handoff["messages"][-1]["text"], "Your request has been sent to our team.")
        self.assertEqual(self.client.post(f"{self.base}/{conversation['id']}/handoff",
                                         headers=headers, json={}).json(), handoff)
        self.assertEqual(self.send(conversation, headers).json(), sent)  # Lost message acknowledgement.
        self.assertTrue(self.process())
        for number, question in enumerate(("What is its weight?", "What material is it made from?"), 1):
            self.answer.text = ("Synthetic rack weighs 30 kg." if number == 1
                                else "Synthetic rack is made from Steel.")
            queued = self.send(conversation, headers, question, f"followup-{number}")
            self.assertEqual(queued.status_code, 200, queued.text)
            self.assertTrue(queued.json()["processing"])
            self.assertTrue(self.process())
            current = self.get(conversation, headers)
            self.assertEqual(current["state"], "waiting_human")
            self.assertTrue(current["needsHuman"])
            self.assertFalse(current["processing"])
            self.assert_private_reason(current, "customer_request")
            self.assertEqual(current["messages"][-1]["text"], self.answer.text)
            self.assertEqual(current["messages"][-1]["role"], "assistant")
            requested = self.client.post(f"{self.base}/{conversation['id']}/handoff", headers=headers, json={}).json()
            self.assertEqual(requested["needsHumanQuestions"], number + 1)
            self.assertEqual(requested["messages"][-1]["replyTo"]["id"],
                             next(message["id"] for message in current["messages"] if message["text"] == question))
            self.assertEqual(self.client.post(f"{self.base}/{conversation['id']}/handoff",
                                             headers=headers, json={}).json(), requested)
            current = requested
        self.assertEqual(len([message for message in current["messages"] if message["role"] == "assistant"]), 3)
        self.assertEqual(len([message for message in current["messages"] if message["role"] == "system"]), 3)
        inbox = self.client.get(self.admin_base, headers=self.admin).json()
        self.assertEqual(inbox["needsHumanCount"], 1)
        self.assertEqual(inbox["items"][0]["lastMessage"], support.HELP_TEXT)
        self.assertEqual(inbox["items"][0]["needsHumanQuestions"], 3)
        self.assertFalse(self.process())
        self.assertEqual(self.provider.await_count, 3)

    def test_provider_failures_and_unsupported_topics_are_sanitized_human_cases(self) -> None:
        for outcome in ("exception", "missing_information", "out_of_scope", "customer_request",
                        "compatibility_unverified", "provider_unavailable", "invalid_reference", "topic"):
            with self.subTest(outcome=outcome):
                conversation, headers = self.create()
                self.send(conversation, headers)
                self.provider.side_effect = RuntimeError("PRIVATE_PROVIDER_SECRET") if outcome == "exception" else None
                answer = deepcopy(self.answer)
                if outcome in ("missing_information", "out_of_scope", "customer_request",
                               "compatibility_unverified", "provider_unavailable"):
                    answer.needs_human, answer.reason = True, outcome
                if outcome == "invalid_reference":
                    answer.references = ("product:2",)
                if outcome == "topic":
                    answer.topic = "medical"
                self.provider.return_value = answer
                if outcome == "exception":
                    with self.assertLogs("app.support", level="WARNING") as logged:
                        self.assertTrue(self.process())
                    self.assertIn("RuntimeError", " ".join(logged.output))
                    self.assertNotIn("PRIVATE_PROVIDER_SECRET", " ".join(logged.output))
                else:
                    self.assertTrue(self.process())
                result = self.get(conversation, headers)
                self.assertEqual(result["state"], "waiting_human")
                self.assertTrue(result["needsHuman"])
                self.assertFalse(result["processing"])
                self.assertEqual(result["messages"][-1]["role"], "system")
                self.assertEqual(result["messages"][-1]["text"], "Your request has been sent to our team.")
                self.assertNotIn("PRIVATE_PROVIDER_SECRET", json.dumps(result))
                reason = {"exception": "provider_failure", "invalid_reference": "missing_information",
                          "topic": "out_of_scope"}.get(outcome, outcome)
                self.assert_private_reason(result, reason)
                self.provider.side_effect = None
                self.provider.return_value = self.answer
                later = self.send(conversation, headers, "What is its weight?", "retry-new-question")
                self.assertEqual(later.status_code, 200, later.text)
                self.assertTrue(later.json()["processing"])
                self.assertTrue(self.process())
                current = self.get(conversation, headers)
                self.assertEqual(current["messages"][-1]["role"], "assistant")
                self.assertEqual(current["state"], "waiting_human")
                self.assertTrue(current["needsHuman"])
                self.assert_private_reason(current, reason)

    def test_concurrent_handoff_retries_preserve_one_confirmation_and_generation(self) -> None:
        conversation, headers = self.create()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.client.post(
                f"{self.base}/{conversation['id']}/handoff", headers=headers, json={}), range(2)))
        self.assertEqual([result.status_code for result in results], [200, 200])
        self.assertEqual(results[0].json(), results[1].json())
        current = results[0].json()
        self.assertEqual(current["revision"], 1)
        self.assertEqual([message["text"] for message in current["messages"]],
                         ["Your request has been sent to our team."])
        self.assert_private_reason(current, "customer_request")
        with support.get_store().connection() as db:
            self.assertEqual(db.execute("SELECT generation FROM conversations").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)

    def test_handoff_during_running_answer_preserves_reply_and_team_only_answers_target(self) -> None:
        async def scenario():
            conversation, headers = self.create()
            sent = self.send(conversation, headers).json()
            started, release = asyncio.Event(), asyncio.Event()

            async def delayed(**kwargs):
                started.set()
                await release.wait()
                return self.answer

            self.provider.side_effect = delayed
            worker = asyncio.create_task(support.process_one())
            try:
                await asyncio.wait_for(started.wait(), 2)
                handoff = self.client.post(f"{self.base}/{conversation['id']}/handoff",
                                           headers=headers, json={}).json()
                self.assertTrue(handoff["processing"])
                self.assertEqual(self.send(conversation, headers).json(), sent)
                self.assertEqual(self.client.post(f"{self.base}/{conversation['id']}/handoff",
                                                 headers=headers, json={}).json(), handoff)
                release.set()
                self.assertTrue(await worker)
                current = self.get(conversation, headers)
                self.assertEqual(current["messages"][-1]["role"], "assistant")
                self.assertEqual(current["state"], "waiting_human")
                self.assertTrue(current["needsHuman"])
                self.assert_private_reason(current, "customer_request")
                queued = self.send(conversation, headers, client_id="before-team").json()
                replied = self.reply(queued, queued["messages"][-1]["id"])
                self.assertEqual(replied.status_code, 200, replied.text)
                self.assertEqual(replied.json()["state"], "waiting_human")
                self.assertEqual(replied.json()["needsHumanQuestions"], 1)
                self.assertFalse(await support.process_one())
                later = self.send(conversation, headers, client_id="after-team").json()
                self.assertTrue(later["processing"])
                self.assertEqual(later["state"], "waiting_human")
                self.assertTrue(later["needsHuman"])
                self.assertTrue(await support.process_one())
                self.assertEqual(self.provider.await_count, 2)
            finally:
                release.set()
                await worker

        asyncio.run(scenario())

    def test_reply_to_older_question_preserves_newer_queued_and_running_ai_jobs(self) -> None:
        async def scenario(boundary):
            conversation, headers = self.create()
            failed = self.send(conversation, headers, "Original\nexact <question>?", item_ref="product:999").json()
            old_question = failed["messages"][0]
            pending = self.send(conversation, headers, "New question", client_id="new-question").json()
            new_question = pending["messages"][-1]
            started, release = asyncio.Event(), asyncio.Event()

            async def delayed(**kwargs):
                started.set()
                await release.wait()
                return self.answer

            self.provider.side_effect = delayed
            worker = asyncio.create_task(support.process_one()) if boundary == "running" else None
            try:
                if worker is not None:
                    await asyncio.wait_for(started.wait(), 2)
                with support.get_store().connection() as db:
                    generation = db.execute("SELECT generation FROM conversations WHERE id=?",
                                            (conversation["id"],)).fetchone()[0]
                cleared = self.reply(pending, old_question["id"])
                self.assertEqual(cleared.status_code, 200, cleared.text)
                current = cleared.json()
                self.assertEqual(current["state"], "ai")
                self.assertFalse(current["needsHuman"])
                self.assertIsNone(current["reason"])
                self.assertTrue(current["processing"])
                self.assertEqual(current["revision"], pending["revision"] + 1)
                self.assertEqual(current["messages"][-1]["replyTo"],
                                 {"id": old_question["id"], "text": old_question["text"]})
                self.assertEqual(current["messages"][0]["answeredBy"], current["messages"][-1]["id"])
                self.assertEqual(self.reply(current, old_question["id"]).json(), current)
                self.assertEqual(self.reply(current, new_question["id"]).status_code, 409)
                self.assertEqual(self.reply(pending, old_question["id"], client_id="stale-new").status_code, 409)
                with support.get_store().connection() as db:
                    self.assertEqual(db.execute("SELECT generation FROM conversations WHERE id=?",
                                                (conversation["id"],)).fetchone()[0], generation)
                    self.assertEqual(db.execute("SELECT status FROM jobs WHERE conversation_id=?",
                                                (conversation["id"],)).fetchone()[0], boundary)
                release.set()
                self.assertTrue(await worker if worker is not None else await support.process_one())
                published = self.get(conversation, headers)
                self.assertEqual(published["state"], "ai")
                self.assertFalse(published["needsHuman"])
                self.assertFalse(published["processing"])
                self.assert_private_reason(published, None)
                self.assertEqual(published["messages"][-1]["role"], "assistant")
                self.assertEqual(published["messages"][-1]["text"], self.answer.text)
                self.assertEqual(published["messages"][-1]["replyTo"],
                                 {"id": new_question["id"], "text": new_question["text"]})
                self.assertEqual(self.reply(published, old_question["id"]).json(), current)
                self.assertEqual(self.client.get(self.admin_base, headers=self.admin).json()["needsHumanCount"], 0)
            finally:
                release.set()
                if worker is not None:
                    await worker

        for boundary in ("queued", "running"):
            with self.subTest(boundary=boundary):
                asyncio.run(scenario(boundary))
        self.assertEqual(self.provider.await_count, 2)

    def test_legacy_waiting_history_and_receipts_are_private_without_rewriting_history(self) -> None:
        conversation, headers = self.create()
        legacy_text = "Your message is saved. Human help has been requested; AI replies are paused."
        body = support.MessageInput(clientMessageId="legacy-message", text="Synthetic saved question")
        with support.get_store().connection() as db:
            db.execute("""UPDATE conversations SET state='waiting_human',needs_human=1,
                          reason='provider_unavailable',unlinked_human_reason='provider_unavailable'""")
            message_id = support._append(db, conversation["id"], "customer", body.text,
                                         client_id=body.clientMessageId, request_hash=support._fingerprint(body))
            support._append(db, conversation["id"], "system", legacy_text)
            support._append(db, conversation["id"], "customer", legacy_text)
            original = support._snapshot(db, conversation["id"])
            db.execute("UPDATE messages SET response_json=? WHERE id=?", (json.dumps(original), message_id))
            stored = list(db.iterdump())
        guest = self.get(conversation, headers)
        self.assert_private_reason(guest, "provider_unavailable")
        self.assertEqual(guest["messages"][1]["text"], "Your request has been sent to our team.")
        self.assertEqual(guest["messages"][2]["text"], legacy_text)  # Never alter customers' words.
        replay = self.send(conversation, headers, body.text, body.clientMessageId, item_ref=None)
        self.assertEqual(replay.status_code, 200, replay.text)
        self.assertEqual(replay.json(), guest)
        admin = self.client.get(f"{self.admin_base}/{conversation['id']}", headers=self.admin)
        self.assertEqual(admin.json(), original)
        with support.get_store().connection() as db:
            self.assertEqual(list(db.iterdump()), stored)
        self.assertTrue(self.send(conversation, headers, client_id="legacy-followup").json()["processing"])
        self.assertTrue(self.process())
        current = self.get(conversation, headers)
        self.assertEqual(current["state"], "waiting_human")
        self.assertTrue(current["needsHuman"])
        self.assert_private_reason(current, "provider_unavailable")
        self.assertEqual(current["messages"][-1]["role"], "assistant")
        self.provider.assert_awaited_once()

    def test_stale_generation_cannot_claim_refresh_publish_or_clear_pending_attention(self) -> None:
        for boundary in ("claim", "refresh", "publish"):
            with self.subTest(boundary=boundary):
                conversation, headers = self.create()
                self.client.post(f"{self.base}/{conversation['id']}/handoff", headers=headers, json={})
                self.send(conversation, headers)
                store = support.get_store()
                job = None if boundary == "claim" else support._claim(store)
                with store.connection() as db:
                    db.execute("UPDATE conversations SET generation=generation+1 WHERE id=?", (conversation["id"],))
                    before = dict(db.execute("SELECT * FROM conversations WHERE id=?", (conversation["id"],)).fetchone())
                if boundary == "claim":
                    self.assertTrue(support._claim(store))
                elif boundary == "refresh":
                    self.assertFalse(support._save_current_payload(store, job, json.loads(job["payload"])))
                else:
                    support._publish(store, job, None, "STALE_REPLY_MUST_NOT_PUBLISH", [], {}, [])
                with store.connection() as db:
                    after = dict(db.execute("SELECT * FROM conversations WHERE id=?", (conversation["id"],)).fetchone())
                    self.assertEqual(after, before)
                    self.assertEqual(db.execute("SELECT status FROM jobs WHERE conversation_id=?",
                                                (conversation["id"],)).fetchone()[0], "cancelled")
                current = self.get(conversation, headers)
                self.assertFalse(current["processing"])
                self.assertTrue(current["needsHuman"])
                self.assert_private_reason(current, "customer_request")
                self.assertFalse(any(message["role"] == "assistant" for message in current["messages"]))
        self.provider.assert_not_called()

    def test_late_answer_cannot_duplicate_team_answer_or_ignore_close_or_settings(self) -> None:
        async def scenario(kind: str) -> None:
            conversation, headers = self.create()
            sent = self.send(conversation, headers).json()
            started, release = asyncio.Event(), asyncio.Event()

            async def delayed(**kwargs):
                started.set()
                await release.wait()
                return self.answer

            self.provider.side_effect = delayed
            worker = asyncio.create_task(support.process_one())
            await asyncio.wait_for(started.wait(), 2)
            self.assertFalse(await support.process_one())  # No second provider call while running.
            pending = self.client.post(f"{self.base}/{conversation['id']}/handoff",
                                       headers=headers, json={}).json()
            self.assertTrue(pending["processing"])
            if kind == "team_reply":
                self.assertEqual(self.reply({**sent, "revision": pending["revision"] + 1},
                                            sent["messages"][0]["id"]).status_code, 409)
                self.assertEqual(self.reply(pending, sent["messages"][0]["id"]).status_code, 200)
                changed = self.get(conversation, headers)
                self.assertFalse(changed["processing"])
                self.assertFalse(changed["needsHuman"])
            elif kind == "close":
                self.assertEqual(self.action(sent, kind).status_code, 409)
                self.assertEqual(self.action(pending, kind).status_code, 200)
                changed = self.get(conversation, headers)
            else:
                self.assertEqual(self.save_settings(kind != "disable", ["products"]).status_code, 200)
                changed = self.get(conversation, headers)
            release.set()
            await worker
            result = self.get(conversation, headers)
            self.assertEqual(result, changed)
            self.assertFalse(any(message["role"] == "assistant" for message in result["messages"]))
            if kind == "close":
                self.assertEqual(self.send(conversation, headers, client_id="closed").status_code, 409)
                self.assertEqual(self.client.post(f"{self.base}/{conversation['id']}/handoff",
                                                 headers=headers, json={}).status_code, 409)

        for kind in ("team_reply", "close", "topics", "disable"):
            with self.subTest(kind=kind):
                asyncio.run(scenario(kind))
        self.assertEqual(self.provider.await_count, 4)

    def test_queue_restart_and_interrupted_running_jobs_do_not_duplicate_calls(self) -> None:
        first, headers = self.create()
        self.send(first, headers)
        store = support.SupportStore(support.configured_path())
        self.assertEqual(support.recover_interrupted(store), 0)
        self.assertTrue(asyncio.run(support.process_one(store)))
        self.assertEqual(len(self.get(first, headers)["messages"]), 2)
        second, second_headers = self.create()
        self.send(second, second_headers)
        with store.connection() as db:
            db.execute("UPDATE jobs SET status='running' WHERE conversation_id=?", (second["id"],))
        self.assertEqual(support.recover_interrupted(support.SupportStore(store.path)), 1)
        result = self.get(second, second_headers)
        self.assertEqual(result["state"], "waiting_human")
        self.assert_private_reason(result, "interrupted")
        self.assertFalse(result["processing"])
        self.assertEqual(support.recover_interrupted(store), 0)
        self.assertFalse(self.process())
        self.provider.assert_awaited_once()

    def test_records_are_retained_and_foreign_keys_cascade_only_on_explicit_delete(self) -> None:
        conversation, headers = self.create()
        queued = self.send(conversation, headers).json()
        self.action(queued, "close")
        with support.get_store().connection() as db:
            db.execute("UPDATE conversations SET created_at='2000-01-01T00:00:00+00:00'")
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        self.assertEqual(self.get(conversation, headers)["state"], "closed")
        support.recover_interrupted()
        self.assertFalse(self.process())
        with support.get_store().connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)
            db.execute("DELETE FROM conversations WHERE id=?", (conversation["id"],))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)

    def test_create_rate_limit_is_transient_without_raw_ip_storage(self) -> None:
        for _ in range(10):
            self.create()
        self.assertEqual(self.client.post(self.base, json={}).status_code, 429)
        self.assertTrue(all(len(key) == 64 for key in support.rate_windows))
        support.rate_windows.clear()
        self.create()

    def test_only_isolated_test_environment_can_override_bounded_creation_limit(self) -> None:
        with patch.dict(os.environ, {"STYL_SUPPORT_CREATE_LIMIT": "100"}):
            for _ in range(11):
                self.create()
            with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "local"}):
                self.assertEqual(support.create_limit(), 10)
            with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "production"}):
                self.assertEqual(support.create_limit(), 10)
        for value in ("0", "201", "-1", "invalid"):
            with patch.dict(os.environ, {"STYL_SUPPORT_CREATE_LIMIT": value}):
                with self.assertRaises(ValueError):
                    support.create_limit()

    def test_private_path_and_environment_separation(self) -> None:
        root = Path(__file__).resolve().parents[2]
        for bad in ("relative.sqlite3", str(root / "frontend" / "public" / "support.sqlite3"),
                    str(self.root / "support.json"), str(self.root / "analytics.sqlite3")):
            with patch.dict(os.environ, {"STYL_SUPPORT_DB": bad}):
                with self.assertRaises(ValueError):
                    support.configured_path()
        self.create()
        with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "local"}):
            self.assertEqual(self.client.get("/api/admin/support/config", headers=self.admin).status_code, 503)

    def test_storage_failure_keeps_commerce_available_and_errors_private(self) -> None:
        conversation, headers = self.create()
        with patch.object(support.SupportStore, "connection", side_effect=sqlite3.OperationalError("PRIVATE_SQL_ERROR")):
            result = self.send(conversation, headers, text="Synthetic draft remains with caller.")
            self.assertEqual(result.status_code, 503)
            self.assertNotIn("PRIVATE_SQL_ERROR", result.text)
            catalog = self.client.get("/api/products")
            self.assertEqual(catalog.status_code, 200)
            self.assertEqual(catalog.json()["items"][0]["name"], "Synthetic rack")
        self.assertEqual(self.get(conversation, headers)["messages"], [])
        self.assertEqual(self.send(conversation, headers).status_code, 200)

    def test_cancelled_worker_is_recovered_without_replaying_provider(self) -> None:
        async def scenario():
            conversation, headers = self.create()
            self.client.post(f"{self.base}/{conversation['id']}/handoff", headers=headers, json={})
            self.send(conversation, headers)
            started = asyncio.Event()

            async def pending(**kwargs):
                started.set()
                await asyncio.Event().wait()

            self.provider.side_effect = pending
            task = asyncio.create_task(support.process_one())
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(support.recover_interrupted(), 1)
            recovered = self.get(conversation, headers)
            self.assert_private_reason(recovered, "customer_request")
            self.assertTrue(recovered["needsHuman"])
            self.assertEqual(recovered["state"], "waiting_human")
            self.assertEqual(recovered["messages"][-1]["text"], "Your request has been sent to our team.")
            self.assertFalse(await support.process_one())
            self.provider.assert_awaited_once()
            self.provider.side_effect = None
            self.assertTrue(self.send(conversation, headers, client_id="after-recovery").json()["processing"])
            self.assertTrue(await support.process_one())
            current = self.get(conversation, headers)
            self.assertEqual(current["messages"][-1]["role"], "assistant")
            self.assertTrue(current["needsHuman"])
            self.assertEqual(current["state"], "waiting_human")
            self.assert_private_reason(current, "customer_request")

        asyncio.run(scenario())
        self.assertEqual(self.provider.await_count, 2)

    def test_worker_database_wait_does_not_block_event_loop(self) -> None:
        async def scenario():
            started, release = Event(), Event()

            def blocked_claim(store):
                started.set()
                if not release.wait(3):
                    raise TimeoutError("Synthetic claim did not get released.")
                return False

            with patch.object(support, "_claim", side_effect=blocked_claim):
                task = asyncio.create_task(support.process_one())
                try:
                    ready = await asyncio.wait_for(asyncio.to_thread(started.wait, 2), 2.5)
                    self.assertTrue(ready)
                    self.assertFalse(task.done())
                    release.set()
                    self.assertFalse(await task)
                finally:
                    release.set()
                    await task

        asyncio.run(scenario())

    def test_lifespan_gate_recovery_and_worker_storage_failure_retry(self) -> None:
        async def startup():
            called = asyncio.Event()

            async def worker(store):
                called.set()
                await asyncio.Event().wait()

            with patch.object(support, "_worker", side_effect=worker) as mocked:
                with patch.dict(os.environ, {"STYL_SUPPORT_ENABLED": "false"}):
                    async with support.lifespan(main.app):
                        mocked.assert_not_called()
                async with support.lifespan(main.app):
                    await asyncio.wait_for(called.wait(), 2)
                    mocked.assert_awaited_once()

        asyncio.run(startup())

        async def storage_recovery():
            store = support.get_store()
            conversation, headers = self.create()
            self.send(conversation, headers)
            original_publish = support._publish
            published = Event()

            def fail_first(*args):
                if not published.is_set():
                    published.set()
                    raise sqlite3.OperationalError("Synthetic storage failure after provider completion.")
                return original_publish(*args)

            recovered = asyncio.Event()
            original_recover = support.recover_interrupted
            loop = asyncio.get_running_loop()

            def track_recovery(value):
                result = original_recover(value)
                if result:
                    loop.call_soon_threadsafe(recovered.set)
                return result

            with patch.object(support, "_publish", side_effect=fail_first), \
                    patch.object(support, "recover_interrupted", side_effect=track_recovery):
                task = asyncio.create_task(support._worker(store))
                try:
                    await asyncio.wait_for(recovered.wait(), 3)
                    current = self.get(conversation, headers)
                    self.assertEqual(current["state"], "waiting_human")
                    self.assert_private_reason(current, "interrupted")
                    self.assertFalse(current["processing"])
                    self.provider.assert_awaited_once()
                finally:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

        asyncio.run(storage_recovery())


if __name__ == "__main__":
    unittest.main()
