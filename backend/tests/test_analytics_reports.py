from concurrent.futures import ThreadPoolExecutor
from collections.abc import Generator
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
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
        "generatedAt": NOW.isoformat(), "cutoffAt": NOW.isoformat(),
        "coverage": {"mode": "aggregate-only", "warnings": ["Anonymous occurrence counts only."]},
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

    def test_an010_schedule_uses_named_timezone_and_dst(self) -> None:
        zone = ZoneInfo("America/Los_Angeles")
        self.assertEqual(reports.due_date(NOW).isoformat(), "2026-09-27")
        self.assertEqual(reports.due_date(NOW - timedelta(minutes=1)).isoformat(), "2026-09-26")
        spring = datetime(2026, 3, 8, 14, tzinfo=timezone.utc)
        autumn = datetime(2026, 11, 1, 14, tzinfo=timezone.utc)
        self.assertEqual(reports.next_run_at(spring, zone).hour, 15)
        self.assertEqual(reports.next_run_at(autumn, zone).hour, 16)
        self.assertEqual(reports.next_run_at(NOW).astimezone(zone).hour, 8)
        with self.assertRaises(reports.ReportError):
            reports.next_run_at(datetime(2026, 9, 28))

    def test_an010_plain_text_html_coverage_and_aggregate_counts(self) -> None:
        rendered = reports.render_report(fixture_report(), "2026-09-27")
        self.assertIn("Page-view change versus baseline: 250%", rendered["text"])
        self.assertIn("Data cutoff:", rendered["text"])
        self.assertIn("Anonymous occurrence counts only.", rendered["text"])
        for obsolete in ("Tracked sessions:", "Estimated browser visitors:", "Median active seconds:", "Tracked quote conversion:", "\nFunnel\n", "opted-in"):
            self.assertNotIn(obsolete, rendered["text"])
        self.assertIn("<script>", rendered["text"])
        self.assertNotIn("<script>", rendered["html"])
        self.assertIn("&lt;script&gt;", rendered["html"])
        self.assertIn("admin sign-in required", rendered["text"])

    def test_an010_unavailable_metrics_are_not_normal_zero_results(self) -> None:
        report = fixture_report()
        summary = report["summary"]
        comparison = report["comparison"]
        assert isinstance(summary, dict) and isinstance(comparison, dict)
        summary["savedInquiries"] = None
        comparison["pageViewsChangePercent"] = None
        text = reports.render_report(report, "2026-09-27")["text"]
        self.assertIn("Saved inquiries: N/A", text)
        self.assertIn("no comparable baseline", text)
        report.pop("summary")
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
        self.assertIn("anonymous aggregate-only", send.call_args.args[0]["text"])
        self.assertNotIn("opted-in tracked sessions", send.call_args.args[0]["text"])

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
        }), patch.object(reports.smtplib, "SMTP") as smtp:
            smtp.return_value.__enter__.return_value.send_message.side_effect = smtplib.SMTPServerDisconnected("PRIVATE_PROVIDER_DETAIL")
            result = reports._send(reports.render_report(fixture_report(), "2026-09-27"), "owner@example.com")
        self.assertEqual(result, ("ambiguous", "acceptance_unknown"))

    def test_an014_private_sqlite_backup_is_consistent_and_refuses_overwrite(self) -> None:
        with patch.object(reports, "preview_report", side_effect=self.preview), patch.object(reports, "_send", return_value=("accepted", None)):
            reports.run_due(NOW)
        target = self.root / "backup.sqlite3"
        reports.backup_store(target)
        with closing(sqlite3.connect(target)) as recovered:
            self.assertEqual(recovered.execute("SELECT count(*) FROM analytics_report_delivery WHERE status='accepted'").fetchone()[0], 1)
        with self.assertRaises(reports.ReportError):
            reports.backup_store(target)

    def test_an013_dashboard_link_cannot_contain_credentials_or_query_tokens(self) -> None:
        for url in ("https://user:password@example.com/admin", "https://example.com/admin?token=private", "http://example.com/admin"):
            with patch.dict(os.environ, {"STYL_ANALYTICS_DASHBOARD_URL": url}):
                with self.assertRaises(reports.ReportError):
                    reports.render_report(fixture_report(), "2026-09-27")


if __name__ == "__main__":
    unittest.main()
