# STYL mobile experience design

Status: Approved scope implemented and locally verified; physical-device and production checks pending

Date: 2026-09-25

Baseline: Repository commit `334d320`

Scope: Responsive web experience, not a native app

### Document library and detail-aware chat (2026-10-01)

Use visible >=48px Choose file/Upload document buttons; missing upload fields
produce inline errors and first-invalid focus, not a disabled button with no
explanation. Preserve selected files/titles/assignments on failure. The dedicated
Uploaded documents section shows title/format/size/time/status/scope and current
readiness without requiring the operator to search through catalog media.
All/Clear controls capture current eligible products only; general customer
service Q&A removes the product-selection requirement. Keep long titles and
assignments inside 320/390px pages.

On verified item details, show a compact About chip using that public item name.
Keep it plain text and within the chat width. Switching routes updates the
default for a new send, not an in-flight/retried question or previous quote.
Preserve chat visibility/draft/history, let explicit item names take precedence,
and clear page context on unavailable/non-detail routes.

### Clean contact follow-up and keyboard continuity (2026-10-01)

Use **STYL Assistant** capitalization. Remove the customer warning banner and
manual help/refresh controls; provide a small Privacy link with the substantive
data-use disclosure on the privacy page. Automatic escalation offers optional
name/email fields through a separate private form, never by composing an AI
message. Display saved-contact acknowledgement quietly and permit deliberate
editing. Contact drafts survive failures/conflicts and reset only for a new
conversation, not ordinary polls.

The message textarea stays focusable (read-only briefly during its HTTP submit,
not disabled). Enter-send retains focus/caret so the next question needs no click;
IME/Shift+Enter and error-draft behavior stay intact. Contact-form Enter cannot
submit the message form. No completion, incoming answer or poll may steal focus
after the customer clicks elsewhere, minimizes the chat or navigates.

### Question-based team collaboration (2026-09-30)

Admin highlights each **Needs a team reply** question and provides Reply on that
question. The chosen question is pinned above **Your reply**; **Send reply**
publishes a warm, clearly attributed team message with the quoted original
question in both admin and customer views. Long quotes must remain readable
without widening the page. Polling/new messages must not retarget an unsent draft.
Keep only reply and close controls for a conversation; no takeover/resume modes.
AI continues answering new questions while earlier questions receive team replies.
Resolved status applies to the specific question, not every pending question in
the thread. Customer and team bubble alignment remains left/right as approved.

### Professional assistant and pending human requests (2026-09-30)

Use **STYL assistant** instead of guest/implementation terminology; actual human
messages use **STYL team**. A successful request displays only **Your request has
been sent to our team.** Customer-visible errors are concise/actionable and retain
drafts; raw HTTP/provider/state reasons stay in admin. A compact local-preview
warning links to the essential privacy detail rather than filling the dialog.
Pending human attention and active answering coexist: show preparing/available
assistant status while retaining the pending notice, never "AI paused" merely
because help was requested. Team identity belongs to its messages, not an
exclusive conversation mode.

### Floating support and focused admin tools (2026-09-30)

The owner approved replacing the dedicated-page-first customer chat with a
persistent bottom-right avatar/dialog. The icon stays with storefront navigation;
it animates subtly only while AI is processing, respects reduced motion and shows
unread replies. No unsolicited auto-open, sound or fake human-typing indication.
Customer messages align left; AI/human messages align right with explicit labels.

On desktop use a compact bottom-right panel. At 320/390px use nearly full width
while retaining visible webpage space, safe-area/visual-viewport offsets and a
reachable composer when the keyboard opens. Avoid sticky Add/quote/cart controls.
Do not compete with gallery/menu dialogs for focus. Preserve guest conversation,
open/minimized state and draft through Next navigation; source links remain safe.
The legacy `/support` entry can open the same shared UI rather than duplicating
chat state. Keep it absent from admin pages.

Customer Support retains its page-style inbox and adds central Knowledge
management for product assignment, extraction and mandatory draft approval.
Merge business/log/support backups into the existing Backup tab alongside catalog
recovery. Keep primary functions prominent; consolidate informational guidance
into short notices/expandable details without hiding failures or destructive
confirmation/verified-download requirements.

### Local Ask STYL / Support inbox (2026-09-29)

Original pilot (presentation superseded by the floating widget above): use a
dedicated responsive `/support` page, linked unobtrusively from navigation
and footer, not an auto-opening overlay competing with galleries, cart stickies
or the quote composer. Keep All products/Equipment/Accessories actions unchanged.
Expose guest start, locally retained access, conversation messages, sources,
human-help status and a >=48px composer action. Preserve unsent text on failure,
support Shift+Enter/IME and do not auto-scroll away from older messages.
The local unpaid-AI/synthetic-only warning must be visible before starting.

Admin Support inbox keeps a distinct guest-thread list and selected conversation,
stacks on narrow phones, and visibly highlights human attention. Explicit
takeover/resume/close, scope checkboxes and reply drafts must remain usable at
320/390px without horizontal scrolling. Failed writes retain drafts; failed reads
are stale/error states, not an empty-success inbox. Auth errors hide private
content. Existing catalog drafts survive visiting the support section.

### Backup & Records (2026-09-29)

Keep create, download, saved-file verification and optional source removal as
distinct actions. Download is not confirmation of a safe saved copy. Display
coverage/disk warnings and private-data guidance without exposing record contents.
Use wrapping archive metadata, clear category choices, >=48px action targets,
explicit destructive confirmations and no 320px horizontal overflow. Preserve
editor drafts when entering/leaving this section and disable overlapping work.
File verification and removal failures remain visible and retryable where safe.
Deleting the verified server ZIP is a separate action from source-record removal.

### Configurable engineering details (2026-09-29)

The Home banner tab includes a separate Engineering details editor for the
section heading, optional introduction, and four image/title/description cards.
Keep the existing four positions and public 1/2/4-column responsive layout.
The current photographs and text are defaults for older configurations, not an
automatic rewrite of saved content. The public section retains its disclosure
control and remains usable on mobile; top-banner mobile hiding is unchanged.

Editors can upload JPG/PNG/WebP/GIF up to 8 MiB or enter an image URL/path.
Banner and engineering photo inputs use a prominent outlined **Choose photo**
button with an upload icon and short format/save instructions inside a bordered
panel, rather than an unstyled "Choose file / No file chosen" line. Keep the
underlying native picker, descriptive accessible names, keyboard operation,
>=48px targets and disabled state during saves/uploads. Cancelling keeps the
existing image; selecting uploads a draft replacement but does not publish.
Show previews without crashing while a URL is partly typed. Keep visible labels,
stable textarea accessible names, multiline wrapping, >=48px actions and no
horizontal overflow at 320px. A single Save changes action publishes changes;
uploads alone do not. Preserve failed/unsaved edits, block overlapping work,
and keep the existing tab/Backup dirty-state guards. Shared images must not be
deleted while another catalog/banner/engineering card references them.

### Safari privacy notice (2026-09-29)

The owner supplied an iPhone banner offering **Dismiss / Reduce Protections**.
This is consistent with Safari's own privacy-compatibility UI, not a STYL consent
panel. It is distinct from a certificate/HTTPS or fraudulent-site warning and
does not by itself prove either malicious behavior or site safety.

WebKit documents that advanced protections can affect legitimate functionality,
including tracker-request blocking and mitigations for graphics/audio/screen APIs.
Apple announced that iOS 26 extends advanced fingerprinting protection to normal
browsing by default; the screenshot does not establish Private Browsing mode.
The exact banner-trigger heuristic is not documented in the reviewed sources.

STYL application-source inspection found no banner text, fingerprinting SDK or
direct canvas/WebGL readback. Optional first-party aggregate measurement and
Web Vitals are present; this does not identify them as the banner's cause.
The previously recorded WebKit prefetch/access-control diagnostics are not proof
of the same issue. Do not claim a fix from emulation or recommend reducing
customer protections simply to hide the message.

If browsing works, dismiss the notice and keep protections enabled. To diagnose
actual breakage, record iOS version/tab mode/current URL and inspect console/
network activity with Safari's trusted-device Web Inspector. The supplied phone
screenshot shows the older two-choice header; reload the current version before
comparing behavior. No phone settings were changed by this work.

Sources: [WebKit Private Browsing 2.0](https://webkit.org/blog/15697/private-browsing-2-0/),
[Apple iOS 26 announcement](https://www.apple.com/newsroom/2025/06/apple-elevates-the-iphone-experience-with-ios-26/),
[Safari security warnings](https://support.apple.com/en-us/102279),
[Web Inspector setup](https://webkit.org/web-inspector/enabling-web-inspector/).

### Round 2 update (2026-09-26)

This update supersedes the earlier currency/publication holds below:

- Independent Canada/CAD and US/USD prices; Canadian IP locations use CAD,
  identified other-country locations use USD, and unknown locations default to
  CAD (updated later on 2026-09-26). Display explicit currency plus two decimals.
- Hide items in markets without a price and flag missing prices in admin.
- New Product and Accessory entries default to Draft; preserve the established
  Product lifecycle and add the same controls/filtering to Accessories.
- Home banner retains the original independent text/image editor and layout,
  but has no price field or price display. The product-selector approach was
  withdrawn on 2026-09-26. Mobile hiding stays unchanged; catalog prices remain.
- Normalize the obvious Bench/Benches duplicate without redesigning taxonomy.
- Optional equipment weight, date persistence regression checks, and separately
  labeled current/earlier upload batches are included.
- On mobile/tablet below the desktop navigation breakpoint, show Products and
  Accessories directly in a second header row. Keep Menu for the other
  destinations and retain desktop navigation. Anchor offsets account for the
  taller header so destination headings remain visible.

The date-clearing report was not reproduced in current Chromium/WebKit tests.
The exact date remains a private date-only string through notes editing,
serialization, persistence, and reload. This is not a claim about all physical
devices or a claim that a database-only fix was made.

### Approved scope update (2026-09-25)

The customer approved implementation of the non-publication pre-launch checklist
and responsive UX improvements. Desktop and mobile have equal priority: desktop
navigation, multi-column catalogs, detail layouts, and split-pane admin editing
must remain optimized rather than adopting stretched phone layouts.

- Draft/publish feedback and related workflow changes are excluded.
- CAD/USD presentation and mixed-currency-summary changes are on hold. Retain
  existing currency defaults, support, symbol-only formatting, and separate totals.
- Prices must accept up to two decimal places and display two decimal places;
  reject negative prices and excess precision with clear errors.
- Keep every eligible product in the home collection. The original Featured-first
  ordering is superseded by the 2026-09-28 decision: manual admin sequence is the
  exact storefront order; Featured remains metadata only.
- Start accessory long-form content with inline expansion, not a new route.
- Add private source tracking without exposing it in public API responses.
- Keep the customer-value business principle prominent in the homepage
  introduction as a compact callout on both desktop and mobile (placement
  confirmed on 2026-09-25). Do not duplicate it in the About section.
- Hide the promotional Home banner image/title card below 768 CSS px.
  Keep the introduction, business principle, and shopping actions visible.
  Tablet/desktop banner display and the admin banner editor remain available.

The original proposal below remains the design reference. Sections proposing
currency changes, new routes, analytics, image-derivative infrastructure, or
publication work are not implementation authorization. Physical-device testing,
field performance measurements, and production video verification cannot be
replaced by local viewport/browser checks.

Local verification completed: 20 production-build browser E2E tests across desktop
and phone-sized Chromium, 35 backend tests, six frontend cart/price tests,
production build and TypeScript, and lint with no errors (five image-optimization
warnings). Browser checks covered 320-1440 px layouts, desktop navigation/grids,
mobile admin list/edit flow, real accessory save/reload, separate public
description/use fields, two-decimal prices, selling units, public exclusion of
source notes, and gallery interactions. A controlled six-second clip retained
video and audio through conversion; byte-range delivery and Chromium seeking were
verified locally. These checks do not certify physical iOS/Android behavior or
production-proxy playback.

The expanded E2E pass found and fixed a mobile interaction bug: changing the Save
bar between relative and sticky positioning on input blur could move the Add media
button during a click. Save-bar positioning is now stable; keyboard visibility
handling does not change document layout. The repeated media-add scenario is
covered by the automated mobile regression test.

## 1. Recommendation

Make mobile a deliberate buying-research journey, not just a stacked version of
the desktop layout:

**Discover equipment -> inspect media and fit -> save a selection -> request a quote.**

Start with navigation, content order, touch controls, and the quote form. Then
improve media browsing and cart feedback. Treat phone-based admin work as a
separate workflow, rather than shrinking the desktop editor.

Keep STYL's off-white/charcoal palette, strong product photography, and restrained
visual style. Mobile should feel clearer and faster, not denser or more animated.
Keep the existing desktop experience polished.

### What this document does not do

- No application code, catalog data, infrastructure, or deployment changes.
- No checkout, payments, customer accounts, native app, or currency conversion.
- No redesign of the product positioning or invention of warranty/delivery claims.
- No commitment to new routes, dependencies, or analytics providers.

## 2. Evidence and limitations

This proposal is grounded in the current source and the original
[portal design](STYL%20Portal%20Design.md), which already identifies mobile-first
design and Chrome/Safari parity as goals.

Reviewed surfaces:

- [Home, navigation, cart preview, and inquiry form](../frontend/src/app/page.tsx)
- [Product detail](../frontend/src/app/products/%5Bslug%5D/page.tsx)
- [Accessories](../frontend/src/app/accessories/page.tsx)
- [Cart](../frontend/src/app/cart/page.tsx)
- [Gallery](../frontend/src/components/PhotoGallery.tsx) and
  [video playback](../frontend/src/components/CatalogVideo.tsx)
- [Product admin](../frontend/src/app/admin/page.tsx),
  [accessory admin](../frontend/src/app/admin/AccessoryManager.tsx), and
  [media editor](../frontend/src/components/PhotoEditor.tsx)
- [Global styles](../frontend/src/app/globals.css)

The public HTTPS preview failed to load during this review. The deployed revision
was not verified. No real-device usability session, responsive screenshot audit,
or performance baseline was completed. Layout risks below are source-backed;
severity and proposed improvements still require viewport and user testing.
Performance values later in this document are targets, not current measurements.

### Current experience: strengths and friction

| Surface | Source-backed observation | Mobile impact / risk | Proposed response |
| --- | --- | --- | --- |
| Home navigation | Main navigation is hidden below `md`; no replacement menu is rendered. Logo, cart, and quote actions remain in one row. | Product/accessory discovery is harder; header crowding needs testing at narrow widths. | Compact shared header with an accessible menu and cart. |
| Home hierarchy | Large hero copy, multiple actions, a principle statement, and a separate feature panel precede the collection. | Products can require substantial scrolling before evaluation begins. | Shorter introduction; make equipment discovery the first task. |
| Long-page content | Brand-detail cards stack on phones; multiple sections use large vertical padding. | A long editorial sequence separates shopping and inquiry tasks. | Prioritize collection and concise trust content; progressively disclose secondary material. |
| Gallery | Shared galleries already support thumbnails, enlargement, and video. Navigation is button-based; no swipe handler is present. | Good functionality exists, but touch discoverability can improve. | Retain shared gallery and explicit controls; add optional swipe with clear position feedback. |
| Controls | Home quantity buttons are 32 px; cart buttons and media-editor controls are 36 px; gallery controls are 40 px. | These fall below the proposed 44 px touch-target standard. | Larger hit areas with clear spacing, without oversized icons. |
| Accessories | Quantity changes use vertically split arrow controls; full specifications appear on each card. | Precision tapping and long browsing sessions. | Horizontal quantity stepper and expandable secondary details. |
| Product detail | Media precedes product identity; specifications and compatibility precede the purchase actions. | Name, price, and actions can be separated by a long scroll. | Bring identity and primary actions forward; keep fit warnings visible. |
| Cart | Summary follows the item list on phones; items have no thumbnails. | Long selections delay the next step and are harder to scan. | Compact rows and a contextual quote action. |
| Quote form | Fields use placeholders without persistent labels; submission has no explicit pending state. | Field meaning disappears while typing; repeated submission is possible. | Labels, autofill, validation, and visible pending/success/error states. |
| Admin | Catalog list and editor stack below `lg`. | Selecting an item can leave the editor far below the viewport. | Separate list and edit views on mobile, preserving desktop split view. |

## 3. Users and success criteria

### Primary journeys

1. **First-time phone visitor:** Understand what STYL sells, find equipment, and
   inspect a relevant item without navigating a long brand presentation.
2. **Careful buyer:** Inspect images/video, dimensions, compatibility, and included
   items; distinguish confirmed information from information requiring a quote.
3. **Returning buyer:** Review saved selections, adjust quantities, and submit an
   inquiry without re-entering product context.
4. **Owner on a phone:** Find an item, update its details or upload media, confirm
   that saving succeeded, and return to the list without losing edits.

### Proposed usability targets

In a formative test with five representative users on their own phones:

- At least four find Products or Accessories within 10 seconds without assistance.
- At least four find dimensions and compatibility information within 30 seconds
  on a fixture where that information is available.
- At least four add an item, find it in the cart, and change quantity without
  an accidental removal.
- At least four complete a prepared quote inquiry within two minutes without
  losing entered data or submitting twice.
- All can explain that the cart requests a quote, not an immediate paid order.

These are proposed release checks, not statistical proof of a conversion uplift.
Collect baseline results before comparing the redesigned experience.

## 4. Shared mobile foundation

### Responsive layout

| Width | Proposed behavior |
| --- | --- |
| 320-639 CSS px | One-column commerce content, 16 px outer gutters, compact header. |
| 640-767 CSS px | Two columns only where cards remain readable; otherwise retain one column. |
| 768-1023 CSS px | Tablet layouts, normally two product columns; navigation must fit without crowding. |
| 1024 CSS px and above | Preserve desktop navigation and appropriate split/grid layouts. |

Use content fit, not device names, to decide where a component changes layout.
Verify 320, 360, 390, 430, 768, 1024, and 1440 px widths, plus landscape phones.
Do not assume a wide viewport implies a mouse.

Proposed mobile visual tokens:

- Body: 16 px with approximately 1.5 line height.
- Supporting text: 14 px; avoid small all-caps text for important information.
- Main heading: approximately 30-36 px, allowed to wrap naturally.
- Section heading: 24-28 px; card title: 20-22 px.
- Section spacing: generally 32-48 px, rather than desktop-scale gaps everywhere.
- Touch targets: at least 44 x 44 CSS px; primary actions preferably 48 px tall.
- Adjacent small controls: at least 8 px separation where practical.
- Inputs: at least 16 px text, persistent labels, and visible focus styles.
- Product media: stable aspect ratio and `contain` treatment when cropping would
  hide equipment; reserve decorative cropping for brand imagery.

These are starting tokens, not fixed-height constraints. Long names, localization,
browser zoom, and accessibility text settings must be allowed to expand layouts.

### Navigation

Recommended header: **STYL logo | Cart with count | Menu**.

- Aim for a compact 56-64 px header at default text size, allowing growth.
- Menu opens a labeled modal sheet with Products, Accessories, About, and
  Request a quote.
- Products links to the collection; Accessories links to its existing page.
- Menu rows have generous touch targets; Close is always visible.
- Move focus into the menu, contain modal focus, support Escape and backdrop
  dismissal, and return focus to the trigger.
- Close the menu after navigation; prevent the background from scrolling while open.
- Keep the header consistent across home, accessories, detail, and cart.
- Make anchor destinations visible below the header; use appropriate scroll offset.
- Do not rely on hover or icon recognition alone.

Do **not** add a permanent bottom navigation bar in the first iteration. Combined
with a sticky header and contextual action bar, it would consume too much of the
phone viewport. Reconsider only if testing shows repeated navigation difficulty.

### Contextual bottom actions

Use one bottom action area only where there is a clear next step:

- Product detail: price and Add to cart.
- Cart: Request a quote, with selected-item count.
- Admin editor: unsaved/saving status and Save.
- Home and accessory listing: no global bottom action bar initially.

Reserve page space for the bar and device safe-area inset. It must not cover the
last content, browser controls, form errors, or keyboard-focused fields.
Hide the detail bar while its equivalent inline action is visible and while a
media dialog is open. Handle virtual keyboards explicitly in forms and admin.
At high zoom or short landscape heights, fall back to an in-flow action.

## 5. Screen-by-screen design

### 5.1 Home: get to equipment sooner

Recommended order:

1. Compact header.
2. Short value proposition, business principle, and the short **All products /
   Equipment / Accessories** actions. Show the
   promotional Home banner card only at widths of 768 CSS px and above.
3. Product collection, with a **Browse accessories** link below 1024 CSS px.
   Hide this duplicate collection link on desktop, where the main Accessories
   navigation remains visible.
4. Concise trust/engineering content.
5. Compact selection summary when the cart is nonempty.
6. Quote form and concise contact information.
7. Secondary brand material.

Target: at 390 x 844 CSS px and default text size, Equipment is visible in the
initial viewport. The collection heading and first product identity should be
reachable within one viewport-height scroll. Validate with real copy and media;
do not meet the target by truncating essential content or shrinking text.

Keep the business principle in a compact callout below the introductory copy and
above the catalog actions. Move the expanded brand-detail presentation below the
collection, keeping that content accessible rather than deleting it. Reduce the
four-card brand sequence to a short preview with an explicit expand action.

Do not show a full empty cart panel to a first-time visitor. For a nonempty cart,
show item count and View cart rather than duplicating the entire cart editor.
Keep `/#contact` working for existing links.

### 5.2 Product and accessory discovery

- Use one card per row on narrow phones; avoid squeezing complex cards into two.
- Keep name, price, media, and action hierarchy consistent across item types.
- Show a short benefit and the most decision-relevant specification when provided.
- Preserve multiple photos and videos on both product and accessory cards.
- Separate media controls from Details and Add to cart. Do not make the whole
  card clickable when it contains other interactive controls.
- After Add to cart, keep the browsing position, update the count, and announce
  a concise confirmation with View cart. The clicked button immediately shows a
  check icon and "Added" for 2.5 seconds only after the cart write succeeds.
  A failed add shows "Not added"; do not report a capped/no-change operation as
  successful. Apply this to product/accessory cards, detail actions and the
  mobile sticky action. Do not force a redirect.
- Wrap long unbroken item names in cart notices and let cart grid children shrink
  within the viewport; moving a long-named item to the top must not make mobile
  feedback, cart totals or Clear cart unreachable.
- Preserve the existing maximum of 10 per item and visibly explain the limit.
- Use horizontal `[-] quantity [+]` controls, with labeled 44 px targets.
- Equipment and accessory listing cards share aligned media, category, name, price,
  expansion and purchase-control rows. Cards in each desktop/
  tablet row stay equal-height, including when one card is expanded; mobile
  single-column cards keep their natural content height.
- Current customer/admin wording is Equipment and Accessories. All products is
  first in header/home navigation and is the default combined catalog. The three
  choices filter one home listing through `catalog=equipment|accessories`, while
  absence/unknown values choose All. All shows saved equipment order followed by
  saved accessory order; admin catalogs and their ordering remain separate.
  Preserve legacy product/accessory URLs, anchors and stored identifiers.
- Admin catalogs share a toolbar ordered Catalog, Arrange listing order, New.
  Arrange/Done stays between the heading and New, including wrapped mobile
  layouts; use at least 48px button height. Click "Arrange listing order" to
  show keyboard/touch-friendly up/down buttons directly on each existing listing
  card, retaining its image, name, prices and status. Do not show a duplicate list
  or position selector. Cards visibly move in the list after each successful
  save; retain focus on the moved card and show its position. "Done arranging"
  returns to normal card selection/editing. Each move saves only the ordered ID
  sequence, preserving all record fields and current unsaved editor values.
  New items append; a stale order or changed item set requires refresh/retry.
  Draft/missing-market items retain their saved positions but are filtered from
  customer lists. This explicitly replaces Featured-first sorting.
- Daily email settings use a checkbox and a full-width recipient textarea with
  save/reload feedback. Preserve unsaved edits across tabs and on failures, block
  repeat saves while pending, and fit the form/errors at 320px without horizontal
  scrolling. Show the non-production no-send restriction independently of the
  saved enabled preference. Keep credentials out of the interface.
- Shared admin error notices scroll into view instantly before receiving focus;
  do not let inherited smooth scrolling keep moving retry/save controls after
  the error has been announced. Native file inputs occupy their own full-width
  upload row so WebKit does not compress their picker button out of the form.
- The approved 2026-09-29 compact design **supersedes** the 2026-09-27 visible
  details, 21rem desktop preview and automatically expanded mobile requirements.
  Initially show only gallery, category, full name, current price/optional MSRP,
  Show more and purchase/navigation actions. Place package contents, descriptions,
  features, compatibility, specifications and quantity controls inside the
  initially hidden panel, on every viewport.
- Show more/less remains keyboard-operable on desktop **and mobile**. Keep the
  decorative "...", regular-weight italic underlined label, subtle neutral
  background, light outline and >=48px hit area. The control precedes the panel
  so collapse remains reachable. `aria-expanded`/`aria-controls` reflect the
  actual hidden panel. Expanded content has no clipping/fade/height cap; resizing
  preserves the user's choice rather than automatically revealing mobile details.
- Both card kinds have the same Add to cart and desktop Details actions.
  Below 1024px omit the separate Details button, retaining Show more and Add.
  Item title links remain usable; both types have matching full detail pages,
  including `/accessories/[id]`. Blank fields stay omitted, media controls and
  existing equipment URLs remain available. Full pages retain readable details.
- Optional CAD/USD MSRP is edited separately from Price. Show labeled struck
  MSRP only when above the selected selling price, never manufacture a discount
  for equal/lower/unset values. Cart/quotes continue using selling price only.
  Main-list filtering, not search or new taxonomy, is in scope for this revision.

For accessories, retain inline overflow expansion because no separate accessory
detail route currently exists. Do not introduce a new route solely for this phase.
Long technical values should stack under labels instead of compressing into narrow
left/right columns.

### 5.3 Media: useful on touch, inexpensive on mobile data

Future customer support: the separate
[AI/human support architecture](customer-service-ai-architecture.md#8-customer-ux)
defines a desktop panel/mobile sheet, focus ownership, and collision rules for
chat alongside menus, enlarged media and sticky cart/quote actions. It is a draft,
not a change to the current storefront.

Retain the shared gallery instead of creating separate product/accessory versions.

- Present a visible position indicator such as `2 / 5`, thumbnails, and a clear
  Video badge or play affordance.
- Add horizontal swipe as an enhancement, not the only navigation mechanism.
  Preserve ordinary vertical page scrolling and browser zoom.
- Enlarge images in a dialog with generous Close/Previous/Next targets.
- Retain button-based zoom; do not disable native browser pinch zoom.
- Start videos only after user intent; retain inline playback and native controls.
- Pause playback when changing slides or closing a dialog. Avoid simultaneous
  background and enlarged-player audio.
- Prefer posters on listing cards; avoid preloading every offscreen video.
- Preserve thumbnail position and selected media when returning from enlargement.
- Announce media changes without repeatedly interrupting assistive technology.
- Provide a clear error message and recovery action for failed image/video loads.
- If spoken demonstrations convey essential information, provide captions or a
  text equivalent; do not rely on audio alone.

Gallery states to design: zero media, one photo, mixed media, video-only, 12 items,
portrait photo, long loading time, failed download, unsupported playback, and
orientation change while enlarged.

### 5.4 Product detail: confidence before a long scroll

Mobile order:

1. Back to collection and compact header.
2. Product name, category, price, and stock information when supplied.
3. Gallery.
4. Short benefit statement and primary action.
5. Dimensions/material highlights and fit limitations.
6. Expandable Specifications, Included items, Features, Warranty, and Overview.
7. Secondary Request quote action.

Keep critical compatibility warnings visible. Do not show empty sections or
invent stock availability when the catalog does not specify it.
Use the contextual action bar when the inline Add to cart is offscreen.
Request quote must preserve product context in the inquiry form.

### 5.5 Cart: a selection for inquiry, not checkout

- Explain: **Review your selection and request a quote. No payment is collected here.**
- Item rows show name, unit price, quantity, line amount, and Remove.
- A small cover thumbnail can improve recognition, but requires extending the
  stored cart shape or fetching catalog media. Existing saved carts must still work
  without that field; this is a later enhancement, not a prerequisite.
- Use clear quantity boundaries and an explicit removal affordance. If decrement
  at one still removes the item, offer an accessible Undo.
- Confirm Clear cart; do not make it visually compete with Request a quote.
- Keep the quote action reachable without scrolling through every item.
- Preserve selections and quantities when navigating back from the quote form.
- Show an empty state with Equipment and Accessories links to the corresponding
  filtered catalog views.

**Currency design constraint:** CAD and USD remain stored separately, while the
requested public price display is `$` only. Never add CAD and USD amounts together
or imply an exchange rate. Two unlabeled currency totals would be confusing.

Recommended mixed-currency presentation: show line amounts, item count, and
**Final total confirmed in your quote**, without a combined numeric total. A
single-currency selection can display its numeric estimate. This changes current
summary behavior and requires product approval before implementation. An
alternative is explicitly labeled currency groups, but that conflicts with the
requested symbol-only public display and also needs approval.

### 5.6 Quote form: finish with one hand

Keep the existing contact anchor and API for the initial iteration.

- Prefill a numbered item list, with quantity, package contents when known, and
  currency-labelled unit price on separate lines. Separate items and the final
  pricing/delivery request with blank lines; never invent prices or combine
  currencies. Product-only requests retain the product name without inventing
  a price or quantity. The editable message area grows from 8 to at most 18 rows;
  edits and line breaks survive submission errors and saved inquiry JSON.
- Quote navigation must land the form just below the actual sticky header on
  desktop and mobile, including after asynchronous catalog/banner/cart content.
  Give the targeted section enough viewport-height space for tall desktop
  windows to reach that position. Quote links disable the router's competing
  automatic scroll; align before paint as initial homepage sections render, then
  stop once initial data settles. Do not paint an early landing followed by a
  visible correction. Cancel further adjustment when the user starts scrolling,
  touching, or typing.
  Preserve quote context, repeated same-page navigation, and reduced-motion safety
  without introducing timed scroll loops or forcing keyboard focus.
- Persistent labels: Name, Email, Phone (optional), Company / Studio (optional),
  and Message.
- Keep Name, Email, and Message required unless the business approves a change.
- Use appropriate input types and autocomplete hints.
- Show a concise selection summary above the fields for cart/product inquiries;
  prefill the existing message without overwriting user edits.
- Do not require customers to retype the model or quantities already selected.
- Use inline field errors and a focusable error summary where needed.
- Preserve values after validation or network failure; do not clear the cart.
- Provide submitting, success, and failure states. Prevent repeated taps while
  the request is pending, but allow an explicit retry after failure.
- Submission success means the inquiry was saved, not that payment or delivery
  is confirmed. Do not claim email arrived or promise an unapproved response time.
- Do not imply that disabling a button provides server-side exactly-once delivery.
  If stronger retry guarantees are needed, design API idempotency separately.
- Keep a clearly visible submit button in the form rather than a keyboard-obscured
  sticky footer.

For long cart-to-inquiry journeys, consider a dedicated quote route later. It is
not required for the first release and must preserve existing inbound links.

### 5.7 Mobile admin: list -> edit -> save

Keep desktop split-pane editing. On phones, use distinct list and edit states:

1. Catalog list with Products / Accessories / Home banner navigation that can wrap.
2. Selecting an item opens its editor at the top, with Back to catalog.
3. Group fields into Basics, Media, Specifications, Compatibility, and Publishing.
4. Keep required fields discoverable; expand and focus a section containing an error.
5. Offer a safe-area-aware Save action with Unsaved changes / Saving / Saved / Failed.
6. Warn before abandoning unsaved edits; keep the draft when upload or save fails.

Media editing should support library selection and optional camera capture,
without forcing camera-only input. Retain batch upload and the combined 12-item
limit, 8 MiB image limit, and 50 MiB video limit.

- Show per-file progress and processing status; do not fake a percentage for video
  conversion when the API provides none.
- Surface partial batch failures and allow retrying failed files only.
- Explain that uploaded files are not attached to the item until it is saved.
- Keep move-earlier/move-later and main-photo buttons; drag-and-drop cannot be the
  only reordering method.
- Increase editor control hit areas; separate Delete from Save.
- Keep CAD as the new-item default, offer CAD/USD only, and retain an existing
  item's saved currency when editing.
- Do not promise resumable uploads or safe background conversion across a lost
  mobile connection without additional backend support.

## 6. Low-fidelity wireframes

Illustrative hierarchy only; not pixel-perfect specifications.

### Home

```text
+----------------------------------+
| STYL                 Cart 2 Menu |
+----------------------------------+
| Equipment for your training space|
| Short supporting value statement |
| [ Purposeful product image     ] |
| [ Equipment                    ] |
|                                  |
| Equipment       Browse accessories|
| [ Gallery                1 / 4 ] |
| Product name              $2,499 |
| One useful benefit               |
| [ Details ] [ Add to cart      ] |
| ...                              |
| Why STYL: concise proof          |
| 2 items selected    [View cart]  |
| Request a quote                  |
+----------------------------------+
```

### Product detail

```text
+----------------------------------+
| Back                 Cart 2 Menu |
| Product name                     |
| $2,499        Stock if provided  |
| [ Main image / video           ] |
| [ Thumbnail strip        1 / 4 ] |
| Key benefit                      |
| [ Add to cart ]  Request quote   |
| Dimensions and fit limitations   |
| Specifications                 v |
| What's included                v |
| Warranty                       v |
+----------------------------------+
| $2,499       [ Add to cart      ] |
|      device safe-area space      |
+----------------------------------+
```

The bottom action is shown only when its inline equivalent is out of view.
Prices above are illustrative, not proposed catalog changes.

### Cart and mobile admin

```text
Cart                         Admin
+------------------------+   +------------------------+
| Your selection (2)     |   | Back to catalog        |
| Item A          $...   |   | Edit product           |
| [-] 1 [+]      Remove  |   | Basics                 |
| Item B          $...   |   | Name / Price / Currency|
| [-] 1 [+]      Remove  |   | Photos & videos      v |
| Estimate / quote note |   | Specifications       v |
| No payment collected  |   | Compatibility        v |
+------------------------+   +------------------------+
| [ Request a quote ]    |   | Unsaved     [ Save ]   |
+------------------------+   +------------------------+
```

## 7. Accessibility, resilience, and performance

### Accessibility requirements

- Target WCAG 2.2 AA; use the stronger 44 px touch target as a product standard.
- Normal text contrast at least 4.5:1; large text at least 3:1. Validate muted text,
  focus indicators, control boundaries, and disabled-state comprehension.
- Semantic headings, persistent form labels, descriptive control names, and
  announced loading/error/cart updates.
- Full keyboard operation and visible focus; no sticky element obscures focus.
- Dialog focus management, Escape support, and focus restoration.
- Respect reduced motion; smooth scrolling must not be mandatory.
- No page-level horizontal overflow at 320 CSS px. Explicit thumbnail scrollers
  may scroll horizontally without forcing the entire page to do so.
- Support 200% text resizing and reflow testing at 400% zoom on desktop.
- Test with iOS VoiceOver and Android TalkBack, not automated checks alone.

### Slow or interrupted connections

- Reserve media dimensions to prevent layout jumps.
- Show skeletons for initially loading catalog content and explicit Retry for errors.
- Distinguish an empty catalog from a failed request.
- Do not clear form values after connection loss.
- Keep video poster/controls meaningful before the clip downloads.
- Cart-storage failures must be visible, not reported as a successful saved selection.
- Do not claim offline ordering or persistent offline admin drafts in this phase.

### Performance targets and proposed work

Mobile field targets at the 75th percentile, once sufficient data exists:

| Metric | Target |
| --- | --- |
| Largest Contentful Paint | <= 2.5 seconds |
| Interaction to Next Paint | <= 200 ms |
| Cumulative Layout Shift | <= 0.1 |

Measure a baseline before setting percentage-improvement claims. On this low-traffic
site, field samples may be insufficient; report that rather than treating a single
Lighthouse score as real-user evidence.

Proposed optimizations:

- Responsive image sizes and compressed derivatives instead of sending full upload
  resolution to thumbnails. Preserve originals; decide server derivatives versus
  framework optimization after measuring the small production server's capacity.
- Prioritize the actual above-the-fold image, not every gallery slide.
- Lazy-load offscreen images and defer offscreen video resources.
- Avoid downloading full videos until play; poster loading must not fetch the clip.
- Reduce unnecessary client work and expensive blur effects only where profiling
  demonstrates a problem.
- Test representative galleries with 12 media entries, not only the seed catalog.
- Avoid introducing a large carousel or animation dependency for simple controls.

## 8. Delivery plan and decision gates

| Phase | Scope | Exit criteria |
| --- | --- | --- |
| 0: Baseline and prototype | Responsive captures, phone tasks, content hierarchy, clickable mobile prototype. | Agree on navigation, quote semantics, and mixed-currency summary; record baseline. |
| 1: Mobile essentials | Shared header/menu, shorter home hierarchy, touch targets, labeled quote form, loading/error states. | Main journeys work at 320-430 px; no covered controls; desktop behavior preserved. |
| 2: Evaluation and conversion | Touch gallery enhancements, product-detail hierarchy, contextual actions, cart feedback, accessory details expansion. | Media, selection, and inquiry tasks pass phone usability checks. |
| 3: Mobile admin | List/edit states, grouped forms, save feedback, safe uploads/reordering. | Owner can edit and save on a phone without accidental loss. |
| 4: Measured optimization | Responsive media delivery and targeted rendering/network improvements. | Measured regression checks and performance targets, with field-data limitations disclosed. |

No code should be changed until the relevant design decisions are approved.
Use separate, reversible implementation changes per phase. A new feature-flag
system is not required for this small site; retain rollback capability and avoid
coupling UX releases to catalog-data migrations.

### Decisions for review

1. Approve the compact shared header/menu instead of permanent bottom navigation.
2. Approve moving extended brand content below shopping content, preserving access.
3. Approve contextual Add to cart / Request a quote actions without introducing checkout.
4. Resolve mixed-currency summary behavior while retaining symbol-only public prices.
5. Confirm that mobile admin follows the customer-facing improvements.
6. Approve any response-time, delivery, warranty, or trust copy before publishing it.

The recommended default is phases 1 and 2 first, with no new public routes.
Backend inquiry semantics, saved currency, quantity limits, and media limits stay
unchanged unless a separately approved requirement demands otherwise.

## 9. Validation and acceptance checklist

### Device matrix

- Real iPhone: current supported iOS Safari, portrait and landscape.
- Real Android: current supported Chrome, including a mid-range device.
- Desktop emulation: 320/360/390/430/768/1024/1440 CSS px.
- Desktop Chrome and Safari regression checks.
- Screen reader, keyboard-only, reduced motion, zoom, slow network, and offline failure.

Viewport resizing alone is insufficient for safe areas, browser chrome, virtual
keyboards, native playback, and touch gestures.

### Required scenarios

| Scenario | Acceptance |
| --- | --- |
| Header/menu at 320 px | Logo, cart, and menu remain usable; no page overflow; all destinations reachable. |
| First arrival at 390 x 844 | All products / Equipment / Accessories actions visible on one row with >=48px height; first item identity reachable within one viewport-height scroll. |
| Long product names and prices | Wrap without hiding actions or essential information. |
| Gallery with 0/1/12 media | Correct states, useful position feedback, no broken navigation. |
| Swipe while browsing | Horizontal change works; vertical scrolling and browser zoom remain available. |
| Video and enlargement | No unexpected autoplay or continued hidden audio; native playback works on real phones. |
| Add/update/remove | Count and quantities remain correct; maximum 10 preserved; confirmation accessible. |
| Returning to collection | Back navigation retains a useful browsing position. |
| Mixed CAD/USD selection | No combined or misleading unlabeled total; approved quote presentation used. |
| Quote with keyboard open | Labels, errors, and submission controls remain reachable; data survives failure. |
| Repeated submit tap | One active client submission; clear pending state, explicit retry after failure. |
| Admin unsaved changes | Leaving prompts appropriately; failed save retains edits and exposes errors. |
| Partial upload failure | Successful files retained in the draft; failed files identified and retryable. |
| Sticky controls and dialogs | Last content and focused controls never covered; safe-area and modal behavior correct. |
| Legacy data | Image-only items and carts lacking optional thumbnail fields still function. |
| Desktop regression | Navigation, catalog grids, detail layout, and admin split editing remain usable. |

### Measurement after release

The original discovery-to-inquiry funnel and device-segmented conversion proposal
is **superseded** by the owner's 2026-09-28
[anonymous aggregate-only contract](traffic-analytics-requirements.md). Compare
page views and separate detail/media/cart/quote action totals, not the progress
of linked visitors through stages. Device/browser/source/campaign/country page-view
breakdowns stay independent; they cannot be joined to item or inquiry histories.
Saved inquiries remain authoritative, separate business counts. No visitors,
sessions, individual journeys, per-session conversions/attribution or medians.

After enabled aggregate-only configuration, eligible pages measure automatically
with bounded in-memory best-effort delivery and no browser/session/event/page-view
IDs or raw-event storage. Persist server-hour totals and independent coarse
dimensions for 13 calendar months, not raw request times, IPs, full URLs/query
strings, referrer hosts, form/contact text or combined fingerprints.

Desktop and mobile storefronts have **no consent panel, banner/modal or technical
analytics status**. The ordinary footer **Privacy** link opens `/privacy`, whose
information and **Turn off usage measurement** / **Allow aggregate measurement**
buttons use only a boolean opt-out. Preserve prior explicit declines and
DNT/GPC/admin/internal/bot exclusions; unreadable privacy storage fails closed.
Do not obstruct navigation, cart controls, inquiry actions or keyboard focus.

Local implementation/final verification is ongoing, not a production rollout.
The notice and served-market privacy/legal review remain release gates; this
design does not assert universal exemption from consent rules. Infrastructure
logs and business contact records have separate personal-data obligations.
City/postal remains deferred. Analytics must never become a dependency of basic
mobile/desktop shopping; see [operations](traffic-analytics-operations.md).

### Review deliverables before implementation

- Approved content order and the decisions in section 8.
- Mobile wireframes for home, accessory list, product detail, cart, inquiry, and admin.
- Interaction prototype covering menu, gallery, sticky actions, and keyboard/form states.
- Baseline captures and a short usability report with observed problems.
- Implementation tickets tied to the acceptance scenarios above.

This proposal is complete as a design document. It does not indicate that the
proposed screens, accessibility targets, or performance improvements are already
implemented or verified.
