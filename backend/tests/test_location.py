from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import stat
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import Request
import maxminddb

from app import location


UNKNOWN = {"countryCode": None, "currency": "USD", "locationStatus": "unknown"}
CANADA = {"countryCode": "CA", "currency": "CAD", "locationStatus": "located"}
USA = {"countryCode": "US", "currency": "USD", "locationStatus": "located"}


def request(host: str | None = "8.8.8.8", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({
        "type": "http",
        "client": (host, 12345) if host is not None else None,
        "headers": headers or [],
    })


def database_stat(inode: int = 1, modified: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        st_mode=stat.S_IFREG, st_dev=1, st_ino=inode, st_size=100,
        st_mtime_ns=modified, st_ctime_ns=modified,
    )


class LocationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.database = location._CountryDatabase()
        self.reader = Mock(spec=maxminddb.Reader)
        self.reader.get.return_value = {"country": {"iso_code": "CA"}}
        patches = {
            "environment": patch.dict(os.environ, {"STYL_GEOIP_DATABASE": "country.mmdb"}),
            "database": patch.object(location, "_database", self.database),
            "stat": patch.object(Path, "stat", return_value=database_stat()),
            "open": patch.object(location.maxminddb, "open_database", return_value=self.reader),
        }
        self.mocks = {}
        for name, replacement in patches.items():
            self.mocks[name] = replacement.start()
            self.addCleanup(replacement.stop)
        self.addCleanup(self.database.close)

    def test_country_controls_currency(self) -> None:
        for code, expected in (("CA", CANADA), ("US", USA), ("GB", {
            "countryCode": "GB", "currency": "USD", "locationStatus": "located",
        })):
            with self.subTest(code=code):
                self.reader.get.return_value = {"country": {"iso_code": code}}
                self.assertEqual(location.resolve_market(request()), expected)

    def test_unlocated_and_malformed_records_use_unknown_usd(self) -> None:
        for record in (
            None, {}, [], {"country": None}, {"country": []},
            {"country": {}}, {"country": {"iso_code": None}},
            {"country": {"iso_code": 123}}, {"country": {"iso_code": "CAN"}},
            {"country": {"iso_code": "ca"}}, {"country": {"iso_code": "ＣＡ"}},
            {"registered_country": {"iso_code": "CA"}},
            {"represented_country": {"iso_code": "CA"}},
        ):
            with self.subTest(record=record):
                self.reader.get.return_value = record
                self.assertEqual(location.resolve_market(request()), UNKNOWN)

    def test_registered_country_does_not_override_location(self) -> None:
        self.reader.get.return_value = {
            "country": {"iso_code": "US"}, "registered_country": {"iso_code": "CA"},
        }
        self.assertEqual(location.resolve_market(request()), USA)

    def test_private_local_reserved_and_invalid_addresses_skip_database(self) -> None:
        for host in (
            None, "", "testclient", "not-an-ip", "8.8.8.8:443",
            "8.8.8.8, 1.1.1.1", "127.0.0.1", "10.1.2.3", "172.16.0.1",
            "192.168.1.1", "169.254.1.1", "100.64.0.1", "0.0.0.0",
            "192.0.2.1", "224.0.0.1", "255.255.255.255",
            "::1", "::", "fc00::1", "fd12::1", "fe80::1", "2001:db8::1",
            "ff02::1", "::ffff:192.168.1.1", "fe80::1%eth0",
            "2606:4700:4700::1111%eth0",
        ):
            with self.subTest(host=host):
                self.assertEqual(location.resolve_market(request(host)), UNKNOWN)
        self.mocks["open"].assert_not_called()
        self.mocks["stat"].assert_not_called()

    def test_public_ipv6_and_ipv4_mapped_addresses(self) -> None:
        for host, expected in (
            ("2606:4700:4700::1111", "2606:4700:4700::1111"),
            ("::ffff:8.8.8.8", "8.8.8.8"),
        ):
            with self.subTest(host=host):
                self.assertEqual(location.resolve_market(request(host)), CANADA)
                self.reader.get.assert_called_with(expected)

    def test_country_and_forwarded_headers_are_ignored(self) -> None:
        headers = [
            (b"x-forwarded-for", b"1.1.1.1"),
            (b"forwarded", b"for=1.1.1.1"),
            (b"x-real-ip", b"1.1.1.1"),
            (b"cf-ipcountry", b"CA"),
            (b"x-country-code", b"CA"),
            (b"x-vercel-ip-country", b"CA"),
        ]
        self.reader.get.return_value = {"country": {"iso_code": "US"}}
        self.assertEqual(location.resolve_market(request(headers=headers)), USA)
        self.reader.get.assert_called_once_with("8.8.8.8")
        self.assertEqual(location.resolve_market(request("127.0.0.1", headers)), UNKNOWN)
        self.reader.get.assert_called_once()

    def test_unset_database_warns_once_and_can_be_enabled(self) -> None:
        os.environ.pop("STYL_GEOIP_DATABASE")
        with self.assertLogs(location.logger, level="WARNING") as captured:
            self.assertEqual(location.resolve_market(request()), UNKNOWN)
            self.assertEqual(location.resolve_market(request()), UNKNOWN)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("STYL_GEOIP_DATABASE is not set", captured.output[0])
        self.assertNotIn("8.8.8.8", captured.output[0])
        self.mocks["open"].assert_not_called()
        os.environ["STYL_GEOIP_DATABASE"] = "country.mmdb"
        self.assertEqual(location.resolve_market(request()), CANADA)

    def test_missing_or_unreadable_database_warns_without_error_details(self) -> None:
        for error in (FileNotFoundError("8.8.8.8"), PermissionError("8.8.8.8")):
            with self.subTest(error=type(error).__name__):
                self.database._warning = None
                self.mocks["stat"].side_effect = error
                with self.assertLogs(location.logger, level="WARNING") as captured:
                    self.assertEqual(location.resolve_market(request()), UNKNOWN)
                    self.assertEqual(location.resolve_market(request()), UNKNOWN)
                self.assertEqual(len(captured.output), 1)
                self.assertIn("missing or unreadable", captured.output[0])
                self.assertNotIn("8.8.8.8", captured.output[0])
        self.mocks["open"].assert_not_called()
        self.mocks["stat"].side_effect = None
        self.assertEqual(location.resolve_market(request()), CANADA)

    def test_non_regular_file_is_not_opened(self) -> None:
        self.mocks["stat"].return_value.st_mode = stat.S_IFDIR
        with self.assertLogs(location.logger, level="WARNING"):
            self.assertEqual(location.resolve_market(request()), UNKNOWN)
        self.mocks["open"].assert_not_called()

    def test_corrupt_database_is_not_retried_until_replaced(self) -> None:
        self.mocks["open"].side_effect = maxminddb.InvalidDatabaseError("8.8.8.8")
        with self.assertLogs(location.logger, level="WARNING") as captured:
            self.assertEqual(location.resolve_market(request()), UNKNOWN)
            self.assertEqual(location.resolve_market(request()), UNKNOWN)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("invalid or unreadable", captured.output[0])
        self.assertNotIn("8.8.8.8", captured.output[0])
        self.mocks["open"].assert_called_once()
        self.mocks["open"].side_effect = None
        self.mocks["stat"].return_value = database_stat(inode=2)
        self.assertEqual(location.resolve_market(request()), CANADA)

    def test_lookup_failure_closes_reader_and_recovers_on_replacement(self) -> None:
        self.reader.get.side_effect = maxminddb.InvalidDatabaseError("8.8.8.8")
        with self.assertLogs(location.logger, level="WARNING") as captured:
            self.assertEqual(location.resolve_market(request()), UNKNOWN)
            self.assertEqual(location.resolve_market(request()), UNKNOWN)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("lookup failed", captured.output[0])
        self.assertNotIn("8.8.8.8", captured.output[0])
        self.reader.close.assert_called_once()
        self.reader.get.side_effect = None
        self.mocks["stat"].return_value = database_stat(modified=2)
        self.assertEqual(location.resolve_market(request()), CANADA)

    def test_reader_is_cached_but_ip_results_are_not(self) -> None:
        for host in ("8.8.8.8", "1.1.1.1", "8.8.8.8"):
            self.assertEqual(location.resolve_market(request(host)), CANADA)
        self.mocks["open"].assert_called_once_with(Path("country.mmdb"), mode=maxminddb.MODE_MEMORY)
        self.assertEqual(self.reader.get.call_count, 3)
        self.reader.close.assert_not_called()

    def test_replacement_closes_old_reader_and_changes_country(self) -> None:
        self.assertEqual(location.resolve_market(request()), CANADA)
        replacement = Mock(spec=maxminddb.Reader)
        replacement.get.return_value = {"country": {"iso_code": "US"}}
        self.mocks["open"].return_value = replacement
        self.mocks["stat"].return_value = database_stat(inode=2)
        self.assertEqual(location.resolve_market(request()), USA)
        self.reader.close.assert_called_once()
        self.assertEqual(self.mocks["open"].call_count, 2)
        self.assertEqual(location.resolve_market(request()), USA)
        replacement.close.assert_not_called()

    def test_path_change_refreshes_reader_even_if_metadata_matches(self) -> None:
        self.assertEqual(location.resolve_market(request()), CANADA)
        os.environ["STYL_GEOIP_DATABASE"] = "updated-country.mmdb"
        self.assertEqual(location.resolve_market(request()), CANADA)
        self.reader.close.assert_called_once()
        self.mocks["open"].assert_called_with(Path("updated-country.mmdb"), mode=maxminddb.MODE_MEMORY)

    def test_removed_or_disabled_database_does_not_serve_stale_country(self) -> None:
        for disable in (False, True):
            with self.subTest(disable=disable):
                self.mocks["stat"].side_effect = None
                os.environ["STYL_GEOIP_DATABASE"] = "country.mmdb"
                self.assertEqual(location.resolve_market(request()), CANADA)
                before = self.reader.close.call_count
                if disable:
                    os.environ["STYL_GEOIP_DATABASE"] = ""
                else:
                    self.mocks["stat"].side_effect = FileNotFoundError()
                with self.assertLogs(location.logger, level="WARNING"):
                    self.assertEqual(location.resolve_market(request()), UNKNOWN)
                self.assertEqual(self.reader.close.call_count, before + 1)

    def test_close_is_idempotent_and_allows_reopening(self) -> None:
        self.assertEqual(location.resolve_market(request()), CANADA)
        self.database.close()
        self.database.close()
        self.reader.close.assert_called_once()
        self.assertEqual(location.resolve_market(request()), CANADA)
        self.assertEqual(self.mocks["open"].call_count, 2)

    def test_replacement_waits_for_inflight_lookup(self) -> None:
        entered, release, second_started = Event(), Event(), Event()

        def read(_address: str) -> dict:
            entered.set()
            if not release.wait(5):
                raise AssertionError("Lookup was not released")
            return {"country": {"iso_code": "CA"}}

        def second_lookup() -> location.MarketContext:
            second_started.set()
            return location.resolve_market(request("1.1.1.1"))

        self.reader.get.side_effect = read
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(location.resolve_market, request())
            try:
                self.assertTrue(entered.wait(5))
                replacement = Mock(spec=maxminddb.Reader)
                replacement.get.return_value = {"country": {"iso_code": "US"}}
                self.mocks["open"].return_value = replacement
                self.mocks["stat"].return_value = database_stat(inode=2)
                second = executor.submit(second_lookup)
                self.assertTrue(second_started.wait(5))
                self.reader.close.assert_not_called()
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5), CANADA)
            self.assertEqual(second.result(timeout=5), USA)
        self.reader.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
