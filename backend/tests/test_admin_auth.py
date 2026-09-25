import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app import main


class AdminAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_data_path = main.DATA_PATH
        self.original_accessories_path = main.ACCESSORIES_PATH
        self.original_admin_token = main.ADMIN_TOKEN
        main.DATA_PATH = Path(self.temporary_directory.name) / "products.json"
        main.ACCESSORIES_PATH = Path(self.temporary_directory.name) / "accessories.json"
        self.original_hero_path = main.HERO_PATH
        main.HERO_PATH = Path(self.temporary_directory.name) / "hero.json"
        self.original_upload_path = main.UPLOAD_PATH
        main.UPLOAD_PATH = Path(self.temporary_directory.name) / "uploads"
        main.UPLOAD_PATH.mkdir()
        main.ADMIN_TOKEN = "test-admin-token"
        self.client = TestClient(main.app)

    def tearDown(self) -> None:
        main.DATA_PATH = self.original_data_path
        main.ACCESSORIES_PATH = self.original_accessories_path
        main.HERO_PATH = self.original_hero_path
        main.UPLOAD_PATH = self.original_upload_path
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

    def test_accessories_are_public_and_editable_only_by_admin(self) -> None:
        listing = self.client.get("/api/accessories")
        self.assertEqual(listing.status_code, 200)
        first = listing.json()["items"][0]

        payload = {**first, "name": "Updated Bar", "price": 99}
        unauthorized = self.client.put(f"/api/accessories/{first['id']}", json=payload)
        authorized = self.client.put(
            f"/api/accessories/{first['id']}",
            json=payload,
            headers={"Authorization": "Bearer test-admin-token"},
        )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(authorized.json()["item"]["name"], "Updated Bar")
        self.assertEqual(self.client.get("/api/accessories").json()["items"][0]["price"], 99)

    def test_new_accessory_ids_stay_above_the_product_range(self) -> None:
        main.ACCESSORIES_PATH.write_text("[]", encoding="utf-8")

        response = self.client.post(
            "/api/accessories",
            json={"name": "Grip", "category": "Handle", "price": 10},
            headers={"Authorization": "Bearer test-admin-token"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"]["id"], main.ACCESSORY_ID_OFFSET + 1)

    def test_admin_can_delete_accessory(self) -> None:
        first_id = self.client.get("/api/accessories").json()["items"][0]["id"]

        unauthorized = self.client.delete(f"/api/accessories/{first_id}")
        authorized = self.client.delete(
            f"/api/accessories/{first_id}",
            headers={"Authorization": "Bearer test-admin-token"},
        )
        missing = self.client.delete(
            f"/api/accessories/{first_id}",
            headers={"Authorization": "Bearer test-admin-token"},
        )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(missing.status_code, 404)
        ids = [item["id"] for item in self.client.get("/api/accessories").json()["items"]]
        self.assertNotIn(first_id, ids)

    def test_hero_defaults_and_admin_update(self) -> None:
        self.assertEqual(self.client.get("/api/hero").json()["item"]["title"], "Series X")

        payload = {"tag": "New", "number": "02", "eyebrow": "Multi", "title": "Trainer", "priceLabel": "$3,999", "image": ""}
        unauthorized = self.client.put("/api/hero", json=payload)
        authorized = self.client.put(
            "/api/hero",
            json=payload,
            headers={"Authorization": "Bearer test-admin-token"},
        )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(authorized.status_code, 200)
        saved = self.client.get("/api/hero").json()["item"]
        self.assertEqual(saved["title"], "Trainer")
        self.assertEqual(saved["image"], main.DEFAULT_HERO.image)


    def test_catalog_photos_and_compatibility_round_trip(self) -> None:
        headers = {"Authorization": "Bearer test-admin-token"}
        for endpoint in ("products", "accessories"):
            with self.subTest(endpoint=endpoint):
                payload = {
                    "name": "Gallery test", "category": "Test", "price": 10,
                    "shortDescription": "Test", "description": "Test",
                    "photos": ["/images/front.jpg", "/images/side.jpg"],
                    "compatibility": {"uprightSize": "75 x 75 mm", "holeDiameter": "1 inch", "holeSpacing": "50 mm", "models": "Confirmed rack", "limitations": "Not confirmed for 3 x 3 inch"},
                }
                self.assertEqual(self.client.post(f"/api/{endpoint}", json=payload).status_code, 401)
                created = self.client.post(f"/api/{endpoint}", json=payload, headers=headers)
                self.assertEqual(created.status_code, 200)
                item = created.json()["item"]
                self.assertEqual(item["image"], payload["photos"][0])
                payload["photos"].reverse()
                updated = self.client.put(f"/api/{endpoint}/{item['id']}", json=payload, headers=headers)
                self.assertEqual(updated.status_code, 200)
                saved = updated.json()["item"]
                self.assertEqual(saved["image"], "/images/side.jpg")
                self.assertEqual(saved["compatibility"], payload["compatibility"])
                del payload["photos"]
                del payload["compatibility"]
                legacy_update = self.client.put(f"/api/{endpoint}/{item['id']}", json=payload, headers=headers)
                self.assertEqual(legacy_update.json()["item"]["photos"], saved["photos"])
                self.assertEqual(legacy_update.json()["item"]["compatibility"], saved["compatibility"])
                listed = self.client.get(f"/api/{endpoint}").json()["items"]
                self.assertEqual(next(entry for entry in listed if entry["id"] == item["id"])["photos"], saved["photos"])
                payload["photos"] = []
                cleared = self.client.put(f"/api/{endpoint}/{item['id']}", json=payload, headers=headers)
                self.assertEqual(cleared.json()["item"]["image"], "")
                self.assertEqual(cleared.json()["item"]["photos"], [])

    def test_shared_photos_are_kept_until_last_reference_is_deleted(self) -> None:
        headers = {"Authorization": "Bearer test-admin-token"}
        shared = main.UPLOAD_PATH / "shared.jpg"
        removed = main.UPLOAD_PATH / "removed.jpg"
        shared.write_bytes(b"test")
        removed.write_bytes(b"test")
        payload = {"name": "Gallery", "category": "Test", "price": 1, "photos": ["/api/uploads/shared.jpg", "/api/uploads/removed.jpg"]}
        first = self.client.post("/api/accessories", json=payload, headers=headers).json()["item"]
        second = self.client.post("/api/accessories", json={**payload, "photos": ["/api/uploads/shared.jpg"]}, headers=headers).json()["item"]
        updated = self.client.put(f"/api/accessories/{first['id']}", json={**payload, "photos": ["/api/uploads/shared.jpg"]}, headers=headers)
        self.assertEqual(updated.status_code, 200)
        self.assertFalse(removed.exists())
        self.client.delete(f"/api/accessories/{first['id']}", headers=headers)
        self.assertTrue(shared.exists())
        self.client.delete(f"/api/accessories/{second['id']}", headers=headers)
        self.assertFalse(shared.exists())

    def test_invalid_catalog_details_are_rejected(self) -> None:
        headers = {"Authorization": "Bearer test-admin-token"}
        payload = {"name": "Gallery", "category": "Test", "price": 1}
        for fields in ({"photos": ["/images/test.jpg"] * 13}, {"photos": ["javascript:alert(1)"]}, {"compatibility": {"uprightSize": "x" * 301}}):
            response = self.client.post("/api/accessories", json={**payload, **fields}, headers=headers)
            self.assertEqual(response.status_code, 422)

    def test_uploaded_gallery_reorder_and_cross_catalog_cleanup(self) -> None:
        headers = {"Authorization": "Bearer test-admin-token"}
        photos = []
        for name in ("front.jpg", "side.jpg"):
            response = self.client.post("/api/uploads/product-image", headers=headers, files={"image": (name, b"test image", "image/jpeg")})
            self.assertEqual(response.status_code, 200)
            photos.append(response.json()["image"])
        payload = {"name": "Uploaded gallery", "category": "Test", "price": 1, "shortDescription": "Test", "description": "Test", "photos": photos}
        product = self.client.post("/api/products", json=payload, headers=headers).json()["item"]
        accessory = self.client.post("/api/accessories", json={**payload, "photos": [photos[0]]}, headers=headers).json()["item"]
        self.client.put("/api/hero", json={"image": photos[1]}, headers=headers)
        reordered = self.client.put(f"/api/products/{product['id']}", json={**payload, "photos": list(reversed(photos))}, headers=headers)
        self.assertEqual(reordered.status_code, 200)
        self.assertEqual(reordered.json()["item"]["image"], photos[1])
        paths = [main.UPLOAD_PATH / Path(photo).name for photo in photos]
        self.assertTrue(all(path.exists() for path in paths))
        self.client.delete(f"/api/products/{product['id']}", headers=headers)
        self.assertTrue(all(path.exists() for path in paths))
        self.client.delete(f"/api/accessories/{accessory['id']}", headers=headers)
        self.assertFalse(paths[0].exists())
        self.assertTrue(paths[1].exists())
        self.client.put("/api/hero", json={"image": ""}, headers=headers)
        self.assertFalse(paths[1].exists())


if __name__ == "__main__":
    unittest.main()