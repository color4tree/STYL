# STYL living regression test plan

Version: 1.0

Updated: 2026-10-02

Scope: System behavior, admin workflows, and customer experience on desktop and
mobile. This is an expandable test catalog and execution/sign-off process.

Baseline: committed history through `c9837e6` plus the pending Round 2 working
changes, including the latest **standalone, price-free Home banner** decision.
Record the exact tested commit and working-tree patch for every future run.

Agent workflow: [styl-regression](../.github/skills/styl-regression/SKILL.md).
Repository [Copilot instructions](../.github/copilot-instructions.md) route full
regression requests to this plan and require coverage maintenance for new features
and bug fixes. The plan remains the source of truth; the skill does not replace
case-level evidence or make manual checks automatic.

## 1. Purpose and operating rules

A regression pass should answer:

1. Does the system still enforce the correct data, visibility, and privacy rules?
2. Can a real customer browse, inspect equipment, select items, and request a quote?
3. Can an administrator edit safely and understand whether changes were saved?
4. Are previous bugs prevented and agreed enhancements still present?
5. Which environments and failure cases were actually verified?

Passing tests provides evidence for a defined build and environment; it is not a
guarantee that every browser, network, deployment, or future data combination works.

### How this document is maintained

- Assign a stable ID to every new case. Never recycle an ID for a different rule.
- Every bug fix gets a regression case reproducing the failure when feasible.
- Every enhancement gets both a positive workflow and relevant negative/boundary
  checks at the system and user levels.
- Link each case to actual automation where available. Do not label a planned
  test automated merely because a nearby test exists.
- Keep the expected behavior synchronized with the latest approved requirements.
- Retire superseded expectations with a reason; do not silently rewrite history.
- Do not mark a reported bug Fixed without a reproduced failure and verified fix,
  or another explicitly documented resolution.
- Record failures, blocked cases, untested areas, and accepted warnings alongside
  passes. Never report skipped/blocked/manual-not-run cases as passing.

### Reference documents

- [Current behavior and execution setup](../README.md)
- [Project history and decisions](project-history.md)
- [Responsive UX design](mobile-ux-design.md)
- [GeoIP provisioning and trust boundary](geoip-pricing.md)
- [Deployment, backup, and rollback](lightsail-deployment.md)
- [Future catalog/admin schema](catalog-and-admin-schema-design.md)

The future schema is not the current release oracle. Global SKUs, unified
Equipment/Attachments storage, and fully configurable enums are not implemented
by the current Round 2 work.

## 2. Current product rules: the regression oracle

These rules supersede earlier requirements when they conflict:

| Area | Current expected behavior |
| --- | --- |
| Country prices | Independent Canada/CAD and US/USD values for products and accessories; no currency conversion or copying between markets |
| Visitor market | Canadian and unknown locations use CAD; identified US/other non-Canadian locations use USD |
| Missing price | Hide the item for that market, including product detail access and cart eligibility; flag missing markets in admin |
| Price display | Catalog/detail/cart values include currency and exactly two decimals, e.g. `CAD $4,005.25` |
| Legacy pricing | Preserve the original price only in its original currency; the other market remains unset |
| Publication | New Product and Accessory default to Draft; existing Product lifecycle is retained and Accessories gain equivalent controls/filtering |
| Legacy status | Records without a publication status retain their existing published behavior; unrelated updates do not unpublish them |
| Categories | One controlled source for both forms; normalize Bench to Benches and case/spacing without a broad taxonomy redesign |
| Catalog brand | Optional text, at most 200 characters, on equipment/accessories. Trim on save; omitted updates preserve, null/blank clears. Cards/details/admin lists show Brand first then Category with a 12px gap, no dot; missing brand shows category alone. Legacy names/brands are not inferred on reads or saves |
| Technical content | Separate descriptions, public use, features, included contents, selling unit, finish/colour, compatibility, and optional weight |
| Captured date | Private date-only `YYYY-MM-DD`; no timezone conversion or day shift |
| Home banner | Independently editable text and image; no product selector, price field, price preview, or automatic price display |
| Engineering details | Home banner tab edits heading/optional intro and four image/title/description cards; existing content is the legacy default, no read-time source rewrite. Save publishes; uploaded/local references participate in cleanup and complete recovery |
| Banner responsive rule | Hidden below 768 CSS px; visible at 768 px and above |
| Brand principle | Exact statement remains prominent in the introduction, above shopping actions, without an About-section duplicate |
| Collection views | All products first/default on home/header; Equipment/Accessories filter the same home catalog with URL/history support. All keeps equipment order followed by accessory order; legacy /accessories and product detail URLs remain valid |
| Listing sequence / Featured | Saved manual sequence is primary for both catalogs; new items append; market/draft filtering preserves remaining relative order. Featured is retained as metadata and does not override sequence or determine publication |
| Media | Up to 12 combined photos/videos; images up to 8 MiB, source videos up to 50 MiB |
| Upload feedback | Current batch results are distinct from unresolved earlier failures; failed-only retry does not resend successful files |
| Commerce | Cart is a selection for a quote, not a paid order; quantity counts sale units and remains capped at 10 per item |
| Add feedback | The clicked card/detail/mobile-sticky button shows Added immediately for 2.5 seconds after a real successful cart addition; failed/no-add operations never show success; existing count and live feedback remain |
| Analytics privacy | Automatic first-party measurement only after enabled aggregate-only config; no storefront consent panel or technical status. Ordinary Privacy notice with boolean opt-out; preserve prior decline and DNT/GPC/admin/internal/bot exclusions; clear retired identifier keys without resetting privacy choices. No browser/session/event/page IDs or raw event/journey persistence |
| Analytics reporting | Private server-hour totals and independent coarse dimensions, not combined fingerprints; counts, total active estimate and average web vitals, no visitor/session/funnel/attribution/median metrics. Saved inquiries are independent business totals. Pacific dates/manual refresh/hour-level last activity; preview excludes incomplete hour; no age expiry of business history; no legacy history in new reports or destructive migration; daily 00:15 Pacific for the previous completed calendar day with production-only explicit mail enablement and separately approved recipients |
| Backup & Records | Website logs and business history never expire by age/size; create/download/verify before optional explicit exact-record removal. Current/pending/changed records, settings and mail duplicate-prevention metadata stay. Verified server ZIP deletion is separate; operational logs expire after 14 days only after website capture separation |
| Layout | Mobile and desktop both remain optimized; mobile changes must not remove desktop functionality |
| Mobile catalog navigation | All products, Equipment and Accessories appear directly below 1024px without opening Menu; all three also appear in desktop navigation |
| Catalog card layout | Shared compact gallery/category/name/Price/optional higher MSRP, then Show more/Add/desktop Details. Body and quantity controls initially hidden on every width; deliberate expansion reveals full unclipped content and resize preserves choice. Mobile omits Details button but title links remain |
| MSRP | Optional independent CAD/USD MSRP; public selected-market scalar only. Labeled struck MSRP only above Price. Missing/equal/lower values do not create a discount; Price alone controls visibility, cart and quotes |
| Quote message layout | Numbered item blocks with separate quantity, known package contents and unit-price lines; blank lines between items and final request; editable text and line breaks preserved |
| Catalog recovery | Admin-only private ZIP contains saved catalogs including drafts/private fields, banner and referenced local media/posters, manifest/checksums and an offline tool; incomplete/external media refuses export; restore targets only a new directory; browser upload/import deferred |

Exact business principle:

> Maximize customer value first, then capture a fair share of the value created.

## 3. Test levels, priority, and coverage notation

### Test levels

- **System:** API validation, persistence, regional selection, authentication,
  privacy, media processing, caching, recovery, and deployment integration.
- **End-user/admin:** real browser workflows, keyboard/touch interactions,
  visible feedback, responsive layout, and saved-state behavior.
- **Operational:** installed service/proxy configuration, real country database,
  backup/restore, actual email delivery, and production smoke checks.

### Priority

- **P0:** incorrect money, exposed private/draft data, lost saved data, or a blocked
  core selection/admin/inquiry flow. Blocks release in the applicable environment.
- **P1:** important functionality, accessibility, media usability, or navigation.
  Requires a fix or explicitly approved, documented exception before release.
- **P2:** lower-risk polish, exploratory checks, and measured improvements.

### Coverage notation used in the catalog

- **A:** existing automation covers the stated core check.
- **P:** partially automated; complete the remaining manual or additional checks.
- **M:** manual/operational check; no equivalent complete automation is claimed.
- **F:** future requirement, not an active release gate until approved/implemented.

Coverage is not a run result. An A case can still be Not run, Failed, or Blocked.

## 4. Existing automation map

Use these short references in the case tables:

| Ref | Source | What it currently provides |
| --- | --- | --- |
| B-AUTH | [test_admin_auth.py](../backend/tests/test_admin_auth.py) | Admin access, inquiry validation/storage/email behavior, product specifications/status, gallery persistence and shared-file cleanup, banner updates |
| B-CAT | [test_catalog_contracts.py](../backend/tests/test_catalog_contracts.py) | Names/prices, accessory fields, provenance privacy, category source, media count and image-size boundary |
| B-GEO | [test_location.py](../backend/tests/test_location.py) | Country resolver, invalid/private IPs, ignored headers, missing/corrupt/replaced database, reader concurrency; mocked MMDB records |
| B-REG | [test_regional_catalog.py](../backend/tests/test_regional_catalog.py) | Regional public/API results, no-store headers, missing prices, Draft behavior, legacy mapping, dates/weight, price-free legacy banner |
| B-MEDIA | [test_media.py](../backend/tests/test_media.py) | Supported video formats, limits, decode/timeouts, conversion/poster, byte ranges, cleanup, real HEVC conversion fixture |
| B-BACKUP | [test_catalog_backup.py](../backend/tests/test_catalog_backup.py) | Authenticated complete ZIP, strict source reads, locks, private scope, checksum/path/size rejection, standalone cold restore and a fresh API on recovered data |
| B-ORDER | [test_catalog_order.py](../backend/tests/test_catalog_order.py) | Protected full-permutation ordering, current-order conflict checks, field preservation, market filtering and backup sequence preservation |
| B-MSRP | [test_catalog_msrp.py](../backend/tests/test_catalog_msrp.py) | Optional regional MSRP validation/persistence/selection, legacy/partial/clear semantics and accessory detail access/privacy/visibility |
| B-BRAND | [test_catalog_brand.py](../backend/tests/test_catalog_brand.py) | Optional brand validation/create/update/clear, legacy/no-read-write semantics, market/privacy boundaries, dry-run/backed-up prefix migration, conflicts and unrelated-field preservation |
| U-BRAND | [public-catalog.test.mjs](../frontend/tests/public-catalog.test.mjs) | Missing/null/blank brand compatibility, invalid public brand rejection, escaped brand-first shared label with no dot |
| E-BRAND | [catalog-brand.spec.ts](../frontend/tests/e2e/catalog-brand.spec.ts) | Both admin editors save/reload/clear brand, retain dirty/failed edits, and show category/brand on cards/details without long-brand overflow across all configured browser projects |
| B-HOME | [test_hero_engineering.py](../backend/tests/test_hero_engineering.py) | Engineering schema/defaults/partial updates, auth, corruption/write failure, shared image/poster retention |
| B-RECORDS | [test_records.py](../backend/tests/test_records.py) | Private consistent ZIP/cold restore, auth, checksum/path rejection, saved-copy verification, exact source removal, preserved new/changed/live records, interrupted cleanup, archive deletion and no age expiry |
| E-RECORDS | [records.spec.ts](../frontend/tests/e2e/records.spec.ts) | Protected admin create/download/verify/optional cleanup, separate server ZIP deletion, retry/busy/dirty guards and responsive behavior |
| E-HOME | [engineering.spec.ts](../frontend/tests/e2e/engineering.spec.ts) | Four-card editing/upload/save/reload/public rendering, multiline content, dirty and busy states, invalid inputs, failures and mobile width |
| B-AN | [test_analytics.py](../backend/tests/test_analytics.py) | Revised aggregate-only assertions: strict unlinked ingestion/legacy 410, independent dimensions, no raw persistence, trusted market/item validation, hour/DST boundaries, independent business inquiry totals, legacy isolation/retention and exports; see AN-001..014 for final integrated evidence |
| B-REPORT | [test_analytics_reports.py](../backend/tests/test_analytics_reports.py) | Revised complete-hour cutoff/aggregate snapshots plus existing non-production sending guards, SMTP mocks, per-recipient mail claims/retries/ambiguous states and SQLite backups; updated outcomes recorded separately |
| U-AN | [analytics.test.mjs](../frontend/tests/analytics.test.mjs) | Rewritten aggregate-only assertions: automatic config gating, Privacy boolean opt-out/legacy decline, exclusions/identifier cleanup, identifier-free Web Lock/visibility/idle bounds, memory-only batches without ambiguous retries, local rerender suppression and safe failure; final execution evidence pending |
| U-CART | [cart.test.mjs](../frontend/tests/cart.test.mjs) | Currency formatting, cents, sale-unit text, regional reconciliation, legacy cart compatibility, quantity cap, storage failure |
| E-CATALOG | [catalog.spec.ts](../frontend/tests/e2e/catalog.spec.ts) | Production-build browser journeys, admin/content/media/cart/inquiry/banner/responsive checks |
| E-MARKET | [market-ui.spec.ts](../frontend/tests/e2e/market-ui.spec.ts) | Mocked Canadian browser pricing/repricing and visible current-versus-earlier upload results |
| E-ROUND2 | [round-two.spec.ts](../frontend/tests/e2e/round-two.spec.ts) | Both catalogs: Draft/missing-price/weight/category workflows and exact date entry-to-reload trace |
| E-QUOTE | [quote-navigation.spec.ts](../frontend/tests/e2e/quote-navigation.spec.ts) | Desktop/mobile quote landing from cart/product/direct/same-page links, frame-by-frame cart/product/header transition positions with separate loading gates and reduced motion, delayed/failed content, input preservation, and cancellation after user interaction; also configured in mobile WebKit |
| E-LAYOUT | [catalog-layout.spec.ts](../frontend/tests/e2e/catalog-layout.spec.ts) | Compact cards, all-width explicit expansion, media counts, keyboard/resize/large-text checks, 7/12-image detail widths and multiline quotes; desktop/phone Chromium and WebKit |
| E-COMPACT | [compact-catalog.spec.ts](../frontend/tests/e2e/compact-catalog.spec.ts) | All/default/filter/order/history, shared compact cards and desktop/mobile actions, MSRP display/cart pricing, accessory details and explicit partial-source failures |
| E-MSRP | [msrp-admin.spec.ts](../frontend/tests/e2e/msrp-admin.spec.ts) | Both editors: optional CAD/USD MSRP validation/save/reload/clear, dirty guards/error retention and responsive input widths |
| E-BACKUP | [catalog-backup.spec.ts](../frontend/tests/e2e/catalog-backup.spec.ts) | Admin ZIP download, saved-data/privacy warnings, retained edits, failure/retry and responsive behavior, including mobile WebKit |
| E-ACTIONS | [cart-feedback-order.spec.ts](../frontend/tests/e2e/cart-feedback-order.spec.ts) | Immediate success/failure/limit feedback on cards and details, mobile sticky action, saved ordering and editor retention on desktop/mobile Chromium and WebKit |
| E-AN | [analytics.spec.ts](../frontend/tests/e2e/analytics.spec.ts) | Revised cases prepared, execution evidence pending: real isolated automatic collector/dashboard, no storefront consent/status panel, /privacy boolean opt-out/exclusions, unlinked item/cart/quote counts, privacy/outage isolation, CSV and disabled complete-hour email preview across configured desktop/phone Chromium and phone WebKit |

Representative exact entry points for diagnosis:

- B-REG: `test_country_prices_and_no_shared_cache_for_all_public_surfaces`
- B-REG: `test_missing_price_hides_item_and_admin_flags_it_without_conversion`
- B-REG: `test_banner_restores_custom_content_and_never_exposes_legacy_price`
- B-AUTH: `test_inquiry_storage_failure_does_not_report_success_or_send_email`
- B-AUTH: `test_uploaded_gallery_reorder_and_cross_catalog_cleanup`
- E-ROUND2: `${endpoint}: captured date survives editing notes, save and reload`
- E-CATALOG: `home banner custom content and upload persist without any price information`
- E-CATALOG: `upload partial failure retries only failed media and enforces 12-item cap`
- E-MARKET: `a successful new upload batch separates earlier failures from current results`

Do not use a test-name match as proof of every clause in a case. Inspect assertions
when expanding the coverage map.

## 5. Environments and safe fixture data

### 5.1 Environment matrix

| Environment | Required checks | Important limitation |
| --- | --- | --- |
| Local API/unit | All backend and frontend unit checks | Does not exercise production proxy/browser/native controls |
| Local production-build browser | Desktop Chromium 1440 x 1000, phone Chromium 390 x 844, boundary widths | Phone viewport/touch emulation is not a physical phone |
| WebKit | Current configured Round 2 date/publication tests | Windows WebKit is not certification of physical iOS Safari; other journeys are not automatically covered by this project |
| Staging, production-like | Actual Caddy/Uvicorn trust chain, real MMDB, persistence/restart, approved test mailbox | Must use staging data and controlled accounts |
| Physical devices | iPhone Safari and Android Chrome; portrait/landscape and keyboard | Record OS/browser/device versions, not just "mobile passed" |
| Production smoke | Read-only public browsing, health/version checks, approved limited admin/mail checks | No destructive fault injection, bulk edits, or unapproved customer-data changes |

Boundary widths: **320, 390, 767, 768, 1023, 1024, 1440 CSS px**.
Also test text zoom, short landscape heights, long names, and slow connections.

Date timezones: **America/Toronto** and **Pacific/Auckland**.
When diagnosing physical-device behavior, also record locale, input method,
autofill, and whether the date was typed by segments or picked from a calendar.

### 5.2 Reusable fixtures

Use unique test names and noncustomer data. Reference examples:

| Fixture | Values / purpose |
| --- | --- |
| F-EQUIPMENT | Published equipment; CAD 4005.25; USD 4000.95; weight `35.5 kg`; main image plus second image and short video |
| F-PAIR | Published attachment/accessory; CAD 29.95; USD 19.95; Pair; package quantity 2; distinct descriptions, use text, and features |
| F-MISSING-CA | CAD unset; USD 19.95; published; hidden for Canada and unknown locations |
| F-MISSING-US | CAD 29.95; USD unset; published; hidden for identified US/other non-Canadian locations |
| F-NO-PRICES | Both prices unset; admin warnings; not public in any market |
| F-ZERO | Price 0.00 in a selected market; must not be mistaken for missing |
| F-DRAFT | Both market prices supplied, Draft; privacy tests independent of price hiding |
| F-LEGACY | Single USD or CAD price; missing status; category `Bench`; image-only media; old cart without optional fields |
| F-PROVENANCE | Captured date `2026-09-26`; synthetic private marker distinct from every public field |
| F-BANNER | Independent tag/number/heading/title/image plus a legacy stored priceLabel marker that must never be returned/rendered |
| F-MEDIA | Valid supported images; deterministic short video with visible progression and audio; invalid/oversized files |

Use a synthetic regional fixture for deterministic UI tests. Separately verify
real GeoIP with controlled known-country egress against the installed database.
Do not equate injecting a country header or mocking a JSON response with real
IP-to-country detection.

For GEO-002/GEO-005 and OPS-002 investigations, capture `/api/market` from the
affected visitor's exact host/network. `unknown` plus CAD is fallback, not evidence
of a detected Canadian location; unknown/USD identifies the earlier fallback
policy and should prompt a deployed-version check. A local loopback request or a second investigator's
response does not establish what the affected visitor received. Follow the
[GeoIP diagnostic procedure](geoip-pricing.md#troubleshooting-a-canadian-visitor-seeing-usd)
without exposing credentials or raw visitor IPs.

### 5.3 Safety and cleanup

- Never point the E2E runner at production storage or a production admin token.
- The runner creates temporary catalog data and an ephemeral token and disables SMTP.
- No real customer contact data, production credentials, or private source
  documents in fixtures or committed snapshots.
- Failure traces can contain form values and the ephemeral test token. Keep test
  reports private and ignored by Git; do not upload them blindly.
- Ensure test ports 3102 and 8102 are free. Do not kill unrelated Node/Python processes.
- Do not override test data-directory settings with a valuable existing directory:
  the test harness owns and removes its temporary directory.
- Clean only specific known test artifacts. Never delete a broad workspace or
  temporary root to resolve a failed cleanup.
- GeoIP/provider credentials and licensed databases stay outside the repository.

## 6. When to run which regression set

The 2026-09-29 workflow clarification replaces the blanket requirement to run
every suite before any push. Use the
[efficient-delivery skill](../.github/skills/styl-efficient-delivery/SKILL.md):
classify impact first, fail fast on one relevant case/browser during iteration,
and then run the final scope below. Explicit full/comprehensive verification and
shared/high-risk changes retain full coverage; speed does not excuse incomplete
evidence or weakened assertions.

| Run | Trigger | Minimum scope |
| --- | --- | --- |
| Documentation/skill checks | Documentation or workflow-guidance only | Content/link/whitespace checks and existing documentation tests; no application suite solely for this change |
| Change-focused | Each functional change | Related cases at both layers plus direct downstream consumers |
| Low-risk UI release | Isolated wording/style/page-layout changes | Affected desktop/mobile navigation and layout checks, relevant lint/type/build; no unrelated backend suite |
| Core smoke | Before handing off a functional build | Affected core journeys; broaden to auth/create/save/reload/pricing/cart/inquiry/banner when those consumers are impacted |
| Full code regression | Explicit full/comprehensive verification, or shared/high-risk changes | Backend suite, frontend unit suite, lint, type/build, entire configured E2E suite; examine warnings |
| High-risk staging release | Changes to auth/privacy/pricing/shared persistence/media deletion/recovery/proxy trust/delivery, or broad shared UI | Full code pass plus applicable physical-device and operational P0/P1 cases; unavailable checks remain Blocked/Not run |
| Post-deploy smoke | After deployment | Verify actual deployed revision, health, region pricing/no-store, public visibility, media and approved inquiry flow |

Deploy authorization does not itself request a full regression or a real email.
Use the scoped gate unless impact or an agreed release requirement calls for the
full baseline. The current E2E runner still rebuilds on each invocation: do not
pretend build reuse is configured. A future reuse path must verify the candidate,
dependencies/toolchain and build environment while keeping API fixtures isolated.
Keep one worker until shared fixture/service dependencies are deliberately isolated.

Examples of impact selection:

- Price/model changes: SYS-003 through SYS-009, GEO-001 through GEO-005,
  ADM-002/005, USR-002/005/006, and inquiry context.
- Provenance/date changes: SYS-010/011, ADM-004, DATE-001 through DATE-004.
- Gallery/upload changes: MED-001 through MED-008, ADM-006/007,
  USR-003, SYS-012, and OPS-003.
- Shared layout/controls: all USR cases and ADM-001/003/007/008 at desktop/phone
  boundaries; business principle and banner must remain correct.
- Banner changes: SYS-013, ADM-008, USR-007/008; shared-image cleanup if uploads change.
- Publication/category changes: SYS-005/006/007, ADM-002/005,
  USR-001/002/005 and direct product URL checks.

## 7. System-level test catalog

### 7.1 Core API, persistence, content, and privacy

| ID | Priority | Steps / input | Expected result | Coverage |
| --- | --- | --- | --- | --- |
| SYS-001 | P0 | Start frontend/API using isolated configuration; call health and public catalog routes. | Services start; health is valid; empty catalog is distinguishable from a failed request; no test data touches production. | P: E-CATALOG harness; startup/health response contract also inspect manually |
| SYS-002 | P0 | Use no token, wrong token, valid token, and unconfigured admin access against protected list/write/upload routes. | Unauthorized access rejected; unconfigured access returns the repository-standard unavailable response; failed attempts do not mutate records/files. | P: B-AUTH/B-MEDIA/E-CATALOG cover key paths; expand explicit route matrix as endpoints grow |
| SYS-003 | P0 | Create and update each catalog using 19, 19.5, 19.95, 0, negative, nonfinite, too-large, and excess-precision prices in each market. | Valid amounts retain cents; invalid values receive clear errors and do not change existing prices. Zero is available; null is missing. | A: B-CAT/B-REG/U-CART; admin cases in E-CATALOG/E-ROUND2 |
| SYS-004 | P0 | Set CAD and USD independently; update/clear one while omitting the other. Load legacy single-price records. | Other-market price survives; explicit null clears only that market; no exchange-rate conversion/copy; legacy value appears only in original currency. | A: B-REG |
| SYS-005 | P0 | Create both item types without status; publish, reload, change only status to Draft; request public lists and selection; request product URL directly. | New defaults Draft; published eligible item is visible; Draft excluded from every public surface. Product direct URL returns unavailable. Do not invent an accessory detail endpoint that does not exist. | P: B-AUTH/B-REG/E-ROUND2; maintain explicit endpoint matrix including selection |
| SYS-006 | P0 | Load legacy records without status; edit an unrelated field while omitting status. | Existing published behavior preserved. No broad migration silently hides legacy items. | A: B-REG, supplemented by legacy fixture review |
| SYS-007 | P1 | Use Bench, Benches, case/spacing variations, an existing custom category, and an invented category. | One canonical Benches option; both forms share options; old references remain valid; unknown new labels rejected; no unrelated category reclassification. | A: B-CAT/B-REG/E-ROUND2 |
| SYS-008 | P1 | Save distinct short/full/use descriptions, features, finish, included contents, Pair/2, and weight for both applicable types; reopen and clear optional fields. | No field overwrites another. Spec omission/clear behavior is deliberate; optional unknown values accepted; equipment weight retained. | P: B-CAT/B-REG/E-CATALOG/E-ROUND2; include explicit display check for equipment weight |
| SYS-009 | P0 | Apply an invalid update to an existing item; simulate an authorized storage failure on isolated/staging data. | No success-shaped response; original valid data remains readable; no partial catalog write. | P: invalid-update preservation covered by B-CAT/B-REG; catalog storage-failure injection needs additional coverage |
| SYS-010 | P0 | Save unique private notes, source URL/listing ID/date; query admin and every public list/detail/banner/selection route. | Admin sees authorized private fields. Public payloads contain none of those private fields/markers. Hiding HTML alone is insufficient. | P: B-CAT/B-REG/E-CATALOG/E-ROUND2; expand nested-field matrix with future schema additions |
| SYS-011 | P0 | Enter valid/invalid captured dates, then edit notes; inspect UI value, request, response, persisted record, and reload. | Exact valid date-only string retained; invalid date rejected; no timezone shift or public exposure. | A for exact current trace: B-CAT/B-REG/E-ROUND2; see detailed DATE cases |
| SYS-012 | P0 | Share uploaded images/video/posters across items and banner; reorder, remove one reference, delete an item, then remove the last reference. | Still-used files remain; only unreferenced uploads are cleaned; order and cover remain correct. | A: B-AUTH/B-MEDIA |
| SYS-013 | P1 | Load legacy custom banner containing priceLabel; edit tag/number/heading/title/image; save/reload; attempt unsupported price/selector fields. | Original text/image retained, price omitted from API/editor/public output, legacy price removed on subsequent save, unsupported new fields rejected. | A: B-AUTH/B-REG/E-CATALOG |
| SYS-014 | P0 | Save an inquiry, simulate SMTP absent/failing, then simulate storage failure before notification. | Receipt only after persistence; SMTP failure does not discard inquiry; storage failure is not success and sends no email. | A: B-AUTH; real receipt in E-CATALOG |
| SYS-015 | P0 | Submit invalid email, whitespace/empty required text, oversized content, and control-character email input. | Clear validation failure; no invalid stored inquiry or unintended mail headers; optional legitimate blanks remain accepted. | P: B-AUTH covers listed API cases; keep client/API validation matrix synchronized |
| SYS-016 | P0 | Configure a sender different from two comma-separated recipients; include a duplicate, an invalid/empty list, and partial SMTP refusal. Exercise STARTTLS and implicit TLS. | Valid recipients receive one envelope entry each, From remains the sending mailbox, Reply-To remains the customer. Default single recipient still works. Invalid configuration sends nothing; refusal retains inquiry with failed email status rather than claiming all recipients accepted. | A: B-AUTH multi-recipient tests; real delivery to every mailbox still requires OPS-006 |
| SYS-017 | P0 | Download catalog backup with valid/invalid/no auth; include drafts, private metadata, both currencies, shared media, uploaded video/poster, bundled image and custom/absent banner. Fail source JSON, media, storage and concurrent generation. | Private no-store ZIP, IDs/fields/media intact, correct filename/length/checksums, no credentials/inquiries/unreferenced files. Source lock prevents mixed snapshots. Missing/corrupt/external media never yields a success-shaped incomplete backup or silently reseeded data. | A core: B-BACKUP/E-BACKUP; large real-catalog transfer capacity M |
| SYS-018 | P0 | Verify/restore valid ZIP and variants with altered/missing files, duplicate/traversal/linked entries, unsupported versions/compression, size limits and an existing destination. Simulate space/commit failure. | Only allowed files extracted; hashes, schema and complete references checked; existing data never merged/overwritten; new result published only after validation; failure explicit, staging cleaned. | A: B-BACKUP; use isolated destinations only |
| SYS-019 | P0 | Reorder products/accessories with correct/absent/invalid auth; duplicate, missing, extra, noninteger and stale IDs; concurrent metadata edit; corrupt/missing source and write failure. Query admin/public markets and download backup afterward. | Full ordered permutation saves atomically under shared lock; no record/metadata loss or reseeding. Stale order/item set is 409, invalid permutation 422, I/O failure explicit. Relative order survives market/draft filtering and backup. | A: B-ORDER/E-ACTIONS; real production rollout not inferred |
| SYS-020 | P0 | Save optional msrps CAD/USD on both types; omit/partial/clear/zero/equal/below/higher values; reject negative/nonfinite/extra precision/unknown currencies/null map and overflow. Query public/admin/detail/selection, backup/restore, cart and quote. | No conversion/copying; missing old values remain null; public selected msrp only. Price still gates visibility/arithmetic; provenance/full maps stay private. MSRP survives unrelated saves and byte-preserving backup. | A: B-MSRP/B-BACKUP, pricing/public-catalog/cart units, E-MSRP/E-COMPACT |

Home content extension **SYS-021 (P0)**: use legacy and configured hero fixtures;
update top banner or engineering independently, reject malformed/fewer/more than
four cards, blank required text, unsafe/video URLs and oversized fields without
partial writes. Missing files use defaults; corrupt saved configuration is 503,
not successful default data. Share an upload across catalog/banner/cards and
remove references in different orders; retain it until the last reference is
removed. Verify new/legacy archives with the standalone tool; default engineering
images are materialized only in exports, and missing/external media still fails.
Coverage: B-HOME/B-BACKUP plus E-HOME; isolated data only.

Records extension **SYS-022 (P0)**: seed isolated old and new analytics, inquiries,
sealed/live logs and saved mail configuration. Create a private archive with
consistent SQLite/WAL snapshot, all supported files and an offline verifier.
Download alone must not unlock deletion; reject truncated/wrong saved files,
damaged server ZIPs, unsafe paths, concurrent operations and insufficient disk.
After verification, require exact confirmation/categories and compare full rows/
bytes. Preserve new/changed/current-hour/pending/live records and delivery claims.
Simulate partial filesystem cleanup failure: report explicitly, retain archive
and prevent unsafe retries/deletion. Separately remove a verified server ZIP;
source data stays and future source removal is blocked. Run maintenance years
later with mail disabled: no age-based business/history/backup deletion.
Coverage B-RECORDS/B-AN/B-REPORT/E-RECORDS; actual production log migration,
OS permissions/signals, large-download capacity and off-server DR remain M.

Catalog brand extension **SYS-024 (P1)**: with isolated equipment/accessory fixtures,
create with missing/null/blank/trimmed/200-character brand; update with omitted,
changed and cleared brand; reject non-string and 201-character values without
writing. Reload admin and public list/detail under CAD/USD. Brand is public but
provenance and full price maps stay private; drafts/missing prices stay hidden.
Legacy reads do not rewrite storage or infer brand from names. Selection/cart
responses retain their existing minimal shape (neither category nor brand).
Verify optional brand survives byte-preserving backup/restore alongside all
other fields. Coverage A: B-BRAND, B-BACKUP, U-BRAND. Cleanup: isolated directories.

Migration extension **DATA-001 (P1)**: preview and apply the offline migration to
disposable copies of both catalogs. Match only standalone leading STYL tokens
(case-insensitive; whitespace/colon/dash separator); do not alter STYLish, STYL123
or later occurrences. Verify exact original backups, changed count, unchanged
IDs/slugs/order/prices/media/private/unknown fields, and no writes on second run.
Reject empty resulting names, conflicting brand, malformed records or unavailable
backup destination before catalog writes. Stop writers for actual application;
cross-file interruption requires restoring the original affected files.
Coverage A: B-BRAND for transform/dry-run/apply/backups/failure/idempotency;
production application and interrupted-process recovery remain operational.
Cleanup: isolated test directories; retain private real-migration backups.

### 7.2 Regional pricing and GeoIP

| ID | Priority | Steps / input | Expected result | Coverage |
| --- | --- | --- | --- | --- |
| GEO-001 | P0 | Resolve controlled CA, US, other-country, unknown, private/local, IPv6, and IPv4-mapped addresses. | CA/unknown -> CAD; identified other countries -> USD; nonpublic/invalid addresses do not become guessed countries. Registration country is not visitor location. | A: B-GEO with mocked MMDB |
| GEO-002 | P0 | Supply untrusted country/forwarded headers to the application; verify actual installed reverse proxy overwrites incoming forwarded IP. | Application does not trust user country headers. Only approved loopback proxy forwarding influences client address. | P: B-GEO checks resolver; real Caddy/Uvicorn chain requires OPS-002 |
| GEO-003 | P0 | Unset database; missing/unreadable/corrupt file; remove/replace a loaded file; concurrent lookup during replacement. | Unknown/CAD fallback, concise diagnostics without IP/secret exposure, no stale country result, safe reader refresh. | A: B-GEO; live update procedure remains operational |
| GEO-004 | P0 | For F-EQUIPMENT, request public list/detail/selection under CA, US, other, unknown markets. Inspect cache headers. | Exact configured regional price/currency returned; no cross-country shared-cache leakage; location-dependent responses are private/no-store. | A: B-REG; Canadian browser rendering separately E-MARKET |
| GEO-005 | P0 | View F-MISSING-CA/US/NONE/ZERO under each market, including direct product URL and saved cart. | Missing-market item not exposed; admin warning accurate; no fallback to the other price; zero-price item is not hidden merely for being zero. | A core: B-REG/U-CART/E-MARKET/E-ROUND2; physical/live geography needs OPS-002 |
| GEO-006 | P1 | Change market between visits and revisit a saved cart/quote; inject a failed current-price request. | Current available items repriced without conversion, unavailable items removed with notice, quantities preserved; failure does not pretend stale prices are current. | P: U-CART/E-MARKET cover reconciliation; extend browser network-failure scenario |
| GEO-007 | P0 | With no resolvable country, query market/list/detail/selection and add a dual-price item to cart; include a USD-only item. | Country remains null/unknown while CAD prices are used end to end; missing CAD items stay hidden; USD is not copied/relabeled. Known US/other-country tests still return USD. | A: B-REG `test_unknown_location_uses_cad_without_relabeling_usd_prices`, B-GEO, E-MARKET `GEO-007` |
| GEO-008 | P1 | Inspect the small GeoLite credit on home/accessories at desktop and mobile widths. | Readable 12px footer with MaxMind/GeoNames links, no page overflow, no impact on quote landing. | A: E-MARKET `GEO-008`; E-QUOTE protects quote positioning |
| GEO-009 | P0 | Validate updater type/freshness boundaries, unchanged files, failed copy/replace/download, expired files and config permissions. Execute installed timer/service with approved credentials and compare before/after API results. | Atomic root-owned publication; API read-only access; no secret/provider URL logs; bad downloads preserve current data; >30-day files removed on runs; explicit failures and scheduled refresh. | P: [updater tests](../backend/tests/test_geoip_update.py); installed timer/network/permissions verification M, never inferred from mocks |

Local operational evidence (2026-09-27): a checksum-verified GeoLite2 Country MMDB
was installed outside the repository. Seven real-MMDB application checks with
temporary catalog fixtures covered GEO-001/002/004/005/007, including IPv6,
missing-market detail access and spoofed-header rejection; all 17 B-GEO tests
also passed. This does not replace the mocked automation or certify actual
visitor location, production forwarding, or scheduled updates. At that local
setup checkpoint AWS provisioning had not yet occurred. See
[local setup](geoip-pricing.md#local-windows-setup-verified-on-2026-09-27).

Subsequent production evidence: updater activation and a second successful manual
run were confirmed by the user through Edge SSH; timer enabled, API PID unchanged,
credentials root-only, database API-readable/not-writable and catalog/SMTP
preserved. Independent public requests returned US/USD/located even with forged
Canadian headers; all public catalog responses used USD with no-store/private
market responses. MaxMind/GeoNames footer and currency assertions passed in six
desktop/mobile storefront checks. WebKit still reported the previously recorded
RSC-prefetch warning, so its no-runtime-errors check did not pass. OPS-002 is
partially verified for this network; Canadian/other visitor egress and observation
of a future scheduled update remain unverified.

### 7.3 Analytics: active local aggregate-only coverage

Oracle: the [approved aggregate-only requirements](traffic-analytics-requirements.md).
On 2026-09-28 the owner replaced identified opt-in/session analytics with automatic
unlinked aggregates and a noninterrupting Privacy-page opt-out. AN-001..014 retain
their identities; superseded assertions and provenance are listed below.
Old test outcomes establish the old implementation only, not the replacement.
Frontend unit assertions have been rewritten and revised E2E cases prepared;
backend implementation is complete and final integrated verification remains
pending. **P below means partial/pending
coverage, not Pass**. This documentation change records no new execution counts
or outcomes. The implementation/testing owner records the exact candidate and
verified results separately in project history.

Shared prerequisites: isolated local analytics/business fixtures, collection
enabled with supported `aggregate-only` config, SMTP disabled, and a separate
non-admin customer context. Repeat negative cases with disabled/failed/old-mode
config, saved opt-out/prior decline and exclusions without changing real choices.
Inspect requests, private new aggregate tables and reports, not just visible UI.
Use controlled server clocks for hour/DST/retention boundaries, desktop and phone
Chromium plus phone WebKit. Clean only owned fixture data; do not delete legacy
user analytics or catalog/inquiries to make a test pass.

| ID | Priority | Workflow / assertion | Coverage and remaining portions |
| --- | --- | --- | --- |
| AN-001 | P0 | Open an eligible fresh customer route: start automatically only after enabled aggregate-only config, no acceptance step or session POST. Navigate/anchor/rerender/prefetch/back/forward/reload; defined views/actions and local in-memory suppression, no event/page UUIDs. Confirm a real initial/ordinary 15-second batch increases aggregates without a test-only forced flush. Missing/old-mode config must not start identified tracking. | P: U-AN/B-AN/E-AN revisions; wider real-browser BFCache matrix remains partial |
| AN-002 | P1 | Test 50% identity/price visibility and one continuous second on both sides of boundaries; tall mobile cards, rerenders and config arriving after render. Once per item per rendered page via memory only, not page-view IDs. | P: U-AN thresholds and E-AN item-flow revisions |
| AN-003 | P1 | Exercise equipment/accessory details, real Show more on desktop/mobile, media/cart/quote actions. Normalize accessory paths; measure actual Price visibility, not MSRP alone. No expansion on render/resize/collapse and no false cart success. | P: U-AN/B-AN/E-AN/E-COMPACT; physical behavior remains manual |
| AN-004 | P0 | Hide/blur/idle/resume/close pages around the 60-second idle limit and bounded 15-second increments. Verify identifier-free Web Lock coordination without persisted tab/lease IDs. Store only total active estimate in receipt hour; no raw start/end/sequence/tab identity, median or session duration. Disclose possible multi-tab overcount/lost final increments; do not claim cross-tab union. | P: U-AN/B-AN passed in aggregate release; physical suspension/touch behavior M |
| AN-005 | P0 | Forge browser country/price/item claims; check trusted server resolver, unknown/CAD distinct from CA, and drafts/private fields excluded. Country labels are US/CA/Unknown rather than country/currency pairs; item totals retain currency groups. Assert hour-based country/currency/source/campaign/device/browser page-view axes stay independent, not stored as a combined fingerprint or joined to item attribution. | P: B-AN revisions with B-GEO/B-REG; real MMDB/proxy geography remains OPS-002 |
| AN-006 | P0 | Save synthetic inquiries with analytics disabled/opted out/unavailable and SMTP failing. Business receipt totals remain authoritative and independent; new inquiries ignore legacy analytics input and never save attribution. Old inquiry JSON/analyticsAttribution fields are not rewritten or used to link new reports. No copied form/contact contents; browser quote attempts never substitute for saved receipt. Unavailable business source gives summary null; daily numeric 0 placeholders require an explicit unconfirmed-totals warning, not verified zero-inquiry days. | P: B-AN/E-AN revisions; B-AUTH preserves inquiry save-before-mail semantics |
| AN-007 | P0 | Inspect all storefront routes: no consent banner/modal/panel or technical status footer. Standard Privacy link opens /privacy; Turn off usage measurement / Allow aggregate measurement saves only boolean styl-analytics-exclude. Preserve prior explicit decline as opt-out before removing legacy consent/visitor/session/lease keys. Opt-out and unreadable privacy storage stop collection/clear queues; no reset of exclude/cart/admin state and no identifiers in any mode. No promise of per-person aggregate deletion or claim existing old data was purged. | P: U-AN/E-AN/B-AN passed and live no-panel smoke verified; served-market notice/legal review and legacy-backup deletion obligations M |
| AN-008 | P1 | Test admin route/saved-token tab, internal preference, DNT/GPC and known bots. No eligible behavioral writes; unrecognized source stays coarse/unknown, campaigns allowlisted, no referrer hosts/full URL/query/raw UA. Coverage warnings cannot claim complete traffic or count client-excluded people from server requests. | P: U-AN/B-AN/E-AN revisions; bot recognition never claimed perfect |
| AN-009 | P0 | Test 15-second/20-event/16-KiB bounds, bounded queue/rates, prompt first-page and pagehide best effort, malformed/oversized/identified batches and ambiguous delivery. Event POST success contains only accepted count; unknown/non-public item rejects the whole batch with 422 and no partial writes. No automatic batch replay/retry or durable queue; legacy session POST is 410. Ingestion/store/config failures cannot break commerce or return success-shaped zero reports; malformed report dates/timezones produce an explicit error. | P: U-AN/B-AN/E-AN revisions; real disk/capacity fault drills M |
| AN-010 | P0 | Compare dashboard, CSV and preview on matching effective windows. Dashboard keeps full coverage details. Email shows page views/seven-day baseline, saved inquiries, estimated minutes/hours, cart/quote opens, top-three equipment/country/source lists and a dashboard link; omit screenshot technical boilerplate and empty sections. Partial days have Through HH:00, not whole-day percentage comparisons. Genuine disabled/unavailable/rejected/error conditions remain actionable Attention; N/A never becomes zero. Test safe HTML, ranking, zero baseline, DST, hour cutoff, currency groups and 320px preview. | P: B-AN/B-REPORT/E-AN; production-volume performance M; latest execution evidence in project history |
| AN-011 | P0 | Date/timezone/version/recipient claims survive restart/concurrency; definite mail failures bounded, ambiguous sends held, accepted recipients not repeated. Version 3 concise snapshots cannot reuse older warning-heavy/session-based content. Across versions, accepted recipients still cannot be resent and ambiguous sends remain held. Distinguish mail retries from prohibited ambiguous collection retries. | P: B-REPORT with mocked SMTP; production maintenance timer installed and observed with sending disabled; real delivery/restart verification M |
| AN-012 | P0 | Preview safe concise HTML/plain text with equivalent key metrics and real Attention conditions; remove static privacy/retention/implementation paragraphs, not operational failures. Local/test/staging cannot send mail. Daily 00:15 Pacific covers the previous complete day, including DST and restart/duplicate-delivery tests. Separate approved recipients required, never inherited from inquiries. An authorized real test must reach each intended mailbox. | P: B-REPORT/E-AN; actual mail test Blocked until recipients/configuration/send approval |
| AN-013 | P0 | Unauthorized reports/exports rejected; CSV/HTML escaped. Inspect new persisted tables, CSV and snapshots for absence of browser/session/event/page IDs, raw request times/IP/full URL/query/referrer hosts/form/token data and raw-event/journey rows. Safe item IDs and operational job IDs must not be mistaken for browsing identifiers. | P: B-AN/B-REPORT/U-AN/E-AN revisions; infrastructure logs/business contact records require separate privacy review |
| AN-014 | P1 | Desktop/mobile, unavailable storage/privacy failure and slow/offline behavior preserve commerce. Verify consistent SQLite backups and no age-based deletion, including legacy and report history with mail disabled. New-mode reports exclude legacy fixtures; explicit privacy withdrawal remains. SYS-022 covers verified optional source cleanup. Approved privacy deletions must apply to restored/downloaded copies separately. | P: U-AN/B-AN/B-REPORT/B-RECORDS/E-AN; physical devices, performance budget/field measurements and production retention/restore M |
| AN-017 | P0 | Open Daily email settings as admin; change on/off and recipients, save/reload/reopen store, change environment defaults, preview and run mocked scheduler/retry. Reject invalid/empty-enabled/oversized lists and stale revisions; dedupe case; test concurrent saves, storage outage, pending UI, unsaved tab changes and 320px. Recheck changes before delivery claims; no real non-production mail, no SMTP/inquiry config changes, no recipient values in public config. SQLite backup retains settings. | A core: B-AN/B-REPORT and `email-settings.spec.ts` across configured browsers; real approved recipient inbox delivery remains OPS-006 |

#### Requirement provenance and superseded assertions

| Current requirement / stable source | Affected cases | Historical expectation replaced |
| --- | --- | --- |
| Owner's 2026-09-28 aggregate-only approval; TA-002/007/008 | AN-001/007/008/009/013 | Explicit acceptance gate, optional remembered-browser/session IDs, consent/status footer and session POST compatibility |
| TA-001/002/003/005/006 | AN-002/003/004/005/010/013 | Event/page UUID deduplication, raw timestamps/journeys, cross-tab session interval union, visitors/median/session funnels and combined attribution |
| TA-004 | AN-006/010 | Analytics-linked inquiry reconciliation and attributed/unattributed session conversion; replaced by independent saved-business-record totals |
| TA-009 | AN-001/009 | ID-based automatic collection retries; replaced by bounded in-memory best-effort batches and no ambiguous replay |
| TA-010/011/012 | AN-010/011/012 | Five-minute cutoff and session-based snapshots replaced by completed-hour aggregate reports; delivery moved to 00:15 Pacific for yesterday, retaining production-only mail guards |
| TA-007/013 | AN-007/013/014 | Raw-history withdrawal as new-mode deletion UX; replaced by opt-out without false individual deletion promises, legacy isolation/non-destructive transition and enforced existing retention |

Endpoint compatibility detail for AN-007/009/013: legacy session **POST** is 410;
legacy session **DELETE** exists only for historical withdrawal. It neither
creates new identifiers nor deletes person-linked contributions from anonymous
aggregates. Config uses the existing enable switch and fixed aggregate-only mode,
not a new environment mode flag. AN-010/014 must also check the legacy-existence
warning without reading legacy rollups or timestamps into new reports;
trackingSince/lastEventAt are separate new-mode hour-rounded metadata.

AN-015 (City/postal, TA-014, Phase 2 / P2) and AN-016 (AI/support aggregate
integration) remain future-only, not activated by this policy change. Historical
“five sessions per locality bucket” needs new review without sessions. Raw session
drill-down is excluded, not an automatically permitted future feature.

### 7.4 Media processing

| ID | Priority | Steps / input | Expected result | Coverage |
| --- | --- | --- | --- | --- |
| MED-001 | P1 | Upload supported image MIME types and video containers; unsupported image type/video extension; malformed/empty video. | Supported content accepted; invalid input rejected with clear error; no empty successful video asset. | P: B-MEDIA/E-CATALOG; supported-image content-decoding validation is not fully certified by MIME-only tests |
| MED-002 | P0 | Image at 8 MiB and one byte above; video above 50 MiB; converted output at rejection threshold; 12 versus 13 gallery items. | Boundaries enforced server-side and in UI; rejected file/count does not partially save a catalog update. Source byte limits and converted-output limit are tested as distinct rules. | P: B-CAT/B-MEDIA/E-CATALOG; some video size tests use reduced mocked limits, real-size UI check covers >50 MiB |
| MED-003 | P1 | Upload controlled video with visible progression/audio; HEVC/10-bit fixture; decode returned MP4/poster. | H.264-compatible output and valid poster; full intended duration/audio preserved within documented conversion behavior; original discarded per policy. | P: B-MEDIA/E-CATALOG cover conversion/decode; visual/audio fidelity on real devices in USR-003/OPS-003 |
| MED-004 | P0 | Request full MP4, explicit range, suffix range, open-ended range, invalid/out-of-bounds range. Seek in browser. | Correct 200/206/416 behavior, Content-Range/length, and functional seeking; no truncated successful playback. | A locally: B-MEDIA/E-CATALOG; installed proxy check in OPS-003 |
| MED-005 | P1 | Force decode failure, conversion timeout, or an unavailable processor; retry a valid file. | Error is explicit; no incomplete published media; temporary state/lock released for subsequent upload. | A core: B-MEDIA; busy-conversion rejection and storage-unavailable branches should be extended |
| MED-006 | P1 | First batch partially fails; retry failed files; reselect already uploaded successful files. | Successful media retained; only failed files retried; no duplicate successful uploads. | A: E-CATALOG |
| MED-007 | P1 | Batch 1 fails, a different Batch 2 succeeds, inspect statuses, expand earlier history, then retry/dismiss old failures. | Current success clearly labeled; old failures are not current red alerts; unresolved old files remain discoverable and retryable. | P: E-MARKET covers separation/expansion; complete old-history retry/dismiss interactions manually or extend automation |
| MED-008 | P1 | Video first, photo second; reorder; select photo as thumbnail/show first; save/reload; test video-only and legacy image-only records. | Editor accurately explains thumbnail versus first gallery item; order is predictable and preserved; poster fallback works; no duplicate authoritative cover state. | A: B-MEDIA/B-AUTH/U-CART/E-CATALOG |

## 8. Admin end-user test catalog

| ID | Priority | Workflow | Expected user experience | Coverage |
| --- | --- | --- | --- | --- |
| ADM-001 | P0 | Sign in, wrong token, session reload, sign out. Test desktop and phone. | Clear error on rejection; correct catalog on success; sign out removes access state; no token shown in content. | A core: E-CATALOG; expired/session-failure paths need continued coverage |
| ADM-002 | P0 | Create Product and Accessory; inspect default Draft; enter separate country prices; save/reopen; publish/unpublish. | Status/price fields are independent; no unexpected publication; warnings identify missing market; saved state survives reload. | A: E-ROUND2 |
| ADM-003 | P0 | Edit item A, attempt item/tab/New/back/sign-out navigation; cancel then confirm discard; force save failure and retry. | Cancel retains item/edits; confirmed discard is deliberate; failure retains input; success reflects actual saved item. No late load response resets selection. | P: E-CATALOG covers tab discard and failed-save retry; item/New/back/sign-out and rapid navigation need manual expansion |
| ADM-004 | P0 | Perform exact Captured date sequence in section 10 on both forms and supported browsers. | Date remains intact before save and after reload; internal notes independent and private. | A core: E-ROUND2; physical segmented typing/calendar behavior M |
| ADM-005 | P1 | Choose categories, inspect Benches alias cleanup, enter optional equipment weight and all accessory content fields. | Shared controlled list; no lost legacy category; optional blanks allowed; separate public/internal fields understandable. | A core: E-CATALOG/E-ROUND2 |
| ADM-006 | P1 | Upload several images/video while trying to change tabs/save; observe processing and partial errors. | Busy state prevents conflicting actions; filenames/current batch are understandable; valid successes survive partial failure. | P: E-CATALOG; real large upload/slow-network operator experience M |
| ADM-007 | P0 | On phone, repeatedly fill Media URL then tap Add through 12 items; focus/blur inputs around the Save bar and virtual keyboard. | Add does not miss taps because layout moved on blur; Save does not cover fields; max count enforced. | A emulated repeated-click regression: E-CATALOG; physical keyboard/safe-area behavior M |
| ADM-008 | P1 | Open Home banner, edit text, upload an image, save, reopen, and inspect desktop/phone preview. | Independent editor restored; no product selector or price control; original text/image preserved; preview contains no automatic price. | A: E-CATALOG; long-text overflow/manual error recovery P |
| ADM-009 | P1 | Trigger invalid names/prices/MSRPs/dates/package counts and server errors; sample scroll positions after an error receives focus, then retry by pointer/keyboard. | Error is reachable and focused with settled instant scrolling, not an animation moving the next control; values remain editable, invalid save never succeeds. | P: B-CAT/B-REG/E-CATALOG/E-MSRP/email-settings frame check; physical keyboard/screen-reader behavior M |
| ADM-010 | P0 | On desktop/mobile, sign in and open Backup from an unsaved editor. Download, attempt repeated clicks, simulate expired access/generation/transfer errors and retry. Return to editor. | Saved data only explained; private unencrypted ZIP warning; no silent save/discard; pending feedback, no duplicate active requests, correct filename, explicit failure and retry. Browser upload remains unavailable. | A: E-BACKUP across desktop/phone Chromium and phone WebKit; physical-device file-save behavior M |
| ADM-011 | P1 | In Equipment and Accessories, assert shared toolbar DOM order Catalog → Arrange/Done → New with 48px controls; cover empty catalogs, pending moves, 503/409 and 320px. Move actual image/price cards up/down, then Done/reload/public view while retaining unsaved fields. | Arrange button is between heading and New; one listing only, no position dropdown. Arrows appear only in arrange mode; saved move updates card position and retains focus. Boundaries/pending/empty states disable inappropriate actions. Done restores normal selection; Featured does not override order. | A: B-ORDER/E-ACTIONS/U-CART; physical-device touch/screen-reader verification M |
| ADM-012 | P1 | In both editors enter CAD/USD selling price and optional MSRP on the same row per country; save/reload/clear one, edit only MSRP then switch tabs/reset/delete, reject precision errors and inject failures. Measure paired labels/input rows at 320/390/1440px. | Optional MSRP does not warn as missing price; stable labels/IDs, independent amounts and dirty/error guards remain. No horizontal overflow or currency conversion. | A: B-MSRP/E-MSRP/pricing units; physical file picker M |

**ADM-013 (P1), Engineering editor:** Home banner → Engineering details. Edit the
heading/introduction and all four titles/descriptions, upload a replacement,
save/reload and inspect public output. Exercise partial image URLs, invalid MIME/
8 MiB boundary, 503/retry, pending-save duplicate prevention, tab guards and Backup
return. Expected: previews/values retained, no publish before save, current banner
preserved, no 320px overflow; E-HOME and hero unit coverage.
Photo-button coverage: banner and all four cards expose a visible >=48px
**Choose photo** control. Pointer and keyboard open the actual native file picker;
cancellation preserves the image, successful selection updates the draft path
without publishing, invalid files remain blocked, and save/upload busy states
disable overlapping choices. E-HOME covers desktop/phone Chromium and WebKit.

**ADM-014 (P0), Backup & Records:** open the protected section from a dirty editor
without silently discarding edits. Review coverage/disk warnings, create a backup,
download, select the saved file and verify it; failure retains retry controls.
Removal requires selected categories, verification and the exact displayed
confirmation; downloading alone never deletes records. Server ZIP deletion is
separate and warns about sole reliance on downloaded copies. Pending work blocks
overlapping navigation/signout/actions. Verify accessible controls, error feedback,
keyboard use and no horizontal overflow at 320/390px. B-RECORDS/E-RECORDS;
physical file-save dialogs and production data cleanup are not test actions.

## 9. Customer end-user test catalog

Brand editor extension **ADM-015 (P1)**: on both editors open an unbranded fixture,
enter/edit Brand, save/reload, clear/reload, cancel navigation with unsaved changes,
and inject a failed save before retry. Blank is allowed, max length is 200, failed
edits remain visible and saved data stays unchanged. Coverage A: E-BRAND/B-BRAND;
desktop Chromium and phone Chromium/WebKit. Cleanup: delete isolated fixtures.

Brand presentation extension **USR-020 (P1)**: browse both catalogs and each detail
route with STYL, a 200-character unbroken brand, and no brand. Brand precedes
category with a measured 12px gap and no dot, above the name; both wrap within
viewport without changing heading/link identity. After clearing, show category
alone without any brand gap/placeholder. Verify names, IDs,
slugs, market visibility and prices remain independent. Coverage A: E-BRAND,
U-BRAND/B-BRAND across configured desktop/phone projects; physical devices and
screen-reader pronunciation not certified. Cleanup: isolated fixture deletion.

Main release boundary **SYS-023 (P0):** [test_non_ai_release.py](../backend/tests/test_non_ai_release.py)
requires records routes but no support/knowledge/AI modules or customer-chat routes.
This main-only gate is not copied into the AI feature branch. Website logging
installation tests are in [deploy/tests/](../deploy/tests/); Windows runs do not
certify Linux process-group/systemd/Caddy integration. Historical journal export
and verified off-instance Records ZIP must precede 14-day journal retention.

| ID | Priority | Workflow | Expected user experience | Coverage |
| --- | --- | --- | --- | --- |
| USR-001 | P0 | Arrive at home, browse products, open a product, visit Accessories, return to collection. | Navigation destinations are correct; no product-browsing CTA unexpectedly leads to contact; eligible content loads, errors/empty states are distinct. | P: E-CATALOG covers main flows and retry; back-position recovery and every CTA M |
| USR-002 | P0 | Browse each market and missing-price fixture; inspect cards/detail/cart and price decimals. | Correct currency and configured amount; unavailable items absent; no cross-market substitution. | P: B-REG + E-MARKET; actual Canadian/US/other visitors in OPS-002 |
| USR-003 | P1 | Browse multiple images/video, use thumbnails/swipe/arrows, enlarge/zoom, Escape/close, retry broken media, seek/play/pause. On equipment details test 7 and 12 images at 320/390/768/1440px; select last thumbnail and enlarge/close. | Gallery/grid stays inside viewport; thumbnails scroll within their strip rather than widening the page. Controls usable on mouse/keyboard/touch; no unwanted autoplay or hidden background audio; focus returns; vertical page scroll remains usable. | P: E-CATALOG/E-LAYOUT core navigation/zoom/seek/error and multi-thumbnail widths; physical gestures, audio, orientation and focus matrix M |
| USR-004 | P1 | Inspect short/long details, blank specs, Pair/2 and compatibility before/after Show more on every width. | Compact default hides body/contents; deliberate expansion reveals complete details and quantity controls on desktop/mobile. Blank rows omitted and units unambiguous; full pages preserve compatibility. | A core: E-CATALOG/E-LAYOUT/E-COMPACT; screen readers M |
| USR-005 | P0 | Add a pair, change quantity 1 -> 2 -> 10, reload, remove, clear/cancel, and return to shopping. | Two pairs cost two unit prices, count persists, max 10 enforced, explicit removal/clear behavior, useful empty state. | A: U-CART/E-CATALOG |
| USR-006 | P0 | Request quote from cart/product; enter contact data; fail a submission, retry, and submit successfully. | Selection context accurate, prices/units current where included, input retained on failure, pending action not repeatedly clickable, cart not cleared, no payment/delivery claim. | A core: B-AUTH/E-CATALOG; no claim of server-side exactly-once submission |
| USR-007 | P1 | Inspect the homepage principle at 320, 390 and 1440px. | Exact statement appears once above the short All products / Equipment / Accessories actions; no Shop prefix, no overflow, >=48px controls and one action row at 390px. Mobile collection remains reachable within the defined scroll target. | A: E-CATALOG/E-QUOTE |
| USR-008 | P1 | Inspect banner at 767/768px and catalog header choices at 1023/1024px. | Banner hidden below 768 and shown above without price; obsolete Browse accessories shortcut removed in favor of all three header/home choices. | A: E-CATALOG/E-COMPACT |
| USR-009 | P1 | Compare 320/390/768/1024/1440 layouts, large text, desktop keyboard, phone landscape and virtual keyboard. | No page overflow or covered controls; desktop grids/split panes retained; input labels remain visible; touch targets practical. | P: E-CATALOG checks widths/navigation; real keyboard/zoom/device matrix M |
| USR-010 | P1 | Use keyboard-only, VoiceOver/TalkBack, reduced motion, and 200% text resizing. | Logical headings/focus, announced errors/results, accessible dialogs, no focus obscured by sticky areas; information not conveyed only by colour. | M, with limited existing role/focus assertions |
| USR-011 | P1 | At 320/390/767/768/1023px use All products/Equipment/Accessories links without Menu; test 1024/1440px, three home catalog links and quote actions. | All products precedes Equipment, correct default/filter destinations and no overflow. Existing #products, /accessories and /products URLs stay compatible; user catalog data untouched. | A: E-MARKET/E-QUOTE/E-COMPACT; physical touch M |
| USR-012 | P1 | Open quote from cart, product detail, direct URL, and repeated same-page links on desktop/mobile. Delay catalog/banner/cart data, fail catalog/banner, and separately start typing or scrolling while data is pending. | After initial layout settles, the form starts 8-32 px below the sticky header and Name is visible; prefilled message remains correct. Enough trailing space exists on tall desktops. Automatic alignment stops after user input/scrolling and does not repeat on later price refresh. Ordinary visits do not jump. | A: E-QUOTE on desktop/phone Chromium and phone WebKit; mobile scroll-intent cancellation uses synthetic touch events, not physical-device certification |
| USR-013 | P1 | Request a quote with multiple items, old prices, Each/Pair/Set or unspecified units; separately test empty and product-only requests. Edit the multiline message, fail submission, retry and read saved inquiry JSON. | Numbered item blocks; separate quantity, contents and current unit price; independent currency labels/two decimals; blank-line-separated final request; no invented product-only values; errors preserve edits and saved JSON retains exact line breaks. | A: U-CART/E-LAYOUT; synthetic market data, real isolated inquiry persistence, SMTP disabled; live mailbox rendering M |
| USR-014 | P1 | Compare short/long/empty details, category/name lengths, media counts and compatibility at 320/390/767/768/1023/1024/1280/1440px. Expand/collapse by pointer/Enter/Space; resize and enlarge text to 200%. | Every card starts compact with body hidden, not capped. Decorative dots, italic underlined label, subtle outline/background and >=48px Show more on all widths. Expansion reveals all, Show less hides it, resize preserves choice. Shared rows align media/names/prices/actions without overlap or page-width expansion. | A: E-LAYOUT/E-COMPACT on desktop/phone Chromium and WebKit; real devices/screen readers M |
| USR-015 | P1 | Navigate to quote from cart, product and shared header on desktop/mobile, with normal and reduced motion. Sample animation frames while independently releasing cart and catalog responses. | Every sampled form/header gap stays 8-32 px, not just the final frame; no initial router jump followed by visible correction. Prefill preserved; USR-012 interruption and later-refresh protections remain. | A: E-QUOTE, 18 combinations on desktop/phone Chromium and phone WebKit; physical-device visual verification M |
| USR-016 | P1 | Add from product/accessory cards, product detail and mobile sticky action. Inspect immediate button feedback, advance 2.5s, repeat through ten-unit cap, and fail browser cart storage. Include a long unbroken item name in feedback/cart. | Successful write immediately shows check/Added then restores action label; count updates and accessible notice remains. Failed storage/no added quantity cannot show Added. Quantity cap and location remain intact; long feedback/cart content stays within the configured viewport, without mobile auto-widening. | A: E-ACTIONS across desktop/phone Chromium and phone WebKit; physical-device checks M |
| USR-017 | P0 | Open home/default/filtered/unknown-filter URLs, use hero/header links, reload/back/forward; compare exact combined ordering and both card kinds. Fail one catalog source. | All = equipment then accessories in saved orders; no partial failure disguised as complete data. Available specific view works independently. Shared compact format, desktop Details on both, mobile Show more/Add/title navigation; MSRP only strikes when higher and never changes quote totals. | A: E-COMPACT/public-catalog/cart units |
| USR-018 | P1 | Open accessory details from desktop Details/mobile title/direct ID; inspect gallery, MSRP/Price, specs/notes/compatibility, cart/quote and unknown/draft/missing-market items. | Matching complete layout, trusted-market/private-field protection, usable media/no overflow, correct accessory identity; unavailable item gets error/retry rather than phantom price. | A: B-MSRP/E-COMPACT/E-LAYOUT; physical media controls M |

**USR-019 (P1), Engineering presentation:** expand the configurable public section
at 320/390/1440px, compare all four images/titles/descriptions with saved data,
including multiline/blank optional text and failed-image retry. Expected: same
responsive four-card design, safe text escaping, unchanged top-banner hiding and
quote navigation. Coverage: E-HOME/E-QUOTE and readonly local/live checks;
physical-device behavior remains manual.

## 10. Permanent Captured date diagnostic protocol

The user reported the date clearing before Save and, on an accessory, after
Save -> Reload. The issue was **not reproduced in the current automated tests**.
Keep the report and test sequence; do not relabel it Fixed without evidence.

| ID | Priority | Exact procedure | Required evidence / pass condition |
| --- | --- | --- | --- |
| DATE-001 | P0 | On a new Product, enter `2026-09-26`; verify display; focus Internal notes and type; inspect date before clicking Save. Repeat on Accessory. | DOM/input value remains `2026-09-26` after notes, blur, and rerender. Capture failures before any database investigation. |
| DATE-002 | P0 | Save DATE-001; inspect outbound JSON and API response; reload/reopen same record; inspect stored record. | `provenance.capturedDate` equals the exact string at every stage; record ID matches; Internal notes preserved independently. |
| DATE-003 | P0 | Repeat under Toronto and Auckland timezones; use calendar picker and typed date where physically supported; include rapid date/notes changes. | No blanking, timezone conversion, previous/next-day shift, or field overwrite. Current automation covers fill, blur, same-task events and both timezone contexts; physical segmented typing remains manual. |
| DATE-004 | P0 | Verify a published, priced record's public list/detail/selection responses and page content. | No captured date, private notes, or source metadata leaks. API redaction, not merely UI hiding. |

If it fails:

1. Record build/patch, browser/OS/device, timezone/locale, record ID, input method,
   and exact steps.
2. Compare native input value with parent form state after each event.
3. Check onChange/onBlur behavior and whether a sibling edit uses an old snapshot.
4. Check remounts, asynchronous loads, record switching, reset/normalization logic.
5. Inspect serialization, API validation, write result, and reload mapping in order.
6. Reduce to a diagnostic form using the same component/event behavior.
7. Add the failing path to automation before fixing when possible.

Never assume this is a database problem solely because Save/Reload is mentioned.
Also do not replace a missing reproduction with a speculative date conversion.

## 11. Deployment and operational tests

Run destructive/error-injection cases only in an isolated/staging environment.

| ID | Priority | Procedure | Expected / evidence | Coverage |
| --- | --- | --- | --- | --- |
| OPS-001 | P0 | Record deployed commit/config version; validate proxy config; inspect service health; make normal public/API requests. | Correct release actually deployed; no 502/startup/import errors; dependencies/environment align. | M |
| OPS-002 | P0 | With a licensed current country MMDB installed, use controlled CA/US/other egress. Attempt spoofed inbound forwarded/country headers through the real proxy. Test sequential different-country requests through any cache/CDN. | Server-derived market and prices correct; spoof does not choose market; missing-price hiding works; cache does not replay another market's JSON. Record database/provider version without credentials. | M; offline B-GEO/B-REG are supporting evidence only |
| OPS-003 | P1 | Upload an approved short clip through staging proxy; play full duration with audio on real iPhone/Android; seek near start/middle/end. | Proxy permits size/processing duration; 206 seeking works; orientation and appearance acceptable; no hidden duplicate audio. | M |
| OPS-004 | P0 | Save/edit fixture, restart services, deploy code without replacing writable data, and reopen it. | Prices, dates, status, text, media and private provenance survive. Static/upload routes do not expose private data directories. | M |
| OPS-005 | P0 | Back up staging catalog/media (and GeoIP configuration separately as licensed); restore to isolated destination and compare. Exercise documented code rollback. | Known recovery point; consistent references and identity; rollback does not overwrite production catalog inadvertently. | M |
| OPS-006 | P0 | Submit an explicitly approved synthetic inquiry to the configured mailbox; inspect message and Reply-To. | Inquiry saved; notification arrives in inbox/spam as checked; recipient and Reply-To correct; no secrets in logs. API "received" alone is not delivery proof. | M; B-AUTH mocks mail transport |
| OPS-007 | P1 | Block browser storage, fail catalog/current-price requests, interrupt upload, and simulate staging disk-full/permission failure. | Explicit actionable failures, retained drafts/data where promised, no false success or stale-price confidence. | P: unit/browser recovery coverage; staging storage/process faults need more automation |
| OPS-008 | P1 | Inspect CORS and public port exposure from an approved test host; test an unapproved browser origin. | Only intended origins can use browser APIs; API/service ports not public; CORS is not treated as admin authentication. | M |
| OPS-009 | P2 | Record mobile/desktop performance on representative 12-media catalogs and slower networks. | No regression against measured baseline; media loading/layout stable. Targets remain LCP <=2.5s, INP <=200ms, CLS <=0.1 when meaningful field data exists. | M; do not claim field performance from a build result |
| OPS-010 | P0 | Validate root/www DNS, trusted certificate chain/hostname, HTTP-to-HTTPS redirect, www-to-root path/query retention, same-origin API requests, allowed-origin preflight, and any explicitly retained IP access. Inspect backed-up/installed configuration and service health without changing mail DNS. | Domain works without TLS bypass; redirect destinations and API routes are correct; certificate renewal remains managed by Caddy; no catalog/email configuration loss. | M: live targeted evidence recorded 2026-09-27 in project history; future runs must reverify current configuration |
| OPS-011 | P0 | Download a catalog ZIP, remove the original isolated fixture data/media, run the bundled restore tool into a nonexistent directory and start a fresh API on recovered storage. Independently repeat with an authorized production archive in an isolated replacement installation. | No original-server/network dependency for file recovery; JSON/media bytes, IDs/slugs, regional prices, drafts, banner and media paths survive. Application/code/credentials/inquiries handled separately. Keep an off-server archive and document recovery steps. | P: B-BACKUP automates fixture cold recovery, fresh API/images/posters/ranges; real production recovery, full frontend restart and physical video playback M |
| OPS-012 | P0 | Inventory existing production logging and archive retained website history before installing 14-day operational journal limits. Validate separate API/web/Caddy/report capture, permissions, UTC/size rotation, restart/shutdown and disk failure using synthetic staging output. Download/verify an archive and compare recovered data off-server; never delete actual production data as a smoke test. | Website history has no age/size expiry; sealed log files and live prefixes are protected, and no headers/query/customer bodies are deliberately added to access logs. Operational rotation cannot delete uncopied website history. Storage pressure is visible and no forced vacuum/cleanup is performed. | P: isolated capture/record tests; installed Linux services, historical migration, physical downloads, real disk monitoring and off-server DR M |

## 12. Recent bugs/enhancements and permanent traceability

| Change or report | Permanent cases | Notes |
| --- | --- | --- |
| Multiple images/videos on homepage product cards | MED-003/004/008, USR-003 | Retain legacy image-only support |
| Clear admin save errors and failure retention | SYS-009, ADM-003/009 | A successful-looking notice must reflect the API result |
| Accessory descriptions/features/finish/package fields | SYS-008, ADM-005, USR-004/005 | Do not collapse them back into Notes/use |
| Private source tracking | SYS-010/011, DATE-004 | Check public JSON, including future nested fields |
| Exact-cent input and display | SYS-003/004, USR-002/005 | No silent rounding or accidental conversion |
| Mobile admin list/editor, desktop split layout | ADM-001/003/007, USR-009 | Both device classes are release targets |
| Mobile Save-bar missed Add-media clicks | ADM-007, MED-006 | Repeat field focus/blur + Add; stable layout is essential |
| Inquiry persistence and feedback | SYS-014/015, USR-006, OPS-006 | Receipt and email delivery are different assertions |
| Business principle moved back to introduction | USR-007 | Preserve exact text and prominence |
| Banner hidden on phones | USR-008, ADM-008 | Verify both sides of 768 px |
| Duplicate desktop Browse accessories link hidden | USR-008 | Verify both sides of 1024 px and retained main navigation |
| Independent Canada/US prices and geographic selection | SYS-003/004, GEO-001..006, USR-002/005/006, OPS-002 | Replaces the earlier symbol-only/single-price rules |
| Missing-market item hiding and admin warning | SYS-004/005, GEO-005, ADM-002 | Absence of price differs from zero |
| Captured date allegedly clearing | DATE-001..004 | Reported/not reproduced in current tested paths; no speculative fix claimed |
| New Product Draft default and Accessory parity | SYS-005/006, ADM-002 | Preserve legacy behavior and existing lifecycle |
| Bench/Benches cleanup | SYS-007, ADM-005 | No broad taxonomy redesign |
| Optional equipment weight | SYS-008, ADM-005 | No inferred weights |
| Optional brand separate from product titles | SYS-024, ADM-015, USR-020, DATA-001 | Both catalog types; explicit backed-up leading-STYL migration only, no inference on ordinary reads/saves; preserve IDs, URLs and all unrelated catalog data |
| Current versus earlier upload batches | MED-006/007, ADM-006 | Preserve failed-only retry |
| Restore standalone banner and remove pricing | SYS-013, ADM-008, USR-008 | Product-selector banner expectation is superseded, not current |
| Default unresolved visitor location to CAD | GEO-001/003/005/007 | Supersedes unknown/USD only; identified US/other-country selection remains USD |
| Always-visible mobile Products / Accessories links | USR-001/008/009/011 | Shared header, not a replacement for desktop navigation; anchor offset preserves visible headings |
| Enable domain HTTPS and canonical www redirect | OPS-001/008/010 | Preserve path/query and existing service access; DNS/mail records and application data must not be overwritten |
| Configurable multiple inquiry recipients | SYS-014/016, USR-006, OPS-006 | Sending mailbox and recipient list are separate; confirm each inbox independently |
| Admin catalog download and offline crash recovery | SYS-017/018, ADM-010, OPS-011 | Self-contained private archive; only saved data and referenced media, no secrets/inquiries; included standalone recovery tool; browser upload/import deferred |
| Immediate cart feedback and explicit listing sequence | SYS-019, ADM-011, USR-016 | User approved exact manual order instead of Featured-first; only real successful additions show Added, including mobile sticky controls |
| Quote link landing after async content and at page end | USR-006/009/012/015 | Stabilize initial layout commits before paint below measured header, avoid competing router scroll, preserve form context, then stop after data settles or user interaction |
| Readable multiline quote requests | USR-006/013, SYS-014 | Preserve sale-unit semantics, current prices, user edits and exact saved line breaks; do not submit real emails during UI validation |
| Aligned cards with visible detail previews | USR-003/004/009/014 | User clarified that only overflow should be hidden, replacing closed accordions; shared product/accessory presentation, explicit fit cue, and full content retained; detail routes/media/cart behavior preserved |

Historical commit context: `334d320`, `c412178`, `1f5f58c`, `f142fb6`,
`aa2861a`, and the pending Round 2 changes. Use the actual tested revision in each
run report; these milestones are not substitutes for it.

## 13. Commands and repeatable execution

Run from the repository root in PowerShell unless stated otherwise.

### 13.1 Prerequisites

- Use the repository's supported Node/Python environments and installed manifests.
- Backend dependencies must include the local GeoIP reader and FFmpeg provider.
- E2E uses the repository-root `.venv` by default, or `STYL_TEST_PYTHON`.
- Install the configured browsers when missing:

```powershell
Push-Location frontend
npx playwright install chromium webkit
Pop-Location
```

Do not install arbitrary packages to work around a failing assertion.

### 13.2 Capture the candidate

```powershell
git rev-parse HEAD
git status --short
git diff --stat
git diff --check
```

For a dirty candidate, record a reviewed patch identifier/hash and include
untracked source/tests relevant to that build. A commit SHA alone does not identify
uncommitted code. Protect patch artifacts from accidentally including secrets.

### 13.3 Full local code regression

Run each command, record its exit status, and stop/triage a failure before claiming
a full pass:

```powershell
Push-Location backend
..\.venv\Scripts\python.exe -m unittest discover -s tests
Pop-Location

npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run test:e2e
```

The E2E runner already builds the production frontend and performs the Next.js
TypeScript build check before starting it. For a build-only check:

```powershell
npm --prefix frontend run build
```

Type/lint/build are necessary checks, not replacements for API/browser tests.

### 13.4 Targeted examples

```powershell
Push-Location frontend
npm run test:e2e -- --grep "captured date survives"
npm run test:e2e -- --grep "home banner|business principle|responsive navigation"
npm run test:e2e -- --project=phone-webkit --grep "captured date survives"
Pop-Location
```

Run selectors together when they cover the same change; avoid repeated full builds
for unrelated one-off assertions. After a broad shared change, still run the
complete configured suite before release.

### 13.5 Failure handling

- Read the assertion, response, error context, screenshot, and trace.
- Identify whether the cause is product behavior, a fixture, a selector, a timing
  assumption, or environment/startup.
- Wait for actual application states/navigation, not fixed sleeps; do not force
  clicks past disabled controls to make an end-user test pass.
- Do not globally relax assertions or enable retries to conceal a regression.
- If a test was wrong, explain and fix it, then rerun affected and downstream cases.
- Windows/OneDrive generated-build-file locks are environment failures until
  diagnosed. Inspect exact files/processes; do not erase source or kill unrelated
  processes.
- Preserve failure artifacts privately. Record the successful rerun after the fix;
  do not erase the history of the failure from the report.

## 14. Sign-off gates and run ledger

### 14.1 Code handoff / push gate

- Tested candidate is identifiable and unchanged since validation.
- Applicable P0 system/user cases pass.
- Backend, frontend unit, lint/type/build, and full configured browser suite pass
  for a broad functional release.
- New bugs/enhancements have cases and the coverage map is updated.
- Warnings, manual gaps, and environmental limitations are explicitly documented.
- No test credentials, database files, customer data, traces, or unapproved local
  catalog files are staged.
- A targeted pass is reported as targeted, not a full regression.

### 14.2 Production release gate

In addition to the code gate:

- Applicable operational and physical-device P0/P1 checks pass or have an explicit
  accountable exception; blocked GeoIP/mail/device checks are not silently waived.
- Deployment configuration, backups, rollback, and country database are ready.
- Missing market prices have been reviewed by the catalog owner.
- The tested release matches the deployed commit/config.
- Post-deploy smoke results are recorded separately.

### 14.3 Result vocabulary

Use **Pass / Fail / Blocked / Not run / Not applicable** per case and environment.

- Blocked includes missing database, credentials, browser binary, inaccessible
  staging service, or required physical device.
- Not applicable requires a reason; it is not a convenient replacement for Not run.
- Flaky is an issue classification, not a passing result.
- A report being Not reproduced describes a bug investigation; the regression
  case itself still has a recorded pass/fail result for the tested path.

### Run record template

```text
Run ID:
Date/time and tester:
Purpose: targeted / full code / staging release / post-deploy
Commit:
Working-tree patch identifier (if any):
Build/deployed revision:
Config and GeoIP database version (no credentials):
Node/Python/browser/OS/device versions:
Viewports, timezone, locale:
Fixtures and injected failures:
Commands and exit statuses:
Case IDs run:
Pass / Fail / Blocked / Not run / Not applicable counts:
Failures and linked issues:
Fix/retest evidence:
Warnings and accepted exceptions (owner/reason):
Private artifact location:
Cleanup result:
Decision: code-ready / staging-approved / deployed-smoke-pass / blocked
```

Append a concise entry to [project history](project-history.md), referencing the
run record and commit. Keep detailed artifacts outside committed docs when they
contain form data, tokens, or private evidence.

### Evidence available when this plan was written

Latest full automated run: **R2-PUSH-2026-09-26**, recorded in
[project history](project-history.md#pre-push-regression---r2-push-2026-09-26).
The final price-free-banner candidate passed 59 backend tests, seven frontend
unit tests, all 40 configured E2E executions, lint (five warnings, no errors),
and production build/TypeScript checks. That entry identifies the tested source
trees and accounts for manual/operational portions as blocked or not run.

Earlier evidence, retained to distinguish what each run actually tested:

- Before the latest banner reversal: 59 backend tests, seven frontend unit tests,
  and 40 configured E2E executions passed for the Round 2 working build.
- After restoring the standalone price-free banner: **four targeted backend
  tests and six targeted browser executions passed**, along with the production
  build and targeted lint (warnings only).
- A full-suite pass was not performed as part of initially writing this document.
  The earlier 40-test run used the then-current selected-product banner behavior;
  do not describe it as a full certification of the later banner reversal.
- Physical iOS/Android, live GeoIP/proxy, and mailbox delivery were not certified
  by those local runs.

Test counts are historical observations, not permanent target counts. As cases are
added, report the runner's actual count and project matrix.

## 15. Adding tests and managing future scope

### New case template

```text
ID: <area>-<next unused number>
Title:
Requirement / bug / enhancement:
Priority and level:
Preconditions and fixture:
Browser/device/market/timezone:
Steps:
Expected results at UI, API, and persistence layers:
Negative/boundary cases:
Privacy and cleanup requirements:
Automation reference:
Coverage: A / P / M / F
Owner:
Last run ID and outcome:
```

### Change checklist

1. Identify impacted current cases.
2. Add a failing regression case for a reproducible bug before the fix when possible.
3. For an enhancement, test absence/invalid/boundary states as well as success.
4. Update source mapping and, for new automated tests, include the case ID in the
   test title or an adjacent mapping comment.
5. Run the appropriate layers; keep successful API tests from masking broken UI.
6. Update the run ledger and remaining gaps.
7. Retire superseded cases only with the new requirement and replacement case IDs.

### Prioritized coverage improvements

1. Physical-device DATE/keyboard and media checks; capture the original date
   reporter's exact browser/input method if it recurs.
2. Staging real-MMDB/trusted-proxy/cross-country cache checks.
3. Catalog storage-failure and reload/restart integration checks.
4. Complete unsaved-navigation matrix and regional-price request failure in browser.
5. Broader accessibility, real video audio/orientation fidelity, and performance.
6. Additional image-content validation and media processor busy/storage-failure
   tests, distinguishing current behavior from proposed stricter validation.

### Future schema cases: not active gates yet

| ID | Future requirement | Activation condition |
| --- | --- | --- |
| FUT-001 | Catalog-wide unique SKU, concurrent allocation, correction history, no reuse | SKU model implemented |
| FUT-002 | Read-only visible Product ID and stable relationships across reclassification | Unified identity model implemented |
| FUT-003 | Admin-configurable enums, retirement/defaults, reference-safe merges | Reference-data management implemented |
| FUT-004 | Typed attributes, unit constraints, evidence/review invalidation | Attribute/review model implemented |
| FUT-005 | Transactional migration/rollback to the approved storage design | Storage migration approved and implemented |
| FUT-006 | Remaining analytics enhancements: City/postal enrichment AN-015 (Phase 2 / P2), optional unlinked support aggregates AN-016 and separately reviewed operational measures; no raw session drill-down | Active AN-001..014 define the approved aggregate-only replacement, with revised verification pending; City/support still require separate approval/implementation and cannot reintroduce identifiers |
| FUT-007 | Grounded AI support, human queue/takeover, conversation access, desktop/mobile chat UX, provider safety/cost and aggregate support outcomes; see CS-001..020 in the [architecture draft](customer-service-ai-architecture.md) | Provider/scope/privacy/human coverage approved and implemented; no current chat capability or passing evaluation is implied |
| FUT-008 | Browser catalog backup upload/import, preview and live replacement/merge safeguards | User explicitly approves import workflow; current release provides download and offline recovery only |

Do not treat these as skipped current tests or use their absence to claim current
functionality exists. Promote them into active SYS/ADM/USR cases when implemented.
