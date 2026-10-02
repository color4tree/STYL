"""SUP-029: conversational phrasing retains factual values and compatibility limits."""

import unittest

from app import catalog_answers


class NarrativeAnswersTests(unittest.TestCase):
    def setUp(self):
        self.item = {
            "ref": "accessory:1", "name": "STYL Sample Attachment", "category": "Attachments",
            "price": 199, "currency": "CAD", "material": "Steel", "colourOptions": "Black",
            "compatibility": {"uprightSize": "3 × 3 in / 75 × 75 mm", "holeDiameter": "1”"},
        }

    def answer(self, question):
        plan = catalog_answers.build_plan(question, [self.item], list(catalog_answers.TOPICS), item_ref=self.item["ref"])
        self.assertIsNotNone(plan)
        self.assertTrue(catalog_answers.validate_plan(plan, [self.item], list(catalog_answers.TOPICS)))
        return plan

    def test_requirements_are_sentences_not_a_specification_dump(self):
        plan = self.answer("What is the compatible hole diameter?")
        self.assertIn("1 inch", plan.text)
        self.assertIn("75 × 75 mm", plan.text)
        self.assertNotIn("Here's what's published", plan.text)
        self.assertNotIn("These are the published requirements", plan.text)
        self.assertNotIn("Hole diameter:", plan.text)
        self.assertNotIn("\n", plan.text)
        self.assertFalse(plan.needs_human)

    def test_price_is_concise_and_keeps_the_market_amount(self):
        plan = self.answer("What is the price?")
        self.assertEqual(plan.text, "For the sample attachment, the current price is CAD $199.00.")

    def test_known_facts_survive_unknowns_in_a_narrative(self):
        plan = self.answer("What are the color, material and safe load?")
        self.assertIn("Black", plan.text)
        self.assertIn("Steel", plan.text)
        self.assertIn("can't confirm", plan.text)
        self.assertTrue(plan.needs_human)
        self.assertEqual(plan.status, "partial")

    def test_natural_fit_wording_never_promises_a_verified_pair(self):
        plan = self.answer("Will it fit my 3x3 rack with 1 inch holes?")
        self.assertIn("isn't a verified fit", plan.text)
        self.assertNotIn("guaranteed", plan.text)
        self.assertFalse(plan.pending_slots)

    def test_only_display_units_change_not_the_stored_evidence(self):
        plan = self.answer("What is the hole diameter?")
        fact = next(field for field in plan.items[0]["fields"] if field["key"] == "compat.holeDiameter")
        self.assertEqual(fact["value"], "1”")
        self.assertIn("1 inch", plan.text)
