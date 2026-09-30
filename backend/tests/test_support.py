"""CS-001..020: isolated support API, private records and fenced worker coverage."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
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

    def action(self, conversation: dict, action: str):
        return self.client.post(f"{self.admin_base}/{conversation['id']}/action", headers=self.admin,
                                json={"action": action, "expectedRevision": conversation["revision"]})

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

    def test_invalid_path_guards_and_admin_auth_matrix(self) -> None:
        identifier = "a" * 32
        for method, path, body in (
            ("GET", "/api/admin/support/config", None),
            ("PUT", "/api/admin/support/config", {"enabled": False, "allowedTopics": ["products"], "expectedRevision": 0}),
            ("GET", self.admin_base, None), ("GET", f"{self.admin_base}/{identifier}", None),
            ("POST", f"{self.admin_base}/{identifier}/action", {"action": "takeover", "expectedRevision": 0}),
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
                         "Hello! I can help with current market prices. Which item would you like to discuss?")

    def test_arbitrary_citation_free_provider_text_cannot_use_greeting_exception(self) -> None:
        self.save_settings(True, ["pricing"])
        conversation, headers = self.create()
        self.send(conversation, headers, "Hello", item_ref=None)
        self.answer.references = ()
        self.answer.text = "Every synthetic item is free; no citation is needed."
        self.process()
        result = self.get(conversation, headers)
        self.assertEqual(result["state"], "waiting_human")
        self.assertEqual(result["reason"], "missing_information")
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
        self.assertEqual(result["reason"], "missing_information")
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
                self.assertEqual(current["reason"], "catalog_changed")
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
        self.assertEqual(result["reason"], "catalog_unavailable")
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
                self.assertEqual(result["reason"], "catalog_unavailable" if change == "unavailable" else "catalog_changed")
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
            result = self.send(conversation, headers, item_ref=item_ref)
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["state"], "waiting_human")
            self.assertEqual(result.json()["reason"], "missing_information")
            self.assertTrue(result.json()["needsHuman"])
            self.assertFalse(result.json()["processing"])
        conversation, headers = self.create()
        with patch.object(main, "load_products", side_effect=HTTPException(503, "synthetic catalog error")):
            result = self.send(conversation, headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["reason"], "catalog_unavailable")
        self.provider.assert_not_called()

    def test_settings_full_validation_cas_and_disabled_ai_still_saves_messages(self) -> None:
        original = self.settings()
        self.assertEqual(original["allowedTopics"], list(support.TOPICS))
        self.assertIsInstance(original["configured"], bool)
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
        result = self.send(conversation, headers)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["state"], "waiting_human")
        self.assertEqual(result.json()["messages"][0]["role"], "customer")
        self.assertFalse(self.process())
        self.provider.assert_not_called()

    def test_human_takeover_reply_attention_explicit_resume_and_close(self) -> None:
        conversation, headers = self.create()
        original = self.send(conversation, headers).json()
        self.assertEqual(self.action(conversation, "takeover").status_code, 409)
        taken = self.action(original, "takeover").json()
        self.assertEqual(taken["state"], "human")
        self.assertFalse(taken["processing"])
        self.assertTrue(taken["needsHuman"])
        self.assertFalse(self.process())
        body = {"text": "Synthetic human response", "clientMessageId": "human-1", "expectedRevision": taken["revision"]}
        result = self.client.post(f"{self.admin_base}/{taken['id']}/messages", headers=self.admin, json=body)
        self.assertEqual(result.status_code, 200, result.text)
        reply = result.json()
        self.assertEqual(reply["state"], "human")
        self.assertFalse(reply["needsHuman"])
        self.assertEqual(self.client.post(f"{self.admin_base}/{taken['id']}/messages",
                                         headers=self.admin, json=body).json(), reply)
        refreshed = self.get(conversation, headers)
        retry = self.client.post(f"{self.admin_base}/{taken['id']}/messages", headers=self.admin,
                                 json={**body, "expectedRevision": refreshed["revision"]})
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json(), reply)
        self.assertEqual(len([message for message in self.get(conversation, headers)["messages"]
                              if message["role"] == "human"]), 1)
        self.assertEqual(self.client.get(self.admin_base, headers=self.admin).json()["needsHumanCount"], 0)
        customer = self.send(conversation, headers, "Synthetic follow-up", "next").json()
        self.assertTrue(customer["needsHuman"])
        self.assertEqual(customer["state"], "human")
        self.assertFalse(customer["processing"])
        inbox = self.client.get(self.admin_base, headers=self.admin).json()
        self.assertEqual(inbox["needsHumanCount"], 1)
        self.assertEqual(inbox["items"][0]["lastMessage"], "Synthetic follow-up")
        self.assertTrue(inbox["items"][0]["guestLabel"].startswith("Guest "))
        resumed = self.action(customer, "resume_ai").json()
        self.assertEqual(resumed["state"], "ai")
        self.assertFalse(resumed["needsHuman"])
        self.assertFalse(resumed["processing"])  # Explicit resume enables the next message; no replay.
        queued = self.send(conversation, headers, client_id="after-resume").json()
        closed = self.action(queued, "close").json()
        self.assertEqual(closed["state"], "closed")
        self.assertEqual(self.send(closed, headers, client_id="after-close").status_code, 409)
        self.assertEqual(self.action(closed, "resume_ai").status_code, 409)
        self.assertFalse(self.process())
        self.provider.assert_not_called()

    def test_human_reply_requires_ownership_and_current_revision(self) -> None:
        conversation, headers = self.create()
        url = f"{self.admin_base}/{conversation['id']}/messages"
        body = {"text": "Synthetic", "clientMessageId": "h-1", "expectedRevision": 0}
        self.assertEqual(self.client.post(url, headers=self.admin, json=body).status_code, 409)
        taken = self.action(conversation, "takeover").json()
        self.assertEqual(self.client.post(url, headers=self.admin, json=body).status_code, 409)
        body["expectedRevision"] = taken["revision"]
        self.assertEqual(self.client.post(url, headers=self.admin, json=body).status_code, 200)
        body["text"] = "Different synthetic"
        self.assertEqual(self.client.post(url, headers=self.admin, json=body).status_code, 409)
        self.save_settings(False)
        current = self.get(conversation, headers)
        self.assertEqual(self.action(current, "resume_ai").status_code, 409)

    def test_guest_handoff_fences_queued_job_and_prevents_automatic_resume(self) -> None:
        conversation, headers = self.create()
        sent = self.send(conversation, headers).json()
        result = self.client.post(f"{self.base}/{conversation['id']}/handoff", headers=headers, json={})
        handoff = result.json()
        self.assertGreater(handoff["revision"], sent["revision"])
        self.assertEqual(handoff["state"], "waiting_human")
        self.assertEqual(handoff["reason"], "customer_request")
        self.assertTrue(handoff["needsHuman"])
        self.assertFalse(self.process())
        later = self.send(conversation, headers, client_id="later").json()
        self.assertEqual(later["state"], "waiting_human")
        self.assertFalse(later["processing"])
        self.provider.assert_not_called()

    def test_provider_failures_and_unsupported_topics_are_sanitized_human_cases(self) -> None:
        for outcome in ("exception", "missing_information", "out_of_scope", "customer_request",
                        "compatibility_unverified", "invalid_reference", "topic"):
            with self.subTest(outcome=outcome):
                conversation, headers = self.create()
                self.send(conversation, headers)
                self.provider.side_effect = RuntimeError("PRIVATE_PROVIDER_SECRET") if outcome == "exception" else None
                answer = deepcopy(self.answer)
                if outcome in ("missing_information", "out_of_scope", "customer_request", "compatibility_unverified"):
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
                self.assertNotIn("PRIVATE_PROVIDER_SECRET", json.dumps(result))
                if outcome == "compatibility_unverified":
                    self.assertEqual(result["reason"], "compatibility_unverified")

    def test_late_answer_cannot_change_human_ownership_close_or_settings(self) -> None:
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
            if kind == "handoff":
                changed = self.client.post(f"{self.base}/{conversation['id']}/handoff", headers=headers, json={}).json()
            elif kind in ("close", "takeover"):
                changed = self.action(sent, kind).json()
            else:
                self.assertEqual(self.save_settings(kind != "disable", ["products"]).status_code, 200)
                changed = self.get(conversation, headers)
            release.set()
            await worker
            result = self.get(conversation, headers)
            self.assertEqual(result, changed)
            self.assertFalse(any(message["role"] == "assistant" for message in result["messages"]))

        for kind in ("handoff", "takeover", "close", "topics", "disable"):
            with self.subTest(kind=kind):
                asyncio.run(scenario(kind))
        self.assertEqual(self.provider.await_count, 5)

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
        self.assertEqual(result["reason"], "interrupted")
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
            self.assertEqual(self.get(conversation, headers)["reason"], "interrupted")
            self.assertFalse(await support.process_one())

        asyncio.run(scenario())
        self.provider.assert_awaited_once()

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
                    self.assertEqual(current["reason"], "interrupted")
                    self.assertFalse(current["processing"])
                    self.provider.assert_awaited_once()
                finally:
                    task.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

        asyncio.run(storage_recovery())


if __name__ == "__main__":
    unittest.main()
