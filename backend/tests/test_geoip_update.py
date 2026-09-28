import importlib.util
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


spec = importlib.util.spec_from_file_location(
    "styl_geoip_update", Path(__file__).resolve().parents[2] / "deploy" / "update_geoip.py",
)
assert spec is not None and spec.loader is not None
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class GeoIPUpdateTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="styl-geoip-update-test-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / "source.mmdb"
        self.target = self.root / "country.mmdb"
        self.source.write_bytes(b"new database")
        self.target.write_bytes(b"existing database")
        self.now = 1_800_000_000

    def test_metadata_rejects_wrong_edition(self) -> None:
        reader = Mock()
        reader.metadata.return_value = SimpleNamespace(database_type="GeoLite2-City", build_epoch=self.now)
        with patch.object(updater.maxminddb, "open_database") as opened:
            opened.return_value.__enter__.return_value = reader
            with self.assertRaisesRegex(ValueError, "Country"):
                updater.database_epoch(self.source)

    def test_freshness_boundaries(self) -> None:
        for offset, valid in (
            (0, True), (-updater.MAX_AGE_SECONDS, True),
            (-updater.MAX_AGE_SECONDS - 1, False),
            (86400, True), (86401, False),
        ):
            with self.subTest(offset=offset), patch.object(updater, "database_epoch", return_value=self.now + offset):
                if valid:
                    self.assertEqual(updater.validate_database(self.source, self.now), self.now + offset)
                else:
                    with self.assertRaises(ValueError):
                        updater.validate_database(self.source, self.now)

    def test_publish_is_atomic_and_sets_read_only_service_permissions(self) -> None:
        original_replace = updater.os.replace
        with patch.object(updater, "validate_database") as validate, \
                patch.object(updater.os, "chown", create=True) as chown, \
                patch.object(updater.os, "replace", wraps=original_replace) as replace:
            self.assertTrue(updater.publish_database(self.source, self.target, 123, self.now))
        validate.assert_called_once_with(self.source, self.now)
        temporary, destination = replace.call_args.args
        self.assertEqual(temporary.parent, self.target.parent)
        self.assertEqual(destination, self.target)
        chown.assert_called_once_with(temporary, 0, 123)
        self.assertEqual(self.target.read_bytes(), b"new database")
        self.assertEqual(list(self.root.glob(".country-*")), [])

    def test_same_database_is_not_replaced(self) -> None:
        self.target.write_bytes(self.source.read_bytes())
        with patch.object(updater, "validate_database"), \
                patch.object(updater.os, "chown", create=True) as chown, \
                patch.object(updater.os, "replace") as replace:
            self.assertFalse(updater.publish_database(self.source, self.target, 123, self.now))
        replace.assert_not_called()
        chown.assert_called_once_with(self.target, 0, 123)

    def test_invalid_download_keeps_existing_database(self) -> None:
        with patch.object(updater, "validate_database", side_effect=ValueError("Invalid database")):
            with self.assertRaises(ValueError):
                updater.publish_database(self.source, self.target, 123, self.now)
        self.assertEqual(self.target.read_bytes(), b"existing database")
        self.assertEqual(list(self.root.glob(".country-*")), [])

    def test_failed_replace_preserves_active_database_and_cleans_temporary_file(self) -> None:
        with patch.object(updater, "validate_database"), \
                patch.object(updater.os, "chown", create=True), \
                patch.object(updater.os, "replace", side_effect=OSError("Disk write failed")):
            with self.assertRaises(OSError):
                updater.publish_database(self.source, self.target, 123, self.now)
        self.assertEqual(self.target.read_bytes(), b"existing database")
        self.assertEqual(list(self.root.glob(".country-*")), [])

    def test_expired_database_removed_but_fresh_database_retained(self) -> None:
        with patch.object(updater, "database_epoch", return_value=self.now):
            updater.discard_expired(self.target, self.now)
        self.assertTrue(self.target.exists())
        with patch.object(updater, "database_epoch", return_value=self.now - updater.MAX_AGE_SECONDS - 1):
            with self.assertLogs(updater.logger, level="WARNING"):
                updater.discard_expired(self.target, self.now)
        self.assertFalse(self.target.exists())

    def test_invalid_existing_database_does_not_leak_exception_details(self) -> None:
        with patch.object(updater, "database_epoch", side_effect=ValueError("PRIVATE_TEST_DETAIL")):
            with self.assertLogs(updater.logger, level="WARNING") as captured:
                updater.discard_expired(self.target, self.now)
        self.assertNotIn("PRIVATE_TEST_DETAIL", " ".join(captured.output))

    def test_non_root_and_insecure_config_are_rejected(self) -> None:
        with patch.dict(sys.modules, {"grp": SimpleNamespace()}):
            with patch.object(updater.os, "geteuid", return_value=1000, create=True):
                with self.assertRaises(PermissionError):
                    updater.main()
            config = Mock()
            config.stat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o644, st_uid=0)
            with patch.object(updater.os, "geteuid", return_value=0, create=True), patch.object(updater, "CONFIG", config):
                with self.assertRaisesRegex(PermissionError, "0600"):
                    updater.main()

    def test_download_failure_does_not_publish_or_expose_provider_output(self) -> None:
        config = Mock()
        config.stat.return_value = SimpleNamespace(st_mode=stat.S_IFREG | 0o600, st_uid=0)
        group = SimpleNamespace(getgrnam=lambda _: SimpleNamespace(gr_gid=123))
        result = SimpleNamespace(returncode=1, stdout="PRIVATE_SIGNED_URL", stderr="PRIVATE_KEY")
        with patch.dict(sys.modules, {"grp": group}), \
                patch.object(updater.os, "geteuid", return_value=0, create=True), \
                patch.object(updater.os, "chown", create=True), \
                patch.object(updater, "CONFIG", config), \
                patch.object(updater, "CACHE", self.root / "cache"), \
                patch.object(updater, "DATABASE", self.target), \
                patch.object(updater, "discard_expired"), \
                patch.object(updater.subprocess, "run", return_value=result) as run, \
                patch.object(updater, "publish_database") as publish:
            with self.assertRaises(RuntimeError) as captured:
                updater.main()
        self.assertNotIn("PRIVATE_", str(captured.exception))
        self.assertTrue(run.call_args.kwargs["capture_output"])
        publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
