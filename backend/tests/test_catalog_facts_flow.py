"""FACT-015: admin-reviewed meanings reach conversational answers through the real API."""

import unittest

from tests import test_catalog_plan_publication as fixture


class CatalogFactsFlowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.CatalogPlanPublicationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.facts = {
            "schemaVersion": 1, "reviewed": False,
            "options": {"colors": ["Blue"], "sizes": ["34 mm", "36 mm"], "finish": "Powder coat"},
            "measurements": [
                {"kind": "width", "scope": "rack", "amount": "150", "unit": "cm", "qualifier": "exact"},
                {"kind": "width", "scope": "smith_bar", "amount": "220", "unit": "cm", "qualifier": "exact"},
            ],
            "interfaces": [{"kind": "socket_drive", "role": "accepts", "constraints": [
                {"attribute": "driveSize", "operator": "eq", "value": "0.5", "unit": "in"},
            ]}],
            "components": [
                {"name": "Mounting pin", "quantity": 2, "status": "included"},
                {"name": "Display shelf", "quantity": None, "status": "excluded"},
            ],
        }

    def save(self, reviewed):
        self.facts["reviewed"] = reviewed
        current = self.fixture.client.get("/api/admin/products", headers=self.fixture.admin).json()["items"][0]
        response = self.fixture.client.put("/api/products/1", headers=self.fixture.admin, json={
            "name": current["name"], "category": current["category"], "schemaVersion": 2,
            "expectedRevision": current["revision"], "catalogFacts": self.facts,
        })
        self.assertEqual(response.status_code, 200, response.text)

    def test_reviewed_colors_and_scoped_widths_are_used_without_changing_prices(self):
        self.save(False)
        public = self.fixture.client.get("/api/products/synthetic-bench").json()["item"]
        self.assertNotIn("catalogFacts", public)
        self.save(True)
        thread = self.fixture.ask("What color is this?", "product:1")
        self.assertIn("Blue", thread["messages"][-1]["text"])
        self.assertNotIn("34 mm", thread["messages"][-1]["text"])
        thread = self.fixture.ask("What is the width?", "product:1")
        answer = thread["messages"][-1]["text"].lower()
        self.assertIn("150", answer)
        self.assertIn("220", answer)
        self.assertIn("rack", answer)
        self.assertIn("smith", answer)
        thread = self.fixture.ask("What is its price?", "product:1")
        self.assertIn("125.50", thread["messages"][-1]["text"])

    def test_socket_interface_and_exclusions_are_not_rack_or_bundle_claims(self):
        self.save(True)
        thread = self.fixture.ask("What is the socket drive size?", "product:1")
        answer = thread["messages"][-1]["text"].lower()
        self.assertIn("0.5", answer)
        self.assertIn("accepts", answer)
        self.assertNotIn("upright", answer)
        thread = self.fixture.ask("What components are included?", "product:1")
        answer = thread["messages"][-1]["text"].lower()
        self.assertIn("mounting pin", answer)
        self.assertIn("2", answer)
        self.assertIn("display shelf", answer)
        self.assertIn("doesn't include display shelf", answer)
