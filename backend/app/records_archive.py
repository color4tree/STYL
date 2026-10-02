"""Offline verification and extraction of private STYL records (Python 3.11+)."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from typing import BinaryIO
import zipfile


FORMAT = "styl-private-records"
CHUNK = 1024 * 1024
MAX_MANIFEST = 16 * 1024 * 1024
MAX_ENTRIES = 100_000
MAX_BYTES = 100 * 1024**3
SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}")


class RecordsError(ValueError):
    """A backup could not be created, verified or safely restored."""


def digest(source: BinaryIO, target: BinaryIO | None = None, limit: int = MAX_BYTES) -> tuple[int, str]:
    size = 0
    checksum = hashlib.sha256()
    while block := source.read(min(CHUNK, limit - size + 1)):
        size += len(block)
        if size > limit:
            raise RecordsError("Record size exceeds the backup limit.")
        checksum.update(block)
        if target is not None:
            target.write(block)
    return size, checksum.hexdigest()


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RecordsError("Duplicate JSON field in backup.")
        result[key] = value
    return result


def allowed_name(name: str) -> bool:
    parts = PurePosixPath(name).parts
    if name in ("analytics.sqlite3", "restore_records.py"):
        return True
    if len(parts) != 2 or "/".join(parts) != name or not SAFE_NAME.fullmatch(parts[1]):
        return False
    return (
        parts[0] == "inquiries" and parts[1].endswith(".json")
        or parts[0] == "website-logs" and parts[1].endswith((".log", ".jsonl", ".active", ".gz"))
    )


def verify_archive(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if len(entries) > MAX_ENTRIES or len(set(names)) != len(names) or len({name.casefold() for name in names}) != len(names):
                raise RecordsError("Duplicate or excessive archive entries.")
            if "manifest.json" not in names or archive.getinfo("manifest.json").file_size > MAX_MANIFEST:
                raise RecordsError("Missing or oversized backup manifest.")
            manifest = json.loads(archive.read("manifest.json"), object_pairs_hook=unique_object)
            if not isinstance(manifest, dict) or manifest.get("format") != FORMAT or manifest.get("version") != 1:
                raise RecordsError("Unsupported records backup.")
            if not re.fullmatch(r"[a-f0-9]{32}", str(manifest.get("id", ""))):
                raise RecordsError("Invalid archive identifier.")
            for field in ("createdAt", "cutoff"):
                if not isinstance(manifest.get(field), str):
                    raise RecordsError("Missing archive timestamp.")
                try:
                    value = datetime.fromisoformat(manifest[field])
                except ValueError as error:
                    raise RecordsError("Invalid archive timestamp.") from error
                if value.tzinfo is None:
                    raise RecordsError("Archive timestamps require a timezone.")
            records = manifest.get("files")
            if not isinstance(records, list) or len(records) + 1 != len(entries):
                raise RecordsError("Manifest does not cover every file.")
            expected: dict[str, dict] = {}
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get("path"), str) or not allowed_name(record["path"]):
                    raise RecordsError("Unsafe backup path.")
                if type(record.get("bytes")) is not int or not 0 <= record["bytes"] <= MAX_BYTES:
                    raise RecordsError("Invalid backup file size.")
                if not re.fullmatch(r"[a-f0-9]{64}", str(record.get("sha256", ""))) or type(record.get("removable")) is not bool:
                    raise RecordsError("Invalid backup file metadata.")
                expected[record["path"]] = record
            if set(expected) != set(names) - {"manifest.json"} or sum(record["bytes"] for record in records) > MAX_BYTES:
                raise RecordsError("Incomplete or oversized backup.")
            if not {"analytics.sqlite3", "restore_records.py"}.issubset(expected):
                raise RecordsError("Backup is missing required recovery files.")
            for entry in entries:
                if entry.is_dir() or entry.flag_bits & 1 or stat.S_ISLNK(entry.external_attr >> 16):
                    raise RecordsError("Links, directories and encrypted entries are not supported.")
                if entry.filename == "manifest.json":
                    continue
                record = expected[entry.filename]
                if entry.file_size != record["bytes"]:
                    raise RecordsError("Backup file size differs from manifest.")
                with archive.open(entry) as source:
                    size, checksum = digest(source, limit=record["bytes"])
                if size != record["bytes"] or checksum != record["sha256"]:
                    raise RecordsError("Backup checksum verification failed.")
            return manifest
    except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError, UnicodeError) as error:
        raise RecordsError("Invalid or damaged records backup.") from error


def restore_archive(path: Path, destination: Path) -> dict:
    manifest = verify_archive(path)
    if destination.exists() or destination.is_symlink():
        raise RecordsError("Restore requires a new, nonexistent directory.")
    if any(parent.is_symlink() for parent in destination.parents):
        raise RecordsError("Restore destination must not pass through a symlink.")
    destination.mkdir(mode=0o700, parents=True)
    try:
        with zipfile.ZipFile(path) as archive:
            for record in manifest["files"]:
                target = destination.joinpath(*PurePosixPath(record["path"]).parts)
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with archive.open(record["path"]) as source, target.open("xb") as output:
                    target.chmod(0o600)
                    size, checksum = digest(source, output, record["bytes"])
                if size != record["bytes"] or checksum != record["sha256"]:
                    raise RecordsError("Archive changed during restore.")
    except (OSError, RecordsError, zipfile.BadZipFile):
        # This directory was exclusively created by this call, never an existing installation.
        shutil.rmtree(destination)
        raise
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--destination", type=Path, help="Extract into a NEW private directory; never overwrites production.")
    args = parser.parse_args()
    try:
        result = restore_archive(args.archive, args.destination) if args.destination else verify_archive(args.archive)
        print(json.dumps({"verified": True, "id": result["id"], "files": len(result["files"]), "restored": args.destination is not None}))
        return 0
    except (RecordsError, OSError) as error:
        print(f"Records recovery failed: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
