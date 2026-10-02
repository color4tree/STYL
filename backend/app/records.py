"""Authenticated private records snapshots and explicitly verified cleanup."""

from __future__ import annotations

from contextlib import contextmanager, closing
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Literal
from uuid import uuid4
import zipfile

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app import analytics, records_archive
from app.records_archive import CHUNK, FORMAT, SAFE_NAME, RecordsError, digest, verify_archive


logger = logging.getLogger(__name__)
OPERATIONS = Lock()
RESERVE_BYTES = 128 * 1024 * 1024
REMOVABLE_TABLES = ("analytics_aggregate_counts", "analytics_aggregate_items")


class RemovalFailed(RecordsError):
    """Cleanup may have partially completed; retain the verified recovery archive."""


class RemoveInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmation: str = Field(max_length=100)
    categories: list[Literal["inquiries", "analytics", "websiteLogs"]] = Field(min_length=1, max_length=3)


class DeleteArchiveInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    confirmation: str = Field(max_length=100)


def private_directory(value: str) -> Path:
    from app import main
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise RecordsError("Records directories must be absolute private paths without symlinks.")
    path = path.resolve()
    root = Path(__file__).resolve().parents[2]
    for public in (main.UPLOAD_PATH, root / "frontend" / "public", root / "frontend" / ".next"):
        if path.is_relative_to(public.resolve()):
            raise RecordsError("Records must be stored outside public/upload directories.")
    return path


def records_directory() -> Path:
    default = analytics.configured_path().parent / "records"
    path = private_directory(os.getenv("STYL_RECORDS_DIR", str(default)))
    logs = os.getenv("STYL_WEBSITE_LOG_DIR")
    if logs and (path.is_relative_to(private_directory(logs)) or private_directory(logs).is_relative_to(path)):
        raise RecordsError("Website logs and records backups require separate directories.")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def log_directory() -> Path | None:
    value = os.getenv("STYL_WEBSITE_LOG_DIR")
    if not value:
        return None
    path = private_directory(value)
    if not path.is_dir():
        raise RecordsError("Configured website log directory is unavailable.")
    return path


def regular_file(path: Path) -> os.stat_result:
    value = path.lstat()
    if not stat.S_ISREG(value.st_mode) or path.is_symlink() or value.st_nlink != 1:
        raise RecordsError("Records must be regular files, not links.")
    return value


def source_files(directory: Path, suffixes: tuple[str, ...]) -> list[Path]:
    if directory.is_symlink():
        raise RecordsError("Record source directory must not be a symlink.")
    if not directory.exists():
        return []
    result = []
    for path in sorted(directory.iterdir()):
        regular_file(path)
        if not SAFE_NAME.fullmatch(path.name) or not path.name.endswith(suffixes):
            raise RecordsError("Unexpected file in the records source directory; review before backup.")
        result.append(path)
    return result


@contextmanager
def index():
    path = records_directory() / "index.sqlite3"
    if path.exists():
        regular_file(path)
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        path.chmod(0o600)
        connection.row_factory = sqlite3.Row
        connection.execute("""CREATE TABLE IF NOT EXISTS archives(
            id TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'ready')""")
        connection.commit()
        with connection:
            yield connection


def get_archive(identifier: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{32}", identifier):
        raise HTTPException(404, "Records backup not found.")
    with index() as connection:
        row = connection.execute("SELECT payload,state FROM archives WHERE id=?", (identifier,)).fetchone()
    if row is None:
        raise HTTPException(404, "Records backup not found.")
    result = json.loads(row["payload"])
    if not isinstance(result, dict) or result.get("id") != identifier:
        raise RecordsError("Records backup index is damaged.")
    result["removalState"] = row["state"]
    return result


def save_archive(value: dict, state: str = "ready") -> None:
    with index() as connection:
        connection.execute("INSERT INTO archives VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,state=excluded.state",
                           (value["id"], json.dumps(value), state))


def archive_path(value: dict) -> Path:
    path = records_directory() / f"styl-records-{value['id']}.zip"
    if value.get("archiveDeletedAt"):
        raise HTTPException(409, "The server backup was removed. Source records cannot be removed using it.")
    regular_file(path)
    return path


def checked_archive(value: dict) -> tuple[Path, dict]:
    path = archive_path(value)
    with path.open("rb") as source:
        size, checksum = digest(source)
    if size != value["bytes"] or checksum != value["sha256"]:
        raise RecordsError("Server backup changed or is damaged; no records were removed.")
    manifest = verify_archive(path)
    if manifest["id"] != value["id"]:
        raise RecordsError("Backup identity does not match its index.")
    return path, manifest


@contextmanager
def operation():
    if not OPERATIONS.acquire(blocking=False):
        raise HTTPException(409, "Another records operation is running. Retry when it finishes.")
    try:
        yield
    finally:
        OPERATIONS.release()


def utcstamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def status() -> dict:
    root = records_directory()
    usage = shutil.disk_usage(root)
    logs = log_directory()
    paths = source_files(logs, (".log", ".jsonl", ".active", ".gz")) if logs is not None else []
    warnings = []
    if logs is None:
        warnings.append("Website log capture is not configured. Backups cover business records only, not website logs.")
    elif not paths:
        warnings.append("No website log files are present. Verify production log capture before relying on this backup.")
    if usage.used / usage.total >= 0.8:
        warnings.append("Records disk usage is at least 80%. Download and verify backups, then explicitly remove backed-up data or add storage. No automatic deletion occurs.")
    with index() as connection:
        rows = connection.execute("SELECT id,state FROM archives ORDER BY rowid DESC").fetchall()
    archives = [get_archive(row["id"]) for row in rows]
    if any(row["state"] in ("removing", "failed") for row in rows):
        warnings.append("A removal was interrupted or failed. Its backup is retained; review recovery before further cleanup.")
    known = {value["filename"] for value in archives}
    if any(path.name not in known for path in root.glob("styl-records-*.zip")):
        warnings.append("An unindexed backup file exists, possibly after interrupted preparation. It was retained; ask the operator to verify and recover its index.")
    return {
        "archives": archives,
        "storage": {"totalBytes": usage.total, "freeBytes": usage.free, "usedPercent": round(usage.used / usage.total * 100, 1)},
        "websiteLogs": {"configured": logs is not None, "activeFiles": sum(path.name.endswith(".active") for path in paths),
                        "sealedFiles": sum(not path.name.endswith(".active") for path in paths),
                        "bytes": sum(regular_file(path).st_size for path in paths)},
        "warnings": warnings,
    }


def add_file(archive: zipfile.ZipFile, path: Path, name: str, removable: bool) -> dict:
    size = regular_file(path).st_size
    checksum = hashlib.sha256()
    remaining = size
    with path.open("rb") as source, archive.open(name, "w", force_zip64=True) as target:
        while remaining:
            block = source.read(min(CHUNK, remaining))
            if not block:
                raise RecordsError("Source file changed during backup; retry.")
            checksum.update(block)
            target.write(block)
            remaining -= len(block)
    return {"path": name, "bytes": size, "sha256": checksum.hexdigest(), "removable": removable}


def create_backup() -> dict:
    from app import main
    root = records_directory()
    logs = log_directory()
    log_files = source_files(logs, (".log", ".jsonl", ".active", ".gz")) if logs is not None else []
    inquiry_files = source_files(main.INQUIRIES_PATH, (".json",))
    estimated = sum(regular_file(path).st_size for path in log_files + inquiry_files)
    store = analytics.get_store()
    if not store.path.is_file():
        raise HTTPException(503, "Analytics source is unavailable. Restore it before creating a complete backup.")
    estimated += regular_file(store.path).st_size
    if shutil.disk_usage(root).free < estimated * 2 + RESERVE_BYTES:
        raise RecordsError("Insufficient space to safely prepare a backup. Add storage; no records were deleted.")
    identifier = uuid4().hex
    created = utcstamp()
    manifest = {
        "format": FORMAT, "version": 1, "id": identifier, "createdAt": created,
        "cutoff": analytics.stamp(analytics.hour_start(datetime.fromisoformat(created))),
        "websiteLogsConfigured": logs is not None, "files": [],
    }
    path = root / f"styl-records-{identifier}.zip"
    with TemporaryDirectory(prefix="prepare-", dir=root) as temporary:
        work = Path(temporary)
        database = work / "analytics.sqlite3"
        with closing(sqlite3.connect(store.path.as_uri() + "?mode=ro", uri=True, timeout=5)) as source, closing(sqlite3.connect(database)) as destination:
            source.backup(destination)
        database.chmod(0o600)
        with closing(sqlite3.connect(database)) as snapshot:
            if snapshot.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RecordsError("Analytics snapshot integrity check failed.")
            saved_environment = snapshot.execute("SELECT value FROM analytics_meta WHERE key='environment'").fetchone()
            if saved_environment is None or saved_environment[0] != os.getenv("STYL_ANALYTICS_ENVIRONMENT", "local"):
                raise RecordsError("Analytics backup environment does not match the application.")
            tables = [row[0] for row in snapshot.execute("SELECT name FROM sqlite_master WHERE type='table'") if re.fullmatch(r"analytics_[a-z_]+", row[0])]
            analytics_rows = sum(snapshot.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0] for table in tables)
        candidate = work / "records.zip"
        with zipfile.ZipFile(candidate, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
            manifest["files"].append(add_file(archive, database, "analytics.sqlite3", False))
            manifest["files"].append(add_file(archive, Path(records_archive.__file__), "restore_records.py", False))
            with main.INQUIRY_LOCK:
                for source in source_files(main.INQUIRIES_PATH, (".json",)):
                    record = json.loads(source.read_bytes())
                    removable = isinstance(record, dict) and record.get("emailStatus") in ("sent", "failed", "unconfigured")
                    manifest["files"].append(add_file(archive, source, "inquiries/" + source.name, removable))
            for source in log_files:
                manifest["files"].append(add_file(archive, source, "website-logs/" + source.name, not source.name.endswith(".active")))
            archive.writestr("manifest.json", json.dumps(manifest, separators=(",", ":")))
        verify_archive(candidate)
        with candidate.open("r+b") as source:
            size, checksum = digest(source)
            os.fsync(source.fileno())
        candidate.chmod(0o600)
        candidate.rename(path)
    value = {
        "id": identifier, "filename": path.name, "createdAt": created, "bytes": size, "sha256": checksum,
        "counts": {"inquiries": sum(record["path"].startswith("inquiries/") for record in manifest["files"]),
                   "analyticsRows": analytics_rows, "websiteLogs": len(log_files)},
        "verifiedAt": None, "removedAt": None, "removal": None, "archiveDeletedAt": None,
    }
    save_archive(value)
    return get_archive(identifier)


def remove_analytics(snapshot: Path, cutoff: str) -> tuple[int, int]:
    removed = skipped = 0
    with closing(sqlite3.connect(snapshot)) as source, analytics.get_store().connection() as target:
        source.row_factory = sqlite3.Row
        target.execute("BEGIN IMMEDIATE")
        tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in REMOVABLE_TABLES:
            if table not in tables:
                continue
            columns = [row[1] for row in source.execute(f"PRAGMA table_info({table})")]
            if columns != [row[1] for row in target.execute(f"PRAGMA table_info({table})")]:
                raise RecordsError("Analytics schema changed since backup; create a fresh backup before removal.")
            if any(not re.fullmatch(r"[a-z_]+", column) for column in columns):
                raise RecordsError("Unsupported analytics schema.")
            condition = " AND ".join(f'"{column}" IS ?' for column in columns)
            for row in source.execute(f"SELECT rowid AS backup_rowid,* FROM {table}"):
                eligible = row["hour"] < cutoff
                if not eligible:
                    skipped += 1
                    continue
                deleted = target.execute(f"DELETE FROM {table} WHERE rowid=? AND {condition}", tuple(row)).rowcount
                removed += deleted
                skipped += 1 - deleted
    return removed, skipped


def remove_sources(value: dict, request: RemoveInput) -> dict:
    from app import main
    if request.confirmation != f"REMOVE {value['id']}" or not value["verifiedAt"]:
        raise HTTPException(409, "Verify the saved downloaded archive and enter the exact removal confirmation first.")
    if value["removalState"] != "ready" or value["removedAt"]:
        raise HTTPException(409, "Removal was already attempted. Create a fresh backup before another removal.")
    path, manifest = checked_archive(value)
    result = {"inquiries": 0, "analyticsRows": 0, "websiteLogs": 0, "skipped": 0}
    # Durable claim prevents a retry from treating a partially completed cleanup as untouched.
    save_archive(value, "removing")
    try:
        if "analytics" in request.categories:
            with TemporaryDirectory(prefix="remove-", dir=records_directory()) as temporary:
                snapshot = Path(temporary) / "analytics.sqlite3"
                with zipfile.ZipFile(path) as archive, archive.open("analytics.sqlite3") as source, snapshot.open("xb") as output:
                    snapshot.chmod(0o600)
                    digest(source, output)
                result["analyticsRows"], result["skipped"] = remove_analytics(snapshot, manifest["cutoff"])
        with main.INQUIRY_LOCK:
            logs = log_directory() if "websiteLogs" in request.categories else None
            for record in manifest["files"]:
                category = "inquiries" if record["path"].startswith("inquiries/") else "websiteLogs" if record["path"].startswith("website-logs/") else None
                if category not in request.categories:
                    continue
                if not record["removable"]:
                    result["skipped"] += 1
                    continue
                directory = main.INQUIRIES_PATH if category == "inquiries" else logs
                if directory is None:
                    raise RecordsError("Website log configuration changed; review before removal.")
                source = directory / record["path"].split("/")[1]
                if not source.exists():
                    if source.is_symlink():
                        raise RecordsError("Record source was replaced by a link.")
                    result["skipped"] += 1
                    continue
                regular_file(source)
                with source.open("rb") as content:
                    size, checksum = digest(content)
                if size != record["bytes"] or checksum != record["sha256"]:
                    result["skipped"] += 1
                    continue
                source.unlink()
                result[category] += 1
        value["removedAt"] = utcstamp()
        value["removal"] = result
        save_archive(value, "complete")
        return get_archive(value["id"])
    except (OSError, ValueError, sqlite3.Error, zipfile.BadZipFile):
        value["removal"] = result
        save_archive(value, "failed")
        logger.error("Records removal failed; verified backup retained. Review partial cleanup before retry.")
        raise RemovalFailed("Removal did not complete. Some selected records may already have been removed. The verified backup is retained and locked for recovery; ask the operator to review before retrying.") from None


def delete_server_archive(value: dict, request: DeleteArchiveInput) -> dict:
    if not value["verifiedAt"] or request.confirmation != f"DELETE BACKUP {value['id']}":
        raise HTTPException(409, "Verify the downloaded archive and enter the exact backup deletion confirmation first.")
    if value["removalState"] in ("removing", "failed"):
        raise HTTPException(409, "This backup is required to recover an interrupted removal; it cannot be deleted here.")
    path, _manifest = checked_archive(value)
    path.unlink()
    value["archiveDeletedAt"] = utcstamp()
    save_archive(value, value["removalState"])
    return get_archive(value["id"])


@contextmanager
def errors():
    try:
        yield
    except RemovalFailed as error:
        raise HTTPException(503, str(error)) from None
    except RecordsError as error:
        logger.warning("Private records operation rejected: %s", error)
        raise HTTPException(409, str(error)) from None
    except (OSError, sqlite3.Error, ValueError, zipfile.BadZipFile):
        logger.error("Private records operation failed. Check private storage, integrity and permissions.")
        raise HTTPException(503, "Records operation could not complete. No automatic cleanup was performed; retain backups and review storage/integrity before retrying.") from None


def make_router(require_admin) -> APIRouter:
    router = APIRouter(prefix="/api/admin/records", dependencies=[Depends(require_admin)])

    @router.get("")
    def list_records(response: Response):
        response.headers["Cache-Control"] = "no-store"
        with errors():
            return status()

    @router.post("/archives", status_code=201)
    def prepare(response: Response):
        response.headers["Cache-Control"] = "no-store"
        with errors(), operation():
            return create_backup()

    @router.get("/archives/{identifier}/download")
    def download(identifier: str):
        with errors(), operation():
            value = get_archive(identifier)
            path, _manifest = checked_archive(value)
            return FileResponse(path, media_type="application/zip", filename=value["filename"],
                                headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})

    @router.post("/archives/{identifier}/verify")
    async def verify(identifier: str, request: Request, response: Response):
        response.headers["Cache-Control"] = "no-store"
        with errors():
            value = await run_in_threadpool(get_archive, identifier)
            if value["archiveDeletedAt"]:
                raise HTTPException(409, "Server backup was already removed.")
            checksum = hashlib.sha256()
            size = 0
            async for chunk in request.stream():
                size += len(chunk)
                if size > value["bytes"]:
                    raise HTTPException(422, "Selected file does not match this backup.")
                checksum.update(chunk)
            if size != value["bytes"] or checksum.hexdigest() != value["sha256"]:
                raise HTTPException(422, "Selected file does not match this backup. Save and select the complete downloaded ZIP.")
            def finish():
                with operation():
                    current = get_archive(identifier)
                    checked_archive(current)
                    current["verifiedAt"] = utcstamp()
                    save_archive(current, current["removalState"])
                    return get_archive(identifier)
            return await run_in_threadpool(finish)

    @router.post("/archives/{identifier}/remove")
    def remove(identifier: str, request: RemoveInput, response: Response):
        response.headers["Cache-Control"] = "no-store"
        with errors(), operation():
            return remove_sources(get_archive(identifier), request)

    @router.delete("/archives/{identifier}")
    def delete(identifier: str, request: DeleteArchiveInput, response: Response):
        response.headers["Cache-Control"] = "no-store"
        with errors(), operation():
            return delete_server_archive(get_archive(identifier), request)

    return router
