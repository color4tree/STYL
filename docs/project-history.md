# STYL project history and handoff

Last recorded: 2026-09-28

## Aggregate-only analytics without a customer agreement - 2026-09-28

The user explicitly replaced the earlier opt-in/session requirement with
aggregate-only analytics and no storefront consent panel. This supersedes both
the original identified-session MVP and the customer-visible status/consent
guidance recorded below; the change is not merely hiding the old tracker.

Implemented:

- Storefront tracking renders no agreement, banner or technical status. A normal
  footer Privacy link leads to plain-language information and an optional boolean
  measurement opt-out. Prior declines are preserved as opt-outs; old analytics
  consent/session/visitor/lease keys are removed. Admin, DNT/GPC, internal and bot
  exclusions remain. Storage failures fail closed without breaking shopping.
- Automatic first-party page/action measurement sends no browser/session/event
  IDs, exact timestamps, full referrers/queries or form contents. Fetches omit
  credentials and referrers. Initial page counts send promptly; subsequent
  bounded batches normally send every 15 seconds. Ambiguous deliveries are not
  retried because there are no deduplication IDs. Active-time estimates use a
  static exclusive Web Lock, not a saved per-tab identifier.
- The backend immediately stores independent hourly dimension and item/currency
  totals, not raw events or individual journeys. Legacy session creation returns
  410; identified/timestamped legacy event bodies are rejected. Invalid/private
  item references reject the entire batch. New reports exclude old session data.
- Dashboard, CSV and version-2 email previews use occurrence counts and average
  performance measurements. Unique/returning visitors, sessions, individual
  journeys, per-session funnels/rates and medians are explicitly not measured.
  Saved inquiries are separate business totals without new analytics attribution;
  unavailable totals, including displayed daily counts, are N/A rather than
  confirmed zeros. Dashboard includes the current hour; previews use completed
  hours. The 08:00 Pacific schedule and production-only mail safeguards remain.
- English/Chinese requirements, operations, architecture references, responsive
  and deployment guidance, README and AN-001..014 assertions were updated.
  Aggregate-only measurement is not claimed universally consent-exempt; privacy
  review remains a production activation gate.

Final automated candidate: dirty `main` on `d874a8e`, with SHA-256 prefixes
`607b9703bf60101f` (backend analytics), `c8f54c9de6097708` (report job),
`40d897a46681f624` (browser tracker), `dd79997374521b10` (dashboard) and
`020a287b8db676445` (analytics E2E).

Verification:

- Backend focused analytics: **49 passed**; complete backend unittest discovery:
  **149 passed**. Pylance/editor checks were clean and the ingest signature was
  checked against its resolved call sites.
- Frontend `npm --prefix frontend test`: **33 passed**, including 23 aggregate
  analytics/privacy cases and the preserved cart/unit coverage.
- Targeted analytics E2E: **27 passed**. Final complete
  `npm --prefix frontend run test:e2e`: **181 passed** across desktop Chromium,
  phone Chromium and phone WebKit, one worker and no test retries. Production
  build/TypeScript passed, including existing quote-frame, media, cart, admin,
  ordering and recovery regressions. Full lint: zero errors and the same five
  pre-existing image warnings; changed-file lint/editor checks clean.
- The first full frontend attempt was blocked by OneDrive's read-only/reparse
  attribute on one generated Next build-ID directory. Inspected and removed only
  that exact generated directory, then the complete final run passed in 5.2 min.
- Restarted only the verified local API. Real local health/config advertise
  enabled aggregate-only collection with email disabled. Authenticated local
  dashboard and customer/footer/Privacy layouts were checked at desktop/320px.
  Those visual checks used DNT, so they did not inflate local traffic. Actual
  automatic collection -> stored counts -> dashboard/CSV/preview was verified
  against the real isolated E2E API. Temporary local verification script removed;
  screenshots remain private session artifacts.

Legacy private analytics data was not destructively migrated: maintenance bounds
old raw/session data to 30 days and old rollups/new aggregates to 13 calendar
months. Existing inquiry JSON and protected backups, including any historical
attribution fields, were not rewritten and require separately approved cleanup
or expiry. User catalog data and existing edits were preserved.

Full automated baseline passed; this does not certify every operational/manual
plan clause. Physical devices, production privacy/activation, real email inbox
delivery, production-volume performance and deletion/backup replay remain
unverified. No commit, push, production deployment or real email was performed.

## Local zero-traffic diagnosis and clearer status - 2026-09-28

Investigated the user's all-zero analytics report against the running local API,
authenticated current-day/seven-day reports and safe flags from the shared
localhost browser. Collection was enabled in the local/Pacific environment, but
the inspected browser had no saved consent or analytics session and the report
had no retained browsing events. Its storage was readable and no admin token,
internal exclusion, DNT or GPC was present. This evidence does not establish the
state of a different browser/hostname. No collector/report counting defect was
reproduced: a separate opted-in customer context increased stored page views
from 0 to 1 through the normal automatic batch timer, without forcing a flush.
Only that synthetic session was revoked afterward; user consent/catalog/data
were unchanged and synthetic traffic was not left in business totals.

Added persistent footer collection status, a zero-visit dashboard guide covering
consent, admin exclusion, separate customer windows, hostname storage, date
ranges, the 15-second batch timer and manual refresh. Disabled collection has
its own explanation. The report displays generation/last-event timestamps in
the report timezone and clarifies that server exclusion counts cannot measure
visits stopped before sending a request. Malformed timestamp/timezone responses
are rejected with the existing explicit invalid-report error, not a render crash.
Consent/exclusion/collection policies were not changed.

Final targeted verification on the dirty `d874a8e` candidate:

- `npm --prefix frontend run test:e2e -- analytics.spec.ts`: **24 passed**,
  desktop Chromium, phone Chromium and phone WebKit, real isolated collector,
  no retries. Includes ordinary timer -> stored count -> refreshed dashboard,
  no pre-consent IDs, same-tab admin exclusion, disabled-collection guidance,
  malformed date/timezone responses and an actual 320px document-width check.
  The harness production build and TypeScript validation passed.
- `npm --prefix frontend test`: **37 passed**. Scoped ESLint for the three changed
  frontend/test files: zero errors/warnings; editor diagnostics clear.
- Real local dev public/admin UI verified at 1440px and 320px without changing
  the user's browser. The initial headless visual probe was correctly excluded;
  the positive probe then used the regression suite's realistic test UA.
  The existing shared tab needs reload to pick up the new footer/status UI.
- Candidate SHA-256 prefixes: AnalyticsManager `99676dfa23db3198`,
  AnalyticsTracker `dc881d087b0a4812`, analytics E2E `34133aecef4dff84`.
  Updated AN-001/007/009/010 and local operations guidance. Screenshots remain
  private session artifacts; temporary verification scripts were removed.

This was targeted analytics verification, not a new full-system regression,
physical-device test or production rollout. No commits, pushes, production
changes or real emails were made.

## Visual arrange mode on existing catalog cards - 2026-09-28

The user found the separate ordering list confusing and requested up/down
controls directly on each listing card. Replaced it with Arrange listing order /
Done arranging mode for both products and accessories. The existing image, name,
prices and publication state remain on the same cards; there is no duplicate
list or position dropdown. A successful move changes the actual list position,
highlights/focuses the moved card and retains immediate saving, boundary buttons,
conflict handling and unsaved editor fields. Done restores normal item selection.

The user also requested a skill to avoid routine testing permission questions.
Added [styl-autonomous-testing](../.github/skills/styl-autonomous-testing/SKILL.md)
and linked it in project instructions. This governs already-authorized execution
and explicitly cannot bypass native VS Code/organization tool confirmations.
The npm command was already allowlisted in both inspected User and workspace
settings; no claim was made that adding a skill disabled the platform prompt.

Validation: all 15 initial arrange-mode cases passed. A broader run exposed
long-name overflow when an arranged item reached the cart: a reproduced 390px
phone layout widened to 1,918px, and its add notice also overflowed. Added minimum
width constraints to cart grid children and wrapping to feedback; the same local
probe then remained at 390px. Regression assertions compare against the configured
viewport, not a mobile layout viewport that can itself expand.

Final targeted regression: **108 browser executions passed** across catalog
editing, arrangement/cart feedback, backup, dates and analytics, including desktop
Chromium, phone Chromium and phone WebKit. Production build/TypeScript passed;
37 frontend unit tests passed; scoped lint had no errors and two pre-existing
image warnings. Local visual checks confirmed a single card list, per-card arrows,
Done mode and 320px layout without changing the user's saved catalog order.
Updated ADM-011/USR-016 and the responsive/README guidance. This was targeted
frontend validation, not a new full backend/physical-device/production run.
No commit, push, deployment, real email or user catalog edit was performed.

## Country-level traffic analytics completed locally - 2026-09-28

Completed the missing analytics backend directly after the delegated backend
worker was cancelled. The integrated local MVP now includes:

- Explicit opt-in before behavioral identifiers/events, separate optional
  30-day remembered-browser choice, DNT/GPC/internal/admin/bot exclusions,
  consent withdrawal and deletion of linked raw history.
- Private environment-separated SQLite collection with server-derived country/
  currency and market-eligible public item metadata, strict event/size/rate
  validation, event/page/impression deduplication and sanitized diagnostics.
  No raw IP, full query string, customer form contents or raw session bearer
  token is persisted in the analytics store.
- Page/navigation/item/media/cart/quote tracking, active-time interval unions
  across tabs, cross-midnight allocation, ordered funnel, source/campaign/device
  breakdowns, current-item interest and hourly/daily aggregates.
- Optional server-validated inquiry attribution, business receipt totals and
  idempotent reconciliation without copying private customer fields. Lost
  browser batches or analytics write failures do not lose a saved inquiry.
  Revocation prevents the old private inquiry association being reattached.
- Admin Analytics date-range reports, item filters, aggregate CSV, daily email
  previews, delivery history, data-quality warnings and explicit unavailable
  states. Open catalog editors and the existing Backup view remain intact.
- Daily report generation for 08:00 America/Los_Angeles, five-minute ingestion
  cutoff, per-recipient durable claims, bounded retries and ambiguous-send review.
  Production-only email enablement and separate recipients are required. Local
  sending is disabled; service/timer templates are provided but not installed.
- Retention maintenance, historical daily rollups with honest unique-count/rate
  limitations, and consistent private SQLite backups. City/ZIP, raw individual
  session drill-down, AI chat and CRM/revenue attribution remain deferred.

Final current-working-tree automated baseline on `d874a8e`:
**141 backend tests, 37 frontend unit tests and all 166 configured browser
executions passed**, including the 21 previously unfinished analytics integration
executions across desktop Chromium, phone Chromium and phone WebKit. Production
build/TypeScript passed; lint had zero errors and the same five image warnings.
Pylance/editor diagnostics for the new implementation were clear.

The new backend checks cover consent and safe identifiers, forged country data,
private/draft exclusion, source/campaign minimization, no form/token leakage,
same-ID and semantic page/impression retries, overlapping active intervals,
23/25-hour DST days, midnight splits and seven-day daily averages, retention,
withdrawal without attribution resurrection, failed-inquiry reconciliation,
auth/CSV/HTML handling, real-store disabled job execution and SQLite backup.
The report tests additionally cover per-recipient/case/version deduplication,
concurrency, definite/ambiguous SMTP outcomes and bounded retries.

Actual localhost checks exercised opt-in collection -> stored page view ->
authenticated admin report -> daily preview, including 320 px layout. The daily
job ran with sending disabled and maintenance succeeded. The synthetic local
visitor history was revoked afterward; no catalog edits or actual inquiry/email
sends were made in that smoke test. Only the local API was restarted.

One intermediate browser test used an ambiguous alert selector and was corrected
to the admin main content. A specific inspected OneDrive-generated manifest
directory blocked a build and was safely removed before the successful reruns.
The emitted chunk containing tracker/consent code (including shared code) measured
13,885 gzip bytes; this does not establish total incremental JS or field performance.

Analytics integration fingerprint:
`62116e820871e9de4c47629d7ac46c1f0331b5ff5888cfdd1c6f8b2a0e2cf583`.
Ordered inputs were backend app analytics/analytics_reports/main, backend tests
test_analytics/test_analytics_reports, frontend lib analytics/analyticsTypes,
AnalyticsTracker, admin AnalyticsManager/page and E2E analytics.spec. The verifier
hashes each relative filename, a NUL, its bytes and a NUL. Temporary verification
and smoke scripts were cleaned up after validation.
Promoted AN-001..014 to the active local regression map and updated
[operations](traffic-analytics-operations.md) plus the English/Chinese requirements.

This is completion of local implementation and the automated code baseline, not
the full manual/production plan. Actual production collection, report recipients,
mailbox delivery, timer operation, physical devices, field/load measurements,
external alerts and production backup restore/deletion replay remain separately
gated. No commit, push, deployment or production tracking was enabled by this task.

## Immediate cart confirmation and manual listing sequence - 2026-09-28

The user requested visible add-to-cart feedback and admin position controls.
They explicitly chose manual order as the exact display order for both catalogs,
replacing the previous Featured-first homepage sort.

Added a shared Add to cart control on product/accessory cards, product detail and
its mobile sticky action. A successful write shows a check icon and Added for
2.5 seconds; a failed add shows Not added. Accessible cart notices include the
updated sale-unit count, and a capped/no-quantity-change operation is not claimed
as an addition. The ten-unit limit and existing cart behavior remain.

Each admin catalog has Arrange listing order with position selectors and
keyboard/touch-friendly up/down buttons. Moves save immediately without saving
or discarding open editor fields. The protected API validates a full permutation
and expected prior order under the shared catalog lock; stale order/item-set
changes return 409 rather than overwriting another session. Record fields are
preserved, new items append, and customer market/draft filtering retains relative
order. Featured remains an explicit metadata tag, not a sorting override.

Validation:

- Eight new backend ordering tests passed; the current complete backend runner
  passed 118 tests (including existing backup and isolated report-job tests).
- All 37 current frontend unit tests passed.
- The final established storefront/admin browser set plus new feedback/order
  cases passed **145 executions** across configured projects, including 21 new
  feedback/order executions. Production build/TypeScript passed.
- Lint had zero errors and the five existing image warnings; edited files had
  no editor errors. Backend's existing contextmanager annotation hint is unchanged.
- Fixed a genuine narrow WebKit overflow with long item names by allowing the
  admin list grid items to shrink and wrap. Tightened a date test to target the
  named Captured date input rather than the first (now possibly hidden analytics)
  date input. Corrected a sticky-action test fixture so it has enough detail
  content to scroll the inline action offscreen.
- Actual localhost browser checks confirmed immediate feedback at desktop/phone
  widths and both admin ordering panels without horizontal overflow at 320 px.
  Test cart data lived in isolated browser storage; real saved catalog ordering
  and other user data were not changed.

Important scope boundary: the prior analytics storage/API worker was cancelled
without a completed backend. Analytics frontend/report code remains work in
progress. Its integration spec was explicitly excluded from the 145-test run;
this is not a full analytics pass or a claim that analytics is operational.
Added SYS-019, ADM-011 and USR-016 coverage and updated the current ordering oracle.
Only the local API was restarted; no production changes, email, commit, push or
deployment occurred.

## Admin catalog ZIP and offline crash recovery implemented locally - 2026-09-28

The user requested catalog download in admin, deferred upload/import, and recovery
after loss of the production server. They confirmed catalog-only scope: saved
products/accessories including drafts, IDs/slugs, prices and private metadata,
banner and all referenced local/static images, videos and posters. Inquiries,
credentials, machine configuration and application code/build remain separate.

Added an authenticated Backup view with privacy/saved-data notices, progress,
duplicate-click prevention, filename handling, explicit errors/retry and retained
editor state. The API builds a disk-backed, no-store/private ZIP under the shared
catalog mutation lock. It uses strict saved-data reads rather than seed fallbacks,
deduplicates shared media and rejects missing/external/unsafe media instead of
claiming an incomplete backup is recoverable.

Each version-1 archive includes SHA256/size metadata, RESTORE.txt and a standalone
standard-library Python recovery tool. Verify/restore checks entries, schemas,
references, checksums, limits, unsupported versions and unsafe ZIP paths/types.
Restore refuses an existing destination and publishes a verified staged recovery
to a new directory. Browser upload/import remains unimplemented.
See [catalog backup and recovery](catalog-backup-and-recovery.md).

Verification against `d874a8e` plus the reviewed working-tree backup changes:

- Final full automated baseline: **92 backend tests, 9 frontend unit tests and
  124 production-build browser executions passed**. Build/TypeScript passed;
  lint had zero errors and the five pre-existing image warnings.
- The backup-specific suite includes 20 backend cases and 21 browser executions
  across desktop Chromium, phone Chromium and phone WebKit.
- The cold-recovery test downloaded the real API ZIP, removed the original
  fixture catalog/media, executed the bundled tool without the original server,
  compared recovered bytes and started a fresh API process on restored storage.
  IDs, private metadata, drafts, market visibility, banner, images/posters and
  video byte ranges were verified. Fixture video data tests byte preservation,
  not actual visual playback quality.
- The actual local admin UI downloaded a 369,342-byte archive containing 4
  products, 11 accessories and 16 referenced media files. Independent verify and
  restore into a private temporary directory succeeded; a 320 px UI check passed.
  The temporary copies were removed and the user's saved data was not edited.
- Intermediate test fixtures were corrected to use the real /api/uploads/ prefix
  and UUID-style uploaded-video paths. A narrowly inspected generated .next
  directory was removed after a Windows build-cache error; no source was deleted.

Code/test candidate SHA256:
`f206cf0cd8785cb7188e1fa656f46eba810b64a72c5dc0ce6abaea1cae57ba91`
(ordered filenames and bytes: backend main/catalog_backup/test_catalog_backup,
frontend admin page/CatalogBackup/catalog-backup.spec, Playwright config).
Added SYS-017/018, ADM-010, OPS-011 and deferred FUT-008.

This passes the automated code baseline, not the entire manual operational plan.
Real production archive recovery, large-volume/mobile download limits, physical
file-save behavior and video playback on a replacement installation remain manual
checks. Only the local API was restarted. No production download/restore, email,
commit, push, deployment or backup-branch update was performed.

## Chinese AI customer-service architecture copy - 2026-09-28

Added a separate [Simplified Chinese architecture copy](customer-service-ai-architecture.zh-CN.md)
at the user's request. Translated all seventeen sections, three architecture/
sequence diagrams, two UX wireframes, ten readiness gates and twenty acceptance
cases, preserving technical endpoints/state codes and draft approval boundaries.
Added plain-language terminology explanations and a README link. The English
source remains unchanged; no application, service, provider or deployment change.

## Chinese traffic-analytics requirements copy - 2026-09-28

At the user's request, created a separate
[Simplified Chinese translation](traffic-analytics-requirements.zh-CN.md) of the
traffic-analytics requirements, using plain-language explanations for readers
with basic English. Preserved all twelve sections, TA-001..014, AN-001..016,
proposed defaults, Phase 2 city/postal priority and privacy/approval limits.
Added a reading glossary and README link. The English source is unchanged;
this is documentation only, with no application or deployment changes.

## AI-assisted customer-service architecture drafted - 2026-09-28

The user requested a current/future architecture for AI-led customer chat with
human fallback, UX and prerequisites; MUSE/CoWork/other provider choice remains
undecided. Added [the architecture draft](customer-service-ai-architecture.md)
with current STYL components, provider-neutral boundaries, approved knowledge
and read-only tools, a durable human queue, named staff access, takeover fencing,
offline follow-up, desktop/mobile wireframes, privacy, cost/operational controls,
phased delivery and twenty future acceptance cases.

Linked optional aggregate support outcomes to the analytics/daily-email draft
without permitting transcripts or contact data in analytics. City/postal analytics
remains Phase 2 / P2 and is not a chat dependency. Recorded FUT-007 and AN-016 as
future-only cases. No AI provider was selected or contacted, no real customer
data was shared, and no chat code, service, tracking, emails or deployment were
enabled. Existing catalog edits and local development settings were preserved.

## City and postal analytics deferred to second priority - 2026-09-28

The user requested city/ZIP information for traffic reporting, with second
priority if another MaxMind package is required. Updated the
[requirements draft](traffic-analytics-requirements.md) to place approximate
city/region/postal-area enrichment in Phase 2 / P2 (TA-014, future AN-015).
It requires the additional GeoLite2 City database, not a mandatory paid
subscription. Country analytics and daily email remain first-release scope.
Documented missing/partial postal data, accuracy limitations, aggregate privacy,
and preservation of the existing Country/CAD/USD path. No database download,
application change, tracking, purchase or deployment was performed.

## Traffic analytics and daily summary requirements drafted - 2026-09-27

The user requested a requirements draft for access timing, IP/country, item
interest, navigation, active time and daily usage emails. Added
[traffic analytics requirements](traffic-analytics-requirements.md), covering
business questions, event/metric definitions, quote attribution, admin reporting,
consent/privacy, retention, exclusions, reliability and a daily scheduled summary.

Recommendations include country lookup without raw-IP business histories,
separate optional restricted security logs, visible/active-time estimates,
server-confirmed inquiry conversion, and aggregate-only daily email. Proposed
delivery time, timezone, recipients, consent mode and retention require owner
review. First-party collection and a separate SQLite analytics store are proposed,
not implemented. Future acceptance cases AN-001..014 are linked as FUT-006.

Documentation only: no tracking code, visitor collection, database, scheduled
report, real email, application configuration, deployment or commit was enabled
by this drafting task. Existing catalog edits and development instructions remain
untouched.

## Production GeoIP activated and US pricing verified - 2026-09-27

After embedded-browser AWS authentication failed, the user continued through
Edge's Ubuntu-1 SSH terminal. They confirmed the replacement MaxMind credential
configuration was installed, the authenticated download succeeded, and the
reviewed updater/service/database installation reported
`UPDATER AND DATABASE READY`. The server's real-MMDB CA and US sample checks and
service invocation succeeded.

Published release `bc45b22` contains the updater, timer, tests, configuration
example and authorized 12px MaxMind/GeoNames attribution. The user ran the reviewed
activation block and confirmed `GEOPRICING ACTIVATED`: a separate frontend build,
configuration/build backups, API database-path setting, explicit loopback-only
Uvicorn proxy trust, API/web restart, and scheduled updater enablement.
Configuration/build rollback materials are in the root-only directory
`/var/backups/styl/geoip-activation-bc45b22`. The database is outside normal catalog
backups; Caddy's existing domain forwarding rules were not changed.

Independent live verification:

- Public market requests returned US / USD / located with `no-store, private`.
  Forged Canadian X-Forwarded-For, X-Real-IP and CF-IPCountry headers produced the
  same US result. The integrated browser also displayed the actual US response.
- Public products returned 3 USD items, accessories 16 USD items, and selection
  19 USD items. Health returned 200. Counts reflect current production data,
  not a fixed contract or a copied Canada price.
- All six storefront currency/attribution/layout checks passed across desktop
  Chromium, phone Chromium and phone WebKit. The additional WebKit no-runtime-
  errors assertion failed on the previously recorded RSC-prefetch access-control
  warning during navigation; that warning remains unresolved.
- The user confirmed the final `GEOIP VERIFIED AND TRANSFER FILES CLEANED` block:
  second updater invocation successful with API PID unchanged, timer enabled,
  database readable but not writable by the API, root-only credentials, matching
  catalog/Caddy checksums and unchanged non-GeoIP environment (including SMTP).
  Temporary server transfer keys/ciphertext/setup scripts/private download logs
  were removed without printing their contents.

Production now detects public IP countries; localhost deliberately remains
unknown/CAD. No visitor IP is sent to MaxMind for lookup. A real Canadian visitor
test and observation of the next scheduled update are still pending; external
updater-failure alerts are not configured. No actual quote emails were sent during
verification. User local catalog edits and the backup branch were preserved.

## Production GeoIP preparation and updater validation - 2026-09-27

The user authorized production country detection, automatic updates, and a very
small attribution footer after the successful local database setup.
Installed Ubuntu's `geoipupdate` 6.1.0 package on Ubuntu-1 and disabled its default
timer pending STYL-specific configuration. Backed up the prior API service,
Caddy and environment under `/etc/styl/geoip-backup-20260928T045300Z`; existing
catalog/Caddy checksums were recorded. The live domain already overwrites
forwarded client IPs. The API's explicit loopback proxy flags still need activation.

The first hidden-prompt credential entry was exposed by the browser tool's
retained input state. The user was notified and confirmed revoking that key and
creating a replacement. The replacement was read from the user-designated local
configuration without displaying it, encrypted to a fingerprint-verified server
public key, and transferred as ciphertext. After embedded AWS login expired,
the user continued in Edge's SSH terminal and confirmed the protected replacement
configuration was installed and `GEOLITE DOWNLOAD OK`. Replacement credentials
were not printed or committed.

Added a root-run updater that validates type/age, atomically publishes a mode-0640
database readable by the API group, suppresses provider output from logs, and
removes >30-day database copies on each run. A twice-daily randomized persistent
timer and a credential-free example configuration are included. Cache/published
data live outside the catalog backup directory. Added the authorized compact
MaxMind/GeoNames footer attribution and GEO-008/009 regression cases.

Validation: all 72 backend tests passed (including ten new updater tests); all
55 selected market/quote browser executions passed with production build and
TypeScript; lint had no errors and five existing image warnings. An ambiguous
mobile Add to cart readiness selector was scoped to the Request quote link after
the sticky action appeared in an intermediate run. No live inquiry emails sent.

At this preparation checkpoint, the production database is downloaded but not
yet published to the API, the scheduled STYL updater is not enabled, and the
attribution frontend has not been deployed. Complete and record those operations
before claiming live country detection works.

## Local MaxMind Country database enabled - 2026-09-27

The user created a MaxMind account and explicitly selected local setup before
AWS configuration. They downloaded GeoLite2 Country binary data and its matching
checksum. The first checksum supplied was for the CSV ZIP; it was not used to
verify or install the binary archive. The correct binary checksum subsequently
matched:

- Archive: `GeoLite2-Country_20260925.tar.gz`, 4,420,208 bytes.
- Archive SHA256: `5c3cb833a65e7dd2975ea0c790fec211863ad10c29aa0c5a66376dcc1dbcada3`.
- Installed MMDB: 8,441,997 bytes; type `GeoLite2-Country`; build
  `2026-09-25T12:18:30Z`; IPv4/IPv6 support.
- MMDB SHA256: `a4c816daf2837559ce2a6470ae59e285ac4666e4535315b4b22adbbf66ef229c`.

Installed under `%LOCALAPPDATA%\STYL\GeoIP`, outside Git and OneDrive. Retained
the bundled license/copyright files and verified Windows ACLs limited to the
developer account, SYSTEM and Administrators. No credentials or database files
were added to the repository.

Updated the ignored local API launcher to supply `STYL_GEOIP_DATABASE` unless
already overridden, then restarted only the verified local API using the existing
VS Code task. The repository virtual environment already contained the required
MaxMind reader; no dependency installation or application-code change was needed.

Verification:

- Real MMDB records returned CA for `24.48.0.1`, US for `8.8.8.8`, GB for
  `81.2.69.142`, and US for `2001:4860:4860::8888`.
- Seven application integration cases used the real MMDB, simulated ASGI client
  addresses, disposable catalog JSON and no SMTP. CA/unknown mapped to CAD;
  US/GB mapped to USD. IPv4-mapped IPv6, exact configured prices, missing-market
  list/detail/selection visibility, no-store headers and ignored forged country/
  forwarded headers all passed. Temporary catalog fixtures were removed.
- All 17 existing GeoIP tests passed, covering missing/corrupt/replaced databases,
  fallback, concurrency and privacy behavior.
- Running local API health returned 200. Loopback market remained unknown/CAD,
  with or without spoofed headers, as designed. The user's three visible local
  products and three accessories remained available; their saved data was not edited.

This is local configuration verification, not a full regression or real visitor/
proxy certification. No license key, scheduled database updates or AWS GeoIP
configuration was added. Production remains on its previous unknown/CAD fallback.
No push, deployment, real email, or production-data operation was performed.

## Catalog and quote UI deployed - 2026-09-27

With explicit user approval, committed/pushed the pending frontend, tests and
related documentation as `08f1334` on `main`, then deployed it to Ubuntu-1 at
2026-09-28 04:04 UTC (September 27 Pacific time). This includes aligned catalog
cards, 21rem desktop previews with subtle italic Show more, complete mobile
details, numbered multiline quote messages, and the quote-navigation flash fix.
The user's local product/accessory JSON edits and untracked banner configuration
were excluded from the release. The backup branch remains at `91f3d3d`.

The data-backup service succeeded. Preserved the prior frontend build and protected
environment/Caddy/web-service configuration in the root-only directory
`/var/backups/styl/ui-release-20260928T040100Z`. Fast-forwarded the production
checkout from `608df88`, preserving existing deployment-script mode changes.
Built the exact candidate in a separate temporary directory, using unchanged
installed dependencies and same-origin API requests. Build and TypeScript passed.
Replaced the built frontend and restarted only `styl-web`; API and Caddy remained
active. The predeployment automated baseline was 101 browser executions and nine
unit tests, with zero lint errors and five existing image warnings.

Targeted live verification:

- Six catalog checks across desktop Chromium, phone Chromium and phone WebKit
  passed: aligned desktop cards, 336 px preview limit, italic overflow controls
  and complete expansion, plus full unmasked mobile details without controls.
- Eighteen cart/product/header quote transitions passed across those browsers
  with normal/reduced motion and separately delayed cart/catalog GET responses.
  Every sampled form/header gap was 16 px. Name stayed visible, and numbered
  multiline cart messages and product-only context were retained.
- Tests used isolated browser storage and read-only production requests.
  No inquiry was submitted, no email was sent, and no customer/catalog record
  was modified. No browser runtime errors occurred.
- HTTPS home, cart, accessories, admin, health, both catalog APIs and market
  endpoint returned 200; the web service started normally.
- Before/after checksums matched for environment, Caddy, products, accessories
  and banner data. The API kept its predeployment process/start time, and the
  environment file remained root-owned mode 0600, preserving SMTP configuration.

Removed the temporary build directory and repeated live verification. Repeat
automation intermittently stalled waiting for catalog/product content, at both
five- and twenty-second readiness limits. Immediate browser diagnostics showed
the populated homepage without errors; server logs showed normal startup and
HTTP 200. A later complete post-cleanup run passed all six catalog and eighteen
frame-transition checks. The intermittent loading cause was not established.
Independent checks without request interception rendered home/accessory/product
pages in all three configurations; WebKit additionally reported RSC-prefetch
access-control errors during rapid programmatic navigation. These repeat-run
warnings are recorded for follow-up, not claimed fixed by this deployment.

This is targeted live deployment verification, not a new full backend regression
or physical-device certification. Outstanding GeoIP provisioning and independent
mailbox-delivery checks are unchanged.

## Quote navigation flash corrected before paint - 2026-09-27

The user reported a flash on the cart-to-quote transition even though the final
content was correct. Local animation-frame traces reproduced two competing
scroll steps: Next's early `scrollIntoView`, then the navigation hook's later
`scrollTo`. The desktop form/header gap moved from 88 to 16 px; mobile briefly
moved from 15 to 161 to 16 px as the selected-cart summary appeared. The new
USR-015 transition test failed against the old implementation.

Quote links in both cart actions, product detail, and desktop/mobile header now
disable Next's automatic scroll. The hook aligns initial homepage layout commits
in a layout effect before paint, stopping once initial loading settles or the
user interacts. Direct hash targets also receive the viewport-height space from
CSS before hydration. No timed scroll loop, hidden-page workaround or forced
input focus was added. Quote text, interruption protection and later price-refresh
behavior are preserved.

After the fix, all sampled local cart-transition frames stayed 16 px below the
header on desktop/mobile, with both normal responses and delayed catalog data.
USR-015 samples intermediate positions while separately releasing cart and catalog
responses for cart/product/header links, normal/reduced motion, and all three
configured browser projects (18 combinations). The existing desktop wheel test
now waits for actual wheel-event delivery before releasing delayed data; the
browser automation's wheel dispatch does not itself wait for that delivery.

Final current-working-tree frontend validation (base `608df88` plus pending UI
changes): all 101 configured browser executions and nine unit tests passed,
including production build/TypeScript. Lint had no errors and the same five image
warnings; editor diagnostics were clear. Updated USR-015, related plan references,
responsive design and README. This was full frontend automation, not a new backend
regression or physical-device certification. No live inquiry/email, catalog-data
edit, push, backup-branch update or deployment was performed.

## Softer italic Show more styling - 2026-09-27

At the user's request, replaced the warm highlight and bold label with a subtle
neutral background, light border, muted text and regular-weight italic label.
Retained the underline, dots, arrow, hit area and existing desktop/mobile behavior.
Updated the design and USR-014 assertions for the new appearance.

All six targeted browser executions passed with production build/TypeScript;
lint had zero errors and the five existing warnings. The color assertion accepts
equivalent RGBA/Oklab serialization. Cleared only inspected generated production
build folders after Windows unlink failures, then reran successfully. Verified
and visually inspected the final localhost control. No data changes or deployment.

## Make Show more easier to notice - 2026-09-27

The user found the plain expansion row easy to miss. Added a decorative "..."
overflow cue, semibold underlined label, warm tinted background, outlined rounded
button and at least a 48 px hit area. The dots disappear when expanded and are
excluded from the accessible name. The 21rem desktop cap and full mobile details
are unchanged. Updated USR-014 and responsive design.

All six targeted product/accessory layout executions passed across desktop/phone
Chromium and phone WebKit, including production build/TypeScript, keyboard/focus,
alignment and breakpoint checks. Lint passed with the five existing image warnings
and no errors. Verified the rendered localhost button styling and hidden mobile
control, and inspected its screenshot. This was targeted validation, not a full
regression or physical-device check. No catalog changes, push or deployment.

## Taller desktop previews; complete mobile details - 2026-09-27

The user requested a 50% longer default preview and no detail truncation on
mobile. Increased the desktop cap from 14rem to 21rem (224 to 336 px at default
text size). Truncation, fade and Show more/less now apply only at the existing
1024 px desktop breakpoint and above. Narrower layouts display the complete
details, including the two-column tablet layout. Returning to desktop retains
the card's expanded/collapsed choice; alignment and full names/prices are unchanged.
This supersedes the all-width preview limit described in the previous entry.

The revised desktop tests first failed on the old 224 px cap. Eight focused
layout/accessory workflow executions then passed, followed by all 39 selected
catalog-layout and quote-navigation executions across desktop Chromium, phone
Chromium and phone WebKit, including production build/TypeScript. Tests cover
1023/1024 px boundaries, full unmasked mobile content, hidden mobile controls,
desktop expansion state across resizes, aligned rows, and 200% text scaling.
Lint passed with zero errors and the five existing image warnings; an initial
lint attempt overlapped Playwright's temporary result-directory cleanup and was
rerun after that cleanup finished.

Refreshed the stale local development CSS cache using verified local-server
control, then checked both actual local catalogs at 1440/1024/1023/390/320 px:
desktop used the 336 px cap; narrower layouts showed full unmasked details and
no visible expansion controls. No saved catalog data was changed.
Updated USR-004/014 and responsive design. This was targeted frontend validation,
not a new full regression or physical-device certification. No push, deployment,
production changes, or real inquiry/email sends were performed.

## Detail previews clarified: hide only overflow - 2026-09-27

The user clarified that the earlier arrow design hid too much: details should
remain visible by default, with only excess content concealed to align cards.
This supersedes the closed-accordion design recorded immediately below.

Products and accessories now show a single details preview containing the summary,
description, features, use, compatibility and supplied specifications. It is
capped at 14rem (224 px with default text size), with a faded cut-off and Show more
only when the content actually overflows. Short content has no toggle; empty
content has no details section. Show more reveals all content and Show less
restores the preview, without duplicating the summary. A resize observer updates
the overflow control as the layout or text size changes. The visible fit-check
cue, full names/prices/units, galleries and product detail links are retained.
Shared rows continue aligning card bottoms and purchase controls when expanded.
Multiline quote formatting is unchanged.

Validation: both new visible-short-detail assertions failed against the closed
accordions before implementation. Eight targeted browser executions passed after
the correction, then all 83 configured frontend browser executions and nine unit
tests passed, including production build/TypeScript. Lint had zero errors and
the same five image warnings; editor diagnostics were clear. USR-014 now checks
initial detail visibility, bounded previews, overflow-only controls, complete
expansion, no overlap, keyboard/focus/ARIA behavior, and control appearance/removal
after resizing and 200% text. USR-004 and the design oracle were updated too.

The local dev server again retained superseded CSS; rebuilt only its generated
development cache. Fresh-browser checks and screenshots then verified the user's
current three CAD products and three CAD accessories with 224 px previews and
working mobile expansion/collapse. Saved catalog edits were left untouched.
No backend source changes, production writes, live inquiry emails, push or
deployment were performed. Physical-device and screen-reader checks remain
unverified. The updated preview is available locally.

## Readable quote messages and aligned catalog cards - 2026-09-27

The user requested line-by-line quote text and consistent product/accessory
cards, then selected inline expandable details with a down arrow rather than a
dialog. Implemented on `main`, based on `608df88`, without pushing or deploying.

- Cart quote messages now use numbered item blocks with separate quantity,
  known package contents, and currency-labelled unit-price lines. Items and the
  final pricing/delivery request are separated by blank lines. Each/Pair/Set
  semantics and legacy unspecified units remain explicit. Product-only requests
  use the same paragraph structure without inventing a quantity or price.
- The editable message area grows from eight to at most eighteen rows. User
  changes survive errors, and exact line breaks reach saved inquiry JSON.
- Both catalogs reuse one card presentation, with aligned media/category/name/
  price/summary/contents/disclosure/action rows. Names remain complete; short
  previews use at most two lines, with full text available in Details &
  specifications. Native keyboard-operable disclosures have rotating chevrons.
- Compatibility and specifications are now inside the approved inline listing
  disclosure, with an explicit visible fit-check cue. Product detail-page
  compatibility is unchanged. Expanding a card stretches its desktop/tablet
  row so the purchase controls stay aligned; mobile cards grow individually.
  Empty fields/disclosures are omitted, and media/cart/detail links remain.

Evidence:

- Before implementation, the new desktop fixtures reproduced card-bottom
  differences of 416 px for products and 875 px for accessories. All four new
  browser scenarios and three changed/new quote unit assertions failed.
- Final full frontend validation: nine unit tests and all 83 configured browser
  executions passed, including production build/TypeScript; lint had zero errors
  and the same five image-optimization warnings. The new E-LAYOUT suite adds
  twelve executions across desktop Chromium, phone Chromium, and phone WebKit.
- An intermediate full run exposed an ambiguous old product-name test selector
  after nested detail headings were added. Scoped the name lookup and preserved
  hierarchical detail headings; the complete rerun passed.
- Additional explicit disclosure/action non-overlap assertions passed all twelve
  E-LAYOUT executions. Widths 320/390/768/1280/1440, two-line previews, complete
  expanded content, empty details, keyboard toggles, and 200% text are covered.
- Inspected local desktop/mobile/expanded/quote screenshots using read-only
  public catalog data with isolated browser storage. A stale local development
  cache initially served superseded seven-row CSS; a clean dev-cache rebuild
  restored the current eight-row layout. The fresh production test builds were
  unaffected. No catalog data or credentials were changed.

Added USR-013/014 and updated the responsive design and regression oracle.
Backend source is unchanged and its full suite was not rerun for this frontend
change. Inquiry persistence checks used the isolated real API with SMTP disabled;
no live inquiries/emails were sent. Physical devices, screen readers and actual
mailbox rendering remain unverified. These changes are local, not deployed.

## Quote-position fix deployed - 2026-09-27

With user approval, committed and pushed the tested frontend change as `7cce208`
on `main`, then fast-forwarded Ubuntu-1 from `94c4e8a` to that revision. The
backup branch remains at `91f3d3d`; local untracked banner data was not staged.

The production data-backup service completed successfully. Preserved the prior
frontend build and protected environment/Caddy/web-service configuration under
`/var/backups/styl/quote-release-20260927T204500Z` (root-only directory).
Built the candidate in a separate temporary directory using the existing,
unchanged dependencies, with same-origin API requests. Production build and
TypeScript checks passed. Replaced the frontend build and restarted only
`styl-web` at approximately 20:48 UTC. The API process and Caddy stayed running.
The server's existing deployment-script executable-mode changes were preserved.

Targeted live verification, in addition to the predeployment 71-browser/seven-unit
frontend results recorded below:

- All 15 live quote landings passed: direct/cart/product and two repeated
  same-page entries in desktop Chromium, phone Chromium, and phone WebKit.
  Each measured a 16 px form-to-header gap and a fully visible Name field.
  Cart/product message context was preserved; no browser runtime errors occurred.
- Tests used fresh isolated browser storage and read-only production requests.
  No inquiry was submitted, no email was sent, and no production record was edited.
- HTTPS home/cart/accessories/admin pages, health, both catalog APIs, and market
  endpoint returned 200. The web service started successfully.
- Before/after checksums confirmed the environment, Caddy configuration, product
  catalog, accessory catalog, and banner data were unchanged. The API retained
  its predeployment process and start time, preserving the live SMTP setup.

This is targeted deployment verification, not a new full backend/manual
regression or physical-device certification. GeoIP provisioning and independent
mailbox delivery checks remain separate outstanding work.

## Quote-form landing position corrected - 2026-09-27

Reported: cart Request a quote navigated to the correct home/contact URL but left
the form low in the viewport. Added USR-012 tests before changing the implementation;
all four original desktop entry/repeat cases failed the landing-position check.
The observed desktop gap was 148 px below the header instead of the expected
8-32 px.

The correction handles both asynchronous layout changes and insufficient trailing
page space on tall desktop windows. Home now waits for initial catalog/banner/cart
loading to settle before a one-time alignment below the measured sticky header.
The targeted form has enough minimum viewport-height space to reach that position.
Client-side history navigation did not reliably set CSS `:target`, so the hook
explicitly marks the quote target and handles repeated same-page quote links.
There are no timed scroll loops or forced input focus.

Wheel/touch/pointer, navigation keys, and field focus cancel pending adjustments.
Quote-prefill text remains intact; ordinary visits and later price refreshes do
not trigger a new quote scroll. Other catalog links keep their normal navigation.

Validation against base `91f3d3d` plus this local frontend patch:

- Seven frontend unit tests passed.
- All 71 configured production-build E2E executions passed, including 27
  USR-012 cases across desktop Chromium, phone Chromium, and phone WebKit.
- New checks cover cart/product/direct/repeated links, delayed catalog/banner/
  cart data, failures, typing/scroll cancellation, and post-landing refresh.
- Production build/TypeScript and editor diagnostics passed; lint had no errors
  and the existing five image-optimization warnings.
- An intermediate test needed a WebKit-compatible touch-intent simulation and
  hydration synchronization; physical touch/keyboard behavior is not certified
  by that simulation. An empty generated build directory was removed after a
  Windows filesystem-lock failure; source/catalog data was not deleted.

Regression plan and responsive design were updated. No backend/SMTP changes,
live inquiry sends, production configuration changes, deployment, or backup-branch
updates were performed during implementation. At that point the fix was local;
the subsequent authorized deployment is recorded above.

## Multiple-recipient SMTP enabled - 2026-09-27

The user approved using a separately authenticated Gmail sender and delivering
quote notifications to that mailbox plus the STYL business mailbox. Added the
server-only `STYL_INQUIRY_RECIPIENTS` comma-separated setting with validated,
deduplicated addresses; default single-recipient behavior is retained.
Reply-To remains the submitting customer's address. Invalid recipient settings
prevent sending; partial refusal retains the inquiry with failed email status.

Validation: the new multi-recipient test failed against the old single-recipient
behavior, then passed. All 62 backend tests, seven frontend unit tests, and all 44
configured production-build browser executions passed; lint has no errors and
five image-optimization warnings. SMTP delivery is mocked in automated tests.
The user entered the app password in a hidden server prompt, outside chat/history.
A real STARTTLS Gmail authentication check succeeded and a root-only pending
configuration was created. No credential is included in this repository.

With explicit user approval, pushed and deployed backend commit `94c4e8a` to
Ubuntu-1. The server retained its unrelated executable-mode changes to deployment
scripts. Backed up the previous environment and API source under
`/etc/styl/smtp-backup-20260927T183705Z`, activated the root-only environment file
(mode 0600), and restarted only `styl-api`. Caddy and the frontend stayed active.
No dependency, frontend build, DNS, catalog-data, or backup-branch change was needed.

Submitted exactly one authorized, clearly marked setup inquiry through the live
website form. Inquiry `5cd25b322b224bcca7b647ecb1fb074e`, created at
`2026-09-27T18:39:05.209585+00:00`, returned HTTP 200 and was persisted with
`emailStatus: sent`; Gmail accepted the envelope containing both configured
notification recipients. The user inspected the received message and confirmed
that its Reply-To header contains one address, then confirmed the desired policy:
Reply-To must remain the submitting customer, not the STYL mailbox.

Receipt in every recipient inbox has not been independently confirmed; access to
the STYL mailbox was unavailable. SMTP acceptance is not a guarantee of inbox
delivery. OPS-006 therefore has live submission/SMTP evidence but remains partly
unverified for per-mailbox arrival and spam-folder checks.

Removed the one-time setup script and pending credential file; the credential
exists only in protected live server configuration, not chat, Git, or local code.
The clearly identified test inquiry remains as the delivery-verification record.
Final public health and market requests returned 200; regional fallback stayed
unknown/CAD. No further test messages were sent.

## Domain HTTPS enabled on Lightsail - 2026-09-27

The user authorized production configuration updates for `stylfitness.com` and
`www.stylfitness.com`, preserving existing IP-based access. No application-code
deployment, DNS/email change, or catalog-data write was performed.

Before the change, public DNS already resolved the root domain to the attached
Lightsail static IP `54.156.37.31`; `www` was a CNAME to the root domain.
The installed Caddy configuration served only the HTTPS IP hostname, explaining
domain TLS failures. The API allowed only the IP origin. The server checkout
was `a78d3c6`, and all application/proxy services were active.

Changes:

- Backed up the original Caddy configuration and environment file under
  `/etc/styl/domain-backup-20260927T172943Z` (root-only directory).
- Appended the root-domain site with existing frontend/API routing and explicit
  client-IP forwarding for the API; preserved the old IP block and its TLS policy.
- Added a permanent `www` redirect to the root domain with path/query retention.
- Added both HTTPS domain origins alongside the existing IP origin.
- Validated the staged Caddy configuration, restarted only `styl-api` for its
  environment setting, and gracefully reloaded Caddy. `styl-web` was not restarted.
- Caddy obtained certificates for both domain names from Let's Encrypt.

Verification (targeted operational smoke, not a full regression):

- Trusted TLS validation succeeded for the root and www hostnames. The observed
  root certificate expires 2026-12-26; Caddy manages renewal.
- HTTPS root, health, admin page, cart page, catalog APIs, and one product detail
  returned 200. Anonymous admin verification returned 401.
- HTTP redirects to HTTPS (308); www redirects to the root (301), preserving a
  test path and query string.
- Allowed-origin preflight for the domain returned 200 and the expected origin.
- Regional catalog/market responses remained private/no-store and returned
  unknown/CAD; this does not prove GeoIP database provisioning.
- Browser loaded the main catalog and Accessories on the domain without visible
  API errors, using same-origin API requests; phone-width navigation was visible.
- An uploaded image endpoint returned 200; an existing video byte range returned
  206 with the requested 100 bytes. Full physical-device video/audio was not tested.
- Existing HTTPS IP health worked from the server and an external explicitly
  named TLS connection. One external IP probe without explicit SNI reset; domain
  access is the recommended public URL.
- Caddy, API, and frontend remained active.

Browser-terminal bulk typing was unreliable; an initial transfer was cancelled,
and another failed decoding before the configuration operation succeeded. Changes
were subsequently staged in short commands and their diff/validation inspected
before applying. No rollback was required for the successful apply.

DNS MX/TXT/email settings, firewall rules, prices, source files, and database files
were not changed. GeoIP setup, real mailbox delivery, and full physical-device
testing remain separate work. The verification backup Git branch was not changed.

Operational cases: OPS-001 and OPS-010 received targeted live evidence;
OPS-002/003/004/005/006/008 are not fully certified by this smoke pass.

## CAD fallback and direct mobile catalog navigation - 2026-09-26

New approved behavior: unresolved visitor location now defaults to CAD, while
countryCode remains null and locationStatus remains unknown. Identified Canada
uses CAD; identified US/other countries still use USD. This supersedes the earlier
unknown/USD rule recorded below. Missing CAD prices still hide items; no price
conversion or data copying is performed.

Added a Products / Accessories row directly below the logo/cart/menu row below
1024 CSS px. Both catalog destinations can be reached without opening Menu.
Desktop full navigation is unchanged. Mobile anchor offsets account for the
taller header.

Regression cases GEO-007 and USR-011 added. A new API test first failed on the old
USD fallback, then passed after the change. Validation: 60 backend tests, seven
frontend unit tests, and all 44 configured E2E executions passed; production
build/TypeScript passed; lint had no errors and five image warnings. The first
browser run exposed an ambiguous test heading selector (hidden dialog headings
also matched); it was corrected, then the full browser suite passed. This is
automated-code verification, not physical-device/live GeoIP sign-off.

The test harness uses explicit synthetic dual-market prices only in disposable
fixtures; the real local catalog was not modified. After restarting the local API,
`/api/market` returned unknown/CAD. The local legacy catalog has no CAD prices, so
its public lists are empty under the agreed missing-price rule. The new navigation
was also visually checked at 390 px with no horizontal overflow.

Changes are local, not committed, pushed, or deployed. The live server still needs
database provisioning and the new release before its fallback changes.

## Live GeoIP configuration confirmed missing - 2026-09-26

After the earlier connection failures, the user shared an authenticated Ubuntu-1
Lightsail SSH terminal. Read-only checks confirmed:

- No `STYL_GEOIP_DATABASE` setting in the expected service environment file or
  the running `styl-api` process environment.
- The expected `/var/lib/styl/geoip` directory and country database file are absent.
- Service logs explicitly report: `GeoIP unavailable: STYL_GEOIP_DATABASE is not
  set; using unknown location and USD.`
- The server checkout is at `6eef5b0`.
- Installed service/proxy configuration lacks the repository's explicit
  proxy-header flags and forwarded-IP overwrite. This difference alone does not
  prove forwarding is broken, since defaults may already forward/trust loopback;
  validate the actual chain after database provisioning.

The missing configuration is a confirmed production defect in geographic pricing
readiness, explaining unknown/USD fallback even for Canadian visitors. No
database was installed, no production file changed, and no service restarted.
The Vancouver visitor's own response and live country accuracy still need
verification after provisioning a licensed country MMDB and configuring the service.
GEO-002/OPS-002 remain incomplete, not passed.

## Targeted GeoIP investigation and local startup - 2026-09-26

Reported: a Vancouver visitor saw USD. The user supplied their own US-network
`/api/market` response showing null country, unknown status, and USD. That proves
fallback for that request, not a correctly detected US country or the Vancouver
visitor's exact response.

Local inspection at `6eef5b0` found no listeners on the frontend/API ports and no
`STYL_GEOIP_DATABASE` environment setting. Started the local API and frontend with
ignored VS Code tasks without terminating unrelated processes. Verified API health,
HTTP 200 on the site, four visible local product cards, and no visible catalog
error. Browser access worked at `http://127.0.0.1:3000`; the integrated browser's
`localhost` navigation failed, while an HTTP probe to localhost succeeded.

A synthetic public-client lookup made no external network request and produced
the explicit warning that the GeoIP database setting is absent. Loopback
unknown/USD is expected separately. All 24 tests in `tests.test_location` and
`tests.test_regional_catalog` passed; their fixtures do not verify a live database.

No application pricing change was made and no production issue is claimed fixed.
Direct production probes failed at TLS, and authenticated server access was not
available. Production configuration, real database accuracy, and the affected
visitor's response remain unverified (GEO-002/OPS-002). See the
[GeoIP troubleshooting steps](geoip-pricing.md#troubleshooting-a-canadian-visitor-seeing-usd).
Local task definitions and the generated local admin credential are ignored by
Git; local catalog data was not edited.

Regression reference: [Living regression test plan](regression-test-plan.md).
Use its stable case IDs, system/user coverage map, and run-record template for
future changes. Record targeted versus full-suite results separately.

Project automation guidance added on 2026-09-26:
the [styl-regression skill](../.github/skills/styl-regression/SKILL.md) defines full
regression execution and requires new features/fixes to maintain this test plan
and executable coverage. Repository Copilot instructions provide the routing.
Creating the skill did not execute a new application test run.

## Pre-push regression - R2-PUSH-2026-09-26

Purpose: complete automated code regression before the user-authorized push of
all Round 2 code, regression documentation, and the project skill. No deployment.

Candidate: base `c9837e687b88db1228b7ba5fbf32d8a4f520a003` plus staged Git tree
`6b0ef9383a1814c92e5d1ef3f89c44ea496f5a9f`. Only documentation recording this run
changed afterward; tested source trees remained:

- Backend: `d6a18341d741478be655b0d67ebb76569901fc70`
- Frontend: `89356dcfe7bb544cbf442e83a9460eb56d4a6511`
- Deployment configuration: `2f385cfedbfc95a6949d92249abf57f6c678f117`
- Project agent instructions/skill: `4c863cbc3ab82a425b37ef7ac2be4c97db65bc1c`

Environment: Windows 10.0.26300, Python 3.11.9 in the repository test virtual
environment, Node 24.14.0, Playwright 1.63.0, Chromium 153.0.8010.12, WebKit 26.6.
Configured projects: desktop Chromium (1440 x 1000), phone Chromium (390 x 844),
and the Round 2 phone WebKit cases. Responsive tests exercised the additional
boundary widths; date cases used Toronto/Auckland timezones.

| Check | Result |
| --- | --- |
| Backend `unittest discover -s tests` | Pass: 59 tests, exit 0 |
| Frontend `npm test` | Pass: 7 tests, exit 0 |
| Frontend `npm run lint` | Pass: exit 0, no errors; five image-optimization warnings remain |
| Frontend `npm run test:e2e` | Pass: 40 executions, exit 0, no retries; production build/TypeScript passed as part of startup |
| Candidate/format checks | Pass: no unstaged application changes; staged diff check clean |

This full run includes the final standalone price-free banner, unlike the older
full run before the banner decision changed. No application failures or fixes
were needed during this final run. Captured-date blanking was not reproduced;
the tests verify the exercised paths rather than claiming a date fix.

Evidence used the real isolated API/storage and real local media conversion.
GeoIP MMDB records, Canadian browser catalog responses, SMTP transport, and
selected failure responses were mocked as documented in the plan. No production
database, public visitor IP, real customer record, or mailbox was used.
Test servers on ports 3102/8102 stopped after the run; the runner owns temporary
data cleanup. Logs remain in local session/tool output; no traces or credentials
are committed. The existing local hero data is excluded from this push.

### Case accounting and limits

This is an automated-code result, **not a complete manual/production sign-off**.
Ranges below include every case ID in that range. A passing automated portion
does not mark the unexecuted portions of that row as passing.

| Cases | Automated portion | Remaining portion / status |
| --- | --- | --- |
| SYS-001, SYS-002 | Pass: isolated startup and existing auth tests | Not run: additional manual health-contract/complete protected-route audit |
| SYS-003, SYS-004, SYS-006, SYS-007, SYS-011, SYS-012, SYS-013, SYS-014 | Pass for the mapped automation | No additional production certification implied |
| SYS-005, SYS-008, SYS-009, SYS-010, SYS-015 | Pass for existing assertions | Not run: broader endpoint/input matrix, equipment-weight visual inspection, and catalog storage-failure injection described in the plan |
| GEO-001, GEO-003, GEO-004, GEO-005 | Pass for offline/local fixtures | Blocked: installed live database accuracy and cross-country proxy/cache verification |
| GEO-002 | Pass: resolver ignores untrusted headers | Blocked: actual installed proxy trust chain |
| GEO-006 | Pass: regional reconciliation | Not run: additional browser current-price-request failure scenario |
| MED-004, MED-006, MED-008 | Pass for mapped local automation | Real-device/proxy portions remain covered by the blocked operational checks |
| MED-001, MED-002, MED-003, MED-005, MED-007 | Pass for existing MIME/size/conversion/failure/batch assertions | Not run: remaining content-decoding/busy/storage/history variants; blocked: physical audio/visual fidelity |
| ADM-001, ADM-002, ADM-004, ADM-005 | Pass for mapped browser workflows | Not run: extra session-expiry paths; blocked: physical date picker/segmented input variants |
| ADM-003, ADM-006, ADM-007, ADM-008, ADM-009 | Pass for current browser assertions | Not run: full navigation/race/error/long-content matrix; blocked: physical keyboard, screen reader and slow-device checks |
| USR-005, USR-006, USR-007, USR-008 | Pass for mapped browser/unit/API flows | No claim of exactly-once submission or live mailbox delivery |
| USR-001, USR-002, USR-003, USR-004, USR-009 | Pass for existing browser assertions | Not run: remaining CTA/back-position/long-content/zoom matrix; blocked: physical devices and live regional checks |
| USR-010 | Not run | Blocked: requested assistive-technology/physical-device verification not available in this run |
| DATE-001, DATE-002 | Pass for both forms in configured browser/timezone cases | No original physical-device reproduction claimed |
| DATE-003, DATE-004 | Pass for mapped automated trace/privacy assertions | Blocked: physical typed-segment/calendar variants; not run: additional public-surface privacy matrix beyond current assertions |
| OPS-001 through OPS-006, OPS-008 | Not run | Blocked: no authorized staging/production deployment, live MMDB/proxy, device, backup exercise or mailbox session in this push |
| OPS-007 | Pass for mapped unit/browser failure portions | Not run: staging disk/permission/process fault injection |
| OPS-009 | Not run | No performance baseline/field measurement collected |
| FUT-001 through FUT-005 | Not applicable | Proposed schema functionality has not been implemented |

Decision: automated candidate checks pass; push approved by the user.
Deployment/physical-device readiness remains unverified. Provision the local
country MMDB, apply proxy/service configuration, review missing market prices,
and complete applicable operational checks before production rollout.

## Round 2 working update - 2026-09-26

The customer reopened country pricing and publication-default work. The working
implementation adds independent CAD/USD prices, local-IP country lookup, explicit
currency labels, market-specific hiding when price is missing, and admin warnings.
No exchange-rate conversion or speculative second-market price is applied.

New products and accessories default to Draft; existing legacy visibility is
preserved. Bench maps to Benches, equipment gains optional weight, and upload
results separate the current batch from earlier unresolved failures.

The proposed sellable-product banner selector was withdrawn later on 2026-09-26.
The original independent banner text/image configuration is restored, with no
price field or price display. Legacy text/image settings remain usable while
legacy price labels are ignored. Phone banner hiding remains unchanged.

Captured date clearing was not reproduced: `2026-09-26` survived notes editing,
same-task input events, save/reload, and private/public API checks in Chromium and
WebKit under Toronto/Auckland timezones. No speculative date implementation change
was made.

Working validation: 59 backend tests, seven frontend unit tests, and 40 E2E tests
passed; the final candidate was rerun in R2-PUSH-2026-09-26 above and is included
in the approved Round 2 push. It has not been deployed. Production needs
a provisioned local country MMDB and the updated trusted-proxy configuration.
The dated history below records earlier behavior and holds, not the new override.

Recorded code/documentation baseline: `c9837e687b88db1228b7ba5fbf32d8a4f520a003`

This is a curated history of implementation and design decisions, not a substitute
for Git history. Keep completed behavior separate from proposed schema work.

## 1. Project status

- Repository: `color4tree/STYL`, branch `main`.
- Changes through `c9837e6` were pushed to GitHub.
- Frontend: Next.js, React, TypeScript, and Tailwind CSS.
- Backend: FastAPI and Pydantic.
- Current storage: JSON catalog files and local uploaded media.
- Deployment architecture: one AWS Lightsail instance with Caddy.
- The expanded catalog/admin schema is documented but **not implemented**.
- No production deployment was completed during this work. Earlier deployment
  access was blocked; the live revision has not been verified.
- An existing untracked local file, `backend/app/data/hero.json`, was
  intentionally left untouched and excluded from commits. Do not treat it as
  an approved catalog-data change.

## 2. Implemented milestones

### Earlier foundations

| Commit | Milestone |
| --- | --- |
| `c960a52` | Admin-editable home banner card |
| `eeab5f0` | Catalog photo galleries and structured compatibility |
| `fd1c54c` | Optional product details and existing product draft/publish functionality |
| `ed6e394` | Homepage simplification and spacing adjustments |
| `c43991a` | Inquiry email notifications and batch video uploads |
| `0e4711c` | More prominent accessory-save errors |

These foundations predate the later decision to exclude additional
draft/publish changes. Existing publication functionality was retained.

### Catalog and responsive improvements

| Commit | Completed change |
| --- | --- |
| `334d320` | Restricted new catalog input to CAD/USD, kept CAD as the new-entry default, used dollar-symbol storefront prices, and added the shared multi-image/video gallery to homepage product cards |
| `c412178` | Rich accessory fields, exact-cent price validation, private provenance, canonical category selection, responsive storefront/admin workflows, and repeatable production-build E2E tests |
| `1f5f58c` | Restored the customer-value principle to a prominent homepage introduction callout and removed its duplicate from About |
| `f142fb6` | Hid the promotional Home banner card below 768 CSS px while retaining tablet/desktop display and admin editing |
| `aa2861a` | Hid the collection-heading "Browse accessories" shortcut at 1024 CSS px and wider; retained smaller-screen access and desktop main navigation |
| `c9837e6` | Added the complete target catalog/admin schema design and companion proposal review, with README links |

## 3. Current customer-facing behavior

### Homepage

- The introduction includes the exact business principle:

  > Maximize customer value first, then capture a fair share of the value created.

- It appears below the introductory copy and above Shop equipment, on both
  desktop and phones.
- The principle is not duplicated in the Why STYL/About section.
- The promotional image/title/price Home banner card is hidden below 768 CSS px.
  The introduction, principle, and shopping actions remain visible.
- The banner remains visible from 768 CSS px upward; its admin editor is unaffected.
- The collection-heading Browse accessories shortcut is visible below 1024 CSS px
  and hidden at desktop widths. The main Accessories navigation remains available.
- The homepage collection retains all eligible products, with Featured items first.

### Catalog, cart, and inquiry

- Public numeric prices use `$` and two decimal places.
- Product and accessory prices reject negative values and excess precision.
- Cart line amounts and totals use cents; different currencies are not combined.
- Accessories support short/full descriptions, public use text, features,
  package contents, selling units, package quantity, and finish/colour.
- Quantity refers to sale units: one pair is one selected sale unit, not one piece.
- Long accessory information uses expandable details; blank optional rows are hidden.
- Product cards, accessory cards, and product details share image/video galleries.
- Customer inquiries are saved before email notification is attempted.
- Forms have labels and submission feedback; failures retain entered text.
- Inquiry success is receipt of a request, not a paid order or confirmed delivery.

## 4. Current admin and media behavior

- Mobile admin separates the catalog list from editing; desktop retains split panes.
- Unsaved-change guards and explicit save/error states protect editing workflows.
- Price entry supports cents and normalizes valid values to two-decimal display.
- Categories use an authenticated canonical list with case/whitespace normalization.
  They are not yet fully configurable through an admin taxonomy editor.
- Source/provenance information is private and excluded from public catalog JSON.
- Full description and Public use description are distinct fields; private
  migration notes belong in Internal notes.
- Shared media editing supports ordering, cover guidance, partial-upload errors,
  and retrying failed files without resending successful ones.
- Galleries have touch-sized controls, enlargement, keyboard navigation, swipe
  enhancement, and controlled video playback.
- Current limits: 12 combined gallery items, 8 MiB per image, 50 MiB per video.
- Uploaded video is converted to H.264/AAC MP4 with a JPEG poster; temporary
  originals are discarded. Externally linked media is not transcoded.
- A mobile missed-click bug was found during E2E testing: changing Save-bar
  positioning on field blur could move the Add media button during a click.
  Stable positioning fixed it, and the mobile test covers repeated media additions.

## 5. Agreed design direction, not yet implemented

The authoritative target design is
[Product catalog and admin data schema](catalog-and-admin-schema-design.md).
The original attachment comparison is
[Accessory schema review](accessory-schema-review.md).

### Naming and identity

- Product is the umbrella for all sellable items.
- Initial types: Equipment and Attachments.
- Equipment includes primary training equipment such as multi trainers, racks,
  and benches.
- Attachments connect to equipment to provide or extend training functionality.
- Do not classify solely by independent usability or blindly relabel every
  existing accessory; review benches, storage, and supporting items individually.
- Every sellable unit receives a unique catalog-wide SKU.
- SKU is a business identifier, separate from optional Model and the internal ID.
- Product ID is the immutable primary key: visible/copyable in admin, never editable,
  and used to retrieve and relate product information.
- SKU correction must not break the internal identity or its relationships.
- A separately sold pair and a separately sold individual component need different
  SKUs. Retired SKUs must not be reused for different products.

The current application still uses the older Product/Accessory split and does
not yet implement the proposed global SKU registry, unified identity model, or
Equipment/Attachments taxonomy migration.

### Configurable admin data

- Business vocabularies should be admin-managed: product types, categories,
  selling units, condition/stock labels, source types, attribute groups, and choices.
- Options have stable identities separate from labels, with defaults, retirement,
  usage checks, reviewed replacements, and audit history.
- Technical rules remain protected: money arithmetic, permissions, parser types,
  conversion factors, and processing-state semantics.
- Attributes need controlled definitions, typed values, units, source evidence,
  and verification meaning.
- Compatibility is not inferred from a category or similar dimensions.
  In particular, 75 mm and 3 inches are not equivalent: 3 inches is 76.2 mm.
- Media should evolve toward stable records, independent covers, alternative text,
  metadata, and reference-safe deletion without breaking existing galleries.
- Private source/review information must be excluded by explicit server-side
  public response contracts, including nested fields.

### Decisions still requiring approval

- SQLite versus a temporary single atomic JSON aggregate for the expanded model.
- Exact SKU allocation policy, manual assignment/correction permissions, and backfill.
- Named admin identities versus acknowledged shared-token attribution limitations.
- Reviewed initial taxonomy and technical-attribute definitions.
- Evidence standards for verified fit and load-related claims.
- Timing of richer collection management and structured inquiry snapshots.

## 6. Scope constraints to preserve

1. Additional draft/publish feedback is excluded. Preserve existing behavior.
2. CAD/USD presentation changes and mixed-currency-summary redesign are on hold.
3. Desktop remains as important as mobile; do not replace desktop layouts with
   stretched phone layouts.
4. Keep public copy, source evidence, and internal operational notes separate.
5. Do not invent missing compatibility, weight, capacity, package contents,
   condition, brand, or historical timestamps.
6. Do not introduce checkout, payments, inventory reservations, ERP, or a complex
   variant engine as part of the approved catalog work.
7. Design documents are not blanket authorization to implement every target feature.
8. Commit/push is separate from deployment; production data is not a test fixture.

## 7. Verification record

### Full implementation pass

At the `c412178` milestone:

- 20 E2E tests passed across desktop and phone-sized Chromium.
- E2E tests used a production frontend build and a real isolated API.
- 35 backend tests passed.
- Six frontend unit tests passed.
- Production build and TypeScript checks passed.
- Lint had no errors and five image-optimization warnings.

Coverage included authentication, real save/reload, separate accessory content
fields, price precision, sale units, private metadata exclusion, failed saves,
unsaved-change protection, deletion, gallery uploads/order, real video seeking,
partial-upload retry, file/count limits, cart limits, inquiry persistence,
responsive navigation, banner editing, and error recovery.

### Later targeted checks

- Principle placement: four targeted browser cases passed, including visibility
  and continued shopping access on desktop and phones.
- Mobile banner hiding: eight targeted cases passed, including the 767/768 px
  boundary and unchanged admin editing.
- Desktop shortcut hiding: two responsive cases passed, including the
  1023/1024 px boundary and retained main navigation.
- These targeted runs also built the production frontend successfully.
- Later regression cases were added to the suite; the recorded 20-test full pass
  is historical and should not be misreported as a later full-suite rerun.

### Remaining release checks

- Physical iPhone Safari and Android Chrome: keyboard, safe areas, actual gestures,
  audio, and native video behavior.
- Production proxy/HTTPS and media seeking against the deployed version.
- Actual inquiry mailbox delivery and Reply-To behavior with production configuration.
- Live performance measurements; local tests do not establish field Core Web Vitals.

## 8. How to resume

1. Inspect Git status before editing. Preserve the untracked local hero data unless
   its inclusion is explicitly requested.
2. Read the latest scope decisions above and the target schema before starting
   schema implementation.
3. Use the test commands and environment guidance in the [README](../README.md).
   The E2E runner uses temporary data, disables SMTP, and requires its ports to be
   free; do not point it at production.
4. Approve outstanding schema decisions, then implement through staged,
   backward-compatible migration rather than replacing data in place.
5. Before production rollout, follow the
   [deployment and backup guide](lightsail-deployment.md), verify the deployed
   commit, and run live health/media checks.
6. Append future milestones with commit IDs, actual verification results, and
   explicit distinction between implemented behavior and proposed design.
