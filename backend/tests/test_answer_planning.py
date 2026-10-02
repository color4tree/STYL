"""SUP-017: owner-reviewable catalog-wide accuracy cases; no live providers."""

from copy import deepcopy
from dataclasses import replace
import os
import unittest
from unittest.mock import AsyncMock, patch

from app import catalog_answers, support_ai as ai


BENCHMARK_ITEMS = (
    ("product", "STYL Alpine Bench", "Benches"),
    ("product", "STYL Summit Rack", "Racks"),
    ("product", "STYL Cedar Barbell", "Bars"),
    ("product", "STYL Harbor Dumbbell", "Weights"),
    ("product", "STYL Valley Kettlebell", "Weights"),
    ("accessory", "STYL Aurora Dip Attachment", "Rack attachments"),
    ("accessory", "STYL Meridian J-Cups", "Rack attachments"),
    ("accessory", "STYL Birch Cable Handle", "Handles"),
    ("accessory", "STYL Grove Storage Peg", "Storage"),
    ("accessory", "STYL Hazel Safety Arm", "Rack attachments"),
)
# Ten independent questions for each equipment/accessory item, visible for owner review.
BENCHMARK_FIELDS = (
    ("price", "What is the price of {name}?", "CAD $"),
    ("weight", "How much does {name} weigh?", "12 kg"),
    ("material", "What is {name} made from?", "Powder-coated steel"),
    ("colourOptions", "What colors are listed for {name}?", "Black / red"),
    ("dimensions", "What are the dimensions of {name}?", "100 x 40 x 30 cm"),
    ("included", "What comes with {name}?", "Mounting hardware"),
    ("sellingUnit", "Is {name} sold as a pair or individually?", "pair"),
    ("packageQuantity", "What is the package quantity of {name}?", "2"),
    ("modelSku", "What is the SKU for {name}?", "SYN-"),
    ("warranty", "What warranty is published for {name}?", "Frame warranty: one year"),
)


def fixture_catalog():
    return [
        {
            "ref": f"{kind}:{index}", "type": kind, "id": index, "name": name,
            "category": category, "publicationStatus": "published",
            "price": 100 + index + .25, "currency": "CAD",
            "weight": "12 kg", "material": "Powder-coated steel",
            "colourOptions": "Black / red", "dimensions": "100 x 40 x 30 cm",
            "included": "Mounting hardware", "sellingUnit": "Pair", "packageQuantity": 2,
            "modelSku": f"SYN-{index:03}", "warranty": "Frame warranty: one year",
            "shortDescription": "Published synthetic catalog overview.",
            "features": ["Rounded contact surfaces", "Adjustable mounting position"],
            "compatibility": {"uprightSize": "75 x 75 mm", "holeDiameter": "25 mm",
                              "models": "STYL Summit Rack", "limitations": "Check the rack version."},
        }
        for index, (kind, name, category) in enumerate(BENCHMARK_ITEMS, 1)
    ]


class AnswerPlanningTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.catalog = fixture_catalog()
        self.calls = []
        for provider in (ai.OpenAIProvider, ai.GeminiProvider):
            mocked = patch.object(provider, "decide", new_callable=AsyncMock,
                                  side_effect=AssertionError("Deterministic fields must not call a provider."))
            self.calls.append(mocked.start())
            self.addCleanup(mocked.stop)

    async def answer(self, question, *, catalog=None, item_ref=None, pending_context=None, topics=None,
                     general_knowledge=None):
        return await ai.respond(
            [{"role": "user", "text": question}], self.catalog if catalog is None else catalog,
            list(ai.TOPICS) if topics is None else topics, "openai", "gpt-6-luna", item_ref,
            general_knowledge, pending_context,
        )

    async def test_sup017_owner_reviewable_hundred_question_benchmark(self):
        count = 0
        for item in self.catalog:
            for field, template, expected in BENCHMARK_FIELDS:
                question = template.format(name=item["name"])
                with self.subTest(case=f"SUP-017-{count + 1:03}", question=question, field=field):
                    result = await self.answer(question)
                    self.assertFalse(result.needs_human, result.text)
                    self.assertEqual(result.references, (item["ref"],))
                    self.assertIn(expected, result.text)
                    self.assertIsInstance(result.answer_plan, dict)
                    self.assertTrue(catalog_answers.validate_plan(
                        result.answer_plan, ai.public_evidence(self.catalog, list(ai.TOPICS)), list(ai.TOPICS)))
                count += 1
        self.assertEqual(count, 100)
        for provider in self.calls:
            provider.assert_not_called()

    async def test_sup017_price_survives_missing_weight_for_every_catalog_kind(self):
        for item in self.catalog:
            catalog = deepcopy(self.catalog)
            target = next(value for value in catalog if value["ref"] == item["ref"])
            target["weight"] = ""
            with self.subTest(item=item["name"]):
                result = await self.answer(f"What are the price and weight of {item['name']}?", catalog=catalog)
                self.assertTrue(result.needs_human)
                self.assertEqual(result.references, (item["ref"],))
                self.assertIn(f"${item['price']:,.2f}", result.text)
                self.assertNotIn("weighs 12 kg", result.text)
                self.assertIsInstance(result.answer_plan, dict)

    async def test_sup017_weight_and_load_are_distinct_requests(self):
        for field in ("load", "maximum load"):
            with self.subTest(field=field):
                result = await self.answer(f"What are the weight and {field} of STYL Alpine Bench?")
                self.assertIn("12 kg", result.text)
                self.assertTrue(result.needs_human)
                self.assertNotIn("maximum load is 12 kg", result.text)
                self.assertIsNotNone(result.answer_plan)
                fields = {fact["key"] for item in result.answer_plan["items"] for fact in item["fields"]}
                self.assertEqual(fields, {"weight.own", "capacity.safeLoad"})

    async def test_sup017_per_clause_fields_do_not_cross_product_associations(self):
        self.catalog[0].update(colourOptions="Blue", material="Aluminium")
        self.catalog[1].update(colourOptions="Green", material="Carbon steel")
        result = await self.answer("What color is STYL Alpine Bench and what material is STYL Summit Rack?")
        self.assertFalse(result.needs_human, result.text)
        self.assertEqual(set(result.references), {"product:1", "product:2"})
        self.assertIn("Blue", result.text)
        self.assertIn("Carbon steel", result.text)
        self.assertNotIn("Green", result.text)
        self.assertNotIn("Aluminium", result.text)
        routed = ai.render(
            ai.Decision(topic="products", references=["product:1", "product:2"],
                        fields=["colourOptions", "material"], needsHuman=False, requestedModel=""),
            ai.public_evidence(self.catalog, list(ai.TOPICS)), list(ai.TOPICS),
            "What color is STYL Alpine Bench and what material is STYL Summit Rack?", {},
        )
        self.assertEqual(routed.text, result.text)
        self.assertEqual(routed.references, result.references)

    async def test_sup017_compare_colors_and_materials_for_both_named_products(self):
        self.catalog[0].update(colourOptions="Blue", material="Aluminium")
        self.catalog[1].update(colourOptions="Green", material="Carbon steel")
        result = await self.answer("Compare the colors and materials of STYL Alpine Bench and STYL Summit Rack")
        self.assertFalse(result.needs_human, result.text)
        self.assertEqual(set(result.references), {"product:1", "product:2"})
        for expected in ("Blue", "Aluminium", "Green", "Carbon steel"):
            self.assertIn(expected, result.text)

    async def test_sup017_requirements_do_not_require_a_customer_rack_model(self):
        for item in self.catalog:
            with self.subTest(item=item["name"]):
                result = await self.answer(f"What upright size and hole diameter are listed for {item['name']}?")
                self.assertFalse(result.needs_human, result.text)
                self.assertIn("75 x 75 mm", result.text)
                self.assertIn("25 mm", result.text)
                self.assertNotIn("flagged", result.text)

    async def test_sup017_page_context_resolves_new_registry_questions_not_just_legacy_words(self):
        cases = [
            ("What are the compatible upright size and hole diameter?", ("75 x 75 mm", "25 mm")),
            ("What are the package quantity and selling unit?", ("2", "pair")),
            ("What is the published product warranty?", ("Frame warranty: one year",)),
            ("What is included in the box?", ("Mounting hardware",)),
        ]
        for question, expected in cases:
            with self.subTest(question=question):
                result = await self.answer(question, item_ref="product:2")
                self.assertFalse(result.needs_human, result.text)
                self.assertEqual(result.references, ("product:2",))
                for value in expected:
                    self.assertIn(value, result.text)
                self.assertIsNotNone(result.answer_plan)

    async def test_sup017_missing_customer_slots_clarify_without_team_request(self):
        result = await self.answer("Will STYL Aurora Dip Attachment fit my rack?")
        self.assertFalse(result.needs_human, result.text)
        self.assertIn("75 x 75 mm", result.text)
        self.assertIn("25 mm", result.text)
        self.assertIn("?", result.text)
        self.assertNotIn(ai.HANDOFF_TEXT, result.text)
        self.assertTrue(result.answer_plan["pendingSlots"])

    async def test_sup017_new_named_product_drops_pending_attachment_slots(self):
        first = await self.answer("Will STYL Aurora Dip Attachment fit my rack?")
        next_answer = await self.answer(
            "What is the price of STYL Alpine Bench?", item_ref="product:1",
            pending_context=first.answer_plan,
        )
        self.assertFalse(next_answer.needs_human)
        self.assertEqual(next_answer.references, ("product:1",))
        self.assertIn("$101.25", next_answer.text)
        self.assertNotIn("hole", next_answer.text.casefold())
        self.assertFalse(next_answer.answer_plan["pendingSlots"])

    async def test_sup017_scoped_bare_measurements_complete_only_the_original_item(self):
        self.catalog[5]["compatibility"] = {
            "uprightSize": "3 × 3 in / 75 × 75 mm", "holeDiameter": "1 in",
        }
        first = await self.answer("Will STYL Aurora Dip Attachment fit my rack?", item_ref="accessory:6")
        self.assertFalse(first.needs_human)
        second = await self.answer("3x3", item_ref="accessory:6", pending_context=first.answer_plan)
        self.assertFalse(second.needs_human, second.text)
        self.assertIn("?", second.text)
        self.assertEqual(second.references, ("accessory:6",))
        third = await self.answer("1 inch", item_ref="accessory:6", pending_context=second.answer_plan)
        self.assertFalse(third.needs_human, third.text)
        self.assertEqual(third.references, ("accessory:6",))
        self.assertFalse(third.answer_plan["pendingSlots"])
        self.assertNotIn("yes, it fits", third.text.casefold())
        self.assertNotIn("guaranteed", third.text.casefold())
        moved = await self.answer("1 inch", item_ref="product:1", pending_context=second.answer_plan)
        self.assertNotIn("accessory:6", moved.references)
        self.assertNotIn("Aurora Dip Attachment", moved.text)

    async def test_sup017_missing_faq_keeps_known_catalog_facts(self):
        result = await self.answer("What is the color of STYL Alpine Bench and your shipping policy?")
        self.assertTrue(result.needs_human)
        self.assertIn("Black / red", result.text)
        self.assertEqual(result.references, ("product:1",))
        self.assertIsNotNone(result.answer_plan)
        self.assertFalse(result.knowledge_sources)
        contextual = await self.answer("What is its color and your shipping policy?", item_ref="product:1")
        self.assertTrue(contextual.needs_human)
        self.assertIn("Black / red", contextual.text)
        self.assertEqual(contextual.references, ("product:1",))
        self.assertEqual(contextual.text, contextual.answer_plan["text"])
        self.assertTrue(contextual.answer_plan["needsHuman"])
        self.assertIn("customer_service", contextual.answer_plan["requestedScopes"])
        self.assertTrue(ai.answer_matches_plan(
            contextual, ai.public_evidence(self.catalog, list(ai.TOPICS)), list(ai.TOPICS)))
        warranty = await self.answer("What is the warranty of STYL Alpine Bench and your shipping policy?")
        self.assertTrue(warranty.needs_human)
        self.assertEqual(warranty.reason, "missing_evidence")
        self.assertIn("one year", warranty.text)

    async def test_sup017_disabled_field_never_discards_allowed_field(self):
        result = await self.answer("What are the price and color of STYL Alpine Bench?", topics=["products"])
        self.assertTrue(result.needs_human)
        self.assertEqual(result.reason, "scope_disabled")
        self.assertEqual(result.topic, "products")
        self.assertIn("Black / red", result.text)
        self.assertNotIn("101.25", result.text)
        fields = {fact["key"]: fact["status"] for item in result.answer_plan["items"] for fact in item["fields"]}
        self.assertEqual(fields["price.current"], "scope_disabled")
        self.assertEqual(fields["colourOptions"], "answered")
        self.assertTrue(ai.answer_matches_plan(
            result, ai.public_evidence(self.catalog, ["products"]), ["products"]))

    async def test_sup017_unreviewed_fields_and_images_are_not_sources(self):
        self.catalog[0]["weight"] = ""
        self.catalog[0]["image"] = "12-kg-bench.jpg"
        self.catalog[0]["draftKnowledge"] = [{"text": "Weight: 12 kg"}]
        result = await self.answer("What is the weight of STYL Alpine Bench?")
        self.assertTrue(result.needs_human)
        self.assertNotIn("12 kg", result.text)

    async def test_sup017_single_item_page_never_overrides_unknown_named_identity(self):
        for question in ("What hole diameter is listed for Rogue Alpine Bench?",
                         "Does AB-501 fit 75 x 75 mm uprights?"):
            with self.subTest(question=question):
                result = await self.answer(question, catalog=self.catalog[:1], item_ref="product:1")
                self.assertTrue(result.needs_human)
                self.assertFalse(result.references)
                self.assertNotIn("25 mm", result.text)
                self.assertNotIn("101.25", result.text)

    async def test_sup017_approved_explicit_labels_fill_blank_structured_fields(self):
        self.catalog[0].update(colourOptions="", material="", included="")
        self.catalog[0]["approvedKnowledge"] = [{
            "text": "Colour options: Olive.\nMaterial: Aluminium.\nIncluded: Two mounting bolts.",
            "topic": "products", "sourceId": "reviewed-bench-manual", "sourceName": "Bench manual",
            "sourceHash": "a" * 64, "revision": 2, "location": "Page 4",
        }]
        result = await self.answer("What are the colors, material and included items for STYL Alpine Bench?")
        self.assertFalse(result.needs_human, result.text)
        for value in ("Olive", "Aluminium", "Two mounting bolts"):
            self.assertIn(value, result.text)
        self.assertIsNotNone(result.answer_plan)
        self.assertIn("reviewed-bench-manual", str(result.answer_plan))
        self.assertIn("a" * 64, str(result.answer_plan))
        del self.catalog[0]["approvedKnowledge"][0]["sourceName"]
        unnamed_source = await self.answer("What material is STYL Alpine Bench made from?")
        self.assertFalse(unnamed_source.needs_human)
        self.assertIn("Aluminium", unnamed_source.text)

    async def test_sup017_explicit_finish_prose_is_not_an_available_color_option_list(self):
        self.catalog[0].update(colourOptions="", description="The bench has a black finish and red padded rollers.")
        colour = await self.answer("What color is STYL Alpine Bench?")
        self.assertIn("black", colour.text.casefold())
        self.assertIn("finish", colour.text.casefold())
        self.assertIsNotNone(colour.answer_plan)
        options = await self.answer("What available color options does STYL Alpine Bench come in?")
        self.assertTrue(options.needs_human)
        self.assertIn("black", options.text.casefold())
        self.assertIn("finish", options.text.casefold())
        fields = {fact["key"]: fact for item in options.answer_plan["items"] for fact in item["fields"]}
        self.assertEqual(fields["colour.availableOptions"]["status"], "unknown")
        self.assertEqual(fields["finish"]["status"], "answered")
        self.assertNotIn("Black / red", options.text)
        finish = await self.answer("What is the finish of STYL Alpine Bench?")
        self.assertFalse(finish.needs_human, finish.text)
        self.assertIn("black", finish.text.casefold())
        self.assertNotIn("red", finish.text.casefold())

    async def test_sup017_own_weight_load_and_resistance_stay_separate(self):
        self.catalog[0].update(safeLoad="300 kg", weightStacks="2 x 60 kg", weightIncrements="5 kg")
        cases = [
            ("What is the own weight of STYL Alpine Bench?", "12 kg", ("300 kg", "2 x 60 kg", "5 kg")),
            ("What is the maximum load of STYL Alpine Bench?", "300 kg", ("12 kg", "2 x 60 kg", "5 kg")),
            ("How much weight can STYL Alpine Bench handle?", "300 kg", ("12 kg", "2 x 60 kg", "5 kg")),
            ("What resistance stacks are listed for STYL Alpine Bench?", "2 x 60 kg", ("12 kg", "300 kg")),
            ("What are the resistance increments of STYL Alpine Bench?", "5 kg", ("12 kg", "300 kg")),
        ]
        for question, expected, excluded in cases:
            with self.subTest(question=question):
                result = await self.answer(question)
                self.assertFalse(result.needs_human, result.text)
                self.assertIn(expected, result.text)
                for value in excluded:
                    self.assertNotIn(value, result.text)

    async def test_sup017_inch_and_metric_labels_are_not_silent_equivalences(self):
        self.catalog[5]["compatibility"] = {
            "uprightSize": "3 x 3 in / 75 x 75 mm", "holeDiameter": "1 in / 25 mm",
        }
        result = await self.answer(
            "Will STYL Aurora Dip Attachment fit my measured 75 x 75 mm uprights and 25 mm holes?"
        )
        self.assertIn("3 x 3 in / 75 x 75 mm", result.text)
        self.assertIn("1 in / 25 mm", result.text)
        self.assertNotIn("guaranteed", result.text.casefold())
        self.assertNotIn("yes, it fits", result.text.casefold())
        self.assertIsNotNone(result.answer_plan)

    async def test_sup017_plan_cannot_survive_changed_canonical_fact_or_fabricated_text(self):
        result = await self.answer("What is the color of STYL Alpine Bench?")
        evidence = ai.public_evidence(self.catalog, list(ai.TOPICS))
        self.assertTrue(catalog_answers.validate_plan(result.answer_plan, evidence, list(ai.TOPICS)))
        tampered = deepcopy(result.answer_plan)
        tampered["text"] += " Yes, this is guaranteed to fit."
        self.assertFalse(catalog_answers.validate_plan(tampered, evidence, list(ai.TOPICS)))
        self.catalog[0]["colourOptions"] = "Gold"
        changed = ai.public_evidence(self.catalog, list(ai.TOPICS))
        self.assertFalse(catalog_answers.validate_plan(result.answer_plan, changed, list(ai.TOPICS)))

    async def test_sup017_composite_plan_revalidates_full_text_flags_refs_and_general_source(self):
        fact = {"text": "Shipping is scheduled after quote approval.", "topic": "customer_service",
                "sourceId": "faq-shipping", "sourceName": "Shipping FAQ", "location": "Page 2",
                "sourceHash": "b" * 64, "revision": 3}
        with patch.dict(os.environ, {"STYL_SUPPORT_ENVIRONMENT": "test"}):
            result = await ai.respond(
                [{"role": "user", "text": "What color is STYL Alpine Bench and what is the shipping policy?"}],
                self.catalog, list(ai.TOPICS), "mock", "mock", general_knowledge=[fact],
            )
        evidence = ai.public_evidence(self.catalog, list(ai.TOPICS))
        self.assertFalse(result.needs_human, result.text)
        self.assertEqual(result.text, result.answer_plan["text"])
        self.assertEqual(result.knowledge_sources, ("faq-shipping",))
        self.assertTrue(ai.answer_matches_plan(result, evidence, list(ai.TOPICS), [fact]))
        self.assertTrue(ai.validate_answer_plan(result.answer_plan, evidence, list(ai.TOPICS), [fact]))
        self.assertFalse(ai.answer_matches_plan(replace(result, text=result.text + " Free shipping."),
                                               evidence, list(ai.TOPICS), [fact]))
        self.assertFalse(ai.answer_matches_plan(replace(result, needs_human=True),
                                               evidence, list(ai.TOPICS), [fact]))
        self.assertFalse(ai.answer_matches_plan(replace(result, references=("product:2",)),
                                               evidence, list(ai.TOPICS), [fact]))
        self.assertFalse(ai.answer_matches_plan(replace(result, knowledge_sources=()),
                                               evidence, list(ai.TOPICS), [fact]))
        for changed in ({**fact, "revision": 4}, {**fact, "sourceHash": "c" * 64},
                        {**fact, "text": "Shipping requires a separate arrangement."}):
            with self.subTest(source=changed):
                self.assertFalse(ai.answer_matches_plan(result, evidence, list(ai.TOPICS), [changed]))
        self.assertFalse(ai.answer_matches_plan(result, evidence, ["products", "pricing"], [fact]))


if __name__ == "__main__":
    unittest.main()
