# Backup & Records

Owner-approved policy, 2026-09-29: operational logs may expire after 14 days.
Website logs and business records must **not** be deleted because of age or
storage pressure. Create a backup, download it, verify the saved copy, and only
then optionally remove explicitly selected backed-up server records.

This is separate from [catalog recovery](catalog-backup-and-recovery.md).
Catalogs, photos, current configuration and credentials are not removed by this
workflow. Backup & Records protects inquiry JSON, the full consistent analytics
SQLite database, and configured website log files. Use both backup types for
business recovery; neither is a full machine image.

## Admin workflow

1. Sign in and open **Backup & Records**.
2. Review disk usage and website-log coverage. Missing log configuration is an
   explicit warning, not a claim that all production logs were backed up.
3. Choose **Create backup**. A private persistent ZIP is created and verified on
   the server; preparation failure never triggers deletion to make room.
4. Download the ZIP to protected storage outside the production server.
5. Select that saved ZIP for verification. It is streamed back to the authenticated
   API for byte-count/SHA-256 comparison, without storing another uploaded copy.
   This avoids loading the whole file into JavaScript memory to hash it.
   Starting a download alone does not unlock removal. Selecting matching bytes
   proves the saved copy matches, not that its disk will survive future failure.
6. Optionally select source categories and type the displayed exact
   `REMOVE <backup-id>` confirmation. There is no automatic removal after download
   or verification. This changes the history available in analytics/reports and
   inquiry counts on this server.
7. A separate `DELETE BACKUP <backup-id>` action can remove the verified server
   ZIP while retaining its audit metadata. Source data is not affected by this
   action. Once the server ZIP is removed, it cannot authorize source removal.
   Keep a tested off-server copy, preferably an additional independent copy.

All endpoints use existing admin bearer authentication and no-store responses.
No public link, query-string token or new external storage provider is introduced.
ZIPs are not encrypted by the application: protect the download destination,
device account and any subsequent transfer. Archives can contain customer contact
information, legacy private analytics and email recipients; they are **not
anonymous exports**. They exclude environment files, SMTP/admin credentials,
GeoIP keys and unrelated server files.

## What optional source removal can do

- **Inquiries:** only byte-identical files from the selected backup with a
  completed email attempt (`sent`, `failed` or `unconfigured`). Pending inquiries,
  newer files and changed files remain. The application's inquiry writes and
  deletion share a lock; the supported production deployment is one API worker.
- **Analytics:** only byte/value-identical snapshot rows in completed-hour
  aggregate counts/items. Comparison includes the
  full row and its identity inside a SQLite write transaction. New/updated rows
  and the current incomplete hour remain.
  SQLite reuses freed pages; deleting rows does not necessarily shrink the
  database file immediately. Offline compaction is a separate reviewed operation,
  not an automatic blocking `VACUUM` during a live admin request.
- **Website logs:** only byte-identical sealed files. Live `.active` file prefixes
  are included in backups but cannot be removed. Logger rotation seals files;
  the admin page does not truncate a live writer.
- Email report content, delivery duplicate-prevention records, settings, tracking metadata and
  legacy personal-data tables remain. Privacy deletion requires separate review;
  clearing delivery claims could otherwise resend an already accepted email,
  while removing report snapshots could change the content of a pending retry.

The server rechecks archive integrity immediately before cleanup. A durable
removal claim prevents unsafe retries. Filesystem and SQLite operations cannot
be one atomic transaction: if a later step fails, earlier selected removals may
already have happened. The UI reports failure; the backup is retained and marked
for review, not automatically retried or deletable through the ordinary UI.
Restore/reconcile from that verified archive under operator supervision.

Overlapping backups are safe: missing or changed records are skipped, never
matched merely by an old timestamp. Backups are point-in-time per source: SQLite
is a consistent snapshot, inquiry copies are protected from concurrent writes,
and live logs capture a bounded byte prefix. This is not a globally atomic
snapshot across the database, mail system and all log writers.

## Retention and privacy

The scheduler still checkpoints SQLite and handles interrupted email claims,
but it no longer expires aggregate, legacy or report history by age. The previous
13-month aggregate, 30-day legacy and 90-day report-history automatic expiry rules
are superseded by this owner-approved policy. New identified tracking remains
disabled; retaining existing records does not re-enable it.

The existing legacy withdrawal endpoint and applicable privacy obligations remain.
An explicit privacy deletion must also be applied to relevant downloaded copies
and restored data; an archive is not permission to resurrect deleted personal
information. Retention changes require served-market privacy review before
production activation. Already deleted or never captured history is not recoverable.

Disk usage at 80% produces an admin warning. No size-triggered deletion is used
for protected data. Backup preparation requires a free-space reserve; a full disk
can still prevent new writes and backups. Plan capacity and monitor externally.
There is no automatic off-server upload or delivered low-disk alert in this feature.
Mailboxes and any external infrastructure logging have their own policies.

## Storage and production activation

- `STYL_RECORDS_DIR`: absolute private directory for ZIPs and the archive index.
  Defaults to `records` beside the configured analytics database.
- `STYL_WEBSITE_LOG_DIR`: absolute private, flat directory for the logging setup's
  sealed `.log`/`.jsonl`/`.gz` files and live `.active` streams.
- Never place either directory inside public assets or uploads, share them with
  one another, or expose them through Caddy. Symlinks/hard-linked source files
  are rejected. Use restrictive owner/group permissions and enough free space.
- The API must read website logs and remove eligible sealed files. Configure only
  that private directory, not unrestricted journal/root filesystem access.
- Keep one API worker and one records-management instance. These APIs coordinate
  in-process long operations; multiple independent API writers are not supported.

Follow [deployment logging instructions](lightsail-deployment.md) before enabling
14-day journal retention. First preserve existing website log history, configure
durable website capture, then validate runtime/access/error coverage. A journal
age/size cap applied before separation could destroy unarchived website logs.
Do not run forced vacuum, logrotate cleanup or historical backup deletion as
part of an ordinary application rollout.

## Offline verification and recovery

The ZIP contains a standard-library Python 3.11+ verification/recovery tool.
Prefer the trusted repository copy; do not execute tools from untrusted archives.

```powershell
.\.venv\Scripts\python.exe backend\app\records_archive.py "C:\PrivateBackups\styl-records-ID.zip"
.\.venv\Scripts\python.exe backend\app\records_archive.py "C:\PrivateBackups\styl-records-ID.zip" --destination "C:\PrivateBackups\recovered-records"
```

The destination must not exist. The tool validates paths, entry sets, sizes and
SHA-256 checksums before extraction, rejects links/duplicate entries and never
overwrites an existing installation. Read-only SQLite integrity validation is
also performed during server backup creation.

Extraction is not live restore: stop applicable writers/mail jobs under an
approved recovery procedure, reconcile newer records and prior privacy deletions,
then install selected recovered files with the correct private ownership. Never
copy a SQLite main file over a running WAL database. Review retained mail delivery
claims before restarting scheduling, to avoid duplicate notifications.

## Verification

- Backend: [test_records.py](../backend/tests/test_records.py), plus analytics and
  email-report suites for no-age-expiry and existing privacy/delivery safeguards.
- Browser: [records.spec.ts](../frontend/tests/e2e/records.spec.ts) exercises the
  isolated admin workflow at configured desktop/mobile browser projects.
- Portable recovery: complete entry/checksum comparisons and SQLite integrity,
  damaged/traversal archives, existing destination rejection.
- Production log migration, service signals/ownership, real disk-pressure alert
  delivery, large real archives and off-server disaster recovery remain separate
  operational checks; local test passes do not certify them.
