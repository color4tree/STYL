"""Country-only pricing context from a server-local MaxMind database."""

import atexit
import ipaddress
import logging
import os
from pathlib import Path
import re
import stat
from threading import Lock
from typing import Literal
from typing_extensions import TypedDict

from fastapi import Request
import maxminddb


class MarketContext(TypedDict):
    countryCode: str | None
    currency: Literal["CAD", "USD"]
    locationStatus: Literal["located", "unknown"]


logger = logging.getLogger(__name__)


class _CountryDatabase:
    def __init__(self) -> None:
        self._lock = Lock()
        self._reader: maxminddb.Reader | None = None
        self._signature: tuple[str, int, int, int, int, int] | None = None
        self._warning: str | None = None

    def _warn(self, reason: str) -> None:
        if self._warning != reason:
            logger.warning("GeoIP unavailable: %s; using unknown location and CAD.", reason)
            self._warning = reason

    def _close_reader(self) -> None:
        if self._reader is not None:
            self._reader.close()
            self._reader = None

    def close(self) -> None:
        with self._lock:
            self._close_reader()
            self._signature = None

    def country_code(self, address: str) -> str | None:
        # Opening, reading and closing share a lock so a refresh cannot close an
        # active reader. Cache one database version, never individual IPs.
        with self._lock:
            configured_path = os.environ.get("STYL_GEOIP_DATABASE", "").strip()
            if not configured_path:
                self._close_reader()
                self._signature = None
                self._warn("STYL_GEOIP_DATABASE is not set")
                return None

            path = Path(configured_path)
            try:
                info = path.stat()
                if not stat.S_ISREG(info.st_mode):
                    raise OSError("Not a regular file")
            except (OSError, ValueError):
                self._close_reader()
                self._signature = None
                self._warn("STYL_GEOIP_DATABASE is missing or unreadable")
                return None

            signature = (
                str(path), info.st_dev, info.st_ino, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns,
            )
            if signature != self._signature:
                self._close_reader()
                self._signature = signature
                try:
                    # A memory snapshot also permits file replacement on Windows.
                    self._reader = maxminddb.open_database(path, mode=maxminddb.MODE_MEMORY)
                except (OSError, ValueError, maxminddb.InvalidDatabaseError):
                    self._warn("STYL_GEOIP_DATABASE is invalid or unreadable")
                    return None
                self._warning = None

            if self._reader is None:
                return None
            try:
                record = self._reader.get(address)
            except (OSError, ValueError, maxminddb.InvalidDatabaseError):
                self._close_reader()
                self._warn("STYL_GEOIP_DATABASE lookup failed")
                return None

            country = record.get("country") if isinstance(record, dict) else None
            code = country.get("iso_code") if isinstance(country, dict) else None
            if isinstance(code, str) and re.fullmatch(r"[A-Z]{2}", code):
                return code
            return None


_database = _CountryDatabase()
atexit.register(_database.close)


def resolve_market(request: Request) -> MarketContext:
    """Use only Uvicorn's client address, not application-level proxy headers."""
    unknown: MarketContext = {
        "countryCode": None,
        "currency": "CAD",
        "locationStatus": "unknown",
    }
    if request.client is None:
        return unknown
    host = request.client.host
    try:
        if "%" in host:
            return unknown
        address = ipaddress.ip_address(host)
    except ValueError:
        return unknown
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    if not address.is_global or address.is_multicast:
        return unknown

    country_code = _database.country_code(str(address))
    if country_code is None:
        return unknown
    return {
        "countryCode": country_code,
        "currency": "CAD" if country_code == "CA" else "USD",
        "locationStatus": "located",
    }
