# Local GeoIP pricing context

STYL's `app.location.resolve_market(request)` reads a **server-local** MaxMind-compatible country MMDB. It sends no visitor IP address to MaxMind or any other lookup service. It does not download a database automatically.

## Contract and limitations

The returned `MarketContext` contains:

| Result | `countryCode` | `currency` | `locationStatus` |
| --- | --- | --- | --- |
| Canadian IP location | `"CA"` | `"CAD"` | `"located"` |
| Any other located country | Country's two-letter code | `"USD"` | `"located"` |
| Unknown/unavailable location | `null` | `"CAD"` | `"unknown"` |

The unknown-location fallback changed from USD to CAD on 2026-09-26 while database
provisioning is pending. Located US/other-country pricing remains USD. A missing
CAD price still hides an item; the USD amount is never relabeled or converted.

Only `country.iso_code` is used. `registered_country` describes registration, not necessarily the user's location, so it is **not** a fallback. VPNs, proxies, mobile networks and database inaccuracies can misidentify a visitor's actual location. This is a display/pricing hint, not proof of residence, tax jurisdiction or eligibility.

The application uses only `request.client.host` after Uvicorn's trusted-proxy processing. It never reads country headers, `X-Forwarded-For`, `Forwarded` or `X-Real-IP` itself. Invalid, private, loopback, link-local, multicast and other non-global addresses remain unknown, including local development requests. IPv4-mapped IPv6 addresses are checked as IPv4.

The service explicitly enables proxy headers **only from loopback peers** (`127.0.0.1,::1`) and binds to `127.0.0.1`. Keep the API port inaccessible publicly. The trusted local reverse proxy must overwrite forwarded client-IP headers with the actual connection address rather than passing an untrusted incoming value unchanged. Do not broaden the allowlist to `*`. If another proxy/CDN is added, review the entire proxy trust chain before relying on location.

The resolver stores no per-IP cache or history and logs no IPs or raw exception details. This does not disable independent Uvicorn, reverse-proxy or infrastructure access logs; configure their privacy/retention separately. Public APIs that return location-dependent prices must set `Cache-Control: no-store`; the resolver returns a dictionary, not an HTTP response, so that policy belongs to API integration.

## Provision a country database

1. Obtain **GeoLite2 Country** through your own [MaxMind account](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/), or obtain a licensed compatible Country database. Use the binary `.mmdb` file, not CSV, a compressed archive or the web-service product. Follow the provider's license, attribution and update requirements. GeoLite licensing has specific freshness requirements; check the current terms.
2. Install the extracted file outside the repository, static/upload roots and catalog backups. The production updater uses `/var/lib/styl-geoip/GeoLite2-Country.mmdb`. Make the directory owned by the administrator/updater with group `styl` and mode `0750`, and the file mode `0640`, readable by `styl` but not writable by the API user. Do not commit databases or download credentials.
3. Set `STYL_GEOIP_DATABASE` in `/etc/styl/styl.env` to that absolute path. Protect the environment file and any updater configuration with restrictive permissions. Keep provider credentials only in protected server-side updater configuration; the API needs no provider credentials.
4. On Windows, use an absolute local path such as `C:\ProgramData\STYL\GeoIP\GeoLite2-Country.mmdb` and an ACL granting read access to the API identity and write access only to the administrator/updater.
5. Install the pinned backend requirements. Restart the service when first changing its environment setting (and reload systemd after changing the unit); routine database replacements do not require a restart.

Leaving `STYL_GEOIP_DATABASE` unset or blank is supported: unknown location and CAD are used. On the first public-IP lookup, absent, missing, unreadable or corrupt databases produce a concise server warning. Repeated failures of the same kind are suppressed rather than logged per visitor. Private/local requests skip database access altogether.

### Local Windows setup verified on 2026-09-27

The development machine has a manually downloaded **GeoLite2 Country** database
under `%LOCALAPPDATA%\STYL\GeoIP\GeoLite2-Country.mmdb`, outside Git, OneDrive,
static files and uploaded content. `LICENSE.txt` and `COPYRIGHT.txt` are retained
beside it. Access is restricted to the current Windows account, SYSTEM and
Administrators. The local API runs as the same developer account; this is not
the production updater/API identity separation described above.

The archive was verified against MaxMind's matching **binary Country** SHA256
download before extraction. The CSV ZIP checksum is a different file and cannot
verify the binary TAR.GZ archive. The installed database reports a build timestamp
of `2026-09-25T12:18:30Z` and supports IPv4/IPv6.

The ignored local API launcher (`.vscode/start-local.ps1`, used by the
**STYL: local API** task) now sets `STYL_GEOIP_DATABASE` to that path unless an
explicit environment value is already supplied. Restart that task after changing
its initial environment. This does not change machine-wide environment variables,
the public AWS service, or unrelated startup scripts. For a separate terminal
startup, set the variable in the same PowerShell process before launching the API:

```powershell
$env:STYL_GEOIP_DATABASE = Join-Path $env:LOCALAPPDATA 'STYL\GeoIP\GeoLite2-Country.mmdb'
```

Actual database/application checks passed for CA/CAD, US/USD, GB/USD, public IPv6,
IPv4-mapped IPv6 and unknown/local addresses, using isolated temporary catalog
fixtures and simulated ASGI client addresses. These are real MMDB lookups, but
not proof of an actual Canadian/US visitor's end-to-end network path. The running
loopback API intentionally still returns `unknown/CAD`, including when a request
supplies forged country/forwarded headers. Keep `--no-proxy-headers` for this
direct local server rather than trusting arbitrary headers to simulate countries.

This installation is **manual**: no MaxMind license key or scheduled updater was
configured locally. Keep this local database current under MaxMind's terms.
Production now has its own independently configured updater; see below and
[project history](project-history.md) for the local verification record.

## Updates without restarting the API

Use the provider's [GeoIP Update tooling or supported download process](https://dev.maxmind.com/geoip/updating-databases/) with your own account. Schedule updates according to its release cadence and licensing requirements. Downloads retrieve database files, not visitor-IP lookups.

Download/extract and validate a new database separately, apply the same ownership/permissions, then **atomically replace** the configured file on the same filesystem. Do not overwrite an active file incrementally. Retain old versions only as allowed by your license.

For each public-IP lookup, the resolver checks the path, file identity, size and modification/change timestamps. A change closes the old reader and loads the new version for that request. Reads and refreshes share one lock per process, so a reader cannot close during a lookup. A single in-memory database snapshot avoids open-file replacement restrictions on Windows; memory consumption scales with database size, not traffic or visitor count. Use a country-only database to keep this small. There is no per-IP cache.

A missing or broken replacement falls back to unknown/CAD; an old country's result is not served. A corrupt file version is not repeatedly reopened; replace/fix the file (changing its metadata) to retry. Updates preserving every observed identity/timestamp/size are not detectable. Each process has its own reader; the provided service runs one worker. This feature does not configure an update job or deploy/download a database for you.

### Production updater installation

The optional [updater](../deploy/update_geoip.py) uses the distribution's
`geoipupdate` binary and [systemd service](../deploy/styl-geoip-update.service) /
[timer](../deploy/styl-geoip-update.timer). Install these only with production
authorization; committing the files does not enable the timer.

- `/etc/styl/GeoIP.conf`: root-owned mode 0600, configured from
  [the example](../deploy/GeoIP.conf.example) with the account's real credentials.
  Download only `GeoLite2-Country`. Never commit or display this file.
- `/var/cache/styl-geoip`: root-only mode 0700 download cache.
- `/var/lib/styl-geoip`: root:styl mode 0750; published
  `GeoLite2-Country.mmdb` is root:styl mode 0640. This separate location avoids
  retaining licensed database copies in the normal catalog backup archives.
- `/usr/local/lib/styl/update_geoip.py`: root-owned copy of the reviewed script.
  The API has read-only database access, not updater credentials.

The script validates database type and build age, copies to a temporary file in
the destination directory, flushes it, then atomically replaces the published
file. An unchanged file is not replaced. Failed downloads or validation do not
overwrite a still-current published database. Provider output is captured rather
than logged because it can contain signed download URLs. Failures produce a
nonzero service result and an explicit sanitized error.

The timer checks at 00:00 and 12:00 UTC, with up to 30 minutes of random delay and
catch-up after downtime. As an additional safeguard, each run removes database
copies whose build timestamps are over 30 days old, even if the next download
fails; the application then uses unknown/CAD. Monitor failed updates: a disabled
timer cannot enforce freshness. MaxMind's license requires prompt updates and
removal of superseded data within 30 days. A small site-footer credit attributes
GeoLite data to MaxMind and GeoNames.

Once directories/configuration and the official updater are installed:

```bash
sudo install -d -m 0755 /usr/local/lib/styl
sudo install -m 0644 /opt/styl/deploy/update_geoip.py /usr/local/lib/styl/update_geoip.py
sudo install -m 0644 /opt/styl/deploy/styl-geoip-update.service /etc/systemd/system/
sudo install -m 0644 /opt/styl/deploy/styl-geoip-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start styl-geoip-update.service
sudo systemctl --no-pager show styl-geoip-update.service -p Result -p ExecMainStatus
sudo systemctl enable --now styl-geoip-update.timer
sudo systemctl --no-pager list-timers styl-geoip-update.timer
```

Only after the first validated publish, set
`STYL_GEOIP_DATABASE=/var/lib/styl-geoip/GeoLite2-Country.mmdb` in the protected
STYL environment, preserving all SMTP/admin/origin settings. Ensure the installed
API service uses the repository's loopback-only proxy trust flags and Caddy
overwrites incoming forwarded IPs. Restart only the API for its environment/unit
change. Deploy/rebuild the frontend separately if its attribution is not yet live.
Routine database refreshes do not require API restarts. Test the public
`/api/market` from actual visitors, including spoofed-header comparisons, then
verify regional catalog visibility and no-store headers.

Production activation was completed with the user through Edge's Ubuntu-1 SSH
terminal on 2026-09-27 Pacific time using application release `bc45b22`.
Independent public requests from the current network return
`{"countryCode":"US","currency":"USD","locationStatus":"located"}` and
`Cache-Control: no-store, private`; forged Canadian forwarding/country headers
do not change that result. The user confirmed a second updater run succeeded
without changing the API PID, the timer is enabled, the API cannot write its
database, credentials remain root-only and non-GeoIP settings/catalog checksums
are unchanged. The tiny attribution footer is live.

Monitor the job with `systemctl --no-pager status styl-geoip-update.timer` and
`journalctl -u styl-geoip-update.service --no-pager`. The built-in job sanitizes
provider failures; never print the protected GeoIP configuration or raw provider
download logs. There is no external failure-alert delivery configured yet.
Real Canadian/other-country browsing and the next scheduled timer invocation
remain separate follow-up checks; local sample lookups do not certify them.

## Offline focused tests

From `backend`, run `python -m unittest discover -s tests -p test_location.py`.
Tests mock MMDB records and file metadata, including country results, unavailable files, replacement and concurrent access. No external database, network or provider account is required.
The updater's separate tests are in
[test_geoip_update.py](../backend/tests/test_geoip_update.py); they exercise atomic
publication, invalid/expired data, permissions and sanitized failure behavior.

## Troubleshooting a Canadian visitor seeing USD

Open `/api/market` on the exact host used by the affected visitor, from that
visitor's browser/network. It returns country/currency/status, not the visitor's
IP. An investigator's response does not establish the affected visitor's result.

| Response | Interpretation / next check |
| --- | --- |
| `countryCode: null`, `locationStatus: unknown`, `currency: CAD` | Current fallback, not confirmation of a Canadian location. Check the database configuration/file and forwarded client address. |
| `countryCode: null`, `locationStatus: unknown`, `currency: USD` | Earlier fallback policy: verify which release is running before investigating pricing or assuming a US location. |
| `countryCode: CA`, `currency: CAD` | Detection succeeded. Check the catalog response, selected market price, frontend API host, and caches if the page still displays USD. |
| A non-CA country with `locationStatus: located` | Check the affected network's VPN/proxy/egress and database accuracy/freshness; physical location alone does not determine the IP record. |

After making a request, an authorized server operator can inspect only relevant
warnings without dumping credentials or full access logs:

```bash
sudo journalctl -u styl-api --since '10 minutes ago' --no-pager -o cat \
  | grep 'GeoIP unavailable'
```

Warnings distinguish unset, unreadable, corrupt, and failed-lookup databases.
Warnings are deduplicated, so an empty recent result does not prove configuration
is correct; an earlier service log may contain the first warning. Check the
effective service environment/path and file readability as the `styl` user, then
verify the installed proxy trust chain against the guidance above. Do not paste
the entire environment file or real visitor IPs into a public issue.

Localhost requests are private/loopback addresses and intentionally return
unknown/CAD even with a database installed. They cannot prove Canadian detection.
Use offline test fixtures for code behavior and an actual configured server with
controlled Canadian egress for live verification. Do not fix a missing database
by guessing country from timezone/language or trusting arbitrary country headers.
