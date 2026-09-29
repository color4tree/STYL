from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app import analytics, analytics_reports, location, main


NOW = datetime(2026, 9, 28, 19, 37, 42, 123456, timezone.utc)


class AnalyticsTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="analytics-fixture-", dir=Path(__file__).parent)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.database = self.root / "analytics.sqlite3"
        self.inquiries = self.root / "inquiries"
        self.inquiries.mkdir()
        self.products = [{
            "id": 1, "slug": "safe-rack", "name": "Safe rack", "category": "Racks",
            "prices": {"CAD": 10.25, "USD": 8.50}, "publicationStatus": "published",
            "provenance": {"notes": "PRIVATE_CATALOG_MARKER"},
        }, {
            "id": 2, "slug": "private-draft", "name": "PRIVATE_DRAFT_MARKER", "category": "Racks",
            "prices": {"CAD": 5, "USD": 4}, "publicationStatus": "draft",
        }, {
            "id": 3, "slug": "canada-only", "name": "Canada only", "category": "Racks",
            "prices": {"CAD": 6, "USD": None}, "publicationStatus": "published",
        }]
        self.products_path = self.root / "products.json"
        self.accessories_path = self.root / "accessories.json"
        self.products_path.write_text(json.dumps(self.products))
        self.accessories_path.write_text("[]")
        for replacement in (
            patch.dict(os.environ, {
                "STYL_ANALYTICS_DB": str(self.database.resolve()), "STYL_ANALYTICS_ENABLED": "true",
                "STYL_ANALYTICS_ENVIRONMENT": "test", "STYL_ANALYTICS_TIMEZONE": "America/Los_Angeles",
                "STYL_ANALYTICS_CAMPAIGN_ALLOWLIST": "launch",
                "STYL_ANALYTICS_EMAIL_ENABLED": "false", "STYL_ANALYTICS_RECIPIENTS": "",
            }),
            patch.multiple(main, DATA_PATH=self.products_path, ACCESSORIES_PATH=self.accessories_path, INQUIRIES_PATH=self.inquiries, ADMIN_TOKEN="analytics-unit-token"),
            patch.object(location, "resolve_market", return_value={"countryCode": "US", "currency": "USD", "locationStatus": "located"}),
            patch.object(main, "send_inquiry_email", return_value="unconfigured"),
            patch.object(analytics, "utcnow", return_value=NOW),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        with analytics.rate_lock:
            analytics.rate_windows.clear()
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        self.headers = {"Origin": main.ALLOWED_ORIGINS[0], "User-Agent": "Mozilla/5.0 (Windows NT 10.0) Chrome/140.0"}
        self.admin = {"Authorization": "Bearer analytics-unit-token"}

    def event(self, name="page_view", properties=None, **extra) -> dict:
        return {"name": name, "path": "/", "properties": properties or {}, **extra}

    def post(self, events=None, context=None, headers=None):
        payload = {"events": events if events is not None else [self.event()]}
        if context is not None:
            payload["context"] = context
        return self.client.post("/api/analytics/events", headers=headers or self.headers, json=payload)

    def report(self, day="2026-09-28") -> dict:
        response = self.client.get(f"/api/admin/analytics/report?start={day}&end={day}", headers=self.admin)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def dump(self) -> str:
        with analytics.get_store().connection() as connection:
            return "\n".join(connection.iterdump())

    def test_an007_config_is_exact_anonymous_contract_without_opening_store(self) -> None:
        response = self.client.get("/api/analytics/config")
        self.assertEqual(response.json(), {
            "enabled": True, "mode": "aggregate-only", "environment": "test",
            "timezone": "America/Los_Angeles", "heartbeatSeconds": 15, "idleSeconds": 60,
            "maxEvents": 20, "maxBatchBytes": 16384, "allowedCampaigns": ["launch"],
        })
        self.assertIn("no-store", response.headers["cache-control"])
        self.assertNotIn("set-cookie", response.headers)
        self.assertFalse(self.database.exists())

    def test_an007_identified_session_creation_is_explicitly_retired(self) -> None:
        for payload in ({}, {"consent": True, "visitorId": "OLD_PRIVATE_ID"}):
            response = self.client.post("/api/analytics/session", headers=self.headers, json=payload)
            self.assertEqual(response.status_code, 410)
            self.assertNotIn("OLD_PRIVATE_ID", response.text)
        self.assertFalse(self.database.exists())

    def test_an009_legacy_ids_tokens_timestamps_and_raw_context_are_rejected(self) -> None:
        base = {"events": [self.event()]}
        payloads = [{**base, key: "PRIVATE_VALUE"} for key in ("visitorId", "sessionToken", "sessionId", "consent", "timestamp", "ip", "url")]
        payloads += [{"events": [{**self.event(), key: "PRIVATE_VALUE"}]} for key in ("id", "pageViewId", "occurredAt", "timestamp", "url", "visitorId")]
        payloads += [{**base, "context": {key: "PRIVATE_VALUE"}} for key in ("referrerHost", "country", "currency", "browser", "ip", "url", "token")]
        for payload in payloads:
            response = self.client.post("/api/analytics/events", headers=self.headers, json=payload)
            self.assertEqual(response.status_code, 422, payload)
            self.assertNotIn("PRIVATE_VALUE", response.text)
        self.assertEqual(self.report()["summary"]["pageViews"], 0)
        self.assertNotIn("PRIVATE_VALUE", self.dump())

    def test_an008_origins_signals_bots_and_admin_credentials_are_excluded(self) -> None:
        for headers in (
            {"Origin": "https://unapproved.example"}, {},
            {**self.headers, "DNT": "1"}, {**self.headers, "Sec-GPC": "1"},
            {**self.headers, "X-STYL-Analytics-Exclude": "1"},
            {**self.headers, "User-Agent": "SearchBot"},
            {**self.headers, **self.admin},
        ):
            response = self.client.post("/api/analytics/events", headers=headers, json={"events": [self.event()]})
            self.assertEqual(response.status_code, 403)
        for signal in ({"Sec-GPC": "1"}, self.admin, {"DNT": "1"}):
            self.assertFalse(self.client.get("/api/analytics/config", headers=signal).json()["enabled"])
        with patch.dict(os.environ, {"STYL_ANALYTICS_ENABLED": "false"}):
            self.assertFalse(self.client.get("/api/analytics/config").json()["enabled"])
            self.assertEqual(self.post().status_code, 403)
        report = self.report()
        self.assertEqual(report["coverage"]["excluded"], 5)
        self.assertEqual(report["coverage"]["rejected"], 2)
        self.assertEqual(report["summary"]["pageViews"], 0)

    def test_an009_invalid_event_rolls_back_whole_batch_before_aggregation(self) -> None:
        for event in (
            self.event(path="/admin"), self.event(path="/?email=PRIVATE_QUERY"),
            self.event(properties={"email": "PRIVATE_FORM"}), self.event(name="inquiry_received"),
            self.event("navigation_click", {"toPath": "/products/safe-rack"}),
            self.event("cart_add", {"itemType": "product", "itemId": True}),
            self.event("cart_add", {"itemType": "product", "itemId": 1.0}),
            self.event("cart_add", {"itemType": "product", "itemId": 0}),
            self.event("cart_add", {"itemType": "product", "itemId": 1, "quantity": 11}),
            self.event("web_vital", {"metric": "CLS"}),
            self.event("engagement", {"activeMs": 15001}),
            self.event("engagement", {"activeMs": 15000.0}),
            self.event("engagement", {"activeMs": -1}),
            self.event("engagement", {"activeMs": 1000, "intervalStart": "PRIVATE_TIME"}),
        ):
            response = self.post([self.event(), event])
            self.assertEqual(response.status_code, 422, event)
            self.assertNotIn("PRIVATE_", response.text)
        report = self.report()
        self.assertEqual(report["summary"]["pageViews"], 0)
        self.assertIsNone(report["coverage"]["trackingSince"])

    def test_an009_finite_strict_measurements_and_malformed_json(self) -> None:
        for value in (float("nan"), float("inf"), -1, True, "5", 3_600_001):
            payload = {"events": [self.event("web_vital", {"metric": "LCP", "value": value})]}
            response = self.client.post("/api/analytics/events", headers=self.headers, content=json.dumps(payload))
            self.assertEqual(response.status_code, 422)
        for data in (b"\xff", b"{", b"null", b"[]", b'{"events": []}',
                     b'{"events":[{"name":"PRIVATE","name":"page_view","path":"/"}]}'):
            self.assertEqual(self.client.post("/api/analytics/events", headers=self.headers, content=data).status_code, 422)
        self.assertEqual(self.report()["webVitals"], [])

    def test_an009_batch_count_and_byte_boundaries(self) -> None:
        self.assertEqual(self.post([self.event() for _ in range(20)]).json(), {"accepted": 20})
        self.assertEqual(self.post([self.event() for _ in range(21)]).status_code, 422)
        raw = json.dumps({"events": [self.event()]}).encode()
        padded = raw + b" " * (analytics.MAX_BATCH_BYTES - len(raw))
        self.assertEqual(self.client.post("/api/analytics/events", headers=self.headers, content=padded).status_code, 200)
        self.assertEqual(self.client.post("/api/analytics/events", headers=self.headers, content=padded + b" ").status_code, 413)
        self.assertEqual(self.report()["summary"]["pageViews"], 21)

    def test_an009_sqlite_failure_rolls_back_all_batch_counts_and_tracking_start(self) -> None:
        with analytics.get_store().connection() as connection:
            connection.execute("""CREATE TRIGGER fixture_write_failure
                BEFORE INSERT ON analytics_aggregate_counts WHEN NEW.dimension='action'
                BEGIN SELECT RAISE(ABORT,'PRIVATE_SQL_FAILURE'); END""")
        response = self.post([self.event(), self.event("cart_clear")])
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("PRIVATE_SQL_FAILURE", response.text)
        with analytics.get_store().connection() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM analytics_aggregate_counts").fetchone()[0], 0)
            self.assertIsNone(connection.execute("SELECT value FROM analytics_meta WHERE key='aggregate_tracking_since'").fetchone())

    def test_an001_occurrences_are_not_deduplicated_or_unique_people(self) -> None:
        events = [self.event(), self.event("item_impression", {"itemType": "product", "itemId": 1})]
        for _ in range(2):
            response = self.post(events)
            self.assertEqual(response.json(), {"accepted": 2})
            self.assertIn("no-store", response.headers["cache-control"])
        report = self.report()
        self.assertEqual(report["summary"]["pageViews"], 2)
        self.assertEqual(report["items"][0]["impressions"], 2)
        self.assertEqual(report["actions"], [{"name": "item_impression", "count": 2}])
        self.assertEqual(report["coverage"]["mode"], "aggregate-only")

    def test_an007_sqlite_contains_only_independent_coarse_aggregate_rows(self) -> None:
        self.post([self.event(), self.event("engagement", {"activeMs": 12000}), self.event("cart_add", {"itemType": "product", "itemId": 1})],
                  {"source": "google", "medium": "cpc", "campaign": "launch", "viewport": "phone"},
                  {**self.headers, "X-Forwarded-For": "24.48.0.1", "X-Request-ID": "PRIVATE_REQUEST_ID"})
        with analytics.get_store().connection() as connection:
            self.assertEqual(analytics._tables(connection), {"analytics_meta", "analytics_aggregate_counts", "analytics_aggregate_items"})
            rows = connection.execute("SELECT * FROM analytics_aggregate_counts").fetchall()
            self.assertEqual({row["hour"] for row in rows}, {analytics.stamp(analytics.hour_start(NOW))})
            self.assertEqual({row["label"] for row in rows if row["dimension"] == "country"}, {"US"})
            self.assertEqual({row["label"] for row in rows if row["dimension"] == "device"}, {"phone"})
            self.assertEqual({row["label"] for row in rows if row["dimension"] == "source"}, {"google / cpc"})
        dump = self.dump()
        for forbidden in ("PRIVATE_", "24.48.0.1", "Chrome/140", "Windows NT", "received_at", "occurred_at", "token", "visitor", "session", "page_id", "event_id", "priceCents", "provenance", analytics.stamp(NOW)):
            self.assertNotIn(forbidden, dump)
        self.assertEqual(self.report()["coverage"]["lastEventAt"], analytics.stamp(analytics.hour_start(NOW)))

    def test_an005_country_enrichment_ignores_forged_headers_and_filters_private_items(self) -> None:
        self.assertEqual(self.post(headers={**self.headers, "CF-IPCountry": "CA", "X-Forwarded-For": "24.48.0.1"}).status_code, 200)
        for item_id in (2, 3, 999):
            self.assertEqual(self.post([self.event(), self.event("item_impression", {"itemType": "product", "itemId": item_id})]).status_code, 422)
        self.assertEqual(self.report()["countries"], [{"label": "US", "pageViews": 1}])
        self.assertNotIn("PRIVATE_", self.dump())
        with patch.object(location, "resolve_market", return_value={"countryCode": None, "currency": "CAD"}):
            self.assertEqual(self.post().status_code, 200)
        self.assertIn({"label": "Unknown", "pageViews": 1}, self.report()["countries"])

    def test_an005_item_currency_counts_are_separate_and_server_prices_are_integer_cents(self) -> None:
        item = {"itemType": "product", "itemId": 1}
        self.post([self.event("cart_add", item)])
        self.assertEqual(main.analytics_catalog({"currency": "USD"})[0]["priceCents"], 850)
        with patch.object(location, "resolve_market", return_value={"countryCode": "CA", "currency": "CAD"}):
            self.post([self.event("cart_add", item)])
        rows = self.report()["items"]
        self.assertEqual({row["currency"] for row in rows}, {"CAD", "USD"})
        self.assertEqual([row["cartAdds"] for row in rows], [1, 1])
        for price in (True, "8.50", -1, 1.001, float("inf"), 2**53):
            self.products[0]["prices"]["USD"] = price
            self.products_path.write_text(json.dumps(self.products))
            self.assertEqual(self.post([self.event("cart_add", item)]).status_code, 422, price)
        with patch.object(location, "resolve_market", return_value={"countryCode": "US", "currency": "EUR"}):
            self.assertEqual(self.post().status_code, 422)

    def test_an008_context_allowlists_reject_urls_referrer_domains_and_unapproved_campaigns(self) -> None:
        for context in (
            {"source": "customer.example.com"}, {"source": "https://google.com?q=PRIVATE"},
            {"medium": "unapproved"}, {"campaign": "unapproved"}, {"campaign": ""},
            {"viewport": "watch"}, {"source": None}, {"referrerHost": "google.com"},
        ):
            self.assertEqual(self.post(context=context).status_code, 422)
        self.assertEqual(self.post(context={"source": "google", "medium": "cpc", "campaign": "launch"}).status_code, 200)
        result = self.report()
        self.assertEqual(result["sources"], [{"label": "google / cpc", "pageViews": 1}])
        self.assertEqual(result["campaigns"], [{"label": "launch", "pageViews": 1}])

    def test_an004_active_time_sums_estimates_without_union_or_timestamps(self) -> None:
        self.post([self.event("engagement", {"activeMs": 10000}), self.event("engagement", {"activeMs": 10000})])
        result = self.report()
        self.assertEqual(result["summary"]["activeSeconds"], 20)
        self.assertEqual(result["pages"], [{"path": "/", "pageViews": 0, "activeSeconds": 20}])
        self.assertEqual(result["hourly"], [{"hour": 12, "pageViews": 0, "activeSeconds": 20}])
        self.assertIn("summed estimates", " ".join(result["coverage"]["warnings"]))
        self.assertIn("Web Locks", " ".join(result["coverage"]["warnings"]))

    def test_an004_midnight_engagement_is_assigned_to_received_hour(self) -> None:
        boundary = datetime(2026, 9, 28, 7, tzinfo=timezone.utc)
        with patch.object(analytics, "utcnow", return_value=boundary + timedelta(seconds=5)):
            self.post([self.event("engagement", {"activeMs": 10000})])
            self.assertEqual(self.report("2026-09-27")["summary"]["activeSeconds"], 0)
            self.assertEqual(self.report()["summary"]["activeSeconds"], 10)

    def test_an010_dst_day_windows_and_repeated_hour_are_correct(self) -> None:
        zone = ZoneInfo("America/Los_Angeles")
        for day, hours in (("2026-03-08", 23), ("2026-11-01", 25)):
            first, last = analytics.day_window(day, day, zone)
            self.assertEqual((last - first).total_seconds(), hours * 3600)
        for hour in (8, 9):
            with patch.object(analytics, "utcnow", return_value=datetime(2026, 11, 1, hour, 30, tzinfo=timezone.utc)):
                self.post()
        with patch.object(analytics, "utcnow", return_value=datetime(2026, 11, 2, 12, tzinfo=timezone.utc)):
            result = self.report("2026-11-01")
        self.assertEqual(result["summary"]["pageViews"], 2)
        self.assertEqual(result["hourly"], [{"hour": 1, "pageViews": 2, "activeSeconds": 0}])
        with self.assertRaisesRegex(ValueError, "whole-hour"):
            analytics.day_window("2026-09-28", "2026-09-28", ZoneInfo("Asia/Kathmandu"))

    def test_an010_current_hour_included_and_explicit_cutoff_excludes_incomplete_hour(self) -> None:
        with patch.object(analytics, "utcnow", return_value=analytics.hour_start(NOW) - timedelta(seconds=1)):
            self.post()
        with patch.object(analytics, "utcnow", return_value=analytics.hour_start(NOW)):
            self.post()
            self.assertEqual(self.report()["summary"]["pageViews"], 2)
        self.post()
        cutoff = analytics.get_report("2026-09-28", "2026-09-28", cutoff=NOW)
        self.assertEqual(cutoff["summary"]["pageViews"], 1)
        self.assertEqual(cutoff["cutoffAt"], analytics.stamp(analytics.hour_start(NOW)))
        self.assertIn("incomplete hour is excluded", " ".join(cutoff["coverage"]["warnings"]))
        with self.assertRaises(ValueError):
            analytics.get_report("2026-09-28", "2026-09-28", cutoff=NOW.replace(tzinfo=None))

    def test_an010_page_view_baseline_compares_daily_averages(self) -> None:
        with patch.object(analytics, "utcnow", return_value=NOW - timedelta(days=7)):
            self.post([self.event() for _ in range(14)])
        self.post([self.event() for _ in range(4)])
        self.assertEqual(self.report()["comparison"], {"days": 7, "pageViewsDailyAverage": 2, "pageViewsChangePercent": 100})

    def test_an003_real_report_shape_item_actions_errors_and_vital_averages(self) -> None:
        item = {"itemType": "product", "itemId": 1}
        events = [self.event(name, item) for name in analytics.ITEM_METRICS]
        events += [
            self.event("site_error", {"errorCode": "catalog"}),
            self.event("web_vital", {"metric": "LCP", "value": 100}),
            self.event("web_vital", {"metric": "LCP", "value": 300}),
            self.event("navigation_click", {"action": "menu", "toPath": "/accessories"}),
        ]
        self.assertEqual(self.post(events).status_code, 200)
        result = self.report()
        self.assertEqual(set(result), {"start", "end", "timezone", "generatedAt", "cutoffAt", "environment", "collectionEnabled", "coverage", "summary", "comparison", "countries", "sources", "campaigns", "devices", "browsers", "pages", "items", "actions", "errors", "webVitals", "daily", "hourly", "observations"})
        self.assertEqual(set(result["summary"]), {"pageViews", "activeSeconds", "savedInquiries"})
        self.assertEqual(set(result["coverage"]), {"mode", "trackingSince", "lastEventAt", "warnings", "excluded", "rejected"})
        self.assertEqual(result["webVitals"], [{"metric": "LCP", "count": 2, "average": 200}])
        self.assertEqual(result["errors"], [{"code": "site_error:catalog", "count": 1}])
        self.assertEqual(result["items"], [{"itemType": "product", "itemId": 1, "name": "Safe rack", "category": "Racks", "currency": "USD", **{metric: 1 for metric in analytics.ITEM_METRICS.values()}}])

    def test_an006_legacy_inquiry_input_is_ignored_never_attributed_or_saved(self) -> None:
        for value in ("PRIVATE_TOKEN", {"sessionToken": "PRIVATE_TOKEN", "source": "cart", "items": [{"itemId": 1, "itemType": "product"}]}):
            with patch.object(analytics, "get_store", side_effect=AssertionError("Inquiry must not access analytics")), patch.object(main, "datetime", wraps=datetime) as clock:
                clock.now.return_value = NOW - timedelta(seconds=1)
                response = self.client.post("/api/inquiries", headers=self.headers, json={
                    "name": "PRIVATE_NAME", "email": "private@example.com", "message": "PRIVATE_FORM", "analytics": value,
                })
                self.assertEqual(response.status_code, 200)
        for path in self.inquiries.glob("*.json"):
            saved = json.loads(path.read_text())
            self.assertNotIn("analytics", saved)
            self.assertNotIn("analyticsAttribution", saved)
            self.assertNotIn("PRIVATE_TOKEN", json.dumps(saved))
        for _ in range(2):
            result = self.report()
            self.assertEqual(result["summary"]["savedInquiries"], 2)
            self.assertEqual(result["daily"], [{"date": "2026-09-28", "pageViews": 0, "activeSeconds": 0, "inquiries": 2}])
            self.assertEqual(result["items"], [])
        self.assertNotIn("PRIVATE_", self.dump())
        self.assertNotIn("private@example.com", self.dump())

    def test_an006_inquiries_independent_of_disabled_invalid_collection_and_smtp(self) -> None:
        with patch.dict(os.environ, {"STYL_ANALYTICS_ENABLED": "invalid"}), patch.object(main, "send_inquiry_email", side_effect=OSError("PRIVATE_SMTP")):
            response = self.client.post("/api/inquiries", json={"name": "Customer", "email": "customer@example.com", "message": "Quote"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(next(self.inquiries.glob("*.json")).read_text())["emailStatus"], "failed")
        self.assertFalse(self.database.exists())

    def test_an006_unavailable_saved_inquiries_are_null_and_not_a_normal_zero(self) -> None:
        with patch.object(main, "analytics_inquiry_summaries", side_effect=OSError("PRIVATE_FAILURE")):
            report = self.report()
        self.assertIsNone(report["summary"]["savedInquiries"])
        self.assertIn("unavailable", " ".join(report["coverage"]["warnings"]))
        self.assertNotIn("PRIVATE_FAILURE", json.dumps(report))
        (self.inquiries / "malformed.json").write_text('{"createdAt": "not-a-date"}')
        self.assertIsNone(self.report()["summary"]["savedInquiries"])

    def legacy(self, when=NOW) -> None:
        with analytics.get_store().connection() as connection:
            connection.executescript("""
                CREATE TABLE analytics_sessions(id TEXT PRIMARY KEY,token_hash TEXT,visitor_hash TEXT,last_at TEXT);
                CREATE TABLE analytics_events(id TEXT,session_id TEXT,occurred_at TEXT,received_at TEXT);
                CREATE TABLE analytics_visitors(hash TEXT,first_at TEXT,expires_at TEXT);
                CREATE TABLE analytics_receipts(id TEXT,created_at TEXT,session_id TEXT,source TEXT,items TEXT);
                CREATE TABLE analytics_rollups(day TEXT,timezone TEXT,payload TEXT);
            """)
            connection.execute("INSERT INTO analytics_sessions VALUES(?,?,?,?)", ("LEGACY_SESSION", hashlib.sha256(("x" * 43).encode()).hexdigest(), "LEGACY_VISITOR", analytics.stamp(when)))
            connection.execute("INSERT INTO analytics_events VALUES(?,?,?,?)", ("LEGACY_EVENT", "LEGACY_SESSION", analytics.stamp(when), analytics.stamp(when)))
            connection.execute("INSERT INTO analytics_visitors VALUES(?,?,?)", ("LEGACY_VISITOR", analytics.stamp(when), analytics.stamp(when + timedelta(days=30))))
            connection.execute("INSERT INTO analytics_receipts VALUES(?,?,?,?,?)", ("LEGACY_INQUIRY", analytics.stamp(when), "LEGACY_SESSION", "cart", "[]"))
            connection.execute("INSERT INTO analytics_rollups VALUES(?,?,?)", (when.date().isoformat(), "America/Los_Angeles", '{"summary":{"sessions":999,"pageViews":999}}'))
            connection.execute("INSERT INTO analytics_meta VALUES('tracking_since',?)", (analytics.stamp(when - timedelta(days=365)),))

    def test_an014_legacy_data_preserved_warned_never_reconstructed_or_counted(self) -> None:
        self.legacy()
        before = self.dump()
        self.post()
        report = self.report()
        self.assertEqual(report["summary"], {"pageViews": 1, "activeSeconds": 0, "savedInquiries": 0})
        self.assertIn("Legacy identified analytics data exists", " ".join(report["coverage"]["warnings"]))
        self.assertEqual(report["coverage"]["trackingSince"], analytics.stamp(analytics.hour_start(NOW)))
        after = self.dump()
        for line in before.splitlines():
            if "INSERT INTO \"analytics_aggregate" not in line:
                self.assertIn(line, after)

    def test_an007_legacy_withdrawal_only_deletes_legacy_identified_activity(self) -> None:
        self.legacy()
        self.post()
        with patch.dict(os.environ, {"STYL_ANALYTICS_ENABLED": "false"}):
            response = self.client.request("DELETE", "/api/analytics/session", headers={**self.headers, "DNT": "1"}, json={"sessionToken": "x" * 43})
        self.assertEqual(response.status_code, 200)
        with analytics.get_store().connection() as connection:
            for table in ("analytics_events", "analytics_sessions", "analytics_visitors"):
                self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
            self.assertIsNone(connection.execute("SELECT session_id FROM analytics_receipts").fetchone()[0])
        self.assertEqual(self.report()["summary"]["pageViews"], 1)

    def test_an014_thirteen_calendar_month_retention_and_bounded_legacy_raw_retention(self) -> None:
        self.legacy(NOW - timedelta(days=31))
        old = datetime(2025, 8, 27, 23, tzinfo=timezone.utc)
        retained = datetime(2025, 8, 28, 7, tzinfo=timezone.utc)
        for when in (old, retained):
            with patch.object(analytics, "utcnow", return_value=when):
                self.post()
        analytics.get_store().prune(NOW)
        with analytics.get_store().connection() as connection:
            self.assertEqual(connection.execute("SELECT min(hour) FROM analytics_aggregate_counts").fetchone()[0], analytics.stamp(retained))
            for table in ("analytics_events", "analytics_sessions", "analytics_visitors", "analytics_receipts"):
                self.assertEqual(connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM analytics_rollups").fetchone()[0], 1)
        self.assertEqual(self.report("2025-08-28")["summary"]["pageViews"], 1)
        analytics.get_store().prune(datetime(2028, 1, 1, tzinfo=timezone.utc))
        with analytics.get_store().connection() as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM analytics_aggregate_counts").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT count(*) FROM analytics_rollups").fetchone()[0], 0)

    def test_an013_admin_reports_require_auth_and_csv_is_safe(self) -> None:
        for endpoint in ("report?start=2026-09-28&end=2026-09-28", "export?start=2026-09-28&end=2026-09-28", "email-preview?date=2026-09-28", "deliveries", "email-settings"):
            self.assertEqual(self.client.get("/api/admin/analytics/" + endpoint).status_code, 401)
        self.products[0]["name"] = "=PRIVATE_FORMULA"
        self.products_path.write_text(json.dumps(self.products))
        self.post([self.event("item_impression", {"itemType": "product", "itemId": 1})])
        result = self.client.get("/api/admin/analytics/export?start=2026-09-28&end=2026-09-28", headers=self.admin)
        self.assertEqual(result.status_code, 200)
        self.assertIn("USD", result.text)
        self.assertNotIn("summary,,sessions", result.text)
        report = self.report()
        report["countries"] = [{"label": "=FORMULA", "pageViews": 1}]
        self.assertIn("'=FORMULA", analytics.export_csv(report))
        self.assertIn("no-store", result.headers["cache-control"])

    def test_an017_settings_api_is_private_persistent_and_never_sends_on_save(self) -> None:
        url = "/api/admin/analytics/email-settings"
        body = {"enabled": True, "recipients": ["owner@example.com", "Owner@EXAMPLE.COM"], "expectedRevision": 0}
        self.assertEqual(self.client.put(url, json=body).status_code, 401)
        before_products = self.products_path.read_bytes()
        before_accessories = self.accessories_path.read_bytes()
        initial = self.client.get(url, headers=self.admin)
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.json()["source"], "environment")
        with patch.object(analytics_reports, "_send") as send:
            response = self.client.put(url, json=body, headers=self.admin)
            send.assert_not_called()
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value["recipients"], ["owner@example.com"])
        self.assertEqual(value["revision"], 1)
        self.assertTrue(value["enabled"])
        self.assertFalse(value["effectiveEnabled"])
        self.assertIn("no-store", response.headers["cache-control"])
        self.assertEqual(self.client.get(url, headers=self.admin).json()["revision"], 1)
        stale = self.client.put(url, json={**body, "recipients": ["different@example.com"]}, headers=self.admin)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.client.get(url, headers=self.admin).json()["recipients"], ["owner@example.com"])
        public = self.client.get("/api/analytics/config")
        self.assertNotIn("owner@example.com", public.text)
        self.assertEqual(self.products_path.read_bytes(), before_products)
        self.assertEqual(self.accessories_path.read_bytes(), before_accessories)

    def test_an017_invalid_settings_are_explicit_and_do_not_overwrite_saved_values(self) -> None:
        url = "/api/admin/analytics/email-settings"
        valid = {"enabled": False, "recipients": ["owner@example.com"], "expectedRevision": 0}
        self.assertEqual(self.client.put(url, json=valid, headers=self.admin).status_code, 200)
        for body in (
            {**valid, "expectedRevision": 1, "enabled": "yes"},
            {**valid, "expectedRevision": 1, "recipients": ["not-an-address"]},
            {**valid, "expectedRevision": 1, "enabled": True, "recipients": []},
            {**valid, "expectedRevision": 1, "recipients": ["owner@example.com\r\nBcc: PRIVATE_VALUE"]},
            {**valid, "expectedRevision": 1, "smtpPassword": "PRIVATE_VALUE"},
            {**valid, "expectedRevision": 1, "recipients": [f"user{i}@example.com" for i in range(21)]},
        ):
            response = self.client.put(url, json=body, headers=self.admin)
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("PRIVATE_VALUE", response.text)
        self.assertEqual(self.client.get(url, headers=self.admin).json()["revision"], 1)
        self.assertEqual(self.client.get(url, headers=self.admin).json()["recipients"], ["owner@example.com"])
        allowed = {**valid, "expectedRevision": 1, "recipients": [f"user{i}@example.com" for i in range(20)]}
        self.assertEqual(self.client.put(url, json=allowed, headers=self.admin).status_code, 200)

    def test_an017_settings_storage_outage_has_no_success_shaped_defaults(self) -> None:
        url = "/api/admin/analytics/email-settings"
        with patch.object(analytics.AnalyticsStore, "connection", side_effect=sqlite3.OperationalError("PRIVATE_DATABASE_DETAIL")):
            for response in (
                self.client.get(url, headers=self.admin),
                self.client.put(url, json={"enabled": False, "recipients": [], "expectedRevision": 0}, headers=self.admin),
            ):
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("PRIVATE_DATABASE_DETAIL", response.text)

    def test_an017_malformed_or_duplicate_json_is_input_error_and_corrupt_saved_state_is_unavailable(self) -> None:
        url = "/api/admin/analytics/email-settings"
        for text in ('{"enabled":', '{"enabled":false,"enabled":true,"recipients":[],"expectedRevision":0}'):
            response = self.client.put(url, content=text, headers={**self.admin, "Content-Type": "application/json"})
            self.assertEqual(response.status_code, 422)
        value = {"enabled": False, "recipients": [], "expectedRevision": 0}
        self.assertEqual(self.client.put(url, json=value, headers=self.admin).status_code, 200)
        with analytics.get_store().connection() as connection:
            connection.execute("UPDATE analytics_email_settings SET recipients='PRIVATE_INVALID_JSON'")
        for response in (
            self.client.get(url, headers=self.admin),
            self.client.put(url, json={**value, "expectedRevision": 1}, headers=self.admin),
        ):
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("PRIVATE_INVALID_JSON", response.text)

    def test_an009_dates_configuration_environment_and_sql_fail_explicitly(self) -> None:
        for first, last in (("20260928", "2026-09-28"), ("2026-02-30", "2026-09-28"), ("2026-09-29", "2026-09-28"), ("2024-01-01", "2026-09-28"), ("9999-12-31", "9999-12-31")):
            response = self.client.get(f"/api/admin/analytics/report?start={first}&end={last}", headers=self.admin)
            self.assertEqual(response.status_code, 422)
        with patch.object(analytics.AnalyticsStore, "connection", side_effect=sqlite3.OperationalError("PRIVATE_SQL")):
            response = self.client.get("/api/admin/analytics/report?start=2026-09-28&end=2026-09-28", headers=self.admin)
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("PRIVATE_SQL", response.text)
            self.assertEqual(self.post().status_code, 503)
        with patch.dict(os.environ, {"STYL_ANALYTICS_TIMEZONE": "not-a-zone"}):
            self.assertEqual(self.client.get("/api/analytics/config").status_code, 503)
        self.post()
        with patch.dict(os.environ, {"STYL_ANALYTICS_ENVIRONMENT": "staging"}):
            self.assertEqual(self.post().status_code, 422)
        with patch.dict(os.environ, {"STYL_ANALYTICS_DB": "relative.sqlite3"}):
            with self.assertRaises(ValueError):
                analytics.configured_path()

    def test_an009_rate_limits_are_bounded_in_memory_and_not_header_identity(self) -> None:
        for _ in range(30):
            self.assertEqual(self.post([self.event() for _ in range(20)]).status_code, 200)
        response = self.post(headers={**self.headers, "X-Forwarded-For": "8.8.8.8"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["retry-after"], "60")
        self.assertNotIn("8.8.8.8", self.dump())
        with patch.object(analytics, "utcnow", return_value=NOW + timedelta(seconds=61)):
            self.assertEqual(self.post().status_code, 200)
        with analytics.rate_lock:
            analytics.rate_windows.clear()
        for index in range(4096):
            analytics.limit_rate(f"synthetic:{index}", 1)
        with self.assertRaises(Exception) as error:
            analytics.limit_rate("beyond-cap", 1)
        self.assertEqual(error.exception.status_code, 429)

    def test_an014_real_store_disabled_job_and_consistent_backup(self) -> None:
        self.post()
        with patch.object(analytics_reports, "_send") as send:
            self.assertEqual(analytics_reports.run_due(NOW)["status"], "disabled")
            preview = analytics_reports.preview_report("2026-09-28", NOW)
            self.assertIn("Page views: 0", preview["text"])
            send.assert_not_called()
        target = self.root / "backup.sqlite3"
        analytics_reports.backup_store(target)
        connection = sqlite3.connect(target)
        try:
            self.assertEqual(connection.execute("SELECT sum(count) FROM analytics_aggregate_counts WHERE dimension='total' AND metric='pageViews'").fetchone()[0], 1)
            self.assertNotIn("analytics_sessions", analytics._tables(connection))
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
