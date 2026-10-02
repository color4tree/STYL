"""SUP-017: question-linked team replies do not interrupt the latest catalog question."""

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

from app import analytics, main, records_archive, support, support_ai


class QuestionReplyFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="styl-question-reply-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        products = self.root / "products.json"
        accessories = self.root / "accessories.json"
        products.write_text(json.dumps([{
            "id": 1, "name": "STYL Adjustable Bench", "slug": "styl-adjustable-bench",
            "category": "Benches", "prices": {"CAD": 750, "USD": 600}, "publicationStatus": "published",
            "weight": "Approx. 50 kg / 110 lb", "description": "Adjustable training bench.",
        }]))
        accessories.write_text(json.dumps([{
            "id": 1001, "name": "STYL Sandwich J-Cups", "category": "Rack attachments",
            "prices": {"CAD": 119, "USD": 95}, "publicationStatus": "published", "description": "Protective J-cups.",
        }]))
        for replacement in (
            patch.dict(os.environ, {
                "STYL_SUPPORT_ENABLED": "true", "STYL_SUPPORT_ENVIRONMENT": "test",
                "STYL_SUPPORT_PROVIDER": "gemini", "STYL_SUPPORT_MODEL": "gemini-3.5-flash",
                "STYL_SUPPORT_DB": str(self.root / "support.sqlite3"),
                "STYL_ANALYTICS_DB": str(self.root / "analytics.sqlite3"),
                "STYL_ANALYTICS_ENVIRONMENT": "test", "STYL_KNOWLEDGE_DIR": str(self.root / "knowledge"),
                "STYL_RECORDS_DIR": str(self.root / "records"), "STYL_WEBSITE_LOG_DIR": "",
                "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "",
            }),
            patch.multiple(main, DATA_PATH=products, ACCESSORIES_PATH=accessories,
                           INQUIRIES_PATH=self.root / "inquiries", ADMIN_TOKEN="question-reply-test-only"),
            patch.object(support_ai.GeminiProvider, "decide", side_effect=AssertionError("Synthetic lookup must not call a provider.")),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        with analytics.get_store().connection():
            pass
        with support.rate_lock:
            support.rate_windows.clear()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        created = self.client.post("/api/support/conversations", json={})
        self.assertEqual(created.status_code, 201, created.text)
        value = created.json()
        self.identifier = value["conversation"]["id"]
        self.url = "/api/support/conversations/" + self.identifier
        self.admin_url = "/api/admin/support/conversations/" + self.identifier
        self.guest = {"Authorization": "Bearer " + value["token"]}
        self.admin = {"Authorization": "Bearer question-reply-test-only"}

    def ask(self, text: str, *, process: bool = True) -> dict:
        response = self.client.post(self.url + "/messages", headers=self.guest,
                                    json={"clientMessageId": uuid4().hex, "text": text})
        self.assertEqual(response.status_code, 200, response.text)
        if process:
            self.assertTrue(asyncio.run(support.process_one()))
        return self.client.get(self.admin_url, headers=self.admin).json()

    def reply(self, question: dict, text: str, revision: int) -> dict:
        response = self.client.post(self.admin_url + "/messages", headers=self.admin, json={
            "clientMessageId": uuid4().hex, "text": text, "expectedRevision": revision,
            "replyToMessageId": question["id"], "expectedAnsweredBy": question.get("answeredBy"),
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_two_unresolved_questions_reply_one_preserves_latest_job_and_exact_quote(self) -> None:
        first = self.ask("What is the weight of STYL Sandwich J-Cups?")
        first_question = next(message for message in first["messages"] if message["role"] == "customer")
        second = self.ask("What are the dimensions of STYL Adjustable Bench?")
        second_question = [message for message in second["messages"] if message["role"] == "customer"][-1]
        self.assertEqual(second["needsHumanQuestions"], 2)
        latest = self.ask("What is the price of STYL Adjustable Bench?", process=False)
        self.assertTrue(latest["processing"])
        replied = self.reply(first_question, "Happy to help with your J-cups question. We will confirm that specification.", first["revision"])
        self.assertTrue(replied["processing"])
        self.assertEqual(replied["needsHumanQuestions"], 1)
        team = replied["messages"][-1]
        self.assertEqual(team["role"], "human")
        self.assertEqual(team["replyTo"], {"id": first_question["id"], "text": first_question["text"]})
        questions = {message["id"]: message for message in replied["messages"] if message["role"] == "customer"}
        self.assertFalse(questions[first_question["id"]]["needsHuman"])
        self.assertEqual(questions[first_question["id"]]["answeredBy"], team["id"])
        self.assertTrue(questions[second_question["id"]]["needsHuman"])
        self.assertTrue(asyncio.run(support.process_one()))
        guest = self.client.get(self.url, headers=self.guest).json()
        self.assertIn("CAD $750.00", guest["messages"][-1]["text"])
        self.assertEqual(guest["needsHumanQuestions"], 1)
        guest_team = next(message for message in guest["messages"] if message["id"] == team["id"])
        self.assertEqual(guest_team["replyTo"], team["replyTo"])
        self.assertTrue(all(message.get("humanReason") is None for message in guest["messages"]))
        followup = self.ask("What is the weight of it?")
        self.assertIn("50 kg", followup["messages"][-1]["text"])
        self.assertEqual(followup["messages"][-1]["role"], "assistant")
        self.assertEqual(followup["needsHumanQuestions"], 1)

    def test_quote_and_resolution_survive_private_backup_and_cold_restore(self) -> None:
        question_thread = self.ask("What is the weight of STYL Sandwich J-Cups?")
        question = next(message for message in question_thread["messages"] if message["role"] == "customer")
        replied = self.reply(question, "Thanks for your question. Here is our follow-up.", question_thread["revision"])
        team = replied["messages"][-1]
        created = self.client.post("/api/admin/records/archives", headers=self.admin)
        self.assertEqual(created.status_code, 201, created.text)
        downloaded = self.client.get(f"/api/admin/records/archives/{created.json()['id']}/download", headers=self.admin)
        self.assertEqual(downloaded.status_code, 200)
        archive = self.root / "quoted-chat.zip"
        archive.write_bytes(downloaded.content)
        restored = self.root / "restored"
        records_archive.restore_archive(archive, restored)
        with closing(sqlite3.connect(restored / "support.sqlite3")) as database:
            database.row_factory = sqlite3.Row
            self.assertEqual(database.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            saved_reply = database.execute("SELECT * FROM messages WHERE id=?", (team["id"],)).fetchone()
            saved_question = database.execute("SELECT * FROM messages WHERE id=?", (question["id"],)).fetchone()
            self.assertEqual(saved_reply["reply_to_id"], question["id"])
            self.assertEqual(saved_question["answered_by_id"], team["id"])
            self.assertEqual(saved_question["needs_human"], 0)
