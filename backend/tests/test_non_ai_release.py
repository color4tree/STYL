"""Main-only release gate: production features must not load the AI branch."""

import importlib.util
import unittest

from pydantic import ValidationError

from app import main, records


class NonAIReleaseTests(unittest.TestCase):
    def test_production_route_table_contains_records_but_no_customer_ai(self) -> None:
        paths = {getattr(route, "path", "") for route in main.app.routes}
        self.assertIn("/api/admin/records/archives", paths)
        self.assertFalse(any("/support" in path or "/knowledge" in path for path in paths))

    def test_ai_implementation_is_not_present_in_main_imports(self) -> None:
        for name in ("support", "support_ai", "knowledge", "knowledge_extract", "openai_api", "catalog_answers"):
            with self.subTest(module=name):
                self.assertIsNone(importlib.util.find_spec(f"app.{name}"))

    def test_records_cleanup_cannot_target_ai_data(self) -> None:
        with self.assertRaises(ValidationError):
            records.RemoveInput(confirmation="REMOVE synthetic", categories=["support"])


if __name__ == "__main__":
    unittest.main()
