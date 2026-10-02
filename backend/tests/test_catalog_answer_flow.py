"""SUP-015: real catalog answers continue through a pending human-support request."""

import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app import main, support, support_ai


class CatalogAnswerFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="styl-catalog-answer-flow-")
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
                "GEMINI_API_KEY": "", "GOOGLE_API_KEY": "",
            }),
            patch.multiple(main, DATA_PATH=products, ACCESSORIES_PATH=accessories, ADMIN_TOKEN="catalog-answer-test-only"),
            patch.object(support_ai.GeminiProvider, "decide", side_effect=AssertionError("Verified catalog facts must not depend on the provider.")),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        with support.rate_lock:
            support.rate_windows.clear()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        created = self.client.post("/api/support/conversations", json={})
        self.assertEqual(created.status_code, 201, created.text)
        value = created.json()
        self.url = "/api/support/conversations/" + value["conversation"]["id"]
        self.guest = {"Authorization": "Bearer " + value["token"]}
        self.admin = {"Authorization": "Bearer catalog-answer-test-only"}

    def ask(self, text: str) -> dict:
        response = self.client.post(self.url + "/messages", headers=self.guest,
                                    json={"clientMessageId": uuid4().hex, "text": text})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(asyncio.run(support.process_one()))
        return self.client.get(self.url, headers=self.guest).json()

    def test_reported_question_sequence_works_with_no_provider_key_after_handoff(self) -> None:
        requested = self.client.post(self.url + "/handoff", headers=self.guest, json={})
        self.assertEqual(requested.status_code, 200, requested.text)
        for question, expected in (
            ("what's price of STYL Sandwich J-Cups", "CAD $119.00"),
            ("what is the brand for STYL adjustable bench", "brand for STYL Adjustable Bench is STYL"),
            ("what the weight of it", "approximately 50 kg / 110 lb"),
            ("what is the weight of it", "approximately 50 kg / 110 lb"),
        ):
            with self.subTest(question=question):
                conversation = self.ask(question)
                self.assertEqual(conversation["state"], "waiting_human")
                self.assertTrue(conversation["needsHuman"])
                self.assertIsNone(conversation["reason"])
                self.assertEqual(conversation["messages"][-1]["role"], "assistant")
                self.assertIn(expected, conversation["messages"][-1]["text"])
        admin_thread = self.client.get(self.url.replace("/api/support/", "/api/admin/support/"), headers=self.admin).json()
        self.assertEqual(admin_thread["reason"], "customer_request")
        self.assertEqual(sum(message["text"] == support.HELP_TEXT for message in admin_thread["messages"]), 1)

    def test_old_provider_failure_does_not_disable_new_basic_catalog_answers(self) -> None:
        failed = self.ask("Compare the STYL Adjustable Bench with another option.")
        self.assertTrue(failed["needsHuman"])
        conversation = self.ask("What is the weight of STYL Adjustable Bench?")
        self.assertIn("50 kg", conversation["messages"][-1]["text"])
        self.assertTrue(conversation["needsHuman"])
        self.assertIsNone(conversation["reason"])
        admin_thread = self.client.get(self.url.replace("/api/support/", "/api/admin/support/"), headers=self.admin).json()
        self.assertEqual(admin_thread["reason"], "provider_unavailable")
