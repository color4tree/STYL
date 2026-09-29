import io
import json
from contextlib import nullcontext
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from app import catalog_backup as backup
from app import main

VIDEO = "1234567890abcdef1234567890abcdef"


class CatalogBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="styl-catalog-backup-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / "original-server"
        self.data = self.source / "data"
        self.uploads = self.data / "uploads"
        self.images = self.source / "public" / "images"
        self.uploads.mkdir(parents=True)
        (self.images / "equipment").mkdir(parents=True)
        (self.images / "brand").mkdir()
        self.media = {
            "data/uploads/shared.png": b"\x89PNG\r\n\x1a\noriginal shared image",
            "data/uploads/banner.webp": b"RIFForiginal banner",
            f"data/uploads/{VIDEO}.mp4": bytes(range(256)) * 4,
            f"data/uploads/{VIDEO}.poster.jpg": b"\xff\xd8original poster",
            "public/images/equipment/rack.svg": b'<svg xmlns="http://www.w3.org/2000/svg"/>',
        }
        for name, content in self.media.items():
            (self.source / name).write_bytes(content)
        (self.images / "brand" / "frame-badge.jpg").write_bytes(b"default banner")
        self.uploads.joinpath("unreferenced.png").write_bytes(b"not part of the catalog")
        self.data.joinpath("inquiries").mkdir()
        self.data.joinpath("inquiries", "customer.json").write_text("PRIVATE-CUSTOMER-NOT-IN-BACKUP")
        self.data.joinpath(".env").write_text("PRIVATE-TOKEN-NOT-IN-BACKUP")
        self.products = [
            {
                "id": 7, "slug": "recovery-rack", "name": "Rack", "category": "Racks",
                "prices": {"CAD": 750.25, "USD": 600.50}, "price": 750.25, "currency": "CAD",
                "publicationStatus": "published", "featured": True,
                "shortDescription": "Training", "description": "Line one\n中文说明",
                "features": ["Feature one"], "weight": "25 kg",
                "image": "/api/uploads/shared.png",
                "photos": ["/api/uploads/shared.png", f"/api/uploads/{VIDEO}.mp4", "/images/equipment/rack.svg"],
                "compatibility": {"uprightSize": "75 mm", "limitations": "Confirm exact model"},
                "provenance": {"capturedDate": "2026-09-25", "notes": "PRIVATE-ADMIN-NOTE"},
            },
            {
                "id": 8, "slug": "draft-item", "name": "Draft", "category": "Benches",
                "prices": {"CAD": None, "USD": 80}, "publicationStatus": "draft",
                "image": "/images/equipment/rack.svg", "photos": [],
            },
        ]
        self.accessories = [{
            "id": 1007, "name": "Pair", "category": "Handle",
            "prices": {"CAD": 49.95, "USD": None}, "sellingUnit": "Pair", "packageQuantity": 2,
            "description": "Full details", "notes": "Public use",
            "image": "/api/uploads/shared.png", "photos": ["/api/uploads/shared.png"],
        }]
        self.hero = {"tag": "Custom", "number": "02", "eyebrow": "Built well", "title": "Banner", "image": "/api/uploads/banner.webp"}
        for name, value in (("products", self.products), ("accessories", self.accessories), ("hero", self.hero)):
            self.data.joinpath(name + ".json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        self.paths = {
            "DATA_PATH": self.data / "products.json", "ACCESSORIES_PATH": self.data / "accessories.json",
            "HERO_PATH": self.data / "hero.json", "UPLOAD_PATH": self.uploads, "PUBLIC_IMAGE_PATH": self.images,
        }
        replacements = patch.multiple(main, **self.paths, ADMIN_TOKEN="ephemeral-backup-test-token")
        replacements.start()
        self.addCleanup(replacements.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer ephemeral-backup-test-token"}

    def download(self) -> bytes:
        response = self.client.get("/api/admin/catalog-backup", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text[:200] if response.status_code != 200 else "")
        return response.content

    def write_archive(self, content: bytes | None = None) -> Path:
        path = self.root / "download.zip"
        path.write_bytes(self.download() if content is None else content)
        return path

    def rewrite(self, changes: dict[str, bytes] | None = None, additions: list[tuple[zipfile.ZipInfo | str, bytes]] | None = None, omit: str | None = None) -> Path:
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.download())) as original, zipfile.ZipFile(output, "w") as rewritten:
            for entry in original.infolist():
                if entry.filename != omit:
                    rewritten.writestr(entry, (changes or {}).get(entry.filename, original.read(entry)))
            for name, value in additions or []:
                rewritten.writestr(name, value)
        return self.write_archive(output.getvalue())

    def test_sys017_authentication_is_required_and_has_no_public_download(self) -> None:
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            response = self.client.get("/api/admin/catalog-backup", headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertNotIn("PRIVATE-ADMIN-NOTE", response.text)
        with patch.object(main, "ADMIN_TOKEN", ""):
            self.assertEqual(self.client.get("/api/admin/catalog-backup", headers=self.headers).status_code, 503)
        self.assertEqual(self.client.get("/api/catalog-backup").status_code, 404)
        self.assertEqual(self.client.post("/api/admin/catalog-backup", headers=self.headers).status_code, 405)

    def test_sys017_headers_complete_catalog_and_private_scope(self) -> None:
        response = self.client.get("/api/admin/catalog-backup", headers={**self.headers, "Origin": "http://localhost:3000"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/zip", response.headers["content-type"])
        self.assertIn("no-store", response.headers["cache-control"])
        self.assertIn("private", response.headers["cache-control"])
        self.assertIn("Content-Disposition", response.headers["access-control-expose-headers"])
        self.assertRegex(response.headers["content-disposition"], r'attachment; filename="styl-catalog-backup-\d{8}T\d{6}Z.zip"')
        self.assertEqual(int(response.headers["content-length"]), len(response.content))
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["version"], 1)
            self.assertEqual(manifest["counts"], {"products": 2, "accessories": 1, "mediaFiles": 5})
            self.assertEqual(json.loads(archive.read("data/products.json")), self.products)
            self.assertEqual(json.loads(archive.read("data/accessories.json")), self.accessories)
            self.assertEqual(json.loads(archive.read("data/hero.json")), self.hero)
            self.assertIn(b"PRIVATE-ADMIN-NOTE", archive.read("data/products.json"))
            self.assertEqual(set(archive.namelist()), {
                "manifest.json", *backup.CATALOG_FILES, *backup.SUPPORT_FILES, *self.media,
            })
            for name, value in self.media.items():
                self.assertEqual(archive.read(name), value)
            all_contents = b"".join(archive.read(name) for name in archive.namelist())
            self.assertNotIn(b"PRIVATE-CUSTOMER-NOT-IN-BACKUP", all_contents)
            self.assertNotIn(b"PRIVATE-TOKEN-NOT-IN-BACKUP", all_contents)
            self.assertNotIn(str(self.source).encode(), all_contents)

    def test_sys017_export_uses_shared_catalog_lock_and_busy_is_retryable(self) -> None:
        original = main.create_archive
        def check_lock(*args, **kwargs):
            self.assertTrue(main.CATALOG_LOCK.locked())
            return original(*args, **kwargs)
        with patch.object(main, "create_archive", side_effect=check_lock):
            self.download()
        with main.BACKUP_LOCK:
            response = self.client.get("/api/admin/catalog-backup", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertIn("retry", response.json()["detail"].lower())

    def test_sys017_bad_or_missing_catalog_is_not_reseeded(self) -> None:
        for value in (b"{", b"{}", b'[{"id":7,"id":8,"name":"Duplicate key"}]'):
            with self.subTest(value=value):
                self.paths["DATA_PATH"].write_bytes(value)
                response = self.client.get("/api/admin/catalog-backup", headers=self.headers)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(self.paths["DATA_PATH"].read_bytes(), value)
        self.paths["DATA_PATH"].unlink()
        self.assertEqual(self.client.get("/api/admin/catalog-backup", headers=self.headers).status_code, 409)
        self.assertFalse(self.paths["DATA_PATH"].exists())

    def test_sys017_absent_banner_materializes_defaults_without_writing_source(self) -> None:
        self.paths["HERO_PATH"].unlink()
        with zipfile.ZipFile(io.BytesIO(self.download())) as archive:
            self.assertEqual(json.loads(archive.read("data/hero.json")), main.DEFAULT_HERO.model_dump())
            self.assertEqual(archive.read("public/images/brand/frame-badge.jpg"), b"default banner")
        self.assertFalse(self.paths["HERO_PATH"].exists())

    def test_sys017_legacy_fields_and_empty_catalog_are_preserved(self) -> None:
        legacy = {"id": 9, "slug": "legacy-item", "name": "Legacy", "category": "Racks", "price": 12.5, "currency": "USD"}
        self.paths["DATA_PATH"].write_text(json.dumps([legacy]))
        self.paths["ACCESSORIES_PATH"].write_text("[]")
        path = self.write_archive()
        destination = self.root / "legacy-recovered"
        manifest = backup.restore_archive(path, destination)
        self.assertEqual(manifest["counts"]["products"], 1)
        self.assertEqual(manifest["counts"]["accessories"], 0)
        restored = json.loads((destination / "data/products.json").read_text())
        self.assertEqual(restored, [legacy])
        self.assertNotIn("prices", restored[0])
        self.assertNotIn("publicationStatus", restored[0])

    def test_sys017_missing_media_or_poster_refuses_incomplete_archive(self) -> None:
        for name in ("shared.png", f"{VIDEO}.poster.jpg"):
            path = self.uploads / name
            value = path.read_bytes()
            path.unlink()
            response = self.client.get("/api/admin/catalog-backup", headers=self.headers)
            self.assertEqual(response.status_code, 409)
            self.assertIn("Missing local media", response.json()["detail"])
            path.write_bytes(value)

    def test_sys017_external_and_unsafe_media_do_not_trigger_network_fetches(self) -> None:
        for url in ("https://example.com/private.png?secret=DO-NOT-LOG", "/api/uploads/../inquiries/customer.json", "/images/%2e%2e/.env"):
            self.products[0]["photos"] = [url]
            self.paths["DATA_PATH"].write_text(json.dumps(self.products))
            response = self.client.get("/api/admin/catalog-backup", headers=self.headers)
            self.assertEqual(response.status_code, 409)
            self.assertNotIn("DO-NOT-LOG", response.text)

    def test_sys017_linked_media_is_rejected(self) -> None:
        original = Path.is_symlink
        with patch.object(Path, "is_symlink", lambda path: path.name == "shared.png" or original(path)):
            self.assertEqual(self.client.get("/api/admin/catalog-backup", headers=self.headers).status_code, 409)

    def test_sys017_io_failure_closes_temporary_archive_and_releases_locks(self) -> None:
        files = []
        def temporary(**kwargs):
            file = tempfile.TemporaryFile(**kwargs)
            files.append(file)
            return file
        with patch.object(main, "TemporaryFile", side_effect=temporary), patch.object(main, "create_archive", side_effect=OSError("Disk full")):
            response = self.client.get("/api/admin/catalog-backup", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertTrue(all(file.closed for file in files))
        self.assertFalse(main.BACKUP_LOCK.locked())
        self.assertFalse(main.CATALOG_LOCK.locked())

    def test_ops011_standalone_cold_restore_without_original_server(self) -> None:
        archive_path = self.write_archive()
        with zipfile.ZipFile(archive_path) as archive:
            tool = self.root / "restore_catalog.py"
            tool.write_bytes(archive.read("restore_catalog.py"))
        original_json = {name: (self.data / name).read_bytes() for name in ("products.json", "accessories.json", "hero.json")}
        shutil.rmtree(self.source)
        target = self.root / "recovered"
        process = subprocess.run(
            [sys.executable, str(tool), "restore", str(archive_path), "--destination", str(target)],
            cwd=self.root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout)["status"], "restored")
        for name, value in original_json.items():
            self.assertEqual((target / "data" / name).read_bytes(), value)
        for name, value in self.media.items():
            self.assertEqual((target / name).read_bytes(), value)
        self.assertFalse((target / "data" / "inquiries").exists())
        self.assertFalse((target / "data" / ".env").exists())
        self.assertEqual(list(self.root.glob(".styl-restore-*")), [])
        self.assertEqual(backup.verify_archive(archive_path)["counts"]["products"], 2)

        with patch.multiple(main, DATA_PATH=target / "data/products.json", ACCESSORIES_PATH=target / "data/accessories.json", HERO_PATH=target / "data/hero.json", UPLOAD_PATH=target / "data/uploads"):
            for country, currency, accessory_count in (("CA", "CAD", 1), ("US", "USD", 0)):
                with patch.object(main, "resolve_market", return_value={"countryCode": country, "currency": currency, "locationStatus": "located"}):
                    products = self.client.get("/api/products").json()["items"]
                    self.assertEqual(len(products), 1)
                    self.assertEqual(products[0]["id"], 7)
                    self.assertEqual(products[0]["price"], 750.25 if currency == "CAD" else 600.50)
                    self.assertNotIn("provenance", products[0])
                    self.assertEqual(len(self.client.get("/api/accessories").json()["items"]), accessory_count)
                    self.assertEqual(self.client.get("/api/products/draft-item").status_code, 404)
            self.assertEqual(self.client.get("/api/admin/products", headers=self.headers).json()["items"][0]["provenance"]["notes"], "PRIVATE-ADMIN-NOTE")
            self.assertEqual(self.client.get("/api/hero").json()["item"], self.hero)
            video = self.client.get(f"/api/uploads/{VIDEO}.mp4", headers={"Range": "bytes=10-49"})
            self.assertEqual(video.status_code, 206)
            self.assertEqual(video.content, self.media[f"data/uploads/{VIDEO}.mp4"][10:50])
        media_app = Starlette(routes=[
            Mount("/images", StaticFiles(directory=target / "public/images")),
            Mount("/api/uploads", StaticFiles(directory=target / "data/uploads")),
        ])
        with TestClient(media_app) as media_client:
            self.assertEqual(media_client.get("/images/equipment/rack.svg").content, self.media["public/images/equipment/rack.svg"])
            self.assertEqual(media_client.get(f"/api/uploads/{VIDEO}.poster.jpg").content, self.media[f"data/uploads/{VIDEO}.poster.jpg"])
            self.assertEqual(media_client.get("/api/uploads/shared.png").content, self.media["data/uploads/shared.png"])
        fresh_api = subprocess.run(
            [sys.executable, "-c", """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app) as client:
    assert client.get('/health').status_code == 200
    products = client.get('/api/products').json()['items']
    assert len(products) == 1 and products[0]['id'] == 7
    assert products[0]['currency'] == 'CAD' and products[0]['price'] == 750.25
    assert len(client.get('/api/accessories').json()['items']) == 1
    assert client.get('/api/products/draft-item').status_code == 404
    assert client.get('/api/uploads/shared.png').content.startswith(b'\\x89PNG')
    assert client.get('/api/uploads/1234567890abcdef1234567890abcdef.mp4', headers={'Range': 'bytes=10-49'}).status_code == 206
    assert client.get('/api/hero').json()['item']['title'] == 'Banner'
print('Fresh application recovered from downloaded catalog: OK')
"""],
            cwd=Path(main.__file__).parents[1],
            env={**os.environ, "STYL_DATA_DIR": str(target / "data"), "STYL_ADMIN_TOKEN": "isolated-recovery-token", "STYL_GEOIP_DATABASE": "", "STYL_SMTP_HOST": ""},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(fresh_api.returncode, 0, fresh_api.stderr)

    def test_sys018_checksum_damage_does_not_publish_destination(self) -> None:
        archive = self.rewrite({"data/uploads/shared.png": b"\x89PNG\r\n\x1a\nchanged! shared image"})
        with self.assertRaises(backup.BackupError):
            backup.restore_archive(archive, self.root / "must-not-exist")
        self.assertFalse(self.root.joinpath("must-not-exist").exists())
        self.assertEqual(list(self.root.glob(".styl-restore-*")), [])

    def test_sys018_missing_archive_entry_is_rejected(self) -> None:
        archive = self.rewrite(omit=f"data/uploads/{VIDEO}.poster.jpg")
        with self.assertRaises(backup.BackupError):
            backup.verify_archive(archive)

    def test_sys018_traversal_links_unexpected_files_and_duplicates_are_rejected(self) -> None:
        symlink = zipfile.ZipInfo("public/images/link.svg")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        for name in ("../outside.txt", "/absolute.png", "C:/escape.png", "public/images/../escape.png",
                     "public/images/a\\b.png", "public/images/file:stream.png", "public/images/NUL.png",
                     "public/images/trailing.png ", "data/.env", "data/products.json", "DATA/PRODUCTS.JSON", symlink):
            with self.subTest(name=str(name)):
                with self.assertWarns(UserWarning) if name == "data/products.json" else nullcontext():
                    archive = self.rewrite(additions=[(name, b"bad")])
                with self.assertRaises(backup.BackupError):
                    backup.restore_archive(archive, self.root / "unsafe")
                self.assertFalse((self.root / "unsafe").exists())
                self.assertFalse((self.root / "outside.txt").exists())

    def test_sys018_unsupported_version_and_size_limits_are_rejected(self) -> None:
        content = self.download()
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
        manifest["version"] = 2
        path = self.rewrite({"manifest.json": json.dumps(manifest).encode()})
        with self.assertRaisesRegex(backup.BackupError, "version"):
            backup.verify_archive(path)
        path = self.write_archive(content)
        with patch.object(backup, "MAX_FILE_BYTES", 1), self.assertRaises(backup.BackupError):
            backup.verify_archive(path)

    def test_sys018_encryption_unsupported_compression_and_entry_limit_are_rejected(self) -> None:
        path = self.write_archive()
        with zipfile.ZipFile(path) as archive:
            archive.getinfo("data/uploads/shared.png").flag_bits |= 1
            with self.assertRaisesRegex(backup.BackupError, "Encrypted"):
                backup._archive_index(archive)
        with zipfile.ZipFile(path) as archive:
            archive.getinfo("data/uploads/shared.png").compress_type = zipfile.ZIP_BZIP2
            with self.assertRaisesRegex(backup.BackupError, "unsupported"):
                backup._archive_index(archive)
        with patch.object(backup, "MAX_ENTRIES", 2), self.assertRaises(backup.BackupError):
            backup.verify_archive(path)

    def test_sys018_existing_destination_is_never_overwritten(self) -> None:
        path = self.write_archive()
        destination = self.root / "existing"
        destination.mkdir()
        sentinel = destination / "keep.txt"
        sentinel.write_text("user data")
        with self.assertRaisesRegex(backup.BackupError, "must not exist"):
            backup.restore_archive(path, destination)
        self.assertEqual(sentinel.read_text(), "user data")

    def test_sys018_failed_restore_commit_cleans_staging(self) -> None:
        path = self.write_archive()
        with patch.object(Path, "rename", side_effect=OSError("Commit failed")), self.assertRaises(OSError):
            backup.restore_archive(path, self.root / "not-published")
        self.assertFalse((self.root / "not-published").exists())
        self.assertEqual(list(self.root.glob(".styl-restore-*")), [])

    def test_sys017_media_limit_refuses_before_a_download_is_returned(self) -> None:
        with patch.object(backup, "MAX_FILE_BYTES", 10):
            response = self.client.get("/api/admin/catalog-backup", headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(main.BACKUP_LOCK.locked())

    def test_sys018_restore_insufficient_space_and_invalid_zip_fail_cleanly(self) -> None:
        path = self.write_archive()
        with patch.object(backup.shutil, "disk_usage", return_value=SimpleNamespace(free=0)):
            with self.assertRaisesRegex(backup.BackupError, "disk space"):
                backup.restore_archive(path, self.root / "no-space")
        self.assertFalse((self.root / "no-space").exists())
        path.write_bytes(b"not a ZIP archive")
        process = subprocess.run(
            [sys.executable, str(Path(backup.__file__)), "verify", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(process.returncode, 1)
        self.assertIn("Catalog recovery failed", process.stderr)

if __name__ == "__main__":
    unittest.main()
