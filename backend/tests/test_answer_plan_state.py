"""SUP-028: answer-plan metadata and clarification context preserve session boundaries."""

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import support


class AnswerPlanStateTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="styl-answer-plan-state-")
        self.addCleanup(temporary.cleanup)
        environment = patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "test"})
        environment.start()
        self.addCleanup(environment.stop)
        self.store = support.SupportStore(Path(temporary.name) / "support.sqlite3")
        self.identifier = "a" * 32
        self.question = "b" * 32
        self.job = "c" * 32
        self.plan = {"schemaVersion": 1, "status": "clarification",
                     "pendingSlots": [{"productRef": "product:1", "slot": "holeDiameter"}]}
        with self.store.connection() as db:
            db.execute("""INSERT INTO conversations(id,token_hash,state,revision,generation,created_at,
                       updated_at,currency,needs_human,reason) VALUES(?,?,'ai',1,1,?,?,'CAD',0,NULL)""",
                       (self.identifier, "hash-test-only", support.now(), support.now()))
            db.execute("""INSERT INTO messages(id,conversation_id,role,text,created_at,references_json)
                       VALUES(?,?,'customer','What holes does it need?',?,'[]')""",
                       (self.question, self.identifier, support.now()))
            db.execute("""INSERT INTO jobs(id,conversation_id,message_id,generation,settings_revision,status,
                       payload,created_at,updated_at,page_context_version,answer_plan_json)
                       VALUES(?,?,?,1,0,'completed','{}',?,?,'page-a',?)""",
                       (self.job, self.identifier, self.question, support.now(), support.now(), json.dumps(self.plan)))

    def test_pending_plan_is_scoped_to_conversation_and_page_transition(self):
        with self.store.connection() as db:
            self.assertEqual(support._pending_plan(db, self.identifier, "page-a"), self.plan)
            self.assertIsNone(support._pending_plan(db, self.identifier, "page-b"))
            self.assertIsNone(support._pending_plan(db, self.identifier, None))
            self.assertIsNone(support._pending_plan(db, "d" * 32, "page-a"))

    def test_failed_latest_job_or_targeted_team_reply_cannot_reuse_old_slots(self):
        with self.store.connection() as db:
            db.execute("UPDATE jobs SET status='failed' WHERE id=?", (self.job,))
            self.assertIsNone(support._pending_plan(db, self.identifier, "page-a"))
            db.execute("UPDATE jobs SET status='completed' WHERE id=?", (self.job,))
            support._append(db, self.identifier, "human", "Team reply", reply_to_id=self.question)
            self.assertIsNone(support._pending_plan(db, self.identifier, "page-a"))

    def test_contact_or_unrelated_revision_does_not_clear_pending_context(self):
        with self.store.connection() as db:
            db.execute("UPDATE conversations SET revision=revision+1 WHERE id=?", (self.identifier,))
            self.assertEqual(support._pending_plan(db, self.identifier, "page-a"), self.plan)

    def test_legacy_message_receipt_identity_does_not_change_when_stamp_is_absent(self):
        body = support.MessageInput(clientMessageId="legacy-request", text="What is the price?", itemRef=None)
        old_payload = {"clientMessageId": "legacy-request", "text": "What is the price?", "itemRef": None}
        old_hash = hashlib.sha256(json.dumps(old_payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(support._fingerprint(body), old_hash)
        a = body.model_copy(update={"pageContextVersion": "page-a"})
        b = body.model_copy(update={"pageContextVersion": "page-b"})
        self.assertNotEqual(support._fingerprint(a), support._fingerprint(b))
        self.assertNotEqual(support._fingerprint(a), old_hash)

    def test_schema_four_adds_metadata_without_rewriting_existing_job(self):
        with self.store.connection() as db:
            db.execute("ALTER TABLE jobs DROP COLUMN page_context_version")
            db.execute("ALTER TABLE jobs DROP COLUMN answer_plan_json")
            db.execute("PRAGMA user_version=3")
            original = tuple(db.execute("SELECT * FROM jobs WHERE id=?", (self.job,)).fetchone())
        with self.store.connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (self.job,)).fetchone()
            self.assertEqual(tuple(row)[:len(original)], original)
            self.assertIsNone(row["page_context_version"])
            self.assertIsNone(row["answer_plan_json"])
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], support.SCHEMA_VERSION)

    def test_malformed_stored_plan_is_an_explicit_error(self):
        with self.store.connection() as db:
            db.execute("UPDATE jobs SET answer_plan_json='[]' WHERE id=?", (self.job,))
            with self.assertRaisesRegex(ValueError, "Stored answer plan is invalid"):
                support._pending_plan(db, self.identifier, "page-a")

    def test_intervening_question_without_a_job_clears_pending_slot_use(self):
        with self.store.connection() as db:
            support._append(db, self.identifier, "customer", "An unrelated newer question")
            current = support._append(db, self.identifier, "customer", "1 inch")
            self.assertIsNone(support._pending_plan(db, self.identifier, "page-a", current))

    def test_old_pending_slots_expire_without_deleting_conversation_history(self):
        with self.store.connection() as db:
            db.execute("UPDATE jobs SET updated_at='2026-10-01T12:00:00+00:00' WHERE id=?", (self.job,))
            with patch.object(support, "now", return_value="2026-10-01T12:30:00+00:00"):
                self.assertEqual(support._pending_plan(db, self.identifier, "page-a"), self.plan)
            with patch.object(support, "now", return_value="2026-10-01T12:30:01+00:00"):
                self.assertIsNone(support._pending_plan(db, self.identifier, "page-a"))
            self.assertEqual(db.execute("SELECT count(*) FROM messages").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)
