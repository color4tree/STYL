from concurrent.futures import ThreadPoolExecutor
from collections.abc import Generator
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import json
import smtplib
import sqlite3
import sys
import tempfile
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from app import analytics_reports as reports


NOW = datetime(2026, 9, 28, 15, tzinfo=timezone.utc)


def fixture_report() -> dict[str, object]:
    return {
        "timezone": "America/Los_Angeles", "environment": "test",
        "collectionEnabled": True,
        "generatedAt": NOW.isoformat(), "cutoffAt": NOW.isoformat(),
        "coverage": {"mode": "aggregate-only", "rejected": 0, "warnings": ["Anonymous occurrence counts only."]},
        "summary": {
            "pageViews": 350, "activeSeconds": 2100, "savedInquiries": 10,
        },
        "comparison": {"days": 7, "pageViewsDailyAverage": 100, "pageViewsChangePercent": 250.0},
        "countries": [{"label": "US", "pageViews": 350}],
        "sources": [{"label": "direct", "pageViews": 350}],
        "campaigns": [], "devices": [{"label": "phone", "pageViews": 350}], "browsers": [],
        "items": [{
            "name": "<script>alert('test')</script>", "currency": "USD",
            "impressions": 10, "detailViews": 12, "expansions": 1, "mediaOpens": 2, "cartAdds": 3, "quoteOpens": 1,
        }],
        "actions": [{"name": "cart_add", "count": 3}],
        "errors": [{"code": "catalog", "count": 1}],
        "observations": ["One observed gap; not a causal claim."],
    }


class ReportStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.prunes = 0

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def prune(self) -> None:
        self.prunes += 1


class AnalyticsReportTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="analytics-report-fixture-", dir=Path(__file__).parent)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = ReportStore(self.root / "analytics.sqlite3")
        store_patch = patch.object(reports, "_store", return_value=self.store)
        store_patch.start()
        self.addCleanup(store_patch.stop)
        environment = patch.dict(os.environ, {
            "STYL_ANALYTICS_TIMEZONE": "America/Los_Angeles",
            "STYL_ANALYTICS_ENVIRONMENT": "production",
            "STYL_ANALYTICS_EMAIL_ENABLED": "true",
            "STYL_ANALYTICS_RECIPIENTS": "owner@example.com",
            "STYL_ANALYTICS_DASHBOARD_URL": "https://example.com/admin",
        })
        environment.start()
        self.addCleanup(environment.stop)

    def preview(self, day: str, now: datetime | None = None) -> dict[str, object]:
        return {
            "reportDate": day, "timezone": "America/Los_Angeles",
            **reports.render_report(fixture_report(), day),
            "emailEnabled": True, "recipientsConfigured": True,
            "nextRunAt": reports.next_run_at(now or NOW).isoformat(),
        }

    def test_an010_schedule_boundary_and_utc_date_offset(self) -> None:
        zone = ZoneInfo("America/Los_Angeles")
        for instant, expected_day, next_instant in (
            ("2026-09-28T07:14:59+00:00", "2026-09-26", "2026-09-28T07:15:00+00:00"),
            ("2026-09-28T07:15:00+00:00", "2026-09-27", "2026-09-29T07:15:00+00:00"),
            ("2026-09-28T00:05:00+00:00", "2026-09-26", "2026-09-28T07:15:00+00:00"),
            ("2027-01-01T08:14:59+00:00", "2026-12-30", "2027-01-01T08:15:00+00:00"),
            ("2027-01-01T08:15:00+00:00", "2026-12-31", "2027-01-02T08:15:00+00:00"),
        ):
            with self.subTest(instant=instant):
                now = datetime.fromisoformat(instant)
                self.assertEqual(reports.due_date(now, zone).isoformat(), expected_day)
                self.assertEqual(reports.next_run_at(now, zone).isoformat(), next_instant)
                settings = reports.get_email_settings(now)
                self.assertEqual(settings["timezone"], zone.key)
                self.assertEqual(settings["nextRunAt"], next_instant)
        for function in (reports.next_run_at, reports.due_date):
            with self.assertRaises(reports.ReportError):
                function(datetime(2026, 9, 28))

    def test_an010_schedule_tracks_midnight_offset_across_spring_and_fall_dst(self) -> None:
        for instant, expected_day, next_instant in (
            ("2026-03-08T08:14:59+00:00", "2026-03-06", "2026-03-08T08:15:00+00:00"),
            ("2026-03-08T08:15:00+00:00", "2026-03-07", "2026-03-09T07:15:00+00:00"),
            ("2026-03-09T07:15:00+00:00", "2026-03-08", "2026-03-10T07:15:00+00:00"),
            ("2026-11-01T07:14:59+00:00", "2026-10-30", "2026-11-01T07:15:00+00:00"),
            ("2026-11-01T07:15:00+00:00", "2026-10-31", "2026-11-02T08:15:00+00:00"),
            ("2026-11-01T08:15:00+00:00", "2026-10-31", "2026-11-02T08:15:00+00:00"),
            ("2026-11-01T09:15:00+00:00", "2026-10-31", "2026-11-02T08:15:00+00:00"),
            ("2026-11-02T08:15:00+00:00", "2026-11-01", "2026-11-03T08:15:00+00:00"),
        ):
            with self.subTest(instant=instant):
                now = datetime.fromisoformat(instant)
                self.assertEqual(reports.due_date(now).isoformat(), expected_day)
                self.assertEqual(reports.next_run_at(now).isoformat(), next_instant)

    def test_an010_concise_business_summary_omits_technical_block_and_escapes_html(self) -> None:
        rendered = reports.render_report(fixture_report(), "2026-09-27")
        self.assertIn("Page views: 350 (7-day average: 100/day; +250%)", rendered["text"])
        self.assertIn("Saved inquiries: 10", rendered["text"])
        self.assertIn("Active time (estimated): 35 min", rendered["text"])
        self.assertIn("Cart adds: 3", rendered["text"])
        self.assertIn("Countries: US (350 views)", rendered["text"])
        for obsolete in (
            "Tracked sessions:", "Estimated browser visitors:", "Median active seconds:", "Tracked quote conversion:",
            "\nFunnel\n", "opted-in", "Warning:", "Anonymous occurrence counts only.", "Data cutoff:", "Generated:",
            "No browser identities", "Hourly storage", "cross-tab", "13 calendar months", "Quotes are saved inquiries",
        ):
            self.assertNotIn(obsolete, rendered["text"])
            self.assertNotIn(obsolete, rendered["html"])
        self.assertIn("Attention\n- Catalog errors: 1.", rendered["text"])
        self.assertIn("<script>", rendered["text"])
        self.assertNotIn("<script>", rendered["html"])
        self.assertIn("&lt;script&gt;", rendered["html"])
        self.assertIn("admin sign-in required", rendered["text"])
        self.assertIn("<table", rendered["html"])
        self.assertNotIn("<pre", rendered["html"])
        self.assertLess(len(rendered["text"].splitlines()), 25)

    def test_an010_unavailable_metrics_are_not_normal_zero_results(self) -> None:
        report = fixture_report()
        summary = report["summary"]
        comparison = report["comparison"]
        assert isinstance(summary, dict) and isinstance(comparison, dict)
        summary["savedInquiries"] = None
        comparison["pageViewsChangePercent"] = None
        text = reports.render_report(report, "2026-09-27")["text"]
        self.assertIn("Saved inquiries: N/A", text)
        self.assertIn("Inquiry totals are unavailable", text)
        self.assertIn("no comparable baseline", text)
        report.pop("summary")
        with self.assertRaises(reports.ReportError):
            reports.render_report(report, "2026-09-27")

    def test_an010_partial_day_is_labelled_without_comparing_it_to_a_whole_day(self) -> None:
        report = fixture_report()
        text = reports.render_report(report, "2026-09-28")["text"]
        self.assertIn("Through 08:00", text)
        self.assertIn("7-day average: 100/day", text)
        self.assertNotIn("+250%", text)
        report["cutoffAt"] = "2026-09-27T06:00:00+00:00"
        self.assertIn("Not started", reports.render_report(report, "2026-09-27")["text"])

    def test_an010_top_three_lists_are_ranked_and_other_details_stay_in_dashboard(self) -> None:
        report = fixture_report()
        original = report["items"][0]
        report["items"] = [{**original, "name": f"Equipment {index}", "cartAdds": index} for index in range(5)]
        report["countries"] = [{"label": f"Country {index}", "pageViews": index} for index in range(5)]
        report["sources"] = [{"label": f"Source {index}", "pageViews": index} for index in range(5)]
        text = reports.render_report(report, "2026-09-27")["text"]
        for prefix in ("Equipment", "Country", "Source"):
            for index in (4, 3, 2):
                self.assertIn(f"{prefix} {index}", text)
            self.assertNotIn(f"{prefix} 1", text)
            self.assertLess(text.index(f"{prefix} 4"), text.index(f"{prefix} 3"))
        for section in ("Campaigns", "Devices", "Browsers", "Actions (occurrences)", "Observations"):
            self.assertNotIn(section, text)

    def test_an009_real_collection_and_data_problems_remain_actionable(self) -> None:
        report = fixture_report()
        report["collectionEnabled"] = False
        report["summary"]["savedInquiries"] = None
        report["coverage"]["rejected"] = 4
        text = reports.render_report(report, "2026-09-27")["text"]
        for message in ("Collection is off", "Inquiry totals are unavailable", "4 measurements rejected", "Catalog errors: 1"):
            self.assertIn(message, text)
        self.assertNotIn("Saved inquiries: 0", text)
        self.assertNotIn("Warning:", text)

    def test_an010_empty_data_is_short_without_empty_sections_or_false_error_assurance(self) -> None:
        report = fixture_report()
        report["summary"] = {"pageViews": 0, "activeSeconds": 0, "savedInquiries": 0}
        report["comparison"] = {"days": 7, "pageViewsDailyAverage": 0, "pageViewsChangePercent": None}
        for field in ("countries", "sources", "items", "actions", "errors"):
            report[field] = []
        rendered = reports.render_report(report, "2026-09-27")
        self.assertIn("Page views: 0", rendered["text"])
        self.assertIn("Active time (estimated): 0 min", rendered["text"])
        for section in ("Attention", "Top equipment", "\nTraffic", "No recorded errors", "No tracked data"):
            self.assertNotIn(section, rendered["text"])
        self.assertLessEqual(len(rendered["text"].splitlines()), 10)

    def test_an010_active_time_is_human_readable_and_does_not_claim_per_visitor_time(self) -> None:
        for seconds, expected in ((30, "<1 min"), (60, "1 min"), (3600, "1 hr"), (3720, "1 hr 2 min")):
            report = fixture_report()
            report["summary"]["activeSeconds"] = seconds
            self.assertIn(f"Active time (estimated): {expected}", reports.render_report(report, "2026-09-27")["text"])

    def test_an009_invalid_metrics_and_coverage_cannot_render_as_a_successful_summary(self) -> None:
        for field, invalid in (("pageViews", -1), ("activeSeconds", float("nan")), ("pageViews", True)):
            report = fixture_report()
            report["summary"][field] = invalid
            with self.assertRaises(reports.ReportError):
                reports.render_report(report, "2026-09-27")
        for field, invalid in (("timezone", "Invalid/Zone"), ("cutoffAt", "invalid"), ("cutoffAt", "2026-09-27T12:00:00"), ("collectionEnabled", None)):
            report = fixture_report()
            report[field] = invalid
            with self.assertRaises(reports.ReportError):
                reports.render_report(report, "2026-09-27")

    def test_an010_legacy_report_contract_cannot_render_under_new_privacy_wording(self) -> None:
        report = fixture_report()
        report["summary"]["sessions"] = 10
        with self.assertRaises(reports.ReportError):
            reports.render_report(report, "2026-09-27")
        report = fixture_report()
        report["coverage"]["mode"] = "raw"
        with self.assertRaises(reports.ReportError):
            reports.render_report(report, "2026-09-27")

    def test_an012_preview_never_sends_and_uses_completed_hour_cutoff(self) -> None:
        get_report = Mock(return_value=fixture_report())
        with patch.dict(sys.modules, {"app.analytics": SimpleNamespace(get_report=get_report)}), \
                patch.object(reports, "_send") as send:
            result = reports.preview_report("2026-09-27", NOW + timedelta(minutes=37))
        get_report.assert_called_once_with("2026-09-27", "2026-09-27", cutoff=NOW)
        self.assertIn("subject", result)
        send.assert_not_called()

    def test_an010_late_partial_preview_keeps_date_cutoff_and_next_midnight_metadata(self) -> None:
        now = datetime(2026, 9, 29, 6, 47, 59, tzinfo=timezone.utc)
        cutoff = now.replace(minute=0, second=0, microsecond=0)
        report = {**fixture_report(), "generatedAt": now.isoformat(), "cutoffAt": cutoff.isoformat()}
        get_report = Mock(return_value=report)
        with patch.dict(sys.modules, {"app.analytics": SimpleNamespace(get_report=get_report)}), \
                patch.object(reports, "_send") as send:
            result = reports.preview_report("2026-09-28", now)
        get_report.assert_called_once_with("2026-09-28", "2026-09-28", cutoff=cutoff)
        self.assertEqual(result["reportDate"], "2026-09-28")
        self.assertEqual(result["timezone"], "America/Los_Angeles")
        self.assertEqual(result["nextRunAt"], "2026-09-29T07:15:00+00:00")
        self.assertEqual(result["subject"], "STYL daily usage | 2026-09-28")
        for field in ("text", "html"):
            self.assertIn("Through 23:00", result[field])
            self.assertNotIn("+250%", result[field])
            self.assertIn("USD", result[field])
        send.assert_not_called()

    def test_an011_local_and_disabled_jobs_do_not_send(self) -> None:
        with patch.object(reports, "_send") as send:
            for environment, enabled in (("local", "true"), ("test", "true"), ("staging", "true"), ("production", "false")):
                with self.subTest(environment=environment), patch.dict(os.environ, {
                    "STYL_ANALYTICS_ENVIRONMENT": environment, "STYL_ANALYTICS_EMAIL_ENABLED": enabled,
                }):
                    self.assertEqual(reports.run_due(NOW)["status"], "disabled")
            send.assert_not_called()
        self.assertEqual(self.store.prunes, 4)

    def test_an011_missing_invalid_and_duplicate_recipient_configuration(self) -> None:
        with patch.dict(os.environ, {"STYL_ANALYTICS_RECIPIENTS": ""}), patch.object(reports, "_send") as send:
            with self.assertRaises(reports.ReportError):
                reports.run_due(NOW)
            send.assert_not_called()
        for value in ("invalid", "owner@example.com\r\nBcc: secret@example.com"):
            with patch.dict(os.environ, {"STYL_ANALYTICS_RECIPIENTS": value}):
                with self.assertRaises(reports.ReportError) as error:
                    reports.recipients()
                self.assertNotIn("secret@example.com", str(error.exception))
        with patch.dict(os.environ, {"STYL_ANALYTICS_RECIPIENTS": "owner@example.com, owner@example.com"}):
            self.assertEqual(reports.recipients(), ["owner@example.com"])

    def test_an011_daily_idempotency_snapshot_and_no_recipient_redelivery(self) -> None:
        with patch.object(reports, "preview_report", side_effect=self.preview) as preview, \
                patch.object(reports, "_send", return_value=("accepted", None)) as send:
            first = reports.run_due(NOW)
            second = reports.run_due(NOW + timedelta(minutes=15))
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(second["status"], "accepted")
        self.assertEqual(send.call_count, 1)
        self.assertEqual(preview.call_count, 1)
        history = reports.delivery_history()
        self.assertEqual(history[0]["status"], "accepted")
        self.assertEqual(history[0]["recipient"], "o***@example.com")

    def test_an011_midnight_boundary_reopen_and_quarter_hour_ticks_keep_delivery_claims(self) -> None:
        first_run = datetime(2026, 9, 27, 7, 15, tzinfo=timezone.utc)
        boundary = first_run + timedelta(days=1)
        with patch.object(reports, "preview_report", side_effect=self.preview) as preview, \
                patch.object(reports, "_send", return_value=("accepted", None)) as send:
            self.assertEqual(reports.run_due(first_run)["reportDate"], "2026-09-26")
            with patch.object(reports, "_store", return_value=ReportStore(self.store.path)):
                for now in (boundary - timedelta(minutes=15), boundary - timedelta(seconds=1)):
                    self.assertEqual(reports.run_due(now)["reportDate"], "2026-09-26")
                self.assertEqual(send.call_count, 1)
                for now in (boundary, boundary + timedelta(minutes=15), boundary + timedelta(minutes=30),
                            NOW, boundary + timedelta(hours=23, minutes=45)):
                    self.assertEqual(reports.run_due(now)["reportDate"], "2026-09-27")
        self.assertEqual(send.call_count, 2)
        self.assertEqual(preview.call_count, 2)
        with self.store.connection() as connection:
            rows = connection.execute("SELECT report_date,status,attempts FROM analytics_report_delivery ORDER BY report_date").fetchall()
            snapshots = connection.execute("SELECT report_date FROM analytics_report_snapshot ORDER BY report_date").fetchall()
        self.assertEqual([tuple(row) for row in rows], [("2026-09-26", "accepted", 1), ("2026-09-27", "accepted", 1)])
        self.assertEqual([row[0] for row in snapshots], ["2026-09-26", "2026-09-27"])

    def test_an011_dst_clock_changes_do_not_resend_completed_reports(self) -> None:
        for first_instant, next_instant, report_day in (
            ("2026-03-08T08:15:00+00:00", "2026-03-09T07:15:00+00:00", "2026-03-07"),
            ("2026-11-01T07:15:00+00:00", "2026-11-02T08:15:00+00:00", "2026-10-31"),
        ):
            with self.subTest(first_instant=first_instant):
                first = datetime.fromisoformat(first_instant)
                next_day = datetime.fromisoformat(next_instant)
                store = ReportStore(self.root / f"dst-{report_day}.sqlite3")
                with patch.object(reports, "_store", return_value=store), \
                        patch.object(reports, "preview_report", side_effect=self.preview) as preview, \
                        patch.object(reports, "_send", return_value=("accepted", None)) as send:
                    for instant in (first, first + timedelta(minutes=15), first + timedelta(hours=1),
                                    first + timedelta(hours=2), next_day - timedelta(minutes=15)):
                        self.assertEqual(reports.run_due(instant)["reportDate"], report_day)
                        self.assertEqual(send.call_count, 1)
                    reports.run_due(next_day)
                    reports.run_due(next_day + timedelta(minutes=15))
                    self.assertEqual(send.call_count, 2)
                    self.assertEqual(preview.call_count, 2)
                    self.assertTrue(all(row["attempts"] == 1 for row in reports.delivery_history()))

    def test_an011_delayed_restart_sends_latest_due_day_without_replaying_old_completed_reports(self) -> None:
        first = datetime(2026, 9, 26, 7, 15, tzinfo=timezone.utc)
        delayed = datetime(2026, 9, 28, 16, 45, tzinfo=timezone.utc)
        with patch.object(reports, "preview_report", side_effect=self.preview) as preview, \
                patch.object(reports, "_send", return_value=("accepted", None)) as send:
            self.assertEqual(reports.run_due(first)["reportDate"], "2026-09-25")
            with self.store.connection() as connection:
                original = tuple(connection.execute("SELECT * FROM analytics_report_delivery").fetchone())
                snapshot = tuple(connection.execute("SELECT * FROM analytics_report_snapshot").fetchone())
            with patch.object(reports, "_store", return_value=ReportStore(self.store.path)):
                self.assertEqual(reports.run_due(delayed)["reportDate"], "2026-09-27")
                reports.run_due(delayed + timedelta(minutes=15))
            self.assertEqual(send.call_count, 2)
            self.assertEqual([call.args[0] for call in preview.call_args_list], ["2026-09-25", "2026-09-27"])
        with self.store.connection() as connection:
            self.assertEqual(tuple(connection.execute(
                "SELECT * FROM analytics_report_delivery WHERE report_date='2026-09-25'"
            ).fetchone()), original)
            self.assertEqual(tuple(connection.execute(
                "SELECT * FROM analytics_report_snapshot WHERE report_date='2026-09-25'"
            ).fetchone()), snapshot)

    def test_an011_recipient_case_or_report_version_change_does_not_duplicate_accepted_mail(self) -> None:
        with patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", return_value=("accepted", None)) as send:
            reports.run_due(NOW)
            with patch.dict(os.environ, {"STYL_ANALYTICS_RECIPIENTS": "Owner@example.com"}):
                reports.run_due(NOW + timedelta(minutes=15))
            with patch.object(reports, "REPORT_VERSION", reports.REPORT_VERSION + 1):
                reports.run_due(NOW + timedelta(minutes=30))
        self.assertEqual(send.call_count, 1)

    def test_an011_legacy_snapshots_are_not_resent_and_accepted_delivery_stays_deduplicated(self) -> None:
        with self.store.connection() as connection:
            reports._ensure_tables(connection)
            connection.execute("INSERT INTO analytics_report_snapshot VALUES(?,?,?,?,?,?,?)",
                               ("2026-09-27", "America/Los_Angeles", 1, "old", "opted-in tracked sessions", "<p>old</p>", NOW.isoformat()))
            for address, status in (("owner@example.com", "accepted"), ("sales@example.com", "failed")):
                connection.execute("INSERT INTO analytics_report_delivery VALUES(?,?,?,?,?,?,?,?,?)",
                                   ("2026-09-27", "America/Los_Angeles", 1, address, status, 1, NOW.isoformat(), None, None))
        with patch.dict(os.environ, {"STYL_ANALYTICS_RECIPIENTS": "owner@example.com,sales@example.com"}), \
                patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", return_value=("accepted", None)) as send:
            result = reports.run_due(NOW)
        self.assertEqual(result["acceptedRecipients"], 2)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[1], "sales@example.com")
        self.assertIn("Page views: 350", send.call_args.args[0]["text"])
        self.assertNotIn("opted-in tracked sessions", send.call_args.args[0]["text"])

    def test_an011_version_three_replaces_old_warning_snapshot_without_resending_uncertain_mail(self) -> None:
        with self.store.connection() as connection:
            reports._ensure_tables(connection)
            connection.execute("INSERT INTO analytics_report_snapshot VALUES(?,?,?,?,?,?,?)",
                               ("2026-09-27", "America/Los_Angeles", 2, "old", "Warning: Hourly storage", "<p>Warning:</p>", NOW.isoformat()))
            for address, status in (("owner@example.com", "ambiguous"), ("sales@example.com", "failed")):
                connection.execute("INSERT INTO analytics_report_delivery VALUES(?,?,?,?,?,?,?,?,?)",
                                   ("2026-09-27", "America/Los_Angeles", 2, address, status, 1, NOW.isoformat(), None, None))
        with patch.dict(os.environ, {"STYL_ANALYTICS_RECIPIENTS": "owner@example.com,sales@example.com"}), \
                patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", return_value=("accepted", None)) as send:
            reports.run_due(NOW)
        self.assertEqual(reports.REPORT_VERSION, 3)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[1], "sales@example.com")
        self.assertNotIn("Warning:", send.call_args.args[0]["text"])
        self.assertIn("Saved inquiries: 10", send.call_args.args[0]["text"])

    def test_an011_definite_failures_have_a_bounded_retry_budget(self) -> None:
        with patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", return_value=("failed", "connection_failed")) as send:
            for minutes in (0, 16, 47, 120, 180):
                reports.run_due(NOW + timedelta(minutes=minutes))
        self.assertEqual(send.call_count, 3)
        self.assertEqual(reports.delivery_history()[0]["attempts"], 3)

    def test_an010_report_generation_failure_does_not_send_zero_metrics(self) -> None:
        with patch.object(reports, "preview_report", side_effect=reports.ReportError("Store unavailable")), patch.object(reports, "_send") as send:
            with self.assertRaises(reports.ReportError):
                reports.run_due(NOW)
        send.assert_not_called()
        self.assertEqual(reports.delivery_history(), [])

    def test_an011_partial_recipient_failure_retries_only_definite_failure(self) -> None:
        def deliver(_message, recipient):
            return ("accepted", None) if recipient == "owner@example.com" else ("failed", "connection_failed")
        with patch.dict(os.environ, {"STYL_ANALYTICS_RECIPIENTS": "owner@example.com,sales@example.com"}), \
                patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", side_effect=deliver) as send:
            self.assertEqual(reports.run_due(NOW)["status"], "needs_review")
            self.assertEqual(send.call_count, 2)
            reports.run_due(NOW + timedelta(minutes=1))
            self.assertEqual(send.call_count, 2)
            reports.run_due(NOW + timedelta(minutes=16))
            self.assertEqual(send.call_count, 3)
            self.assertEqual(send.call_args.args[1], "sales@example.com")

    def test_an011_ambiguous_or_crashed_send_is_not_automatically_retried(self) -> None:
        with patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", return_value=("ambiguous", "acceptance_unknown")) as send:
            reports.run_due(NOW)
            reports.run_due(NOW + timedelta(hours=1))
            self.assertEqual(send.call_count, 1)
        with self.store.connection() as connection:
            connection.execute("UPDATE analytics_report_delivery SET status='sending',updated_at=?", (NOW.isoformat(),))
        with patch.object(reports, "_send") as send:
            reports.run_due(NOW + timedelta(minutes=11))
            send.assert_not_called()
        self.assertEqual(reports.delivery_history()[0]["status"], "ambiguous")

    def test_an011_concurrent_jobs_claim_a_recipient_once(self) -> None:
        started, release = Event(), Event()
        def delayed_send(_message, _recipient):
            started.set()
            if not release.wait(5):
                raise RuntimeError("Test synchronization timed out")
            return "accepted", None
        with patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", side_effect=delayed_send) as send, \
                ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(reports.run_due, NOW)
            self.assertTrue(started.wait(5))
            try:
                second = executor.submit(reports.run_due, NOW)
                self.assertEqual(second.result(timeout=5)["status"], "in_progress")
            finally:
                release.set()
            self.assertEqual(first.result(timeout=5)["status"], "accepted")
            self.assertEqual(send.call_count, 1)

    def test_an011_manual_retry_requires_acknowledgement_and_keeps_attempt_count(self) -> None:
        with patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", return_value=("ambiguous", "acceptance_unknown")):
            reports.run_due(NOW)
        with self.assertRaises(reports.ReportError):
            reports.retry_delivery("2026-09-27", "owner@example.com", False)
        with patch.object(reports, "_send", return_value=("accepted", None)) as send:
            result = reports.retry_delivery("2026-09-27", "owner@example.com", True)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(send.call_count, 1)
        self.assertEqual(reports.delivery_history()[0]["attempts"], 2)

    def test_an012_mail_transport_has_aggregate_only_alternatives_and_explicit_envelope(self) -> None:
        settings = {
            "STYL_SMTP_HOST": "smtp.example.com", "STYL_SMTP_USERNAME": "sender@example.com",
            "STYL_SMTP_PASSWORD": "synthetic-test-password", "STYL_SMTP_FROM": "sender@example.com",
            "STYL_ANALYTICS_REPLY_TO": "team@example.com",
        }
        for port in ("587", "465"):
            with self.subTest(port=port), patch.dict(os.environ, {**settings, "STYL_SMTP_PORT": port}), \
                    patch.object(reports.smtplib, "SMTP") as smtp, patch.object(reports.smtplib, "SMTP_SSL") as smtp_ssl:
                transport = smtp_ssl if port == "465" else smtp
                connection = transport.return_value.__enter__.return_value
                connection.send_message.return_value = {}
                outcome = reports._send(reports.render_report(fixture_report(), "2026-09-27"), "owner@example.com")
                self.assertEqual(outcome, ("accepted", None))
                message = connection.send_message.call_args.args[0]
                self.assertEqual(connection.send_message.call_args.kwargs["to_addrs"], ["owner@example.com"])
                self.assertEqual(str(message["Reply-To"]), "team@example.com")
                self.assertEqual(message.get_content_type(), "multipart/alternative")
                self.assertNotIn("synthetic-test-password", message.as_string())
                if port == "587":
                    connection.starttls.assert_called_once()

    def test_an011_disconnect_during_data_is_ambiguous_without_provider_error_leak(self) -> None:
        with patch.dict(os.environ, {
            "STYL_SMTP_HOST": "smtp.example.com", "STYL_SMTP_USERNAME": "sender@example.com",
            "STYL_SMTP_PASSWORD": "synthetic-test-password", "STYL_SMTP_FROM": "sender@example.com", "STYL_SMTP_PORT": "587",
            "STYL_ANALYTICS_REPLY_TO": "",
        }), patch.object(reports.smtplib, "SMTP") as smtp, self.assertNoLogs(reports.logger, level="DEBUG"):
            smtp.return_value.__enter__.return_value.send_message.side_effect = smtplib.SMTPServerDisconnected(
                "PRIVATE_PROVIDER_DETAIL synthetic-test-password"
            )
            result = reports._send(reports.render_report(fixture_report(), "2026-09-27"), "owner@example.com")
        self.assertEqual(result, ("ambiguous", "acceptance_unknown"))

    def test_an011_scheduler_failure_logs_never_include_credentials_or_private_details(self) -> None:
        for error_type in (reports.ReportError, OSError, sqlite3.OperationalError):
            with self.subTest(error_type=error_type), \
                    patch.object(sys, "argv", ["analytics_reports", "run-due"]), \
                    patch.object(reports, "run_due", side_effect=error_type("synthetic-test-password PRIVATE_PROVIDER_DETAIL")), \
                    self.assertLogs(reports.logger, level="ERROR") as captured:
                self.assertEqual(reports.main(), 1)
            self.assertIn(error_type.__name__, captured.output[0])
            self.assertNotIn("synthetic-test-password", "\n".join(captured.output))
            self.assertNotIn("PRIVATE_PROVIDER_DETAIL", "\n".join(captured.output))

    def test_an014_private_sqlite_backup_is_consistent_and_refuses_overwrite(self) -> None:
        with patch.object(reports, "preview_report", side_effect=self.preview), patch.object(reports, "_send", return_value=("accepted", None)):
            reports.run_due(NOW)
        target = self.root / "backup.sqlite3"
        reports.backup_store(target)
        with closing(sqlite3.connect(target)) as recovered:
            self.assertEqual(recovered.execute("SELECT count(*) FROM analytics_report_delivery WHERE status='accepted'").fetchone()[0], 1)
        with self.assertRaises(reports.ReportError):
            reports.backup_store(target)

    def test_an017_email_settings_use_environment_defaults_until_saved_and_survive_reopen(self) -> None:
        initial = reports.get_email_settings(NOW)
        self.assertEqual(initial["source"], "environment")
        self.assertEqual(initial["revision"], 0)
        self.assertTrue(initial["enabled"])
        self.assertEqual(initial["recipients"], ["owner@example.com"])
        saved = reports.save_email_settings(reports.EmailSettingsInput(
            enabled=False, recipients=[" owner@example.com ", "Owner@EXAMPLE.COM", "sales@example.com"], expectedRevision=0,
        ))
        self.assertEqual(saved["recipients"], ["owner@example.com", "sales@example.com"])
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(saved["source"], "admin")
        with patch.object(reports, "_store", return_value=ReportStore(self.store.path)), \
                patch.dict(os.environ, {"STYL_ANALYTICS_RECIPIENTS": "different@example.com", "STYL_ANALYTICS_EMAIL_ENABLED": "true"}):
            self.assertEqual(reports.recipients(), ["owner@example.com", "sales@example.com"])
            self.assertFalse(reports.email_enabled())
        same = reports.save_email_settings(reports.EmailSettingsInput(
            enabled=False, recipients=["owner@example.com", "sales@example.com"], expectedRevision=1,
        ))
        self.assertEqual(same["revision"], 1)

    def test_an017_enabled_settings_require_recipients_and_validate_without_leaking_values(self) -> None:
        for addresses in ([], ["invalid"], ["owner@example.com\r\nBcc: private@example.com"]):
            with self.subTest(addresses=addresses), self.assertRaises(reports.ReportError) as error:
                reports.save_email_settings(reports.EmailSettingsInput(enabled=True, recipients=addresses, expectedRevision=0))
            self.assertNotIn("private@example.com", str(error.exception))
        self.assertEqual(reports.get_email_settings()["revision"], 0)
        saved = reports.save_email_settings(reports.EmailSettingsInput(enabled=False, recipients=[], expectedRevision=0))
        self.assertEqual(saved["recipients"], [])
        self.assertFalse(saved["enabled"])

    def test_an017_stale_or_concurrent_saves_cannot_silently_replace_recipients(self) -> None:
        def save(address):
            try:
                reports.save_email_settings(reports.EmailSettingsInput(enabled=False, recipients=[address], expectedRevision=0))
                return "saved"
            except reports.EmailSettingsConflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(save, ["one@example.com", "two@example.com"]))
        self.assertCountEqual(results, ["saved", "conflict"])
        self.assertEqual(reports.get_email_settings()["revision"], 1)

    def test_an017_local_saved_enabled_is_not_effective_and_never_sends(self) -> None:
        with patch.dict(os.environ, {"STYL_ANALYTICS_ENVIRONMENT": "local"}), patch.object(reports, "_send") as send:
            saved = reports.save_email_settings(reports.EmailSettingsInput(
                enabled=True, recipients=["owner@example.com"], expectedRevision=0,
            ))
            self.assertTrue(saved["enabled"])
            self.assertFalse(saved["effectiveEnabled"])
            self.assertEqual(reports.run_due(NOW)["status"], "disabled")
            send.assert_not_called()
        self.assertEqual(self.store.prunes, 1)
        self.assertEqual(reports.get_email_settings()["revision"], 1)

    def test_an017_save_never_sends_and_preview_uses_persisted_configuration(self) -> None:
        with patch.object(reports, "_send") as send:
            reports.save_email_settings(reports.EmailSettingsInput(enabled=False, recipients=[], expectedRevision=0))
            with patch.dict(sys.modules, {"app.analytics": SimpleNamespace(get_report=Mock(return_value=fixture_report()))}):
                preview = reports.preview_report("2026-09-27", NOW)
            self.assertFalse(preview["emailEnabled"])
            self.assertFalse(preview["recipientsConfigured"])
            send.assert_not_called()

    def test_an017_scheduler_uses_saved_recipients_instead_of_environment(self) -> None:
        reports.save_email_settings(reports.EmailSettingsInput(
            enabled=True, recipients=["new@example.com"], expectedRevision=0,
        ))
        with patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", return_value=("accepted", None)) as send:
            self.assertEqual(reports.run_due(NOW)["status"], "accepted")
        send.assert_called_once()
        self.assertEqual(send.call_args.args[1], "new@example.com")

    def test_an017_disable_or_recipient_removal_stops_unclaimed_deliveries(self) -> None:
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                self.store = ReportStore(self.root / f"change-during-send-{enabled}.sqlite3")
                with patch.object(reports, "_store", return_value=self.store), \
                        patch.dict(os.environ, {"STYL_ANALYTICS_RECIPIENTS": "owner@example.com,sales@example.com"}):
                    def send_first(_message, address):
                        self.assertEqual(address, "owner@example.com")
                        reports.save_email_settings(reports.EmailSettingsInput(
                            enabled=enabled, recipients=["owner@example.com"], expectedRevision=0,
                        ))
                        return "accepted", None
                    with patch.object(reports, "preview_report", side_effect=self.preview), \
                            patch.object(reports, "_send", side_effect=send_first) as send:
                        result = reports.run_due(NOW)
                    send.assert_called_once()
                    self.assertEqual(result["acceptedRecipients"], 1)
                    self.assertEqual(result["skippedRecipients"], 1)

    def test_an017_disabled_saved_settings_block_manual_retry(self) -> None:
        with patch.object(reports, "preview_report", side_effect=self.preview), \
                patch.object(reports, "_send", return_value=("failed", "connection_failed")):
            reports.run_due(NOW)
        reports.save_email_settings(reports.EmailSettingsInput(enabled=False, recipients=["owner@example.com"], expectedRevision=0))
        with patch.object(reports, "_send") as send, self.assertRaises(reports.ReportError):
            reports.retry_delivery("2026-09-27", "owner@example.com", True)
        send.assert_not_called()

    def test_an017_corrupt_settings_fail_closed_instead_of_reverting_to_enabled_environment(self) -> None:
        reports.save_email_settings(reports.EmailSettingsInput(enabled=False, recipients=[], expectedRevision=0))
        with self.store.connection() as connection:
            connection.execute("UPDATE analytics_email_settings SET recipients='invalid JSON'")
        with self.assertRaises(reports.ReportError), patch.object(reports, "_send") as send:
            reports.run_due(NOW)
        send.assert_not_called()

    def test_an017_sqlite_backup_includes_settings_without_changing_the_catalog_scope(self) -> None:
        reports.save_email_settings(reports.EmailSettingsInput(enabled=False, recipients=["owner@example.com"], expectedRevision=0))
        target = self.root / "settings-backup.sqlite3"
        reports.backup_store(target)
        with closing(sqlite3.connect(target)) as connection:
            row = connection.execute("SELECT enabled,recipients,revision FROM analytics_email_settings").fetchone()
        self.assertEqual(row[0], 0)
        self.assertEqual(json.loads(row[1]), ["owner@example.com"])
        self.assertEqual(row[2], 1)

    def test_an013_dashboard_link_cannot_contain_credentials_or_query_tokens(self) -> None:
        for url in ("https://user:password@example.com/admin", "https://example.com/admin?token=private", "http://example.com/admin"):
            with patch.dict(os.environ, {"STYL_ANALYTICS_DASHBOARD_URL": url}):
                with self.assertRaises(reports.ReportError):
                    reports.render_report(fixture_report(), "2026-09-27")


if __name__ == "__main__":
    unittest.main()
