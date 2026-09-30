# Catalog download and offline recovery

The admin **Backup** view downloads a private, self-contained catalog ZIP.
Browser upload/import is deferred. Recovery is available now through the
standalone Python command included in each archive, even if the original server
and its data are no longer available.

This restores **catalog content onto a clean, compatible STYL installation**.
It is not a full AWS instance, application-source, credential or inquiry backup.

## Local production-catalog mirror (2026-09-29)

The owner supplied `styl-catalog-backup-20260929T232242Z.zip` for local testing.
It was verified using the trusted repository recovery module, not by executing
the Python file inside the archive, and restored to a new private directory:

```text
%LOCALAPPDATA%\STYL\CatalogMirrors\production-20260929T232242Z\data
```

The snapshot contains **3 equipment records, 16 accessories and 100 media files**,
captured at `2026-09-29T23:22:42.861671+00:00`.
Input ZIP SHA-256:
`fcdf415966870038604d89adbc062a7cbc78d6abffa62b15daeab00d91355398`.
All 105 manifest entries were verified; a ZIP re-exported from the running local
API byte-matched all 103 catalog/media payloads. All 100 upload URLs served the
matching bytes. This archive has no bundled `/images` entries, so checked-out
static assets were not replaced.

An ignored `.styl-runtime/local-catalog.json` selects this directory on future
local API starts. The standard starter and local API task validate the absolute
path and required files before using it. To return to the earlier local catalog,
stop the local API, move/remove only that profile and clear any explicit
`STYL_DATA_DIR` override, then restart with the original paths. Do not copy
production credentials or rewrite prices to simulate a country.

The previous active local catalog was exported and verified at:

```text
%LOCALAPPDATA%\STYL\CatalogMirrors\before-production-20260929T232242Z\local-catalog.zip
```

It contains 4 equipment records, 11 accessories and 16 referenced media files.
Original repository catalog/hero files and upload directories were left intact.
Two existing local inquiry files were preserved in the new data directory; no
production inquiries, credentials, email settings or analytics were imported.
The mirror root has restricted user/SYSTEM/Administrators access and is outside
Git and OneDrive.

This matches the **supplied catalog snapshot**, not every part of current
production. Later production edits require another export. Localhost resolves
to unknown/CAD; the snapshot has valid CAD and USD prices for all 19 items.
Real SMTP/report sending is disabled locally, and local browsing/analytics/inquiry
history remains local rather than pretending to be production activity.

## Included and excluded

Included:

- Saved products and accessories, including Draft/Published state, record IDs,
  product slugs, independent CAD/USD prices and optional MSRPs, legacy fields, specifications,
  compatibility and private provenance/admin notes.
- Home banner configuration. If it has never been saved, the current default
  configuration is materialized in the archive without changing the source.
- All referenced local uploaded images/videos and required MP4 posters.
- Referenced bundled media under the frontend's public images directory.
- A versioned manifest with file lengths and SHA256 hashes, restore instructions
  and a standalone recovery script. Shared media files appear only once.

Not included:

- Unsaved form edits, unreferenced uploads or customer browser carts.
- Customer inquiries, contact details, SMTP/admin/MaxMind credentials or `.env`.
- Private analytics SQLite data and daily-report delivery history; use the
  separate [analytics backup procedure](traffic-analytics-operations.md#retention-deletion-and-backups).
- Licensed GeoIP databases, AWS/DNS/TLS configuration, application source/build,
  system packages or the Python runtime.

The ZIP is **not encrypted** and includes private admin fields. Save it somewhere
secure **off the production server**, such as protected backup storage, and keep
more than one dated recovery point. Do not put it in Git, public uploads, shared
unprotected folders or ordinary email attachments.

## Download

1. Sign in to admin and open **Backup**.
2. Save edits first if you need them in the backup. Opening Backup preserves the
   current editor; it neither saves nor silently discards changes.
3. Choose **Download catalog backup** and keep the page open until transfer ends.
4. Confirm the ZIP exists in your browser's downloads. The browser may prompt for
   a save location. A UI acknowledgement is not proof that the file reached your
   chosen disk; verify the downloaded ZIP with the command below.
5. Periodically perform a cold restore into a new directory, not just a ZIP listing.

The protected endpoint is `GET /api/admin/catalog-backup`, using the existing
Bearer admin authentication. No credentials go in the download URL.
Successful responses are `application/zip`, with a timestamped
`styl-catalog-backup-YYYYMMDDTHHMMSSZ.zip` filename and `no-store, private` caching.
There is no publicly accessible server-side backup link.

The server builds a temporary disk archive before returning a successful response;
large video catalogs are not assembled in server RAM. The current browser UI
assembles the download as a Blob, so prefer desktop for large archives and ensure
enough client memory/disk space. Real large-volume/mobile download capacity is a
separate operational check, not established by small fixture tests.

## Completeness and failure behavior

The backup reads saved JSON strictly. Missing/corrupt catalog data is an error;
it is not replaced by demo data. Invalid saved banner data also fails the backup.
All fields are retained, rather than exporting the market-filtered public list.

An export refuses to claim completeness if a referenced local file/poster is
missing, a linked filesystem path is encountered, or media still uses an external
absolute URL. Upload externally hosted media into STYL and save its local reference
first. No automatic external downloads are attempted, including for absolute
URLs pointing at the old production hostname. Ordinary text/source URLs in private
provenance are preserved as data, not fetched.

The current implementation relies on STYL's single API worker and shared
catalog-write lock. Catalog saves/deletions wait while the archive is generated;
this prevents media cleanup or cross-catalog edits from producing a mixed
snapshot. Public reads are not replaced or disabled. Do not bypass the lock with
manual filesystem edits or introduce multiple catalog writers during export.
Uploaded files are referenced only after their normal upload completes.

Supported limits: 8 GiB payload total, 512 MiB per media file, 16 MiB per JSON
metadata file, and 50,000 archive entries including the manifest. Errors are
explicit and no incomplete archive is presented as a successful backup. These
are safety limits, not a guarantee of browser performance at that size.

Only one archive generation runs at a time. Retry a busy/error response once its
cause is resolved. A disconnected/incomplete transfer must be discarded and
downloaded again; verify length/checksums before relying on it.

## Archive format 1

```text
manifest.json
RESTORE.txt
restore_catalog.py
data/
  products.json
  accessories.json
  hero.json
  uploads/
    <referenced image/video/poster files>
public/
  images/
    <referenced bundled media, preserving relative paths>
```

The manifest identifies `styl-catalog-backup`, version `1`, creation time,
application version, record/media counts, inclusion/exclusion scope and a hash/
size for every payload file. The application version is descriptive, not a copy
of the application code. Keep a matching application release separately.

SHA256 detects accidental damage or altered payloads relative to the manifest.
It is **not an authenticity signature**: someone who replaces the archive and
its manifest can rewrite both. Restore only your own trusted backups, and prefer
the recovery tool from trusted STYL source. Never execute a script extracted from
an untrusted ZIP.

## Verify and restore without the original server

Requirements: Python 3.11 or newer, sufficient disk space, and access to the
downloaded archive. The recovery tool uses only the Python standard library;
it does not contact production, MaxMind or any other network service.

From a trusted STYL checkout on Windows:

```powershell
.\.venv\Scripts\python.exe .\backend\app\catalog_backup.py verify "C:\SecureBackups\BACKUP.zip"
.\.venv\Scripts\python.exe .\backend\app\catalog_backup.py restore "C:\SecureBackups\BACKUP.zip" --destination "C:\STYL-Recovery\catalog-restored"
```

Alternatively, extract only `restore_catalog.py` and `RESTORE.txt` from your own
trusted archive and run them with an installed Python 3.11+ interpreter:

```powershell
python .\restore_catalog.py verify "C:\SecureBackups\BACKUP.zip"
python .\restore_catalog.py restore "C:\SecureBackups\BACKUP.zip" --destination "C:\STYL-Recovery\catalog-restored"
```

Create the destination's parent directory first. The destination itself **must
not exist**, even as an empty directory. The tool does not merge with or overwrite
existing data. Do not run other processes that create/write that destination
while recovery is in progress.

The tool rejects unsupported versions, missing/extra/duplicate entries, symlinks,
unsafe paths, unsupported compression, invalid metadata, size-limit violations,
missing referenced media and checksum failures. Extraction uses a private staging
directory; only a complete result is moved into the new recovery destination.
On failure, the existing destination is untouched and temporary extraction files
are cleaned. Errors return a nonzero exit code.

Successful verification/recovery prints its status and record counts, not private
catalog content. The recovered root contains `data`, `public/images`, manifest,
instructions and the standalone tool.

## Attach recovered content to a clean STYL installation

1. Install a compatible STYL application and its dependencies on a replacement
   machine using trusted source. Recreate HTTPS/proxy/systemd or local startup
   configuration using the [deployment guide](lightsail-deployment.md).
2. Verify and restore the ZIP into a new recovery directory.
3. Keep the new API stopped while attaching recovered data. Set `STYL_DATA_DIR`
   to the restored **data** directory, not the archive root. This makes the API
   use its recovered `uploads` directory too.
4. Copy the recovered `public/images` contents into the clean frontend's
   `public/images`, preserving subdirectories and filenames. Do not overwrite a
   different live site's media; this procedure targets a clean installation.
5. Grant the service account access. Restored files/directories are intentionally
   private by default; on Linux, transfer appropriate ownership to `styl` and
   keep private catalog fields unavailable to other accounts.
6. Configure fresh admin credentials and restore SMTP/GeoIP settings separately
   from protected operational records. Do not invent or copy another market's
   prices to make the recovered store look populated.
7. Build/start the frontend and API, then inspect:
   - Admin product/accessory counts, IDs/slugs and private metadata.
   - CAD/USD prices and optional MSRPs independently, including missing-selling-price
     hiding, higher-only MSRP display and cart/quote totals based on selling Price.
   - Draft privacy and published detail links.
   - Home banner, images, all video/poster references and byte-range seeking.
   - Save/reload and service restart persistence.
8. Open public access only after this recovery check succeeds.

No production overwrite, service restart, email send or live rollback is
performed automatically by the restore command. Website code, server
configuration and customer inquiries still need their own recovery plan.

## Verification coverage

[Backend tests](../backend/tests/test_catalog_backup.py) download the real API ZIP,
remove the original fixture data/media, run the included standalone script from
an isolated directory, compare restored JSON and media bytes, and boot a fresh
API process against recovered storage. They verify draft/price/privacy behavior,
restored images/posters and video byte ranges, plus rejection of damaged and
unsafe archives. Fixture video bytes test preservation/range behavior, not visual
playback quality.

[Browser tests](../frontend/tests/e2e/catalog-backup.spec.ts) cover authenticated
download, progress/error/retry behavior, saved-data warnings, retained editor
changes and responsive layouts.

This evidence is an isolated recovery proof, not a completed recovery drill of
the real production catalog. A production archive should be independently
verified and restored in an isolated replacement environment before being relied
on for disaster recovery. Do not test restoration over the live site.
