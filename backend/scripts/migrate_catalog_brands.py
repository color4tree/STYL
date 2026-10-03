"""Offline, explicit migration of leading STYL name tokens into optional brand."""

import argparse
import json
import os
from pathlib import Path
import re
import stat
import tempfile


PREFIX = re.compile(r"^STYL(?:[\s:\-\u2013\u2014]+|$)", re.IGNORECASE)


def migrate_items(items: object) -> tuple[list[dict[str, object]], int]:
    if not isinstance(items, list):
        raise ValueError("Catalog must be a JSON array.")
    result = []
    count = 0
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise ValueError("Each catalog record must have a text name.")
        name = item["name"]
        match = PREFIX.match(name)
        if not match:
            result.append(item)
            continue
        title = name[match.end():].strip()
        if not title:
            raise ValueError(f"Record {item.get('id')} would have an empty name.")
        brand = item.get("brand")
        if brand is not None and (not isinstance(brand, str) or brand.strip().casefold() not in ("", "styl")):
            raise ValueError(f"Record {item.get('id')} has a conflicting brand; review it manually.")
        result.append({**item, "name": title, "brand": "STYL"})
        count += 1
    return result, count


def migrate_catalogs(directory: Path, backup_directory: Path | None = None) -> dict[str, int]:
    changes = []
    counts = {}
    for filename in ("products.json", "accessories.json"):
        path = directory / filename
        original = path.read_bytes()
        items, count = migrate_items(json.loads(original))
        counts[filename] = count
        if count:
            changes.append((path, original, (json.dumps(items, ensure_ascii=False, indent=2) + "\n").encode("utf-8")))
    if backup_directory is None or not changes:
        return counts

    backup_directory.mkdir(parents=True, exist_ok=False)
    backup_directory.chmod(0o700)
    for path, original, _ in changes:
        backup = backup_directory / path.name
        with backup.open("xb") as output:
            backup.chmod(0o600)
            output.write(original)
        if backup.read_bytes() != original:
            raise OSError(f"Backup verification failed for {path.name}.")
    for path, original, replacement in changes:
        if path.read_bytes() != original:
            raise RuntimeError(f"{path.name} changed during migration; stop catalog writers and retry.")
        with tempfile.NamedTemporaryFile(dir=directory, prefix=".brand-", delete=False) as output:
            temporary = Path(output.name)
            try:
                output.write(replacement)
                output.flush()
                os.fsync(output.fileno())
            except OSError:
                output.close()
                temporary.unlink()
                raise
        try:
            temporary.chmod(stat.S_IMODE(path.stat().st_mode))
            os.replace(temporary, path)
            if path.read_bytes() != replacement:
                raise OSError(f"Migration verification failed for {path.name}; restore the backup.")
        finally:
            temporary.unlink(missing_ok=True)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Write changes; stop the API/catalog writers first.")
    parser.add_argument("--backup-dir", type=Path, help="New private directory for verified byte-for-byte backups.")
    args = parser.parse_args()
    if args.apply != (args.backup_dir is not None):
        parser.error("--apply and --backup-dir must be supplied together.")
    counts = migrate_catalogs(args.data_dir, args.backup_dir)
    print(json.dumps({"mode": "applied" if args.apply else "dry-run", "changed": counts}))


if __name__ == "__main__":
    main()
