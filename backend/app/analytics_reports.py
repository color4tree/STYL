"""Aggregate-only daily analytics previews and an opt-in production mail job."""

from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from email.message import EmailMessage
import html
import json
import logging
import math
import os
from pathlib import Path
import smtplib
import sqlite3
import ssl
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, EmailStr, Field, TypeAdapter, ValidationError


logger = logging.getLogger(__name__)
REPORT_VERSION = 3
MAX_ATTEMPTS = 3
EMAILS = TypeAdapter(list[EmailStr])


class ReportError(ValueError):
    """Report configuration or content is not safe to send."""


class EmailSettingsConflict(ReportError):
    """The administrator edited a stale settings revision."""


class EmailSettingsUnavailable(ReportError):
    """Persisted configuration cannot be read safely."""


class EmailSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    enabled: bool
    recipients: list[str] = Field(max_length=20)
    expectedRevision: int = Field(ge=0, le=2**53 - 1)


@dataclass(frozen=True)
class EmailPreferences:
    enabled: bool
    recipients: tuple[str, ...]
    revision: int


def report_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(os.getenv("STYL_ANALYTICS_TIMEZONE", "America/Los_Angeles"))
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ReportError("Analytics reporting timezone is invalid or its timezone data is missing.") from error


def _environment_email_enabled() -> bool:
    value = os.getenv("STYL_ANALYTICS_EMAIL_ENABLED", "false").strip().lower()
    if value not in ("true", "false", "1", "0", "yes", "no", ""):
        raise ReportError("STYL_ANALYTICS_EMAIL_ENABLED must be true or false.")
    return value in ("true", "1", "yes")


def _validated_recipients(configured: list[str]) -> list[str]:
    if any("\r" in value or "\n" in value for value in configured):
        raise ReportError("Enter valid email addresses without line breaks inside an address.")
    try:
        addresses = EMAILS.validate_python([value.strip() for value in configured])
    except ValidationError as error:
        raise ReportError("Enter valid recipient email addresses.") from error
    unique: dict[str, str] = {}
    for address in addresses:
        unique.setdefault(str(address).casefold(), str(address))
    if len(unique) > 20:
        raise ReportError("Configure at most 20 internal analytics recipients.")
    return list(unique.values())


def _read_email_preferences(connection: sqlite3.Connection) -> EmailPreferences:
    row = connection.execute("SELECT enabled,recipients,revision FROM analytics_email_settings WHERE id=1").fetchone()
    if row is None:
        configured = os.getenv("STYL_ANALYTICS_RECIPIENTS", "").strip()
        addresses = _validated_recipients(configured.split(",") if configured else [])
        return EmailPreferences(_environment_email_enabled(), tuple(addresses), 0)
    try:
        addresses = json.loads(row["recipients"])
        if (row["enabled"] not in (0, 1) or type(row["revision"]) is not int or not 1 <= row["revision"] <= 2**53 - 1
                or not isinstance(addresses, list) or any(not isinstance(value, str) for value in addresses)):
            raise ReportError("Stored email settings are invalid.")
        addresses = _validated_recipients(addresses)
        if row["enabled"] and not addresses:
            raise ReportError("Stored enabled email settings have no recipients.")
        return EmailPreferences(bool(row["enabled"]), tuple(addresses), row["revision"])
    except (ValueError, TypeError) as error:
        raise EmailSettingsUnavailable("Stored email settings are invalid; check the private analytics database.") from error


def _email_preferences() -> EmailPreferences:
    with _store().connection() as connection:
        _ensure_tables(connection)
        return _read_email_preferences(connection)


def email_enabled() -> bool:
    return _email_preferences().enabled


def recipients() -> list[str]:
    return list(_email_preferences().recipients)


def _settings_view(preferences: EmailPreferences, now: datetime | None = None) -> dict[str, object]:
    environment = os.getenv("STYL_ANALYTICS_ENVIRONMENT", "local")
    zone = report_timezone()
    return {
        "enabled": preferences.enabled, "recipients": list(preferences.recipients),
        "revision": preferences.revision, "source": "admin" if preferences.revision else "environment",
        "environment": environment, "effectiveEnabled": preferences.enabled and bool(preferences.recipients) and environment == "production",
        "timezone": zone.key, "nextRunAt": next_run_at(now or datetime.now(timezone.utc), zone).isoformat(),
    }


def get_email_settings(now: datetime | None = None) -> dict[str, object]:
    return _settings_view(_email_preferences(), now)


def save_email_settings(value: EmailSettingsInput) -> dict[str, object]:
    addresses = tuple(_validated_recipients(value.recipients))
    if value.enabled and not addresses:
        raise ReportError("Add at least one recipient before enabling daily email.")
    now = datetime.now(timezone.utc)
    with _store().connection() as connection:
        _ensure_tables(connection)
        if not connection.in_transaction:
            connection.execute("BEGIN IMMEDIATE")
        previous = _read_email_preferences(connection)
        if previous.revision != value.expectedRevision:
            raise EmailSettingsConflict("Email settings changed in another session. Reload saved settings before saving your changes.")
        if previous.revision and previous.enabled == value.enabled and previous.recipients == addresses:
            return _settings_view(previous, now)
        if previous.revision >= 2**53 - 1:
            raise ReportError("Email settings revision limit reached; contact the administrator.")
        saved = EmailPreferences(value.enabled, addresses, previous.revision + 1)
        result = _settings_view(saved, now)
        connection.execute(
            """INSERT INTO analytics_email_settings(id,enabled,recipients,revision,updated_at) VALUES(1,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled,recipients=excluded.recipients,
            revision=excluded.revision,updated_at=excluded.updated_at""",
            (int(saved.enabled), json.dumps(saved.recipients), saved.revision, now.isoformat()),
        )
    return result


def next_run_at(now: datetime, zone: ZoneInfo | None = None) -> datetime:
    if now.tzinfo is None:
        raise ReportError("A timezone-aware timestamp is required.")
    zone = zone or report_timezone()
    local = now.astimezone(zone)
    day = local.date() + (timedelta(days=1) if local.time() >= time(8) else timedelta())
    return datetime.combine(day, time(8), zone).astimezone(timezone.utc)


def due_date(now: datetime, zone: ZoneInfo | None = None) -> date:
    if now.tzinfo is None:
        raise ReportError("A timezone-aware timestamp is required.")
    local = now.astimezone(zone or report_timezone())
    return local.date() - timedelta(days=1 if local.time() >= time(8) else 2)


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReportError("Report data is incomplete; no normal-looking zero report was generated.")
    return value


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ReportError("Report breakdown data is incomplete.")
    return value


def _number(value: object) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ReportError("Report metrics are invalid.")
    return f"{value:,.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}"


def _label(value: object) -> str:
    if not isinstance(value, str):
        raise ReportError("Report labels are invalid.")
    return value


def _metric(value: object, *, signed: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (value < 0 and not signed):
        raise ReportError("Report metrics are invalid.")
    return float(value)


def _active_time(seconds: float) -> str:
    if 0 < seconds < 60:
        return "<1 min"
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} hr" + (f" {minutes} min" if minutes else "")
    return f"{minutes} min"


def _dashboard_url() -> str:
    production = os.getenv("STYL_ANALYTICS_ENVIRONMENT", "local") == "production"
    url = os.getenv("STYL_ANALYTICS_DASHBOARD_URL", "https://stylfitness.com/admin" if production else "http://127.0.0.1:3000/admin")
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ReportError("Use a credential-free analytics dashboard URL without query parameters.")
    if production and parsed.scheme != "https":
        raise ReportError("The production analytics dashboard URL must use HTTPS.")
    return url


def render_report(report: dict[str, object], report_date: str) -> dict[str, str]:
    day = date.fromisoformat(report_date)
    summary = _mapping(report.get("summary"))
    coverage = _mapping(report.get("coverage"))
    comparison = _mapping(report.get("comparison"))
    try:
        zone = ZoneInfo(_label(report.get("timezone")))
        cutoff = datetime.fromisoformat(_label(report.get("cutoffAt")).replace("Z", "+00:00"))
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ReportError("Report time information is invalid.") from error
    if cutoff.tzinfo is None or not isinstance(report.get("collectionEnabled"), bool):
        raise ReportError("Report coverage is incomplete.")
    local_cutoff = cutoff.astimezone(zone)
    subject = f"STYL daily usage | {report_date}"
    if coverage.get("mode") != "aggregate-only" or set(summary) != {"pageViews", "activeSeconds", "savedInquiries"}:
        raise ReportError("Only the aggregate-only report contract can be rendered.")
    warnings = coverage.get("warnings")
    observations = report.get("observations")
    if not isinstance(warnings, list) or not all(isinstance(value, str) for value in warnings):
        raise ReportError("Report coverage is missing.")
    if not isinstance(observations, list) or not all(isinstance(value, str) for value in observations):
        raise ReportError("Report observations are invalid.")
    page_views = _metric(summary.get("pageViews"))
    active_seconds = _metric(summary.get("activeSeconds"))
    inquiries = summary.get("savedInquiries")
    if inquiries is not None:
        inquiries = _metric(inquiries)
    baseline = _metric(comparison.get("pageViewsDailyAverage"))
    change = comparison.get("pageViewsChangePercent")
    if change is not None:
        change = _metric(change, signed=True)
    partial = local_cutoff.date() <= day
    zone_label = "Pacific time" if zone.key == "America/Los_Angeles" else zone.key
    period = f"{day:%b %d, %Y} | {zone_label}"
    if local_cutoff.date() == day:
        period += f" | Through {local_cutoff:%H:%M}"
    elif local_cutoff.date() < day:
        period += " | Not started"
    environment = _label(report.get("environment"))
    if environment != "production":
        period += f" | {environment} preview"
    comparison_text = f"7-day average: {_number(baseline)}/day"
    if not partial:
        comparison_text += f"; {change:+.0f}%" if change is not None else "; no comparable baseline"
    metrics = [
        ("Page views", f"{_number(page_views)} ({comparison_text})"),
        ("Saved inquiries", _number(inquiries)),
        ("Active time (estimated)", _active_time(active_seconds)),
    ]
    actions: dict[str, float] = {}
    for row in _rows(report.get("actions")):
        name = _label(row.get("name"))
        actions[name] = actions.get(name, 0) + _metric(row.get("count"))
    metrics.extend([
        ("Cart adds", _number(actions.get("cart_add", 0))),
        ("Quote opens", _number(actions.get("quote_open", 0))),
    ])
    sections: list[tuple[str, list[str]]] = []
    items = sorted(_rows(report.get("items")), key=lambda item: (
        _metric(item.get("cartAdds")), _metric(item.get("detailViews")), _metric(item.get("impressions")),
    ), reverse=True)
    if items:
        sections.append(("Top equipment", [
            f"{' '.join(_label(item.get('name')).split())} ({_label(item.get('currency'))}): "
            f"{_number(item.get('impressions'))} impressions, {_number(item.get('detailViews'))} details, {_number(item.get('cartAdds'))} cart adds"
            for item in items[:3]
        ]))
    traffic = []
    for title, key in (("Countries", "countries"), ("Sources", "sources")):
        rows = sorted(_rows(report.get(key)), key=lambda row: _metric(row.get("pageViews")), reverse=True)
        if rows:
            traffic.append(f"{title}: " + "; ".join(
                f"{' '.join(_label(row.get('label')).split())} ({_number(row.get('pageViews'))} views)" for row in rows[:3]
            ))
    if traffic:
        sections.append(("Traffic", traffic))
    attention = []
    if report["collectionEnabled"] is False:
        attention.append("Collection is off. Check analytics settings.")
    if inquiries is None:
        attention.append("Inquiry totals are unavailable. Check saved-inquiry storage.")
    rejected = _metric(coverage.get("rejected"))
    if rejected:
        attention.append(f"{_number(rejected)} measurements rejected. Check the collector.")
    for row in _rows(report.get("errors")):
        count = _metric(row.get("count"))
        if count:
            attention.append(f"{_label(row.get('code')).capitalize()} errors: {_number(count)}. Review in the dashboard.")
    if attention:
        sections.append(("Attention", attention))
    lines = ["STYL daily usage", period, "", *[f"{label}: {value}" for label, value in metrics]]
    for title, entries in sections:
        lines.extend(["", title, *[f"- {entry}" for entry in entries]])
    dashboard = _dashboard_url()
    lines.extend(["", f"Open analytics (admin sign-in required): {dashboard}"])
    text = "\n".join(lines)
    markup = '<!doctype html><html><body style="margin:0;padding:24px;font:15px/1.6 Arial,sans-serif;color:#171717">'
    markup += '<div style="max-width:640px;margin:auto;overflow-wrap:anywhere">'
    markup += f'<h1 style="margin:0;font-size:24px">STYL daily usage</h1><p style="color:#555">{html.escape(period)}</p>'
    markup += '<table style="width:100%;border-collapse:collapse">'
    for label, value in metrics:
        markup += f'<tr><th scope="row" style="padding:8px;text-align:left;border-bottom:1px solid #eee">{html.escape(label)}</th>'
        markup += f'<td style="padding:8px;border-bottom:1px solid #eee">{html.escape(value)}</td></tr>'
    markup += "</table>"
    for title, entries in sections:
        markup += f'<h2 style="margin:24px 0 8px;font-size:18px">{html.escape(title)}</h2><ul style="padding-left:20px">'
        markup += "".join(f"<li>{html.escape(entry)}</li>" for entry in entries) + "</ul>"
    markup += f'<p style="margin-top:24px"><a href="{html.escape(dashboard, quote=True)}">Open STYL analytics</a></p></div></body></html>'
    return {"subject": subject, "text": text, "html": markup}


def preview_report(report_date: str, now: datetime | None = None) -> dict[str, object]:
    from app.analytics import get_report

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ReportError("A timezone-aware timestamp is required.")
    now = now.astimezone(timezone.utc)
    date.fromisoformat(report_date)
    report = get_report(report_date, report_date, cutoff=now.replace(minute=0, second=0, microsecond=0))
    rendered = render_report(report, report_date)
    settings = get_email_settings(now)
    return {
        "reportDate": report_date, "timezone": report_timezone().key, **rendered,
        "emailEnabled": settings["effectiveEnabled"],
        "recipientsConfigured": bool(settings["recipients"]), "nextRunAt": settings["nextRunAt"],
    }


def _store():
    from app.analytics import get_store

    return get_store()


def _ensure_tables(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS analytics_email_settings (
        id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
        recipients TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0), updated_at TEXT NOT NULL
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analytics_report_snapshot (
        report_date TEXT NOT NULL, timezone TEXT NOT NULL, version INTEGER NOT NULL,
        subject TEXT NOT NULL, text_body TEXT NOT NULL, html_body TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY (report_date, timezone, version)
    )""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analytics_report_delivery (
        report_date TEXT NOT NULL, timezone TEXT NOT NULL, version INTEGER NOT NULL, recipient TEXT NOT NULL COLLATE NOCASE,
        status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL,
        retry_after TEXT, error TEXT,
        PRIMARY KEY (report_date, timezone, version, recipient)
    )""")


def delivery_history() -> list[dict[str, object]]:
    with _store().connection() as connection:
        _ensure_tables(connection)
        records = connection.execute(
            "SELECT * FROM analytics_report_delivery ORDER BY updated_at DESC LIMIT 50"
        ).fetchall()
    return [{
        "reportDate": row["report_date"], "timezone": row["timezone"],
        "recipient": row["recipient"].split("@")[0][:1] + "***@" + row["recipient"].split("@")[1],
        "status": row["status"], "attempts": row["attempts"],
        "updatedAt": row["updated_at"], "error": row["error"],
    } for row in records]


def _send(rendered: dict[str, str], recipient: str) -> tuple[str, str | None]:
    host = os.getenv("STYL_SMTP_HOST", "").strip()
    username = os.getenv("STYL_SMTP_USERNAME", "").strip()
    password = os.getenv("STYL_SMTP_PASSWORD", "")
    sender = os.getenv("STYL_SMTP_FROM", username).strip()
    reply_to = os.getenv("STYL_ANALYTICS_REPLY_TO", "").strip()
    try:
        checked = EMAILS.validate_python([sender, *([reply_to] if reply_to else [])])
        port = int(os.getenv("STYL_SMTP_PORT", "587"))
    except (ValidationError, ValueError):
        return "failed", "invalid_smtp_configuration"
    if not host or not username or not password or not 1 <= port <= 65535:
        return "failed", "smtp_unconfigured"
    message = EmailMessage()
    message["Subject"] = rendered["subject"]
    message["From"] = str(checked[0])
    message["To"] = recipient
    if reply_to:
        message["Reply-To"] = str(checked[1])
    message.set_content(rendered["text"])
    message.add_alternative(rendered["html"], subtype="html")
    phase = "connecting"
    try:
        context = ssl.create_default_context()
        transport = smtplib.SMTP_SSL(host, port, timeout=10, context=context) if port == 465 else smtplib.SMTP(host, port, timeout=10)
        with transport as smtp:
            if port != 465:
                smtp.starttls(context=context)
            smtp.login(username, password)
            phase = "sending"
            refused = smtp.send_message(message, to_addrs=[recipient])
            if refused:
                return "failed", "recipient_refused"
            phase = "accepted"
    except (smtplib.SMTPAuthenticationError, smtplib.SMTPConnectError, smtplib.SMTPSenderRefused, smtplib.SMTPRecipientsRefused, smtplib.SMTPDataError):
        return "failed", "smtp_rejected"
    except (OSError, smtplib.SMTPException):
        if phase == "accepted":
            return "accepted", None
        return ("ambiguous", "acceptance_unknown") if phase == "sending" else ("failed", "connection_failed")
    return "accepted", None


def _deliver(report_date: str, now: datetime, addresses: list[str]) -> dict[str, object]:
    store = _store()
    zone = report_timezone().key
    key = (report_date, zone, REPORT_VERSION)
    with store.connection() as connection:
        _ensure_tables(connection)
        snapshot = connection.execute(
            "SELECT * FROM analytics_report_snapshot WHERE report_date=? AND timezone=? AND version=?", key,
        ).fetchone()
    if snapshot is None:
        preview = preview_report(report_date, now)
        with store.connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO analytics_report_snapshot VALUES(?,?,?,?,?,?,?)",
                (*key, preview["subject"], preview["text"], preview["html"], now.isoformat()),
            )
            snapshot = connection.execute(
                "SELECT * FROM analytics_report_snapshot WHERE report_date=? AND timezone=? AND version=?", key,
            ).fetchone()
    if snapshot is None:
        raise ReportError("Unable to persist the report snapshot; no email sent.")
    rendered = {"subject": snapshot["subject"], "text": snapshot["text_body"], "html": snapshot["html_body"]}
    outcomes: list[str] = []
    skipped = 0
    for recipient in addresses:
        with store.connection() as connection:
            if not connection.in_transaction:
                connection.execute("BEGIN IMMEDIATE")
            preferences = _read_email_preferences(connection)
            if (not preferences.enabled or os.getenv("STYL_ANALYTICS_ENVIRONMENT", "local") != "production"
                    or recipient.casefold() not in {address.casefold() for address in preferences.recipients}):
                skipped += 1
                continue
            earlier = connection.execute(
                "SELECT status FROM analytics_report_delivery WHERE report_date=? AND timezone=? AND recipient=? COLLATE NOCASE AND version<>? AND status IN ('accepted','sending','ambiguous')",
                (report_date, zone, recipient, REPORT_VERSION),
            ).fetchone()
            if earlier is not None:
                outcomes.append(earlier["status"])
                continue
            connection.execute(
                "INSERT OR IGNORE INTO analytics_report_delivery VALUES(?,?,?,?,?,?,?,?,?)",
                (*key, recipient, "pending", 0, now.isoformat(), None, None),
            )
            row = connection.execute(
                "SELECT * FROM analytics_report_delivery WHERE report_date=? AND timezone=? AND version=? AND recipient=?",
                (*key, recipient),
            ).fetchone()
            if row is None:
                raise ReportError("Unable to claim report delivery.")
            status = row["status"]
            if status == "sending":
                # Never automatically retry a send whose acknowledgement was lost.
                if datetime.fromisoformat(row["updated_at"]) < now - timedelta(minutes=10):
                    connection.execute(
                        "UPDATE analytics_report_delivery SET status='ambiguous',error='interrupted_send',updated_at=? WHERE report_date=? AND timezone=? AND version=? AND recipient=?",
                        (now.isoformat(), *key, recipient),
                    )
                    status = "ambiguous"
                outcomes.append(status)
                continue
            manual_retry = status == "pending" and row["error"] == "manual_retry"
            if status in ("accepted", "ambiguous") or (row["attempts"] >= MAX_ATTEMPTS and not manual_retry) or (
                row["retry_after"] and datetime.fromisoformat(row["retry_after"]) > now
            ):
                outcomes.append(status)
                continue
            attempts = row["attempts"] + 1
            connection.execute(
                "UPDATE analytics_report_delivery SET status='sending',attempts=?,updated_at=?,retry_after=NULL,error=NULL WHERE report_date=? AND timezone=? AND version=? AND recipient=?",
                (attempts, now.isoformat(), *key, recipient),
            )
        status, error = _send(rendered, recipient)
        retry_after = (now + timedelta(minutes=15 * 2 ** (attempts - 1))).isoformat() if status == "failed" and attempts < MAX_ATTEMPTS else None
        with store.connection() as connection:
            connection.execute(
                "UPDATE analytics_report_delivery SET status=?,updated_at=?,retry_after=?,error=? WHERE report_date=? AND timezone=? AND version=? AND recipient=? AND status='sending'",
                (status, now.isoformat(), retry_after, error, *key, recipient),
            )
        outcomes.append(status)
    return {
        "status": "skipped" if not outcomes and skipped else
                  "accepted" if outcomes and all(outcome == "accepted" for outcome in outcomes) else
                  "in_progress" if outcomes and all(outcome in ("accepted", "sending") for outcome in outcomes) else "needs_review",
        "reportDate": report_date, "acceptedRecipients": outcomes.count("accepted"),
        "failedRecipients": outcomes.count("failed"), "ambiguousRecipients": outcomes.count("ambiguous"),
        "skippedRecipients": skipped,
        "nextRunAt": next_run_at(now).isoformat(),
    }


def run_due(now: datetime | None = None) -> dict[str, object]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ReportError("A timezone-aware timestamp is required.")
    now = now.astimezone(timezone.utc)
    store = _store()
    store.prune()
    with store.connection() as connection:
        _ensure_tables(connection)
        connection.execute(
            "UPDATE analytics_report_delivery SET status='ambiguous',error='interrupted_send',updated_at=? WHERE status='sending' AND updated_at < ?",
            (now.isoformat(), (now - timedelta(minutes=10)).isoformat()),
        )
    if not email_enabled() or os.getenv("STYL_ANALYTICS_ENVIRONMENT", "local") != "production":
        return {"status": "disabled", "nextRunAt": next_run_at(now).isoformat()}
    addresses = recipients()
    if not addresses:
        raise ReportError("Configure separate internal STYL_ANALYTICS_RECIPIENTS before enabling email.")
    return _deliver(due_date(now).isoformat(), now, addresses)


def retry_delivery(report_date: str, recipient: str, acknowledge_duplicate_risk: bool) -> dict[str, object]:
    if not acknowledge_duplicate_risk:
        raise ReportError("Explicit duplicate-risk acknowledgement is required for manual retry.")
    if not email_enabled() or os.getenv("STYL_ANALYTICS_ENVIRONMENT", "local") != "production":
        raise ReportError("Real analytics mail is disabled outside an explicitly enabled production environment.")
    if recipient not in recipients():
        raise ReportError("Recipient must be in the current analytics recipient configuration.")
    date.fromisoformat(report_date)
    now = datetime.now(timezone.utc)
    key = (report_date, report_timezone().key, REPORT_VERSION, recipient)
    with _store().connection() as connection:
        _ensure_tables(connection)
        if not connection.in_transaction:
            connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status FROM analytics_report_delivery WHERE report_date=? AND timezone=? AND version=? AND recipient=?", key,
        ).fetchone()
        if row is None or row["status"] not in ("failed", "ambiguous"):
            raise ReportError("Only failed or ambiguous deliveries may be manually retried.")
        connection.execute(
            "UPDATE analytics_report_delivery SET status='pending',retry_after=NULL,error='manual_retry',updated_at=? WHERE report_date=? AND timezone=? AND version=? AND recipient=?",
            (now.isoformat(), *key),
        )
    return _deliver(report_date, now, [recipient])


def backup_store(destination: Path) -> None:
    if destination.exists() or not destination.parent.is_dir():
        raise ReportError("Choose a new private backup file in an existing directory.")
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with _store().connection() as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
    except (sqlite3.Error, OSError):
        destination.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview aggregate analytics or run the guarded daily email job.")
    commands = parser.add_subparsers(dest="command", required=True)
    preview = commands.add_parser("preview")
    preview.add_argument("--date", required=True)
    preview.add_argument("--format", choices=("text", "html", "json"), default="text")
    commands.add_parser("run-due")
    retry = commands.add_parser("retry")
    retry.add_argument("--date", required=True)
    retry.add_argument("--recipient", required=True)
    retry.add_argument("--acknowledge-duplicate-risk", action="store_true")
    backup = commands.add_parser("backup")
    backup.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "preview":
            result = preview_report(args.date)
            print(json.dumps(result) if args.format == "json" else result[args.format])
        elif args.command == "backup":
            backup_store(args.destination)
            print("Private analytics SQLite backup completed; protect it and enforce retention/deletion policy.")
        else:
            result = run_due() if args.command == "run-due" else retry_delivery(args.date, args.recipient, args.acknowledge_duplicate_risk)
            print(json.dumps(result))
            if result["status"] == "needs_review":
                return 1
    except (ReportError, ValueError, OSError, sqlite3.Error) as error:
        logger.error("Analytics report failed (%s). Check configuration/store health; private data was not logged.", type(error).__name__)
        return 1
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
