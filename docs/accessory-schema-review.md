# STYL accessory schema proposal: evaluation against the current implementation

Status: Draft review with agreed naming/SKU direction; not implementation approval

Reviewed: 2026-09-25

Implementation baseline: `c412178` on `main`

Proposal: `STYL_Schema.docx`, titled **STYL Accessory + Attribute Schema v1**,
provided from the user's Downloads folder.

Follow-on target design: [Product catalog and admin data schema](catalog-and-admin-schema-design.md).
It incorporates the agreed naming/SKU direction and the subsequent requirement
for admin-configurable business options. This review retains the rationale and
comparison with the original attachment.

## Agreed naming and SKU direction

Following discussion on 2026-09-25, use **Product** as the umbrella term for every
sellable catalog item, with two main types:

| Type | Meaning | Examples |
| --- | --- | --- |
| Equipment | Primary training equipment or the foundation of a setup | Multi trainers, racks, benches, rowing machines |
| Attachments | Items designed to connect to equipment and provide or extend a training function | J-cups, dip attachments, cable handles, bench attachments |

Customer navigation: **Equipment / Attachments**. Admin umbrella: **Product
catalog**, with categories under each type. Being sold separately is different
from being usable independently; independence is not a strict classification test.
Compatibility remains a separate evidence-backed relationship, not something
implied by an item's type or category.

Reserve **Accessories** for a future supporting-items group only if needed for
items such as mats or maintenance supplies that are not attachments. Do not
blindly relabel every existing accessory record: review benches, storage items,
and other borderline entries individually.

Every sellable item should have a dedicated **SKU**, separate from optional
**Model**, internal record ID, and URL slug:

- Unique across the entire catalog, not merely within Equipment or Attachments.
- Stored as text, preserving letters and leading zeros.
- Stable when names, categories, or classifications change.
- Identifies the sellable unit: a pair has its own SKU; an individually sold
  component would have a different SKU if offered separately.
- Existing entries require deliberate assignment/backfill. Do not assume that
  the combined legacy `modelSku` text is already a valid, unique SKU.

A neutral sequence such as `STYL-000101` is the recommended example, not a final
allocation specification. Automatic versus manual assignment, duplicate handling,
and migration rules still need to be specified before implementation.

This decision supersedes the earlier recommendation to merely add an optional
combined Model / SKU field to accessories. References below to the current
Product/Accessory split describe the existing implementation, not the target
customer terminology. UI naming can evolve without immediately renaming API
routes, storage files, or breaking existing links and saved carts.

## 1. Executive recommendation

**Adopt the proposal's information architecture, but do not implement the entire
schema as one replacement project.**

The strongest idea is that an accessory is an independently sellable item with
its own content, sale-unit meaning, technical specifications, compatibility,
media, and source evidence. That matches STYL's direction and addresses real
catalog-mapping problems.

However, the proposal partly describes gaps that the latest code has already
closed. Descriptions, features, selling units, package quantity, included contents,
finish/colour, category selection, and private provenance now exist. Rebuilding
them would add migration risk without a corresponding customer benefit.

The genuinely new opportunities are:

1. A small, controlled technical-attribute system with evidence and review status.
2. Dedicated catalog-wide SKU, separate optional Model, and optional stock-status
   and warranty parity.
3. Better media metadata, particularly meaningful alternative text and an
   independently selected cover.
4. More precise source/review information where the migration workflow needs it.

The parts that need revision are:

- Do not equate 75 x 75 mm with 3 x 3 inches or infer compatibility from dimensions.
- Do not create multiple editable sources for the same specification.
- Do not make unknown selling units or other unknown facts mandatory by inventing
  defaults.
- Do not put a full attribute-definition engine, filtering engine, comparison
  engine, and normalized-unit system into the first increment.
- Do not rename established API keys or replace working storage just to match
  the proposal's naming.
- Do not expose internal evidence because a parent attribute or media record is
  marked public.

### Existing decisions remain in force

This review does **not** reopen draft/publish work or CAD/USD presentation changes.
Those remain excluded/on hold as previously requested.

Prices still accept up to two decimal places and display two decimal places.
Desktop and mobile remain equally important. The site remains a lightweight
catalog, selection cart, and inquiry flow, not a payment or inventory platform.

## 2. Evidence and interpretation

The comparison uses these current sources:

- [API models, persistence mapping, category handling, and public responses](../backend/app/main.py)
- [Video conversion and delivery](../backend/app/media.py)
- [Accessory frontend contract](../frontend/src/lib/accessories.ts)
- [Shared catalog fields and media helpers](../frontend/src/lib/catalogDetails.ts)
- [Accessory admin editor](../frontend/src/app/admin/AccessoryManager.tsx)
- [Accessory customer presentation](../frontend/src/app/accessories/page.tsx)
- [Shared media editor](../frontend/src/components/PhotoEditor.tsx)
- [Shared gallery](../frontend/src/components/PhotoGallery.tsx)
- [Cart and selling-unit behavior](../frontend/src/lib/cart.ts)
- [Original product/design goals](STYL%20Portal%20Design.md)
- [Responsive UX design and approved-scope update](mobile-ux-design.md)
- [Current behavior documentation](../README.md)

The responsive design document contains both an implementation update and older
proposal sections. Its historical problem table is not treated as evidence that
those problems still exist. Current source takes precedence for implementation
status.

This is a source-based design assessment, not a fresh production audit. It does
not assert that `c412178` is deployed, or that supplier claims in the Word example
are independently verified. No application changes or new runtime tests are part
of this documentation task.

Verdicts used below:

- **Keep:** already implemented and appropriate.
- **Adopt:** useful addition with a clear benefit.
- **Adapt:** good intention, but the proposed representation or scope needs change.
- **Defer:** reasonable later, without enough immediate benefit.
- **Do not adopt as written:** creates ambiguity, duplication, or unjustified claims.
- **On hold / excluded:** governed by an existing user decision.

## 3. Current schema and design in brief

### What exists today

Accessories have integer IDs and a category string selected from an authenticated
canonical category list. They support name, price, currency, dimensions, material,
weight, short description, full description, public-use text, features, included
contents, selling unit, package quantity, finish/colour, media, compatibility, and
private provenance.

Important implementation details:

- API keys are predominantly camelCase. The public-use field is still named
  `notes`, but the editor clearly labels it **Public use description**.
- `sellingUnit` accepts an unspecified value, Each, Pair, or Set. Quantity counts
  sale units; `packageQuantity` describes individual pieces within one sale unit.
- Price validation uses `Decimal`; responses and JSON catalog files currently
  store numeric values through a float conversion, with a representability check.
  Cart calculations use integer cents. This is not a SQL decimal column.
- New accessory specification fields preserve existing values when omitted from
  an update; explicit empty values clear them.
- Category matching normalizes case and whitespace, incorporates existing
  categories, and rejects newly invented labels. It does not yet have category IDs
  or merge semantic aliases such as Bench and Benches.
- `photos` is an ordered list of image/video URL strings. `image` is a derived
  image cover or generated poster, not a separately editable media record.
- The first gallery item and the derived cover can differ. The editor explains
  this. Selecting a photo as thumbnail currently also moves it to the front.
- Private source data lives under `provenance`. Public responses remove that key;
  authenticated admin endpoints retain it.
- Accessories use expandable detail content rather than a dedicated detail route.
- Product and accessory models share several foundations but are not identical.
  Accessories do not currently have product-style Model / SKU, stock status,
  warranty, slug, or Featured fields.

### What this means for the proposal

The proposal is strongest as a **next-stage model refinement**, not as a diagnosis
that the current persistence or gallery system needs replacing.

Its final observation about information being lost during mapping, rather than
save/reload, is useful: the next work should focus on preserving information that
still lacks a suitable field, not rebuilding already-working save operations.

## 4. Field-by-field assessment

### 4.1 Identity, category, and merchandising

| Proposed field | Current equivalent | Verdict and reason |
| --- | --- | --- |
| `id` as UUID/int, internal only | Integer `id`, also used by public responses and the cart | **Keep integer IDs.** Do not migrate IDs or hide them simply because they are internal identifiers. Public record IDs are not secrets; authorization must protect private operations. Changing them risks saved-cart references. |
| Required, editable `slug` | Products have slugs; accessories do not | **Defer.** A stable shareable accessory page would justify this, but current approved UX uses inline expansion. If introduced, define uniqueness, reserved names, and redirects when edited; do not silently break shared links. |
| `type = accessory` | Separate accessory endpoints and record types | **Defer as a persisted field.** It is currently redundant and could disagree with the endpoint. A unified catalog API could derive it later. |
| `category_id` relation | Canonical string categories | **Adapt.** Stable category IDs are a good long-term direction for rename/merge/filtering. Current dropdown validation already prevents most new spelling fragmentation. Approve taxonomy and alias mapping before migrating existing values. |
| `brand` | No dedicated field | **Conditional adopt.** Useful if the catalog includes multiple brands. If every item is genuinely STYL, site-level presentation may suffice. Do not assign STYL to imported items without confirmation. |
| `condition` New / Used | No dedicated field | **Conditional adopt.** Important if physical item condition varies. A Marketplace source alone does not establish Used condition. Keep unspecified values allowed; define whether listings represent unique used items or repeatable SKUs before expanding commerce behavior. |
| `model_sku` | Product `modelSku`; absent for accessories | **Adapt per the agreed direction.** Introduce dedicated catalog-wide SKU and separate optional Model instead of extending the combined field. Preserve legacy values during a reviewed backfill; enforce uniqueness across all sellable items. |
| `publication_status`, default Draft | Product-only publication behavior; no accessory equivalent | **Excluded.** Record the proposal, but do not change defaults, add accessory publication, or couple other schema work to it in this batch. |
| `featured` | Products use Featured to show first in the home collection | **Defer for accessories.** It has no defined accessory placement today. If introduced, specify which collection it affects and preserve the approved product meaning; it is not a publication switch. |
| `sort_order` | List order plus product Featured priority | **Defer.** Add only when editors need manual merchandising. Define ordering scope, ties, and interaction with Featured. Do not add both controls without a predictable rule. |

### 4.2 Content, commerce, and physical fields

| Proposed field | Current equivalent | Verdict and reason |
| --- | --- | --- |
| `short_description` | `shortDescription` | **Keep.** Already stored, edited, and shown on accessory cards. No second field or migration needed. |
| `full_description` | `description` | **Keep.** Already separate from use text and rendered in expanded details. |
| `public_use_description` | `notes`, labeled Public use description | **Keep the separation; adapt the name only if necessary.** The UI meaning is now clear. A future API rename needs a compatibility alias and migration, not two competing text fields. |
| `features` | `features: string[]` | **Keep.** Suitable for selling points. Do not turn the list into a substitute for structured technical claims. |
| `retail_price: decimal` | `price`, exact-cent input validation | **Keep behavior and key.** No reason to rename `price` or introduce another price source. If storage later changes, a decimal or minor-unit representation is appropriate, but it must preserve existing API behavior. |
| Explicit public `currency` | CAD/USD stored; public prices use `$` | **On hold.** Preserve current support, defaults, formatting, and grouping. The attachment is not approval to add public currency labels. |
| `compare_at_price` | Absent | **Defer.** Requires trustworthy reference-price data and promotion rules; it is not necessary to preserve source specifications and was already outside the agreed v1 batch. |
| Required `selling_unit`, including Kit | Optional/unspecified `sellingUnit`: Each / Pair / Set | **Adapt.** Unit clarity is important, but requiring unknown data contradicts the proposal's no-guessing principle. Keep unspecified values valid. Add Kit only for an actual catalog need, then update labels, cart, inquiry, validation, and tests together. |
| `package_quantity: number` | Positive integer or null `packageQuantity` | **Keep the stricter existing type.** Pieces are a count, not a fractional measurement. A confirmed pair can contain two pieces; a heterogeneous kit may need contents text rather than an invented total. |
| `whats_included` | `included` | **Keep.** Already supports descriptive package contents. Do not duplicate it under an attribute unless it is a read-only projection. |
| `stock_status` | Product field only | **Adopt optional accessory parity when operationally maintained.** Show supplied availability without inventing In stock. This is descriptive stock status, not quantity tracking or an inventory reservation system. |
| `dimensions`, structured/text | `dimensions: string` | **Adapt incrementally.** Keep source text, units, qualifiers, and orientation. Typed dimensions help filtering later, but parsing free text automatically would risk changing meaning. |
| Structured `weight` | Accessory `weight: string` | **Adapt incrementally.** Record whether a weight is per piece, sale unit, or package, and net versus shipping. A bare `{value, unit}` is insufficient for pairs and kits. Keep legacy source text during transition. |
| `material` | `material` | **Keep.** Free text is adequate for current presentation. |
| `finish_colour` | `colourOptions`, labeled Colour / options | **Keep storage; improve terminology if helpful.** A clearer accessory label is possible without schema replacement. Material, coating, and colour should not become conflicting duplicates. |
| `attributes` | No generic technical-attribute list | **Adopt a limited version.** This is a real remaining gap for pin length, usable peg length, connection type, and similar item-specific facts. See section 5. |
| `warranty` | Product field only | **Adopt optional accessory parity.** Store only supplied terms; do not inherit or invent a promise just because an item uses the STYL brand. |

### 4.3 Compatibility and private source fields

| Proposed field | Current equivalent | Verdict and reason |
| --- | --- | --- |
| `upright_size`, `hole_diameter`, `hole_spacing` | `compatibility.uprightSize`, `holeDiameter`, `holeSpacing` | **Keep separate compatibility ownership.** The fields already exist. Do not introduce an independently editable duplicate in Attributes. |
| `confirmed_compatible_models` | `compatibility.models` text | **Keep text initially.** Relations become useful only when the catalog maintains reliable model identifiers, including external brands and revisions. Confirmation requires evidence, not matching numbers. |
| `compatibility_limitations` | `compatibility.limitations` | **Keep.** Continue making important exclusions visible, including outside expandable secondary specifications. |
| `internal_notes` | `provenance.notes` supports migration ambiguity | **Adapt.** General operational notes and source-specific notes may differ, but two vague note boxes create duplication. Define their ownership before adding a second field. |
| `source_type` enum | `provenance.sourceType` text | **Adapt to controlled suggestions or a small vocabulary.** Preserve existing values. Measured describes a verification method, while Supplier/Marketplace describes an information origin; avoid treating those as always mutually exclusive. |
| `source_url` | `provenance.marketplaceUrl`, UI says Marketplace / source URL | **Keep current storage for now.** It already accepts HTTP/HTTPS source URLs. Generalize the key later only with a backward-compatible alias. |
| `source_listing_id` | `provenance.listingId` | **Keep.** Optional because non-marketplace sources may not have listing IDs. |
| `source_captured_at` datetime | `provenance.capturedDate`, date-only | **Adapt if time-level audit matters.** New captures can record timezone-aware timestamps. Do not fabricate an exact time or timezone for legacy date-only evidence. |
| `source_notes` | `provenance.notes` | **Keep.** Already private and persisted. Distinguish source ambiguity from public copy. |

## 5. Attribute model: valuable direction, too broad as a first release

### 5.1 The problem it should solve

A fixed accessory form cannot anticipate every technical characteristic.
Adding a database column for every pin, roller, sleeve, or peg dimension is not
sustainable. STYL currently uses JSON files, not a relational catalog database,
but uncontrolled growth of fixed API fields would create the same design problem.

A small attributes list can preserve supported facts without distorting
Descriptions, Features, or Public use description.

### 5.2 Separate definitions from item values

The proposal puts global attribute rules and per-item values in one row. That is
convenient for a sketch, but weak for reuse and future comparison.

Recommended conceptual separation:

- **Definition:** stable key, display label, allowed type/unit family, group,
  and whether the application supports filtering/comparison for that definition.
- **Item value:** reference to the definition, value, original/source expression,
  unit where relevant, source reference, verification state, and private notes.

These can initially be a small registry plus embedded JSON values. They do not
require a database migration or an arbitrary admin schema builder.

| Proposed attribute fields | Recommendation |
| --- | --- |
| `id`, `key`, `label` | Use a stable definition key; avoid separately editable keys/labels on every item. Add a value-record ID only if there is a concrete editing/reference requirement. |
| `value`, `value_type` | Start with a limited, validated type set. If boolean/range are supported, the value contract must actually represent them, not ambiguously treat everything as text or number. |
| `unit` | Restrict numeric definitions to compatible units; retain original units. Do not allow kg on a length definition or rely on free-text unit spellings for comparison. |
| `group`, `display_order` | Use controlled groups and deterministic order. An array order can satisfy initial display needs; a second editable order field is unnecessary unless independently needed. |
| `is_public` | Apply on the server. A public value does not make its notes, evidence URLs, or reviewer data public. |
| `is_filterable`, `is_comparable` | **Defer runtime features.** These belong to curated definitions, not arbitrary per-item toggles. A flag alone does not deliver correct filtering, normalization, or comparable semantics. |
| `source` | Prefer a reference to a source record when a technical claim came from a different source than the overall item. A label alone is not traceable evidence. |
| `verification_status` | **Adopt with a defined workflow.** State what Source stated, Needs review, Unknown, and Verified mean. Importing/copying data must not automatically mark it Verified. |
| `notes` | Internal only. Keep source conflicts and reviewer remarks out of the public attribute payload. |
| `min_value`, `max_value` | Add only for actual range attributes; require valid unit/type, `min <= max`, and defined inclusive/exclusive semantics where relevant. Avoid conflicting scalar and range values on the same record. |
| `normalized_value` | **Defer until filtering requires it.** Derive it using a versioned conversion rule; never make it a second manually editable truth. Preserve the original measurement and precision. |

### 5.3 Verification needs more than a status word

Recommended meanings:

- **Unknown:** not supplied or not established; no invented value.
- **Source stated:** accurately copied from an identified source, not independently
  verified.
- **Needs review:** conflict, ambiguity, unclear unit, or uncertain mapping.
- **Verified:** checked by an identified reviewer using recorded evidence/method
  appropriate to the claim.

If Verified is used, retain who verified it, when, and against what evidence.
Changing the value, unit, or evidence should invalidate or reopen verification.
Physical measurement, supplier assertion, and a load-test certification are
different forms of evidence; do not present them as equivalent assurance.

Do not show every unverified internal import value to customers simply because it
has a label. Establish claim-level public-display rules separately from the
excluded item publication workflow. Load-related and fit-related claims merit
stricter review than cosmetic descriptions.

### 5.4 Attribute groups: avoid overlapping sources of truth

The suggested groups are a good classification reference, but not all should
become separate editable data immediately.

| Group | Assessment |
| --- | --- |
| Dimensions / Weight | Useful, but choose ownership relative to existing dimensions/weight fields. Start with legacy summaries plus reviewed technical extensions, not duplicate editable totals. |
| Rack interface / Compatibility | Installation-related facts belong to Compatibility or a shared underlying definition projected there. Do not store two competing upright/hole-size values. |
| Mounting | Good early attribute candidates: pin length, mounting-hole size, and similar source-backed measurements. |
| Construction | Keep material/finish in their existing fixed fields; add genuinely new details such as source-stated steel thickness. |
| Barbell interface / Cable interface | Good candidates where the catalog actually supplies them. Preserve qualifiers and fitting context. |
| Load-related | Optional only. Store the rating's source, units, conditions, and whether it applies to one item, a pair, or the system. A bare capacity number is not enough. |
| Adjustment / Storage | Good candidates for verified position counts, adjustment ranges, and usable peg length. |
| Package | Selling unit, piece count, and included contents already have fixed fields. Do not independently re-enter them here. |
| Miscellaneous | Keep as a reviewed exception, not a new free-form notes bucket that recreates the original mapping problem. |

## 6. Compatibility: agree with the principle, correct the example

The proposal correctly warns against inventing brand/model compatibility from
similar dimensions. That should be retained.

However, both its compatibility section and J-Cups example use:

`75 x 75 mm / 3 x 3 in`

**These are not exact equivalent measurements.** One inch is exactly 25.4 mm, so
3 inches is 76.2 mm, not 75 mm. Products may be marketed with nominal labels, but
a nominal description does not establish tolerance, clearance, pin fit, or
compatibility with both systems.

Recommended handling:

1. Preserve the source's original claim verbatim in private evidence.
2. Do not silently rewrite 75 mm as 3 inches, or vice versa.
3. Record the source-stated interface and the uncertainty separately.
4. Mark ambiguous dual-system claims Needs review until confirmed.
5. Do not populate confirmed model names without actual evidence.
6. Keep important limitations visible in customer-facing fit information.

The J-Cups example's pair count, material, protective surfaces, and price are
illustrative proposal data, not verified STYL inventory facts. Use them as a
mapping exercise, not a seed catalog update. The example's publication and
explicit CAD presentation remain outside this review's actionable scope.

## 7. Media model: evolve the working gallery, do not replace it wholesale

The proposed `media[]` model is a sound longer-term direction. STYL already has a
unified ordered image/video gallery, just under the historical `photos` key.
It does not use fixed `photo1` / `photo2` columns.

### Useful additions

| Proposed field | Recommendation and reason |
| --- | --- |
| `id` | Useful stable identity for metadata, covers, and shared references; URLs alone are fragile identities. |
| `type` | Useful explicit image/video discriminator; current type inference uses the URL extension. |
| `url` | Keep the stored/delivered resource URL; distinguish uploads from externally hosted resources. |
| `position` | Array order is enough initially. If persisted separately, enforce deterministic ordering and avoid two competing orders. |
| `is_cover` | Useful independence from gallery-first media. Prefer one parent `coverMediaId` or enforce exactly one selected image cover. Define video-only poster fallback and cover-removal behavior. |
| `alt_text` | High-value addition. Current image descriptions are primarily generated from item name and position. Allow meaningful image-specific text without keyword stuffing or copying filenames. |
| `original_filename` | Useful for admin traceability, not normally public. It may contain personal or operational information. Original filename does not imply original file retention. |
| `mime_type`, `file_size`, `width`, `height`, `duration` | Useful server-derived facts about the delivered asset. Do not trust client-supplied metadata. Clarify bytes, pixels, and seconds, and distinguish source from processed values. |
| `source_type`, `source_url` | Useful optional internal provenance, with explicit public-response filtering. External origin URLs need not be exposed to shoppers. |
| `created_at` | Useful server-generated timestamp with timezone. Legacy unknown upload times should remain unknown unless recoverable from reliable evidence. |
| `processing_status` | **Do not adopt the proposed enum as written.** Original / processed / derivative describe asset roles, not a complete processing lifecycle. Separate role from states such as processing / ready / failed only if the application exposes such a lifecycle. |

Current uploaded videos are synchronously converted to H.264/AAC MP4, scaled to a
maximum dimension of 1280 px, and given a JPEG poster. Temporary originals are
discarded. The upload response is returned after processing; URLs added directly
are not converted.

Do not imply that the proposed metadata enables resumable upload, an asynchronous
processing queue, or recovery of discarded originals. Those are separate features.

### Safe transition

- Initially read both legacy `photos: string[]` and new media records.
- Establish one authoritative new representation and derive compatibility fields;
  do not let two editors independently modify `photos` and `media`.
- Preserve image-only records, video order, current uploaded URLs, and poster use.
- Carry deletion/reference protection across products, accessories, and the hero.
- Keep the current 12 combined media, 8 MiB image, and 50 MiB video limits unless
  separately approved.
- Backfill metadata only from available files/evidence; do not fabricate names,
  source URLs, or upload timestamps.

## 8. Relationship diagram and privacy boundaries

The proposal's arrow sequence:

`Accessory -> Category -> Features[] -> Attributes[] -> Media[] -> Compatibility -> Source`

is understandable as a list of concerns, but **should not be implemented as a
literal ownership chain**. Category does not own an accessory's features, and a
feature should not be the parent of media.

Better conceptual model:

```text
Sellable item (product or accessory)
  |-- identity / commerce / content
  |-- category reference
  |-- features[]
  |-- technical attribute values[] -> controlled definitions
  |-- compatibility
  |-- ordered media[] + cover reference
  `-- private provenance / review information
          ^
          `-- optional evidence references from individual claims/media
```

Reuse shared commerce/content/media contracts without forcing every item to have
every field. Keep product/accessory differences intentional. This model can start
inside existing JSON storage; it does not mandate an immediate relational schema.

### Public and admin contracts

Today, public responses remove `provenance`. That correctly protects the current
private structure but would not automatically protect newly introduced top-level
`internal_notes`, attribute notes, reviewer identity, or media source URLs.

Before adding those fields:

- Define explicit public and admin response shapes.
- Publish only approved public attribute/media properties.
- Apply filtering server-side on every public list/detail surface.
- Do not rely on `is_public` alone, frontend hiding, or a field's descriptive name.
- Test that internal values are absent from public JSON, not merely invisible in
  screenshots.

This is a necessary design boundary for the new schema, not a finding that the
currently implemented provenance field is exposed.

## 9. Fit with the current desktop and mobile design

### Storefront

Keep the current hierarchy: media, item identity, price/unit, short description,
critical compatibility, and the selection action. Put extended technical
attributes inside grouped details.

- **Desktop:** use readable grouped specification sections and retain multi-column
  browsing; do not turn every card into a full engineering table.
- **Mobile:** use stacked label/value rows and expandable secondary groups;
  important fit limitations stay visible.
- Do not show Unknown/blank rows for every unused attribute.
- Do not make users interpret internal verification notes to understand a product.
- Defer a dedicated accessory route until shareability or content depth justifies
  it; a required slug alone is not a UX requirement.
- Preserve sale-unit meaning throughout card, cart, and inquiry, including any
  future Kit support.

### Admin

Do not show a 17-column attribute editor on a phone or require the owner to
configure filtering flags for every item.

Recommended flow:

1. Choose a category.
2. Edit the shared basics and existing content fields.
3. Add a technical specification from suggested definitions.
4. Enter the value/unit and source evidence.
5. Mark unresolved mapping as Needs review without guessing.
6. Preview the exact public content.

Keep desktop split-pane editing and mobile list-to-editor navigation.
Retain unsaved-change protection, stable Save actions, clear validation, and
failed-upload retry. Any schema addition must be tested on both layouts.

## 10. Recommended priorities

This revises the Word document's priority list against the current baseline,
rather than implementing it in its original order.

| Phase | Work | Why / acceptance gate |
| --- | --- | --- |
| 0: Reconcile examples | Map a small representative set of real source listings into current fields; log only residual information gaps. | Avoid rebuilding fields already delivered. Confirm source evidence and category ownership before schema expansion. |
| 1: Identity and parity | Establish Equipment/Attachments terminology, dedicated catalog-wide SKU and optional Model, with reviewed classification and SKU backfill. Add optional warranty; stock status only if maintained. Review Kit, brand, and condition against real inventory needs. | Preserve IDs and links; resolve duplicate/ambiguous legacy identifiers before enforcing SKU completeness. Other unknown optional facts remain blank. |
| 2: Minimal attributes | Controlled definitions, bounded values/units, source reference, verification state, and private notes. Pilot mounting/cable/storage facts not already owned elsewhere. | Roundtrip preserves source meaning; no duplicate compatibility/package fields; public response filtering is tested. |
| 3: Media metadata | Image-specific alt text and cover selection first; stable IDs and server-derived metadata as required. | Existing galleries, video playback, ordering, deletion protection, and old records continue to work. |
| 4: Conditional expansion | Category IDs, multi-source records, structured dimensions/weight, normalization, filtering/comparison, and accessory routes. | Implement only after actual catalog scale or user tasks justify each capability. |

Draft/publish changes, public CAD/USD labels, compare-at pricing, variant engines,
and inventory/checkout systems are not prerequisites for these phases.

## 11. Migration and verification requirements

Before implementing an approved phase:

1. Document the API mapping from proposal names to existing camelCase fields.
2. Add optional fields and backward-compatible readers first.
3. Back up catalog/media data and trial the migration on a copy.
4. Preserve IDs, existing URLs, prices, units, source text, and gallery order.
5. Keep omitted versus explicitly cleared update semantics intentional.
6. Migrate category aliases only through an approved mapping; preserve unresolved
   labels for review.
7. Require review of parsed measurements rather than overwriting the originals.
8. Define one owner for each fact and each representation during transition.
9. Provide rollback without depending on a destructive rewrite of the old catalog.

Extend the existing [API contract tests](../backend/tests/test_catalog_contracts.py)
and [browser E2E suite](../frontend/tests/e2e/catalog.spec.ts) to cover:

- Legacy and new accessories through create/edit/reload and public rendering.
- Unknown units, legitimate blanks, zero/false values, invalid ranges, and units
  from the wrong measurement family.
- The 75 mm versus 3 inch case without automatic compatibility inference.
- Review invalidation after a value or evidence changes.
- Internal attribute/media/source fields absent from every public response.
- Pair/set/kit meaning in cart quantities and quote messages.
- Independent cover selection, removal of a cover, video-only media, and legacy
  URL-only media.
- Desktop and phone editor layouts with long technical content.
- Unchanged currency and publication behavior while those topics remain held.

## 12. Decisions to make before coding

1. Which real source facts still cannot be represented by the current fields?
2. Which initial attribute definitions are needed, and which existing field owns
   each overlapping fact?
3. What evidence and reviewer action are sufficient for Verified, especially for
   fit and load-related claims?
4. Do accessories genuinely need Kit, brand, Used condition, or separate pages now?
5. Is independent cover selection more valuable immediately than a complete media
   metadata migration?
6. Is a date-only capture adequate, or does the workflow require timestamped,
   multiple-source evidence?

**Bottom line:** the proposal is a good target architecture for preserving
accessory information. Keep the parts already implemented, add a small
evidence-aware attribute system next if real examples justify it, and evolve
media deliberately. Do not import its ambiguities, duplicate fields, or broad
future-facing scope into the current release.
