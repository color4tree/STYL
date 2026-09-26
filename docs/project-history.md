# STYL project history and handoff

Last recorded: 2026-09-26

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
