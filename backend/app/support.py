"""Private guest support records and a single, fenced, durable AI queue."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Generator
from contextlib import asynccontextmanager, contextmanager, suppress
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
from threading import Lock
import time
from typing import Literal
import unicodedata
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from httpx import HTTPError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app import analytics
from app.location import MarketContext


logger = logging.getLogger(__name__)
TOPICS = ("products", "pricing", "compatibility", "customer_service")
NOTICE = (
    "Local testing only. Use synthetic test information. "
    "AI can make mistakes. Ask for human help at any time. Chats are retained as business records."
)
HELP_TEXT = "Your request has been sent to our team."
LEGACY_HELP_TEXT = "Your message is saved. Human help has been requested; AI replies are paused."
AI_ELIGIBLE_STATES = ("ai", "waiting_human", "human")
SCHEMA_VERSION = 4
IDENTIFIER = re.compile(r"[a-f0-9]{32}")
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
rate_lock = Lock()
rate_salt = secrets.token_bytes(32)
rate_windows: dict[str, deque[float]] = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def environment() -> str:
    value = os.getenv("STYL_SUPPORT_ENVIRONMENT", os.getenv("STYL_ANALYTICS_ENVIRONMENT", "local"))
    if value not in ("local", "test", "staging", "production"):
        raise ValueError("Invalid support environment.")
    return value


def feature_enabled() -> bool:
    return analytics.setting_bool("STYL_SUPPORT_ENABLED") and environment() in ("local", "test")


def create_limit() -> int:
    if environment() != "test":
        return 10
    value = os.getenv("STYL_SUPPORT_CREATE_LIMIT", "10")
    if not re.fullmatch(r"[0-9]{1,3}", value) or not 1 <= int(value) <= 200:
        raise ValueError("Test support creation limit must be between 1 and 200.")
    return int(value)


def message_limit() -> int:
    if environment() != "test":
        return 120
    value = os.getenv("STYL_SUPPORT_MESSAGE_LIMIT", "120")
    if not re.fullmatch(r"[0-9]{1,4}", value) or not 1 <= int(value) <= 1000:
        raise ValueError("Test support message limit must be between 1 and 1000.")
    return int(value)


def provider_settings() -> tuple[str, str]:
    from app import support_ai

    provider = os.getenv("STYL_SUPPORT_PROVIDER", "openai")
    model = os.getenv("STYL_SUPPORT_MODEL", support_ai.DEFAULT_MODELS.get(provider, ""))
    if provider not in support_ai.DEFAULT_MODELS or not re.fullmatch(r"[a-zA-Z0-9._-]{1,100}", model):
        raise ValueError("Invalid support provider configuration.")
    if provider == "mock" and environment() not in ("local", "test"):
        raise ValueError("Mock support is local only.")
    return provider, model


def configured_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    path = Path(os.getenv("STYL_SUPPORT_DB", str(analytics.configured_path().with_name("support.sqlite3"))))
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("Support storage must use an absolute private path.")
    path = path.resolve()
    data = Path(os.getenv("STYL_DATA_DIR", str(root / "backend" / "app" / "data")))
    forbidden = (root / "frontend" / "public", root / "frontend" / ".next",
                 root / "backend" / "app" / "uploads", data / "uploads")
    if path.suffix != ".sqlite3" or any(path.is_relative_to(p.resolve()) for p in forbidden):
        raise ValueError("Support storage must be outside public and upload directories.")
    if path == analytics.configured_path():
        raise ValueError("Support records require their own private database.")
    return path


class SupportStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.path.is_symlink():
            raise OSError("Support database must not be a symlink.")
        if not self.path.exists():
            try:
                descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if self.path.is_symlink():
                    raise OSError("Support database must not be a symlink.") from None
            else:
                os.close(descriptor)
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            deadline = time.monotonic() + 5
            while True:
                try:
                    db.execute("PRAGMA journal_mode=WAL")
                    break
                except sqlite3.OperationalError as error:
                    # WAL conversion can return SQLITE_BUSY immediately even with
                    # busy_timeout when another process opens a legacy database.
                    if error.sqlite_errorcode != sqlite3.SQLITE_BUSY or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.01)
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA secure_delete=ON")
            db.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS settings(
                    id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL,
                    allowed_topics TEXT NOT NULL, revision INTEGER NOT NULL,
                    environment TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS conversations(
                    id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL CHECK(state IN ('ai','waiting_human','human','closed')),
                    revision INTEGER NOT NULL, generation INTEGER NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    currency TEXT NOT NULL CHECK(currency IN ('CAD','USD')),
                    needs_human INTEGER NOT NULL, reason TEXT, unlinked_human_reason TEXT);
                CREATE TABLE IF NOT EXISTS messages(
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('customer','assistant','human','system')),
                    text TEXT NOT NULL, created_at TEXT NOT NULL, references_json TEXT NOT NULL,
                    client_message_id TEXT, request_hash TEXT, response_json TEXT,
                    reply_to_id TEXT, needs_human INTEGER NOT NULL DEFAULT 0,
                    human_reason TEXT, answered_by_id TEXT,
                    UNIQUE(conversation_id,role,client_message_id));
                CREATE TABLE IF NOT EXISTS jobs(
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    message_id TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    generation INTEGER NOT NULL, settings_revision INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN
                        ('queued','running','completed','cancelled','failed','interrupted')),
                    payload TEXT NOT NULL, usage_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id,created_at);
                CREATE INDEX IF NOT EXISTS jobs_queue ON jobs(status,created_at);
                CREATE UNIQUE INDEX IF NOT EXISTS one_conversation_job
                    ON jobs(conversation_id) WHERE status IN ('queued','running');
                CREATE UNIQUE INDEX IF NOT EXISTS one_running_job
                    ON jobs(status) WHERE status='running';
            """)
            self._migrate(db)
            db.execute("INSERT OR IGNORE INTO settings VALUES(1,1,?,0,?)",
                       (json.dumps(TOPICS), environment()))
            if db.execute("SELECT environment FROM settings WHERE id=1").fetchone()[0] != environment():
                raise ValueError("Support databases cannot be shared between environments.")
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _migrate(db: sqlite3.Connection) -> None:
        # Schema inspection, ALTERs, backfill and version commit share the writer lock.
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version >= SCHEMA_VERSION:
            return
        if version < 1:
            for table, additions in (
                ("messages", {"reply_to_id": "TEXT", "needs_human": "INTEGER NOT NULL DEFAULT 0",
                              "human_reason": "TEXT", "answered_by_id": "TEXT"}),
                ("conversations", {"unlinked_human_reason": "TEXT"}),
            ):
                columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                for column, definition in additions.items():
                    if column not in columns:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
            # Only durable job links identify legacy questions. Unlinked staff replies
            # cannot prove which question was answered, and must never acquire a quote.
            db.execute("""
                UPDATE messages SET needs_human=1,human_reason=COALESCE(human_reason,
                    CASE WHEN EXISTS(SELECT 1 FROM jobs WHERE message_id=messages.id
                        AND conversation_id=messages.conversation_id AND status='interrupted')
                        THEN 'interrupted' ELSE 'needs_human' END)
                WHERE role='customer' AND answered_by_id IS NULL AND EXISTS(
                    SELECT 1 FROM jobs WHERE message_id=messages.id
                    AND conversation_id=messages.conversation_id AND status IN ('failed','interrupted'))
            """)
            db.execute("""
                UPDATE conversations SET unlinked_human_reason=COALESCE(reason,'needs_human')
                WHERE needs_human=1 AND unlinked_human_reason IS NULL AND NOT EXISTS(
                    SELECT 1 FROM messages WHERE conversation_id=conversations.id
                    AND role='customer' AND needs_human=1)
            """)
        if version < 2:
            db.execute("""
                CREATE TABLE IF NOT EXISTS conversation_contacts(
                    conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
                    name TEXT NOT NULL, email TEXT NOT NULL,
                    revision INTEGER NOT NULL CHECK(revision>=1), updated_at TEXT NOT NULL)
            """)
        if version < 3:
            settings = db.execute("SELECT allowed_topics FROM settings WHERE id=1").fetchone()
            if settings is not None:
                topics = json.loads(settings["allowed_topics"])
                if (not isinstance(topics, list) or not topics or any(not isinstance(topic, str) or topic not in TOPICS for topic in topics)
                        or len(set(topics)) != len(topics)):
                    raise ValueError("Stored support topics are invalid.")
                if set(topics) == {"products", "pricing", "compatibility"}:
                    db.execute("UPDATE settings SET allowed_topics=?,revision=revision+1 WHERE id=1", (json.dumps(TOPICS),))
        if version < 4:
            columns = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
            for column in ("page_context_version", "answer_plan_json"):
                if column not in columns:
                    db.execute(f"ALTER TABLE jobs ADD COLUMN {column} TEXT")
        db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


def get_store() -> SupportStore:
    return SupportStore(configured_path())


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EmptyInput(Input):
    pass


class ContactInput(Input):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr = Field(max_length=254)
    expectedRevision: int = Field(ge=0)

    @field_validator("name", "email", mode="before")
    @classmethod
    def trim_contact(cls, value: object) -> object:
        if isinstance(value, str):
            if any(unicodedata.category(character) in ("Cc", "Cs") for character in value):
                raise ValueError("Contact details cannot contain control characters.")
            return value.strip()
        return value

    @field_validator("email", mode="before")
    @classmethod
    def single_address(cls, value: object) -> object:
        if isinstance(value, str) and (len(value) > 254 or any(
            character in "<>,;" or character.isspace() for character in value.strip()
        )):
            raise ValueError("A single email address is required.")
        return value


class MessageInput(Input):
    clientMessageId: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    text: str = Field(min_length=1, max_length=2000)
    itemRef: str | None = Field(default=None, pattern=r"^(product|accessory):[1-9][0-9]{0,15}$")
    pageContextVersion: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        if not value.strip() or "\x00" in value:
            raise ValueError("A nonempty text message is required.")
        return value


class HumanMessageInput(MessageInput):
    expectedRevision: int = Field(ge=0)
    replyToMessageId: str | None = Field(pattern=r"^[a-f0-9]{32}$")
    expectedAnsweredBy: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")

    @field_validator("itemRef", "pageContextVersion")
    @classmethod
    def no_item_context(cls, value: str | None) -> None:
        if value is not None:
            raise ValueError("Human replies do not accept item context.")
        return None


class SettingsInput(Input):
    enabled: bool
    allowedTopics: list[Literal["products", "pricing", "compatibility", "customer_service"]] = Field(min_length=1, max_length=4)
    expectedRevision: int = Field(ge=0)

    @field_validator("allowedTopics")
    @classmethod
    def unique_topics(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Allowed topics must be unique.")
        return value


class ActionInput(Input):
    action: Literal["close"]
    expectedRevision: int = Field(ge=0)


def _limit(request: Request, action: str, maximum: int, period: int = 3600,
           scope: str | None = None) -> None:
    # The server-observed address exists only in this salted, bounded in-memory window.
    address = request.client.host if request.client else "unknown"
    key = hashlib.sha256(rate_salt + f"{action}:{scope or address}".encode()).hexdigest()
    current = time.monotonic()
    with rate_lock:
        for existing in list(rate_windows):
            window = rate_windows[existing]
            while window and window[0] <= current - 3600:
                window.popleft()
            if not window:
                del rate_windows[existing]
        if key not in rate_windows and len(rate_windows) >= 2048:
            raise HTTPException(429, "Support is busy. Please try again later.", headers={"Retry-After": "60"})
        window = rate_windows.setdefault(key, deque())
        if sum(value > current - period for value in window) >= maximum:
            raise HTTPException(429, "Support request limit reached. Please try later.", headers={"Retry-After": "60"})
        window.append(current)


def _require_feature() -> None:
    if not feature_enabled():
        raise HTTPException(404, "Support is not available.")


def _identifier(identifier: str) -> None:
    if not IDENTIFIER.fullmatch(identifier):
        raise HTTPException(404, "Conversation not found.")


def _conversation(db: sqlite3.Connection, identifier: str, request: Request | None = None) -> sqlite3.Row:
    _identifier(identifier)
    row = db.execute("SELECT * FROM conversations WHERE id=?", (identifier,)).fetchone()
    if request is not None:
        authorization = request.headers.get("authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else ""
        digest = hashlib.sha256(token.encode()).hexdigest()
        if not TOKEN.fullmatch(token) or row is None or not secrets.compare_digest(row["token_hash"], digest):
            raise HTTPException(404, "Conversation not found.")
    if row is None:
        raise HTTPException(404, "Conversation not found.")
    return row


def _attention(db: sqlite3.Connection, row: sqlite3.Row) -> tuple[int, str | None]:
    if row["state"] == "closed":
        return 0, None
    pending = list(db.execute(
        """SELECT human_reason FROM messages WHERE conversation_id=?
           AND role='customer' AND needs_human=1 ORDER BY created_at,rowid""", (row["id"],)
    ))
    return len(pending), (pending[0]["human_reason"] or "needs_human"
                          if pending else row["unlinked_human_reason"])


def _refresh_attention(db: sqlite3.Connection, identifier: str) -> None:
    row = _conversation(db, identifier)
    count, reason = _attention(db, row)
    state = "closed" if row["state"] == "closed" else "waiting_human" if count or reason else "ai"
    db.execute("UPDATE conversations SET state=?,needs_human=?,reason=? WHERE id=?",
               (state, int(bool(count or reason)), reason, identifier))


def _mark_question(db: sqlite3.Connection, identifier: str, message_id: str, reason: str) -> None:
    db.execute(
        """UPDATE messages SET needs_human=1,human_reason=COALESCE(human_reason,?),answered_by_id=NULL
           WHERE id=? AND conversation_id=? AND role='customer'""", (reason, message_id, identifier),
    )
    _refresh_attention(db, identifier)


def _contact(db: sqlite3.Connection, identifier: str) -> dict[str, object] | None:
    row = db.execute("SELECT * FROM conversation_contacts WHERE conversation_id=?", (identifier,)).fetchone()
    return ({"name": row["name"], "email": row["email"], "revision": row["revision"],
             "updatedAt": row["updated_at"]} if row else None)


def _snapshot(db: sqlite3.Connection, identifier: str) -> dict[str, object]:
    row = _conversation(db, identifier)
    count, reason = _attention(db, row)
    return {
        "id": row["id"], "state": row["state"], "revision": row["revision"],
        "createdAt": row["created_at"], "updatedAt": row["updated_at"], "currency": row["currency"],
        "needsHuman": bool(count or reason), "needsHumanQuestions": count, "reason": reason,
        "contact": _contact(db, identifier),
        "processing": bool(db.execute(
            "SELECT 1 FROM jobs WHERE conversation_id=? AND status IN ('queued','running')", (identifier,)
        ).fetchone()),
        "messages": [{
            "id": message["id"], "role": message["role"], "text": message["text"],
            "createdAt": message["created_at"], "references": json.loads(message["references_json"]),
            "needsHuman": bool(message["needs_human"]) if message["role"] == "customer" else False,
            "humanReason": message["human_reason"] if message["role"] == "customer" else None,
            "answeredBy": message["answered_by_id"],
            "replyTo": {"id": message["target_id"], "text": message["target_text"]}
            if message["target_id"] else None,
        } for message in db.execute(
            """SELECT message.*,target.id AS target_id,target.text AS target_text
               FROM messages AS message LEFT JOIN messages AS target
               ON target.id=message.reply_to_id AND target.conversation_id=message.conversation_id
               AND target.role='customer' WHERE message.conversation_id=?
               ORDER BY message.created_at,message.rowid""", (identifier,)
        )],
    }


def _public_conversation(snapshot: dict[str, object]) -> dict[str, object]:
    # Apply this to saved receipts too, without rewriting diagnostic history.
    return {
        **snapshot, "reason": None,
        "messages": [
            {**message, "humanReason": None,
             "text": HELP_TEXT if message["role"] == "system" and message["text"] == LEGACY_HELP_TEXT
             else message["text"]}
            for message in snapshot["messages"]
        ],
    }


def _settings(db: sqlite3.Connection) -> sqlite3.Row:
    return db.execute("SELECT * FROM settings WHERE id=1").fetchone()


def _config(db: sqlite3.Connection) -> dict[str, object]:
    provider, model = provider_settings()
    settings = _settings(db)
    from app import support_ai
    return {
        "enabled": bool(settings["enabled"]), "allowedTopics": json.loads(settings["allowed_topics"]),
        "revision": settings["revision"], "provider": provider, "model": model,
        "configured": support_ai.configured(provider, model),
        "environment": environment(), "localTestingOnly": True,
    }


def _check_revision(row: sqlite3.Row, expected: int) -> None:
    if row["revision"] != expected:
        raise HTTPException(409, "This record changed. Refresh before trying again.")


def _append(db: sqlite3.Connection, identifier: str, role: str, text: str,
            references: list[dict[str, object]] | None = None,
            client_id: str | None = None, request_hash: str | None = None,
            reply_to_id: str | None = None) -> str:
    message_id = uuid4().hex
    db.execute("""INSERT INTO messages(id,conversation_id,role,text,created_at,references_json,
                  client_message_id,request_hash,reply_to_id) VALUES(?,?,?,?,?,?,?,?,?)""",
               (message_id, identifier, role, text, now(), json.dumps(references or []),
                client_id, request_hash, reply_to_id))
    return message_id


def _fence(db: sqlite3.Connection, identifier: str, state: str, reason: str | None,
           needs_human: bool = True) -> None:
    timestamp = now()
    if needs_human and reason:
        for job in db.execute(
            "SELECT message_id FROM jobs WHERE conversation_id=? AND status IN ('queued','running')",
            (identifier,),
        ).fetchall():
            _mark_question(db, identifier, job["message_id"], reason)
    db.execute(
        """UPDATE conversations SET state=?,reason=?,needs_human=?,generation=generation+1,
           revision=revision+1,updated_at=? WHERE id=?""",
        (state, reason, int(needs_human), timestamp, identifier),
    )
    db.execute("UPDATE jobs SET status='cancelled',updated_at=? WHERE conversation_id=? AND status IN ('queued','running')",
               (timestamp, identifier))
    _refresh_attention(db, identifier)


def _fingerprint(body: BaseModel) -> str:
    # Admission preconditions are not the identity of a saved reply.
    payload = body.model_dump(exclude={"expectedRevision", "expectedAnsweredBy"})
    if payload.get("pageContextVersion") is None:
        payload.pop("pageContextVersion", None)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _receipt(db: sqlite3.Connection, identifier: str, role: str, body: MessageInput) -> dict[str, object] | None:
    previous = db.execute(
        "SELECT request_hash,response_json FROM messages WHERE conversation_id=? AND role=? AND client_message_id=?",
        (identifier, role, body.clientMessageId),
    ).fetchone()
    if previous is None:
        return None
    if previous["request_hash"] != _fingerprint(body):
        raise HTTPException(409, "This message ID was already used for different content.")
    return {**json.loads(previous["response_json"]), "contact": _contact(db, identifier)}


def _save_receipt(db: sqlite3.Connection, message_id: str, snapshot: dict[str, object]) -> None:
    # Contact details live only in their own table, never in message history/receipts.
    receipt = {key: value for key, value in snapshot.items() if key != "contact"}
    db.execute("UPDATE messages SET response_json=? WHERE id=?", (json.dumps(receipt), message_id))


def _public_catalog_locked(market: MarketContext) -> list[dict[str, object]]:
    from app import knowledge, main
    result = []
    for kind, items in (("product", main.load_products()), ("accessory", main.load_accessories())):
        for item in items:
            if not main.visible_in_market(item, market):
                continue
            public = main.public_catalog_item(item, market)
            identifier = public["id"]
            url = (f"/products/{quote(str(public['slug']), safe='')}" if kind == "product"
                   else f"/accessories/{identifier}")
            result.append({**public, "ref": f"{kind}:{identifier}", "type": kind, "id": identifier, "url": url})
    approved = knowledge.approved_facts(result)
    for item in result:
        if facts := approved.get(str(item["ref"])):
            item["approvedKnowledge"] = facts
    return result


def public_catalog(market: MarketContext) -> list[dict[str, object]]:
    from app import main
    with main.CATALOG_LOCK:
        return _public_catalog_locked(market)


def _customer_message(identifier: str, body: MessageInput, request: Request, response: Response) -> dict[str, object]:
    from app import main, support_ai
    effective_item_ref = None if support_ai.is_service_only_question(body.text) else body.itemRef
    store = get_store()
    with store.connection() as db:
        _conversation(db, identifier, request)
        receipt = _receipt(db, identifier, "customer", body)
        if receipt is not None:
            return _public_conversation(receipt)
    market = main.request_market(request, response)
    try:
        catalog = public_catalog(market)
        catalog_available = True
    except (OSError, ValueError, KeyError, TypeError, HTTPException):
        catalog, catalog_available = [], False
    with store.connection() as db:
        row = _conversation(db, identifier, request)
        receipt = _receipt(db, identifier, "customer", body)
        if receipt is not None:
            return _public_conversation(receipt)
        if row["state"] == "closed":
            raise HTTPException(409, "This conversation is closed. Start a new conversation.")
        if db.execute("SELECT 1 FROM jobs WHERE conversation_id=? AND status IN ('queued','running')", (identifier,)).fetchone():
            raise HTTPException(409, "A reply is still processing. Wait or ask for human help.")
        _limit(request, "message", message_limit())
        settings = _settings(db)
        first_question = not db.execute(
            "SELECT 1 FROM messages WHERE conversation_id=? AND role='customer'", (identifier,)
        ).fetchone()
        message_id = _append(db, identifier, "customer", body.text, client_id=body.clientMessageId,
                             request_hash=_fingerprint(body))
        if first_question and row["unlinked_human_reason"]:
            _mark_question(db, identifier, message_id, row["unlinked_human_reason"])
            db.execute("UPDATE conversations SET unlinked_human_reason=NULL WHERE id=?", (identifier,))
        db.execute(
            "UPDATE conversations SET currency=?,revision=revision+1,generation=generation+1,updated_at=? WHERE id=?",
            (market["currency"], now(), identifier),
        )
        reason = None
        if not settings["enabled"]:
            reason = "ai_disabled"
        elif not catalog_available:
            reason = "catalog_unavailable"
        elif (effective_item_ref is not None and not any(item["ref"] == effective_item_ref for item in catalog)
              and not support_ai.resolve_catalog_items(
                  support_ai.public_evidence(catalog, json.loads(settings["allowed_topics"])), body.text)):
            reason = "missing_information"
        if reason:
            _mark_question(db, identifier, message_id, reason)
            _append(db, identifier, "system", HELP_TEXT, reply_to_id=message_id)
        else:
            provider, model = provider_settings()
            history = list(db.execute(
                """SELECT message.role,message.text,message.references_json,target.text AS question_text
                   FROM messages AS message LEFT JOIN messages AS target
                   ON target.id=message.reply_to_id AND target.conversation_id=message.conversation_id
                   AND target.role='customer' WHERE message.conversation_id=? AND message.role!='system'
                   ORDER BY message.created_at DESC,message.rowid DESC LIMIT 20""", (identifier,)
            ))
            payload = {
                "messages": [_history_context(message) for message in reversed(history)],
                "catalog": catalog, "allowed_topics": json.loads(settings["allowed_topics"]),
                "provider": provider, "model": model, "item_ref": effective_item_ref,
                "pending_context": _pending_plan(db, identifier, body.pageContextVersion, message_id),
            }
            timestamp = now()
            db.execute(
                """INSERT INTO jobs(id,conversation_id,message_id,generation,settings_revision,status,payload,created_at,updated_at,page_context_version)
                   VALUES(?,?,?,?,?,'queued',?,?,?,?)""",
                (uuid4().hex, identifier, message_id, row["generation"] + 1, settings["revision"],
                 json.dumps(payload, ensure_ascii=False), timestamp, timestamp, body.pageContextVersion),
            )
        _refresh_attention(db, identifier)
        snapshot = _public_conversation(_snapshot(db, identifier))
        _save_receipt(db, message_id, snapshot)
        return snapshot


def _history_context(message: sqlite3.Row) -> dict[str, str]:
    value = {
        "role": "user" if message["role"] == "customer" else "model",
        "text": (f"Reply to earlier question: {message['question_text']}\nTeam reply: {message['text']}"
                 if message["role"] == "human" and message["question_text"] is not None else message["text"]),
    }
    if message["role"] == "assistant":
        references = json.loads(message["references_json"])
        if not isinstance(references, list):
            raise ValueError("Stored answer references are invalid.")
        if references:
            if any(not isinstance(reference, dict) or reference.get("type") not in ("product", "accessory")
                   or type(reference.get("id")) is not int or reference["id"] < 1 for reference in references):
                raise ValueError("Stored answer references are invalid.")
            value["catalogRefs"] = json.dumps([f"{reference['type']}:{reference['id']}" for reference in references])
    return value


def _pending_plan(db: sqlite3.Connection, identifier: str, page_version: str | None,
                  current_message_id: str | None = None) -> dict | None:
    previous = db.execute(
        "SELECT * FROM jobs WHERE conversation_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (identifier,)
    ).fetchone()
    if previous is None or previous["status"] != "completed" or not previous["answer_plan_json"]:
        return None
    if previous["page_context_version"] != page_version:
        return None
    latest_question = db.execute(
        """SELECT id FROM messages WHERE conversation_id=? AND role='customer' AND (? IS NULL OR id!=?)
           ORDER BY created_at DESC,rowid DESC LIMIT 1""", (identifier, current_message_id, current_message_id)
    ).fetchone()
    if latest_question is None or latest_question["id"] != previous["message_id"]:
        return None
    age = (datetime.fromisoformat(now()) - datetime.fromisoformat(previous["updated_at"])).total_seconds()
    if not 0 <= age <= 1800:
        return None
    if db.execute("SELECT 1 FROM messages WHERE reply_to_id=? AND role='human'", (previous["message_id"],)).fetchone():
        return None
    plan = json.loads(previous["answer_plan_json"])
    if not isinstance(plan, dict):
        raise ValueError("Stored answer plan is invalid.")
    return plan


class PrivateRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        handler = super().get_route_handler()

        async def private_handler(request: Request) -> Response:
            try:
                if request.method in ("POST", "PUT"):
                    data = bytearray()
                    async for chunk in request.stream():
                        data.extend(chunk)
                        if len(data) > 16384:
                            raise HTTPException(413, "Support request is too large.")
                    request._body = bytes(data)
                response = await handler(request)
            except RequestValidationError:
                raise HTTPException(422, "Invalid support request. Check the fields and message length.",
                                    headers={"Cache-Control": "private, no-store"}) from None
            except HTTPException as error:
                error.headers = {**(error.headers or {}), "Cache-Control": "private, no-store"}
                raise
            except (OSError, sqlite3.Error, ValueError) as error:
                logger.warning("Support operation unavailable (%s).", type(error).__name__)
                raise HTTPException(503, "Support is temporarily unavailable. Your unsent text can be retried.",
                                    headers={"Cache-Control": "private, no-store"}) from None
            response.headers["Cache-Control"] = "private, no-store"
            return response

        return private_handler


def make_router(require_admin: Callable) -> APIRouter:
    router = APIRouter(route_class=PrivateRoute)
    admin = [Depends(require_admin)]

    @router.get("/api/support/config")
    def config() -> dict[str, object]:
        provider, model = provider_settings()
        result: dict[str, object] = {
            "enabled": feature_enabled(), "aiEnabled": False, "environment": environment(),
            "provider": provider, "model": model, "allowedTopics": list(TOPICS),
            "localTestingOnly": True, "notice": NOTICE,
        }
        if feature_enabled():
            with get_store().connection() as db:
                settings = _settings(db)
                result.update(aiEnabled=bool(settings["enabled"]), allowedTopics=json.loads(settings["allowed_topics"]))
        return result

    @router.post("/api/support/conversations", status_code=201)
    def create(body: EmptyInput, request: Request, response: Response) -> dict[str, object]:
        _require_feature()
        _limit(request, "create", create_limit())
        from app import main
        market = main.request_market(request, response)
        token, identifier, timestamp = secrets.token_urlsafe(32), uuid4().hex, now()
        with get_store().connection() as db:
            # Bound storage/provider abuse across rotating source addresses too.
            recent = datetime.fromtimestamp(time.time() - 3600, timezone.utc).isoformat(timespec="microseconds")
            if db.execute("SELECT COUNT(*) FROM conversations WHERE created_at>?", (recent,)).fetchone()[0] >= 200:
                raise HTTPException(429, "Support is busy. Please try later.", headers={"Retry-After": "3600"})
            ai = bool(_settings(db)["enabled"])
            db.execute("""INSERT INTO conversations(id,token_hash,state,revision,generation,created_at,updated_at,
                          currency,needs_human,reason,unlinked_human_reason) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                       (identifier, hashlib.sha256(token.encode()).hexdigest(), "ai" if ai else "waiting_human",
                        0, 0, timestamp, timestamp, market["currency"], int(not ai),
                        None if ai else "ai_disabled", None if ai else "ai_disabled"))
            return {"conversation": _public_conversation(_snapshot(db, identifier)), "token": token}

    @router.get("/api/support/conversations/{identifier}")
    def get_conversation(identifier: str, request: Request) -> dict[str, object]:
        _require_feature()
        _identifier(identifier)
        with get_store().connection() as db:
            _conversation(db, identifier, request)
            return _public_conversation(_snapshot(db, identifier))

    @router.post("/api/support/conversations/{identifier}/messages")
    def customer_message(identifier: str, body: MessageInput, request: Request, response: Response) -> dict[str, object]:
        _require_feature()
        _identifier(identifier)
        return _customer_message(identifier, body, request, response)

    @router.put("/api/support/conversations/{identifier}/contact")
    def save_contact(identifier: str, body: ContactInput, request: Request) -> dict[str, object]:
        _require_feature()
        _identifier(identifier)
        from app import main
        origin = request.headers.get("origin")
        if origin is not None and origin not in (str(request.base_url).rstrip("/"), *main.ALLOWED_ORIGINS):
            raise HTTPException(403, "This request is not allowed.")
        with get_store().connection() as db:
            row = _conversation(db, identifier, request)
            if row["state"] == "closed":
                raise HTTPException(409, "This conversation is closed.")
            contact = _contact(db, identifier)
            revision = contact["revision"] if contact else 0
            unchanged = contact and contact["name"] == body.name and contact["email"] == body.email
            if unchanged and body.expectedRevision in (revision, revision - 1):
                return _public_conversation(_snapshot(db, identifier))
            if body.expectedRevision != revision:
                raise HTTPException(409, "Contact details changed. Refresh before trying again.")
            _limit(request, "contact", 30)
            _limit(request, "contact-conversation", 10, scope=identifier)
            _limit(request, "contact-global", 200, scope="global")
            timestamp = now()
            db.execute("""
                INSERT INTO conversation_contacts(conversation_id,name,email,revision,updated_at)
                VALUES(?,?,?,?,?) ON CONFLICT(conversation_id) DO UPDATE SET
                name=excluded.name,email=excluded.email,revision=excluded.revision,updated_at=excluded.updated_at
            """, (identifier, body.name, body.email, revision + 1, timestamp))
            db.execute("UPDATE conversations SET revision=revision+1,updated_at=? WHERE id=?",
                       (timestamp, identifier))
            return _public_conversation(_snapshot(db, identifier))

    @router.post("/api/support/conversations/{identifier}/handoff")
    def handoff(identifier: str, body: EmptyInput, request: Request) -> dict[str, object]:
        _require_feature()
        _identifier(identifier)
        with get_store().connection() as db:
            row = _conversation(db, identifier, request)
            if row["state"] == "closed":
                raise HTTPException(409, "This conversation is closed.")
            question = db.execute(
                """SELECT * FROM messages WHERE conversation_id=? AND role='customer'
                   ORDER BY created_at DESC,rowid DESC LIMIT 1""", (identifier,)
            ).fetchone()
            if question is not None and not question["needs_human"]:
                _mark_question(db, identifier, question["id"], "customer_request")
            elif question is None and not row["unlinked_human_reason"]:
                db.execute("UPDATE conversations SET unlinked_human_reason='customer_request' WHERE id=?", (identifier,))
            else:
                return _public_conversation(_snapshot(db, identifier))
            db.execute("UPDATE conversations SET revision=revision+1,updated_at=? WHERE id=?", (now(), identifier))
            _append(db, identifier, "system", HELP_TEXT, reply_to_id=question["id"] if question else None)
            _refresh_attention(db, identifier)
            return _public_conversation(_snapshot(db, identifier))

    @router.get("/api/admin/support/config", dependencies=admin)
    def admin_config() -> dict[str, object]:
        with get_store().connection() as db:
            return _config(db)

    @router.put("/api/admin/support/config", dependencies=admin)
    def save_config(body: SettingsInput) -> dict[str, object]:
        with get_store().connection() as db:
            _check_revision(_settings(db), body.expectedRevision)
            db.execute("UPDATE settings SET enabled=?,allowed_topics=?,revision=revision+1 WHERE id=1",
                       (int(body.enabled), json.dumps(body.allowedTopics)))
            affected = list(db.execute(
                "SELECT DISTINCT conversation_id FROM jobs WHERE status IN ('queued','running')"
            ))
            for row in affected:
                _fence(db, row["conversation_id"], "waiting_human", "settings_changed" if body.enabled else "ai_disabled")
                _append(db, row["conversation_id"], "system", HELP_TEXT)
            return _config(db)

    @router.get("/api/admin/support/conversations", dependencies=admin)
    def inbox() -> dict[str, object]:
        with get_store().connection() as db:
            items = []
            for row in db.execute("SELECT * FROM conversations ORDER BY updated_at DESC,id"):
                count, reason = _attention(db, row)
                last = db.execute(
                    "SELECT text FROM messages WHERE conversation_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1",
                    (row["id"],),
                ).fetchone()
                contact = _contact(db, row["id"])
                items.append({
                    "id": row["id"], "state": row["state"], "currency": row["currency"],
                    "revision": row["revision"], "createdAt": row["created_at"], "updatedAt": row["updated_at"],
                    "lastMessage": last["text"] if last else "", "needsHuman": bool(count or reason),
                    "needsHumanQuestions": count, "reason": reason, "guestLabel": "Guest " + row["id"][:8],
                    "contactName": contact["name"] if contact else None,
                    "messageCount": db.execute("SELECT COUNT(*) FROM messages WHERE conversation_id=?", (row["id"],)).fetchone()[0],
                })
            return {"items": items, "needsHumanCount": sum(bool(item["needsHuman"]) for item in items)}

    @router.get("/api/admin/support/conversations/{identifier}", dependencies=admin)
    def admin_conversation(identifier: str) -> dict[str, object]:
        _identifier(identifier)
        with get_store().connection() as db:
            return _snapshot(db, identifier)

    @router.post("/api/admin/support/conversations/{identifier}/action", dependencies=admin)
    def action(identifier: str, body: ActionInput) -> dict[str, object]:
        _identifier(identifier)
        with get_store().connection() as db:
            row = _conversation(db, identifier)
            _check_revision(row, body.expectedRevision)
            if row["state"] == "closed":
                raise HTTPException(409, "This conversation is closed.")
            _fence(db, identifier, "closed", None, False)
            return _snapshot(db, identifier)

    @router.post("/api/admin/support/conversations/{identifier}/messages", dependencies=admin)
    def human_message(identifier: str, body: HumanMessageInput) -> dict[str, object]:
        _identifier(identifier)
        with get_store().connection() as db:
            row = _conversation(db, identifier)
            receipt = _receipt(db, identifier, "human", body)
            if receipt is not None:
                return receipt
            if row["state"] == "closed":
                raise HTTPException(409, "This conversation is closed.")
            if body.expectedRevision > row["revision"]:
                raise HTTPException(409, "This record changed. Refresh before trying again.")
            if body.replyToMessageId is None:
                if db.execute("SELECT 1 FROM messages WHERE conversation_id=? AND role='customer'",
                              (identifier,)).fetchone():
                    raise HTTPException(422, "Select the customer question to reply to.")
                _check_revision(row, body.expectedRevision)
                if body.expectedAnsweredBy is not None:
                    raise HTTPException(422, "A greeting cannot reference a previous answer.")
            else:
                target = db.execute(
                    "SELECT answered_by_id FROM messages WHERE id=? AND conversation_id=? AND role='customer'",
                    (body.replyToMessageId, identifier),
                ).fetchone()
                if target is None:
                    raise HTTPException(404, "Customer question not found.")
                if target["answered_by_id"] != body.expectedAnsweredBy:
                    raise HTTPException(409, "This question received another answer. Refresh before replying.")
            message_id = _append(db, identifier, "human", body.text, client_id=body.clientMessageId,
                                 request_hash=_fingerprint(body), reply_to_id=body.replyToMessageId)
            if body.replyToMessageId is not None:
                db.execute("""UPDATE messages SET needs_human=0,human_reason=NULL,answered_by_id=?
                              WHERE id=? AND conversation_id=?""",
                           (message_id, body.replyToMessageId, identifier))
                db.execute("""UPDATE jobs SET status='cancelled',updated_at=? WHERE conversation_id=?
                              AND message_id=? AND status IN ('queued','running')""",
                           (now(), identifier, body.replyToMessageId))
            db.execute("UPDATE conversations SET revision=revision+1,updated_at=?,unlinked_human_reason=NULL WHERE id=?",
                       (now(), identifier))
            _refresh_attention(db, identifier)
            snapshot = _snapshot(db, identifier)
            _save_receipt(db, message_id, snapshot)
            return snapshot

    return router


def recover_interrupted(store: SupportStore | None = None) -> int:
    store = store or get_store()
    with store.connection() as db:
        jobs = list(db.execute("SELECT * FROM jobs WHERE status='running'"))
        for job in jobs:
            row = _conversation(db, job["conversation_id"])
            db.execute("UPDATE jobs SET status='interrupted',updated_at=? WHERE id=?", (now(), job["id"]))
            if row["state"] in AI_ELIGIBLE_STATES and row["generation"] == job["generation"]:
                _mark_question(db, row["id"], job["message_id"], "interrupted")
                db.execute("UPDATE conversations SET revision=revision+1,updated_at=? WHERE id=?", (now(), row["id"]))
                _append(db, row["id"], "system", HELP_TEXT, reply_to_id=job["message_id"])
        return len(jobs)


def _claim(store: SupportStore) -> sqlite3.Row | bool:
    with store.connection() as db:
        if db.execute("SELECT 1 FROM jobs WHERE status='running'").fetchone():
            return False
        job = db.execute(
            """SELECT jobs.*,conversations.currency FROM jobs
               JOIN conversations ON conversations.id=jobs.conversation_id
               WHERE jobs.status='queued' ORDER BY jobs.created_at,jobs.rowid LIMIT 1"""
        ).fetchone()
        if job is None:
            return False
        row, settings = _conversation(db, job["conversation_id"]), _settings(db)
        if row["state"] not in AI_ELIGIBLE_STATES or row["generation"] != job["generation"]:
            db.execute("UPDATE jobs SET status='cancelled',updated_at=? WHERE id=?", (now(), job["id"]))
            return True
        if not settings["enabled"] or settings["revision"] != job["settings_revision"]:
            _fence(db, row["id"], "waiting_human", "ai_disabled" if not settings["enabled"] else "settings_changed")
            return True
        db.execute("UPDATE jobs SET status='running',updated_at=? WHERE id=?", (now(), job["id"]))
        return job


def _job_market(job: sqlite3.Row) -> MarketContext:
    return {"countryCode": None, "currency": job["currency"], "locationStatus": "unknown"}


def _save_current_payload(store: SupportStore, job: sqlite3.Row, payload: dict[str, object]) -> bool:
    with store.connection() as db:
        current = db.execute("SELECT status FROM jobs WHERE id=?", (job["id"],)).fetchone()
        if current is None or current["status"] != "running":
            return False
        row, settings = _conversation(db, job["conversation_id"]), _settings(db)
        if row["state"] not in AI_ELIGIBLE_STATES or row["generation"] != job["generation"]:
            db.execute("UPDATE jobs SET status='cancelled',updated_at=? WHERE id=?", (now(), job["id"]))
            return False
        if (not settings["enabled"] or settings["revision"] != job["settings_revision"] or not feature_enabled()):
            _fence(db, row["id"], "waiting_human", "settings_changed" if settings["enabled"] else "ai_disabled")
            return False
        db.execute("UPDATE jobs SET payload=?,updated_at=? WHERE id=?",
                   (json.dumps(payload, ensure_ascii=False), now(), job["id"]))
        return True


def _publish(store: SupportStore, job: sqlite3.Row, failure: str | None, text: str,
             references: list[dict[str, object]], usage: dict[str, int],
             evidence: list[dict[str, object]], general_evidence: list[dict[str, object]] | None = None,
             knowledge_sources: tuple[str, ...] = (), answer_plan: dict | None = None,
             needs_human: bool = False, attention_reason: str | None = None) -> None:
    from app import knowledge, main, support_ai
    with store.connection() as db:
        current = db.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()
        if current is None or current["status"] != "running":
            return
        row, settings = _conversation(db, job["conversation_id"]), _settings(db)
        if row["state"] not in AI_ELIGIBLE_STATES or row["generation"] != job["generation"]:
            db.execute("UPDATE jobs SET status='cancelled',updated_at=? WHERE id=?", (now(), job["id"]))
            return
        if not settings["enabled"] or settings["revision"] != job["settings_revision"] or not feature_enabled():
            _fence(db, row["id"], "waiting_human", "settings_changed" if settings["enabled"] else "ai_disabled")
            return
        # Acquire the database first so a busy support store cannot monopolize the catalog.
        # Catalog writers share this lock through validation and the publication commit.
        with main.CATALOG_LOCK:
            if failure is None:
                try:
                    current_catalog = {item["ref"]: item for item in _public_catalog_locked(_job_market(job))}
                    previous = {item["ref"]: item for item in evidence}
                    if answer_plan is None and any(current_catalog.get(f"{ref['type']}:{ref['id']}") !=
                           previous.get(f"{ref['type']}:{ref['id']}") for ref in references):
                        failure = "catalog_changed"
                    current_general = knowledge.approved_general_facts() if knowledge_sources or answer_plan else []
                    if answer_plan is not None:
                        planned_answer = support_ai.Answer(
                            text=text, references=tuple(f"{ref['type']}:{ref['id']}" for ref in references),
                            needs_human=needs_human, reason=attention_reason, usage=usage,
                            knowledge_sources=knowledge_sources, answer_plan=answer_plan,
                        )
                        topics = json.loads(settings["allowed_topics"])
                        if not support_ai.answer_matches_plan(
                            planned_answer, support_ai.public_evidence(list(current_catalog.values()), topics),
                            topics, current_general,
                        ):
                            failure = "catalog_changed"
                    if knowledge_sources:
                        for source_id in knowledge_sources:
                            before = [fact for fact in general_evidence or [] if fact.get("sourceId") == source_id]
                            after = [fact for fact in current_general if fact.get("sourceId") == source_id]
                            if not before or before != after:
                                failure = "knowledge_changed"
                                break
                except (OSError, ValueError, KeyError, TypeError, HTTPException) as error:
                    logger.warning("Support catalog validation unavailable (%s).", type(error).__name__)
                    failure = "catalog_unavailable"
            db.execute("UPDATE jobs SET status=?,usage_json=?,answer_plan_json=?,updated_at=? WHERE id=?",
                       ("failed" if failure else "completed", json.dumps(usage),
                        json.dumps(answer_plan, ensure_ascii=False) if not failure and answer_plan is not None else None,
                        now(), job["id"]))
            if failure:
                _mark_question(db, row["id"], job["message_id"], failure)
                _append(db, row["id"], "system", HELP_TEXT, reply_to_id=job["message_id"])
            else:
                if needs_human:
                    _mark_question(db, row["id"], job["message_id"], attention_reason or "missing_information")
                answer_id = _append(db, row["id"], "assistant", text, references, reply_to_id=job["message_id"])
                db.execute("UPDATE messages SET answered_by_id=? WHERE id=? AND needs_human=0",
                           (answer_id, job["message_id"]))
                if needs_human and HELP_TEXT not in text:
                    _append(db, row["id"], "system", HELP_TEXT, reply_to_id=job["message_id"])
            db.execute("UPDATE conversations SET revision=revision+1,updated_at=? WHERE id=?", (now(), row["id"]))
            _refresh_attention(db, row["id"])
            db.commit()


async def process_one(store: SupportStore | None = None) -> bool:
    """Claim once, release the transaction for network IO, then fence publication."""
    if not feature_enabled():
        return False
    store = store or get_store()
    job = await asyncio.to_thread(_claim, store)
    if isinstance(job, bool):
        return job
    payload = json.loads(job["payload"])
    from app import support_ai
    if payload["messages"] and support_ai.is_service_only_question(payload["messages"][-1]["text"]):
        payload["item_ref"] = None
    failure = None
    text, references, usage = HELP_TEXT, [], {}
    knowledge_sources: tuple[str, ...] = ()
    answer_plan = None
    needs_human = False
    attention_reason = None
    try:
        payload["catalog"] = await asyncio.to_thread(public_catalog, _job_market(job))
        from app import knowledge
        payload["general_knowledge"] = (await asyncio.to_thread(knowledge.approved_general_facts)
                                        if "customer_service" in payload["allowed_topics"] else [])
    except (OSError, ValueError, KeyError, TypeError, HTTPException) as error:
        logger.warning("Support catalog refresh unavailable (%s).", type(error).__name__)
        failure = "catalog_unavailable"
    if (failure is None and payload["item_ref"] is not None
            and not any(item["ref"] == payload["item_ref"] for item in payload["catalog"])
            and not support_ai.resolve_catalog_items(
                support_ai.public_evidence(payload["catalog"], payload["allowed_topics"]),
                payload["messages"][-1]["text"])):
        failure = "catalog_changed"
    if failure:
        await asyncio.to_thread(_publish, store, job, failure, text, references, usage, payload["catalog"])
        return True
    if not await asyncio.to_thread(_save_current_payload, store, job, payload):
        return True
    try:
        from app import support_ai
        answer = await support_ai.respond(**payload)
        local_reply = support_ai.is_greeting_answer(answer, payload["messages"], payload["allowed_topics"])
        lookup = {item["ref"]: item for item in payload["catalog"]}
        supplied_sources = {fact["sourceId"] for fact in payload["general_knowledge"]}
        answer_sources = getattr(answer, "knowledge_sources", ())
        service_answer = bool(answer.topic == "customer_service" and answer_sources
                              and all(isinstance(source_id, str) and source_id in supplied_sources for source_id in answer_sources))
        plan = getattr(answer, "answer_plan", None)
        valid_plan = plan is not None and support_ai.answer_matches_plan(
            answer, support_ai.public_evidence(payload["catalog"], payload["allowed_topics"]),
            payload["allowed_topics"], payload["general_knowledge"],
        )
        if plan is not None and not valid_plan:
            failure = "invalid_answer"
        elif valid_plan:
            if (not isinstance(answer.text, str) or not answer.text.strip() or len(answer.text) > 8000
                    or any(ref not in lookup for ref in answer.references)
                    or any(source_id not in supplied_sources for source_id in answer_sources)):
                failure = "invalid_answer"
            else:
                answer_plan = plan
                text = answer.text
                references = [{"type": lookup[ref]["type"], "id": lookup[ref]["id"], "url": lookup[ref]["url"],
                               "label": lookup[ref]["name"]} for ref in dict.fromkeys(answer.references)]
                knowledge_sources = tuple(dict.fromkeys(answer_sources))
                needs_human = answer.needs_human
                attention_reason = answer.reason
        elif answer.needs_human:
            failure = answer.reason if answer.reason in (
                "missing_information", "out_of_scope", "customer_request", "provider_failure", "not_configured",
                "quota", "timeout", "unsafe_input", "invalid_response",
                "user_requested", "personal_data", "provider_unavailable", "provider_limit", "scope_disabled",
                "unavailable_item", "invalid_answer", "missing_evidence", "compatibility_unverified",
            ) else "needs_human"
        elif not local_reply and answer.topic not in payload["allowed_topics"]:
            failure = "out_of_scope"
        elif (not isinstance(answer.text, str) or not answer.text.strip() or len(answer.text) > 8000
              or (not local_reply and not answer.references and not service_answer)
              or answer_sources and not service_answer
              or any(ref not in lookup for ref in answer.references)):
            failure = "missing_information"
        else:
            text = answer.text
            references = [{"type": lookup[ref]["type"], "id": lookup[ref]["id"], "url": lookup[ref]["url"],
                           "label": lookup[ref]["name"]} for ref in dict.fromkeys(answer.references)]
            knowledge_sources = tuple(dict.fromkeys(answer_sources))
        usage = {key: value for key, value in answer.usage.items()
                 if key in ("input_tokens", "output_tokens", "total_tokens", "promptTokenCount",
                            "candidatesTokenCount", "thoughtsTokenCount", "totalTokenCount")
                 and type(value) is int and value >= 0}
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError, ImportError, HTTPError) as error:
        # Never expose SDK exception bodies, provider keys, prompts or response payloads.
        logger.warning("Support provider response failed (%s).", type(error).__name__)
        failure = "provider_failure"
    await asyncio.to_thread(_publish, store, job, failure, text, references, usage, payload["catalog"],
                            payload.get("general_knowledge", []), knowledge_sources, answer_plan,
                            needs_human, attention_reason)
    return True


async def _worker(store: SupportStore) -> None:
    recovered = False
    while True:
        try:
            if not recovered:
                await asyncio.to_thread(recover_interrupted, store)
                recovered = True
            worked = await process_one(store)
        except (OSError, sqlite3.Error, ValueError):
            logger.warning("Support worker storage unavailable.")
            recovered = False
            worked = False
        await asyncio.sleep(0.05 if worked else 1)


@asynccontextmanager
async def lifespan(_app):
    tasks = []
    try:
        if feature_enabled():
            from app import knowledge
            tasks = [asyncio.create_task(_worker(get_store())), asyncio.create_task(knowledge.worker())]
    except (OSError, ValueError):
        logger.warning("Support worker unavailable; commerce remains active.")
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
