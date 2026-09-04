import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main


class AdminAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_data_path = main.DATA_PATH
        self.original_admin_token = main.ADMIN_TOKEN
        main.DATA_PATH = Path(self.temporary_directory.name) / "products.json"
        main.ADMIN_TOKEN = "test-admin-token"
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        main.DATA_PATH = self.original_data_path
        main.ADMIN_TOKEN = self.original_admin_token
        self.temporary_directory.cleanup()

    def test_admin_access_is_disabled_without_a_configured_token(self) -> None:
        main.ADMIN_TOKEN = ""

        response = self.client.get("/api/admin/verify")

        self.assertEqual(response.status_code, 503)

    def test_admin_verification_rejects_missing_and_incorrect_tokens(self) -> None:
        missing = self.client.get("/api/admin/verify")
        incorrect = self.client.get(
            "/api/admin/verify",
            headers={"Authorization": "Bearer incorrect"},
        )

        self.assertEqual(missing.status_code, 401)
        self.assertEqual(incorrect.status_code, 401)

    def test_valid_token_can_create_a_product(self) -> None:
        payload = {
            "name": "Test Bench",
            "category": "Strength",
            "price": 499,
            "shortDescription": "A test product.",
            "description": "Created by the API authentication test.",
            "features": ["Stable frame"],
        }

        unauthorized = self.client.post("/api/products", json=payload)
        authorized = self.client.post(
            "/api/products",
            json=payload,
            headers={"Authorization": "Bearer test-admin-token"},
        )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(authorized.json()["item"]["slug"], "test-bench")
        self.assertTrue(main.DATA_PATH.exists())


if __name__ == "__main__":
    unittest.main()