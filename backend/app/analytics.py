"""Anonymous occurrence counts, aggregated before storage without browser identities."""

from __future__ import annotations

import calendar
from collections import defaultdict, deque
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
import csv
import hashlib
import io
import json
import logging
import math
import os
from pathlib import Path
import re
import secrets
import sqlite3
from threading import Lock
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError


logger = logging.getLogger(__name__)
MAX_BATCH_BYTES = 16 * 1024
MAX_EVENTS = 20
PATHS = {"/", "/accessories", "/cart", "/products/[slug]", "other"}
SOURCES = {"google", "bing", "facebook", "instagram", "youtube", "linkedin", "newsletter", "direct", "other"}
MEDIUMS = {"organic", "cpc", "paid", "social", "email", "referral", "direct", "other"}
ENUMS = {
    "itemType": {"product", "accessory"},
    "action": {"header", "menu", "catalog", "details", "continue_shopping", "back_to_collection", "section", "quote", "other"},
    "source": {"header", "cart", "product", "direct", "unknown"},
    "list": {"products", "accessories"}, "mediaType": {"image", "video"},
    "errorCode": {"validation", "network", "storage", "catalog", "media", "unknown"},
    "metric": {"LCP", "INP", "CLS"},
}
ITEM = {"itemType", "itemId"}
EVENT_FIELDS = {
    "page_view": set(), "navigation_click": {"action", "toPath"},
    "item_impression": ITEM | {"list"}, "item_detail_open": ITEM,
    "item_details_expand": ITEM, "media_open": ITEM | {"mediaType", "mediaIndex"},
    "cart_add": ITEM | {"quantity", "lineCount", "saleUnits"},
    "cart_quantity_change": ITEM | {"quantity", "lineCount", "saleUnits"},
    "cart_remove": ITEM | {"quantity", "lineCount", "saleUnits"},
    "cart_clear": {"lineCount", "saleUnits"}, "cart_view": {"lineCount", "saleUnits"},
    "quote_open": ITEM | {"source"}, "quote_form_start": {"source"},
    "quote_submit_attempt": {"source"}, "quote_error": {"source", "errorCode"},
    "catalog_empty": {"list"}, "item_unavailable": ITEM,
    "engagement": {"activeMs"}, "site_error": {"errorCode"},
    "web_vital": {"metric", "value"},
}
ITEM_REQUIRED = {"item_impression", "item_detail_open", "item_details_expand", "cart_add", "cart_quantity_change", "cart_remove"}
ITEM_METRICS = {
    "item_impression": "impressions", "item_detail_open": "detailViews",
    "item_details_expand": "expansions", "media_open": "mediaOpens",
    "cart_add": "cartAdds", "quote_open": "quoteOpens",
}
LEGACY_TABLES = ("analytics_events", "analytics_sessions", "analytics_visitors", "analytics_receipts", "analytics_rollups")
rate_lock = Lock()
rate_salt = secrets.token_bytes(32)
rate_windows: dict[str, deque[tuple[float, int]]] = {}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def hour_start(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("A timezone-aware timestamp is required.")
    return value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def moment(value: object) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("Invalid timestamp.")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamps require a timezone.")
    return parsed.astimezone(timezone.utc)


def setting_bool(name: str, default: str = "false") -> bool:
    value = os.getenv(name, default).strip().lower()
    if value not in ("true", "false", "1", "0", "yes", "no", ""):
        raise ValueError(f"{name} must be true or false.")
    return value in ("true", "1", "yes")


def enabled() -> bool:
    return setting_bool("STYL_ANALYTICS_ENABLED")


def environment() -> str:
    value = os.getenv("STYL_ANALYTICS_ENVIRONMENT", "local")
    if value not in ("local", "test", "staging", "production"):
        raise ValueError("Invalid analytics environment.")
    return value


def report_zone() -> ZoneInfo:
    try:
        return ZoneInfo(os.getenv("STYL_ANALYTICS_TIMEZONE", "America/Los_Angeles"))
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Analytics timezone is invalid or timezone data is unavailable.") from error


def campaigns() -> list[str]:
    values = list(dict.fromkeys(value.strip() for value in os.getenv("STYL_ANALYTICS_CAMPAIGN_ALLOWLIST", "").split(",") if value.strip()))
    if len(values) > 100 or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value) for value in values):
        raise ValueError("Invalid analytics campaign allowlist.")
    return values


def excluded(request: Request) -> bool:
    return (
        request.headers.get("DNT", "").lower() in ("1", "yes")
        or request.headers.get("Sec-GPC") == "1"
        or request.headers.get("X-STYL-Analytics-Exclude") == "1"
        or bool(request.headers.get("authorization"))
        or bool(re.search(r"bot|crawler|spider|headless|uptime|monitor", request.headers.get("user-agent", ""), re.I))
    )


def public_config(request: Request) -> dict[str, object]:
    return {
        "enabled": enabled() and not excluded(request), "mode": "aggregate-only",
        "environment": environment(), "timezone": report_zone().key,
        "heartbeatSeconds": 15, "idleSeconds": 60, "maxEvents": MAX_EVENTS,
        "maxBatchBytes": MAX_BATCH_BYTES, "allowedCampaigns": campaigns(),
    }


class EventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(max_length=40)
    path: str = Field(max_length=40)
    properties: dict[str, object] = Field(default_factory=dict)


class ContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source: str = Field(default="direct", max_length=64)
    medium: str = Field(default="direct", max_length=64)
    campaign: str = Field(default="", max_length=64)
    viewport: Literal["phone", "tablet", "desktop"] = "desktop"


class BatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    events: list[EventInput] = Field(min_length=1, max_length=MAX_EVENTS)
    context: ContextInput = Field(default_factory=ContextInput)


class RevokeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    sessionToken: str = Field(min_length=32, max_length=128)


def browser_family(request: Request) -> str:
    agent = request.headers.get("user-agent", "")
    return "Edge" if "Edg/" in agent else "Firefox" if "Firefox/" in agent else "Chrome" if "Chrome/" in agent else "Safari" if "Safari/" in agent else "Other"


def limit_rate(key: str, maximum: int, cost: int = 1) -> None:
    now = utcnow().timestamp()
    with rate_lock:
        for old in [key for key, values in rate_windows.items() if not values or values[-1][0] < now - 60]:
            del rate_windows[old]
        if key not in rate_windows and len(rate_windows) >= 4096:
            raise HTTPException(status_code=429, detail="Analytics rate limit reached.", headers={"Retry-After": "60"})
        window = rate_windows.setdefault(key, deque())
        while window and window[0][0] < now - 60:
            window.popleft()
        if sum(value for _, value in window) + cost > maximum:
            raise HTTPException(status_code=429, detail="Analytics rate limit reached.", headers={"Retry-After": "60"})
        window.append((now, cost))


def configured_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    path = Path(os.getenv("STYL_ANALYTICS_DB", str(root / ".styl-runtime" / "analytics.sqlite3")))
    if not path.is_absolute():
        raise ValueError("Analytics storage must use an absolute private path.")
    if path.is_symlink():
        raise ValueError("Analytics database must not be a symlink.")
    path = path.resolve()
    data = Path(os.getenv("STYL_DATA_DIR", str(root / "backend" / "app" / "data")))
    forbidden = [root / "frontend" / "public", root / "frontend" / ".next", root / "backend" / "app" / "uploads", data / "uploads"]
    if any(path.is_relative_to(directory.resolve()) for directory in forbidden) or path.suffix != ".sqlite3":
        raise ValueError("Analytics storage must be a private SQLite file outside public/upload directories.")
    return path


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _increment(connection: sqlite3.Connection, hour: str, dimension: str, label: str, metric: str, total: float = 0) -> None:
    connection.execute(
        """INSERT INTO analytics_aggregate_counts VALUES(?,?,?,?,1,?)
           ON CONFLICT(hour,dimension,label,metric) DO UPDATE SET count=count+1,total=total+excluded.total""",
        (hour, dimension, label, metric, total),
    )


class AnalyticsStore:
    def __init__(self, path: Path, env: str | None = None) -> None:
        self.path = path
        self.environment = env or environment()

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise OSError("Analytics database must not be a symlink.")
        if not self.path.exists():
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if self.path.is_symlink():
                    raise OSError("Analytics database must not be a symlink.") from None
            else:
                os.close(descriptor)
        if self.path.stat().st_size > 1024**3:
            raise OSError("Analytics storage limit reached; run retention maintenance.")
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA secure_delete=ON")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS analytics_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS analytics_aggregate_counts(
                    hour TEXT NOT NULL, dimension TEXT NOT NULL, label TEXT NOT NULL,
                    metric TEXT NOT NULL, count INTEGER NOT NULL, total REAL NOT NULL,
                    PRIMARY KEY(hour,dimension,label,metric));
                CREATE TABLE IF NOT EXISTS analytics_aggregate_items(
                    hour TEXT NOT NULL, item_type TEXT NOT NULL, item_id INTEGER NOT NULL,
                    currency TEXT NOT NULL, name TEXT NOT NULL, category TEXT NOT NULL,
                    metric TEXT NOT NULL, count INTEGER NOT NULL,
                    PRIMARY KEY(hour,item_type,item_id,currency,metric));
            """)
            connection.execute("INSERT OR IGNORE INTO analytics_meta VALUES('environment',?)", (self.environment,))
            if connection.execute("SELECT value FROM analytics_meta WHERE key='environment'").fetchone()[0] != self.environment:
                raise ValueError("Do not share an analytics database across environments.")
            connection.commit()
            with connection:
                yield connection
        finally:
            connection.close()

    def counter(self, kind: Literal["excluded", "rejected"]) -> None:
        with self.connection() as connection:
            _increment(connection, stamp(hour_start(utcnow())), "quality", kind, "count")

    def ingest(self, batch: BatchInput, market: Mapping[str, object], browser: str = "Other") -> dict[str, int]:
        checked = [_event(value) for value in batch.events]
        context = batch.context
        if context.source not in SOURCES or context.medium not in MEDIUMS or (
            "campaign" in context.model_fields_set and context.campaign not in campaigns()
        ):
            raise ValueError("Unsupported analytics context.")
        country, currency = market.get("countryCode"), market.get("currency")
        if (country is not None and (not isinstance(country, str) or not re.fullmatch("[A-Z]{2}", country))) or currency not in ("CAD", "USD"):
            raise ValueError("Invalid server market.")
        if browser not in ("Edge", "Firefox", "Chrome", "Safari", "Other"):
            raise ValueError("Invalid browser family.")
        lookup = public_items(market) if any("itemId" in event.properties for event in checked) else {}
        for event in checked:
            props = event.properties
            if "itemId" in props and (props["itemType"], props["itemId"]) not in lookup:
                raise ValueError("Item is not in the public market catalog.")
        hour = stamp(hour_start(utcnow()))
        dimensions = {
            "country": country or "Unknown", "source": f"{context.source} / {context.medium}",
            "campaign": context.campaign or "none", "device": context.viewport, "browser": browser,
        }
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("INSERT INTO analytics_meta VALUES('aggregate_tracking_since',?) ON CONFLICT(key) DO UPDATE SET value=min(value,excluded.value)", (hour,))
            for event in checked:
                props = event.properties
                if event.name in ("page_view", "engagement"):
                    metric = "pageViews" if event.name == "page_view" else "activeMs"
                    total = props.get("activeMs", 0)
                    _increment(connection, hour, "total", "all", metric, total)
                    _increment(connection, hour, "page", event.path, metric, total)
                if event.name == "page_view":
                    for dimension, label in dimensions.items():
                        _increment(connection, hour, dimension, label, "pageViews")
                elif event.name == "web_vital":
                    _increment(connection, hour, "vital", str(props["metric"]), "value", props["value"])
                elif event.name != "engagement":
                    _increment(connection, hour, "action", event.name, "count")
                if event.name in ("quote_error", "site_error", "catalog_empty", "item_unavailable"):
                    label = f"{event.name}:{props.get('errorCode', props.get('list', 'unknown'))}"
                    _increment(connection, hour, "error", label, "count")
                if "itemId" in props and event.name in ITEM_METRICS:
                    item = lookup[(props["itemType"], props["itemId"])]
                    connection.execute(
                        """INSERT INTO analytics_aggregate_items VALUES(?,?,?,?,?,?,?,1)
                           ON CONFLICT(hour,item_type,item_id,currency,metric)
                           DO UPDATE SET count=count+1,name=excluded.name,category=excluded.category""",
                        (hour, item["itemType"], item["itemId"], item["currency"], item["name"], item["category"], ITEM_METRICS[event.name]),
                    )
            connection.execute("INSERT INTO analytics_meta VALUES('aggregate_last_event_at',?) ON CONFLICT(key) DO UPDATE SET value=max(value,excluded.value)", (hour,))
        return {"accepted": len(checked)}

    def revoke(self, token: str) -> None:
        # Only the retired collector's deletion path accepts an old token.
        with self.connection() as connection:
            tables = _tables(connection)
            if "analytics_sessions" not in tables:
                return
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT id,visitor_hash FROM analytics_sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
            if row is None:
                return
            ids = [item[0] for item in connection.execute("SELECT id FROM analytics_sessions WHERE visitor_hash=?", (row["visitor_hash"],))] if row["visitor_hash"] else [row["id"]]
            for session_id in ids:
                if "analytics_events" in tables:
                    connection.execute("DELETE FROM analytics_events WHERE session_id=?", (session_id,))
                if "analytics_receipts" in tables:
                    connection.execute("UPDATE analytics_receipts SET session_id=NULL,source='unknown',items='[]' WHERE session_id=?", (session_id,))
                connection.execute("DELETE FROM analytics_sessions WHERE id=?", (session_id,))
            if row["visitor_hash"] and "analytics_visitors" in tables:
                connection.execute("DELETE FROM analytics_visitors WHERE hash=?", (row["visitor_hash"],))

    def prune(self, now: datetime | None = None) -> None:
        now = now or utcnow()
        today = now.astimezone(report_zone()).date()
        month = today.year * 12 + today.month - 1 - 13
        floor_day = date(month // 12, month % 12 + 1, min(today.day, calendar.monthrange(month // 12, month % 12 + 1)[1]))
        floor = stamp(datetime.combine(floor_day, time.min, report_zone()))
        legacy_floor = stamp(hour_start(now - timedelta(days=30)))
        with self.connection() as connection:
            connection.execute("DELETE FROM analytics_aggregate_counts WHERE hour<?", (floor,))
            connection.execute("DELETE FROM analytics_aggregate_items WHERE hour<?", (floor,))
            tables = _tables(connection)
            if "analytics_events" in tables:
                connection.execute("DELETE FROM analytics_events WHERE occurred_at<? OR received_at<?", (legacy_floor, legacy_floor))
            if "analytics_receipts" in tables:
                connection.execute("DELETE FROM analytics_receipts WHERE created_at<?", (legacy_floor,))
            if "analytics_sessions" in tables:
                remaining = " AND id NOT IN (SELECT session_id FROM analytics_events)" if "analytics_events" in tables else ""
                connection.execute("DELETE FROM analytics_sessions WHERE last_at<?" + remaining, (legacy_floor,))
                if "analytics_visitors" in tables:
                    connection.execute("UPDATE analytics_sessions SET visitor_hash=NULL WHERE visitor_hash IN (SELECT hash FROM analytics_visitors WHERE expires_at<=? OR first_at<?)", (stamp(now), legacy_floor))
            if "analytics_visitors" in tables:
                connection.execute("DELETE FROM analytics_visitors WHERE expires_at<=? OR first_at<?", (stamp(now), legacy_floor))
            if "analytics_rollups" in tables:
                connection.execute("DELETE FROM analytics_rollups WHERE day<?", (floor_day.isoformat(),))
            if "analytics_counters" in tables:
                connection.execute("DELETE FROM analytics_counters WHERE day<?", (floor_day.isoformat(),))
        with self.connection() as connection:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def get_store() -> AnalyticsStore:
    return AnalyticsStore(configured_path())


def public_items(market: Mapping[str, object]) -> dict:
    from app.main import analytics_catalog
    return {(item["itemType"], item["itemId"]): item for item in analytics_catalog(market)}


def _event(value: EventInput) -> EventInput:
    if value.name not in EVENT_FIELDS or value.path not in PATHS or not set(value.properties).issubset(EVENT_FIELDS[value.name]):
        raise ValueError("Unsupported analytics event or field.")
    props = value.properties
    for key, field in props.items():
        if key in ENUMS:
            if not isinstance(field, str) or field not in ENUMS[key]:
                raise ValueError("Unsupported analytics property value.")
        elif key == "toPath":
            if not isinstance(field, str) or field not in PATHS | {"#products", "#about", "#contact", "#gallery"}:
                raise ValueError("Noncanonical analytics navigation path.")
        else:
            maximum = {"quantity": 10, "activeMs": 15000, "mediaIndex": 11, "itemId": 2**53 - 1, "value": 3_600_000}.get(key, 10000)
            if isinstance(field, bool) or not isinstance(field, (int, float)) or not math.isfinite(field) or not (1 if key == "itemId" else 0) <= field <= maximum or (key != "value" and not isinstance(field, int)):
                raise ValueError("Invalid analytics measurement.")
    if ("itemId" in props) != ("itemType" in props) or (value.name in ITEM_REQUIRED and not ITEM.issubset(props)):
        raise ValueError("Incomplete item reference.")
    if value.name in ("engagement", "web_vital") and set(props) != EVENT_FIELDS[value.name]:
        raise ValueError("Incomplete analytics measurement.")
    return value


def day_window(start: str, end: str, zone: ZoneInfo) -> tuple[datetime, datetime]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end):
        raise ValueError("Use ISO calendar dates.")
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first > last or (last - first).days > 396:
        raise ValueError("Choose an ordered date range of at most 397 days.")
    try:
        beginning = datetime.combine(first, time.min, zone).astimezone(timezone.utc)
        ending = datetime.combine(last + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    except OverflowError:
        raise ValueError("Date range exceeds supported calendar bounds.") from None
    if beginning.minute or ending.minute or beginning.second or ending.second:
        raise ValueError("Hourly analytics reports require whole-hour UTC offsets.")
    return beginning, ending


def _aggregate(connection: sqlite3.Connection, first: datetime, last: datetime, cutoff: datetime, zone: ZoneInfo) -> dict:
    bounds = (stamp(first), stamp(min(last, cutoff)))
    rows = connection.execute(
        """SELECT dimension,label,metric,sum(count) AS count,sum(total) AS total
           FROM analytics_aggregate_counts WHERE hour>=? AND hour<?
           GROUP BY dimension,label,metric""", bounds,
    ).fetchall()
    summary = {"pageViews": 0, "activeSeconds": 0, "savedInquiries": 0}
    breakdowns = {field: [] for field in ("countries", "sources", "campaigns", "devices", "browsers")}
    names = {"country": "countries", "source": "sources", "campaign": "campaigns", "device": "devices", "browser": "browsers"}
    pages = {}
    actions, errors, vitals = [], [], []
    quality = {"excluded": 0, "rejected": 0}
    for row in rows:
        dimension, label, metric = row["dimension"], row["label"], row["metric"]
        amount = row["total"] / 1000 if metric == "activeMs" else row["count"]
        field = "activeSeconds" if metric == "activeMs" else metric
        if dimension == "total":
            summary[field] = amount
        elif dimension in names:
            breakdowns[names[dimension]].append({"label": label, "pageViews": amount})
        elif dimension == "page":
            pages.setdefault(label, {"path": label, "pageViews": 0, "activeSeconds": 0})[field] = amount
        elif dimension == "action":
            actions.append({"name": label, "count": row["count"]})
        elif dimension == "error":
            errors.append({"code": label, "count": row["count"]})
        elif dimension == "vital":
            vitals.append({"metric": label, "count": row["count"], "average": row["total"] / row["count"]})
        elif dimension == "quality":
            quality[label] = row["count"]
    items = {}
    for row in connection.execute("SELECT * FROM analytics_aggregate_items WHERE hour>=? AND hour<? ORDER BY hour", bounds):
        key = (row["item_type"], row["item_id"], row["currency"])
        item = items.setdefault(key, {
            "itemType": row["item_type"], "itemId": row["item_id"], "currency": row["currency"],
            **{metric: 0 for metric in ITEM_METRICS.values()},
        })
        item.update(name=row["name"], category=row["category"])
        item[row["metric"]] += row["count"]
    daily = defaultdict(lambda: {"pageViews": 0, "activeSeconds": 0, "inquiries": 0})
    hourly = defaultdict(lambda: {"pageViews": 0, "activeSeconds": 0})
    for row in connection.execute("SELECT hour,metric,count,total FROM analytics_aggregate_counts WHERE dimension='total' AND hour>=? AND hour<?", bounds):
        local = moment(row["hour"]).astimezone(zone)
        metric = "activeSeconds" if row["metric"] == "activeMs" else "pageViews"
        amount = row["total"] / 1000 if metric == "activeSeconds" else row["count"]
        daily[local.date().isoformat()][metric] += amount
        hourly[local.hour][metric] += amount
    return {
        "summary": summary, **{key: sorted(value, key=lambda row: (-row["pageViews"], row["label"])) for key, value in breakdowns.items()},
        "pages": sorted(pages.values(), key=lambda row: (-row["pageViews"], row["path"])),
        "items": sorted(items.values(), key=lambda row: (-row["impressions"], -row["cartAdds"], row["name"], row["itemId"], row["currency"])),
        "actions": sorted(actions, key=lambda row: (-row["count"], row["name"])),
        "errors": sorted(errors, key=lambda row: (-row["count"], row["code"])),
        "webVitals": vitals, "daily": daily, "hourly": hourly, "quality": quality,
    }


def get_report(start: str, end: str, *, cutoff: datetime | None = None, inquiries_path: Path | None = None) -> dict:
    from app.main import analytics_inquiry_summaries
    zone = report_zone()
    first, last = day_window(start, end, zone)
    now = utcnow()
    completed_hours = cutoff is not None
    if cutoff is not None:
        cutoff = min(hour_start(cutoff), hour_start(now))
    else:
        cutoff = now
    aggregate_cutoff = cutoff if completed_hours else hour_start(now) + timedelta(hours=1)
    store = get_store()
    warnings = [
        "Anonymous aggregate-only activity; no unique or returning visitors, sessions, funnels or inquiry attribution.",
        "Counts are occurrences, not people. Lost, blocked, offline or repeated requests can change totals.",
        "Active seconds are summed estimates assigned to the received hour, not per-visitor medians or interval unions. Exclusive browser Web Locks reduce cross-tab overlap where available; delivery and browser limitations remain.",
        "Independent coarse dimensions cannot be combined into visitor profiles.",
        "Aggregate retention is 13 calendar months; expired browsing counts cannot be recovered from this report.",
    ]
    warnings.append("Data cutoff is the start of the current completed-hour boundary; the incomplete hour is excluded." if completed_hours else "The current hour is included and incomplete; activity is bucketed by server receipt hour.")
    earlier_day = first.astimezone(zone).date() - timedelta(days=7)
    earlier_first, earlier_last = day_window(earlier_day.isoformat(), (earlier_day + timedelta(days=6)).isoformat(), zone)
    with store.connection() as connection:
        result = _aggregate(connection, first, last, aggregate_cutoff, zone)
        earlier = _aggregate(connection, earlier_first, earlier_last, aggregate_cutoff, zone)
        meta = dict(connection.execute("SELECT key,value FROM analytics_meta"))
        tables = _tables(connection)
        if any(connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() for table in LEGACY_TABLES if table in tables):
            warnings.append("Legacy identified analytics data exists but is excluded from this report. Maintenance retains legacy raw data for at most 30 days and legacy rollups for 13 calendar months; protected backups require separate expiry.")
    if not enabled():
        warnings.append("Collection is disabled; existing aggregate data may be displayed.")
    tracked = meta.get("aggregate_tracking_since")
    if tracked is None or first < moment(tracked):
        warnings.append("Earlier browsing activity is unavailable; aggregate-only tracking begins with its first accepted hour.")
    try:
        inquiry_times = [moment(row.get("createdAt")) for row in analytics_inquiry_summaries(inquiries_path)]
    except (OSError, ValueError):
        result["summary"]["savedInquiries"] = None
        warnings.append("Saved-inquiry totals are unavailable; daily inquiry counts are unconfirmed, not evidence of zero inquiries.")
    else:
        for created in inquiry_times:
            if first <= created < min(last, cutoff):
                result["summary"]["savedInquiries"] += 1
                result["daily"][created.astimezone(zone).date().isoformat()]["inquiries"] += 1
    result["daily"] = [{"date": day, **values} for day, values in sorted(result["daily"].items())]
    result["hourly"] = [{"hour": hour, **values} for hour, values in sorted(result["hourly"].items())]
    quality = result.pop("quality")
    average = earlier["summary"]["pageViews"] / 7
    days = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    current_average = result["summary"]["pageViews"] / days
    result.update({
        "start": start, "end": end, "timezone": zone.key, "generatedAt": stamp(now), "cutoffAt": stamp(cutoff),
        "environment": store.environment, "collectionEnabled": enabled(),
        "coverage": {"mode": "aggregate-only", "trackingSince": tracked, "lastEventAt": meta.get("aggregate_last_event_at"), "warnings": warnings, **quality},
        "comparison": {"days": 7, "pageViewsDailyAverage": average, "pageViewsChangePercent": (current_average - average) / average * 100 if average else None},
        "observations": [f"{result['summary']['pageViews']} page views recorded; these are occurrence counts, not distinct visitors."],
    })
    if result["errors"]:
        result["observations"].append("Recorded catalog, media or quote errors warrant review; absent error counts do not prove there were no failures.")
    return result


def export_csv(report: dict) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["section", "label", "metric", "value"])
    def safe(value: object) -> str:
        text = "N/A" if value is None else str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
    for key in ("start", "end", "timezone", "generatedAt", "cutoffAt", "environment"):
        writer.writerow(["report", "", key, safe(report[key])])
    for warning in report["coverage"]["warnings"]:
        writer.writerow(["coverage", "", "warning", safe(warning)])
    for key, value in report["summary"].items():
        writer.writerow(["summary", "", key, safe(value)])
    for field in ("countries", "sources", "campaigns", "devices", "browsers", "pages", "items", "actions", "errors", "webVitals", "daily", "hourly"):
        for row in report[field]:
            label = row.get("label", row.get("name", row.get("path", row.get("code", row.get("metric", row.get("date", row.get("hour", "")))))))
            if field == "items":
                label = f"{row['itemType']}:{row['itemId']} | {label} | {row['currency']}"
            for key, value in row.items():
                if isinstance(value, (int, float)) or value is None:
                    writer.writerow([field, safe(label), key, safe(value)])
    return output.getvalue()


def make_router(require_admin, allowed_origins: list[str]) -> APIRouter:
    router = APIRouter()

    def note(kind: Literal["excluded", "rejected"]) -> None:
        try:
            if enabled():
                get_store().counter(kind)
        except (OSError, ValueError, sqlite3.Error):
            logger.warning("Analytics quality counter unavailable; no request fields were logged.")

    def guard(request: Request, collect: bool = True) -> None:
        if request.headers.get("origin") not in allowed_origins:
            note("rejected")
            raise HTTPException(status_code=403, detail="Analytics request origin is not allowed.")
        if collect and (not enabled() or excluded(request)):
            note("excluded")
            raise HTTPException(status_code=403, detail="Analytics collection is disabled or excluded.")
        actor = hashlib.sha256(rate_salt + (request.client.host if request.client else "unknown").encode()).hexdigest()
        limit_rate("request:" + actor, 120)

    async def body(request: Request) -> object:
        def unique_object(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate analytics JSON field.")
                result[key] = value
            return result

        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BATCH_BYTES:
                note("rejected")
                raise HTTPException(status_code=413, detail="Analytics batch exceeds 16 KiB.")
            data.extend(chunk)
        return json.loads(data, object_pairs_hook=unique_object)

    def safe_error(error: Exception) -> HTTPException:
        if isinstance(error, (ValidationError, ValueError)):
            note("rejected")
            return HTTPException(status_code=422, detail="Invalid analytics request or reporting configuration.")
        logger.error("Analytics storage unavailable (%s); private request data was not logged.", type(error).__name__)
        return HTTPException(status_code=503, detail="Analytics storage is unavailable. Shopping and inquiries are unaffected.")

    @router.get("/api/analytics/config")
    def config(request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store, private"
        try:
            return public_config(request)
        except (ValueError, KeyError):
            logger.error("Analytics configuration is invalid.")
            raise HTTPException(status_code=503, detail="Analytics configuration is unavailable.") from None

    @router.post("/api/analytics/session")
    async def start_session():
        raise HTTPException(status_code=410, detail="Identified analytics collection is retired. Use aggregate-only events.", headers={"Cache-Control": "no-store, private"})

    @router.post("/api/analytics/events")
    async def ingest(request: Request, response: Response):
        try:
            guard(request)
            batch = BatchInput.model_validate(await body(request))
            actor = hashlib.sha256(rate_salt + (request.client.host if request.client else "unknown").encode()).hexdigest()
            limit_rate("events:" + actor, 600, len(batch.events))
            from app.location import resolve_market
            result = get_store().ingest(batch, resolve_market(request), browser_family(request))
            response.headers["Cache-Control"] = "no-store, private"
            return result
        except (ValueError, OSError, sqlite3.Error) as error:
            raise safe_error(error) from None

    @router.delete("/api/analytics/session")
    async def revoke(request: Request, response: Response):
        try:
            guard(request, collect=False)
            value = RevokeInput.model_validate(await body(request))
            get_store().revoke(value.sessionToken)
            response.headers["Cache-Control"] = "no-store, private"
            return {"status": "revoked"}
        except (ValueError, OSError, sqlite3.Error) as error:
            raise safe_error(error) from None

    @router.get("/api/admin/analytics/report", dependencies=[Depends(require_admin)])
    def admin_report(start: str, end: str, response: Response):
        try:
            response.headers["Cache-Control"] = "no-store, private"
            return get_report(start, end)
        except (ValueError, OverflowError, OSError, sqlite3.Error) as error:
            raise safe_error(error) from None

    @router.get("/api/admin/analytics/export", dependencies=[Depends(require_admin)])
    def csv_report(start: str, end: str):
        try:
            return Response(export_csv(get_report(start, end)), media_type="text/csv", headers={
                "Cache-Control": "no-store, private", "Content-Disposition": f'attachment; filename="styl-analytics-{start}-{end}.csv"',
            })
        except (ValueError, OverflowError, OSError, sqlite3.Error) as error:
            raise safe_error(error) from None

    @router.get("/api/admin/analytics/email-preview", dependencies=[Depends(require_admin)])
    def preview(date: str, response: Response):
        from app.analytics_reports import preview_report
        try:
            response.headers["Cache-Control"] = "no-store, private"
            return preview_report(date)
        except (ValueError, OverflowError, OSError, sqlite3.Error) as error:
            raise safe_error(error) from None

    @router.get("/api/admin/analytics/deliveries", dependencies=[Depends(require_admin)])
    def deliveries(response: Response):
        from app.analytics_reports import delivery_history
        try:
            response.headers["Cache-Control"] = "no-store, private"
            return {"items": delivery_history()}
        except (ValueError, OSError, sqlite3.Error) as error:
            raise safe_error(error) from None

    return router
