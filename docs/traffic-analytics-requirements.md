# STYL traffic analytics and daily usage email

Status: **Approved anonymous aggregate-only contract; local implementation and
verification in progress. Not deployed.** Production collection and real daily
email remain disabled. This document defines the current acceptance requirements,
not a claim that the revised tests or production release have passed.

Date: 2026-09-27

Updated: 2026-09-28

The owner approved replacing optional identified-session analytics with automatic,
first-party, aggregate-only measurement. There is **no storefront consent panel,
banner, modal, or technical collection-status footer**. An ordinary **Privacy**
link to `/privacy` explains measurement and provides a measurement opt-out preference.
The goal is uninterrupted shopping, not hiding the notice.

The earlier explicit opt-in, optional 30-day browser identifier, raw session
history, linked inquiry attribution and five-minute email cutoff are
**superseded historical decisions**, not alternative current modes. Their earlier
verification remains historical in [project history](project-history.md).
Existing private legacy data is not thereby deleted or approved for migration.
TA-001..014 and AN-001..016 retain their IDs; City/postal and chat remain deferred.

Related: [Current application](../README.md),
[local use and operations](traffic-analytics-operations.md),
[简体中文](traffic-analytics-requirements.zh-CN.md),
[GeoIP configuration](geoip-pricing.md),
[future AI/human support](customer-service-ai-architecture.md),
[regression plan](regression-test-plan.md).

## 1. Purpose and confirmed request

Help the owner understand when public pages are used, broad country/market and
acquisition patterns, item interest, shopping actions, estimated active time and
coarse usability problems. Report **counts**, not people or individual journeys.
Provide protected admin reports and an aggregate daily email.

This approval covers local implementation and testing, not deployment, real
mail, recipient approval, or a determination that consent is unnecessary in every
jurisdiction. Privacy/legal review for the served markets is a release gate.
City and ZIP/postal-area analysis remains **Phase 2 / P2**.

## 2. Business questions and priorities

| Priority | Question | Measures available in this mode |
| --- | --- | --- |
| P0 | Is measured activity growing? | Page views and event totals by server hour/day; no visitor or session counts |
| P0 | Where does measured traffic broadly come from? | Independent country, currency, source-category, approved campaign, device and browser page-view counts |
| P0 | Which items attract interest? | Per-item impressions, detail opens, expansions, media opens, cart actions and quote actions |
| P0 | Are inquiries being received? | Authoritative server-saved business inquiry totals, independent of analytics |
| P1 | Are usability problems visible? | Total estimated active time, fixed error-category counts, average web vitals and sample counts |
| P1 | Are there empty or unavailable catalog results? | Allowlisted catalog-empty/item-unavailable counts; no customer-level market histories |
| P2 | Which cities/postal areas show demand? | Deferred; separate privacy, data and aggregation design required |
| P2 | Would more media/support measures help? | Separately approved unlinked aggregate additions; no visitor-cohort or journey expansion |

STYL requests quotes, not online payments. A quote is not a sale; cart value is
not revenue. Sales won, profit, advertising ROI and customer lifetime value
require separate business systems and are outside this contract.

## 3. Scope and hard exclusions

The first-party browser collector starts automatically only after successful
configuration confirms collection is enabled **and** the mode is
`aggregate-only`, with no opt-out or applicable exclusion. Missing, incompatible
or unavailable configuration must not fall back to identified tracking.

The server immediately adds accepted values to hour buckets and independent
coarse dimensions in a private analytics store. There is no durable raw-event
staging table, session table, event outbox, navigation history or journey record
for new collection. New-mode reporting never reads legacy session/event history
or legacy rollups, and never repackages them into new aggregate reports.

Do not create, send or retain analytics browser/session identifiers, cookies,
localStorage identifiers, event UUIDs, page-view UUIDs, or request correlation
IDs. Do not persist raw request/occurrence times, raw IPs, full URLs, query strings,
referrer hosts, raw user agents, customer form text/contact data, private catalog
fields, or combined dimension tuples that can act as a fingerprint. No session
replay, keystroke/mouse recording, identity matching, cross-site tracking or
third-party analytics tags.

A non-identifying boolean measurement opt-out and the existing internal-exclusion
choice are preferences, not visitor identifiers. Essential cart and admin state
have separate purposes; this change must not remove or repurpose them.

### Later work

- TA-014 / AN-015: City/postal enrichment, still Phase 2 / P2 and disabled.
- AN-016: optional aggregate support outcomes when separately approved chat exists.
- Weekly/monthly summaries, reviewed media milestones and business-system
  outcomes may be proposed separately without weakening the aggregate-only model.
- Persistent cohorts and raw session drill-down are **not** dormant options in
  this release. Restoring identified tracking would require a new product/privacy
  decision, not toggling an undocumented fallback.

## 4. Measurement definitions

| Measure | Required definition |
| --- | --- |
| Time bucket | Server receipt hour stored as a UTC hour boundary; no raw client/server event timestamp persists |
| Page view | A rendered public route entry, including real SPA navigation; not prefetch, hydration, RSC/API/media requests or rerenders |
| Section navigation | An intentional allowlisted anchor/navigation action, separate from a page view |
| Item impression | At least 50% of the item's identity/price summary visible for one continuous second; local in-memory suppression once per item per rendered page |
| Detail view | Successfully rendered product detail, not a URL request or loading state |
| Expansion | A real desktop Show more action; automatic full details on mobile are not an expansion |
| Cart/quote action | A named action total; a cart write must succeed before its success action is counted |
| Saved inquiry | A successfully persisted business inquiry, counted from business records, never inferred from a browser event |
| Inquiry email accepted | SMTP accepted the notification, not proof of inbox delivery/read status |

Item type plus immutable catalog ID identifies an **item**, not a person or
browsing instance. Public catalog labels may be resolved for reports without
exposing drafts/private fields. Current catalog prices are not revenue.

### Total active-time estimate: TA-001

- Count only while the document is visible and focused, with activity in the
  last 60 seconds; signals contain no typed values. Visible active video may
  qualify, but background playback does not imply attention.
- Use bounded approximately 15-second increments. Pause on hidden/idle pages;
  avoid double-counting a local interval and never infer a long stay from a late
  disconnect. A final pagehide flush is best effort.
- Persist only accumulated duration and counts in the server receipt hour.
  Do not store interval start/end times, sequences or tab identifiers.
- Identifier-free browser Web Lock coordination may reduce overlapping active
  increments; do not replace it with stored tab IDs or lease identifiers.
- Report **total estimated active time**, not median or per-session duration.
  No cross-tab/session union or person-level elapsed-time guarantee is possible
  without linkage. Explain lost final increments, idle-reading undercounts and
  possible multi-tab overcounts. Do not introduce identifiers to correct them.

## 5. Event contract

### Unlinked envelope and dimensions: TA-002

Accept only the versioned, allowlisted event name, canonical route category,
necessary fixed properties, safe item references and bounded numeric increments.
Browser event objects exist only in the bounded in-memory delivery queue.
The server selects environment, hour and trusted country/currency; browser
country, price, timestamps and identity claims are not authoritative.

- Normalize paths to known routes/templates before sending; never send full
  URLs, product-name query text, fragments or unrestricted paths.
- Reduce acquisition to fixed source categories; do not send/store referrer
  hostnames. Retain only explicitly allowlisted campaign codes, not arbitrary
  UTM values or customer information embedded in marketing URLs.
- Use coarse device and browser families, not full UA/viewport/OS combinations.
- Store each breakdown independently: for example `hour + source category`
  page-view count and `hour + device family` page-view count, **not**
  `hour + country + campaign + device + browser + item` histories.
- A dimension breakdown describes its own page-view counts. It cannot be joined
  to item/quote actions to reconstruct attribution, nor summed with other axes
  as if they represented disjoint traffic.
- Country labels are country-only, such as `US`, `CA` and `Unknown`, not
  country/currency combinations. Per-item action totals may retain separate
  currency groups; this does not permit joining them to country, source,
  campaign, device or browser histories.

### Action catalog: TA-003

| Event/category | Required aggregate treatment |
| --- | --- |
| `page_view` | Route/hour total and independent coarse page-view dimensions |
| `navigation_click` | Fixed navigation/anchor action count, not from/to journey rows |
| `item_impression`, `item_detail_open`, `item_details_expand` | Separate per-item counts under the visibility/render/action definitions |
| `media_open` | Deliberate media-open count; safe item/media category, no private URL |
| `cart_add`, `cart_quantity_change`, `cart_remove`, `cart_clear`, `cart_view` | Distinct successful actions/views; no saved-cart or session snapshot |
| `quote_open`, `quote_form_start`, `quote_submit_attempt` | Unlinked action counts; safe item reference only when directly available; no form values or correlation token |
| `quote_error`, `site_error` | Fixed coarse error-category counts, never exception bodies, stacks or request data |
| `catalog_empty`, `item_unavailable` | Genuine empty/unavailable result counts, with only validated public context |
| `engagement` | Bounded duration added to total active estimate, no interval history |
| `web_vital` | Bounded metric sum/sample count yielding an average, no raw samples or median |

These counts are directional, not exactly-once visitor measurements. In-memory
route/impression suppression avoids routine rerender duplicates without UUIDs.
After a reload or uncertain network delivery there is no durable deduplication
identity. Do not promise replay detection that this model cannot provide.

### Independent business inquiry counts: TA-004

Saved inquiries remain authoritative even when analytics is disabled, opted out,
blocked or unavailable, and when notification sending fails. Count the saved
business records independently; do not send/store an analytics identity or
associate their IDs with page/item/source/campaign history.

Do not parse private messages for items or copy contacts into analytics. Existing
plain-text inquiry clients remain valid. Any business-side deduplication uses the
business record under its own access policy, not a browser analytics token.
Report **saved inquiries (business total)** separately from quote action counts.
There are no attributed/unattributed-session totals or session conversion rates.

For compatibility, new inquiry submissions ignore legacy analytics input and
never save or assign attribution; this is separate from rejecting identified
payloads at the analytics collector. Existing authoritative inquiry JSON is not
rewritten: historical `analyticsAttribution` fields may remain until separately
approved cleanup. New reports must not use those old associations.

If the business inquiry source cannot be confirmed, the summary inquiry value
is `null` (unavailable). The existing daily-row response shape keeps a numeric
`0` with an explicit **unconfirmed inquiry totals** warning in that situation;
it is not evidence that no inquiries were saved. Consumers must retain/display
the warning and must not present these daily placeholders as verified zeroes.

## 6. Dashboard and interpretation

### Protected admin view: TA-005

Use the existing authenticated admin surface, with today/yesterday/7/30 days and
custom dates in **America/Los_Angeles** and explicit manual refresh.

- Show page/event totals, independent coarse breakdowns, per-item interest/action
  counts, total active estimate, coarse errors and average web vitals.
- Saved inquiries are a separately labelled business total, not a measured
  visitor funnel. Do not call any event count “visitors”.
- Last measured activity is **hour-granular**, with timezone; report generation
  time is operational metadata, not an exact last-visitor timestamp.
  `coverage.trackingSince` and `coverage.lastEventAt` use separate new-mode,
  hour-rounded metadata, not legacy event timestamps.
- Explain unavailable metrics and partial coverage. A zero-count guide checks
  enabled aggregate-only configuration, exclusions, date range, batching and
  refresh; never instruct the operator/customer to “Accept analytics”.
- Collection/job diagnostics belong in admin, not a storefront technical footer.
  Server-observed excluded requests cannot count people excluded before sending.
- CSV and new saved report snapshots are aggregate-only, authenticated where
  applicable, range-bounded and formula/HTML-safe. No IDs identifying traffic,
  session metrics or legacy report content may leak into them.

### Unavailable metrics and comparisons: TA-006

Unique/new/returning visitors, sessions, individual journeys, landing/exit
attribution, per-session funnels/drop-off/conversion rates, session-linked
campaign/item/inquiry attribution and medians are **not measurable in this mode**.
Do not estimate them from IP, page-view totals or independent dimension counts.

Independent action counts may be displayed side by side, but not as an ordered
cohort funnel. Compare completed-day totals with the prior seven completed days'
daily average, showing counts, coverage and sample sizes. A zero baseline is
“no comparable baseline”, not infinity. Do not infer causes, revenue or lost
sales from these totals. Keep CAD/USD separate whenever business amounts appear.

## 7. Privacy, preferences and retention: TA-007

Use the trusted server-local country resolver transiently; raw IP is not written
to analytics. Unknown country stays unknown even when its pricing fallback is
CAD. Do not make a geographic request to an external service.

The ordinary `/privacy` page must explain purpose, collected aggregate categories,
automatic measurement, retention, opt-out, exclusions, limitations and contact
route. Provide a non-identifying boolean opt-out, without an interrupting consent
panel or storefront on/off/connecting diagnostic status. Do not conceal the notice
or claim all first-party aggregate measurement is legally consent-exempt.

- **Turn off usage measurement** / **Allow aggregate measurement** changes only
  the boolean `styl-analytics-exclude` preference; it does not create an ID or
  consent/session record. This page is not a technical collection-status panel.
- Preserve a previous explicit decline as boolean measurement opt-out before
  removing the legacy `styl-analytics-consent` record. Do not silently override
  that choice when migrating preferences or receiving new configuration.
- Clear retired analytics visitor/session/lease keys and the migrated legacy
  consent key. Do not erase the resulting privacy/exclusion choice, essential
  cart contents or admin credentials.
- Opt-out stops collection and clears queued events; honor DNT/GPC, admin,
  internal and known bot exclusions. If privacy choices cannot safely be read,
  fail closed rather than treating the failure as permission.
- No individual history exists in new aggregates to retrieve or erase by person.
  Opt-out does not promise retroactive removal of a person's aggregate
  contributions. Explain this honestly rather than inventing a deletion receipt.

| Data | Retention and transition rule |
| --- | --- |
| New anonymous hour/dimension aggregates | 13 calendar months; enforce calendar-based expiry, including backups/exports |
| New raw events/identifiers/journeys | Never persist |
| Legacy private session/event data | Not read by new-mode reports; no destructive migration by this change. Existing 30-local-calendar-day raw retention and approved cleanup/deletion obligations still apply |
| Legacy reports/backups | Keep restricted, subject to existing expiry/deletion obligations; never serve as new aggregate-only report content |
| New aggregate email snapshots/delivery metadata | 90 days; operational report/delivery IDs are not browser/event IDs |
| Business inquiries and infrastructure logs | Separate purpose, access and retention policies; not made anonymous by this feature |

Do not claim legacy data has already been deleted. Verify its maintenance path or
approve a bounded cleanup before release; disabling legacy reporting must not
silently retain old personal/pseudonymous records forever. Backups must honor
expiry and previously approved deletions when restored.

Analytics maintenance expires legacy raw/session tables after their existing
30-day window and legacy rollups after 13 calendar months. It does not rewrite
authoritative inquiry JSON or protected backup copies. Any historical inquiry
`analyticsAttribution` fields and backup contents remain private and subject to
their separate approved retention/cleanup process, not an implicit purge here.

Caddy/Uvicorn/infrastructure access logs and business inquiry/contact records
may contain personal data. The aggregate-only claim is limited to new analytics
collection, not the whole website or every file in a legacy database/backup.

## 8. Traffic quality and reliable collection

### Exclusions and trust: TA-008

Separate local/test/staging/production data. Exclude admin routes/tabs with saved
admin credentials, explicit internal browsing, DNT/GPC, known bots, monitoring and
automation. Do not disable real customers' privacy choices for a test. Classification
is imperfect; totals are best-effort measured actions, not all traffic.

Validate item visibility and coarse fields server-side. Reject identified legacy
payloads, unknown fields and unsafe metadata without logging bodies. The old
`POST /api/analytics/session` endpoint returns **410 Gone**, not an identity or a
compatibility session. There is no fallback to identified collection.

`POST /api/analytics/events` returns only `{accepted: number}` on success, with
no event IDs or timestamps. An unknown/non-public item reference rejects the
entire batch with **422**; no partial aggregate increments are committed.

Legacy `DELETE /api/analytics/session` remains solely for historical withdrawal.
It does not create/resume identified collection or provide per-person deletion
of new anonymous aggregates. Its presence is not a claim that old data was purged.

### Delivery and failure isolation: TA-009

- Same-origin first-party asynchronous ingestion; bounded schemas, origins,
  rates, increments and queue age. Maximum **20 events / 16 KiB** per batch,
  normally flushed every **15 seconds**.
- The initial page can flush promptly to measure short visits; pagehide/beacon
  is best effort. In-flight events and local deduplication state are in memory
  only, not durable browser storage or a server raw-event queue.
- **No automatic retry of ambiguous collection delivery.** Without event IDs,
  replay can double-count. Prefer dropping a failed/uncertain batch to inventing
  durable identifiers or exactly-once guarantees.
- Receipt hour, not client clock, determines aggregation; delayed delivery may
  land in a later hour/day. Do not save precise times to backfill its origin.
- Analytics outage, validation failure or storage failure must not interrupt
  navigation, media, cart, or inquiry receipt. Surface sanitized operator errors,
  not a false customer-facing commerce failure or success-shaped zero report.

## 9. Daily summary email

### Schedule and destination: TA-010

The approved schedule remains **08:00 America/Los_Angeles**, for the preceding
local calendar day, using IANA timezone rules for DST. A persistent server job
must work independently of VS Code/chat. Sending remains disabled outside
production and requires explicit production enablement and separately approved
internal analytics recipients. **Recipients are not yet approved.**

Reuse protected SMTP transport without inheriting inquiry recipients or changing
customer Reply-To. Use only a configured business Reply-To and a credential-free
authenticated dashboard link. Preview never sends mail.

### Required content: TA-011

Include report date/timezone, completed-hour cutoff, generation time, page/event
counts, total active estimate, independent coarse page-view breakdowns, per-item
action counts, coarse errors, average web vitals/sample counts, separate saved
business inquiries, prior completed-day comparisons, coverage warnings and job
status. Up to three rule-based observations must be supported by counts.

No visitors/sessions, median time, ordered funnels, attributed inquiry rates,
raw identifiers or person-level paths in text, HTML, CSV or new snapshots.
For example, use “Page views: <count>; saved inquiries (independent business
total): <count>”, not “<visitors> converted at <rate>”.

Future support integration supplies only approved unlinked aggregates, not
transcripts, contact data or correlation IDs. It remains optional for basic
support; city/postal sections remain absent until separately approved.

### Windows, snapshots and failures: TA-012

- Use half-open Pacific calendar-day windows converted to UTC; account for
  23/25-hour DST days without merging repeated UTC hour buckets incorrectly.
  Reporting currently supports zones with whole-hour UTC offsets, including
  Pacific DST. Fractional-offset zones must fail explicitly, not round a
  boundary or silently miscount hour buckets.
- Email/preview excludes the **incomplete current hour**. The old five-minute
  cutoff is superseded: hour-only storage cannot prove minute-level completeness.
  State the completed-hour boundary; a current dashboard may include the ongoing
  hour and thus differ from a preview with a narrower effective window.
- Freeze aggregate-only snapshots for recipient retries; do not load a legacy
  session-based snapshot for a new-mode delivery. Generation/run/send timestamps
  are operational metadata, not retained browsing timestamps.
- Version 2 mail reports use the new aggregate-only format. Previously accepted
  or ambiguous deliveries still constrain sending across report versions:
  changing formats must not resend an accepted recipient or bypass an
  ambiguous-send hold, even though legacy snapshot content is not reused.
- Persist date/timezone/report-version/per-recipient delivery state. Prevent
  concurrent duplicate sends and resending already accepted recipients.
- SMTP acceptance is not inbox delivery. Bounded retries apply only to definite
  **mail** failures, not ambiguous analytics batches. Hold uncertain/interrupted
  sends for operator review; do not promise exactly-once email.
- A genuinely zero-activity day may send a short enabled summary; report failure
  must not produce a normal-looking zero report. Expose failures outside the
  failing SMTP channel; no automatic repeated correction emails.

## 10. Operations and deferred locality

### Storage and rollout: TA-013

Use first-party browser actions -> FastAPI validation -> immediate private
hour/dimension increments -> authenticated admin/CSV/email. Keep analytics SQLite
separate from catalog JSON and inquiry persistence; no managed database purchase
or catalog migration is required.

Use transactions, bounded writes/indexes, private paths/permissions, storage
limits and a consistent SQLite backup API (not the main file alone during WAL).
Collection and mail switches are independent. Rollback disables collection/mail;
it must not reactivate identified tracking. Preserve GeoIP no-store responses,
current commerce, and the existing inquiry notification workflow.

Retain the provisional additional-JS budget of 15 KiB compressed and measure
against the storefront baseline; production load, storage, backup/restore, alerts
and field performance remain verification gates, not assumed passes.

### City and ZIP/postal-area enrichment: TA-014 (Phase 2 / P2)

**Deferred and disabled.** The installed Country MMDB is not a City database.
This change does not download, configure, purchase or activate City enrichment.
An additional GeoLite2 City binary database and separate enrichment/updater work
would be needed. Free GeoLite availability is subject to MaxMind account/license
terms; no paid subscription is authorized or required by this proposal.

If separately approved, review independent coarse locality aggregates,
small-group suppression, coverage and precision first. The old proposal of
“five eligible sessions per bucket” is historical and unusable without sessions;
choose a reviewed aggregate threshold, not a claim to count distinct people.
No locality attached to a journey, IP history, coordinates or combined fingerprint.

Preserve leading zeros/partial postal values and unknowns; do not infer missing
postal codes, addresses, delivery eligibility, shipping cost or tax. Broad network
exit locations and accuracy radii do not prove a person's position. Keep Country
pricing unchanged; missing/unreadable City data must not break country reports,
quotes or daily mail. Do not backfill using raw IP histories.

References retained from 2026-09-28:
[GeoLite availability/accuracy](https://dev.maxmind.com/geoip/geolite2-free-geolocation-data/)
and [City fields](https://dev.maxmind.com/geoip/docs/databases/city-and-country/city-binary/).

## 11. Acceptance criteria and regression plan

The [living plan](regression-test-plan.md#73-analytics-active-local-aggregate-only-coverage)
retains AN-001..014 with revised assertions/provenance. Their test sources remain
the existing backend runners, `frontend/tests/analytics.test.mjs` and
`frontend/tests/e2e/analytics.spec.ts`. Revised execution results are recorded
separately by the implementation/testing owner; documentation is not a test pass.

| Case | Required proof |
| --- | --- |
| AN-001 | Automatic enabled aggregate-only startup, defined route/anchor counts, no UUIDs; real ordinary batching/initial flush without a forced test flush |
| AN-002 | Visibility/time threshold boundaries, local rerender suppression, tall mobile cards and config arriving after render |
| AN-003 | Distinct per-item detail/expansion/media/cart/quote counts; no manufactured mobile expansion or session attribution |
| AN-004 | Visible/focused/non-idle bounded total-time increments; no raw intervals, per-session medians or cross-tab identity |
| AN-005 | Trusted country/currency and public-item validation; unknown/CAD not Canada; independent dimensions, no combined fingerprint |
| AN-006 | Saved inquiries remain authoritative independent business totals despite SMTP/analytics failure; no analytics linkage/private text |
| AN-007 | No consent/status panel; Privacy notice/boolean opt-out; preserve prior decline and clear legacy identifiers without resetting privacy choices |
| AN-008 | DNT/GPC/admin/internal/bot exclusions, minimized sources/approved campaigns, honest incomplete coverage |
| AN-009 | 15-second/20-event/16-KiB bounds, prompt initial/pagehide best effort, no ambiguous retries; identified inputs rejected and old session POST returns 410 |
| AN-010 | Totals/labels/manual refresh/Pacific dates/hour last activity; explicit unavailable metrics; completed-hour preview cutoff/DST/no false zero success |
| AN-011 | Restart/concurrency-safe mail state; bounded definite mail retries and held ambiguous sends; no legacy snapshots reused |
| AN-012 | Safe previews and non-production mail disabled; actual mailbox test blocked until approved recipients/configuration |
| AN-013 | Protected reports/CSV and safe rendering; no IDs/raw request times/IP/URL/referrer/form data in new analytics persistence or exports |
| AN-014 | Desktop/phone Chromium/WebKit, blocked storage/privacy failure, outages, 13-month expiry and legacy isolation/non-destructive transition; manual performance/restore gaps explicit |
| AN-015 (Phase 2 only) | Separately approved City/postal quality, suppression and operational checks; remains future |
| AN-016 (future chat only) | Optional unlinked support aggregates; no transcripts/contact/correlation IDs, no substitution of handoff for saved inquiry |

## 12. Approved decisions and outstanding release gates

Approved: aggregate-only automatic collection with opt-out/exclusions, no
storefront consent/status UI, independent hour/coarse dimensions, 13-calendar-month
aggregate retention and 08:00 Pacific daily schedule. No identified-mode fallback.

Outstanding: final local implementation/test evidence, served-market privacy
review and public notice, separate recipients and real-mail authorization,
production deployment/enablement, real proxy/GeoIP and capacity checks, installed
timer/alerts, legacy-retention/approved-cleanup verification and private
backup/restore/expiry checks. No existing legacy private data is claimed deleted.
