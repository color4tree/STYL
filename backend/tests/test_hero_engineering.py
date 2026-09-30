from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import main


class HeroEngineeringTests(unittest.TestCase):
    # SYS-012/013: fixed-card configuration, compatibility, persistence and media lifecycle.
    def setUp(self) -> None:
        scratch = Path(__file__).resolve().parents[2] / ".styl-runtime" / "backend-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(prefix="engineering-", dir=scratch)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.paths = {
            "DATA_PATH": self.root / "products.json",
            "ACCESSORIES_PATH": self.root / "accessories.json",
            "HERO_PATH": self.root / "hero.json",
            "UPLOAD_PATH": self.root / "uploads",
        }
        self.paths["UPLOAD_PATH"].mkdir()
        self.paths["DATA_PATH"].write_text("[]", encoding="utf-8")
        self.paths["ACCESSORIES_PATH"].write_text("[]", encoding="utf-8")
        settings = patch.multiple(main, **self.paths, ADMIN_TOKEN="engineering-test-token")
        settings.start()
        self.addCleanup(settings.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer engineering-test-token"}
        self.engineering = main.DEFAULT_ENGINEERING.model_dump()
        self.hero = {
            "tag": "Custom", "number": "08", "eyebrow": "Independent",
            "title": "Saved banner", "image": "/images/custom.jpg",
            "engineering": deepcopy(self.engineering),
        }

    def save_source(self, value: object | None = None) -> bytes:
        content = json.dumps(self.hero if value is None else value, ensure_ascii=False, indent=3).encode("utf-8")
        self.paths["HERO_PATH"].write_bytes(content)
        return content

    def update(self, payload: object):
        return self.client.put("/api/hero", headers=self.headers, json=payload)

    def upload(self, name: str) -> str:
        self.paths["UPLOAD_PATH"].joinpath(name).write_bytes(b"isolated image")
        return f"/api/uploads/{name}"

    def test_authentication_required_for_home_update_and_admin_read(self) -> None:
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            self.assertEqual(self.client.put("/api/hero", headers=headers, json={"engineering": self.engineering}).status_code, 401)
            self.assertEqual(self.client.get("/api/admin/hero", headers=headers).status_code, 401)
        self.assertFalse(self.paths["HERO_PATH"].exists())

    def test_missing_and_legacy_defaults_are_in_memory_only(self) -> None:
        for endpoint, headers in (("/api/hero", {}), ("/api/admin/hero", self.headers)):
            response = self.client.get(endpoint, headers=headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["item"], main.DEFAULT_HERO.model_dump())
        self.assertFalse(self.paths["HERO_PATH"].exists())
        legacy = {key: value for key, value in self.hero.items() if key != "engineering"}
        content = self.save_source({**legacy, "priceLabel": "PRIVATE-LEGACY-PRICE"})
        for endpoint, headers in (("/api/hero", {}), ("/api/admin/hero", self.headers)):
            response = self.client.get(endpoint, headers=headers)
            self.assertEqual(response.json()["item"], {**legacy, "engineering": self.engineering})
            self.assertNotIn("PRIVATE-LEGACY-PRICE", response.text)
            self.assertEqual(self.paths["HERO_PATH"].read_bytes(), content)

    def test_exact_default_copy_and_card_order(self) -> None:
        value = main.load_hero()["engineering"]
        self.assertEqual(value["heading"], "Explore our engineering details")
        self.assertEqual(value["intro"], "Our mark, engineered into every piece.")
        self.assertEqual(value["items"], [
            {"title": "Signature shield", "description": "Laser-etched into brushed stainless steel on every frame upright.", "image": "/images/brand/logo-plate.jpg"},
            {"title": "J-hook", "description": "Rubber-lined steel hooks that protect the bar and carry the wordmark.", "image": "/images/brand/j-hook.jpg"},
            {"title": "Cable swivel plate", "description": "Machined plate and 360° swivel for smooth, tangle-free cable work.", "image": "/images/brand/cable-swivel.jpg"},
            {"title": "Frame badge", "description": "Brushed steel badge finishing the top crossmember of the multi trainer.", "image": "/images/brand/frame-badge.jpg"},
        ])
        value["items"][0]["title"] = "Do not mutate shared defaults"
        self.assertEqual(main.load_hero()["engineering"], self.engineering)

    def test_engineering_only_save_and_reload_preserves_entire_banner(self) -> None:
        self.save_source()
        edited = deepcopy(self.engineering)
        edited["heading"] = "  Custom engineering  "
        edited["intro"] = "  中文\nNext line  "
        edited["items"][2] = {"title": " Swivel ", "description": " Line one\nLine two ", "image": "/api/uploads/new.jpg"}
        original_write = main.write_json_list

        def write_locked(*args):
            self.assertTrue(main.CATALOG_LOCK.locked())
            original_write(*args)

        with patch.object(main, "write_json_list", side_effect=write_locked):
            response = self.update({"engineering": edited})
        self.assertEqual(response.status_code, 200, response.text)
        expected = {**self.hero, "engineering": deepcopy(edited)}
        expected["engineering"]["heading"] = "Custom engineering"
        expected["engineering"]["intro"] = "中文\nNext line"
        expected["engineering"]["items"][2]["title"] = "Swivel"
        expected["engineering"]["items"][2]["description"] = "Line one\nLine two"
        self.assertEqual(response.json()["item"], expected)
        self.assertEqual(json.loads(self.paths["HERO_PATH"].read_bytes()), expected)
        for endpoint, headers in (("/api/hero", {}), ("/api/admin/hero", self.headers)):
            self.assertEqual(self.client.get(endpoint, headers=headers).json()["item"], expected)

    def test_top_only_and_empty_update_preserve_engineering_and_omitted_banner_fields(self) -> None:
        self.hero["engineering"]["items"][0]["title"] = "Already customized"
        self.save_source()
        response = self.update({"title": "  New banner  "})
        expected = {**self.hero, "title": "New banner"}
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item"], expected)
        self.assertEqual(self.update({}).json()["item"], expected)
        response = self.update({"tag": "", "number": "", "eyebrow": "", "title": "", "image": " "})
        self.assertEqual(response.status_code, 200)
        item = response.json()["item"]
        self.assertEqual([item[key] for key in ("tag", "number", "eyebrow", "title")], [""] * 4)
        self.assertEqual(item["image"], main.DEFAULT_HERO.image)
        self.assertEqual(item["engineering"], self.hero["engineering"])

    def test_schema_missing_fields_null_extras_and_exact_four_never_partially_save(self) -> None:
        original = self.save_source()
        invalid = [None, {}, [], "bad"]
        for field in ("heading", "intro", "items"):
            value = deepcopy(self.engineering)
            del value[field]
            invalid.append(value)
        for count in (0, 1, 3, 5):
            invalid.append({**self.engineering, "items": [self.engineering["items"][0]] * count})
        invalid.append({**self.engineering, "extra": "private"})
        for field in ("title", "description", "image"):
            value = deepcopy(self.engineering)
            del value["items"][0][field]
            invalid.append(value)
            value = deepcopy(self.engineering)
            value["items"][0][field] = None
            invalid.append(value)
        for card in (None, "card", {}, {**self.engineering["items"][0], "extra": True}):
            value = deepcopy(self.engineering)
            value["items"][0] = card
            invalid.append(value)
        for value in invalid:
            with self.subTest(value=value):
                response = self.update({"title": "Must not save", "engineering": value})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.paths["HERO_PATH"].read_bytes(), original)

    def test_text_limits_whitespace_and_image_validation(self) -> None:
        original = self.save_source()
        for field, length, card in (("heading", 120, False), ("intro", 1000, False), ("title", 120, True), ("description", 2000, True), ("image", 500, True)):
            value = deepcopy(self.engineering)
            (value["items"][0] if card else value)[field] = "x" * (length + 1)
            self.assertEqual(self.update({"engineering": value}).status_code, 422, field)
        for field, card in (("heading", False), ("title", True), ("image", True)):
            for blank in ("", " \n\t "):
                value = deepcopy(self.engineering)
                (value["items"][0] if card else value)[field] = blank
                self.assertEqual(self.update({"engineering": value}).status_code, 422)
        for image in (
            "/api/uploads/movie.MP4?x=1", "https://example.com/clip.webm#t=1",
            "/images/../private.jpg", "/images/%2e%2e/private.jpg", "/api/uploads/nested/x.jpg",
            "/api/uploads/a\\b.jpg", "//example.com/photo.jpg", "data:image/png;base64,abc",
            "javascript:alert(1)", "file:///private.jpg", "/other/file.jpg", "/images/file.txt",
            "https://", "https://example.com:bad/file.jpg", "/images/test\n.jpg",
        ):
            value = deepcopy(self.engineering)
            value["items"][0]["image"] = image
            self.assertEqual(self.update({"engineering": value}).status_code, 422, image)
        self.assertEqual(self.paths["HERO_PATH"].read_bytes(), original)

    def test_boundary_text_blank_optional_and_supported_image_urls_save(self) -> None:
        engineering = deepcopy(self.engineering)
        engineering["heading"] = " " + "h" * 120 + " "
        engineering["intro"] = "i" * 1000
        engineering["items"][0]["title"] = "t" * 120
        engineering["items"][0]["description"] = "d" * 2000
        engineering["items"][1]["description"] = " \n "
        images = ["http://example.com/image.jpg", "https://example.com/image", "/images/brand/image.svg", "/api/uploads/image.png?version=1"]
        for card, image in zip(engineering["items"], images):
            card["image"] = image
        response = self.update({"engineering": engineering})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["item"]["engineering"]["heading"], "h" * 120)
        self.assertEqual(response.json()["item"]["engineering"]["items"][1]["description"], "")
        engineering["intro"] = ""
        engineering["items"][0]["image"] = "https://example.com/" + "x" * (500 - len("https://example.com/"))
        self.assertEqual(self.update({"engineering": engineering}).status_code, 200)

    def test_corrupt_saved_configuration_fails_closed_for_get_and_save_without_logging_content(self) -> None:
        invalid = [
            b'{"secret":"DO-NOT-LOG"', b"[]", b"{}", b"\xff",
            b'{"tag":"first","tag":"duplicate"}',
            b"[" * 2000 + b"]" * 2000,
            json.dumps({**self.hero, "engineering": None}).encode(),
            json.dumps({**self.hero, "engineering": {"heading": "DO-NOT-LOG"}}).encode(),
            json.dumps({**self.hero, "engineering": {**self.engineering, "items": self.engineering["items"][:3]}}).encode(),
        ]
        for content in invalid:
            self.paths["HERO_PATH"].write_bytes(content)
            with self.subTest(content=content), self.assertLogs(main.logger, level="ERROR") as logs:
                for endpoint, headers in (("/api/hero", {}), ("/api/admin/hero", self.headers)):
                    response = self.client.get(endpoint, headers=headers)
                    self.assertEqual(response.status_code, 503, response.text)
                    self.assertNotIn("DO-NOT-LOG", response.text)
                response = self.update({"engineering": self.engineering})
                self.assertEqual(response.status_code, 503)
            self.assertNotIn("DO-NOT-LOG", "\n".join(logs.output))
            self.assertEqual(self.paths["HERO_PATH"].read_bytes(), content)

    def test_read_and_atomic_write_failures_are_generic_503_and_keep_old_media(self) -> None:
        old_image = self.upload("old.jpg")
        self.hero["engineering"]["items"][0]["image"] = old_image
        original = self.save_source()
        with patch.object(Path, "read_text", side_effect=PermissionError("PRIVATE-STORAGE-PATH")), self.assertLogs(main.logger, level="ERROR") as logs:
            response = self.update({"engineering": self.engineering})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("PRIVATE-STORAGE-PATH", response.text)
        self.assertNotIn("PRIVATE-STORAGE-PATH", "\n".join(logs.output))
        for operation in ("write_text", "replace"):
            with patch.object(Path, operation, side_effect=OSError("PRIVATE-STORAGE-PATH")), self.assertLogs(main.logger, level="ERROR") as logs:
                response = self.update({"engineering": self.engineering})
                self.assertEqual(response.status_code, 503)
            self.assertNotIn("PRIVATE-STORAGE-PATH", "\n".join(logs.output))
            self.assertEqual(self.paths["HERO_PATH"].read_bytes(), original)
            self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("old.jpg").exists())
            self.assertFalse(self.paths["HERO_PATH"].with_suffix(".tmp").exists())
            self.assertFalse(main.CATALOG_LOCK.locked())

    def test_product_and_accessory_deletion_keeps_card_references_until_last_card_removed(self) -> None:
        shared = self.upload("shared.jpg")
        for card in self.hero["engineering"]["items"][:2]:
            card["image"] = shared
        self.save_source()
        self.paths["DATA_PATH"].write_text(json.dumps([{"id": 1, "slug": "test", "name": "Test", "image": shared, "photos": [shared]}]))
        self.paths["ACCESSORIES_PATH"].write_text(json.dumps([{"id": 1001, "name": "Test", "image": shared, "photos": [shared]}]))
        for route in ("/api/products/1", "/api/accessories/1001"):
            self.assertEqual(self.client.delete(route, headers=self.headers).status_code, 200)
            self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())
        value = deepcopy(self.hero["engineering"])
        value["items"][0] = self.engineering["items"][0]
        self.assertEqual(self.update({"engineering": value}).status_code, 200)
        self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())
        self.assertEqual(self.update({"engineering": self.engineering}).status_code, 200)
        self.assertFalse(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())

    def test_banner_card_and_catalog_replacements_keep_each_others_shared_images(self) -> None:
        shared = self.upload("shared.jpg")
        self.hero["image"] = shared
        self.hero["engineering"]["items"][0]["image"] = shared
        self.save_source()
        self.assertEqual(self.update({"image": ""}).status_code, 200)
        self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())
        self.assertEqual(self.update({"image": shared}).status_code, 200)
        self.assertEqual(self.update({"engineering": self.engineering}).status_code, 200)
        self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())
        self.paths["DATA_PATH"].write_text(json.dumps([{"id": 1, "slug": "test", "name": "Test", "image": shared}]))
        self.assertEqual(self.update({"image": ""}).status_code, 200)
        self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())
        self.assertEqual(self.client.delete("/api/products/1", headers=self.headers).status_code, 200)
        self.assertFalse(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())

    def test_query_encoded_image_aliases_and_video_posters_keep_live_references(self) -> None:
        shared = self.upload("shared.jpg")
        self.hero["image"] = shared
        self.hero["engineering"]["items"][0]["image"] = "/api/uploads/%73hared.jpg?v=2"
        self.save_source()
        self.assertEqual(self.update({"image": ""}).status_code, 200)
        self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())
        self.assertEqual(self.update({"engineering": self.engineering}).status_code, 200)
        self.assertFalse(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())
        video = self.upload("clip.mp4")
        poster = self.upload("clip.poster.jpg")
        self.paths["DATA_PATH"].write_text(json.dumps([{"id": 1, "slug": "test", "name": "Test", "image": poster, "photos": [video]}]))
        self.hero["engineering"]["items"][0]["image"] = poster
        self.hero["image"] = "/images/another.jpg"
        self.save_source()
        self.assertEqual(self.client.delete("/api/products/1", headers=self.headers).status_code, 200)
        self.assertFalse(self.paths["UPLOAD_PATH"].joinpath("clip.mp4").exists())
        self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("clip.poster.jpg").exists())
        self.assertEqual(self.update({"engineering": self.engineering}).status_code, 200)
        self.assertFalse(self.paths["UPLOAD_PATH"].joinpath("clip.poster.jpg").exists())

    def test_product_edit_keeps_engineering_image_and_failed_save_does_not_clean_up(self) -> None:
        shared = self.upload("shared.jpg")
        self.hero["engineering"]["items"][0]["image"] = shared
        self.save_source()
        payload = {"name": "Test", "category": "Racks", "price": 12, "photos": [shared]}
        response = self.client.post("/api/products", headers=self.headers, json=payload)
        self.assertEqual(response.status_code, 200)
        identifier = response.json()["item"]["id"]
        response = self.client.put(f"/api/products/{identifier}", headers=self.headers, json={**payload, "photos": ["/images/other.jpg"]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())
        with patch.object(main, "write_json_list", side_effect=OSError), patch.object(main, "delete_uploaded_image") as delete:
            self.assertEqual(self.update({"engineering": self.engineering}).status_code, 503)
            delete.assert_not_called()

    def test_cleanup_keeps_media_when_saved_home_references_cannot_be_read(self) -> None:
        shared = self.upload("shared.jpg")
        self.paths["HERO_PATH"].write_bytes(b'{"engineering":')
        with self.assertLogs(main.logger, level="WARNING"):
            main.delete_uploaded_image(shared)
        self.assertTrue(self.paths["UPLOAD_PATH"].joinpath("shared.jpg").exists())


if __name__ == "__main__":
    unittest.main()
