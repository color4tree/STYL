# Traffic analytics: local use and operations

Status: **Aggregate-only collection deployed in release `a611b4e`.**
Production collection and the 15-minute maintenance timer are enabled. Actual
daily email remains disabled; recipients and a real-mail test are not approved.
See [project history](project-history.md) for exact release/test evidence and the
concise version-3 email rollout (`dbccf7a`, deployed 2026-09-29).
No mailbox-delivery claim is made.

Scope: automatic first-party country-level aggregate measurement, a protected
admin dashboard, CSV and daily-email preview/job. City/postal, AI chat, CRM/revenue
attribution and individual visitor journeys are outside this release.

Requirements: [English](traffic-analytics-requirements.md) /
[简体中文](traffic-analytics-requirements.zh-CN.md).

## Approved privacy and schedule choices

- Start automatically only after configuration confirms **enabled** and
  **aggregate-only**. There are no browser/session identifiers, analytics cookies,
  localStorage identifiers, event/page-view UUIDs or durable raw-event/journey
  rows. There is no identified-mode fallback.
- Store server receipt **hour** totals and **independent** coarse dimensions,
  not raw request times, IPs, URLs/query strings, referrer hosts, form/contact
  data, raw user agents or a combined country/source/device/item fingerprint.
- The storefront has no consent banner, modal, preferences panel or technical
  collection-status footer. Its ordinary **Privacy** link to `/privacy` explains
  measurement and offers a non-identifying boolean opt-out. This is transparent,
  noninterrupting UX, not an instruction to hide measurement.
- Preserve a prior explicit decline as opt-out; honor DNT/GPC/admin/internal/bot
  exclusions. Clear retired visitor/session/lease keys without clearing privacy
  choices, essential cart data or administrator credentials.
- Report timezone: **America/Los_Angeles**; daily schedule: **08:00**, for the
  preceding local calendar day. IANA timezone rules handle daylight saving.
- Real analytics email is disabled in local/test/staging. Recipients are
  **not yet approved** and must be configured separately from inquiry recipients.
- Privacy review for served jurisdictions is a release gate. Self-hosted
  aggregate measurement is not universally exempt from consent/privacy rules.
  Access logs and saved business inquiries may separately contain personal data.

### Superseded behavior and existing data

The 2026-09-28 opt-in/session implementation, optional 30-day browser remembering,
footer status, linked inquiry attribution, session-history deletion UI and
five-minute email cutoff are historical, not current instructions.
The old zero-traffic diagnosis and test counts remain historical in
[project history](project-history.md); they do not verify this replacement.

New-mode reports must not read old raw session/event history or legacy rollups,
or reuse old session-based email snapshots. The replacement does **not** destructively migrate
existing private data and does not assert it has been deleted. Preserve and
enforce existing retention/approved deletion obligations; see
[retention, deletion and backups](#retention-deletion-and-backups).

## Local verification workflow

Use isolated local data and SMTP-disabled configuration, not the user's real
catalog/inquiry records. The ignored **STYL: local API** task provides a local
analytics environment and Pacific timezone. Its established default private path
is `%LOCALAPPDATA%\STYL\Analytics\analytics.sqlite3`, outside Git and OneDrive;
an explicit `STYL_ANALYTICS_DB` may select a different private store. A database
with legacy records is not automatically a clean anonymous-only file.

1. Start the usual local API/web tasks after the revised implementation is
   integrated. Confirm enabled aggregate-only configuration through admin or
   developer/network inspection, not a storefront technical status panel.
2. Open an isolated customer context and type the storefront address directly.
   Do not copy an admin tab, reset real privacy choices or reuse saved admin
   credentials. A fresh eligible page starts measuring automatically; **no
   “Accept analytics” action is required or offered**.
3. Browse items, open details/media and use the cart. Ordinary batches flush
   within about 15 seconds, with a possible prompt initial-page flush; pagehide
   is best effort. Optional synthetic inquiries must use isolated storage with
   SMTP disabled.
4. In a separate admin context, select **Analytics**, choose **Today** in Pacific
   time and **Refresh analytics**. The view is a snapshot, not a live counter.
   Inspect page/event totals, independent coarse breakdowns, per-item actions,
   total active estimate and the separate saved-inquiry business total.
5. Use **Preview daily email** to inspect safe aggregate text/HTML, without
   sending or marking delivery accepted. Only complete hours are included;
   current-hour traffic may appear in the dashboard but not this preview.
6. Use **Download aggregate CSV** through authenticated admin access.
7. Separately verify `/privacy`: **Turn off usage measurement** /
   **Allow aggregate measurement** saves only the boolean
   `styl-analytics-exclude` preference. Old explicit declines and exclusions
   still stop collection. Check request bodies and new persistence contain
   no browser/session/event/page IDs or raw event times. Confirm legacy
   `POST /api/analytics/session` returns **410 Gone** and identified batches
   are rejected, not silently converted.

Successful `POST /api/analytics/events` returns only `{accepted: number}`.
Unknown/non-public item references reject the whole batch with **422**, with
no partial aggregate writes. A rejected batch cannot be read as a smaller
successful batch or an excuse to retry ambiguous delivery.

The retained key `styl-analytics-exclude` is the boolean measurement opt-out /
internal exclusion choice, not an identity. Migrate an existing
`styl-analytics-consent` explicit decline to that boolean before removing the
old consent record. Clear `styl-analytics-visitor`, `styl-analytics-session`,
`styl-analytics-lease` and the migrated legacy consent key without silently
re-enabling measurement. If privacy storage cannot be read safely, fail closed.
The new Privacy page does not show technical collection/session status.

### Why a local report may show zero

- Collection may be disabled, configuration may be unavailable/incompatible,
  or the API/web processes may still run the old version. Inspect admin/config,
  not an on/off status on the storefront.
- A previous decline, current opt-out, DNT/GPC, saved admin token, internal
  exclusion or known automation can stop collection. Do not override these on
  real customer browsers simply to increase counts.
- `localhost` and `127.0.0.1` have different origin preferences. Check the
  actual test origin; do not assume another tab/hostname's settings apply.
- Check Pacific date range, allow normal batching and manually refresh admin.
  Last measured activity is an hour bucket, not an exact event timestamp.
- Preview excludes the current incomplete hour. The old five-minute cutoff
  cannot be reconstructed from hour-only storage.
- Network loss, blocked scripts and ambiguous delivery may drop batches.
  No automatic collection retry occurs without IDs; zero retained counts do
  not prove nobody visited.
- Server-observed excluded requests count only requests the server saw,
  not visits excluded by the browser before any behavioral request.

Never instruct customers to accept analytics or reveal internal collection
diagnostics on the storefront. Do not restore legacy session reports merely to
make a new dashboard nonzero. Business inquiry totals remain independently useful.

Localhost resolves to unknown/CAD; this is not evidence of a Canadian visitor.
Country/currency comes from the existing trusted-IP server-local resolver, not
browser country headers or submitted prices.

## What is measured, and what is not

- Actual rendered route entries and allowlisted navigation actions; not prefetch,
  rerenders, API calls or media downloads.
- Item impressions after the identity/price area reaches 50% visibility for one
  continuous second; separate loaded detail, desktop expansion and media actions.
  Full mobile details do not manufacture Show more clicks.
- Successful cart actions and quote open/start/attempt/error counts. A quote
  action is not a saved inquiry or proof of an individual conversion.
- Visible/focused, non-idle bounded active-time increments, summed as a
  **total estimate**. No raw time intervals, cross-tab identity/union, per-session
  duration, median or guarantee of distinct-person time.
  Identifier-free Web Lock coordination may reduce simultaneous active increments;
  it must not introduce stored tab/lease identifiers.
- Country, currency, source category, approved campaign, device and browser
  **page-view counts on independent axes**. No referrer hosts or combined
  multi-axis profiles. Do not combine filters to manufacture attribution.
  Country labels are country-only (`US`, `CA`, `Unknown`), not country/currency
  pairs. Per-item counts retain currency groups without joining page-view axes.
- Fixed coarse error counts and web-vital sums/sample counts for averages.
- Saved inquiries counted from authoritative business records, independent of
  analytics collection, linked to no analytics identity/source/journey. Notification
  failure does not undo receipt. Do not copy customer messages/contacts into analytics.
  New inquiries ignore legacy analytics input and never assign/save attribution.
  Existing private inquiry JSON may still contain historical
  `analyticsAttribution` fields; it is not rewritten, and new reports ignore
  those associations. This compatibility rule does not permit identified
  payloads at the analytics collector.

If saved business inquiries cannot be confirmed, the summary value is `null`.
Daily rows retain numeric `0` under the current response shape but include an
explicit unconfirmed-totals warning. Treat those rows as unavailable/unconfirmed,
not measured zero-inquiry days; preserve the warning in presentation/export.
Do not infer a conversion rate or a successful business-source read from them.

Only approved campaign codes in `STYL_ANALYTICS_CAMPAIGN_ALLOWLIST` are allowed.
Do not include customer data in marketing URLs. Server validation protects
market eligibility and public item metadata.

**Unavailable by design:** unique/new/returning visitors, sessions, individual
journeys, ordered per-session funnels, conversion/abandonment rates, per-session
source/item/inquiry attribution and medians. Label them unavailable; do not
estimate them from IPs, page views, or separate dimension totals. Independent
action counts may appear side by side but are not a cohort funnel.

## Configuration

These settings are server-side; never expose SMTP credentials to the frontend.

| Setting | Purpose / default |
| --- | --- |
| `STYL_ANALYTICS_ENABLED` | Collection switch; disabled unless deliberately enabled; client also requires the supported aggregate-only mode in public config |
| `STYL_ANALYTICS_ENVIRONMENT` | Separate local/test/staging/production datasets; local launcher forces local |
| `STYL_ANALYTICS_DB` | Private SQLite path; production example `/var/lib/styl-analytics/analytics.sqlite3` |
| `STYL_ANALYTICS_TIMEZONE` | `America/Los_Angeles` |
| `STYL_ANALYTICS_CAMPAIGN_ALLOWLIST` | Approved campaign codes only; empty means no campaign values retained |
| `STYL_ANALYTICS_EMAIL_ENABLED` | Initial default until admin settings are saved; defaults false. Local/test/staging sending is always blocked |
| `STYL_ANALYTICS_RECIPIENTS` | Initial comma-separated recipients until admin settings are saved; never inherits inquiry recipients |
| `STYL_ANALYTICS_REPLY_TO` | Optional business reply address, never a customer's form address |
| `STYL_ANALYTICS_DASHBOARD_URL` | Credential-free admin URL; HTTPS required in production |

Use existing SMTP settings only for an explicitly approved production send.
Do not overwrite inquiry configuration or treat a local flag as mail authorization.
Pacific is the approved reporting zone. Whole-hour UTC-offset zones are
supported, including Pacific DST; fractional-offset zones fail explicitly
because hour-only buckets cannot represent their day boundaries exactly.

### Admin daily-email settings

The new **Analytics → Daily email settings** form is implemented locally; this
change does not itself deploy it or enable production mail. It provides:

- **Enable daily summary emails**, recipient addresses and **Save email settings**.
  Enter one address per line or separate addresses with commas, up to 20 entries.
  The server validates addresses and removes case-insensitive duplicates.
  Enabling requires at least one recipient; disabling may retain addresses or save
  an empty list.
- A saved revision in the private `analytics_email_settings` SQLite table.
  Settings survive API/job restarts and override the two environment defaults
  above. They are not catalog data, not browser-local settings, and are included
  in a consistent analytics SQLite backup but not the catalog recovery ZIP.
- Authenticated `GET` and `PUT /api/admin/analytics/email-settings`, both private/
  no-store. PUT accepts `{enabled, recipients, expectedRevision}`; stale edits
  return 409 rather than overwrite another administrator. Validation and storage
  errors retain form entries; unavailable settings are not displayed as default
  disabled settings. SMTP passwords/sender settings are not exposed or editable.
- Preview, scheduled delivery and manual retry all read the saved settings.
  Local/test/staging can save an enabled preference for testing but
  `effectiveEnabled` remains false and no actual mail is sent.
- Saving settings does not send mail. When enabled in production, the existing
  job may send the latest due report at its next 15-minute check. Disabling or
  removing a recipient is checked again transactionally before each delivery
  claim; an email already claimed/in progress cannot be recalled.

Unsaved entries survive admin tab changes. Save clears any stale preview;
**Discard changes and reload** requires explicit confirmation. Corruption or
inaccessible storage causes an explicit error rather than fallback. Do not delete
the saved row to turn mail off: an absent row uses the environment defaults.
Use the disabled preference instead.
Settings persist until an administrator changes them; the 90-day report-history
cleanup does not remove current configuration.

### Public collector contract and private aggregate tables

There is **no new environment mode flag**: `STYL_ANALYTICS_ENABLED` remains the
switch and `GET /api/analytics/config` always advertises `mode: "aggregate-only"`.
Its response fields are `enabled`, `mode`, `environment`, `timezone`,
`heartbeatSeconds` (15), `idleSeconds` (60), `maxEvents` (20),
`maxBatchBytes` (16384) and `allowedCampaigns`. The browser must check enabled
and supported mode before measuring; config is not permission to override opt-out.

`POST /api/analytics/events` accepts an `events` array of objects with `name`,
`path` and optional `properties`. Optional batch `context` permits only the
reviewed `source`, `medium`, `campaign` and `viewport` fields. Success returns
only `{accepted: number}`. Old tokens, identity fields, event times and referrer
fields are rejected with 422; there are no retry/deduplication IDs.

`POST /api/analytics/session` is 410. Legacy
`DELETE /api/analytics/session` remains solely for historical withdrawal,
not new tracking or person-specific erasure from aggregate counters.

| Private table | New durable data |
| --- | --- |
| `analytics_aggregate_counts` | UTC receipt hour + independent dimension/label/metric counts and sums |
| `analytics_aggregate_items` | Hour + catalog item identity/currency occurrence counts, without browser linkage |

New-mode hour-rounded `coverage.trackingSince` and `coverage.lastEventAt`
metadata is separate from legacy timestamps. If legacy data exists, show its
existence warning without using its sessions/events/rollups as report data.
Maintenance expires old raw event/session/visitor/receipt rows under the existing
30-day bound (including visitor expiry) and old rollups/new aggregates at
13 calendar months. Historical inquiry JSON and backup copies are not rewritten.

## Daily report commands

From the backend directory, using the configured Python environment:

```powershell
..\.venv\Scripts\python.exe -m app.analytics_reports preview --date 2026-09-28
..\.venv\Scripts\python.exe -m app.analytics_reports preview --date 2026-09-28 --format html
..\.venv\Scripts\python.exe -m app.analytics_reports run-due
```

Set the private database/environment in that same terminal. Preview reads
aggregate reporting data and separate safe business inquiry totals; it never
sends mail, edits catalog/inquiry records or attaches legacy sessions.
`run-due` performs retention/job maintenance and sends only in explicitly enabled
production with separately configured recipients. Local sending stays disabled.

Email/preview uses half-open Pacific day windows with an effective end no later
than the current complete-hour boundary. A prior completed day can be reported
in full; a current day's incomplete hour is excluded. Raw event times do not
exist to provide five-minute precision. Frozen new-mode text/HTML snapshots
contain aggregates only and must not reuse legacy snapshots.

The daily message is a short business digest: page views and a seven-day baseline,
saved inquiries, estimated active minutes/hours, cart/quote actions, top-three
equipment and country/source lists, and a dashboard link. Full-day changes are
not applied to a partial day; its header says "Through HH:00". General technical
coverage/retention/privacy explanations stay in the full dashboard, not the email.
Only actionable collection/data/error issues appear under **Attention**.
Unavailable inquiry totals stay N/A. Empty breakdowns and routine no-error text
are omitted. HTML uses headings and a compact table; previewing still sends nothing.

### Delivery states and retries

- Report date/timezone/version/recipient has durable operational delivery state;
  these job identifiers are not browsing identifiers.
- Version 3 mail uses concise aggregate-only snapshots. Cross-version accepted/ambiguous
  delivery protections remain: a format change cannot resend an already accepted
  recipient or bypass an uncertain-send hold. Do not load old privacy/session
  snapshot content into the new report.
- SMTP acceptance is not inbox/read confirmation.
- Definite mail failures use bounded backoff, at most three automatic attempts.
  Accepted recipients are not resent because another recipient failed.
- Interrupted or ambiguous sends are held for operator review, not blindly
  replayed after restart. Concurrent workers must not duplicate daily sends.
- The timer catches up the latest due reporting day, not every historical missed
  date. Do not flood recipients or automatically send repeated corrections.
- These **mail** retries do not authorize retrying uncertain browser event
  batches. Collection has no event IDs and cannot safely deduplicate a replay.

Manual retry is a deliberate production operation with duplicate risk:

```powershell
..\.venv\Scripts\python.exe -m app.analytics_reports retry --date 2026-09-28 --recipient internal@example.com --acknowledge-duplicate-risk
```

It requires production email enablement and a currently configured approved
recipient, and cannot resend an already accepted delivery. Review delivery
history/mailbox before any authorized retry. No real send is authorized here.

## Production schedule

Existing templates:
[service](../deploy/styl-analytics-report.service) /
[timer](../deploy/styl-analytics-report.timer).
They were installed during the approved `a611b4e` production rollout.
The timer checks every 15 minutes; the job handles the 08:00 Pacific boundary,
mail retry rules, retention and restart catch-up without sending on every tick.
The first manual run and next scheduled run succeeded with email sending disabled.
No recipient delivery has been attempted. Before enabling actual mail, retain the
remaining privacy/recipient/inbox-verification gates below.

Release checklist:

1. Complete served-market privacy review and plain-language Privacy notice/opt-out.
   If applicable rules require another processing/consent model, resolve that
   before enabling production; do not assume universal consent exemption.
2. Approve analytics recipients, a separate real-mail test and deployment.
3. Create private service-owned storage, outside public/catalog/upload paths,
   with independent production configuration and reviewed campaign allowlist.
4. Verify final dependencies/timezone data, aggregate-only ingestion, rejected
   identified payloads, legacy 410 endpoint and client/server exclusions.
5. Prove new reports and snapshots exclude legacy history. Verify the old private
   data's existing retention/approved cleanup path rather than deleting it as an
   incidental migration or leaving it indefinitely.
6. Review/install the timer under deployment approval. Retention must run even
   if email is disabled; exact calendar expiry and backup policy need verification.
7. Verify real proxy/GeoIP behavior, load, dashboard/CSV, safe backups/restore,
   job state and each approved recipient's mailbox separately.

SMTP failure cannot reliably alert through that same SMTP channel; external
operational alert delivery remains a separate setup. Rollback should disable new
collection/mail, never re-enable old identified tracking.

## Retention, deletion and backups

- New hour/dimension aggregates: **13 calendar months**, not a fixed 390-day
  approximation. Expire according to calendar boundaries and test those boundaries.
- New raw events/browser identifiers/session/journey rows: never persist.
- New aggregate report snapshots/delivery metadata: **90 days**.
- Existing legacy raw/session data: retain privately, outside new reporting,
  under the pre-existing **30-local-calendar-day** raw-data bound and approved
  deletion obligations. This change does not destructively migrate or certify
  deletion of existing data. Verify maintenance or an approved bounded cleanup
  before release; turning off reads is not retention enforcement.
- Existing legacy summaries/snapshots/backups retain their own existing expiry
  obligations. Do not relabel a mixed legacy database/backup as anonymous.
- Business inquiries and infrastructure logs have separate retention/access
  policies and may contain personal data.

Analytics maintenance applies the existing raw 30-day and rollup
13-calendar-month expiry windows. It does not rewrite authoritative inquiry JSON
or protected backups. Historical `analyticsAttribution` fields in saved inquiries
can remain until separately approved cleanup; backup expiry/deletion handling
also remains a separate obligation. Do not claim all legacy associations were
removed simply because current analytics tables were maintained.

Opt-out clears queued events and stops later collection, but anonymous totals
cannot be linked back to an individual for selective deletion. Do not offer a
false server-history deletion confirmation or silently reset old privacy choices.
Exports/backups and previously delivered mail copies also need appropriate
expiry; mailboxes have their own retention policy.

The catalog recovery ZIP does **not** include analytics. Use a consistent SQLite
backup API rather than copying the main file alone while WAL is active:

```powershell
..\.venv\Scripts\python.exe -m app.analytics_reports backup --destination "C:\PrivateBackups\analytics-copy.sqlite3"
```

Use a new, private destination. A full backup may include legacy private data and
mail recipient/delivery metadata, not only anonymous counters. Keep it protected.
Restore only under the approved procedure, not over a running service; reapply
expiry and earlier approved deletions without reintroducing legacy data into
new reports. A real production restore remains a verification gate.

## Local validation versus production readiness

Existing test locations remain `backend/tests/test_analytics.py`,
`backend/tests/test_analytics_reports.py`, `frontend/tests/analytics.test.mjs` and
`frontend/tests/e2e/analytics.spec.ts`. The aggregate-only release passed
149 backend, 33 frontend unit and 181 configured browser executions. Live
desktop/phone smoke checks, private report/preview/auth boundaries, a consistent
SQLite backup and a same-server catalog recovery drill were completed.
The concise email revision has its own tests and release evidence in project history.
Use isolated test data with SMTP disabled and record the final candidate/results
in project history through the implementation/testing owner.

Verify enabled automatic aggregate-only startup, Privacy opt-out/prior decline,
absence of identifiers/raw persistence/combined dimensions, normal bounded
batching and no ambiguous retries, independent inquiry counts, Pacific/DST/hour
cutoffs, legacy isolation/retention, auth/export safety and mail-job guards.

Mocks/emulation do not certify physical devices, actual cross-country visitors,
mailbox delivery, production capacity, installed jobs/alerts or production
backup restoration. Those remain separate gates. City/postal and AI chat stay
deferred; identified session drill-down is excluded, not a future toggle.
