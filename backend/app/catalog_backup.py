"""Versioned catalog archives and a standalone, offline recovery command."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
from typing import BinaryIO, TypedDict
import unicodedata
from urllib.parse import unquote, urlsplit
import zipfile
import zlib


FORMAT = "styl-catalog-backup"
VERSION = 1
MAX_TOTAL_BYTES = 8 * 1024**3
MAX_FILE_BYTES = 512 * 1024**2
MAX_JSON_BYTES = 16 * 1024**2
MAX_ENTRIES = 50_000
CHUNK_SIZE = 1024 * 1024
CATALOG_FILES = ("data/products.json", "data/accessories.json", "data/hero.json")
SUPPORT_FILES = ("restore_catalog.py", "RESTORE.txt")
MEDIA_EXTENSIONS = {".svg", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL", *(f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10))}
RECOVERY_NOTES = """STYL CATALOG RECOVERY BACKUP - FORMAT 1

PRIVATE, UNENCRYPTED: includes drafts and private admin/source notes.
Keep this archive securely OFF the production server and out of Git/public folders.
Only saved records are included. Unreferenced uploads are not required by this backup.
No customer inquiries, passwords, SMTP/MaxMind credentials, GeoIP database, AWS
settings, application source/build or customer browser carts are included.

Recover with Python 3.11 or newer; no server, network or third-party packages needed:
  python restore_catalog.py verify BACKUP.zip
  python restore_catalog.py restore BACKUP.zip --destination NEW_RECOVERY_DIRECTORY

Use a trusted copy of this tool from STYL, or extract restore_catalog.py from your
own trusted archive. Checksums detect damage, not an attacker's rewritten manifest.
Do not run programs from an untrusted archive.
The destination must NOT exist. Existing data is never merged or overwritten.
Validation and extraction happen in a private staging directory. Only a complete,
verified result is published to the destination.

The restored directory contains:
  data/products.json, data/accessories.json, data/hero.json
  data/uploads/        (required uploaded images, videos and posters)
  public/images/       (required bundled catalog/banner media)
  manifest.json, RESTORE.txt, restore_catalog.py

Install a compatible STYL application on a clean replacement server.
Stop its API while attaching restored data. Set STYL_DATA_DIR to the recovered
data directory. Copy public/images into that clean frontend's public/images,
preserving relative paths; rebuild/restart the frontend as required.
On Linux grant the STYL service ownership/read access to recovered data/media;
the offline restore intentionally creates private files/directories by default.
Configure fresh admin/SMTP/GeoIP/TLS settings separately from protected backups.
Check admin record counts/IDs, both market prices, draft privacy, banner, images,
video playback/seeking and service restart before opening the replacement site.
Keep the recovery archive until an independent restored copy is verified.

Browser upload/import is not implemented. This is catalog recovery, not a full
machine backup. The original production server is not needed to recover these files.
"""


class BackupError(ValueError):
    """The archive cannot safely represent or restore the catalog."""


class FileRecord(TypedDict):
    path: str
    size: int
    sha256: str


def _reject_constant(value: str) -> None:
    raise BackupError(f"Catalog JSON contains the non-finite number {value}.")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise BackupError("Catalog JSON contains duplicate object keys.")
        value[key] = item
    return value


def _json(data: bytes, label: str) -> object:
    if len(data) > MAX_JSON_BYTES:
        raise BackupError(f"{label} exceeds the 16 MiB metadata limit.")
    try:
        return json.loads(data.decode("utf-8"), parse_constant=_reject_constant, object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise BackupError(f"{label} is not valid JSON; no recovery backup was created.") from error


def _catalog(data: bytes, label: str, products: bool) -> list[dict[str, object]]:
    value = _json(data, label)
    if not isinstance(value, list):
        raise BackupError(f"{label} must contain a saved catalog list.")
    records: list[dict[str, object]] = []
    identifiers: set[int] = set()
    slugs: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            raise BackupError(f"{label} contains an invalid record.")
        identifier = item.get("id")
        if not isinstance(identifier, int) or isinstance(identifier, bool) or identifier < 1 or identifier in identifiers:
            raise BackupError(f"{label} has an invalid or duplicate record ID.")
        identifiers.add(identifier)
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            raise BackupError(f"{label} record {identifier} has no valid name.")
        if products:
            slug = item.get("slug")
            if not isinstance(slug, str) or not slug or slug in slugs:
                raise BackupError(f"{label} has a missing or duplicate product slug.")
            slugs.add(slug)
        records.append(item)
    return records


def _hero(data: bytes) -> dict[str, object]:
    value = _json(data, "hero.json")
    if not isinstance(value, dict) or any(not isinstance(value.get(key), str) for key in ("tag", "number", "eyebrow", "title", "image")):
        raise BackupError("hero.json is not a valid saved banner configuration.")
    return value


def _safe_parts(name: str) -> list[str]:
    parts = name.split("/")
    if not parts or any(
        not part or part in (".", "..") or part.endswith((" ", "."))
        or any(ord(character) < 32 or character in '<>:"\\|?*' for character in part)
        or part.split(".")[0].upper() in RESERVED_NAMES
        for part in parts
    ):
        raise BackupError("Unsafe or non-portable archive/media path.")
    return parts


def _allowed_entry(name: str) -> None:
    parts = _safe_parts(name)
    if name in (*CATALOG_FILES, *SUPPORT_FILES, "manifest.json"):
        return
    media = (parts[:2] == ["data", "uploads"] and len(parts) == 3) or (parts[:2] == ["public", "images"] and len(parts) >= 3)
    if not media or PurePosixPath(name).suffix.lower() not in MEDIA_EXTENSIONS:
        raise BackupError("The archive contains a file outside the catalog recovery scope.")


def _media_names(records: list[dict[str, object]]) -> set[str]:
    required: set[str] = set()
    for item in records:
        label = f"record {item.get('id', 'Home banner')}"
        photos = item.get("photos")
        if photos is not None and (not isinstance(photos, list) or any(not isinstance(photo, str) for photo in photos)):
            raise BackupError(f"Invalid media list in {label}.")
        values = [item.get("image"), *(photos if isinstance(photos, list) else [])]
        for value in values:
            if value is None or value == "":
                continue
            if not isinstance(value, str):
                raise BackupError(f"Invalid media reference in {label}.")
            try:
                parsed = urlsplit(value)
                media_path = unquote(parsed.path, errors="strict")
            except (ValueError, UnicodeError) as error:
                raise BackupError(f"Invalid media URL in {label}.") from error
            if parsed.scheme or parsed.netloc:
                raise BackupError(f"External media in {label}: upload it to STYL before creating a self-contained backup.")
            if media_path.startswith("/api/uploads/"):
                name = "data/uploads/" + media_path.removeprefix("/api/uploads/")
            elif media_path.startswith("/images/"):
                name = "public/images/" + media_path.removeprefix("/images/")
            else:
                raise BackupError(f"Unsupported media path in {label}.")
            _allowed_entry(name)
            required.add(name)
            if name.startswith("data/uploads/") and name.endswith(".mp4"):
                required.add(name[:-4] + ".poster.jpg")
    return required


def _file_source(root: Path, relative: str) -> Path:
    root = root.resolve()
    candidate = root.joinpath(*_safe_parts(relative))
    current = root
    for part in _safe_parts(relative):
        current = current / part
        if current.is_symlink():
            raise BackupError("Linked media files cannot be included in a recovery backup.")
    if not candidate.resolve().is_relative_to(root) or not candidate.is_file():
        raise BackupError(f"Missing local media: {relative}. Repair or upload the file before downloading a backup.")
    return candidate


def _read_saved(path: Path, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise BackupError(f"{label} is missing or is not a regular saved catalog file.")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise BackupError(f"{label} exceeds the 16 MiB metadata limit.")
    return path.read_bytes()


def _stream_digest(source: BinaryIO, destination: BinaryIO | None = None, limit: int = MAX_FILE_BYTES) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while chunk := source.read(CHUNK_SIZE):
        size += len(chunk)
        if size > limit:
            raise BackupError("A recovery file exceeds its supported size limit.")
        digest.update(chunk)
        if destination is not None:
            destination.write(chunk)
    return size, digest.hexdigest()


def create_archive(
    output: BinaryIO, *, products_path: Path, accessories_path: Path, hero_path: Path,
    uploads_path: Path, images_path: Path, default_hero: dict[str, object], app_version: str,
) -> dict[str, object]:
    """Caller holds the application's catalog/media-reference mutation lock."""
    products = _read_saved(products_path, "products.json")
    accessories = _read_saved(accessories_path, "accessories.json")
    hero = _read_saved(hero_path, "hero.json") if hero_path.exists() else json.dumps(default_hero, ensure_ascii=False).encode("utf-8")
    product_records = _catalog(products, "products.json", True)
    accessory_records = _catalog(accessories, "accessories.json", False)
    required = _media_names([*product_records, *accessory_records, _hero(hero)])
    assets = {
        name: _file_source(
            uploads_path if name.startswith("data/uploads/") else images_path,
            name.split("/", 2)[2],
        ) for name in required
    }
    content = {
        "data/products.json": products, "data/accessories.json": accessories, "data/hero.json": hero,
        "RESTORE.txt": RECOVERY_NOTES.encode("utf-8"), "restore_catalog.py": Path(__file__).read_bytes(),
    }
    names = [*content, *assets]
    if len(names) + 1 > MAX_ENTRIES or len({unicodedata.normalize("NFC", name).casefold() for name in names}) != len(names):
        raise BackupError("Too many files or conflicting portable media filenames.")
    sizes = [path.stat().st_size for path in assets.values()]
    if any(size > MAX_FILE_BYTES for size in sizes) or sum(sizes) + sum(map(len, content.values())) > MAX_TOTAL_BYTES:
        raise BackupError("Catalog backup exceeds the 8 GiB total or 512 MiB per-media-file limit.")
    files: list[FileRecord] = []
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for name, data in content.items():
            archive.writestr(name, data)
            files.append({"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        for name, path in sorted(assets.items()):
            before = path.stat()
            entry = zipfile.ZipInfo(name)
            entry.compress_type = zipfile.ZIP_STORED
            entry.external_attr = (stat.S_IFREG | 0o600) << 16
            with path.open("rb") as source, archive.open(entry, "w", force_zip64=True) as target:
                size, digest = _stream_digest(source, target)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (size, after.st_mtime_ns, after.st_ctime_ns):
                raise BackupError("A media file changed while the backup was being built. Please retry.")
            files.append({"path": name, "size": size, "sha256": digest})
        manifest: dict[str, object] = {
            "format": FORMAT, "version": VERSION,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "applicationVersion": app_version,
            "counts": {"products": len(product_records), "accessories": len(accessory_records), "mediaFiles": len(assets)},
            "files": files,
            "scope": "Saved catalog, banner and referenced local media; private admin fields included.",
            "excluded": ["inquiries", "credentials", "server configuration", "GeoIP databases", "application code/build", "unreferenced uploads"],
        }
        encoded = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        if len(encoded) > MAX_JSON_BYTES:
            raise BackupError("Backup manifest exceeds the metadata limit.")
        archive.writestr("manifest.json", encoded)
    output.seek(0)
    return manifest


def _archive_index(archive: zipfile.ZipFile) -> tuple[dict[str, object], list[FileRecord]]:
    entries = archive.infolist()
    names = {entry.filename for entry in entries}
    if len(entries) > MAX_ENTRIES or sum(entry.file_size for entry in entries) > MAX_TOTAL_BYTES + MAX_JSON_BYTES:
        raise BackupError("Archive exceeds recovery size/count limits.")
    seen: set[str] = set()
    for entry in entries:
        _allowed_entry(entry.filename)
        normalized = unicodedata.normalize("NFC", entry.filename).casefold()
        mode = entry.external_attr >> 16
        if normalized in seen or entry.is_dir() or stat.S_IFMT(mode) not in (0, stat.S_IFREG):
            raise BackupError("Archive has duplicate, linked or non-regular entries.")
        if entry.flag_bits & 1 or entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise BackupError("Encrypted or unsupported ZIP entries are not supported.")
        if entry.file_size > (MAX_JSON_BYTES if entry.filename in (*CATALOG_FILES, "manifest.json") else MAX_FILE_BYTES):
            raise BackupError("Archive entry exceeds its size limit.")
        seen.add(normalized)
    if "manifest.json" not in names:
        raise BackupError("Catalog backup manifest is missing.")
    value = _json(archive.read("manifest.json"), "manifest.json")
    if not isinstance(value, dict) or value.get("format") != FORMAT or type(value.get("version")) is not int or value.get("version") != VERSION:
        raise BackupError("Unsupported catalog backup format/version.")
    raw_files = value.get("files")
    if not isinstance(raw_files, list):
        raise BackupError("Invalid backup file manifest.")
    files: list[FileRecord] = []
    listed: set[str] = set()
    for raw in raw_files:
        if not isinstance(raw, dict):
            raise BackupError("Invalid manifest entry.")
        name, size, digest = raw.get("path"), raw.get("size"), raw.get("sha256")
        if not isinstance(name, str) or type(size) is not int or size < 0 or not isinstance(digest, str) or not re.fullmatch("[0-9a-f]{64}", digest):
            raise BackupError("Invalid manifest file size or checksum.")
        if name in listed or name == "manifest.json" or name not in names or archive.getinfo(name).file_size != size:
            raise BackupError("Manifest and archive entries do not match.")
        listed.add(name)
        files.append({"path": name, "size": size, "sha256": digest})
    if listed | {"manifest.json"} != names or not set((*CATALOG_FILES, *SUPPORT_FILES)).issubset(listed):
        raise BackupError("Required backup files are missing or unlisted files were added.")
    products = _catalog(archive.read("data/products.json"), "products.json", True)
    accessories = _catalog(archive.read("data/accessories.json"), "accessories.json", False)
    hero = _hero(archive.read("data/hero.json"))
    required = _media_names([*products, *accessories, hero])
    if required != listed - set((*CATALOG_FILES, *SUPPORT_FILES)):
        raise BackupError("Archive media does not match all catalog/banner references.")
    counts = {"products": len(products), "accessories": len(accessories), "mediaFiles": len(required)}
    recorded_counts = value.get("counts")
    if not isinstance(recorded_counts, dict) or any(type(count) is not int for count in recorded_counts.values()) or recorded_counts != counts:
        raise BackupError("Manifest catalog counts do not match the saved data.")
    return value, files


def verify_archive(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        manifest, files = _archive_index(archive)
        for entry in files:
            with archive.open(entry["path"]) as stream:
                size, digest = _stream_digest(stream)
            if size != entry["size"] or digest != entry["sha256"]:
                raise BackupError("Backup checksum verification failed; do not restore this archive.")
    return manifest


def restore_archive(path: Path, destination: Path) -> dict[str, object]:
    destination = destination.absolute()
    if destination.exists() or destination.is_symlink():
        raise BackupError("Recovery destination must not exist; existing data is never overwritten.")
    if not destination.parent.is_dir():
        raise BackupError("Create the recovery parent directory first.")
    with zipfile.ZipFile(path) as archive:
        manifest, files = _archive_index(archive)
        if shutil.disk_usage(destination.parent).free < sum(entry["size"] for entry in files) + 32 * 1024**2:
            raise BackupError("Not enough free disk space for recovery.")
        staged = Path(tempfile.mkdtemp(prefix=".styl-restore-", dir=destination.parent))
        try:
            for entry in files:
                target = staged.joinpath(*_safe_parts(entry["path"]))
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with archive.open(entry["path"]) as source, target.open("xb") as output:
                    size, digest = _stream_digest(source, output)
                target.chmod(0o600)
                if size != entry["size"] or digest != entry["sha256"]:
                    raise BackupError("Backup checksum verification failed; destination was not published.")
            (staged / "manifest.json").write_bytes(archive.read("manifest.json"))
            (staged / "manifest.json").chmod(0o600)
            (staged / "data" / "uploads").mkdir(parents=True, exist_ok=True, mode=0o700)
            (staged / "public" / "images").mkdir(parents=True, exist_ok=True, mode=0o700)
            if destination.exists() or destination.is_symlink():
                raise BackupError("Recovery destination appeared during extraction; refusing to replace it.")
            staged.rename(destination)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify or recover a private STYL catalog ZIP without the original server.")
    parser.add_argument("action", choices=("verify", "restore"))
    parser.add_argument("archive", type=Path)
    parser.add_argument("--destination", type=Path, help="New, nonexistent recovery directory (restore only)")
    args = parser.parse_args()
    if args.action == "restore" and args.destination is None:
        parser.error("restore requires --destination")
    try:
        if args.action == "restore":
            manifest = restore_archive(args.archive, args.destination)
        else:
            manifest = verify_archive(args.archive)
    except (BackupError, OSError, zipfile.BadZipFile, RuntimeError, EOFError, zlib.error) as error:
        print(f"Catalog recovery failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "restored" if args.action == "restore" else "verified", "counts": manifest["counts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
