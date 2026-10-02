from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

from app import analytics, analytics_reports, main, records, records_archive, support


class RecordsTests(unittest.TestCase):
    """SYS-022 / ADM-014: private verified backups before any optional deletion."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="styl-records-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.inquiries = self.root / "inquiries"
        self.logs = self.root / "website-logs"
        self.backups = self.root / "records"
        self.inquiries.mkdir()
        self.logs.mkdir()
        self.database = self.root / "analytics.sqlite3"
        for replacement in (
            patch.dict(os.environ, {
                "STYL_RECORDS_DIR": str(self.backups), "STYL_WEBSITE_LOG_DIR": str(self.logs),
                "STYL_ANALYTICS_DB": str(self.database), "STYL_ANALYTICS_ENVIRONMENT": "test",
                "STYL_SUPPORT_DB": str(self.root / "support.sqlite3"), "STYL_SUPPORT_ENVIRONMENT": "test",
                "STYL_KNOWLEDGE_DIR": str(self.root / "knowledge"),
                "STYL_ANALYTICS_EMAIL_ENABLED": "false", "STYL_ANALYTICS_RECIPIENTS": "",
                "STYL_SMTP_PASSWORD": "SECRET_MUST_NOT_BE_ARCHIVED",
            }),
            patch.multiple(main, INQUIRIES_PATH=self.inquiries, ADMIN_TOKEN="records-test-only"),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer records-test-only"}
        self.base = "/api/admin/records"
        self.inquiry = {"id": "old", "createdAt": "2020-01-01T00:00:00+00:00", "emailStatus": "sent", "email": "synthetic@example.com"}
        (self.inquiries / "old.json").write_text(json.dumps(self.inquiry))
        (self.logs / "old.log").write_bytes(b"old website log\n")
        (self.logs / "current.active").write_bytes(b"current prefix\n")
        with analytics.get_store().connection() as connection:
            connection.execute("INSERT INTO analytics_aggregate_counts VALUES(?,?,?,?,?,?)",
                               ("2020-01-01T00:00:00.000000+00:00", "total", "all", "page_view", 7, 0))
            analytics_reports._ensure_tables(connection)
            connection.execute("INSERT INTO analytics_report_snapshot VALUES(?,?,?,?,?,?,?)",
                               ("2020-01-01", "America/Los_Angeles", 3, "old report", "text", "html", "2020-01-02T00:00:00+00:00"))
            connection.execute("INSERT INTO analytics_report_delivery VALUES(?,?,?,?,?,?,?,?,?)",
                               ("2020-01-01", "America/Los_Angeles", 3, "synthetic@example.com", "accepted", 1, "2020-01-02T00:00:00+00:00", None, None))
        analytics_reports.save_email_settings(analytics_reports.EmailSettingsInput(
            enabled=False, recipients=["synthetic@example.com"], expectedRevision=0))

    def create(self) -> dict:
        response = self.client.post(self.base + "/archives", headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_missing_analytics_source_is_not_recreated_as_an_empty_success(self) -> None:
        held = self.root / "held-analytics.sqlite3"
        self.database.rename(held)
        response = self.client.post(self.base + "/archives", headers=self.headers)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertFalse(self.database.exists())
        self.assertEqual(list(self.backups.glob("styl-records-*.zip")), [])
        self.assertTrue(held.exists())

    def url(self, value: dict, suffix: str = "") -> str:
        return f"{self.base}/archives/{value['id']}" + suffix

    def download(self, value: dict) -> bytes:
        response = self.client.get(self.url(value, "/download"), headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text[:200] if response.status_code != 200 else "")
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertIn(value["filename"], response.headers["content-disposition"])
        return response.content

    def verify(self, value: dict) -> dict:
        response = self.client.post(self.url(value, "/verify"), headers=self.headers, content=self.download(value))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def remove(self, value: dict, categories=None):
        return self.client.post(self.url(value, "/remove"), headers=self.headers, json={
            "confirmation": "REMOVE " + value["id"], "categories": categories or ["analytics", "inquiries", "websiteLogs"],
        })

    def test_auth_every_route_and_invalid_ids(self) -> None:
        identifier = "a" * 32
        for method, suffix, body in (
            ("get", "", None), ("post", "/archives", None),
            ("get", f"/archives/{identifier}/download", None),
            ("post", f"/archives/{identifier}/verify", None),
            ("post", f"/archives/{identifier}/remove", {"confirmation": "x", "categories": ["inquiries"]}),
            ("delete", f"/archives/{identifier}", {"confirmation": "x"}),
        ):
            response = self.client.request(method, self.base + suffix, json=body)
            self.assertEqual(response.status_code, 401, (method, suffix, response.text))
        response = self.client.get(self.base + "/archives/not-valid/download", headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(self.backups.exists())

    def test_complete_private_archive_and_cold_restore(self) -> None:
        value = self.create()
        content = self.download(value)
        self.assertEqual(hashlib.sha256(content).hexdigest(), value["sha256"])
        self.assertEqual(len(content), value["bytes"])
        saved = self.root / "saved.zip"
        saved.write_bytes(content)
        destination = self.root / "offline"
        manifest = records_archive.restore_archive(saved, destination)
        self.assertEqual(manifest["id"], value["id"])
        self.assertEqual((destination / "inquiries" / "old.json").read_bytes(), (self.inquiries / "old.json").read_bytes())
        self.assertEqual((destination / "website-logs" / "old.log").read_bytes(), b"old website log\n")
        self.assertTrue((destination / "restore_records.py").exists())
        with closing(sqlite3.connect(destination / "analytics.sqlite3")) as database:
            self.assertEqual(database.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(database.execute("SELECT count FROM analytics_aggregate_counts").fetchone()[0], 7)
            self.assertEqual(database.execute("SELECT recipients FROM analytics_email_settings").fetchone()[0], '["synthetic@example.com"]')
        with zipfile.ZipFile(saved) as archive:
            self.assertNotIn(b"SECRET_MUST_NOT_BE_ARCHIVED", b"".join(archive.read(name) for name in archive.namelist()))
        with self.assertRaises(records_archive.RecordsError):
            records_archive.restore_archive(saved, destination)

    def test_download_is_never_verification_or_deletion(self) -> None:
        value = self.create()
        self.download(value)
        listed = self.client.get(self.base, headers=self.headers).json()["archives"][0]
        self.assertIsNone(listed["verifiedAt"])
        self.assertEqual(self.remove(value).status_code, 409)
        response = self.client.request("DELETE", self.url(value), headers=self.headers,
                                       json={"confirmation": "DELETE BACKUP " + value["id"]})
        self.assertEqual(response.status_code, 409)
        self.assertTrue((self.inquiries / "old.json").exists())

    def test_verification_rejects_truncated_wrong_and_oversized_files(self) -> None:
        value = self.create()
        content = self.download(value)
        for bad in (content[:-1], b"x" * len(content), content + b"x"):
            response = self.client.post(self.url(value, "/verify"), headers=self.headers, content=bad)
            self.assertEqual(response.status_code, 422)
        self.assertIsNone(records.get_archive(value["id"])["verifiedAt"])
        self.assertEqual(self.remove(value).status_code, 409)

    def test_verified_removal_preserves_new_changed_active_and_safety_metadata(self) -> None:
        (self.inquiries / "pending.json").write_text(json.dumps({**self.inquiry, "emailStatus": "pending"}))
        value = self.verify(self.create())
        (self.inquiries / "new.json").write_text(json.dumps(self.inquiry))
        (self.logs / "current.active").write_bytes(b"current prefix\nnew bytes\n")
        (self.logs / "new.log").write_bytes(b"new file")
        with analytics.get_store().connection() as connection:
            connection.execute("INSERT INTO analytics_aggregate_counts VALUES(?,?,?,?,?,?)",
                               (analytics.stamp(analytics.hour_start(datetime.now(timezone.utc))), "total", "all", "page_view", 2, 0))
        response = self.remove(value)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["removal"]["inquiries"], 1)
        self.assertEqual(response.json()["removal"]["websiteLogs"], 1)
        self.assertEqual(response.json()["removal"]["analyticsRows"], 1)
        self.assertFalse((self.inquiries / "old.json").exists())
        for path in (self.inquiries / "new.json", self.inquiries / "pending.json", self.logs / "current.active", self.logs / "new.log"):
            self.assertTrue(path.exists(), path.name)
        with analytics.get_store().connection() as connection:
            self.assertEqual(connection.execute("SELECT count FROM analytics_aggregate_counts").fetchone()[0], 2)
            self.assertEqual(connection.execute("SELECT count(*) FROM analytics_report_delivery").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT count(*) FROM analytics_report_snapshot").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT revision FROM analytics_email_settings").fetchone()[0], 1)
        self.assertEqual(self.remove(value).status_code, 409)
        self.assertTrue((self.backups / value["filename"]).exists())

    def test_changed_records_and_sql_rows_are_not_removed(self) -> None:
        value = self.verify(self.create())
        changed = {**self.inquiry, "emailStatus": "failed"}
        (self.inquiries / "old.json").write_text(json.dumps(changed))
        (self.logs / "old.log").write_bytes(b"changed!")
        with analytics.get_store().connection() as connection:
            connection.execute("UPDATE analytics_aggregate_counts SET count=8")
        response = self.remove(value)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()["removal"]
        self.assertEqual((result["inquiries"], result["websiteLogs"], result["analyticsRows"]), (0, 0, 0))
        self.assertGreaterEqual(result["skipped"], 3)
        self.assertEqual(json.loads((self.inquiries / "old.json").read_text()), changed)
        with analytics.get_store().connection() as connection:
            self.assertEqual(connection.execute("SELECT count FROM analytics_aggregate_counts").fetchone()[0], 8)

    def test_only_explicitly_selected_categories_are_removed(self) -> None:
        value = self.verify(self.create())
        response = self.remove(value, ["websiteLogs"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue((self.inquiries / "old.json").exists())
        self.assertFalse((self.logs / "old.log").exists())
        self.assertEqual(response.json()["removal"]["analyticsRows"], 0)

    def test_wrong_confirmation_and_unknown_categories_fail_without_deleting(self) -> None:
        value = self.verify(self.create())
        for payload, expected in (
            ({"confirmation": "yes", "categories": ["inquiries"]}, 409),
            ({"confirmation": "REMOVE " + value["id"], "categories": ["catalog"]}, 422),
            ({"confirmation": "REMOVE " + value["id"], "categories": []}, 422),
        ):
            response = self.client.post(self.url(value, "/remove"), headers=self.headers, json=payload)
            self.assertEqual(response.status_code, expected)
        self.assertTrue((self.inquiries / "old.json").exists())

    def test_damaged_server_archive_blocks_removal_even_after_prior_verification(self) -> None:
        value = self.verify(self.create())
        (self.backups / value["filename"]).write_bytes(b"damaged")
        self.assertEqual(self.remove(value).status_code, 409)
        self.assertTrue((self.inquiries / "old.json").exists())

    def test_delete_verified_server_backup_keeps_sources_and_audit_but_blocks_removal(self) -> None:
        value = self.verify(self.create())
        response = self.client.request("DELETE", self.url(value), headers=self.headers,
                                       json={"confirmation": "DELETE BACKUP " + value["id"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["archiveDeletedAt"])
        self.assertFalse((self.backups / value["filename"]).exists())
        self.assertTrue((self.inquiries / "old.json").exists())
        self.assertEqual(self.remove(value).status_code, 409)
        self.assertEqual(self.client.get(self.url(value, "/download"), headers=self.headers).status_code, 409)
        self.assertEqual(len(self.client.get(self.base, headers=self.headers).json()["archives"]), 1)

    def test_no_age_expiry_even_with_mail_disabled(self) -> None:
        value = self.create()
        with patch.object(analytics_reports, "_send") as send:
            analytics_reports.run_due(datetime(2035, 1, 1, tzinfo=timezone.utc))
            send.assert_not_called()
        with analytics.get_store().connection() as connection:
            for table in ("analytics_aggregate_counts", "analytics_report_snapshot", "analytics_report_delivery"):
                self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 1)
        self.assertTrue((self.backups / value["filename"]).exists())
        self.assertTrue((self.inquiries / "old.json").exists())

    def test_unconfigured_logs_are_explicit_not_claimed_covered(self) -> None:
        with patch.dict(os.environ, {"STYL_WEBSITE_LOG_DIR": ""}):
            status = self.client.get(self.base, headers=self.headers)
            self.assertEqual(status.status_code, 200, status.text)
            self.assertFalse(status.json()["websiteLogs"]["configured"])
            self.assertTrue(status.json()["warnings"])
            self.assertEqual(self.create()["counts"]["websiteLogs"], 0)

    def test_invalid_private_paths_and_unexpected_log_files_fail_explicitly(self) -> None:
        with patch.dict(os.environ, {"STYL_RECORDS_DIR": str(main.UPLOAD_PATH.resolve() / "private-records")}):
            self.assertEqual(self.client.post(self.base + "/archives", headers=self.headers).status_code, 409)
        (self.logs / "unexpected.env").write_text("not a website log")
        self.assertEqual(self.client.post(self.base + "/archives", headers=self.headers).status_code, 409)

    def test_storage_pressure_warns_and_does_not_delete_to_make_space(self) -> None:
        usage = records.shutil.disk_usage(self.root)
        low = type(usage)(total=usage.total, used=usage.total - 1024, free=1024)
        with patch.object(records.shutil, "disk_usage", return_value=low):
            self.assertTrue(self.client.get(self.base, headers=self.headers).json()["warnings"])
            response = self.client.post(self.base + "/archives", headers=self.headers)
            self.assertEqual(response.status_code, 409, response.text)
        self.assertTrue((self.logs / "old.log").exists())
        self.assertTrue((self.inquiries / "old.json").exists())

    def test_concurrent_operation_is_rejected_without_touching_sources(self) -> None:
        with records.OPERATIONS:
            self.assertEqual(self.client.post(self.base + "/archives", headers=self.headers).status_code, 409)
        self.assertTrue((self.logs / "old.log").exists())

    def test_interrupted_removal_retains_archive_and_blocks_unsafe_retry(self) -> None:
        value = self.verify(self.create())
        original = Path.unlink
        def failure(path, *args, **kwargs):
            if path == self.logs / "old.log":
                raise OSError("simulated filesystem error")
            return original(path, *args, **kwargs)
        with patch.object(Path, "unlink", failure):
            response = self.remove(value, ["inquiries", "websiteLogs"])
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("may already have been removed", response.json()["detail"])
        self.assertEqual(records.get_archive(value["id"])["removalState"], "failed")
        self.assertTrue((self.backups / value["filename"]).exists())
        self.assertEqual(self.remove(value).status_code, 409)
        self.assertTrue(self.client.get(self.base, headers=self.headers).json()["warnings"])
        response = self.client.request("DELETE", self.url(value), headers=self.headers,
                                       json={"confirmation": "DELETE BACKUP " + value["id"]})
        self.assertEqual(response.status_code, 409)

    def test_archive_rejects_traversal_missing_extra_and_checksum_damage(self) -> None:
        value = self.create()
        content = self.download(value)
        for mode in ("extra", "missing", "damage", "traversal"):
            output = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output, "w") as target:
                for item in source.infolist():
                    if mode == "missing" and item.filename == "analytics.sqlite3":
                        continue
                    data = source.read(item)
                    if mode == "damage" and item.filename == "website-logs/old.log":
                        data = b"x" * len(data)
                    target.writestr(item, data)
                if mode in ("extra", "traversal"):
                    target.writestr("extra" if mode == "extra" else "../outside", b"bad")
            saved = self.root / f"{mode}.zip"
            saved.write_bytes(output.getvalue())
            with self.assertRaises(records_archive.RecordsError):
                records_archive.restore_archive(saved, self.root / f"restore-{mode}")
            self.assertFalse((self.root / f"restore-{mode}").exists())

    def test_hard_link_sources_are_not_exported_or_removed(self) -> None:
        os.link(self.logs / "old.log", self.logs / "linked.log")
        response = self.client.post(self.base + "/archives", headers=self.headers)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertTrue((self.logs / "old.log").exists())

    def test_snapshot_contains_live_prefix_but_later_append_is_not_in_backup(self) -> None:
        value = self.create()
        with (self.logs / "current.active").open("ab") as target:
            target.write(b"later\n")
        content = self.download(value)
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            self.assertEqual(archive.read("website-logs/current.active"), b"current prefix\n")
        verified = self.verify(value)
        self.assertEqual(self.remove(verified, ["websiteLogs"]).status_code, 200)
        self.assertEqual((self.logs / "current.active").read_bytes(), b"current prefix\nlater\n")

    def test_current_hour_is_kept_even_if_unchanged_since_backup(self) -> None:
        with analytics.get_store().connection() as connection:
            connection.execute("INSERT INTO analytics_aggregate_counts VALUES(?,?,?,?,?,?)",
                               (analytics.stamp(analytics.hour_start(datetime.now(timezone.utc))), "total", "all", "page_view", 2, 0))
        value = self.verify(self.create())
        self.assertEqual(self.remove(value, ["analytics"]).status_code, 200)
        with analytics.get_store().connection() as connection:
            self.assertEqual(connection.execute("SELECT count FROM analytics_aggregate_counts").fetchone()[0], 2)

    def test_schema_change_blocks_analytics_deletion_and_retains_recovery(self) -> None:
        value = self.verify(self.create())
        with analytics.get_store().connection() as connection:
            connection.execute("ALTER TABLE analytics_aggregate_counts ADD COLUMN future_field TEXT")
        response = self.remove(value, ["analytics"])
        self.assertEqual(response.status_code, 503, response.text)
        with analytics.get_store().connection() as connection:
            self.assertEqual(connection.execute("SELECT count FROM analytics_aggregate_counts").fetchone()[0], 7)
        self.assertEqual(records.get_archive(value["id"])["removalState"], "failed")
        self.assertTrue((self.backups / value["filename"]).exists())

    def test_overlapping_backups_do_not_remove_new_records(self) -> None:
        first = self.verify(self.create())
        second = self.verify(self.create())
        self.assertEqual(self.remove(first).status_code, 200)
        (self.inquiries / "new.json").write_text(json.dumps(self.inquiry))
        response = self.remove(second)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["removal"]["inquiries"], 0)
        self.assertTrue((self.inquiries / "new.json").exists())

    def test_unindexed_archive_is_reported_without_deletion(self) -> None:
        self.backups.mkdir()
        orphan = self.backups / "styl-records-orphan.zip"
        orphan.write_bytes(b"operator must review this interrupted preparation")
        response = self.client.get(self.base, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("unindexed backup", " ".join(response.json()["warnings"]))
        self.assertTrue(orphan.exists())

    def test_report_content_is_preserved_for_pending_failed_and_ambiguous_retries(self) -> None:
        for state in ("pending", "failed", "sending", "ambiguous"):
            with self.subTest(state=state):
                with analytics.get_store().connection() as connection:
                    connection.execute("UPDATE analytics_report_delivery SET status=?", (state,))
                value = self.verify(self.create())
                self.assertEqual(self.remove(value, ["analytics"]).status_code, 200)
                with analytics.get_store().connection() as connection:
                    snapshot = connection.execute("SELECT text_body,html_body FROM analytics_report_snapshot").fetchone()
                    self.assertEqual(tuple(snapshot), ("text", "html"))
                    self.assertEqual(connection.execute("SELECT status FROM analytics_report_delivery").fetchone()[0], state)

    def test_bundled_tool_restores_without_original_records_or_installed_packages(self) -> None:
        value = self.create()
        saved = self.root / "off-server.zip"
        saved.write_bytes(self.download(value))
        tool = self.root / "restore_records.py"
        with zipfile.ZipFile(saved) as archive:
            tool.write_bytes(archive.read("restore_records.py"))
        shutil.rmtree(self.inquiries)
        shutil.rmtree(self.logs)
        self.database.unlink()
        destination = self.root / "cold-recovered"
        result = subprocess.run(
            [sys.executable, "-S", str(tool), str(saved), "--destination", str(destination)],
            cwd=self.root, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(json.loads(result.stdout)["restored"])
        self.assertEqual((destination / "website-logs" / "old.log").read_bytes(), b"old website log\n")
        self.assertEqual(json.loads((destination / "inquiries" / "old.json").read_text()), self.inquiry)
        with closing(sqlite3.connect(destination / "analytics.sqlite3")) as database:
            self.assertEqual(database.execute("SELECT count FROM analytics_aggregate_counts").fetchone()[0], 7)

    def support_fixture(self) -> tuple[str, str]:
        closed, active = "c" * 32, "a" * 32
        with support.get_store().connection() as database:
            for identifier, state in ((closed, "closed"), (active, "ai")):
                database.execute("""INSERT INTO conversations(id,token_hash,state,revision,generation,
                                 created_at,updated_at,currency,needs_human,reason) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                                 (identifier, hashlib.sha256(identifier.encode()).hexdigest(), state, 1, 0,
                                  "2020-01-01", "2020-01-01", "CAD", 0, None))
                database.execute("""INSERT INTO messages(id,conversation_id,role,text,created_at,references_json,
                                 client_message_id,request_hash,response_json) VALUES(?,?,?,?,?,?,?,?,?)""",
                                 ("message-" + identifier, identifier, "customer", "Synthetic catalog question",
                                  "2020-01-01", "[]", "request-" + identifier, "hash", None))
        return closed, active

    def test_support_snapshot_restores_all_threads_and_settings(self) -> None:
        self.support_fixture()
        value = self.create()
        self.assertEqual(value["counts"]["supportConversations"], 2)
        self.assertEqual(value["counts"]["supportMessages"], 2)
        saved = self.root / "support-download.zip"
        saved.write_bytes(self.download(value))
        destination = self.root / "support-restore"
        records_archive.restore_archive(saved, destination)
        with closing(sqlite3.connect(destination / "support.sqlite3")) as database:
            self.assertEqual(database.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(database.execute("SELECT count(*) FROM conversations").fetchone()[0], 2)
            self.assertEqual(database.execute("SELECT count(*) FROM messages").fetchone()[0], 2)
            self.assertEqual(database.execute("SELECT environment FROM settings").fetchone()[0], "test")

    def test_support_removal_only_cascades_unchanged_closed_threads(self) -> None:
        closed, active = self.support_fixture()
        value = self.verify(self.create())
        response = self.remove(value, ["support"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["removal"]["supportConversations"], 1)
        with support.get_store().connection() as database:
            self.assertIsNone(database.execute("SELECT id FROM conversations WHERE id=?", (closed,)).fetchone())
            self.assertIsNotNone(database.execute("SELECT id FROM conversations WHERE id=?", (active,)).fetchone())
            self.assertEqual(database.execute("SELECT count(*) FROM messages").fetchone()[0], 1)
            self.assertEqual(database.execute("SELECT count(*) FROM settings").fetchone()[0], 1)
        self.assertTrue((self.inquiries / "old.json").exists())

    def test_support_changed_message_or_reopened_thread_survives(self) -> None:
        closed, _active = self.support_fixture()
        value = self.verify(self.create())
        with support.get_store().connection() as database:
            database.execute("UPDATE messages SET text='Later change' WHERE conversation_id=?", (closed,))
        response = self.remove(value, ["support"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["removal"]["supportConversations"], 0)
        second = self.verify(self.create())
        with support.get_store().connection() as database:
            database.execute("UPDATE conversations SET state='human',revision=revision+1 WHERE id=?", (closed,))
        self.assertEqual(self.remove(second, ["support"]).json()["removal"]["supportConversations"], 0)

    def test_closed_support_thread_with_pending_job_is_not_removed(self) -> None:
        closed, _active = self.support_fixture()
        with support.get_store().connection() as database:
            database.execute("""INSERT INTO jobs(id,conversation_id,message_id,generation,settings_revision,status,
                             payload,usage_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                             ("pending-job", closed, "message-" + closed, 0, 0, "queued", "{}", "{}", "2020-01-01", "2020-01-01"))
        value = self.verify(self.create())
        response = self.remove(value, ["support"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["removal"]["supportConversations"], 0)
        with support.get_store().connection() as database:
            self.assertEqual(database.execute("SELECT count(*) FROM jobs").fetchone()[0], 1)

    def test_legacy_archive_cannot_authorize_support_cleanup_or_partial_source_removal(self) -> None:
        value = self.verify(self.create())
        self.support_fixture()
        response = self.remove(value, ["inquiries", "support"])
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("no support snapshot", response.json()["detail"])
        self.assertTrue((self.inquiries / "old.json").exists())
        self.assertEqual(records.get_archive(value["id"])["removalState"], "ready")

    def test_sup014_knowledge_source_versions_are_backed_up_and_restored_but_not_removed_with_threads(self) -> None:
        self.support_fixture()
        knowledge = self.root / "knowledge"
        knowledge.mkdir()
        contents = b"%PDF-1.4\nSynthetic immutable manual version\n%%EOF"
        name = hashlib.sha256(contents).hexdigest() + ".pdf"
        (knowledge / name).write_bytes(contents)
        value = self.create()
        self.assertEqual(value["counts"]["knowledgeFiles"], 1)
        saved = self.root / "knowledge-download.zip"
        saved.write_bytes(self.download(value))
        destination = self.root / "knowledge-restore"
        manifest = records_archive.restore_archive(saved, destination)
        self.assertTrue(manifest["knowledgeIncluded"])
        self.assertEqual((destination / "knowledge" / name).read_bytes(), contents)
        verified = self.verify(value)
        response = self.remove(verified, ["support"])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue((knowledge / name).exists())
        self.assertEqual(response.json()["removal"]["supportConversations"], 1)

    def test_sup014_arbitrary_files_in_knowledge_storage_fail_backup_explicitly(self) -> None:
        knowledge = self.root / "knowledge"
        knowledge.mkdir()
        (knowledge / "credentials.env").write_text("synthetic-private-value")
        response = self.client.post(self.base + "/archives", headers=self.headers)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertTrue((knowledge / "credentials.env").exists())

    def test_sup014_changed_content_addressed_knowledge_blob_never_yields_successful_backup(self) -> None:
        knowledge = self.root / "knowledge"
        knowledge.mkdir()
        (knowledge / ("a" * 64 + ".pdf")).write_bytes(b"Corrupt source with the wrong content address")
        response = self.client.post(self.base + "/archives", headers=self.headers)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("content hash", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
