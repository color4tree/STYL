"""SUP-027/028: publish validated partial facts, retaining team attention and scoped state."""

import asyncio
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app import catalog_answers, main, support, support_ai


class CatalogPlanPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="styl-catalog-plan-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.products = self.root / "products.json"
        self.data = [
            {"id": 1, "slug": "synthetic-bench", "name": "STYL Synthetic Bench", "category": "Benches",
             "prices": {"CAD": 125.50, "USD": 100.25}, "publicationStatus": "published", "colourOptions": "Teal",
             "material": "Steel", "weight": "", "description": "Synthetic benchmark."},
            {"id": 2, "slug": "synthetic-rack", "name": "STYL Synthetic Rack", "category": "Racks",
             "prices": {"CAD": 400, "USD": 300}, "publicationStatus": "published", "colourOptions": "Red",
             "material": "Steel", "weight": "Approx. 50 kg / 110 lb", "description": "Synthetic rack.",
             "compatibility": {"uprightSize": "3 × 3 in / 75 × 75 mm", "holeDiameter": "1 in"}},
        ]
        self.products.write_text(json.dumps(self.data))
        accessories = self.root / "accessories.json"
        accessories.write_text("[]")
        for replacement in (
            patch.dict(os.environ, {
                "STYL_SUPPORT_ENABLED": "true", "STYL_SUPPORT_ENVIRONMENT": "test",
                "STYL_SUPPORT_PROVIDER": "mock", "STYL_SUPPORT_MODEL": "mock",
                "STYL_SUPPORT_DB": str(self.root / "support.sqlite3"),
                "STYL_ANALYTICS_DB": str(self.root / "analytics.sqlite3"), "STYL_ANALYTICS_ENVIRONMENT": "test",
                "STYL_KNOWLEDGE_DIR": str(self.root / "knowledge"), "OPENAI_API_KEY": "", "GEMINI_API_KEY": "",
            }),
            patch.multiple(main, DATA_PATH=self.products, ACCESSORIES_PATH=accessories,
                           ADMIN_TOKEN="catalog-plan-test-only"),
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
        self.identifier = value["conversation"]["id"]
        self.url = "/api/support/conversations/" + self.identifier
        self.guest = {"Authorization": "Bearer " + value["token"]}
        self.admin = {"Authorization": "Bearer catalog-plan-test-only"}

    def ask(self, text, ref=None, stamp="page-a"):
        response = self.client.post(self.url + "/messages", headers=self.guest, json={
            "clientMessageId": uuid4().hex, "text": text, "itemRef": ref, "pageContextVersion": stamp,
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(asyncio.run(support.process_one()))
        return self.client.get(self.url, headers=self.guest).json()

    def latest_plan(self):
        with support.get_store().connection() as db:
            row = db.execute("SELECT answer_plan_json FROM jobs WHERE conversation_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (self.identifier,)).fetchone()
            return json.loads(row[0]) if row[0] else None

    def test_price_survives_missing_weight_and_question_remains_for_team(self):
        thread = self.ask("What is the price and weight?", "product:1")
        replies = [message for message in thread["messages"] if message["role"] == "assistant"]
        self.assertEqual(len(replies), 1)
        self.assertIn("CAD $125.50", replies[0]["text"])
        self.assertTrue(thread["needsHuman"])
        self.assertEqual(thread["needsHumanQuestions"], 1)
        self.assertEqual(self.latest_plan()["status"], "partial")
        self.assertEqual(replies[0]["references"][0]["id"], 1)
        self.assertNotIn("answer_plan_json", json.dumps(thread))

    def test_direct_requirements_answer_without_customer_rack_model_or_team_flag(self):
        thread = self.ask("What are the compatible upright size and hole diameter?", "product:2")
        self.assertFalse(thread["needsHuman"])
        self.assertEqual(thread["messages"][-1]["role"], "assistant")
        plan = self.latest_plan()
        self.assertEqual(plan["items"][0]["compatibility"]["status"], "listed_requirements")
        self.assertIn("75", thread["messages"][-1]["text"])
        self.assertIn("1", thread["messages"][-1]["text"])

    def test_direct_requirement_grammar_variants_are_not_personal_fit_checks(self):
        for question in (
            "what the compatible upright size",
            "What is the compatible upright size of STYL Synthetic Rack?",
            "Which rack post size does STYL Synthetic Rack require?",
        ):
            with self.subTest(question=question):
                thread = self.ask(question, "product:2")
                self.assertFalse(thread["needsHuman"])
                self.assertEqual(self.latest_plan()["items"][0]["compatibility"]["status"], "listed_requirements")
                self.assertNotIn("your equipment", thread["messages"][-1]["text"])

    def test_capacity_is_not_product_own_weight_and_known_weight_survives(self):
        thread = self.ask("What is the weight and safe load?", "product:2")
        response = next(message for message in thread["messages"] if message["role"] == "assistant")
        self.assertIn("50", response["text"])
        self.assertTrue(thread["needsHuman"])
        fields = {field["key"]: field for item in self.latest_plan()["items"] for field in item["fields"]}
        self.assertEqual(fields["weight.own"]["status"], "answered")
        self.assertEqual(fields["capacity.safeLoad"]["status"], "unknown")

    def test_tampered_answer_text_cannot_use_a_valid_plan_as_permission(self):
        original = support_ai.respond

        async def tampered(**payload):
            answer = await original(**payload)
            return replace(answer, text=answer.text + " Guaranteed safe load is 9999 kg.")

        with patch.object(support_ai, "respond", side_effect=tampered):
            thread = self.ask("What color is it?", "product:1")
        self.assertFalse(any(message["role"] == "assistant" for message in thread["messages"]))
        self.assertNotIn("9999", json.dumps(thread))
        self.assertIsNone(self.latest_plan())

    def test_fact_changed_during_planning_prevents_stale_partial_publication(self):
        original = support_ai.respond

        async def changed(**payload):
            answer = await original(**payload)
            self.data[0]["prices"]["CAD"] = 175.50
            self.products.write_text(json.dumps(self.data))
            return answer

        with patch.object(support_ai, "respond", side_effect=changed):
            thread = self.ask("What is the price and weight?", "product:1")
        self.assertFalse(any(message["role"] == "assistant" for message in thread["messages"]))
        self.assertNotIn("125.50", json.dumps(thread))
        self.assertTrue(thread["needsHuman"])

    def test_scoped_hole_followup_continues_but_navigation_stamp_does_not(self):
        initial = self.ask("Will this fit a 3x3 upright?", "product:2")
        self.assertFalse(initial["needsHuman"])
        self.assertTrue(self.latest_plan()["pendingSlots"])
        completed = self.ask("1 inch", "product:2")
        self.assertFalse(completed["needsHuman"])
        self.assertFalse(self.latest_plan()["pendingSlots"])
        self.assertNotIn("guaranteed", completed["messages"][-1]["text"].lower())
        self.ask("Will this fit a 3x3 upright?", "product:2")
        changed = self.ask("1 inch", "product:1", stamp="page-b")
        self.assertNotIn("requirements_match_not_verified", json.dumps(self.latest_plan()))
        self.assertNotIn("STYL Synthetic Rack", changed["messages"][-1]["text"])

    def test_compound_known_product_fact_survives_missing_general_policy(self):
        thread = self.ask("What color is the STYL Synthetic Bench and what is your return policy?", "product:1")
        responses = [message for message in thread["messages"] if message["role"] == "assistant"]
        self.assertEqual(len(responses), 1)
        self.assertIn("Teal", responses[0]["text"])
        self.assertTrue(thread["needsHuman"])
        self.assertIn("servicePart", self.latest_plan())

    def test_page_context_preserved_for_catalog_part_of_compound_policy_question(self):
        thread = self.ask("What color is this and what is your return policy?", "product:1")
        responses = [message for message in thread["messages"] if message["role"] == "assistant"]
        self.assertEqual(len(responses), 1)
        self.assertIn("Teal", responses[0]["text"])
        self.assertTrue(thread["needsHuman"])

    def test_explicit_current_product_overrides_stale_page_reference(self):
        thread = self.ask("What color is the STYL Synthetic Bench?", "product:99999")
        self.assertEqual(thread["messages"][-1]["role"], "assistant")
        self.assertIn("Teal", thread["messages"][-1]["text"])
        self.assertFalse(thread["needsHuman"])

    def test_pin_dimension_is_not_answered_using_the_hole_requirement(self):
        thread = self.ask("What is the pin diameter?", "product:2")
        fields = {field["key"]: field for item in self.latest_plan()["items"] for field in item["fields"]}
        self.assertEqual(fields["compat.pinDiameter"]["status"], "unknown")
        self.assertNotIn("compat.holeDiameter", fields)
        self.assertTrue(thread["needsHuman"])
        self.assertNotIn("holeDiameter", catalog_answers.parse_customer_slots("3x3 uprights with 1 inch pins"))

    def test_explicit_description_and_overview_do_not_need_provider_selection(self):
        with patch.object(support_ai.MockProvider, "decide", side_effect=RuntimeError("No model should be needed")):
            thread = self.ask("What is the description of STYL Synthetic Bench?", "product:1")
        self.assertFalse(thread["needsHuman"])
        self.assertIn("Synthetic benchmark.", thread["messages"][-1]["text"])
        self.assertEqual(self.latest_plan()["items"][0]["fields"][0]["key"], "description")

    def test_duplicate_display_names_use_the_selected_page_without_merging_records(self):
        self.data.append({**self.data[0], "id": 3, "slug": "other-bench",
                          "prices": {"CAD": 222, "USD": 180}, "colourOptions": "Blue"})
        self.products.write_text(json.dumps(self.data))
        first = self.ask("What color is STYL Synthetic Bench?", "product:1")
        self.assertIn("Teal", first["messages"][-1]["text"])
        self.assertNotIn("Blue", first["messages"][-1]["text"])
        second = self.ask("What color is STYL Synthetic Bench?", "product:3", stamp="page-b")
        self.assertIn("Blue", second["messages"][-1]["text"])
        self.assertNotIn("Teal", second["messages"][-1]["text"])

    def test_lower_msrp_is_a_fact_without_a_discount_claim(self):
        self.data[0]["msrps"] = {"CAD": 100, "USD": 90}
        self.products.write_text(json.dumps(self.data))
        thread = self.ask("What is the MSRP?", "product:1")
        self.assertFalse(thread["needsHuman"])
        self.assertIn("CAD", thread["messages"][-1]["text"])
        self.assertIn("100.00", thread["messages"][-1]["text"])
        self.assertNotIn("discount", thread["messages"][-1]["text"].lower())

    def test_negated_or_other_component_claims_never_become_product_specifications(self):
        for description, question, key in (
            ("This bench is not rated for 500 kg.", "What is the safe load?", "capacity.safeLoad"),
            ("The manufacturer does not specify that the hole diameter is 25 mm.", "What is the hole diameter?", "compat.holeDiameter"),
            ("The optional weight plate weighs 20 kg.", "What is the own weight?", "weight.own"),
        ):
            with self.subTest(description=description):
                self.data[0]["description"] = description
                self.products.write_text(json.dumps(self.data))
                thread = self.ask(question, "product:1")
                plan = self.latest_plan()
                fields = {field["key"]: field for item in plan["items"] for field in item["fields"]}
                self.assertEqual(fields[key]["status"], "unknown")
                self.assertTrue(thread["needsHuman"])

    def test_missing_component_does_not_erase_known_component_material(self):
        self.data[0]["materialParts"] = {"handle": "Rubber"}
        self.products.write_text(json.dumps(self.data))
        thread = self.ask("What are the frame and handle materials?", "product:1")
        replies = [message for message in thread["messages"] if message["role"] == "assistant"]
        self.assertEqual(len(replies), 1)
        self.assertIn("Rubber", replies[0]["text"])
        self.assertIn("frame", replies[0]["text"].lower())
        self.assertTrue(thread["needsHuman"])
        self.assertEqual(self.latest_plan()["status"], "partial")

    def test_leaving_detail_preserves_prior_verified_identity_without_reusing_measurement_slots(self):
        self.ask("How much?", "product:1")
        thread = self.ask("What is its price?", stamp="home-page")
        self.assertEqual(thread["messages"][-1]["role"], "assistant")
        self.assertIn("125.50", thread["messages"][-1]["text"])
        self.assertEqual(thread["messages"][-1]["references"][0]["id"], 1)
        self.assertFalse(thread["needsHuman"])

    def test_delayed_team_quote_cannot_retarget_prior_verified_identity(self):
        initial = self.ask("How much?", "product:1")
        older = next(message for message in initial["messages"] if message["role"] == "customer")
        latest = self.ask("How much?", "product:2", stamp="page-b")
        reply = self.client.post(self.url.replace("/api/support/", "/api/admin/support/") + "/messages",
                                 headers=self.admin, json={"clientMessageId": uuid4().hex, "text": "STYL Synthetic Bench follow-up.",
                                 "replyToMessageId": older["id"], "expectedAnsweredBy": older["answeredBy"],
                                 "expectedRevision": latest["revision"]})
        self.assertEqual(reply.status_code, 200, reply.text)
        thread = self.ask("What is its price?", stamp="home-page")
        self.assertIn("400.00", thread["messages"][-1]["text"])
        self.assertNotIn("125.50", thread["messages"][-1]["text"])

    def test_named_pin_measurement_cannot_fill_a_pending_hole_slot(self):
        self.ask("Will this fit a 3x3 upright?", "product:2")
        thread = self.ask("1 inch pins", "product:2")
        plan = self.latest_plan()
        for item in (plan or {}).get("items", []):
            self.assertNotIn((item.get("compatibility") or {}).get("status"),
                             ("requirements_match_not_verified", "conditional_match"))
        self.assertNotIn("consistent with the listed requirements", thread["messages"][-1]["text"])
