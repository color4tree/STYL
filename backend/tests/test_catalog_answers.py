"""SUP-015: ordinary catalog questions remain grounded without provider availability."""

import unittest
from unittest.mock import patch

from app import support_ai as ai


class CatalogAnswerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.catalog = [
            {"ref": "product:1", "type": "product", "id": 1, "name": "STYL Adjustable Bench",
             "category": "Benches", "price": 750, "currency": "CAD", "weight": "Approx. 50 kg / 110 lb",
             "shortDescription": "Adjustable training bench with padded leg rollers.", "material": "Steel",
             "publicationStatus": "published", "compatibility": {}},
            {"ref": "accessory:1001", "type": "accessory", "id": 1001, "name": "STYL Sandwich J-Cups",
             "category": "Rack attachments", "price": 119, "currency": "CAD", "weight": "",
             "shortDescription": "Sandwich-style J-cups with protective contact surfaces.",
             "sellingUnit": "Pair", "publicationStatus": "published", "compatibility": {}},
            {"ref": "product:2", "type": "product", "id": 2, "name": "PRIVATE DRAFT BENCH",
             "category": "Benches", "price": 999, "currency": "CAD", "publicationStatus": "draft"},
        ]
        network = patch.object(ai.GeminiProvider, "decide", side_effect=AssertionError("Simple catalog questions must not call Gemini."))
        self.network = network.start()
        self.addCleanup(network.stop)

    async def answer(self, question: str, history=None, topics=None, item_ref=None) -> ai.Answer:
        return await ai.respond([*(history or []), {"role": "user", "text": question}],
                                self.catalog, list(ai.TOPICS) if topics is None else topics,
                                "gemini", "gemini-3.5-flash", item_ref)

    async def test_reported_j_cups_question_uses_catalog_not_previous_operator_amount(self):
        result = await self.answer("what's price of STYL Sandwich J-Cups", [
            {"role": "user", "text": "What is the price of STYL Sandwich J-Cups?"},
            {"role": "model", "text": "ok. it is 40"},
        ])
        self.assertFalse(result.needs_human)
        self.assertEqual(result.references, ("accessory:1001",))
        self.assertIn("CAD $119.00", result.text)
        self.assertNotIn("$40", result.text)
        self.network.assert_not_called()

    async def test_reported_brand_and_weight_followup_resolve_latest_item(self):
        earlier = [
            {"role": "user", "text": "what's price of STYL Sandwich J-Cups"},
            {"role": "model", "text": "ok. it is 40"},
        ]
        brand = await self.answer("what is the brand for STYL adjustable bench", earlier)
        self.assertFalse(brand.needs_human)
        self.assertIn("brand for STYL Adjustable Bench is STYL", brand.text)
        history = [*earlier, {"role": "user", "text": "what is the brand for STYL adjustable bench"},
                   {"role": "model", "text": brand.text}]
        for question in ("what the weight of it", "what is the weight of it", "How much does it weigh?"):
            result = await self.answer(question, history)
            self.assertFalse(result.needs_human)
            self.assertIn("weighs approximately 50 kg / 110 lb", result.text)
            self.assertNotIn("$750", result.text)
            self.assertEqual(result.references, ("product:1",))

    async def test_case_punctuation_and_unique_short_names(self):
        for question in ("Price of the sandwich j cups?", "What's the price of the sandwich jcups?", "What is the weight of the adjustable bench?", "What is the weight of the bench?"):
            result = await self.answer(question)
            self.assertFalse(result.needs_human)
            self.assertTrue(result.references)

    async def test_sup015_default_styl_aliases_spacing_and_minor_typos(self):
        cases = (
            ("What's the price of the   ADJUSTABLE   BENCH?", "product:1", "CAD $750.00"),
            ("price of adjustbale bench", "product:1", "CAD $750.00"),
            ("price of adjustble bench", "product:1", "CAD $750.00"),
            ("price of bnech", "product:1", "CAD $750.00"),
            ("price of the weight bench", "product:1", "CAD $750.00"),
            ("how much is a weight-bench?", "product:1", "CAD $750.00"),
            ("price of j hooks", "accessory:1001", "CAD $119.00"),
            ("price of J-hooks", "accessory:1001", "CAD $119.00"),
            ("price of sandwich jhooks", "accessory:1001", "CAD $119.00"),
            ("price of sandiwch j cups", "accessory:1001", "CAD $119.00"),
        )
        for question, reference, expected in cases:
            with self.subTest(question=question):
                result = await self.answer(question)
                self.assertFalse(result.needs_human)
                self.assertEqual(result.references, (reference,))
                self.assertIn(expected, result.text)
                self.assertNotIn("weighs", result.text)
        self.network.assert_not_called()

    async def test_sup015_page_item_is_default_but_explicit_customer_item_wins(self):
        default = await self.answer("How much is it?", item_ref="accessory:1001")
        self.assertEqual(default.references, ("accessory:1001",))
        for question in ("What is the price of the bench?", "Price of the adjustbale bench?",
                         "What is the price of STYL Adjustable Bench?"):
            with self.subTest(question=question):
                result = await self.answer(question, item_ref="accessory:1001")
                self.assertEqual(result.references, ("product:1",))
                self.assertIn("750.00", result.text)
        result = await self.answer("Price of the bench?", item_ref="product:2")
        self.assertEqual(result.references, ("product:1",))

    async def test_sup015_unknown_brands_short_typos_and_numeric_models_never_guess(self):
        self.catalog[0]["modelSku"] = "AB-500"
        for question in ("Price of Rogue adjustable bench?", "Price of Rep bench?", "Price of jk?",
                         "Price of STYL Adjustable Bench 501?", "Price of AB-501?",
                         "Price of AB-5001?", "Price of STYL Adjustable Bench Pro?",
                         "Tell me about Rogue adjustable bench", "Do you have Rogue adjustable bench?", "Price of j?"):
            with self.subTest(question=question):
                result = await self.answer(question, item_ref="product:1")
                self.assertTrue(result.needs_human)
                self.assertEqual(result.references, ())
        exact = await self.answer("Price of AB-500?")
        self.assertEqual(exact.references, ("product:1",))
        self.catalog[0]["modelSku"] = "FRAME-500"
        result = await self.answer("Price of FRMAE-500?")
        self.assertTrue(result.needs_human)
        self.assertEqual(result.references, ())
        self.network.assert_not_called()

    async def test_sup015_mixed_shipping_question_still_uses_live_product_price(self):
        result = await self.answer("What is the price of STYL Adjustable Bench and shipping?")
        self.assertTrue(result.needs_human)
        self.assertEqual(result.references, ("product:1",))
        self.assertIn("CAD $750.00", result.text)
        self.assertIsNotNone(result.answer_plan)
        self.assertIn("service-policy part", result.text)
        self.network.assert_not_called()

    async def test_sup015_full_mock_pipeline_never_substitutes_an_explicit_foreign_brand(self):
        for question in ("Rogue bench", "Price of Rogue bench?", "Tell me about Rogue bench",
                         "Does Rogue bench recline?", "Rogue adjustable bench",
                         "What is the weight of a Rogue bench?"):
            with self.subTest(question=question):
                result = await ai.respond([{"role": "user", "text": question}], self.catalog,
                                          list(ai.TOPICS), "mock", "mock", "product:1")
                self.assertTrue(result.needs_human)
                self.assertEqual(result.references, ())
                self.assertNotIn("750.00", result.text)
                self.assertNotIn("STYL Adjustable Bench", result.text)

    async def test_sup015_full_mock_pipeline_clarifies_bare_ambiguous_short_names(self):
        self.catalog.append({"ref": "product:3", "type": "product", "id": 3,
                             "name": "STYL Flat Bench", "price": 200, "currency": "CAD"})
        for question in ("bench", "bnech"):
            with self.subTest(question=question):
                result = await ai.respond([{"role": "user", "text": question}], self.catalog,
                                          list(ai.TOPICS), "mock", "mock", "product:1")
                self.assertFalse(result.needs_human)
                self.assertIn("Which product or accessory", result.text)
                self.assertEqual(result.references, ())
                self.assertEqual(result.answer_plan["status"], "clarification")
                self.assertTrue(ai.answer_matches_plan(
                    result, ai.public_evidence(self.catalog, list(ai.TOPICS)), list(ai.TOPICS)))

    async def test_sup015_full_mock_pipeline_never_fuzzes_numeric_model_identity(self):
        self.catalog[0]["modelSku"] = "FRAME-500"
        for question in ("FRAME-501", "FRMAE-500", "Price of FRAME-501?", "What is the weight of FRAME-501?"):
            with self.subTest(question=question):
                result = await ai.respond([{"role": "user", "text": question}], self.catalog,
                                          list(ai.TOPICS), "mock", "mock", "product:1")
                self.assertTrue(result.needs_human)
                self.assertEqual(result.references, ())

    async def test_sup015_partial_and_fuzzy_ambiguity_requires_choice_without_guessing(self):
        self.catalog.append({
            "ref": "product:3", "type": "product", "id": 3, "name": "STYL Adjustable Bench Pro",
            "category": "Benches", "price": 900, "currency": "CAD", "weight": "55 kg",
        })
        for question in ("Price of the bench?", "Price of adjustable?", "Price of adjustble?",
                         "Price of bnech?"):
            with self.subTest(question=question):
                result = await self.answer(question, item_ref="product:1")
                self.assertFalse(result.needs_human)
                self.assertIn("Which product or accessory", result.text)
                self.assertEqual(result.references, ())
                self.assertEqual(result.answer_plan["status"], "clarification")
                self.assertNotIn("750.00", result.text)
        exact = await self.answer("Price of the Adjustable Bench Pro?")
        self.assertEqual(exact.references, ("product:3",))

    async def test_missing_specification_does_not_invent_or_explain_internal_failure(self):
        result = await self.answer("What is the weight of STYL Sandwich J-Cups?")
        self.assertTrue(result.needs_human)
        self.assertEqual(result.reason, "missing_evidence")
        self.assertIsNotNone(result.answer_plan)
        self.assertEqual(result.references, ("accessory:1001",))
        self.assertIn("not published", result.text)
        self.assertNotIn("weighs 50", result.text)

    async def test_ambiguous_short_name_clarifies_instead_of_choosing_an_item(self):
        self.catalog.append({
            "ref": "product:3", "type": "product", "id": 3, "name": "STYL Flat Bench",
            "category": "Benches", "price": 200, "currency": "CAD", "weight": "20 kg",
        })
        result = await self.answer("What is the weight of the bench?")
        self.assertFalse(result.needs_human)
        self.assertIn("Which product or accessory", result.text)
        self.assertEqual(result.references, ())
        self.assertEqual(result.answer_plan["status"], "clarification")
        self.assertNotIn("PRIVATE DRAFT", result.text)

    async def test_catalog_listing_and_prices_cover_all_visible_items(self):
        result = await self.answer("What products do you have?")
        self.assertFalse(result.needs_human)
        self.assertIn("STYL Adjustable Bench", result.text)
        self.assertIn("STYL Sandwich J-Cups", result.text)
        self.assertNotIn("PRIVATE DRAFT", result.text)
        result = await self.answer("List all products and prices")
        self.assertIn("CAD $750.00", result.text)
        self.assertIn("CAD $119.00", result.text)
        result = await self.answer("What do you sell?")
        self.assertIn("STYL Adjustable Bench", result.text)
        self.assertIn("STYL Sandwich J-Cups", result.text)
        result = await self.answer("Do you have benches?")
        self.assertFalse(result.needs_human)
        self.assertIn("STYL Adjustable Bench", result.text)
        self.assertNotIn("J-Cups", result.text)
        self.assertNotIn("in stock", result.text)

    async def test_current_market_and_latest_price_are_authoritative(self):
        self.catalog[1]["currency"] = "USD"
        self.catalog[1]["price"] = 99.25
        result = await self.answer("What is the price of STYL Sandwich J-Cups?")
        self.assertIn("USD $99.25", result.text)
        self.assertNotIn("CAD", result.text)

    async def test_pricing_scope_remains_enforced_without_external_calls(self):
        result = await self.answer("What is the price of STYL Sandwich J-Cups?", topics=["products"])
        self.assertTrue(result.needs_human)
        self.assertEqual(result.reason, "scope_disabled")
        self.assertNotIn("119", result.text)

    async def test_private_history_does_not_poison_future_safe_catalog_questions(self):
        result = await self.answer("What is the weight of the STYL Adjustable Bench?", [
            {"role": "user", "text": "Contact synthetic@example.com"},
            {"role": "model", "text": ai.HANDOFF_TEXT},
        ])
        self.assertFalse(result.needs_human)
        self.assertIn("50 kg", result.text)
        self.assertNotIn("synthetic@", result.text)

    async def test_product_overview_is_grounded_and_not_a_provider_dependent_handoff(self):
        result = await self.answer("Tell me about the STYL Adjustable Bench")
        self.assertFalse(result.needs_human)
        self.assertIn("padded leg rollers", result.text)
        self.assertNotIn("scope", result.text)

    async def test_missing_load_is_an_explicit_unknown_field_not_an_overview(self):
        evidence = ai.public_evidence(self.catalog, list(ai.TOPICS))
        result = ai.direct_catalog_answer(
            [{"role": "user", "text": "What is the maximum load of STYL Adjustable Bench?"}],
            evidence, list(ai.TOPICS), None,
        )
        self.assertTrue(result.needs_human)
        self.assertEqual(result.reason, "missing_evidence")
        self.assertIsNotNone(result.answer_plan)
        self.assertEqual(result.answer_plan["items"][0]["fields"][0]["key"], "capacity.safeLoad")
        self.assertNotIn("padded leg rollers", result.text)

    async def test_unknown_or_hidden_named_product_is_not_replaced_with_a_similar_public_item(self):
        self.catalog.append({"ref": "product:4", "type": "product", "id": 4, "name": "STYL Bench",
                             "category": "Benches", "price": 100, "currency": "CAD", "weight": "10 kg"})
        evidence = ai.public_evidence(self.catalog, list(ai.TOPICS))
        for question in ("What is the weight of a Rogue bench?", "What is the weight of PRIVATE DRAFT BENCH?"):
            result = ai.direct_catalog_answer([{"role": "user", "text": question}], evidence, list(ai.TOPICS), None)
            self.assertIsNone(result)
            result = ai.direct_catalog_answer([
                {"role": "user", "text": "Tell me about STYL Adjustable Bench"},
                {"role": "user", "text": question},
            ], evidence, list(ai.TOPICS), "product:1")
            self.assertIsNone(result)

    async def test_delayed_team_reply_to_older_question_does_not_retarget_followup(self):
        history = [
            {"role": "user", "text": "What is the weight of STYL Sandwich J-Cups?"},
            {"role": "model", "text": ai.HANDOFF_TEXT},
            {"role": "user", "text": "What is the brand for STYL Adjustable Bench?"},
            {"role": "model", "text": "STYL Adjustable Bench\nBrand: STYL"},
            {"role": "model", "text": "Reply to earlier question: What is the weight of STYL Sandwich J-Cups?\nTeam reply: We will confirm the J-cups weight."},
        ]
        result = await self.answer("What is the weight of it?", history)
        self.assertFalse(result.needs_human)
        self.assertEqual(result.references, ("product:1",))
        self.assertIn("50 kg", result.text)

    async def test_replies_are_conversational_sentences_without_changing_facts(self):
        price = await self.answer("What is the price of STYL Sandwich J-Cups?")
        self.assertEqual(price.text, "The current listed price for STYL Sandwich J-Cups is CAD $119.00.")
        weight = await self.answer("What is the weight of STYL Adjustable Bench?")
        self.assertEqual(weight.text, "STYL Adjustable Bench weighs approximately 50 kg / 110 lb.")
        brand = await self.answer("What brand is STYL Adjustable Bench?")
        self.assertEqual(brand.text, "The brand for STYL Adjustable Bench is STYL.")
        overview = await self.answer("Tell me about STYL Adjustable Bench")
        self.assertIn("Here is an overview of STYL Adjustable Bench", overview.text)
        for answer in (price, weight, brand, overview):
            self.assertNotIn("Category:", answer.text)
            self.assertTrue(answer.text.endswith("."))
            self.assertTrue(answer.references)


if __name__ == "__main__":
    unittest.main()
