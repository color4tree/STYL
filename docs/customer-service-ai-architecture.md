# STYL website and AI-assisted customer-service architecture

Status: Local guest chat, single-operator inbox and scoped Gemini adapter
implemented and locally verified (see project history for harness caveats). No production push/deployment
or paid billing authorized. Synthetic Gemini adapter connectivity verified.

Date: 2026-09-28

Current source baseline: `d874a8e`; deployed GeoIP/attribution application baseline:
`bc45b22`, plus subsequent operational documentation.

Related documents:

- [Current STYL application](../README.md)
- [Traffic analytics and daily email requirements](traffic-analytics-requirements.md)
- [Current responsive UX](mobile-ux-design.md)
- [Future catalog/admin schema](catalog-and-admin-schema-design.md)
- [Hosting/deployment](lightsail-deployment.md)
- [Country/market selection](geoip-pricing.md)
- [Living regression plan](regression-test-plan.md)
- [Backup & Records policy](records-backup-and-retention.md)

## 2026-09-29 local implementation request and readiness

The owner requested customer text chat, a consolidated admin inbox with separate
conversations for different customers, clearly highlighted human-intervention
cases, and AI answers constrained by an approved, expandable scope (initially
product information and evidenced compatibility). Gemini is the preferred first
provider to evaluate, with provider/model replacement supported without rebuilding
the chat UI, conversation store or business rules. Finish log-backup work first;
development and testing remain local, with no production push/deployment.

The prior MUSE/CoWork discussion is historical, not the selected integration.
The broader design below remains a proposal unless covered by this confirmed
direction. Confirmed: guest chat now with future guest/account coexistence;
existing admin sign-in for this single-operator local pilot; initial configurable
topics are published product facts, current selected-market prices and explicitly
documented compatibility. Missing evidence, excluded topics and customer requests
go to human help. Named/revocable staff identities remain a multi-agent public
release requirement. The current English UI/response templates do not constitute
multilingual certification or a production response-time promise.

### Gemini prerequisites verified from official documentation

Checked 2026-09-29; these are service documentation facts, not an account inspection:

- [Google AI plans](https://ai.google.dev/gemini-api/docs/google-ai-plans):
  subscription development benefits apply to the AI Studio web interface.
  Direct Gemini API use by STYL is separately billed/managed. Eligible Developer
  Program Cloud credits may apply after Cloud Billing setup; Google One AI
  credits are a different system. No credit entitlement/balance is assumed.
- [API keys](https://ai.google.dev/gemini-api/docs/api-key): a Gemini API key is
  associated with a Google Cloud project. New AI Studio keys are authorization
  keys by default; unrestricted standard keys are rejected. Keys remain backend
  only and must never enter browser bundles, chat, screenshots or Git.
- [Billing](https://ai.google.dev/gemini-api/docs/billing): select models support
  free-tier testing; paid-tier access requires linked Cloud Billing and may
  require a minimum prepayment. Do not activate billing, auto-reload or a purchase
  without owner approval. Subscription quotas are not the website's API budget.
- [Terms](https://ai.google.dev/gemini-api/terms): unpaid input/output may be
  used to improve Google's services and reviewed by people; do not submit
  sensitive, confidential or personal information. Paid services do not use
  prompts/responses for product improvement, but limited abuse-monitoring/legal
  retention still applies. Paid is not zero retention. Review age, regional and
  customer-facing use restrictions before any public rollout.

### Access checklist before a real connection test

- Confirm an AI Studio/Cloud project and project identifier under the intended
  Google account; do not assume the Google One subscription created one.
- Confirm the project's billing tier, credit availability and an approved test
  spending limit. Synthetic/non-sensitive messages only for local tests.
- Have the owner place a restricted API key in a private local secret store
  outside Git/OneDrive. Record only configured/not-configured status, never its
  value. Do not ask the owner to paste a key or password into chat.
- Select an API model actually available to that project. Keep provider/model
  configurable server-side; do not bind business policy to a hard-coded Gemini
  UI product name or consumer account session.
- Verify authentication/model availability, one bounded synthetic generation,
  timeout/quota failures and usage accounting without printing credentials.
- Verified: the owner-created **STYL chatbot** project
  (`gen-lang-client-0774748468`) shows **Free tier**. The owner entered the key
  through a masked local terminal; it is encrypted with Windows-user DPAPI under
  `%LOCALAPPDATA%\STYL\AI\gemini-key.dpapi`, outside Git/OneDrive. No full key was
  sent in chat or committed. Model listing authenticated successfully.
- A small `gemini-3.8-flash` connectivity call returned the expected synthetic
  acknowledgement, but subsequent structured support calls returned HTTP 503.
  A listed `gemini-2.5-flash` alternative returned 404. Actual structured support
  with **`gemini-3.5-flash`** succeeded: synthetic CAD price and source reference
  were correctly rendered, with 802 total tokens reported. The local default is
  therefore `gemini-3.5-flash`, explicitly configurable rather than silently
  switching models on failure. Listing alone is not inference-availability proof.
- No billing was enabled, no automatic paid fallback exists, and live checks
  used only synthetic non-sensitive content. Free-tier limits/service
  availability can change; quota/errors persist a human-help outcome.

Support transcripts, settings and queue history are business records under the
new no-age-expiry policy. Their separate SQLite store must join the private
backup/restore workflow before the chat feature is declared complete. Explicit
privacy deletion remains separate; chat must not create identified traffic
analytics or transmit private catalog provenance to an AI provider.

### Implemented local pilot versus the broader proposal

- `/support`: opt-in guest conversation start, browser-token resume, scoped
  messages, current state and sources, explicit human-help button. No intrusive
  popup; Ask STYL links remain separate from shopping/quote controls.
- Admin **Support inbox**: separate guest threads, attention count/highlights,
  takeover, human replies, explicit resume for subsequent messages and close.
  Configurable automatic replies and topic checkboxes; provider/model/credential
  readiness is visible but keys never appear in the UI.
- Private SQLite conversations/messages/jobs/settings, one bounded in-process
  worker, scoped request idempotency and compare-and-swap revisions. Provider
  calls happen outside database transactions. Guest tokens are stored only as
  hashes on the server. Future account ownership can be added at the access
  boundary; there is no customer account system or cross-device recovery yet.
- Catalog evidence is refreshed before inference and rechecked before publishing;
  drafts, missing-market items and changed prices/details cannot produce stale
  queued answers. Human takeover/settings changes fence late AI publication.
- Gemini returns a constrained topic/reference/field decision, **not unrestricted
  factual prose**. Trusted code renders published values and exact currency
  amounts, or flags missing/unverified compatibility for a human. This intentionally
  conservative first version favors evidence over conversational elaboration.
- Public fact fields are allowlisted; no tools, arbitrary URL fetches, private
  provenance, admin credentials or other customer records are available to AI.
  Obvious email/phone/URL input is kept away from the provider, but that heuristic
  is not comprehensive personal-data detection. Synthetic-only local use remains
  mandatory with the unpaid provider.
- Support SQLite is included in Backup & Records. Optional cleanup only removes
  complete, unchanged, closed threads and their children from a verified archive;
  active/changed/pending work and current settings remain.
- No automatic expiry, named staff login, email notification/outbox, file/voice
  upload, arbitrary FAQ authoring, analytics correlation, or production enablement
  was added. Those broader sections below remain future design.

### Local configuration and verification commands

`STYL_SUPPORT_ENABLED` defaults false. Even when true, this pilot refuses feature
use outside `local`/`test`; do not change a production analytics environment to
circumvent that restriction. Provider defaults `gemini`, model defaults
`gemini-3.5-flash`. `STYL_SUPPORT_DB` must be a separate absolute private SQLite
path, defaulting beside the analytics database. `mock` is for isolated local/tests.
The current local API task loads the private key and uses
`%LOCALAPPDATA%\STYL\AI\support.sqlite3`; SMTP remains disabled.

```powershell
# Save through a masked prompt (no API call or billing change):
.\configure-local-gemini.ps1 -Action Save
# Use -Replace only for intentional key replacement.
.\configure-local-gemini.ps1 -Action Status

# A new shell must load the key privately before a synthetic live check:
.\configure-local-gemini.ps1 -Action Load
.\.venv\Scripts\python.exe backend\check_gemini.py --model gemini-3.5-flash --support
```

The helper decrypts only into the current process environment; launch only the
backend from that shell, not a frontend build. The `NEXT_PUBLIC_*` namespace must
never contain an API key. Model changes use server configuration and restart, not
provider-specific UI changes. Another provider implements the small
`Provider.decide` protocol and adapter registry; policy, storage and UI stay owned
by STYL. Configuration alone cannot magically support an unimplemented provider.

Automated verification uses isolated temporary databases/catalogs, `mock`, empty
provider-key environment variables and mocked HTTP transports. Real Gemini
synthetic checks are reported separately, never as production customer-readiness.

### Switching between the deployed baseline and AI development

The owner requested separate branches on 2026-09-30:

- `main`: deployed application `d6d00a3`, plus documentation-only deployment record
  `b903f1c`. The application/deployment files in these commits are identical.
- `ai-assistant/baseline-2026-09-29-2227-pt`: the undeployed AI pilot and its
  Backup & Records/log-retention dependency. The name records the production
  baseline activation, **2026-09-29 22:27 Pacific** (`2026-09-30T05:27:30Z`),
  not a claim that this experimental work is deployed.

Stop the two local STYL tasks before changing branches, inspect `git status`,
then use either:

```powershell
git switch main
git switch ai-assistant/baseline-2026-09-29-2227-pt
```

Run only the switch for the branch you want, then restart **STYL: local API**
and **STYL: local web**. The existing ignored local starter checks whether the
support module and private-key loader exist on the selected branch. On `main`
it disables support and does not load Gemini credentials; on the AI branch it
uses the existing encrypted key and private support database.

Git switching does not migrate or delete local data. The selected private catalog
mirror, chat/analytics databases and DPAPI key remain outside Git. Original
uncommitted catalog JSON edits are intentionally excluded from the AI commit;
do not overwrite them or indiscriminately stage/stash all files. If future branch
changes conflict with those edits, resolve that explicitly rather than forcing
checkout. Branch switching itself never pushes, deploys or changes billing.

## 1. Executive recommendation

Add a first-party customer chat experience to STYL, backed by a server-controlled
support service. Use an AI-provider adapter so the implementation is not tied to
MUSE, CoWork or another candidate before evaluation.

The AI should answer routine questions using approved STYL information and
current public catalog facts. It should not guess when it lacks context. A
durable human-support queue is part of the first customer-facing release,
not a later substitute for failed AI responses.

Recommended approach:

1. Define support policies, approved knowledge and human ownership first.
2. Establish reliable human contact/handoff and named staff access.
3. Add read-only, grounded AI assistance behind a feature flag.
4. Pilot and evaluate answer quality, escalation and privacy before broad rollout.
5. Integrate aggregate support outcomes with the future analytics/dashboard and
   daily email without copying transcripts into analytics.

Keep the existing catalog, prices, cart and quote flow operational if chat,
its provider or its database is unavailable. Do not run a large language model
on the current small Lightsail instance, and do not make production chat depend
on an open VS Code session, desktop automation or an operator's personal login.

## 2. Scope and decisions

### User-confirmed direction

- Near-future live chat for customer questions.
- AI normally responds; human fallback when the AI lacks sufficient context.
- Gemini free tier is selected for synthetic local testing, with the verified
  `gemini-3.5-flash` model; paid/customer production use remains unapproved.
- Architecture must include the current website, UX, prerequisites and overall design.

### Proposed first release

- Text chat on public desktop/mobile pages; explicitly labelled AI assistance.
- Contextual questions about an item, general policies and an optional shared cart.
- Approved FAQ/policy retrieval and live public catalog tools.
- Human handoff, offline follow-up, support inbox, assignment and notifications.
- Conversation recovery, abuse/cost controls, privacy notice and retention.
- Basic support health/quality metrics; optional aggregate analytics integration.

### Not in the first release

- AI changing catalog data, prices, publication status, stock or compatibility.
- Autonomous discounts, binding quotes, purchases, refunds or payment handling.
- Customer order/account lookup without a separately designed identity check.
- General browsing of arbitrary customer-supplied URLs or autonomous desktop work.
- Customer image/file uploads, voice, social-channel chat or screen sharing.
- Unrestricted training/medical/rehabilitation advice or invented load/fit claims.
- Automatic learning from every chat or human response.
- Replacing the broader catalog model or completing the analytics project as a
  prerequisite for launching support.

All schedules, budgets, retention periods and performance limits in this draft
are proposed defaults requiring review, not existing service promises.

## 3. Current STYL: what exists today

| Component | Current capability | Implication for chat |
| --- | --- | --- |
| Next.js/React/TypeScript frontend | Home/product collection, accessories, product details, cart, quote form and admin | Integrate a shared public-site launcher without disrupting these journeys |
| FastAPI | Public catalog/market/selection, protected admin writes, uploads and inquiry receipt | Reuse domain validation, not an admin credential inside an AI tool |
| Catalog persistence | Separate product/accessory JSON and uploaded media on disk | Current item type + immutable ID is the integration key; no dependency on future global SKUs |
| Pricing/publication | Independent CAD/USD, country-based market, missing-market hiding, draft exclusion | AI answers must respect the same visibility and price semantics |
| GeoIP | Local Country MMDB with scheduled production updates | Pass only necessary country/currency context; not raw IP or an inferred delivery address |
| Cart | Browser-local selected items/quantities reconciled with the current catalog | Share with chat only through an explicit action and server revalidation |
| Inquiries | Save request JSON before SMTP; customer email is Reply-To | Existing inquiry endpoint is not a support conversation, agent inbox or delivery/read receipt |
| Admin access | Shared bearer-token access | Not sufficient for accountable multi-agent support; named identities/roles are a prerequisite |
| Hosting | One AWS Lightsail Ubuntu instance, Caddy HTTPS, frontend :3000 and API :8000 on loopback | Start small; isolate AI work and bound load so the storefront remains responsive |
| Traffic analytics | Aggregate-only collection deployed in a611b4e; real daily email disabled | Future support may supply optional unlinked aggregate counts only; no browser/session/conversation correlation in traffic analytics |
| AI/live support | Local/test guest chat, Gemini adapter and single-operator inbox implemented | Not deployed; no production staffing schedule/SLA, account login or arbitrary knowledge-base authoring; see local pilot scope above |

Current source references:
[API and inquiry handling](../backend/app/main.py),
[country resolver](../backend/app/location.py),
[root layout](../frontend/src/app/layout.tsx),
[store header](../frontend/src/components/StoreHeader.tsx),
[cart logic](../frontend/src/lib/useCart.ts).

### Current deployment diagram

```mermaid
flowchart LR
    Visitor["Customer browser"] --> TLS["Caddy HTTPS"]
    TLS --> Web["Next.js :3000"]
    TLS --> API["FastAPI :8000"]
    Web --> API
    API --> Catalog["Catalog JSON and media"]
    API --> Inquiry["Private inquiry JSON"]
    API --> Country["Local GeoLite2 Country MMDB"]
    API --> SMTP["Configured SMTP notification"]
    Updater["Scheduled root updater"] --> Country
```

The diagram is logical. Browser API calls use same-origin routing in production;
ports 3000/8000 must not be opened publicly to support chat.

## 4. Prerequisites and readiness gates

| Gate | Needed before | Required owner/input and exit condition |
| --- | --- | --- |
| PR-01: support scope | AI pilot | Business owner approves supported topics, prohibited promises, escalation reasons and initial language(s) |
| PR-02: human service | Public chat | Named people, support hours/timezone/holidays, backup coverage, queue ownership and achievable response target |
| PR-03: knowledge readiness | AI answers | Reviewed product facts, compatibility evidence and shipping/installation/warranty/returns FAQs with owner/version/effective dates |
| PR-04: provider eligibility | Any external AI request | Exact product/vendor identified; production API/SDK, data-processing terms, retention/training controls, region, deletion and cost evaluated |
| PR-05: privacy and consent | Collecting chats | Customer notice, processing basis/consent model, transcript/contact retention, human/provider sharing and deletion process approved |
| PR-06: staff identity | Human inbox | Named authentication, operator permissions, audit trail and ability to revoke access; no shared catalog token as an agent login |
| PR-07: durable storage | Handoff pilot | Conversations, ownership, ticket state and notifications survive restart; tested backup/restore and deletion |
| PR-08: operations | Production rollout | Secrets, rate/cost limits, monitoring, fallback, feature flags, rollback and operator runbook verified |
| PR-09: evaluation set | AI pilot | Owner-reviewed common questions, missing/conflicting-data examples and unsafe/private-data requests with expected outcomes |
| PR-10: customer fallback | Any public release | A working human/offline route is visible even if the AI provider, stream or widget fails |

Important unanswered business content is not something the model should invent.
Examples to prepare: delivery coverage, freight/installation process, lead-time
policy, returns, warranty applicability, assembly/manual links, support contact,
business hours, and evidence for model-specific fit/load claims.

An email notification mailbox alone does not establish staffed live support.
If no operator is available, launch as "AI help + contact the team", not as
guaranteed live human chat.

## 5. Future logical architecture

```mermaid
flowchart TB
    Browser["STYL browser: storefront + lazy chat UI"] --> Edge["Caddy / HTTPS"]
    Edge --> Existing["Existing catalog / market / inquiry APIs"]
    Edge --> ChatAPI["Chat API: guest access, validation, rate limits"]
    Edge --> StaffUI["Protected support inbox"]
    StaffUI --> StaffAuth["Named staff identity and role checks"]
    StaffAuth --> ChatAPI
    ChatAPI --> Store["Private support store: conversations, tickets, outbox"]
    ChatAPI --> Stream["Authenticated SSE / polling updates"]
    Stream --> Browser
    Store --> Worker["Bounded support worker / job dispatcher"]
    Worker --> Policy["Context, grounding, action and handoff policy"]
    Policy --> Tools["Allowlisted read-only catalog tools"]
    Tools --> Existing
    Policy --> KB["Approved, versioned support knowledge"]
    Policy --> Adapter["AI provider adapter"]
    Adapter --> Provider["Selected production AI service: TBD"]
    Worker --> Human["Human queue / assignment"]
    Human --> Store
    Worker --> Notify["Durable notification outbox / existing SMTP transport"]
    Store --> Events["Sanitized support outcome events"]
    Events -. "When enabled and separately approved" .-> Analytics["Unlinked analytics aggregates"]
    Analytics -.-> Daily["Daily business summary email"]
```

### Component responsibilities

- **Chat UI:** render messages/status, collect deliberate customer input and
  selected context, resume authorized conversations, expose human/quote actions.
- **Chat API:** own authentication, conversation access, idempotency, current
  market resolution, message validation, durable state and authorized events.
- **Support worker:** make bounded provider calls outside catalog request paths;
  never hold a database transaction while waiting for a model/network.
- **Grounding/policy layer:** select approved evidence, constrain tools, validate
  answer/action contracts and decide when to clarify or hand off.
- **Provider adapter:** isolate provider SDK, model/version configuration,
  deadlines, cancellation, usage and error mapping. It does not own business policy.
- **Knowledge store:** approved business documents and publication metadata,
  distinct from arbitrary repository files or customer transcripts.
- **Support inbox:** assignments, full authorized context, replies, handoff state
  and staff audit; no dependency on the owner keeping this chat session open.
- **Notification worker:** persist notifications and delivery status; a failed
  email does not lose a handoff ticket.
- **Analytics adapter:** emit allowed counts/outcomes only. It must be safe to
  disable without disabling customer support.

### Initial infrastructure recommendation

Keep the current frontend/API and catalog JSON. Add a separate private SQLite
support database with transactions, uniqueness constraints, WAL-aware backups
and bounded lock waits. A small dedicated worker can use durable jobs/outbox
tables in that database; Redis, a vector service and a new managed database are
not mandatory for the first release.

Use an approved external production AI API for inference. The current 1 GB
Lightsail server is not a target for hosting a large model. Prefer curated text
search/SQLite full-text search for a small FAQ corpus initially; introduce
embeddings/vector retrieval only if evaluation shows a need.

Bound worker concurrency and queue length, and measure memory/CPU/latency with
the storefront under load. Move the worker/storage to separate infrastructure
when measurements justify it. Do not add multiple catalog-writing API workers
or multi-server writes to the current JSON catalog as a side effect of chat.

## 6. Grounding and safe AI behavior

### Knowledge sources and trust

| Source | Use | Restrictions |
| --- | --- | --- |
| Current public catalog/market services | Price, selling unit, published specifications, eligible items | Fetch structured current facts; enforce current market and publication rules on every turn |
| Approved STYL FAQ/policies/manual excerpts | General service/product guidance | Published, versioned, applicable, reviewed and within expiry; cite the relevant source |
| Customer's explicit chat input | Question and stated requirements | Untrusted data, not instructions to override policy or obtain privileged tools |
| Customer-shared item/cart references | Context for the question | Re-resolve IDs and prices server-side; never trust client prices/status |
| Staff-only support notes | Authorized human work | Excluded from customer AI retrieval unless separately reviewed/published |
| Private provenance, credentials, admin files, other customers' inquiries | None | Never indexed or passed to the model |
| Arbitrary external URLs or uploaded documents | None in MVP | No autonomous fetch/ingestion from customer instructions |

RAG means retrieving approved evidence to support a response; it is not a
guarantee that a model will be correct. Retrieved text can contain malicious
instructions too. Treat all retrieved/customer text as data, restrict tool
capabilities server-side and validate outputs independently of the prompt.

### Response decision

1. Resolve the customer question and explicit item/context references.
2. Obtain current market-eligible public facts and applicable knowledge.
3. If the question is ambiguous, ask a concise clarification; proposed maximum
   two unsuccessful clarification turns before handoff.
4. If evidence is missing, stale, contradictory, out of scope or insufficient
   for a safe answer, explain the gap and start the human fallback flow.
5. Otherwise generate a short answer with source links/identifiers, then validate
   item references, amounts, currency and permitted actions before publication.

Do not use the model's self-reported confidence as the sole handoff gate.
Use evidence sufficiency, topic risk, tool outcomes and evaluated thresholds.

### Non-negotiable business rules

- Never fabricate stock, delivery dates, installation coverage, discounts,
  warranty entitlement, certifications or final shipping/tax amounts.
- Live catalog data is authoritative for displayed prices; cached embeddings or
  previous chat turns cannot override it. CAD/USD stay separate.
- An item hidden for the current market or in Draft cannot be disclosed through
  chat search, comparison, citations, recommendations or tool output.
- Do not infer compatibility from category or nominal dimensions. **75 mm is
  not exactly 3 inches (76.2 mm)**; unsupported model-specific fit/load questions
  go to the team rather than receiving a confident guess.
- Quotes are requests, not purchases or binding offers. Direct customers to the
  existing quote flow and let them review anything proposed for submission.
- No admin token, production shell, generic SQL, arbitrary HTTP fetch, payment,
  catalog-write or customer-record-search tool is available to the customer AI.
- The model may propose a handoff; application policy persists and authorizes it.
- Human corrections become knowledge drafts for review, not automatically
  published training material or shared memory across customers.

For MVP, send progress/status events while preparing an answer, but buffer and
validate the complete answer before publishing it. Token-by-token answer
streaming is optional later; it must not expose unvalidated prices or unsafe
claims that cannot be meaningfully retracted.

## 7. Human fallback and conversation ownership

### Handoff triggers

- Customer explicitly requests a person, at any time.
- Insufficient/conflicting/outdated evidence or an unsupported question.
- Specific compatibility/load/warranty/exception questions needing confirmation.
- Requested commercial negotiation, custom delivery or other binding decision.
- Repeated misunderstandings, negative feedback or provider/tool failure.
- Abuse/security handling or a topic outside the approved support scope.

The initial notice must clearly explain AI assistance and possible review by
the STYL team. The final privacy design determines when additional confirmation
is needed before forwarding a transcript, especially to an external helpdesk.

### State model

| State | Customer sees | Allowed responder |
| --- | --- | --- |
| `ai_active` | AI assistant label and grounded replies | AI through policy-controlled worker |
| `handoff_requested` | Request is being saved | AI may send acknowledgement only, not continue guessing |
| `queued` | Saved request; live availability or offline follow-up explained | No new substantive AI reply |
| `human_active` | Named STYL team member joined | Assigned human |
| `waiting_customer` | Team needs a clarification | Human remains owner |
| `resolved` | Resolution and optional feedback | No new answer until explicit reopen |
| `closed` | Read-only history where retained | None; new/reopened request follows a defined route |

Provider failures are recorded separately from conversation ownership. They must
not silently switch a human-owned conversation back to AI.

### Handoff requirements

- Persist a ticket before displaying "Your request has been saved."
- Save reason code, item references, market, last question, available source
  references and the authorized transcript. A machine-generated summary must be
  labelled and must not replace the transcript as the evidence.
- Assignment/claim is transactional. Two staff members cannot unknowingly claim
  the same conversation. Audit who claimed, transferred, replied and resolved it.
- Taking over increments an ownership/generation version, cancels in-flight AI
  work and fences stale replies. A late model result must not reach the customer
  after human takeover. This is a database/server rule, not only a hidden UI button.
- Returning control to AI requires an explicit staff action and customer-visible
  notice. No automatic "AI resumes after N minutes" while a human owns the chat.
- Presence combines staffed hours, assignment/capacity and recent staff heartbeat.
  A configured schedule alone does not justify "A person is online."
- Outside coverage, say the team is offline and offer follow-up. Ask for a contact
  address only when needed; show the configured response target without inventing
  an exact wait time or guaranteeing immediate service.
- A browser close does not erase a saved queue ticket. Provide an authorized
  resume method; email follow-up is separate from an in-browser delivery receipt.

If the support database cannot save a handoff, say it was **not saved** and show
the existing contact/quote route. SMTP acceptance, ticket creation, agent
assignment and a human response are four different states.

## 8. Customer UX

### Launcher and contextual entry

- Use a small, clearly labelled **Ask STYL** launcher, not an intrusive auto-open
  popup. No unsolicited fake "agent typing" messages or repeated attention sounds.
- Place a contextual "Ask about this item" action on detail pages and optionally
  cards after layout review. Pass item type/ID, not the full DOM.
- On the cart, offer "Ask about my selection" with a clear share-selection action.
  Do not silently scrape browser storage or quote fields into chat.
- Show the current item/market as removable context chips inside chat. Changing
  an item or leaving a page must not silently replace a question's context.
- Keep the primary shopping/quote actions visually dominant.

### Desktop wireframe

```text
Catalog / product page                       +------------------------------+
                                            | Ask STYL                  [-]|
Existing details and actions remain usable   | AI assistant | Talk to team  |
                                            | About: [Selected item x]     |
                                            | Prices: USD                  |
                                            |------------------------------|
                                            | Customer question            |
                                            | AI answer with source link   |
                                            | [View item] [Request quote]  |
                                            |------------------------------|
                                            | Message...             [Send]|
                                            | AI can make mistakes. Privacy|
                                            +------------------------------+
```

Proposed width: 360-420 CSS px with a responsive maximum; height limited to the
visible viewport. It must not cover the active quote form or important cart
controls. Allow minimize/close without losing an already saved conversation.

### Mobile wireframe and collision rules

```text
+----------------------------------+
| Back   Ask STYL             Close |
| AI assistant / STYL team member   |
| [Item context] [USD]              |
|----------------------------------|
| Message history                  |
| Grounded reply / human status    |
|                                  |
|----------------------------------|
| Message...                 Send  |
| Privacy / contact fallback       |
+----------------------------------+
```

- Use a full-height sheet or dedicated support route on narrow phones rather
  than shrinking a desktop panel. Respect dynamic viewport height and safe areas.
- The software keyboard must not cover the composer or Send; keep a reachable
  Close/Back control. Browser back closes the sheet before unexpectedly leaving
  the shopping journey.
- Offset/minimize the launcher above existing cart/product sticky actions, or
  place it in a non-overlapping header/menu location when space is insufficient.
  Never hide Add to cart, Request a quote or Submit inquiry behind chat.
- Define stacking with the menu and enlarged media dialogs: one modal surface
  owns focus at a time. Opening a gallery/menu must not leave two focus traps.
- Preserve shopping scroll position, selected media, cart and quote input after
  closing chat; do not reintroduce the fixed quote-navigation flash.

### Interaction states and accessibility

- States: closed, connecting, ready, waiting for answer, answer available,
  handoff saving/queued, human joined, offline, reconnecting, failed and resolved.
- Send on Enter; Shift+Enter adds a newline. Support IME composition, touch,
  screen readers, keyboard navigation, large text and reduced motion.
- Announce complete new messages/status politely, not every token. Keep focus
  predictable and return it to the launcher on close.
- Keep unsent text on recoverable failures; retry a send with the same idempotency
  key. Distinguish locally typed, server-saved and recipient-delivered states.
- Scroll to a new message only if the user is near the bottom. Otherwise show a
  "New message" indicator without pulling them away from older messages.
- Buttons/links need visible labels and practical touch targets, at least 44 px.
- Sources and quotes are rendered as sanitized text/limited Markdown; block
  active HTML, scripts, remote embeds and unapproved URLs.
- Never label an AI as a person. When a human joins, change the header and show
  the responder's approved display name. Offer "Talk to the team" persistently.

Example insufficient-context reply:

> I cannot confirm that attachment fits your exact rack from the information
> available. I can ask the STYL team to check it. Please share the rack model;
> I will not assume that 75 mm and 3-inch uprights are interchangeable.

### Quote integration

For the first release, prefer a clear **Request a quote** action that opens the
existing form with a customer-reviewable summary. Sharing transcript excerpts
or contact data requires the approved privacy flow. The form still saves through
the existing inquiry API and retains its failure behavior.

Do not mark a quote as received merely because chat recommended one or created
a support ticket. Persist an optional support/inquiry association only when a
real inquiry was saved; use idempotent linkage and preserve old inquiry clients.

## 9. Data and API design

### Proposed logical records

| Record | Important fields/invariants |
| --- | --- |
| Conversation | Opaque ID, access scope, state, market, creation/update time, retention expiry, ownership version |
| Participant / guest access | Bound guest session or named staff ID/role; expiry/revocation; no identity inferred from IP |
| Message | ID, conversation ID, author type, sequence, client idempotency key, body, save time, reply/generation version |
| Context snapshot | Server-validated item references, currency, optional explicitly shared cart; no client-authoritative prices |
| Evidence / knowledge document | Approved content, owner, version, publication/effective/expiry status, scope and source link |
| AI run | Provider/model/policy versions, evidence references, status, latency, usage/cost and sanitized failure; no credentials |
| Handoff ticket | Reason, state, priority, owner, timestamps, approved contact reference and conversation link |
| Notification/outbox job | Unique delivery key, destination class, attempt/status, safe error and next retry |
| Staff audit | Actor, action, target and timestamp; restricted retention/access |
| Support outcome | Fixed topic/reason/outcome codes in private support records; only separately approved unlinked aggregates may leave for traffic analytics, never conversation/customer correlation IDs |

Conversation state, ownership claims and message/outbox persistence require
transactions. Do not implement them as independently overwritten JSON files.
Support content and optional contact details are private, not stored under
public catalog uploads or returned by public catalog routes.

### Proposed endpoints, not existing APIs

- `POST /api/support/conversations`: create/resume an authorized guest scope.
- `POST /api/support/conversations/{id}/messages`: validate and persist a message
  with idempotency key; enqueue work and return its accepted ID/status.
- `GET /api/support/conversations/{id}/events`: authenticated SSE or incremental
  polling with an ordered cursor; resume without duplicate messages.
- `POST /api/support/conversations/{id}/handoff`: persist a human request.
- `POST /api/support/conversations/{id}/close`: close under the defined policy.
- Protected staff endpoints for queue/claim/reply/transfer/resolve and knowledge
  publication, each enforcing named roles and ownership.

Opaque IDs are not authorization. Bind every read, write and stream to the
customer's guest scope or an authorized staff session. Use secure same-origin
session handling, CSRF/origin protection where applicable, expiry and revocation.
Never place conversation bearer credentials in public URLs, analytics or logs.
Cross-device/email recovery needs a separate verified, expiring access flow.

Start with HTTP POST plus authenticated fetch-based SSE and bounded polling
fallback. WebSockets are optional if selected human-chat tooling requires them.
Caddy streaming/timeouts and reconnect behavior must be tested; do not assume
the current proxy configuration already meets long-lived chat needs.

## 10. Typical end-to-end flows

### A. Answerable item question

```mermaid
sequenceDiagram
    participant C as Customer
    participant U as Chat UI
    participant S as STYL support service
    participant K as Catalog / approved knowledge
    participant A as Selected AI provider
    C->>U: Ask about this item
    U->>S: Message + item reference + idempotency key
    S->>S: Authorize, persist, queue
    S-->>U: Saved / checking information
    S->>K: Resolve eligible current facts and evidence
    K-->>S: Facts + source versions
    S->>A: Minimum permitted context and question
    A-->>S: Proposed grounded reply
    S->>S: Validate reply, ownership version and allowed links/actions
    S-->>U: Persisted answer + sources
```

### B. Missing context / human handoff

1. The support policy identifies insufficient evidence or an explicit person request.
2. AI acknowledges the limitation; no speculative answer is substituted.
3. Save a handoff ticket, preserving authorized context and reason.
4. Show queued/live/offline state from real staffing information.
5. A staff member atomically claims it; cancel/fence any pending AI response.
6. The customer sees the human join. If offline, collect follow-up contact only
   as needed and state the approved response target.
7. Staff reply/resolution is saved and audited. Any knowledge improvement goes
   through a separate approval process.

### C. Provider or network failure

The saved message remains durable. A bounded retry cannot create duplicate
messages/tickets or repeat side effects. If the provider exceeds its deadline,
cost budget or availability limit, offer human/offline support. If the browser
disconnects, resume from its authorized event cursor. If storage itself failed,
show "not sent/saved" and the existing contact route instead of claiming success.

## 11. Privacy, security and provider boundaries

- Customer chat is a separate customer-service processing purpose from
  aggregate-only traffic measurement. Its notice, processing basis/consent,
  provider sharing and retention still require separate approval. Traffic
  measurement starts automatically only with enabled aggregate-only config and
  no opt-out/exclusion; it has an ordinary Privacy-page opt-out, not a storefront
  consent panel or technical status. Opting out must not prevent basic support;
  do not use chat as a hidden substitute for tracking.
- No real transcripts, contact details or private business data go to an external
  AI/helpdesk provider until that provider and data-sharing scope are approved.
  Local tests use synthetic messages and mocked providers.
- Send only the minimum approved conversation/context to the model. Keep
  contact information out of model prompts when not needed for the answer.
- Keep all provider/SMTP credentials server-side and out of browsers, prompts,
  screenshots, source control and diagnostics. Use least-privilege keys and
  document rotation/revocation.
- Apply access checks to messages, streams, exports, staff notes and recovery.
  Test cross-conversation access and role bypass, not only the login screen.
- Use allowlisted tools/arguments, timeouts, rate limits and bounded output.
  The model cannot authorize its own write/tool permission.
- Validate user/provider/staff content before rendering. Retrieved instructions
  must not cause arbitrary URL fetches, credential access or data exfiltration.
- Progressive abuse controls should protect availability/cost without retaining
  raw IP histories by default. If security logs require IPs, document separate
  restricted purpose and retention as in the analytics requirements. Existing
  infrastructure logs and business contact records may contain personal data;
  aggregate-only traffic measurement does not make the whole site anonymous.
- The 2026-09-29 owner policy supersedes the earlier proposed 30/90-day cleanup:
  support transcripts, contact linkage and business audit history have no
  automatic age expiry. Include them in private backup/download verification and
  approved optional cleanup. Operational logs are separate (14 days); applicable
  privacy and explicit deletion obligations still apply.
- Deletion must cover provider copies where supported, local content, derived
  embeddings, exports and backup expiry/replay. Provider deletion capability is
  a selection gate, not an assumed promise.

Attachments are deferred. Adding them later requires private storage, file/type/
size validation, malware handling, metadata stripping, access expiry and a
separate decision on whether an AI may process them.

## 12. Analytics and daily email integration

Follow the [analytics requirements](traffic-analytics-requirements.md): automatic
first-party aggregate-only measurement with Privacy-page opt-out, prior-decline
preservation, exclusions, independent coarse dimensions and retention.
Chat itself must work if analytics is absent or opted out. This does not remove
the separate future chat notice/consent/provider-approval gates.

Proposed safe events: `chat_open`, `chat_started`, `ai_answer_completed`,
`handoff_requested`, `handoff_claimed`, `human_first_reply`, `chat_resolved`,
`chat_feedback` and `chat_to_inquiry`. These are future private support-domain
signals, not authorization to send raw events to traffic analytics. Only approved
unlinked hour/category totals, bounded duration sums/counts and provider
usage/cost aggregates may be exported. No conversation, customer, browser,
session, event or page-view correlation IDs, exact event/request times, message
text, email/phone, raw IP or customer-entered postal codes enter traffic analytics.
Do not store combined dimensions or derive a person's journey from those totals.

Useful aggregate daily additions:

- New support conversations, human requests and unresolved queue count.
- AI response latency/failures, handoff reasons and human first-response time.
- Customer-rated helpfulness and explicitly confirmed resolutions.
- Chat-assisted saved-inquiry business totals only if that separate private
  support/inquiry association is approved; export unlinked counts, never the
  association or a traffic-session conversion rate.
- Recurring **approved topic categories** with knowledge gaps.
- Provider usage/cost and service-quality warnings.

Do not call absence of a handoff "AI resolution". Report no-handoff rate separately
from confirmed resolution; abandoned chats are unknown outcomes. Chat-assisted
inquiry counts are association, not evidence that AI caused the conversion.
Do not count a handoff ticket as a lead/quote unless it meets the separately
defined business record criteria.

Daily email contains aggregates only; the approved schedule remains 08:00 Pacific,
with incomplete-hour exclusion for previews. Traffic visitors/sessions, medians,
individual journeys and per-session attribution remain unavailable. Do not email
full transcripts or feed them to an external summarizing agent merely to produce
the report. Rules-based
observations are the default. Human case notifications and daily business
summaries have separate recipient/purpose settings.

City/ZIP analytics remains Phase 2 / P2. It is not required for chat and must
not be used to infer a customer's delivery address or identity.

## 13. Provider/platform selection

Gemini is now the preferred first local API candidate. MUSE/CoWork were earlier
discussion candidates, not verified production integrations. A personal desktop
agent or consumer Gemini session is not a substitute for a supported server API.

| Evaluation area | Required evidence |
| --- | --- |
| Integration | Supported server-side API/SDK, service authentication, deployment terms; no scraping a personal UI |
| Grounding | Structured tool/context support, source attribution, output validation and predictable missing-context behavior |
| Human support | Native or integrable inbox, webhooks/events, assignments, identity and takeover/cancellation semantics |
| Privacy | Retention/training settings, data region/subprocessors, deletion/export, contractual review and minimum-context controls |
| Reliability | Deadlines, cancellation, rate limits, streaming/resume, outage handling and observable errors |
| Cost | Input/output/tool charges, staff seats if any, budget controls, alerts and usage export |
| Portability | Exportable conversations/knowledge, STYL-owned IDs and policy, stable adapter contract, migration/exit path |
| Quality | Passes STYL's curated evaluation set across required languages and risk topics |

Possible implementation patterns:

1. **First-party UI + STYL orchestration + AI API + own human inbox:** most control;
   STYL must build and operate the inbox/queue.
2. **Managed support platform with AI and human agents:** potentially quicker
   staffing workflow, but requires verified hooks, privacy, pricing and export.
3. **Hybrid:** first-party storefront UX/domain tools, with a selected platform
   providing agent inbox and model integration.

Recommended default is **first-party UX and domain/policy control**, with the
inbox/provider choice decided by evidence. Do not build all three patterns.
The adapter boundary should support submit/cancel, response/status, evidence/tool
results, usage and normalized failures; avoid designing a generic agent platform.

## 14. Operations, budgets and release gates

Proposed pilot limits to validate:

- Maximum customer message length: 4,000 characters.
- One in-flight AI turn per conversation; initially at most two provider calls
  concurrently across the support worker, with a bounded queue.
- Acknowledge saved messages within one second at expected load; target a
  validated answer within 15 seconds at p95, with a 30-second provider deadline.
  These are test targets, not public promises before measurement.
- Explicit per-session and daily cost budgets, set by the owner before launch.
  Estimate cost from calls/tokens/tool usage and provider rates; no assumed price.
- Lazy-load chat code only as needed. Measure storefront LCP/INP/CLS, memory and
  CPU against the existing baseline; chat must not worsen the quote/cart path.

Feature controls: chat enabled, AI enabled, human live mode, offline follow-up,
analytics emission and allowed tool/topic set. With AI disabled or budget
exhausted, preserve human/offline support rather than hiding the fallback.

Monitor API/worker/job health, queue depth/age, oldest unassigned ticket, provider
latency/errors/cost, stale knowledge, message delivery and notification outcomes.
Alerts need an owner and a fallback channel; a failed SMTP channel cannot be its
only failure notification.

Restore testing must cover guest access, staff ownership, message sequencing,
pending handoffs and outbox deduplication. A restore/deployment must not resurrect
deleted conversations or restart old AI replies. Treat existing intermittent
WebKit/prefetch issues as known baseline concerns to test, not as solved by chat.

## 15. Phased delivery

| Phase | Deliverable | Exit condition |
| --- | --- | --- |
| 0: discovery/readiness | Confirm provider identity, support scope/hours, knowledge, privacy, budget and UX | PR-01..10 have owners; launch blockers identified |
| 1: human support foundation | Guest conversations, named staff access, queue, offline follow-up, notifications and recovery | A customer reaches a responsible human without AI; persistence and privacy verified |
| 2: grounded AI pilot | Read-only catalog/knowledge answers and reliable handoff behind flags | Evaluation gates, ownership fencing, outages and cost limits pass; internal/small pilot approved |
| 3: controlled public rollout | Desktop/mobile widget, monitoring, feedback and operations runbook | Human coverage/fallback ready; limited rollout and rollback demonstrated |
| 4: business insight/expansion | Approved aggregate analytics/daily summary; optional languages/media/CRM | Separate feature decisions and privacy/capacity review; no scope creep into autonomous commerce |

Analytics implementation can proceed separately; use a no-op analytics adapter
until it is ready. The broader SKU/catalog migration and City database are not
launch dependencies.

## 16. Acceptance/evaluation catalog

All cases below are planned; none are certified by this draft.

| Case | Required evidence |
| --- | --- |
| CS-001 | Answer a supported product/policy question using current approved evidence and valid source links |
| CS-002 | Missing, stale, conflicting and ambiguous knowledge produces clarification/handoff, not an invented answer |
| CS-003 | CA/US/unknown contexts preserve correct CAD/USD prices, draft/missing-market hiding and separate sale units |
| CS-004 | Unsupported model-specific compatibility/load claims, including 75 mm versus 3 inch, escalate safely |
| CS-005 | Customer can request a person at any time; offline/unavailable support is honestly labelled |
| CS-006 | Handoff persists before confirmation; assignment is atomic; simultaneous claims and transfer races are handled |
| CS-007 | Human takeover cancels/fences delayed AI work; no late AI message appears after takeover, including reconnect |
| CS-008 | Retry, double-click, disconnection, BFCache and server restart preserve message order without duplicate messages/tickets |
| CS-009 | Provider timeout/outage/quota and database/SMTP failure retain safe fallback and never fake a saved/delivered state |
| CS-010 | No cross-conversation or staff-role access; guest expiry/recovery/revocation and CSRF/origin protections verified |
| CS-011 | Prompt injection, malicious source text and output links cannot obtain secrets/private drafts or invoke unapproved tools |
| CS-012 | Chat and provider records obey separately approved notice/consent/retention/deletion; traffic analytics receives only approved unlinked aggregates, no transcripts/contact data, conversation/customer correlation IDs or raw event times |
| CS-013 | Desktop and phone Chromium/WebKit, keyboard/IME/screen reader, safe areas, large text and reduced motion verified |
| CS-014 | Launcher/panel does not cover cart/quote controls or conflict with menu/media dialogs; closing restores focus/scroll/input |
| CS-015 | Explicit item/cart context is accurate; navigation and quote conversion do not silently submit or alter customer data |
| CS-016 | Provider/model/source versions, usage/cost and handoff reasons are auditable without exposing credentials |
| CS-017 | Daily support aggregates agree with fixed conversation/inquiry fixtures; abandonment is not counted as resolution |
| CS-018 | Worker/store backup and rollback preserve ownership/outbox/deletion state and do not affect catalog/quote availability |
| CS-019 | Load, message/queue/cost limits and measured latency meet approved pilot targets on actual deployment resources |
| CS-020 | Any enabled external provider and real notification channel pass explicitly approved end-to-end tests; blocked human/device checks are not reported passed |

Initial AI release gate: zero private/draft-data disclosures, unauthorized actions,
fabricated price/fit promises or takeover-race replies in the curated critical
evaluation set. Report the set's size and coverage; a clean set is evidence, not
a guarantee of universal model correctness. Track useful-answer and handoff
quality separately and require owner review before changing the provider/model.

## 17. Decisions to resolve next

1. Exact MUSE/CoWork/other candidates and whether to build or buy the human inbox.
2. Support topics, initial language(s), knowledge owner and evidence standards.
3. Who answers handoffs, hours/timezone, response target and backup staffing.
4. Named staff identity provider and permission roles.
5. Transcript/contact retention, provider sharing/region and customer notice.
6. Daily/per-session AI budgets and expected concurrency/traffic.
7. Approved contact/notification recipients and offline recovery method.
8. Desktop panel/mobile sheet design and contextual entry points.
9. When the aggregate support metrics join the separately planned daily email.

Recommended immediate next step: approve the support scope and human fallback
workflow, assemble the knowledge pack, and evaluate the exact provider candidates
against the same questions before implementing an integration.
