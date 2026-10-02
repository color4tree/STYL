# STYL project history and handoff

## Non-AI production activation verified - 2026-10-02 UTC

Application **`3ead5c679db41be21c1d5296a05df295826a8714`** was activated at
**2026-10-02T03:24:09Z / October 1, 20:24 Pacific**. Main was pushed only after
the local non-AI baseline passed. No customer-chat/knowledge/model implementation
was deployed; `/support` and `/api/support/config` return 404.

The isolated Linux build reused matching dependency manifests. Turbopack rejected
an external node_modules symlink, so a separate dependency copy was used without
installing/upgrading packages. Build completed successfully; all **82 Linux
deployment tests passed**, including the two process-group cases unavailable on
Windows. The reviewed installer and configuration payload were copied into a
root-protected release directory and pinned across preparation/cutover/retention.

Release backup: `/var/backups/styl/release-3ead5c6`. Old source, mode-only Git
changes, environment, consistent analytics SQLite, complete data archive and
previous Next build were preserved. Code fast-forward and build swap used a
rollback trap; catalog products/accessories/home hashes matched before cutover.
Existing environment values, including SMTP/GeoIP, and saved analytics email
settings were compared unchanged. All six API/web/Caddy/backup/report/GeoIP
services/timers were active after deployment.

Saved daily mail remains enabled at revision 2; actual nextRunAt was verified as
`2026-10-02T07:15:00+00:00` (**00:15 Pacific**), with no forced send or recipient
change. Apex/www/static-IP HTTP redirects retain their prior same-host 308
behavior; HTTPS health and canonical www redirect remain working. Website
capture was verified with 134 Caddy access entries and no request objects.

The protected historical journal exports were captured before any retention
change. A production Records ZIP was downloaded, hash-verified and cold-restored
locally; SQLite integrity and both gzip journal exports passed. The actual saved
file was then re-uploaded through the authenticated verification endpoint:

- Archive ID: `01e71c4e796d46f5aa86a48117e2c1c0`
- Bytes: **11,510,526**
- SHA-256: `83ac6c9dfae02f8ae4e3328ff83a272783d6f167371ee5a3fb4ae8b3f3a5f222`
- Contents: three inquiries, 968 database rows, six website-log files.
- Verified server receipt: `2026-10-02T03:44:33.166333+00:00`.
- Private local copy/restore:
  `%LOCALAPPDATA%\STYL\CatalogMirrors\production-records-release-20261002`.

Only after that proof, operational **journald** retention was activated at
14 days / 250 MB. Website/business archives have no automatic age/size expiry,
and no business records or server archives were removed. Other vendor OS
logrotate policies were inventoried but deliberately not rewritten.

Browser-console background-tab throttling caused delayed rendering and one
mistyped temporary stage path; literal paths, focused/visible terminal input,
source hashes and syntax guards prevented unreviewed execution. The temporary
empty wrong-path directory was cleaned. The activation script required explicit
CRLF-to-LF normalization; its verified Linux hash was
`6eb3ddfc09cf689e93ce72cdf2d0f1f94510f6a528e65153ba07439aa452e1fd`.
The retired stage dependency copy was removed and source artifacts retained
under the protected release backup.

## Non-AI main release preparation - 2026-10-01

The owner explicitly approved moving analytics, backup/log retention and shared
admin improvements into main, deploying only those features, then returning to
the AI branch. AI development was preserved locally at `1bb6272` on
`ai-assistant/baseline-2026-09-29-2227-pt`. Shared country-price rows were committed
there as `92c09ba` and cherry-picked to main as `744a781`; the documentation
conflict was resolved without importing AI-only sections.

Main contains no support/knowledge/model modules, routes, customer widget or
provider dependencies. A main-only release test checks that boundary. Non-AI
records code was recovered from the pre-AI implementation and revalidated;
missing analytics storage now fails explicitly with 503 through a readonly
snapshot connection, rather than creating an empty replacement backup source.

Included:
- Daily analytics mail at **00:15 Pacific for the previous completed day**,
  retaining saved enablement/recipients and delivery deduplication.
- Backup tab with Catalog recovery and Business / log records; private durable
  download/verification and explicit optional exact-record cleanup.
- No age expiry for business history, website logs or catalog backups.
- Safe website log collectors and a staged logging installer. Journal-only
  operational retention is gated on historical capture and a verified off-server
  Records ZIP; existing OS logrotate policies are not silently replaced.
- CAD/USD selling price and optional MSRP side by side in each country's row.
  An overlong accessory specification legend was shortened to fit 320px WebKit.
- Existing Home banner/photo-picker improvements remain from the deployed base.

Local release verification: **240 backend tests passed** (35.334s), **54 frontend
units passed** (0.87s), **310 configured browser executions passed** (10.6m).
Installer/collector suite: **80 passed, 2 Linux-only skips** out of 82 tests
(3.745s). Type/build/lint passed with four existing image warnings. Restored
test harness issues were corrected without weakening backup assertions: native
module loading, explicit accessible labels, browser-response predicates and
durable verification receipts rather than evicted upload bodies.

Production preflight was read-only: deployed app `d6d00a3`, five services active,
24 GB free, 56 MB journal usage, and same-host HTTP 308 redirects confirmed for
apex/www/static IP. Repository access uses its `styl` owner, without adding a
global Git trust exception. A production catalog ZIP was downloaded and verified
locally: 29,143,365 bytes, three equipment, sixteen accessories, 104 manifest files,
SHA-256 `9b0d127eb573e35aecb50a37a696db60478c327e212e9a73272c6e44ff25fb93`.
It is stored under the restricted non-synced
`%LOCALAPPDATA%\STYL\CatalogMirrors\production-records-release-20261002`.

Production activation and off-server journal/records verification are recorded
separately after completion. Owner product/accessory/home JSON and private
runtime credentials remain outside these commits.

Last recorded: 2026-09-29

## Photo-picker presentation deployed - 2026-09-29 Pacific

Deployed **`d6d00a3192b9d4f71088142eee26549bc13d779a`** at
`2026-09-30T05:27:30Z` (September 29, 22:27 Pacific), about 11.5 minutes after
the request. This publishes the Choose photo presentation and the previously
requested efficient-delivery skill/project guidance.

The scoped frontend release reused the established protected deployment template,
with reviewed revision/service checks. Backup:
`/var/backups/styl/release-d6d00a3`. The production build/type check passed;
only styl-web restarted. API PID **129002** remained unchanged, all five services/
timers were active, and config/catalog/GeoIP hashes matched. No saved photos,
text, recipients or credentials were changed.

Local coverage was the new fail-fast case followed by **17 affected browser
executions**, not a full-system rerun. Real picker opening, pointer/keyboard,
cancellation, uploads, validation and disabled/pending behavior were tested with
the isolated API. A readonly 390px local visual check captured the new controls.
Live verification confirmed the updated admin JavaScript was served and admin
sign-in/storefront pages worked at desktop/phone Chromium and phone WebKit with
no runtime diagnostics or test server writes. Actual authenticated upload/save
was deliberately not performed against production; physical device picker UI is
not certified by browser automation.

Candidate build-ID matched the running output; staging and deployment logs/scripts
were moved into the protected backup, transfer files and local helper scripts
removed. No redundant backend/full browser suite or second complete live run was
used. Data-preservation/rollback checks and focused live verification were retained.

## Clear Home banner photo buttons - 2026-09-29 (release candidate)

Replaced the unstyled native file-input presentation in the Home banner editor
and its four engineering cards with explicit **Choose photo** buttons, upload
icons and concise format/save guidance. Native file selection, 8 MiB/type limits,
image previews, error reporting, draft-before-save behavior and busy guards are
unchanged. The hidden native inputs keep their existing accessible labels for
test/assistive identification; visible buttons have distinct descriptive names.

Applied the new efficient-delivery guidance: scoped this as a bounded frontend
presentation change, not shared storage/media cleanup. One desktop first-case
run passed in **46.8 seconds** including its build. The final affected matrix
passed **17 executions in 48.5 seconds**, including desktop/phone Chromium and
phone WebKit: actual chooser pointer/keyboard activation, cancellation, draft
upload/no publish, validation, save/reload/public display, failed-save recovery
and disabled pending controls. Build/TypeScript and scoped lint/editor checks
passed with one existing banner image warning. No unrelated backend/full-system
suite was launched. Inspected only known generated artifacts before removing
OneDrive-blocked build output.

The previously requested efficient-delivery skill and linked project/regression
guidance are included with this release's documentation. They do not alter tool
approvals, worker isolation or runtime behavior. Production rollout evidence
follows after deployment; local catalog/mirror content remains excluded.

## Durable efficient-delivery workflow - 2026-09-29

Added the project `styl-efficient-delivery` skill at the owner's request and
linked it from project instructions and the existing autonomous/regression
skills. The living plan now explicitly selects verification by impact instead
of requiring every suite for every push: documentation checks for guidance-only
work, affected desktop/mobile checks for isolated UI changes, downstream tests
for bounded features, and full regression for explicit comprehensive requests
or shared/high-risk changes.

The skill requires one relevant case/browser and `--max-failures=1` during
iteration, diagnosis before retries, use of established helpers/readiness checks,
coherent edits, no duplicate full runs/builds without a reason, preserved fixture
isolation and actual phase timings. Backups, authorization boundaries, rollback
preparation and live verification remain. High-risk media cleanup/recovery,
pricing, auth/privacy and shared persistence are not downgraded to smoke tests.

This changes persistent project guidance, not Playwright's default commands,
worker count, build cache, VS Code approvals, workspace location or SSH/CI
configuration. Guarded artifact reuse and infrastructure setup remain future
work. Checked Markdown links, front matter and whitespace only; no application
suite or deployment was triggered by creating the skill. Local catalog data
was not touched, and these workflow edits have not been committed/pushed.

## Engineering editor deployed and workflow review - 2026-09-29 Pacific

Deployed **`efb3f5c1a5a7b5a33fc3acbc55a87b61ae0fe611`** at
`2026-09-30T04:15:29Z` (September 29, 21:15 Pacific), under the owner's explicit
develop/test/deploy request. Protected backup:
`/var/backups/styl/release-efb3f5c`. Linux passed **204 backend tests, 48 frontend
units and the production build/TypeScript check** before web/API activation.
The report timer was paused around activation, waiting for any in-flight job
instead of interrupting it, and resumed. Catalog, environment and GeoIP checksums
matched; no saved homepage content was automatically rewritten.

The authenticated production hero API returned the four-card configuration.
A new private recovery ZIP verified successfully with **3 equipment records,
16 accessories and 99 referenced media files**, including the four engineering
images. Live desktop Chromium, phone Chromium and phone WebKit checks confirmed
the API-backed heading/text, all images, responsive layout, disclosure behavior
and unchanged top-banner hiding. Final checks after staging cleanup had no runtime
diagnostics or server writes. No creative test content was saved on production.
Build-ID comparison matched the running and staged artifacts; stage/scripts/logs
were moved into the protected backup and scratch scripts removed.

Live-check corrections were verification issues, not product fixes: image URLs
were compared by normalized URL identity rather than relative/absolute spelling;
lazy images were scrolled into view before checking load completion. Physical
iPhone behavior and the earlier native Safari notice remain separate.

The owner requested an explanation of elapsed time. Activation was about
71 minutes after the request; final verification followed. Observable testing
costs included the initial targeted run (**4.9 minutes**, three 60-second textarea
locator timeouts), corrected targeted run (**1.5 minutes**) and the full
271-execution browser matrix (**10 minutes**). The Linux backend/unit checks
themselves took seconds. The remaining time was implementation, integration,
repeated local probes, documentation and browser-terminal deployment operations;
it was not precisely profiled and should not be assigned invented percentages.

Necessary scope included persistence/validation, uploads, shared-file retention,
legacy compatibility and recoverability, not just four HTML inputs. Avoidable
overhead included testing a broken first case across all browsers before stopping,
repeated browser-state injection probes instead of the normal sign-in helper,
extra one-off verification scripts/URL assumptions, OneDrive-generated artifact
handling, and manual browser-SSH command/screenshot round trips.

Next-workflow improvements: fail fast on the new case in one browser during
iteration, run the affected multi-browser group once after it is stable, and use
full-system regression deliberately for requested/broad high-risk changes rather
than reflexively for every small UI task. Reuse builds when the application
candidate has not changed, use existing auth/test helpers, and batch inspection/
edits. A clone outside OneDrive and a reviewed direct-SSH/CI release path would
remove recurring infrastructure overhead, but require a separate setup decision;
no credentials, approval settings, system networking or workspace relocation were
changed as part of this review. Retain validation, backups and live verification.

## Configurable engineering details - 2026-09-29 Pacific

The owner requested development, testing and deployment of an editable version
of the homepage engineering photograph section. Added Engineering details under
Home banner: section heading/optional introduction and four fixed image/title/
description cards, upload controls and previews. Existing content/layout is the
default, not a production data rewrite. Save changes publishes; uploads alone
do not. The price-free top banner and its phone hiding remain unchanged.

The existing hero configuration/API now supports the nested engineering section.
Omitted fields preserve saved values; the frontend submits changed top-level
settings only. Required headings/titles/images, image schemes/types and text
limits are validated. Partial/unsafe image text does not crash previews. Invalid
stored configuration returns an explicit logged 503 and cannot be overwritten
through a default-shaped admin response; an absent file can still use defaults.
Shared catalog/banner/engineering image and poster references protect media from
premature cleanup.

Recovery ZIPs include engineering configuration and images. For legacy saved
banners, defaults are materialized in the export copy only, with their referenced
bundled images. Current verification/restore supports both old and new ZIPs;
older tools may reject the added references, so use the current/included tool.
Standalone standard-library cold restore and byte/hash checks are covered.

Validation of the final implementation on base `bb672f7`:
**204 backend tests, 48 frontend unit tests and all 271 browser executions passed**.
Production build/TypeScript passed; lint had zero errors and four pre-existing
image warnings (the engineering images now reuse the existing image component).
The initial targeted run found textarea exact-label matching included their
contents; explicit stable accessible names fixed it. The corrected targeted run
passed 37 executions before the complete final run. No assertions were removed
or test retries enabled.

Readonly local normal-sign-in checks confirmed four editor cards, desktop/320px
layout and public defaults with saved hero bytes unchanged and no server writes.
An initial preloaded-session visual probe did not reach the local editor; the
normal sign-in workflow succeeded without changing auth behavior. Screenshots
remain private session artifacts.

Implementation/test fingerprint:
`242c415989b57a72ce7d64000ddf20f3d6516952edd067d5ff5739b2ce8caf13`
(12 changed/new code files, excluding all user catalog data). Regression cases
SYS-021 / ADM-013 / USR-019 and related README/responsive/recovery guidance were
updated. Deployment verification follows separately; physical-device checks,
production content editing and real email are not implied by isolated tests.

## Short catalog labels deployed - 2026-09-29 Pacific

Pushed application **`f62087c289e31fc876be751ff9946756737c8834`** under the
owner's deployment authorization. Activation completed at
`2026-09-30T00:47:36Z` (September 29, 17:47 Pacific).
The live actions now read All products / Equipment / Accessories; short
empty-cart links point to the matching filtered views.

This was a **frontend-only** release. Source comparison confirmed no backend or
service-definition changes. The API PID remained **124988** throughout; Caddy,
GeoIP and analytics/report scheduling were not restarted or reconfigured.
Protected rollback material is in `/var/backups/styl/release-f62087c`, including
old source/build/config, data archive, analytics SQLite snapshot and the isolated
candidate build. Linux **43 frontend unit tests and production build/TypeScript
passed**; the preceding local targeted browser run passed 14 checks.

Two operational issues were handled before activation:

- A browser-terminal transfer timed out with an incomplete quoted input. No
  deployment command was executed from it. The SSH session was renewed and the
  existing protected release template was transformed/reviewed in short commands;
  variables, service scope and shell syntax were checked before execution.
- The first activation guard found catalog/media changes during the build,
  including two formerly listed files no longer present, and correctly stopped
  before switching services. Nothing was restored over those live edits.
  Downloaded and verified a fresh protected catalog ZIP under the catalog lock:
  **3 equipment, 16 accessories, 95 referenced media files**. Resumed only the
  already-built frontend swap with the original rollback protection and unchanged
  backend/API/config guards. Do not claim the catalog was byte-identical across
  the whole build; concurrent edits were explicitly preserved.

Live desktop Chromium, 390px phone Chromium and phone WebKit checks passed:
short labels, >=48px targets, all three phone actions on one row, correct catalog
filters, no horizontal overflow and correct empty-cart destinations. They passed
again after staging cleanup, with no runtime diagnostics in these short runs and
no server writes from the DNT-protected checks. This does not certify physical
Safari or resolve the previously documented privacy/prefetch notices.

The running build matched the protected candidate. Deployment scripts/logs were
retained privately and temporary transfer/local helper files removed. The local
production ZIP mirror, its machine-specific profile and all pre-existing local
catalog edits were excluded from the push. That local mirror still represents
the supplied 23:22:42 UTC snapshot, not the subsequent live catalog edits.
No production catalog, email settings or credentials were overwritten and no
test inquiry/email was submitted.

## Short mobile actions, Safari notice and local production snapshot - 2026-09-29

Shortened home actions to **All products / Equipment / Accessories**, keeping
their existing filtered destinations. Reduced small-screen horizontal padding
without reducing the 48px hit height; all three fit one row at 390px and wrap
safely at narrower widths. Empty-cart links use the same short names and correct
filtered destinations. **14 focused desktop/phone Chromium/WebKit checks passed**,
including 320/390px layout, filter/quote navigation, empty-cart recovery and the
existing banner/principle rules. Build/TypeScript and scoped lint passed (two
pre-existing home-image warnings). This is targeted validation, not a new full run.

The iPhone screenshot's Dismiss / Reduce Protections text is Safari-owned privacy
compatibility UI, not a STYL agreement or a certificate-warning screen. Official
WebKit/Apple sources describe legitimate functionality being affected and iOS 26
fingerprinting protection extending to normal browsing; they do not document the
exact display heuristic for that banner. App-source inspection found no banner
text, fingerprinting SDK or direct canvas/WebGL readback; optional first-party
analytics/Web Vitals exist but are not established as the cause. The screenshot
shows the older two-choice header. No iPhone protections were reduced, and the
native banner was not falsely declared reproduced/fixed by WebKit emulation.
Source links and the remaining device-inspection steps are in the mobile guide.

The supplied production archive `styl-catalog-backup-20260929T232242Z.zip`
(28,940,527 bytes; SHA-256
`fcdf415966870038604d89adbc062a7cbc78d6abffa62b15daeab00d91355398`)
was verified with the trusted repository restore implementation, not by executing
the archive's embedded Python. It was restored into the new private
`%LOCALAPPDATA%\STYL\CatalogMirrors\production-20260929T232242Z` directory,
outside Git/OneDrive with restricted user/SYSTEM/Administrators access.

Before switching, exported and verified the current local catalog to
`CatalogMirrors\before-production-20260929T232242Z\local-catalog.zip`:
4 equipment, 11 accessories, 16 referenced media files. Original repository JSON/
hero and upload directories were not overwritten. Two existing local inquiry
files were byte-preserved in the new data directory; no production inquiries,
credentials, email settings or analytics database were imported.

The local API now reads the supplied snapshot through ignored
`.styl-runtime/local-catalog.json`: **3 equipment, 16 accessories, 100 media**.
All **105 manifest entries** passed file checks; all **100 HTTP upload responses**
matched their hashes; a ZIP downloaded again from the running local API
byte-matched **103 catalog/media payloads** against the input archive. There
were zero bundled-image entries, so frontend static assets were not replaced.
Authenticated API IDs/order/names/prices/photos matched restored data, and
readonly desktop/390px browsing showed all 19 items and working accessory details.

Both local launchers honor the profile with explicit absolute-path/completeness
validation and locally disabled SMTP/report sending. **Eight isolated profile
checks passed** without starting/stopping services via the legacy standard
launcher. Only the verified local API task was restarted. Localhost remains
unknown/CAD; both CAD and USD prices are present for all 19 snapshot items.
The mirror matches the ZIP's 23:22:42 UTC catalog snapshot, not subsequent
production edits or production geography/services.

Persistent catalog/profile and rollback archives remain private; scratch scripts
were removed. Existing local edits are retained. No commit, push, production
deployment, real mail or production-data change was performed in this task.

## Compact All products / MSRP release deployed - 2026-09-29

The owner authorized push/deploy. Verified the exact implementation fingerprint
from the preceding local run before committing/pushing application release
**`17b30fcb2f2d1bae53542f8f3d1bb668e9056668`**. Production activation completed
at **`2026-09-29T23:21:12Z`** on Ubuntu-1 via the verified kenny-daily session.
The stale browser SSH connection was refreshed through the signed-in Lightsail
page; no password/token was requested in chat or entered into terminal input.

Protected backup: `/var/backups/styl/release-17b30fc`, including previous code/
mode changes/build, catalog/media/inquiries, original environment and a consistent
private analytics SQLite backup. The isolated Linux candidate passed **184 backend
tests, 43 frontend unit tests and production build/TypeScript** before service
activation. Dependencies/lockfiles were unchanged. The maintenance timer was paused
and any running report job allowed to finish before the web/API switch; it was
resumed afterward. Rollback was prepared but not needed.

Verified live:

- Default All products contains **3 equipment + 16 accessories**, in the expected
  saved per-catalog order. All three filters, compact initial cards, explicit
  expansion/collapse and desktop-versus-mobile actions worked.
- Equipment and accessory detail pages, accessory-to-quote prefill, legacy URLs,
  public selected-market MSRP shape and private-field redaction passed the live
  functional assertions in desktop Chromium, phone Chromium and phone WebKit.
  Desktop/phone Chromium had zero runtime errors and passed again after cleanup.
- WebKit's functional assertions passed, but its separate zero-runtime-error
  assertion did **not** pass: rapid navigation produced five, then four
  previously observed prefetch/analytics-config access-control diagnostics.
  Do not report that browser's complete smoke as a clean pass or claim this known
  warning has been fixed. Physical Safari behavior remains unverified.
- Protected admin catalog responses contained normalized CAD/USD MSRP maps for
  all 19 records. Unauthorized admin routes returned 401. A private comparison
  confirmed saved email preferences/revision exactly matched the SQLite backup;
  SQLite integrity was OK. No recipient addresses or credentials were printed.
- Catalog/inquiry/media, environment and GeoIP checksums matched the pre-release
  copies. US/USD location remained correct; all five web/API/Caddy/analytics/
  GeoIP services or timers were active. Existing prices and MSRP data were not
  edited, seeded or migrated by deployment. No synthetic catalog/settings writes,
  analytics events or test email/inquiry submissions were used for live checks.

The staged build and deployment script/log were moved into the protected backup,
with build-ID comparison against the running output; transient transfer/local
verification scripts were removed. Local catalog edits and the historical backup
branch were excluded from publishing. Existing saved email settings were retained,
not automatically enabled/disabled by this UI release.

The prior local 259-browser attempt remains recorded as 258 passes plus one
ERR_NO_BUFFER_SPACE interruption that passed a focused rerun, not a fictitious
single clean pass. Operator note: once MSRP fields are edited in production, review
any rollback to serializers predating MSRP support; older generic serializers
do not know to redact the full MSRP map. Backups alone do not certify arbitrary
older application versions against newer catalog fields.

## Combined compact catalog, accessory details and regional MSRP - 2026-09-29 (local)

The owner approved three specific choices: Equipment is the correct uncountable
label; All products/Equipment/Accessories filter one home catalog (All is default,
equipment first then accessories in their saved orders); desktop Details opens
matching full pages for both item types. Optional MSRP is separate for CAD/USD
and crossed out only when higher than the selling Price.

Implemented a shared compact card/grid and full-detail component. Default cards
show gallery, category, name, actual Price/optional higher MSRP and actions.
Descriptions, specifications, compatibility, package contents and quantity
controls are initially hidden under explicit Show more on every viewport.
Mobile keeps Show more/Add but not a separate Details button; item titles remain
links. Expansion keeps the complete content and the user's resize choice, without
a clipped preview. This supersedes the previous 21rem desktop/automatic-full-mobile
requirement. Quote navigation retains selected filters and the existing pre-paint
alignment/interruption behavior. Equipment URLs and the legacy /accessories page
remain valid; new /accessories/[id] pages use the same gallery/spec/quote layout.

Backend/admin MSRP uses nullable independent `msrps.CAD` and `msrps.USD`, with
exact-cent validation, partial/omitted/clear semantics and legacy compatibility.
Public serializers expose only selected-market `msrp`; selling Price still gates
visibility and cart/quote arithmetic. Both editors include optional MSRP fields,
dirty guards, retained failed input and summaries. Backup/cold-restore checks
preserve MSRP bytes. Accessory detail responses retain draft/market/privacy and
cache protections. Analytics normalizes accessory detail paths and counts actual
mobile Show more actions; impression observation marks selling Price, not MSRP.

Verification found and addressed:

- Mobile editor tests incorrectly expected New while the retained Equipment
  editor was open; they now wait for the actual active editor rather than
  contradicting preserved mobile editing behavior.
- WebKit's native upload input shrank to 10.31px while its control required 108px,
  widening a 390px page to 437px. Giving the input its own full-width row fixed
  the real shared-editor overflow.
- Error notices inherited smooth scrolling after focus, moving the next action.
  A readonly local WebKit probe measured **382px across 24 frames** after error
  focus. Explicit instant scrolling reduced this to **0px**, with no server
  writes. Added a permanent frame-stability assertion and retained pointer recovery
  coverage rather than replacing every failing click with a retry.
- Updated obsolete backup wording and synchronized invalid-report route fixtures
  with the actual response before removing the handler. A filter-recovery test
  activated a server-rendered link before catalog hydration; it now waits for the
  selected view and `aria-busy=false`/loaded content.
- One rapid transition between independent gallery fixtures stalled before any
  client API request; 7/12-image layout fixtures now have separate fresh contexts.
  Their assertions remain intact. This is not a claim that the earlier intermittent
  Next.js loading/prefetch behavior is fixed.
- OneDrive blocked generated build-directory cleanup; only inspected inactive
  generated artifacts were removed. A test-loader variable was renamed to satisfy
  the existing Next lint rule, without adding tooling.

Final dirty candidate on `233292f`, implementation/test-file SHA-256
`5541017e03efa680c4842e6b6eb1e28d08bcab6a78d99257e23df9d2ac40634c`
(42 changed/new code files excluding user catalog data):

- **184 backend tests and 43 frontend unit tests passed**. Build/TypeScript and
  editor/Pylance checks passed; full lint had zero errors and the same five
  pre-existing image warnings.
- The final complete **259-execution browser attempt had 258 passes and one
  browser transport failure**, not a clean full-suite pass. The preserved trace
  showed admin verification 200 followed by `net::ERR_NO_BUFFER_SPACE` on the
  admin equipment request. The exact interrupted ZIP-download check then passed
  in a separate focused run, without changing code/assertions or enabling retries.
  Do not combine those into a fictitious single clean full run.
- All compact-catalog, regional MSRP, accessory-detail, media-width and
  quote-frame scenarios passed across desktop/phone Chromium and phone WebKit.
  Readonly localhost visual checks confirmed default All/filter navigation,
  desktop/mobile collapsed cards, accessory details and admin MSRP inputs.
  A struck-MSRP screenshot used response-only sample data; no catalog value was
  saved. DNT prevented synthetic behavioral traffic. One initial local visual
  probe did not complete, but its instrumented repeat did; no unproven fix claimed.

Updated README, pricing/backup/analytics/responsive guidance and stable cases
SYS-020, ADM-012, USR-017/018 plus the superseded card/expansion cases. Screenshots
and diagnostic traces remain private session artifacts; scratch scripts removed.
Existing global numeric IDs were confirmed unique in current data; the pre-existing
separate ID allocators are not an unlimited collision-free scheme and were not
migrated as part of this UI task.

This work is local and uncommitted. No push, deployment, real email, user catalog
save or credential change was performed. Physical devices, production behavior
and operational/mail/privacy checks remain separate; the browser transport
interruption is explicitly recorded rather than reported as a full baseline pass.

## Daily email settings and Equipment labels deployed - 2026-09-29

The owner authorized push/deploy. The exact implementation fingerprint matched
the candidate with 170 backend, 33 unit and 217 browser passes before publishing.
Release **`e91f28afd3452134dfe99070ea9132aa0ba81cb1`** deployed at
`2026-09-29T18:43:24Z`, using the verified kenny-daily SSH session.

Protected `/var/backups/styl/release-e91f28a` includes catalog/media/inquiries,
original environment, previous source/mode changes and frontend output, plus a
consistent 0600 SQLite analytics backup. The candidate was built separately;
170 backend tests and the Linux production build/TypeScript check passed.
Web/API were switched with rollback prepared; the report timer was briefly
paused and resumed. Environment, catalog and GeoIP hashes remained unchanged,
and all five application/maintenance/GeoIP services or timers were active.
No SMTP settings or real recipient values were entered during deployment.

Final application runtime is **`30d25896e68819cce6376af30fca15147a96cac2`**,
activated at `2026-09-29T19:01:21Z`, after the detail-width correction below.
Its separate protected backup is `/var/backups/styl/release-30d2589`; Linux
170-test backend/build checks passed again and data/config/GeoIP hashes matched.
Both staging builds and deployment logs/scripts were moved into their protected
release folders; the running build ID matched the staged candidate. Temporary
transfer files, local helper scripts and the stopped one-use transfer helper were
cleaned up. One follow-up script checksum initially differed because of Windows
CRLF versus Linux LF; the normalized reviewed hash was verified before execution.

Authenticated production checks confirmed private email settings:
enabled/effectiveEnabled false, recipients empty, revision 0/environment defaults;
the concise preview remained disabled and delivery history empty. Public
unauthorized GET/PUT settings requests returned 401. No production settings were
saved or real emails sent. The live phone detail check then found the gallery
width issue documented below; the rollout remained open for its verified
follow-up rather than reporting that failing phone check as passed.
After the correction, all three live browser flows passed: desktop Chromium,
phone Chromium and phone WebKit, including the production seven-image equipment
detail width, Equipment/Shop accessories navigation and compatible URLs. There
were no runtime errors or behavioral/catalog writes in those DNT-protected checks.
The same checks passed again after staging cleanup. Final private configuration
verification confirmed mail still off, recipients empty and revision 0; no settings
were saved or mail sent to make verification pass.

Validation totals must not be combined into a fictitious full run: the primary
release passed 170 backend / 33 unit / 217 full browser executions; the CSS-only
follow-up passed 76 affected layout/navigation executions plus the unchanged
backend baseline on Linux. Physical devices, real mail delivery and broader
operational/privacy gates remain separate. Local catalog edits and the historical
backup branch were not published or changed.

## Equipment-detail width found during live release verification - 2026-09-29

After deploying the settings/Equipment release `e91f28a`, the public detail-flow
phone check exposed an existing gallery sizing issue with the actual production
item's seven images: a 390px viewport had a 473px document. The gallery/title grid
children retained intrinsic minimum widths, letting the thumbnail strip widen
the implicit single-column grid. No customer data was changed to hide the issue.

An isolated seven-image fixture reproduced the exact 473px failure before the
fix. Added an explicit shrinkable single-column track and `min-w-0` on the two
detail grid children; the desktop two-column layout remains. New USR-003 coverage
checks 7 and 12 photos at 320/390/768/1440px, selecting the last thumbnail,
enlarging/closing media and asserting document width against the configured
viewport. All **76 affected layout/quote/navigation executions passed** across
desktop/phone Chromium and phone WebKit; build/TypeScript/scoped lint and editor
diagnostics passed. Backend and email settings are unchanged by this correction.

## Admin email settings and Equipment catalog UX - 2026-09-29 (local)

Completed the owner's five new requests. The owner clarified that Products
should be renamed Equipment while Accessories remains a separate catalog;
URLs, API/data field names, IDs and saved catalog content must stay compatible.

- Added Analytics → Daily email settings: enabled preference, editable recipient
  list, explicit save/reload, pending/error/conflict feedback and unsaved-state
  retention across admin tabs. Recipients accept lines or commas, up to 20,
  validated and deduplicated case-insensitively. Enabled requires a recipient;
  disabled may preserve or clear addresses.
- Protected GET/PUT settings endpoints store a revisioned configuration in private
  SQLite. Concurrent stale saves return 409; malformed input is 422 and unavailable/
  corrupt storage is 503, not a successful default state. After the first save,
  these preferences override the initial environment defaults. Current settings
  survive restarts/history cleanup and are included in SQLite backups, not
  catalog recovery ZIPs. No SMTP secrets or inquiry-notification settings changed.
- Preview, scheduled delivery and manual retries share those saved settings.
  Every recipient is checked again before its transactional delivery claim, so
  disabling/removing recipients stops unclaimed sends; an already in-progress
  email cannot be recalled. Saving itself sends nothing. Local/test/staging mail
  remains blocked even when the saved preference is on. The UI explains that
  enabled production may send the latest due report at the next 15-minute check.
- Both catalog toolbars now read Catalog → Arrange listing order/Done arranging
  → New, with the existing visual card movement, saving and selection behavior.
  Added Shop accessories beside Shop equipment; Equipment wording is consistent
  in navigation/catalog/admin views while existing quote journeys remain intact.
- Updated the English/Chinese email requirements, operations, responsive guidance,
  README and regression cases AN-017, ADM-011 and USR-011.

Final dirty candidate on `b4c6ff2`: implementation/test-file SHA-256
`67e00cc2cc9a2bebc911102a580005272a6fbf1e0c32757e56ccaa1846e81aec`
(23 changed/new code files, excluding user catalog data).

Verification:

- **170 complete backend tests and 33 frontend unit tests passed.**
- **All 217 configured browser executions passed**, including desktop Chromium,
  phone Chromium and phone WebKit, without test retries. Build/TypeScript passed;
  full lint had zero errors and the same five pre-existing image warnings.
  Relevant editor/Pylance diagnostics were clear.
- The initial targeted run had 96 passes and one WebKit arrange-mode failure.
  Its trace showed the moved card already at position 1 while the outer fieldset
  was still disabled. The test's non-waiting focus call therefore missed Done,
  and Enter stayed on the card. The test now waits for enabled and confirms
  keyboard focus before Enter; pointer coverage and toolbar assertions remain.
  The focused rerun and the final complete matrix passed. No UI defect was
  claimed fixed from that timing evidence.
- Local readonly browser checks confirmed both Catalog/Arrange/New toolbars,
  Equipment/Accessories navigation, the new shop link and the settings form at
  320px. DNT prevented synthetic traffic; no user settings, catalog order or
  records were saved by those visual checks. Screenshots and the diagnostic trace
  remain private session artifacts; the temporary verification script was removed.

These changes are local and uncommitted, not deployed. Production email remains
unchanged/disabled; no real email or credential changes were performed. The user's
local products/accessories/hero edits remain intact. Full automated regression
passed; physical devices, actual mailbox delivery and production operation of the
new settings interface remain unverified until an approved rollout.

## Concise daily email deployed - 2026-09-29

Deployed application **`dbccf7a69d61bdd15bab0c78b150646d67f0366f`** using the
verified kenny-daily Lightsail SSH session. Activation completed at
`2026-09-29T17:47:06Z`. The protected backup is
`/var/backups/styl/release-dbccf7a`; current data, original environment, previous
source and frontend build were preserved before an isolated build.

The production host passed **156 backend tests** and the production
build/TypeScript check. No dependency versions changed. Only web/API services
were briefly switched; the maintenance timer was paused during the switch and
resumed. Rollback was prepared but not needed. The environment file was
byte-identical afterward, including SMTP and disabled-email settings; customer
data checksums matched. All five application/maintenance/GeoIP services or timers
were active. Staging output and deployment logs/scripts were moved into the
protected release backup, and transient transfer files were removed.

The actual authenticated production preview returned **template version 3**:
22 lines for the measured day, key business metrics present, screenshot technical
block absent, concise HTML table present, and email sending false. Both text and
HTML outputs were saved privately for release evidence, without printing tokens
or sending an email. Desktop Chromium, phone Chromium and phone WebKit live
public/admin-entry smoke checks passed with no runtime errors or server writes;
DNT avoided synthetic analytics traffic. Local preview layout was also verified
at 320px, and HTML at 390px.

Current verification: 156 complete backend tests, 33 frontend unit tests,
27 affected analytics/browser executions, build/TypeScript and scoped lint/
Pylance checks passed. This was a targeted email rollout, not another full
181-browser/physical-device/operational regression. Actual recipient approval,
email enablement and inbox delivery remain separate.

## IAM daily access and concise daily email - 2026-09-29

Verified the existing `kenny-daily` user already had console access and the
Lightsail-only customer-managed policy through `LightsailDailyUsers`; no
AWS-wide IAM permissions or programmatic access keys were needed. The user chose
a passkey and completed the native enrollment privately. AWS then showed MFA
enabled and one passkey. The subsequent signed-in identity was independently
confirmed as kenny-daily, with Ubuntu-1 visible and an SSH connection that returned
the expected hostname/ubuntu user and active STYL web/API services. IAM-dashboard
denials were out-of-scope IAM administration, not a Lightsail permission defect.
No password or permission expansion was performed.

The user requested removal of the screenshot's technical email explanations and
a simpler business summary, then explicitly authorized deploying it after tests.
The background tasks had been cancelled without implementing that change, so the
parent completed it directly rather than treating earlier aggregate tests as
verification of the new template.

Version 3 renders both plain text and HTML with date/Pacific time, page views and
seven-day baseline, saved inquiries, estimated active minutes/hours, cart adds and
quote opens, up to three ranked equipment items and country/source entries, and
the dashboard link. Static privacy/retention/cutoff/first-tracking paragraphs,
redundant observations and empty sections are removed from email only; full
dashboard coverage remains. Real disabled-collection, unavailable-inquiry,
rejected-measurement and error conditions retain concise Attention messages.
Partial days show Through HH:00 and do not compare a partial count to a whole-day
percentage. HTML uses a compact table/headings and escapes catalog text.
Cross-version accepted/ambiguous delivery protections and disabled-email guards
remain unchanged; version 3 prevents reuse of warning-heavy version-2 snapshots.

Verification: **56 focused analytics/report tests, 156 full backend tests,
33 frontend unit tests and the final 27 analytics E2E executions passed**.
Production build/TypeScript and scoped lint/editor/Pylance checks passed.
An initial WebKit response-validation test clicked during focus-driven scrolling
and sent no new request; its preserved trace demonstrated this. That test now
waits for the button to be enabled and uses keyboard activation, without retries
or weakening the report/error assertions. The complete affected browser matrix
then passed. Local admin preview at desktop/320px and HTML at 390px were inspected;
the API returned the concise content with sending disabled. No real email was sent.

Prior a611b4e deployment-status documentation was also brought up to date. This
does not retroactively certify physical devices, legal review or mailbox delivery.

## Production release: aggregate analytics, catalog recovery and ordering - 2026-09-28

The user explicitly authorized deployment after sharing the signed-in Lightsail
console. Navigating the SSH terminal inside that same authenticated tab succeeded;
new tabs had redirected to sign-in. No passwords, admin tokens, SMTP credentials
or GeoIP license contents were copied into browser input or output.

Application release **`a611b4ee5a8b7ccd4d8b48de7734e0a87cb35066`** was committed
and pushed on main, then deployed to Ubuntu-1 / `54.156.37.31`. It includes the
previously local catalog recovery ZIP, visual per-card listing order, immediate
cart feedback, and the final aggregate-only analytics/Privacy UI. The local
products/accessories edits and untracked hero data were deliberately excluded.
The historical backup branch was not moved.

### Protection and preparation

- Prior runtime was `bc45b22`; web/API/Caddy and GeoIP timer were healthy. The only
  server worktree changes were executable modes on the two existing deploy shell
  scripts; both were preserved.
- Created protected root-only `/var/backups/styl/release-a611b4e`, containing
  catalog/uploads/inquiries, source revision and mode patch, protected original
  environment and service/Caddy files, previous frontend output and backend
  virtual environment. Gzip integrity and data/GeoIP hashes were verified.
- Extracted the exact candidate to a separate staging directory, checked unchanged
  package-lock contents, reused matching frontend dependencies, and installed the
  newly declared tzdata dependency. On production Node 22.23.2 / Python 3.12.3:
  **149 backend tests, 33 frontend unit tests and production build/TypeScript
  passed** while the existing application remained serving.
- Activation prechecked current source/config/data, then performed a short
  web/API stop, fast-forward and build-directory replacement. The reviewed script
  included code/config/venv/build rollback on failed health checks; rollback was
  not needed. Runtime returned successfully at approximately
  `2026-09-29T06:52Z` (September 28, 23:52 Pacific).

### Activated configuration

- `STYL_ANALYTICS_ENABLED=true`, aggregate-only production mode, private
  `/var/lib/styl-analytics/analytics.sqlite3`, America/Los_Angeles timezone.
  Directory is 0700 and SQLite file 0600, owned by styl.
- Daily-email sending remains explicitly **disabled**; no recipients or SMTP
  settings were changed. The 15-minute report/retention timer was installed and
  enabled; both its first manual run and next scheduled run completed with
  sending disabled. The target daily schedule remains 08:00 Pacific.
- No domain/DNS/Caddy changes, server reboot, catalog edits or test inquiry/email
  sends were performed. Production data and GeoIP database/config hashes remained
  unchanged; all non-analytics environment lines were preserved.

### Live verification

- HTTPS health and analytics config returned success. US/USD location remained
  correct and forged country/forwarding headers did not change pricing.
  www redirects to the HTTPS root domain; DNT/GPC disable measurement.
  Unauthenticated admin/analytics/catalog-backup endpoints return 401.
  Retired session creation returns 410.
- Fresh desktop Chromium, 390px phone Chromium and phone WebKit passed live
  catalog/detail/cart-add feedback/cart/quote prefill/accessories/Privacy/admin
  sign-in-page checks, with **zero runtime and console errors** in this run.
  No agreement or technical tracker status was present and there was no horizontal
  overflow. Checks used DNT, produced no behavioral writes or inquiry submission,
  and did not change any user's saved browser choices.
- After moving the isolated build into protected release artifacts, one repeat
  automation run missed the transient Added label. An instrumented rerun of all
  three browsers passed with zero runtime/console errors. The intermittent miss
  was not reproduced with diagnostic output and is not claimed fixed; distinguish
  these smoke results from a guarantee that brief feedback can never be missed.
- Server-local authenticated report/preview/delivery checks passed without
  printing credentials. Aggregate DTO contains no session/visitor/funnel fields;
  times are hour-rounded, delivery history empty and real email disabled.
  Raw visitor/session/event rows were confirmed absent/empty.
- Downloaded the actual protected catalog recovery ZIP: **3 products,
  16 accessories, 100 media files**. Verified the archive, ran its included
  standalone recovery tool with system Python into a new protected directory,
  and matched restored source bytes/checksums. This is a same-server isolated
  recovery drill, not an off-server disaster-recovery certification.
- A consistent SQLite backup was created through the supplied backup command,
  separate from catalog backup and the existing catalog-only periodic backup.
  Automatic off-server analytics backups are not configured by this release.
- Two verification-tool issues were corrected without changing the release:
  an initial compressed script transfer failed its integrity step and was not
  executed; the first private recovery check needed an explicit backend import
  path. Its corrected rerun passed. Protected deployment/recovery artifacts are
  retained; transient transfer files and local verification scripts were removed.

Pre-release complete automated baseline remains **149 backend / 33 unit /
181 browser executions**, with zero lint errors and five pre-existing image
warnings. Production manual gaps remain: physical devices, independent Canadian
egress, jurisdiction-specific privacy review, actual approved email recipients/
inbox delivery, off-server restores and longer-term capacity/performance. The
successful short WebKit run does not establish that the earlier intermittent
RSC-prefetch warning can never recur.

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
