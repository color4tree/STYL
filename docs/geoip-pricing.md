# Local GeoIP pricing context

STYL's `app.location.resolve_market(request)` reads a **server-local** MaxMind-compatible country MMDB. It sends no visitor IP address to MaxMind or any other lookup service. It does not download a database automatically.

## Contract and limitations

The returned `MarketContext` contains:

| Result | `countryCode` | `currency` | `locationStatus` |
| --- | --- | --- | --- |
| Canadian IP location | `"CA"` | `"CAD"` | `"located"` |
| Any other located country | Country's two-letter code | `"USD"` | `"located"` |
| Unknown/unavailable location | `null` | `"USD"` | `"unknown"` |

Only `country.iso_code` is used. `registered_country` describes registration, not necessarily the user's location, so it is **not** a fallback. VPNs, proxies, mobile networks and database inaccuracies can misidentify a visitor's actual location. This is a display/pricing hint, not proof of residence, tax jurisdiction or eligibility.

The application uses only `request.client.host` after Uvicorn's trusted-proxy processing. It never reads country headers, `X-Forwarded-For`, `Forwarded` or `X-Real-IP` itself. Invalid, private, loopback, link-local, multicast and other non-global addresses remain unknown, including local development requests. IPv4-mapped IPv6 addresses are checked as IPv4.

The service explicitly enables proxy headers **only from loopback peers** (`127.0.0.1,::1`) and binds to `127.0.0.1`. Keep the API port inaccessible publicly. The trusted local reverse proxy must overwrite forwarded client-IP headers with the actual connection address rather than passing an untrusted incoming value unchanged. Do not broaden the allowlist to `*`. If another proxy/CDN is added, review the entire proxy trust chain before relying on location.

The resolver stores no per-IP cache or history and logs no IPs or raw exception details. This does not disable independent Uvicorn, reverse-proxy or infrastructure access logs; configure their privacy/retention separately. Public APIs that return location-dependent prices must set `Cache-Control: no-store`; the resolver returns a dictionary, not an HTTP response, so that policy belongs to API integration.

## Provision a country database

1. Obtain **GeoLite2 Country** through your own [MaxMind account](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/), or obtain a licensed compatible Country database. Use the binary `.mmdb` file, not CSV, a compressed archive or the web-service product. Follow the provider's license, attribution and update requirements. GeoLite licensing has specific freshness requirements; check the current terms.
2. Install the extracted file outside the repository and static/upload roots. A Linux deployment can use `/var/lib/styl/geoip/GeoLite2-Country.mmdb`. Make the directory owned by the administrator/updater with group `styl` and mode `0750`, and the file mode `0640`, readable by `styl` but not writable by the API user. Do not commit databases or download credentials.
3. Set `STYL_GEOIP_DATABASE` in `/etc/styl/styl.env` to that absolute path. Protect the environment file and any updater configuration with restrictive permissions. Keep provider credentials only in protected server-side updater configuration; the API needs no provider credentials.
4. On Windows, use an absolute local path such as `C:\ProgramData\STYL\GeoIP\GeoLite2-Country.mmdb` and an ACL granting read access to the API identity and write access only to the administrator/updater.
5. Install the pinned backend requirements. Restart the service when first changing its environment setting (and reload systemd after changing the unit); routine database replacements do not require a restart.

Leaving `STYL_GEOIP_DATABASE` unset or blank is supported: unknown location and USD are used. On the first public-IP lookup, absent, missing, unreadable or corrupt databases produce a concise server warning. Repeated failures of the same kind are suppressed rather than logged per visitor. Private/local requests skip database access altogether.

## Updates without restarting the API

Use the provider's [GeoIP Update tooling or supported download process](https://dev.maxmind.com/geoip/updating-databases/) with your own account. Schedule updates according to its release cadence and licensing requirements. Downloads retrieve database files, not visitor-IP lookups.

Download/extract and validate a new database separately, apply the same ownership/permissions, then **atomically replace** the configured file on the same filesystem. Do not overwrite an active file incrementally. Retain old versions only as allowed by your license.

For each public-IP lookup, the resolver checks the path, file identity, size and modification/change timestamps. A change closes the old reader and loads the new version for that request. Reads and refreshes share one lock per process, so a reader cannot close during a lookup. A single in-memory database snapshot avoids open-file replacement restrictions on Windows; memory consumption scales with database size, not traffic or visitor count. Use a country-only database to keep this small. There is no per-IP cache.

A missing or broken replacement fails closed to unknown/USD; an old country's result is not served. A corrupt file version is not repeatedly reopened; replace/fix the file (changing its metadata) to retry. Updates preserving every observed identity/timestamp/size are not detectable. Each process has its own reader; the provided service runs one worker. This feature does not configure an update job or deploy/download a database for you.

## Offline focused tests

From `backend`, run `python -m unittest discover -s tests -p test_location.py`.
Tests mock MMDB records and file metadata, including country results, unavailable files, replacement and concurrent access. No external database, network or provider account is required.
