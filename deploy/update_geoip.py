"""Download and atomically publish STYL's server-local country database."""

import hashlib
import logging
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time

import maxminddb


CONFIG = Path("/etc/styl/GeoIP.conf")
CACHE = Path("/var/cache/styl-geoip")
DATABASE = Path("/var/lib/styl-geoip/GeoLite2-Country.mmdb")
MAX_AGE_SECONDS = 30 * 24 * 60 * 60
logger = logging.getLogger("styl.geoip-update")


def database_epoch(path: Path) -> int:
    with maxminddb.open_database(str(path)) as reader:
        metadata = reader.metadata()
        if metadata.database_type != "GeoLite2-Country":
            raise ValueError("Expected a GeoLite2 Country database.")
        return metadata.build_epoch


def validate_database(path: Path, now: float) -> int:
    epoch = database_epoch(path)
    if not now - MAX_AGE_SECONDS <= epoch <= now + 24 * 60 * 60:
        raise ValueError("Country database is older than 30 days or has an invalid future build time.")
    return epoch


def discard_expired(path: Path, now: float) -> None:
    if not path.exists():
        return
    try:
        epoch = database_epoch(path)
    except (OSError, ValueError, maxminddb.InvalidDatabaseError):
        logger.warning("Existing country database is unreadable; attempting a fresh download.")
        return
    if epoch < now - MAX_AGE_SECONDS:
        path.unlink()
        logger.warning("Removed a country database older than 30 days; unknown/CAD applies until refreshed.")


def digest(path: Path) -> bytes:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").digest()


def publish_database(source: Path, target: Path, group_id: int, now: float) -> bool:
    validate_database(source, now)
    if target.exists() and digest(source) == digest(target):
        os.chown(target, 0, group_id)
        target.chmod(0o640)
        return False
    descriptor, name = tempfile.mkstemp(prefix=".country-", dir=target.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as output, source.open("rb") as downloaded:
            shutil.copyfileobj(downloaded, output)
            output.flush()
            os.fsync(output.fileno())
        os.chown(temporary, 0, group_id)
        temporary.chmod(0o640)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main() -> None:
    import grp

    if os.geteuid() != 0:
        raise PermissionError("Run the GeoIP updater as root.")
    config_stat = CONFIG.stat()
    if not stat.S_ISREG(config_stat.st_mode) or config_stat.st_uid != 0 or stat.S_IMODE(config_stat.st_mode) != 0o600:
        raise PermissionError("GeoIP.conf must be a root-owned regular file with mode 0600.")
    group_id = grp.getgrnam("styl").gr_gid
    for directory, group, mode in ((CACHE, 0, 0o700), (DATABASE.parent, group_id, 0o750)):
        directory.mkdir(parents=True, exist_ok=True)
        os.chown(directory, 0, group)
        directory.chmod(mode)
    source = CACHE / DATABASE.name
    now = time.time()
    for path in (source, DATABASE):
        discard_expired(path, now)
    result = subprocess.run(
        ["/usr/bin/geoipupdate", "-f", str(CONFIG), "-d", str(CACHE)],
        capture_output=True, text=True, timeout=360, check=False,
    )
    if result.returncode:
        # Provider output can contain signed download URLs; keep it out of logs.
        raise RuntimeError(
            f"geoipupdate exited {result.returncode}; check protected credentials, account entitlement and network access."
        )
    changed = publish_database(source, DATABASE, group_id, time.time())
    logger.info("Country database %s; build epoch %s.", "updated" if changed else "already current", database_epoch(DATABASE))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        main()
    except (OSError, ValueError, RuntimeError, maxminddb.InvalidDatabaseError, subprocess.TimeoutExpired) as error:
        logger.error("GeoIP update failed: %s", error)
        raise SystemExit(1) from None
