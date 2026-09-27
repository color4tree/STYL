# STYL project history and handoff

Last recorded: 2026-09-27

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
