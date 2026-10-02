"""Private durable source versions and explicit administrator-reviewed knowledge."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import re
import sqlite3
from threading import Event
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import knowledge_extract as extraction, support


MAX_SOURCES = 1000
MAX_REFS = 500
MAX_PRIVATE_BYTES = 2 * 1024 * 1024 * 1024
IDENTIFIER = re.compile(r"[a-f0-9]{32}")
REFERENCE = re.compile(r"(?:product|accessory):[1-9][0-9]{0,15}")
BLOB_NAME = re.compile(r"[a-f0-9]{64}\.(?:jpg|png|webp|gif|svg|pdf|docx|txt|md|mp4|mov|m4v|webm|mkv|avi)")
PRICE = re.compile(r"[$€£¥]|\b(?:CAD|USD|MSRP|price|pricing|discount|sale price|costs?)\b|售价|价格|折扣|美元|加元", re.I)
PRIVATE = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://|\b(?:api[_ -]?key|password|secret|supplier|"
    r"internal notes?|private|confidential|customer (?:name|address|phone|email))\b|"
    r"(?<!\w)(?:\+?\d[\s().-]*){7,}(?!\w)|供应商|密码|内部|客户地址", re.I,
)
UNSAFE_POLICY = re.compile(r"\b(?:medical|diagnos\w*|treat(?:ment)?|cure|legal|lawsuit|"
                           r"discount\w*|MSRP|prices?|pricing|product costs?|selling costs?)\b|折扣|售价|价格|诊断|治疗|法律建议", re.I)
SERVICE_FEE = re.compile(r"\b(?:shipping|delivery|return(?:s)?|refund|restocking|warranty|repair|support|"
                         r"service|cancellation)\s+(?:(?:handling|processing|service)\s+)?"
                         r"(?:fees?|charges?|costs?|rates?)\b|运费|退货费|维修费|服务费", re.I)
CURRENCY = r"(?:CAD|USD|EUR|GBP|JPY|CNY|加元|美元|欧元|英镑|日元|人民币)"
AMOUNT = rf"(?:{CURRENCY}\s*)?[$€£¥]?\s*\d+(?:,\d{{3}})*(?:\.\d+)?(?:\s*(?:{CURRENCY}|dollars?|euros?|pounds?|yen|yuan|元)\b)?"
SERVICE_MONEY = re.compile(
    rf"(?:{SERVICE_FEE.pattern})\s*(?:(?:is|are|of|:|=|是|为)\s*)?"
    rf"(?:(?:between|from|ranges from)\s+{AMOUNT}\s+(?:and|to)\s+{AMOUNT}|{AMOUNT})"
    rf"|{AMOUNT}\s+(?:(?:for|as)\s+(?:(?:a|the)\s+)?)?(?:{SERVICE_FEE.pattern})", re.I,
)
MONEY_REFERENCE = re.compile(
    PRICE.pattern + r"|\b(?:EUR|GBP|JPY|CNY|dollars?|euros?|pounds?|yen|yuan)\b"
    r"|\b(?:CAD|USD|EUR|GBP|JPY|CNY)(?=\d)|(?<=\d)(?:CAD|USD|EUR|GBP|JPY|CNY)\b", re.I,
)
STATES = ("pending", "queued", "processing", "review", "approved", "rejected", "failed", "stale", "paused")
LIMITS = {"documentBytes": extraction.DOCUMENT_BYTES, "imageBytes": extraction.IMAGE_BYTES,
          "videoBytes": extraction.VIDEO_BYTES, "documentTextCharacters": extraction.MAX_TEXT,
          "docxEntries": extraction.DOCX_ENTRIES, "docxUncompressedBytes": extraction.DOCX_UNCOMPRESSED_BYTES,
          "docxCompressionRatio": extraction.DOCX_COMPRESSION_RATIO}
WARNING = ("Product documents require currently published, priced catalog items. General customer-service documents need no product assignment. "
           "Imported files are private versioned copies. "
           "Extraction sends acknowledged sources to the configured provider for their media type; "
           "all output is draft until an administrator approves it. "
           "Do not upload customer data, credentials or confidential documents.")
logger = logging.getLogger(__name__)


def _no_symlinks(path: Path) -> None:
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Knowledge paths must not contain symlinks.")


def configured_directory() -> Path:
    root = Path(__file__).resolve().parents[2]
    value = Path(os.getenv("STYL_KNOWLEDGE_DIR", str(support.configured_path().parent / "knowledge")))
    if not value.is_absolute():
        raise ValueError("Knowledge storage must use an absolute private directory.")
    _no_symlinks(value)
    value = value.resolve()
    data = Path(os.getenv("STYL_DATA_DIR", str(root / "backend" / "app" / "data")))
    forbidden = (root / "frontend" / "public", root / "frontend" / ".next",
                 root / "backend" / "app" / "uploads", data / "uploads")
    if any(value.is_relative_to(path.resolve()) for path in forbidden):
        raise ValueError("Knowledge storage must be outside public/upload directories.")
    if value.exists() and not value.is_dir():
        raise ValueError("Knowledge storage must be a directory.")
    if value == support.configured_path().parent:
        raise ValueError("Knowledge blobs require a separate directory, not the database directory.")
    return value


@contextmanager
def _connection() -> Generator[sqlite3.Connection, None, None]:
    with support.get_store().connection() as db:
        # executescript commits SupportStore's active transaction; use individual statements.
        db.execute("""CREATE TABLE IF NOT EXISTS knowledge_sources(
            id TEXT PRIMARY KEY, source_key TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            kind TEXT NOT NULL, origin TEXT NOT NULL, item_refs TEXT NOT NULL,
            sourceScope TEXT NOT NULL DEFAULT 'products',
            item_identities TEXT NOT NULL DEFAULT '{}',
            catalog_path TEXT, catalog_refs TEXT NOT NULL, blob_name TEXT, source_hash TEXT,
            revision INTEGER NOT NULL, state TEXT NOT NULL, facts TEXT NOT NULL,
            error TEXT, catalog_error TEXT, retry_at TEXT, attempts INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        columns = {row[1] for row in db.execute("PRAGMA table_info(knowledge_sources)")}
        if "item_identities" not in columns:
            db.execute("ALTER TABLE knowledge_sources ADD COLUMN item_identities TEXT NOT NULL DEFAULT '{}'")
        if "sourceScope" not in columns:
            db.execute("ALTER TABLE knowledge_sources ADD COLUMN sourceScope TEXT NOT NULL DEFAULT 'products'")
        for column in ("extraction_provider", "extraction_model"):
            if column not in columns:
                db.execute(f"ALTER TABLE knowledge_sources ADD COLUMN {column} TEXT")
        db.execute("""CREATE TABLE IF NOT EXISTS knowledge_versions(
            source_id TEXT NOT NULL, revision INTEGER NOT NULL, snapshot TEXT NOT NULL,
            PRIMARY KEY(source_id,revision))""")
        db.execute("""CREATE TABLE IF NOT EXISTS knowledge_uploads(
            name TEXT PRIMARY KEY, source_id TEXT NOT NULL, revision INTEGER NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, retry_at TEXT, error TEXT)""")
        db.execute("""CREATE TABLE IF NOT EXISTS knowledge_provider_cooldowns(
            provider TEXT NOT NULL, model TEXT NOT NULL, retry_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, PRIMARY KEY(provider,model))""")
        db.execute("CREATE INDEX IF NOT EXISTS knowledge_queue ON knowledge_sources(state,updated_at)")
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS knowledge_one_processing
            ON knowledge_sources(state) WHERE state='processing'""")
        yield db


def _current_catalog_locked() -> list[dict]:
    merged = {}
    for currency in ("CAD", "USD"):
        market = {"currency": currency, "countryCode": "CA" if currency == "CAD" else "US",
                  "locationStatus": "located"}
        for item in support._public_catalog_locked(market):
            merged.setdefault(item["ref"], item)
    return list(merged.values())


def _current_catalog() -> list[dict]:
    from app import main
    with main.CATALOG_LOCK:
        return _current_catalog_locked()


@contextmanager
def _catalog_transaction() -> Generator[tuple[sqlite3.Connection, list[dict]], None, None]:
    from app import main
    with _connection() as db:
        with main.CATALOG_LOCK:
            yield db, _current_catalog_locked()


@contextmanager
def catalog_delete_guard(item_ref: str) -> Generator[None, None, None]:
    """Commit knowledge invalidation under the catalog lock, before catalog deletion."""
    from app import main
    if not REFERENCE.fullmatch(item_ref):
        raise ValueError("Invalid catalog deletion reference.")
    db = None
    acquired = False
    try:
        path = support.configured_path()
        if path.exists():
            _no_symlinks(path)
            db = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=5)
            db.row_factory = sqlite3.Row
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='knowledge_sources' AND type='table'").fetchone():
                db.execute("BEGIN IMMEDIATE")
                main.CATALOG_LOCK.acquire()
                acquired = True
                for row in db.execute("SELECT * FROM knowledge_sources").fetchall():
                    if _source_scope(row) == "products" and item_ref in json.loads(row["item_refs"]):
                        identity = {"item_identities": "{}"} if "item_identities" in row.keys() else {}
                        _update(db, row, state="stale", facts="[]", retry_at=None, **identity,
                                error="An assigned catalog item was deleted. Explicitly reassign before extracting or approving.")
                db.commit()
            db.close()
            db = None
        if not acquired:
            main.CATALOG_LOCK.acquire()
            acquired = True
    except (OSError, sqlite3.Error, ValueError, TypeError):
        if db is not None:
            db.close()
        if acquired:
            main.CATALOG_LOCK.release()
        raise HTTPException(503, "Catalog deletion is blocked because private knowledge invalidation could not be saved.",
                            headers={"Cache-Control": "private, no-store"}) from None
    try:
        yield
    finally:
        main.CATALOG_LOCK.release()


def _eligible(catalog: list[dict]) -> dict[str, dict]:
    result = {}
    for item in catalog:
        kind, identifier, price = item.get("type"), item.get("id"), item.get("price")
        if (kind not in ("product", "accessory") or type(identifier) is not int or identifier < 1
                or item.get("publicationStatus") not in (None, "", "published")
                or type(price) not in (int, float) or not math.isfinite(price) or price < 0
                or item.get("currency") not in ("CAD", "USD")):
            continue
        ref = f"{kind}:{identifier}"
        if item.get("ref") != ref or not REFERENCE.fullmatch(ref):
            continue
        result[ref] = item
    return result


def _media(item: dict) -> list[str]:
    photos = item.get("photos", [])
    if not isinstance(photos, list):
        photos = []
    return list(dict.fromkeys(value for value in (item.get("image"), *photos) if isinstance(value, str) and value))


def _identity(item: dict) -> str:
    # Only known public identity/content fields; no price/market or private/future fields.
    fields = ("type", "id", "name", "slug", "category", "modelSku", "shortDescription", "description",
              "features", "specifications", "compatibility", "included", "sellingUnit", "packageQuantity")
    payload = {key: item[key] for key in fields if key in item}
    payload["media"] = _media(item)
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _identities(refs: list[str], catalog: list[dict]) -> str:
    lookup = _eligible(catalog)
    return json.dumps({ref: _identity(lookup[ref]) for ref in refs})


def _same_identity(row: sqlite3.Row | dict, lookup: dict[str, dict], refs: list[str]) -> bool:
    try:
        identities = json.loads(row["item_identities"])
        return all(identities.get(ref) == _identity(lookup[ref]) for ref in refs)
    except (IndexError, KeyError, ValueError, TypeError, AttributeError):
        return False


def _catalog_path(value: str) -> Path:
    from app import main
    if value.startswith("/api/uploads/"):
        relative, root = value[len("/api/uploads/"):], main.UPLOAD_PATH
        if "/" in relative:
            raise ValueError("Nested upload paths are not supported.")
    elif value.startswith("/images/"):
        relative, root = value[len("/images/"):], main.PUBLIC_IMAGE_PATH
    else:
        raise ValueError("External or unsupported catalog media is not fetched. Upload a local source instead.")
    if not relative or any(not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part)
                           or part in (".", "..") for part in relative.split("/")):
        raise ValueError("Unsafe catalog media path.")
    path = root.joinpath(*relative.split("/"))
    _no_symlinks(path)
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Catalog media is missing or unavailable.")
    return path


def _blob_path(name: str) -> Path:
    if not isinstance(name, str) or not BLOB_NAME.fullmatch(name):
        raise ValueError("Invalid private source identity.")
    path = configured_directory() / name
    _no_symlinks(path)
    return path


def _read_file(path: Path, limit: int) -> bytes:
    _no_symlinks(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError("Source is missing or exceeds its size limit.")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Source exceeds its size limit.")
    return data


def _copy_blob(data: bytes, extension: str) -> tuple[str, str]:
    digest = hashlib.sha256(data).hexdigest()
    directory = configured_directory()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = _blob_path(digest + extension)
    if destination.exists():
        if hashlib.sha256(_read_file(destination, extraction.VIDEO_BYTES)).hexdigest() != digest:
            raise ValueError("An existing private source copy failed its integrity check.")
        return destination.name, digest
    total = 0
    for entry in directory.iterdir():
        if entry.is_symlink() or not entry.is_file() or not BLOB_NAME.fullmatch(entry.name):
            raise ValueError("Knowledge storage contains an unexpected file; inspect it before importing.")
        total += entry.stat().st_size
    if total + len(data) > MAX_PRIVATE_BYTES:
        raise HTTPException(413, "Private knowledge storage reached its 2 GiB limit. No source was deleted.")
    # Keep in-progress writes outside the flat blob directory so a concurrent
    # DB-then-blobs archive can include every visible blob without partial files.
    pending = directory.parent / f".knowledge-{uuid4().hex}.pending"
    try:
        descriptor = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _no_symlinks(destination)
        os.replace(pending, destination)
    finally:
        pending.unlink(missing_ok=True)
    return destination.name, digest


def _public(row: sqlite3.Row | dict) -> dict:
    size = 0
    blob_warning = None
    name = row["blob_name"]
    extension = Path(name).suffix.lstrip(".") if isinstance(name, str) and BLOB_NAME.fullmatch(name) else ""
    try:
        path = _blob_path(name)
        if not path.is_file():
            raise ValueError()
        size = path.stat().st_size
    except (OSError, ValueError, TypeError):
        blob_warning = "Private source blob is missing or unavailable. Re-upload before processing or approval."
    issues = [value for value in (row["error"], blob_warning) if value]
    try:
        refs = json.loads(row["item_refs"])
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not REFERENCE.fullmatch(ref) for ref in refs):
            raise ValueError()
    except (TypeError, ValueError):
        refs = []
        issues.append("Stored assignments are invalid; explicitly reassign this source before use.")
    try:
        facts = json.loads(row["facts"])
        if not isinstance(facts, list):
            raise ValueError()
        facts = [Fact.model_validate(fact).model_dump() for fact in facts]
    except (TypeError, ValueError):
        facts = []
        issues.append("Stored facts are invalid; extract and review this source again before use.")
    error = " ".join(issues) or None
    return {
        "id": row["id"], "name": row["name"], "kind": row["kind"], "origin": row["origin"],
        "scope": _source_scope(row), "format": extension or "unknown", "bytes": size,
        "itemRefs": refs, "state": row["state"], "revision": row["revision"],
        "facts": facts, "error": error, "retryAt": row["retry_at"],
        "updatedAt": row["updated_at"], "createdAt": row["created_at"],
        "provider": row["extraction_provider"] if "extraction_provider" in row.keys() else None,
        "model": row["extraction_model"] if "extraction_model" in row.keys() else None,
    }


def _source(db: sqlite3.Connection, identifier: str, revision: int | None = None) -> sqlite3.Row:
    if not IDENTIFIER.fullmatch(identifier):
        raise HTTPException(404, "Knowledge source not found.")
    row = db.execute("SELECT * FROM knowledge_sources WHERE id=?", (identifier,)).fetchone()
    if row is None:
        raise HTTPException(404, "Knowledge source not found.")
    if revision is not None and row["revision"] != revision:
        raise HTTPException(409, "This source changed. Reload before continuing.")
    return row


def _update(db: sqlite3.Connection, row: sqlite3.Row, **values) -> sqlite3.Row:
    db.execute("INSERT OR IGNORE INTO knowledge_versions VALUES(?,?,?)",
               (row["id"], row["revision"], json.dumps(dict(row))))
    values.update(revision=row["revision"] + 1, updated_at=support.now())
    db.execute("UPDATE knowledge_sources SET " + ",".join(key + "=?" for key in values) + " WHERE id=?",
               (*values.values(), row["id"]))
    return _source(db, row["id"])


def _capacity(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM knowledge_sources").fetchone()[0] >= MAX_SOURCES:
        raise HTTPException(413, f"Knowledge has reached its {MAX_SOURCES}-source limit. No sources were deleted.")


def _insert(db: sqlite3.Connection, *, key: str, name: str, kind: str, origin: str, refs: list[str],
            catalog_path: str | None, catalog_refs: list[str], blob: str | None, digest: str | None,
            error: str | None = None, identities: str = "{}", scope: str = "products") -> sqlite3.Row:
    _capacity(db)
    identifier, timestamp = uuid4().hex, support.now()
    db.execute("""INSERT INTO knowledge_sources(
        id,source_key,name,kind,origin,item_refs,item_identities,catalog_path,catalog_refs,blob_name,source_hash,sourceScope,
        revision,state,facts,error,catalog_error,retry_at,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,'[]',?,?,NULL,?,?)""", (
        identifier, key, name, kind, origin, json.dumps(refs), identities, catalog_path, json.dumps(catalog_refs),
        blob, digest, scope, "failed" if error else "pending", error, error if origin == "catalog" else None, timestamp, timestamp,
    ))
    return _source(db, identifier)


def _extraction_routes() -> dict[str, tuple[str, str]]:
    return {kind: extraction.provider_settings(kind) for kind in ("image", "pdf", "docx", "text", "video")}


def _route_fingerprint(routes: dict[str, tuple[str, str]]) -> str:
    encoded = json.dumps([(kind, *routes[kind]) for kind in sorted(routes)],
                         separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _acknowledged_routes(expected: str | None) -> dict[str, tuple[str, str]]:
    routes = _extraction_routes()
    if expected != _route_fingerprint(routes):
        raise HTTPException(409, "Extraction routes changed or were not acknowledged. "
                            "Reload and reconfirm the current providers before extracting.")
    return routes


def _index(db: sqlite3.Connection, catalog: list[dict], warnings: list[str] | None = None) -> dict:
    rows = db.execute("SELECT * FROM knowledge_sources ORDER BY created_at,id").fetchall()
    sources = []
    for row in rows:
        facts, refs = _approved_source(row, catalog)
        sources.append({**_public(row), "approvedCurrent": bool(facts), "currentItemRefs": refs})
    issues = list(warnings or [])
    issues.extend(f"{row['name']}: {row['error']}" for row in sources if row["error"])
    if db.execute("SELECT 1 FROM knowledge_uploads WHERE error IS NOT NULL LIMIT 1").fetchone():
        issues.append("One or more provider files could not be cleaned up. Their private identities are retained; "
                      "after three cleanup attempts, administrator follow-up is required.")
    routes = _extraction_routes()
    for provider, model in dict.fromkeys(routes.values()):
        cooldown = _cooldown(db, provider, model)
        if cooldown:
            issues.append(f"External extraction for {provider}/{model} is paused until {cooldown}. "
                          "Unattempted sources on this route remain queued; no paid upgrade or model fallback is attempted.")
    chat_provider, chat_model = support.provider_settings()
    return {
        "sources": sources,
        "documentCount": sum(row["origin"] == "document" for row in rows),
        "approvedDocumentCount": sum(source["origin"] == "document" and source["approvedCurrent"] for source in sources),
        "items": [{"ref": ref, "name": str(item.get("name", ref)), "type": item["type"], "id": item["id"]}
                  for ref, item in _eligible(catalog).items()],
        "warnings": list(dict.fromkeys([WARNING, *issues])),
        "limits": LIMITS, "provider": routes["image"][0], "routeFingerprint": _route_fingerprint(routes),
        "routes": {**{kind: {"provider": provider, "model": model} for kind, (provider, model) in routes.items()},
                   "chat": {"provider": chat_provider, "model": chat_model}},
    }


def refresh_catalog(catalog: list[dict] | None = None) -> dict:
    catalog = _current_catalog() if catalog is None else catalog
    lookup = _eligible(catalog)
    discovered: dict[str, list[str]] = {}
    for ref, item in lookup.items():
        for media in _media(item):
            discovered.setdefault(media, []).append(ref)
    warnings = []
    with _connection() as db:
        for value, refs in discovered.items():
            refs = sorted(set(refs))
            previous = db.execute("SELECT * FROM knowledge_sources WHERE source_key=?", ("catalog:" + value,)).fetchone()
            blob = digest = error = None
            extension = Path(value).suffix.lower()
            kind = extraction.FORMAT_MIME.get(extension, ("image", ""))[0]
            try:
                if previous is None:
                    _capacity(db)
                path = _catalog_path(value)
                data = _read_file(path, LIMITS[{"image": "imageBytes", "video": "videoBytes"}.get(kind, "documentBytes")])
                kind, _, extension = extraction.identify(data, path.suffix)
                if kind in extraction.DOCUMENT_KINDS:
                    raise ValueError("Catalog documents must be imported and assigned through Documents.")
                blob, digest = _copy_blob(data, extension)
            except (ValueError, OSError, HTTPException) as failure:
                error = str(failure.detail) if isinstance(failure, HTTPException) else str(failure)
                if isinstance(failure, OSError):
                    error = "Catalog media is unavailable."
                if previous is None and isinstance(failure, HTTPException) and failure.status_code == 413:
                    warnings.append(error)
                    continue
            name = "Catalog " + kind + " — " + value.rsplit("/", 1)[-1][:160]
            if previous is None:
                _insert(db, key="catalog:" + value, name=name, kind=kind, origin="catalog", refs=refs,
                        catalog_path=value, catalog_refs=refs, blob=blob, digest=digest, error=error)
            elif (digest is not None and previous["source_hash"] != digest or json.loads(previous["catalog_refs"]) != refs
                  or previous["catalog_error"] != error
                  or previous["state"] == "stale" and previous["error"] == "Catalog source is no longer published or associated."):
                _update(db, previous, blob_name=blob or previous["blob_name"], source_hash=digest or previous["source_hash"],
                        item_refs=json.dumps(refs), catalog_refs=json.dumps(refs), facts="[]",
                        state="failed" if error else "stale", error=error, catalog_error=error,
                        retry_at=None, attempts=0, kind=kind)
        for row in db.execute("SELECT * FROM knowledge_sources").fetchall():
            if _source_scope(row) == "general":
                continue
            if row["origin"] == "catalog":
                missing = row["catalog_path"] not in discovered
            else:
                refs = json.loads(row["item_refs"])
                missing = any(ref not in lookup for ref in refs) or not _same_identity(row, lookup, refs)
            if missing and row["state"] != "stale":
                _update(db, row, state="stale", facts="[]", retry_at=None,
                        error="Catalog source is no longer published or associated.")
        return _index(db, catalog, warnings)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Fact(Input):
    text: str = Field(min_length=1, max_length=extraction.MAX_FACT_TEXT)
    topic: Literal["products", "compatibility", "customer_service"]
    location: str = Field(min_length=1, max_length=240)

    @field_validator("text", "location")
    @classmethod
    def clean_text(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise ValueError("Fact fields must contain readable text.")
        return value.strip()


class EmptyInput(Input):
    pass


class RevisionInput(Input):
    expectedRevision: int = Field(ge=1)


class ExtractInput(RevisionInput):
    acknowledgeExternalProcessing: Literal[True]
    expectedRouteFingerprint: str | None = Field(default=None, max_length=64)


class PendingInput(Input):
    acknowledgeExternalProcessing: Literal[True]
    expectedRouteFingerprint: str | None = Field(default=None, max_length=64)


class AssignmentInput(RevisionInput):
    itemRefs: list[str] = Field(min_length=0, max_length=MAX_REFS)
    scope: Literal["products", "general"] | None = None


class ReviewInput(RevisionInput):
    decision: Literal["approve", "reject"]
    facts: list[Fact] | None = Field(default=None, max_length=extraction.MAX_FACTS)


def _source_scope(row: sqlite3.Row | dict) -> str:
    return row["sourceScope"] if "sourceScope" in row.keys() else "products"


def _refs(refs: object, catalog: list[dict], scope: str = "products") -> list[str]:
    if scope == "general":
        if refs != []:
            raise HTTPException(422, "General customer-service documents must have an empty itemRefs array.")
        return []
    if scope != "products":
        raise HTTPException(422, "Scope must be products or general.")
    lookup = _eligible(catalog)
    if (not isinstance(refs, list) or not 1 <= len(refs) <= MAX_REFS
            or any(not isinstance(ref, str) or not REFERENCE.fullmatch(ref) or ref not in lookup for ref in refs)):
        raise HTTPException(422, "Assign one or more currently published, priced products/accessories.")
    return sorted(set(refs))


def _current(row: sqlite3.Row | dict, catalog: list[dict], *, reference: str | None = None) -> bool:
    try:
        scope = _source_scope(row)
        refs = json.loads(row["item_refs"])
        if not isinstance(refs, list) or any(not isinstance(ref, str) for ref in refs):
            return False
        if scope == "general":
            if (reference is not None or refs or row["origin"] != "document"
                    or row["kind"] not in extraction.DOCUMENT_KINDS
                    or json.loads(row["item_identities"]) != {}):
                return False
        elif scope == "products":
            lookup = _eligible(catalog)
            check_refs = [reference] if reference is not None else refs
            if not refs or any(ref not in refs or ref not in lookup for ref in check_refs):
                return False
        else:
            return False
        blob = _blob_path(row["blob_name"])
        expected_kind = extraction.FORMAT_MIME.get(blob.suffix, (None,))[0]
        if row["kind"] != expected_kind or row["source_hash"] != blob.stem:
            return False
        if hashlib.sha256(_read_file(blob, extraction.VIDEO_BYTES)).hexdigest() != row["source_hash"]:
            return False
        if scope == "general":
            return True
        if row["origin"] == "catalog":
            value = row["catalog_path"]
            if any(value not in _media(lookup[ref]) for ref in check_refs):
                return False
            source = _catalog_path(value)
            return hashlib.sha256(_read_file(source, extraction.VIDEO_BYTES)).hexdigest() == row["source_hash"]
        return row["origin"] == "document" and _same_identity(row, lookup, check_refs)
    except (ValueError, OSError, TypeError, KeyError, IndexError):
        return False


def approved_facts(catalog: list[dict]) -> dict[str, list[dict]]:
    """Read-only, nonblocking under an existing support write transaction/catalog lock."""
    path = support.configured_path()
    if not path.is_file():
        return {}
    result: dict[str, list[dict]] = {}
    _no_symlinks(path)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_sources'").fetchone() is None:
            return {}
        rows = db.execute("SELECT * FROM knowledge_sources WHERE state='approved'").fetchall()
        for row in rows:
            if _source_scope(row) != "products":
                continue
            facts, refs = _approved_source(row, catalog)
            for ref in refs:
                result.setdefault(ref, []).extend(facts)
    return result


def approved_general_facts() -> list[dict]:
    """Read-only approved snapshot; never creates schema, takes catalog locks or calls catalog retrieval."""
    path = support.configured_path()
    if not path.is_file():
        return []
    _no_symlinks(path)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_sources'").fetchone() is None:
            return []
        if "sourceScope" not in {row[1] for row in db.execute("PRAGMA table_info(knowledge_sources)")}:
            return []
        rows = db.execute("SELECT * FROM knowledge_sources WHERE state='approved' AND sourceScope='general' ORDER BY id").fetchall()
        result = []
        for row in rows:
            facts, _ = _approved_source(row, [])
            result.extend(facts)
        return result


def _approved_source(row: sqlite3.Row | dict, catalog: list[dict]) -> tuple[list[dict], list[str]]:
    """Use the same read-only publication eligibility for retrieval and library readiness."""
    try:
        if (row["state"] != "approved" or not isinstance(row["name"], str) or not row["name"].strip()
                or len(row["name"]) > 200 or any(ord(char) < 32 for char in row["name"])
                or PRIVATE.search(row["name"]) or not IDENTIFIER.fullmatch(row["id"])
                or type(row["revision"]) is not int or row["revision"] < 1):
            return [], []
        scope = _source_scope(row)
        facts = _validated_facts(json.loads(row["facts"]), scope)
        refs = json.loads(row["item_refs"])
        if (not isinstance(refs, list) or len(refs) > MAX_REFS
                or any(not isinstance(ref, str) or not REFERENCE.fullmatch(ref) for ref in refs)):
            return [], []
        if scope == "general":
            if not _current(row, []):
                return [], []
            current_refs = []
        else:
            current_refs = [ref for ref in dict.fromkeys(refs) if _current(row, catalog, reference=ref)]
            if not current_refs:
                return [], []
        return [{**fact, "sourceId": row["id"], "sourceName": row["name"],
                 "sourceHash": row["source_hash"], "revision": row["revision"]} for fact in facts], current_refs
    except (ValueError, TypeError, HTTPException, KeyError, IndexError):
        return [], []


def backup_blob_names(connection: sqlite3.Connection) -> set[str]:
    """Read referenced current AND historical blob names from a frozen DB snapshot."""
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('knowledge_sources','knowledge_versions')"
    )}
    names: set[str] = set()

    def include(name: object, digest: object) -> None:
        if name is None and digest is None:
            return
        if not isinstance(name, str) or not BLOB_NAME.fullmatch(name) or digest != name.split(".", 1)[0]:
            raise ValueError("Knowledge backup contains an invalid source-copy reference.")
        names.add(name)

    if "knowledge_sources" in tables:
        for row in connection.execute("SELECT blob_name,source_hash FROM knowledge_sources"):
            include(row[0], row[1])
    if "knowledge_versions" in tables:
        for row in connection.execute("SELECT snapshot FROM knowledge_versions"):
            try:
                snapshot = json.loads(row[0])
                if not isinstance(snapshot, dict):
                    raise ValueError()
                include(snapshot["blob_name"], snapshot["source_hash"])
            except (TypeError, ValueError, KeyError):
                raise ValueError("Knowledge backup contains an invalid historical source-copy reference.") from None
    return names


def _validated_facts(values: list[dict], scope: str = "products") -> list[dict]:
    if not isinstance(values, list) or not 1 <= len(values) <= extraction.MAX_FACTS:
        raise HTTPException(422, "Approval requires 1–2000 reviewed facts.")
    facts = [Fact.model_validate(value).model_dump() for value in values]
    if sum(len(fact["text"]) for fact in facts) > extraction.MAX_TEXT:
        raise HTTPException(422, "The reviewed facts exceed the text limit.")
    allowed = ("customer_service",) if scope == "general" else ("products", "compatibility")
    if scope not in ("products", "general") or any(fact["topic"] not in allowed for fact in facts):
        raise HTTPException(422, "Reviewed fact topics must match the document scope.")
    if scope == "products" and any(PRICE.search(fact["text"]) for fact in facts):
        raise HTTPException(422, "Remove selling prices, MSRP and discounts. Customer prices come only from the current catalog.")
    if scope == "general" and any(UNSAFE_POLICY.search(fact["text"]) or not _service_money_only(fact["text"])
                                  for fact in facts):
        raise HTTPException(422, "Only explicit customer-service policies and service fees are allowed; no product prices, discounts or medical/legal promises.")
    if any(PRIVATE.search(fact["text"]) or PRIVATE.search(fact["location"]) for fact in facts):
        raise HTTPException(422, "Remove private/contact information, links and credentials before approval.")
    return facts


def _service_money_only(text: str) -> bool:
    amounts = [match.span() for match in SERVICE_MONEY.finditer(text)]
    fees = [match.span() for match in SERVICE_FEE.finditer(text)]
    for match in MONEY_REFERENCE.finditer(text):
        spans = fees if re.fullmatch(r"costs?", match.group(), re.I) else amounts
        if not any(start <= match.start() and match.end() <= end for start, end in spans):
            return False
    return True


class _CooldownActive(Exception):
    def __init__(self, retry_at: str):
        self.retry_at = retry_at
        super().__init__("Provider cooldown is active. Unattempted extraction remains queued.")


def _cooldown(db: sqlite3.Connection, provider: str, model: str) -> str | None:
    row = db.execute("SELECT retry_at FROM knowledge_provider_cooldowns WHERE provider=? AND model=?",
                     (provider, model)).fetchone()
    return row[0] if row is not None and row[0] > support.now() else None


def _check_provider_cooldown(provider: str, model: str) -> None:
    with closing(sqlite3.connect(support.configured_path().as_uri() + "?mode=ro", uri=True, timeout=1)) as db:
        db.execute("PRAGMA query_only=ON")
        retry_at = _cooldown(db, provider, model)
        if retry_at:
            raise _CooldownActive(retry_at)


def _pause_provider(provider: str, model: str, retry_at: str) -> None:
    with _connection() as db:
        db.execute("""INSERT INTO knowledge_provider_cooldowns VALUES(?,?,?,?)
            ON CONFLICT(provider,model) DO UPDATE SET
            retry_at=MAX(knowledge_provider_cooldowns.retry_at,excluded.retry_at),updated_at=excluded.updated_at""",
                   (provider, model, retry_at, support.now()))


def _queue(db: sqlite3.Connection, row: sqlite3.Row, catalog: list[dict], route: tuple[str, str]) -> sqlite3.Row:
    if row["state"] in ("queued", "processing"):
        raise HTTPException(409, "This source already has an extraction in progress.")
    if row["retry_at"] and row["retry_at"] > support.now():
        raise HTTPException(429, "The provider retry delay has not elapsed.")
    if not _current(row, catalog):
        raise HTTPException(409, "The source or assignment is no longer current. Sync the catalog or reassign the document.")
    provider, model = route
    return _update(db, row, state="queued", facts="[]", error=None, retry_at=None,
                   extraction_provider=provider, extraction_model=model)


def _track(identifier: str, revision: int, name: str) -> None:
    with _connection() as db:
        db.execute("INSERT OR REPLACE INTO knowledge_uploads(name,source_id,revision) VALUES(?,?,?)",
                   (name, identifier, revision))


def _untrack(name: str) -> None:
    with _connection() as db:
        db.execute("DELETE FROM knowledge_uploads WHERE name=?", (name,))


def recover_interrupted() -> int:
    with _connection() as db:
        rows = db.execute("SELECT * FROM knowledge_sources WHERE state='processing'").fetchall()
        for row in rows:
            _update(db, row, state="paused", retry_at=None,
                    error="Extraction was interrupted. Review the source and explicitly retry; no automatic upload was started.")
        return len(rows)


def _cleanup_one() -> bool:
    if extraction.provider_settings("video")[0] == "mock" or not os.getenv("GEMINI_API_KEY", "").strip():
        return False
    with _connection() as db:
        row = db.execute("""SELECT * FROM knowledge_uploads WHERE attempts<3
            AND (retry_at IS NULL OR retry_at<=?) ORDER BY name LIMIT 1""", (support.now(),)).fetchone()
        if row is None:
            return False
        # Do not remove a file still used by the currently running extractor.
        source = db.execute("SELECT state,revision FROM knowledge_sources WHERE id=?", (row["source_id"],)).fetchone()
        if source and source["state"] == "processing" and source["revision"] == row["revision"]:
            return False
    try:
        extraction.cleanup_file(row["name"])
        _untrack(row["name"])
    except (ValueError, OSError, extraction.httpx.HTTPError):
        with _connection() as db:
            retry = (datetime.now(timezone.utc) + timedelta(seconds=min(3600, 60 * 2 ** row["attempts"]))).isoformat()
            db.execute("UPDATE knowledge_uploads SET attempts=attempts+1,retry_at=?,error=? WHERE name=?",
                       (retry, "Provider file cleanup failed. The provider file identity is retained.", row["name"]))
            source = _source(db, row["source_id"])
            db.execute("UPDATE knowledge_sources SET error=? WHERE id=?",
                       ((source["error"] or "") + " Provider file cleanup failed; administrator follow-up is required.", source["id"]))
    return True


def _claim() -> dict | None:
    with _connection() as db:
        if db.execute("SELECT 1 FROM knowledge_sources WHERE state='processing'").fetchone():
            return None
        rows = db.execute("""SELECT * FROM knowledge_sources WHERE state='queued'
            AND (retry_at IS NULL OR retry_at<=?) ORDER BY updated_at,id""", (support.now(),)).fetchall()
        for row in rows:
            provider, model = extraction.provider_settings(row["kind"])
            if (row["extraction_provider"], row["extraction_model"]) != (provider, model):
                _update(db, row, state="paused", retry_at=None,
                        error="Knowledge provider configuration changed or was not recorded. "
                              "Review the source and explicitly retry; no automatic upload was started.")
                continue
            if _cooldown(db, provider, model):
                continue
            row = _update(db, row, state="processing")
            return {**dict(row), "provider": provider, "model": model}
        return None


def _process(job: dict, interrupted: Event | None = None) -> None:
    from app import main
    facts: list[dict] = []
    error = None
    retry = None
    state = "review"
    attempted = True
    provider_value = job.get("provider", job.get("extraction_provider"))
    model_value = job.get("model", job.get("extraction_model"))
    provider = provider_value if isinstance(provider_value, str) else ""
    model = model_value if isinstance(model_value, str) else ""

    def cancelled() -> bool:
        if interrupted is not None and interrupted.is_set():
            return True
        if extraction.provider_settings(job["kind"]) != (provider, model):
            raise extraction.ExtractionCancelled(
                "Knowledge provider configuration changed. Review the source and explicitly retry.")
        # The extractor calls this immediately before uploads/generation and
        # between PDF/video chunks, not just when the durable job is claimed.
        _check_provider_cooldown(provider, model)
        return False

    try:
        extraction._check_cancelled(cancelled)
        if not _current(job, _current_catalog()):
            raise extraction.ExtractionError("Source or catalog assignment changed. Sync/reassign before extracting.")
        result = extraction.extract(
            _blob_path(job["blob_name"]), job["kind"],
            track=lambda name: _track(job["id"], job["revision"], name), untrack=_untrack,
            cancelled=cancelled, expected_route=(provider, model), scope=_source_scope(job),
        )
        facts = [Fact.model_validate(fact).model_dump() for fact in result.facts]
        if not facts or len(facts) > extraction.MAX_FACTS or sum(len(fact["text"]) for fact in facts) > extraction.MAX_TEXT:
            raise extraction.ExtractionError("Extraction returned an empty or oversized fact set.")
        error = " ".join(result.warnings) or None
    except _CooldownActive as failure:
        state, error, retry, attempted = "queued", str(failure), failure.retry_at, False
    except extraction.ExtractionCancelled as failure:
        state, error = "paused", str(failure)
    except extraction.ExtractionError as failure:
        state, error = ("paused" if failure.retryable else "failed"), str(failure)
        if failure.retryable:
            delay = min(3600, max(failure.retry_after, 60 * 2 ** min(job["attempts"], 6)))
            retry = (datetime.fromisoformat(support.now()) + timedelta(seconds=delay)).isoformat()
            # Persist even if a concurrent reassignment fences this source's result.
            _pause_provider(provider, model, retry)
    except Exception:
        state, error = "failed", "Source extraction failed safely. No drafts were published; retry after checking the source."
    with _connection() as db:
        with main.CATALOG_LOCK:
            try:
                catalog = _current_catalog_locked()
            except (OSError, ValueError, HTTPException):
                catalog = []
            row = _source(db, job["id"])
            if row["revision"] != job["revision"] or row["state"] != "processing":
                return
            if not _current(row, catalog):
                state, facts, error, retry = "stale", [], "Source or catalog assignment changed during extraction.", None
            _update(db, row, state=state, facts=json.dumps(facts), error=error, retry_at=retry,
                    attempts=row["attempts"] + int(attempted))


async def process_one() -> bool:
    if not support.feature_enabled():
        return False
    if await asyncio.to_thread(_cleanup_one):
        return True
    job = await asyncio.to_thread(_claim)
    if job is None:
        return False
    interrupted = Event()
    task = asyncio.create_task(asyncio.to_thread(_process, job, interrupted))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        interrupted.set()
        # Allow the bounded in-flight operation and provider-file cleanup to finish,
        # rather than leaving a detached thread able to publish after shutdown.
        await asyncio.shield(task)
        raise
    return True


async def worker() -> None:
    """Run separately from chat. Cancellation pauses extraction after bounded cleanup."""
    recovered = False
    while True:
        try:
            if not recovered:
                await asyncio.to_thread(recover_interrupted)
                recovered = True
            worked = await process_one()
        except (OSError, sqlite3.Error, ValueError, HTTPException):
            logger.warning("Knowledge worker storage unavailable.")
            recovered = False
            worked = False
        await asyncio.sleep(0.05 if worked else 1)


class PrivateRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        handler = super().get_route_handler()

        async def private_handler(request: Request) -> Response:
            try:
                if not support.feature_enabled():
                    raise HTTPException(404, "Knowledge is available only in the enabled local/test pilot.")
                content_length = request.headers.get("content-length")
                maximum = extraction.VIDEO_BYTES + 1024 * 1024 if request.url.path.endswith("/documents") else 5 * 1024 * 1024
                if content_length and (not content_length.isdigit() or int(content_length) > maximum):
                    raise HTTPException(413, "Knowledge request is too large.")
                # Enforce actual streamed bytes too, before multipart parser spool allocation.
                receive = request._receive
                received = 0

                async def bounded_receive():
                    nonlocal received
                    message = await receive()
                    received += len(message.get("body", b""))
                    if received > maximum:
                        raise HTTPException(413, "Knowledge request is too large.")
                    return message

                request._receive = bounded_receive
                response = await handler(request)
            except RequestValidationError:
                raise HTTPException(422, "Invalid knowledge request. Check fields, revisions and acknowledgement.",
                                    headers={"Cache-Control": "private, no-store"}) from None
            except HTTPException as failure:
                failure.headers = {**(failure.headers or {}), "Cache-Control": "private, no-store"}
                raise
            except (OSError, sqlite3.Error, ValueError):
                raise HTTPException(503, "Knowledge storage is unavailable. No customer facts were published.",
                                    headers={"Cache-Control": "private, no-store"}) from None
            response.headers["Cache-Control"] = "private, no-store"
            return response

        return private_handler


def make_router(require_admin: Callable) -> APIRouter:
    class AdminRoute(PrivateRoute):
        def get_route_handler(self) -> Callable:
            handler = super().get_route_handler()

            async def authenticated_handler(request: Request) -> Response:
                # Authenticate before FastAPI's multipart parser can allocate a spool file.
                try:
                    require_admin(request.headers.get("authorization"))
                except HTTPException as failure:
                    failure.headers = {**(failure.headers or {}), "Cache-Control": "private, no-store"}
                    raise
                return await handler(request)

            return authenticated_handler

    router = APIRouter(prefix="/api/admin/support/knowledge", dependencies=[Depends(require_admin)], route_class=AdminRoute)

    @router.get("")
    def index() -> dict:
        # Listing does not start jobs or external processing.
        catalog = _current_catalog()
        with _connection() as db:
            return _index(db, catalog)

    @router.post("/catalog-sync")
    def sync(body: EmptyInput) -> dict:
        return refresh_catalog()

    @router.post("/documents", status_code=201)
    def document(file: UploadFile = File(...), title: str = Form(...), itemRefs: str = Form(...),
                 scope: Literal["products", "general"] = Form("products")) -> dict:
        catalog = _current_catalog()
        try:
            if not title.strip() or len(title) > 200 or any(ord(char) < 32 for char in title):
                raise HTTPException(422, "Provide a document title of 1–200 readable characters.")
            try:
                refs = _refs(json.loads(itemRefs), catalog, scope)
            except (ValueError, TypeError):
                raise HTTPException(422, "itemRefs must be a JSON array of eligible product/accessory references.") from None
            extension = Path(file.filename or "").suffix.lower()
            kind = extraction.FORMAT_MIME.get(extension, (None, None))[0]
            if kind is None:
                raise HTTPException(415, "Unsupported document format.")
            if scope == "general" and kind not in extraction.DOCUMENT_KINDS:
                raise HTTPException(422, "General customer-service knowledge requires PDF, DOCX, TXT or MD.")
            limit = LIMITS[{"image": "imageBytes", "video": "videoBytes"}.get(kind, "documentBytes")]
            data = file.file.read(limit + 1)
            if len(data) > limit:
                raise HTTPException(413, "File exceeds the allowed size for this format.")
            try:
                kind, _, extension = extraction.identify(data, extension, file.content_type)
                if kind == "pdf":
                    extraction.validate_pdf(data)
            except extraction.ExtractionError as failure:
                raise HTTPException(422, str(failure)) from None
            with _catalog_transaction() as (db, catalog):
                refs = _refs(refs, catalog, scope)
                _capacity(db)
                blob, digest = _copy_blob(data, extension)
                row = _insert(db, key="document:" + uuid4().hex, name=title.strip(), kind=kind, origin="document",
                              refs=refs, catalog_path=None, catalog_refs=[], blob=blob, digest=digest,
                              identities=_identities(refs, catalog), scope=scope)
                return _public(row)
        finally:
            file.file.close()

    @router.get("/sources/{identifier}/file")
    def download(identifier: str) -> FileResponse:
        with _connection() as db:
            row = _source(db, identifier)
            if not row["blob_name"]:
                raise HTTPException(404, "No private source copy is available.")
            path = _blob_path(row["blob_name"])
            if hashlib.sha256(_read_file(path, extraction.VIDEO_BYTES)).hexdigest() != row["source_hash"]:
                raise HTTPException(409, "The private source failed its integrity check.")
            # Always download; never execute uploaded HTML/SVG in the admin origin.
            return FileResponse(path, media_type="application/octet-stream", filename="knowledge-source" + path.suffix,
                                headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox"})

    @router.post("/sources/{identifier}/extract")
    def queue(identifier: str, body: ExtractInput) -> dict:
        with _catalog_transaction() as (db, catalog):
            routes = _acknowledged_routes(body.expectedRouteFingerprint)
            row = _source(db, identifier, body.expectedRevision)
            return _public(_queue(db, row, catalog, routes[row["kind"]]))

    @router.post("/extract-pending")
    def pending(body: PendingInput) -> dict:
        with _catalog_transaction() as (db, catalog):
            routes = _acknowledged_routes(body.expectedRouteFingerprint)
            warnings = []
            for row in db.execute("SELECT * FROM knowledge_sources WHERE state IN ('pending','stale','failed')").fetchall():
                try:
                    _queue(db, row, catalog, routes[row["kind"]])
                except HTTPException as failure:
                    warnings.append(f"{row['name']}: {failure.detail}")
            return _index(db, catalog, warnings)

    @router.put("/sources/{identifier}/assignment")
    def assignment(identifier: str, body: AssignmentInput) -> dict:
        with _catalog_transaction() as (db, catalog):
            row = _source(db, identifier, body.expectedRevision)
            scope = body.scope if body.scope is not None else _source_scope(row)
            if scope == "general" and (row["origin"] != "document" or row["kind"] not in extraction.DOCUMENT_KINDS):
                raise HTTPException(422, "General customer-service knowledge requires an uploaded PDF, DOCX, TXT or MD.")
            refs = _refs(body.itemRefs, catalog, scope)
            if row["origin"] == "catalog" and any(row["catalog_path"] not in _media(_eligible(catalog)[ref]) for ref in refs):
                raise HTTPException(422, "Catalog media can only be assigned to items currently publishing that media.")
            return _public(_update(db, row, item_refs=json.dumps(refs), item_identities=_identities(refs, catalog),
                                   sourceScope=scope, state="stale", facts="[]", error=None, retry_at=None,
                                   extraction_provider=None, extraction_model=None))

    @router.post("/sources/{identifier}/review")
    def review(identifier: str, body: ReviewInput) -> dict:
        with _catalog_transaction() as (db, catalog):
            row = _source(db, identifier, body.expectedRevision)
            if row["state"] not in ("review", "approved", "rejected", "failed"):
                raise HTTPException(409, "Only completed or failed extractions can be reviewed.")
            if not _current(row, catalog):
                raise HTTPException(409, "The source or assignment changed. Sync/reassign and extract again.")
            facts = [fact.model_dump() for fact in body.facts] if body.facts is not None else json.loads(row["facts"])
            if body.decision == "approve":
                if PRIVATE.search(row["name"]):
                    raise HTTPException(422, "The source title contains private/contact information. Use a public-safe title.")
                facts = _validated_facts(facts, _source_scope(row))
            return _public(_update(db, row, state="approved" if body.decision == "approve" else "rejected",
                                   facts=json.dumps(facts), retry_at=None))

    return router
