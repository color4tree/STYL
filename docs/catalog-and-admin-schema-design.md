# STYL product catalog and admin data schema

Status: Complete target-design draft for review; no application changes authorized

Date: 2026-09-25

Current implementation reference: `c412178`

## 1. Decisions and scope

### 1.1 Confirmed requirements

1. **Product** is the umbrella term for every sellable catalog item.
2. Initial product types are **Equipment** and **Attachments**.
3. Every sellable product has a unique, stable SKU across the entire catalog.
4. SKU and optional Model are different fields; neither is the internal record ID.
5. Business classifications and choices should be configurable in admin.
6. Prices accept up to two decimal places and display exactly two decimals.
7. Desktop and mobile have equal priority.
8. Technical facts, compatibility, selling points, media, and private source notes
   have distinct responsibilities.
9. Unknown facts remain unknown; no inferred compatibility, capacity, or package
   contents.
10. Preserve existing catalog data, links, media, and saved selections during migration.

### 1.2 Explicit exclusions and holds

- **CAD/USD behavior is held:** retain support for those two currencies, CAD as
  the new-entry default, symbol-only public prices, and separate currency totals.
  Configurable business options do not authorize adding currencies, conversion,
  or changing currency-display policy.
- **Draft/publish changes remain excluded.** Do not add attachment publication
  controls, change defaults, or introduce a new publication lifecycle as a
  dependency of this design.
- No checkout, payment, stock reservation, ERP, complex variants, compare-at
  pricing, native app, arbitrary scripting, or universal low-code form builder.
- Admin user identity, storage migration, new routes, and detailed SKU allocation
  policy below are recommendations that still need implementation approval.

### 1.3 Design approach

Use a **shared Product core with controlled, extensible data**, not separate
equipment and attachment schemas that continually drift.

Use configurable reference data instead of hard-coded business enums.
Keep technical discriminators and behavioral rules protected. For example,
an owner may add a stock label, but cannot turn an arbitrary label into a payment,
inventory, or publication action.

This document describes the full target model and a staged delivery path.
It does not claim these entities or admin screens already exist.

## 2. Current state and recommended persistence

Current evidence:

- [API models and catalog operations](../backend/app/main.py)
- [Media processing](../backend/app/media.py)
- [Catalog shared types](../frontend/src/lib/catalogDetails.ts)
- [Current accessory contract](../frontend/src/lib/accessories.ts)
- [Current cart](../frontend/src/lib/cart.ts)
- [Schema proposal evaluation](accessory-schema-review.md)
- [Responsive design and approved scope](mobile-ux-design.md)
- [Original product goals](STYL%20Portal%20Design.md)

Today STYL uses separate product/accessory JSON files, string categories,
partial shared fields, ordered media URLs, one private provenance object, and a
shared admin token. The current `modelSku` field is not a catalog-wide SKU system.
There is no database-backed reference-data editor, named-user audit trail, or
generic technical-attribute model.

### Persistence recommendation, not a required infrastructure expansion

The logical schema below is storage-independent. For implementation of the
**complete** configurable model, recommend SQLite on the existing single server:

- Unique SKUs, foreign keys, configuration defaults, and multi-record edits need
  atomic transactions.
- SQLite adds no managed database service and fits the current deployment scale.
- Enable foreign-key enforcement on every connection; use explicit transactions,
  a bounded busy timeout, and a tested backup/restore procedure.
- Catalog/media files remain on disk outside the database; their metadata and
  references are transactional records.
- Use SQLite's supported backup operation for a live database, not an uncoordinated
  copy that omits a write-ahead log.

Do not split this model into dozens of independently rewritten JSON files. If
storage migration is deferred, use a single versioned aggregate snapshot with a
single-writer lock and atomic replacement for related changes, and preserve the
same validation/uniqueness rules. Do not claim this supports multi-server writers.

Implement the model behind existing API adapters first. Moving storage does not
require simultaneously changing public URLs, UI terminology, and every client.

## 3. Vocabulary and relationship model

### 3.1 Customer and admin terminology

| Concept | Meaning |
| --- | --- |
| Product | One independently priced, sellable catalog offer with a SKU |
| Equipment | Primary training equipment: multi trainers, racks, benches, rowers |
| Attachment | A product designed to connect to equipment and extend its use |
| Category | A controlled classification within a product type |
| Selling unit | What quantity 1 buys: each, pair, set, or another configured unit |
| Package quantity | Individual-piece count inside one selling unit, when known |
| Model | Optional manufacturer/business model designation, not necessarily unique |
| Attribute | An item-specific technical fact, not a marketing feature |
| Compatibility assertion | An evidence-backed fit claim, limitation, or exclusion |

Do not classify solely by whether an item can be used without anything else.
Review existing benches/storage items rather than blindly renaming all current
accessories to attachments. A supporting-accessories type can be added later
through configuration if actual inventory requires it.

### 3.2 Logical entity map

```text
Admin principal ---- role binding ---- protected role/permission definitions
       |
       +---- configuration revision / audit event
       +---- source capture / claim review / migration resolution

Product
  +---- SKU registry / SKU allocation policy
  +---- product type --------------------------+
  +---- category tree                          |
  +---- brand                                  +---- admin reference configuration
  +---- selling unit / condition / stock label -+
  +---- product features[]
  +---- physical/content fields
  +---- product attribute values[] ---- attribute definitions / groups / choices
  +---- compatibility profiles[] ------ interface definitions / external models
  +---- compatibility assertions[] ---- optional equipment product reference
  +---- product media links[] --------- media assets / renditions
  +---- product source links[] -------- source records
  +---- claim reviews[] --------------- claim evidence[] ---- source records
  +---- private internal notes
  +---- collection memberships[]
  `---- legacy identity mappings

Inquiry ---- immutable selection line snapshots
```

The arrows are real ownership/references, not a chain in which a Category owns
Features, which then own Media.

## 4. Shared data conventions

The entity tables below specify **logical API field names** in camelCase.
Physical SQL naming may use snake_case through one mapping layer.

### 4.1 IDs, timestamps, versions, and values

- New target IDs: opaque UUID strings generated by the server.
- Product ID is the immutable primary key and canonical lookup identifier.
  Related records reference it through `productId`; SKU is an additional unique
  business lookup, not a replacement for product identity.
- Slugs, labels, and category codes are never used as foreign keys.
- Existing numeric IDs remain resolvable through explicit legacy mappings.
- Common mutable-record fields: `id`, `createdAt`, `updatedAt`, `createdBy`,
  `updatedBy`, and integer `version >= 1`.
- Timestamps are server-generated UTC ISO 8601. Preserve date-only precision for
  historical source captures; do not fabricate an exact time.
- Actor fields reference admin principals; migrated unknown actors may be null
  with an import/system attribution, not a fabricated human identity.
- Optional unknown values use null in the target schema. Legacy empty strings are
  handled by adapters. A false boolean and numeric zero are valid known values.
- Human text is plain text initially. No raw HTML/script expressions in attributes,
  option labels, notes rendered publicly, or configurable templates.
- Reject over-limit input rather than silently truncating it.

### 4.2 Equality and uniqueness

- Option codes: lowercase ASCII stable keys, scoped to their option set.
- Option/category labels: trim, collapse whitespace, normalize Unicode, and compare
  case-insensitively for duplicate suggestions within the relevant scope.
- SKU: canonical uppercase ASCII text with letters, digits, and hyphens; retain
  leading zeros. Recommended length 3-64. No category-dependent meaning.
- Model text: not unique; a model may identify a family or manufacturer designation.
- Product names: not globally unique. SKU resolves identity.
- Slugs: unique only within a documented route namespace. Changing a label does not
  change a slug or code.

### 4.3 Referential and concurrency rules

- Foreign keys use restricted deletion by default.
- Referenced reference-data options are retired, not deleted.
- API updates carry `If-Match`/expected aggregate version. A stale edit returns
  `412 Precondition Failed` with a reload/compare action, never overwrites silently.
- Product child edits increment the parent product aggregate version in the same
  transaction.
- Configuration has its own monotonically increasing revision. A product write
  is checked against current reference validity even when an editor loaded an
  earlier config revision.
- SKU allocation, product creation, initial evidence, and audit entry commit
  atomically where included in one save.
- Omitted fields on PATCH mean unchanged; null/empty-list means intentional clear
  only where allowed. Preserve the existing omitted-versus-cleared behavior.

## 5. Admin-configurable reference data

### 5.1 Configuration matrix

| Choice | Admin capability | Protected boundary |
| --- | --- | --- |
| Product types | Add, relabel, order, retire; seed Equipment and Attachments | No runtime behavior inferred from the label |
| Categories/subcategories | Add, rename, reorder, reparent, retire; reviewed merge | Acyclic tree, valid type membership, explicit reassignment |
| Brands | Add, relabel, retire | Never assume imported goods belong to STYL |
| Selling units | Add display terms and plural forms; seed Each, Pair, Set; Kit when needed | Whole sale-unit quantities; referenced unit meaning cannot change |
| Stock labels | Add/relabel/order/retire | Map to protected availability meanings; no automatic purchase rules |
| Condition labels | Add/relabel/order/retire | No condition inferred from source type |
| Source types | Add/relabel/order/retire | Source origin is not verification or evidence quality |
| Attribute groups | Add/relabel/order/retire | Presentation only |
| Attribute definitions | Create approved definitions, choose supported types/units, applicability | No arbitrary code or live type changes that invalidate stored values |
| Attribute choice lists | Add/relabel/order/retire choices | Stable choice identity; used meanings immutable |
| Measurement unit labels | Edit display/preferred units; activate supported units | Conversion factors and dimensions are protected, versioned math |
| Interface types | Add names such as rack upright or cable connection | Does not prove products fit each other |
| Verification/review labels | Add workflow labels mapped to fixed review meanings | Cannot redefine what Verified means or bypass evidence requirements |
| Review reasons | Configure reasons such as conflicting units or missing source | Does not change permissions/publication rules |
| Collection names/navigation labels | Configure curated groupings and placement | Existing routes and publication eligibility remain authoritative |
| SKU prefix/padding | Owner configuration for future allocation, versioned | Uniqueness, no reuse, sequence concurrency, and existing SKUs protected |
| CAD/USD | Read-only in this scope | No currencies/default/display policy changed while held |
| Product draft/publish status | Existing behavior only | No new states, defaults, or transitions in this scope |
| Attribute value kinds | Read-only: text, decimal, integer, boolean, choice, range | Parser/validator and storage representation |
| Media kinds/process states | Read-only | Upload decoding, processing, playback, and failure semantics |
| Roles/permissions | Owner assigns supported roles to identities | Permission definitions are not business option lists |
| Upload limits and retention policy | Read-only policy summary initially | Server/proxy/storage constraints cannot be bypassed by UI configuration |

**Default rule:** admins configure business vocabulary; the application controls
the meaning of data types, money, authorization, and technical state transitions.

### 5.2 `optionSet`

One row defines an approved configurable vocabulary, not a user-created arbitrary
database table.

| Field | Type / requirement | Meaning |
| --- | --- | --- |
| `id` | UUID, required | Stable identity |
| `code` | String, unique, immutable | Example: `selling_unit`, `stock_status` |
| `label` | String, max 100 | Admin heading |
| `description` | String, max 500, optional | Guidance |
| `purpose` | Protected discriminator | Determines which entity may reference it |
| `defaultOptionId` | FK, nullable | New-entry suggestion, if appropriate |
| `allowCustomOptions` | Protected policy flag | Whether owner may add options |
| `version`, audit fields | Common fields | Concurrency and change history |

Core sets are installed by the application. Admins may also create a set with
the supported `attribute_choice` purpose when defining a choice attribute.
That creates a vocabulary for an existing supported value kind, not a new
system field, arbitrary database table, or editable set purpose.

### 5.3 `option`

| Field | Type / requirement | Meaning |
| --- | --- | --- |
| `id` | UUID | Immutable reference |
| `optionSetId` | FK, required | Parent vocabulary |
| `code` | Stable string, max 80 | Unique within set |
| `label` | String, max 120 | Customer/editor display |
| `description` | String, max 1000, optional | Guidance, public only if explicitly projected |
| `sortOrder` | Integer, default 0 | Stable tie-break by code/ID |
| `isActive` | Boolean | Available for new assignments |
| `retiredAt` | Timestamp, nullable | Retirement record |
| `replacementOptionId` | Same-set FK, nullable | Suggested replacement, never automatic rewrite |
| `version`, audit fields | Common fields | History |

Constraints: unique `(optionSetId, code)`; replacement cannot point to itself or
form a cycle. Purpose validation guarantees a product's sellingUnitId cannot
reference a stock-status option.

`optionAlias(optionId, normalizedAlias)` supports legacy import matching.
Aliases are unique within a set. They do not rewrite stored IDs or SKUs.

### 5.4 Typed option extensions

Avoid an unconstrained `metadata` bag for behavior-bearing fields.

- `sellingUnitDefinition(optionId, priceLabel, quantitySingular, quantityPlural,
  expectedPieceCount?)`
  - Example Pair: priceLabel `pair`, nouns `pair`/`pairs`, expectedPieceCount `2`.
  - Piece count is an optional **consistency rule**, not an automatic assertion
    about an unknown legacy item. An explicit mismatch blocks save or requires
    choosing a more accurate selling unit.
  - Once used, changing the unit's piece-count meaning requires a new option.
- `stockStatusDefinition(optionId, availabilityMeaning)`
  - Protected meanings: unspecified, in_stock, out_of_stock, preorder,
    made_to_order.
  - Custom labels can map to these meanings. The current quote-only purchase
    behavior is not automatically changed.
- `verificationStatusDefinition(optionId, reviewMeaning)`
  - Protected meanings: unknown, source_stated, needs_review, verified.
  - Custom labels cannot reduce the evidence required for a meaning.

### 5.5 Retirement, defaults, and merges

- Renaming updates labels everywhere for current catalog rendering; historical
  inquiry snapshots retain their original labels.
- Retiring hides an option from **new selection**, but existing products keep its
  ID and readable label. Admin shows an inactive badge and usage count.
- Unchanged references to retired options are accepted during unrelated edits;
  assigning a retired option to another product is rejected.
- Retirement of a default requires choosing another active default or clearing
  the optional default in the same transaction.
- Defaults apply only to new forms/records, never to existing items or unknown
  imported data. Field-specific defaults are limited to genuine business policy.
- Deleting a never-used option is allowed only when no alias, source, template,
  historical reference requiring it, or other record depends on it.
- Merging is a previewed migration: counts, affected products, replacement,
  conflicting values, version check, transaction, audit, and rollback mapping.
  Retiring alone does not perform a merge.
- Product-type and selling-unit reassignment may change business meaning.
  Require review of classification, package contents, and sale-unit pricing;
  never multiply/divide prices automatically.

## 6. Core Product catalog

### 6.1 `product`

One row represents one sellable unit with one SKU and one current price.
Pairs and kits sold as a unit are one product. A separately sold component is
another product. Variants are not added implicitly.

| Field | Type / requirement | Rules |
| --- | --- | --- |
| `id` | UUID, required | Server-generated immutable primary key; visible and copyable, never editable in admin |
| `sku` | String, required | Global unique SKU from registry |
| `name` | String, required, 1-200 after trim | No blank/whitespace-only values |
| `productTypeId` | Product-type option FK, required | Initially Equipment or Attachments |
| `primaryCategoryId` | Category FK, required | Must belong to the chosen type |
| `brandId` | Brand FK, optional | No automatic STYL assignment to imports |
| `conditionId` | Condition option FK, optional | Unknown allowed |
| `model` | String, max 200, optional | Not a substitute for SKU |
| `slug` | String, optional during migration | Required only for a route that uses it |
| `shortDescription` | String, max 1000, optional | Card summary |
| `description` | String, max 10000, optional | Full description |
| `publicUseDescription` | String, max 4000, optional | Public use text, never internal notes |
| `priceMinor` | Integer, required, >= 0 | Cents; see money rules |
| `currencyCode` | CAD or USD, required | Existing default/display policy held |
| `sellingUnitId` | Selling-unit option FK, nullable | Unknown allowed; null is not Each |
| `packageQuantity` | Positive integer, nullable | Individual pieces per sale unit |
| `included` | String, max 4000, optional | Descriptive package contents |
| `stockStatusId` | Stock option FK, nullable | Descriptive availability only |
| `dimensionsText` | String, max 2000, optional | Preserved source summary, not normalized math |
| `weightText` | String, max 1000, optional | Preserve basis/unit qualifiers |
| `material` | String, max 1000, optional | Primary material description |
| `finishColour` | String, max 1000, optional | Simple finish/colour; no variant engine |
| `warranty` | String, max 4000, optional | Source-supported terms only |
| `coverMediaLinkId` | Product-media-link FK, nullable | Explicit image cover; same product |
| `internalNotes` | String, max 10000, optional, private | Operational notes, not source claims |
| `deletedAt` | Timestamp, nullable, server-only | Tombstone for the existing delete operation; retains identity/history |
| `version`, audit fields | Common fields | Whole aggregate concurrency |

Publication eligibility is deliberately **not redefined** here. During migration,
retain the existing eligibility data/adapter: current equipment publication
behavior and current accessory visibility behavior. This target table must not
impose a new default or expose existing hidden records by omitting the legacy rule.
Any unified publication field/workflow is a separate future decision.

The saved Product editor shows **Product ID** as read-only text with a Copy action
on both desktop and mobile. Before creation, it shows "Assigned on first save."
Even an owner cannot replace the ID; the API rejects attempts to change it.
Renaming, SKU correction, and reclassification retain the same Product ID.

Retrieval by Product ID assembles the product's core data and related attributes,
compatibility, media, and source/review records as appropriate to the endpoint.
The public endpoint returns only its public projection; knowing a Product ID does
not grant access to private source notes or admin operations.

During compatibility rollout, retain a one-to-one
`legacyCatalogBehavior(productId, sourceEntityType, publicationStatus?, featured?)`
record populated by the existing product/accessory adapter. Its fields preserve
existing behavior, are not editable business option sets, and are not inferred
from a renamed product type. Migrating an old accessory bench into the Equipment
classification must not silently change its visibility policy.

Deletion sets the product tombstone, retires its SKU assignment, removes it from
public results, and retains identity/audit references in one transaction. This
preserves the meaning of Delete without reusing identifiers; it is not a new
product publication state. Private content and inquiry retention are separate
policies, so retaining a SKU tombstone does not require retaining all content forever.

### 6.2 Categories and brands

`category`:

- `id`, stable `code`, `label`, `productTypeId`, optional `parentId`,
  optional `description`, optional `slug`, `sortOrder`, `isActive`,
  `replacementCategoryId`, common version/audit fields.
- Unique `(productTypeId, code)` and normalized sibling labels.
- Parent must belong to the same product type; prevent cycles and limit depth
  initially to two levels below type.
- Retire/merge rules mirror options. Reparenting updates navigation/templates only
  after impact preview; it cannot silently invalidate assigned attributes.

`categoryAlias(categoryId, legacySystem?, normalizedAlias)`:

- Supports reviewed mappings from Bar, Handle, Bench, Benches, etc.
- Scope aliases to avoid resolving an ambiguous name to the wrong product type.
- Unresolved mappings remain in the migration review queue.

`brand`:

- `id`, `name`, optional `websiteUrl`, optional `description`, `isActive`,
  common fields.
- Catalog brand records are not admin users or suppliers; do not overload them
  with authentication/contact credentials.

Recommended seed taxonomy, to be reviewed against real inventory:

```text
Equipment
  Multi trainers
  Racks
  Benches
  Cardio equipment

Attachments
  Rack attachments
  Cable attachments
  Bench attachments
```

### 6.3 `productFeature`

Fields: `id`, `productId`, `text` (1-1000), `sortOrder`, common audit fields.

Maximum 50 per product initially. Blank entries are not saved. Features are public
selling points; technical measurements belong in attributes/compatibility.
The public API may project an ordered string array to preserve current clients.

### 6.4 Money and sale-unit rules

- Store `priceMinor` as cents; no binary floating-point arithmetic in the target
  persistence/calculation layer.
- Input accepts decimal text with at most two meaningful fractional digits.
  Reject negatives, non-finite values, and excess precision instead of rounding.
- For JSON clients using integer cents, cap numeric values/calculated totals at
  the supported exact-integer range. Recommended `0..9,007,199,254,740,991` for
  cents, with checked multiplication/sums; a lower business cap can be approved.
- `19`, `19.5`, `19.95` display as `$19.00`, `$19.50`, `$19.95`.
- Quantity counts whole sale units, currently capped at 10 per cart item.
- Package quantity does not multiply the listed price. Two pairs at $19.95 per
  pair cost $39.90, not $79.80.
- A price belongs to its selling unit and currency. Changing either requires
  explicitly reviewing price meaning, not assuming a conversion.
- Existing mixed-currency totals remain separate; no new currency-label or
  conversion design is introduced while that topic is held.

## 7. Catalog-wide SKU design

### 7.1 Policy

Recommended default: auto-allocate neutral SKUs such as `STYL-000101`, with
authorized manual assignment for already established business SKUs.

- Format is a proposed allocation policy, not an approved business numbering
  standard until reviewed.
- SKU is mandatory for every committed sellable Product, including entries that
  are not publicly visible under existing rules.
- Source listing ID and manufacturer model are not automatically SKUs.
- Never derive SKU from category, name, Equipment/Attachment, or sale price.
- Never reuse a previously assigned SKU, including after an item is removed.
- Renaming/reclassifying a product does not regenerate its SKU.
- SKU corrections require privileged action, reason, and retained previous-SKU
  resolution; ordinary product editing cannot silently change identity.
- Temporary import rows may lack a SKU; they are staging records, not Products.

### 7.2 Entities

`skuPolicy`:

| Field | Meaning |
| --- | --- |
| `id`, `version` | Versioned allocation policy |
| `prefix` | Example `STYL-`; validated limited text |
| `minimumDigits` | Example 6; padding width, not a maximum sequence length |
| `sequenceId` | FK to server-controlled counter |
| `allowManualAssignment` | Owner policy |
| `isRetired` | Retired policies remain readable and cannot become the current policy |
| Common audit fields | Who changed future allocation behavior |

`skuSequence(id, nextValue)` is server-controlled. Admins cannot reset it below a
previous allocation or promise gapless numbering.

`catalogSettings.activeSkuPolicyId` is the single authoritative pointer to the
current non-retired policy. Do not also maintain independent "active policy"
booleans that can disagree with it.

`skuRegistry`:

- `sku` canonical string primary key.
- `productId` nullable FK while reserving; assigned when product creation commits.
- `allocationState`: protected reserved / assigned / retired.
- `policyId` nullable for manual/migrated identifiers.
- `reservedAt`, `assignedAt`, `retiredAt`, `assignedBy`, optional `reason`.
- Multiple historical SKUs may point to a product, but exactly one is the
  product's current `sku`.

`product.sku` references `skuRegistry.sku`. At transaction commit, a nondeleted
product's current entry must be assigned to that same product; a deleted product
retains its own retired entry. Cross-product references are invalid.
Retired entries remain reserved forever.

### 7.3 Atomic allocation

1. Authenticate and validate the request and reference-data selections.
2. Begin a write transaction and advance the appropriate sequence, or reserve
   the normalized manual SKU subject to its unique constraint.
3. Insert the product and assign its registry entry in that transaction.
4. Record audit and request identity; commit.
5. Return the assigned SKU, ID, and version.

Use an idempotency key for create requests to prevent a network retry creating
two products/SKUs. Persist request identity/result with bounded retention; a
reused key with a different payload is rejected. Gaps are acceptable. Duplicate
SKUs, lost updates, and sequence reuse are not.

`adminMutationRequest` stores `principalId`, operation code, idempotency-key hash,
request-payload hash, result entity ID/version, response status, createdAt, and
expiresAt. Unique `(principalId, operation, keyHash)` serializes duplicates.
Use a documented retry window; the SKU registry remains permanent even when these
request records expire. Do not store authentication tokens or full private request
payloads in this table.

## 8. Technical attributes and configurable forms

### 8.1 Attribute groups and definitions

`attributeGroup`: `id`, stable `code`, `label`, `sortOrder`, `isActive`, common fields.
Initial useful groups: Mounting, Cable interface, Barbell interface, Adjustment,
Storage, Construction. Other groups may be configured.

`attributeDefinition`:

| Field | Type / purpose |
| --- | --- |
| `id`, `key` | Stable identity; global unique key such as `pin_length` |
| `label`, `description` | Display and guidance, max 120 / 1000 |
| `groupId` | Attribute-group FK |
| `valueKind` | Protected text / decimal / integer / boolean / choice / range |
| `unitDimension` | Protected length / mass / count / none, with approved expansion |
| `choiceSetId` | FK required only for choice values |
| `defaultUnitId` | Nullable FK in the allowed dimension |
| `riskClass` | Protected descriptive / fit / load classification |
| `publicByDefault` | Display suggestion, not permission to expose private evidence |
| `isActive`, `sortOrder` | Availability and default order |
| `definitionVersion` | Semantic schema version |
| Common audit fields | Change tracking |

Typed optional constraints belong to the definition: `maxTextLength`,
`minNumericValue`, `maxNumericValue`, and `maxFractionDigits`. Only applicable
constraints are accepted for the chosen value kind; bounds must be internally
consistent. Initial service-wide limits cap text at 4000 characters and numeric
values at 18 significant digits and 6 fractional digits, unless a reviewed
definition needs a different supported precision. A tighter constraint cannot
be applied to existing values until an impact check/migration resolves violations.

`attributeAllowedUnit(definitionId, unitId)` restricts accepted units.
`attributeApplicability(definitionId, productTypeId?, categoryId?)` determines where
an attribute is suggested/allowed; references must have consistent scopes.

Do not permit an owner to change the type, measurement dimension, choice-set
meaning, or risk class of a definition with existing values without a versioned,
validated migration. Labels/order may change without rewriting values.

### 8.2 `productAttributeValue`

Fields:

- `id`, `productId`, `definitionId`, `definitionVersion`, `sortOrder`.
- One typed value representation: `textValue`, `decimalValue`, `integerValue`,
  `booleanValue`, `choiceOptionId`, or `rangeMin`/`rangeMax`.
- `unitId` where the definition requires a unit.
- `sourceExpression` optional private original text, max 4000.
- `isPublic` boolean, subject to server review policy.
- Common audit fields; review/evidence references are separate records.

Constraints:

- At most one value per `(productId, definitionId)` initially. Repeatable
  multi-interface measurements use profiles rather than duplicate ambiguous keys.
- Exactly one appropriate typed representation is present; no scalar and range
  on the same row.
- Range endpoints must be finite, in one unit, and `min <= max`; initially ranges
  are inclusive and this meaning is documented.
- Decimal technical values use a lossless decimal representation, not the
  currency two-decimal rule. Precision limits belong to definition validation.
- Choice options must belong to the definition's set.
- False, zero, and a valid empty-choice absence are handled distinctly.
- An absent fact has no value row, or a review item for missing evidence. Do not
  put the word Unknown in a numeric column.
- Start with text/decimal/integer/choice only if those cover the pilot. Supporting
  additional listed kinds is a deliberate application increment, not an admin
  ability to create a new parser.

### 8.3 Units

`measurementUnit`: `id`, immutable `code`, editable `label`, `symbol`,
`dimension`, canonical conversion numerator/denominator, `conversionVersion`,
`isActive`.

Known conversions are application-controlled, preferably exact rational rules:
1 inch = 25.4 mm. Admins choose supported units and labels, not conversion math.
New nonstandard units require an explicitly reviewed application addition.

Do not infer equivalent interfaces: 3 inches = 76.2 mm, not 75 mm.
Normalization preserves the original value/unit/precision and is derived only
when needed. It never proves fit or capacity.

### 8.4 Fixed-field versus attribute ownership

| Fact | Authoritative owner |
| --- | --- |
| SKU, name, price, selling unit, piece count, included contents | Product core |
| Public descriptions, material, finish, warranty | Product core |
| Selling points | ProductFeature |
| Pin length, usable peg length, adjustment count, connection details | Technical attribute values, where not an interface constraint |
| Rack upright size, pin/hole interface needed to establish fit | Compatibility profile facts |
| Confirmed/incompatible model relationships | Compatibility assertions |
| Image/video ordering and cover | Product-media links |
| Private source ambiguity and review | Source/review records |

Legacy dimensions/weight summaries remain source-preserving text. Do not add an
independently editable normalized copy of the same fact. If typed measurements
replace a summary later, mark the summary derived/read-only or retain it as private
original source text.

## 9. Compatibility and fit evidence

### 9.1 `compatibilityProfile`

A product may have several interfaces; a multi trainer may have rack and cable
interfaces. A single flat compatibility object is insufficient for that case.

Fields: `id`, `productId`, `label`, `interfaceTypeId`, `role`, `sortOrder`,
optional `publicLimitations`, common fields.

- `interfaceTypeId` references a configurable interface vocabulary.
- `role` is protected accepts / requires / descriptive.
- This role describes the connection, not whether the whole product is usable alone.

`interfaceDefinition`: controlled fact key, label, supported value kind, unit
dimension, allowed units, and applicable interface types. Reuse the same typed
value validation machinery as attributes, not duplicate product data.

`compatibilityFact`: `id`, `profileId`, `definitionId`, typed value fields,
unit, optional original source expression, review references.
Examples: upright width/depth, nominal-system text, hole diameter/spacing.

Do not build an automatic fit-matching engine in v1. Similar measurements,
category membership, or shared interface-type labels are not confirmation.

### 9.2 `equipmentModel`

Represents a model referenced by compatibility, including equipment not sold by
STYL. Fields: `id`, `brandId?`, `manufacturerName?`, `modelName`, `revision?`,
`modelCode?`, optional internal source reference, `isActive`.

Use either a verified brand reference or explicit manufacturer text; preserve
unknowns. Do not force external equipment into the sellable Product catalog.

### 9.3 `compatibilityAssertion`

| Field | Rule |
| --- | --- |
| `id`, `productId`, `profileId?` | Claim belongs to a product/interface |
| `targetProductId` or `targetEquipmentModelId` | Exactly one, when naming a concrete target |
| `assertionKind` | Protected compatible / incompatible / conditional / unverified |
| `conditions` | Required for conditional; includes clearances/revisions/context |
| `publicLimitations` | Customer-facing caveats |
| `isPublic` | Subject to claim review, never bypasses evidence rules |
| Common fields and claim review | Provenance and accountability |

Free-text source claims such as "fits many 3 x 3 racks" stay in source evidence or
clearly qualified limitations until the actual targets are established. Do not
create brand/model assertions from them.

Existing flat compatibility fields are read through a legacy profile adapter.
Migration does not automatically promote existing text to Verified.

## 10. Media assets, presentation, and ownership

### 10.1 `mediaAsset`

Fields:

- `id`, protected `kind` image/video, protected `storageKind` uploaded/external.
- `originalFilename?` private, `sourceRecordId?` private, `uploadedBy?`.
- `processingState`: protected processing / ready / failed.
- `processingErrorCode?` internal safe code, not raw paths/credentials.
- `createdAt`, `updatedAt`, `version`.

Asset identity is not its URL. External source records do not automatically
authorize copying or redistribution; editors need rights to use the media.

### 10.2 `mediaRendition`

Fields: `id`, `assetId`, protected `role` primary/poster/thumbnail,
server `storageKey` or external HTTPS URL (exactly one), verified/detected MIME,
`byteSize?`, `widthPx?`, `heightPx?`, `durationSeconds?`, optional hash,
`createdAt`.

- These describe delivered files, not necessarily original inputs.
- The server generates metadata for uploaded files; external metadata may remain
  unknown. Do not trust an editor-entered MIME or file size.
- Storage keys resolve under the approved upload store, never arbitrary filesystem
  paths supplied by clients.
- An asset with a ready primary rendition may be linked publicly.
- Poster is a rendition role, not an independent claim that original video remains.
- Originals currently are temporary and discarded. Preserve that policy unless
  separately approved; filename/evidence does not imply original retention.
- Existing synchronous upload can create the ready asset/renditions transactionally.
  A persistent processing queue is not required just because a state is modeled.

### 10.3 `productMedia`

Fields: `id`, `productId`, `assetId`, integer `position`, `altText?`,
`caption?`, common fields.

- Unique `(productId, assetId)` and `(productId, position)`; reorder as one aggregate
  update. Bound to 12 links initially.
- Alternative text is per product usage, because the same asset may have different
  context. Filename is not a default meaningful description.
- A product's explicit `coverMediaLinkId` must point to its own ready image link.
- If no explicit cover: derive first ready image, otherwise the first video's
  poster, otherwise a placeholder. This is distinct from the first gallery item.
- Removing the explicit cover clears that reference in the same transaction and
  previews the fallback; it does not leave a dangling reference.
- Shared media deletion checks all product, hero, and other usage references before
  deleting physical assets. Orphan cleanup is a bounded, auditable maintenance task.

### 10.4 Preserved delivery policies

Images: up to 8 MiB. Videos: up to 50 MiB. Combined gallery: 12.
Retain actual server validation and proxy limits. Current H.264/AAC conversion,
poster generation, seeking/range delivery, no autoplay, and error recovery remain.
Media metadata is not resumable-upload or background-job functionality.

## 11. Sources, claim reviews, and migration management

### 11.1 `sourceRecord` and `productSource`

`sourceRecord`:

| Field | Meaning |
| --- | --- |
| `id`, `sourceTypeId` | Configurable origin such as Marketplace/Supplier/Manual |
| `title?`, `providerName?` | Internal description of the evidence |
| `url?`, `listingId?` | Original reference; URL is validated, not automatically fetched |
| `capturedDate?`, `capturedAt?`, `capturePrecision` | Date-only or exact UTC timestamp, never fabricated precision |
| `capturedBy?` | Actual actor or unknown legacy attribution |
| `sourceNotes?` | Conflicts/ambiguities, max 10000, private |
| `evidenceStorageKey?` | Optional controlled private snapshot; not a public upload URL |
| Common fields | Version and attribution |

`capturePrecision` is protected unknown/date/timestamp and constrains which date
fields are populated. Source origin is separate from verification method.

`productSource(productId, sourceRecordId, isPrimary)` links reusable sources;
at most one primary source per product. No global uniqueness assumption for a
listing ID without its provider context.

Keep private snapshots only when authorized and needed; reference URLs and
review notes do not require copying every source document.

### 11.2 `claimReview`

Tracks evidence for one product fact. Fields:

- `id`, `productId`, protected `targetKind`.
- Exactly one target: allowed `productFieldKey`, `attributeValueId`,
  `compatibilityFactId`, or `compatibilityAssertionId`.
- `verificationStatusId` mapped to the protected review meanings.
- `reviewReasonId?`, `reviewNotes?`, `verifiedBy?`, `verifiedAt?`.
- `valueRevision` or content fingerprint binding review to the precise fact.
- Common version/audit fields.

Enforce target ownership and existence. Product field keys come from a
server-registered allowlist, not arbitrary JSON paths supplied by a client.
If physical relational storage cannot enforce the polymorphic reference directly,
use separate target-FK columns with an exactly-one check plus service validation;
do not accept unvalidated string target IDs.

`claimEvidence(reviewId, sourceRecordId, excerpt?, verificationMethodId?)`
supports multiple sources and explicit conflicting evidence.

Rules:

- Imported data begins Unknown or Source stated, not Verified.
- Verified requires permitted reviewer identity, timestamp, and evidence/method
  appropriate to the claim.
- Changing value, unit, target model, conditions, or relevant evidence invalidates
  verification in the same transaction.
- A source-stated load rating is not a measured/certified safe working load.
- Protected claim-display policy determines whether fit/load claims can be shown;
  changing an option label cannot relax it.
- This is a claim-quality workflow, not a new product draft/publish workflow.

Recommended default policy for new claim records:

| Claim | Public-display requirement |
| --- | --- |
| Ordinary descriptive value | Valid value, explicitly public, Source stated or Verified; no private evidence fields exposed |
| Concrete compatible/conditional model assertion | Verified for the exact target/interface/revision and conditions; category similarity is insufficient |
| Unverified fit or potential exclusion | No positive compatibility badge; an explicitly reviewed qualification such as "Fit not confirmed" may be displayed |
| Load-related number | Reviewer has verified the cited source and applicability, including per-piece/pair/system basis; public wording identifies manufacturer-stated or documented-test basis as appropriate |

Verified records the performed review method; it does not turn a supplier claim
into an independently tested or certified capacity. If a method or required basis
is missing, do not display an unqualified rating. Roll out these new-claim rules
after reviewing migrated data; do not silently assign Verified or unexpectedly
reinterpret legacy claims at cutover.

### 11.3 `migrationBatch` and `migrationItem`

`migrationBatch`: `id`, label, source description, mapping-version identifier,
created actor/time, counts, protected processing state, completion time.

`migrationItem`:

- `id`, `batchId`, original source record/reference, original identifier,
  private original payload/text or snapshot key.
- Proposed canonical field mapping, unresolved-field list, proposed category/type,
  proposed SKU/model separation.
- Protected resolution state: pending_review / approved_mapping / imported / failed.
- `targetProductId?`, reviewer/time, safe validation errors.

These are staging records, not public products or product-publication states.
They can retain incomplete facts without fabricating required catalog fields.
Approved import validates against current config and reserves SKU atomically.
Retry is idempotent by migration item ID.

### 11.4 Privacy rules

- Private source notes, excerpts, reviewer identities, original filenames,
  internal errors, migration payloads, and internal notes are admin-only.
- Public serialization uses explicit allowlists, including nested media and
  attributes. Removing only `provenance` is insufficient for this richer schema.
- Private evidence storage is separate from public static upload routes.
- A public attribute exposes approved value/label/unit and optional safe qualification,
  not its entire review/source record.
- URLs alone do not establish authorization to expose private source content.

## 12. Admin management schema and workflows

### 12.1 Admin identity and authorization

Current shared-token access cannot truthfully attribute changes to individual
humans. Do not label an audit entry "verified by Kenny" merely because the shared
token was used.

`adminPrincipal`:

- `id`, `displayName`, protected `kind` user/service/legacy_shared,
  `identityProvider?`, immutable provider `subject?`, `isActive`, common fields.
- Unique `(identityProvider, subject)` where present.
- No plaintext tokens, password copies, or authentication secrets in this schema.

`roleBinding(principalId, roleCode, assignedBy, assignedAt)`:

Recommended protected roles:

| Role | Capabilities |
| --- | --- |
| Owner | Reference/config changes, identity assignments, SKU policy, all catalog functions |
| Catalog editor | Edit product content/media, capture sources, use existing active options |
| Reviewer | Review evidence, approve mapping, resolve fit/source ambiguities |
| Viewer | Read-only admin data as permitted; no mutation |

Roles can be combined. Permissions are enforced by the API; hiding UI buttons is
not authorization. Technical permission definitions are code-managed. Business
option-set editing never grants privileges.

Introducing named identities is a recommended prerequisite for reliable human
verification. If the shared token is retained temporarily, audit records must
use `legacy_shared`; configuration is owner-level and review claims must not
pretend to identify a particular human.

### 12.2 Configuration revision and change audit

`configurationRevision`:

- `revision` integer primary key, created time/actor, reason,
  previous revision, schema version, optional immutable configuration snapshot/hash.

`auditEvent`:

- `id`, occurredAt, actorId, requestId, action code, entity kind/ID,
  beforeVersion, afterVersion, changed-field summary, reason, config revision.
- Private, append-only to normal users; privileged retention policy separately
  controls archival/deletion.
- Redact secrets and avoid embedding customer inquiry bodies in general audit logs.
- Detailed source-note history, if retained, inherits private-source permissions.

Do not make every minor label edit require a multi-person approval engine.
Use impact preview + owner confirmation + versioned transaction + audit.
Risky semantic changes require an explicit migration instead of bypassing validation.

### 12.3 Limited `catalogSettings`

Typed settings, not arbitrary key/value behavior:

- `activeSkuPolicyId`, the authoritative allocation-policy reference.
- Optional default category, validated against the selected default type.
- Default product type, selling unit, and condition are projections/edit links to
  the corresponding `optionSet.defaultOptionId`, not separate stored defaults.
  Recommend no forced selling-unit/condition default for imported unknown facts.
- Public collection/navigation references and supported label overrides.
- Preferred display units chosen from registered supported units.
- Read-only currency, publication, upload-limit, and security-policy summaries in
  this scope.

Changes affect new-entry suggestions only unless a reviewed operation explicitly
updates existing records. A configuration page must show that distinction.

### 12.4 Admin form schema: controlled templates, not arbitrary forms

`categoryAttributeTemplate(categoryId, definitionId, sectionOrder, fieldOrder,
suggestedUnitId?, guidance?, isSuggested)`:

- Suggests relevant technical fields per category.
- Shared identity/price/SKU fields are built-in and cannot be removed by a template.
- Technical facts are optional unless an explicit catalog policy requires their
  presence and provides a legitimate unknown/review path.
- Template changes do not erase values from existing products.
- Removing a definition from suggestions leaves assigned values visible with a
  review notice; it is not data deletion.
- No injected JavaScript, SQL, HTML, regex execution, or URL fetches in templates.
- Typed validators belong to supported definitions, not arbitrary admin scripts.

### 12.5 Admin screens

1. **Product catalog:** Equipment/Attachments filters, SKU/name search and exact
   Product ID lookup, category,
   source-review status, price, existing visibility status where already supported.
2. **Product editor:** Identity & SKU; Commerce; Content; Technical specifications;
   Compatibility; Media; Sources & review; Internal notes.
3. **Catalog settings:** Types, Categories, Selling units, Conditions, Stock labels,
   Brands, Defaults, SKU policy.
4. **Attribute library:** Groups, definitions, choices, supported units, category
   suggestions, usage/impact counts.
5. **Media library:** Referenced assets, metadata, usage, failure state, safe orphan
   cleanup preview.
6. **Source/migration review:** Unmapped facts, category ambiguity, SKU conflicts,
   evidence and review assignment.
7. **Activity:** Audited changes, configuration revisions, conflict resolution.
8. **Access:** Owner-only supported role assignments when named identities exist.

For every configurable option, display its code/label, default status, active
state, usage count, and edit/retire/replace actions. Desktop uses tables and
split panes; phones use list/detail screens. Both expose the same capabilities.

## 13. Collections, navigation, and home content

`collection`: `id`, stable code, label, description?, optional productTypeId,
ordered category filter references or explicit membership mode, sortOrder,
isActive, common fields.

`collectionProduct(collectionId, productId, position?)` supports curated membership.
Use a protected selection mode explicit / type_category_filter; no arbitrary
query-language strings.

`navigationEntry`: `id`, label, targetKind, targetReference or approved local anchor,
position, isActive. Targets are approved routes/collections, not arbitrary
executable or credential-bearing URLs.

`homeBanner`: existing text fields and price-label copy, media reference, version/
audit fields. It remains promotional content, not a second source for a product's
actual catalog price.

Keep the existing full home collection with Featured products first.
Do not add an attachment Featured toggle or change merchandising behavior merely
because this target model supports collections. A future generalized sort policy
must explicitly preserve or supersede the current rule.

## 14. Inquiry and cart-related data

These are part of admin-managed business data but not an order/payment schema.

`inquiry`:

- `id`, submittedAt, customer name/email, optional phone/company, message,
  source-channel, existing email-delivery state, optional assigned admin/review note.
- Existing name/email/message validation and persistence-before-notification remain.
- Customer contact data is private, separately permissioned, with an explicit
  retention policy.

`inquiryLineSnapshot`:

- `id`, `inquiryId`, `productId?`, `skuSnapshot`, `nameSnapshot`,
  `quantity`, `sellingUnitLabelSnapshot?`, `packageQuantitySnapshot?`,
  `priceMinorSnapshot?`, `currencyCodeSnapshot?`.
- Store the product version/reference used and whether a value was catalog-
  validated or supplied by a visitor; never trust client prices as an order total.
- Snapshots preserve quote context when product names, unit labels, or prices change.
- A product deletion/reclassification does not destroy the original inquiry context.
- Adding structured selection lines is an optional future extension of the current
  message-prefill flow, not an immediate API requirement.

Guest carts can remain browser-stored. New clients should store stable product ID,
SKU/name/unit snapshots and quantity, refresh against catalog availability when
needed, and support old numeric IDs through the legacy map.

No currency conversion, stock reservation, or payment-state machine is introduced.

## 15. API contracts and validation

### 15.1 Target API grouping

Keep existing routes through adapters during migration. Illustrative new routes:

| Surface | Operations |
| --- | --- |
| Public catalog | List/search approved public products; fetch a product; public category/option labels actually needed for rendering |
| Admin catalog | Create/read/update product aggregate; assign/correct SKU with privilege; manage media/attributes/source links |
| Admin configuration | Read config revision; list/add/update/retire options/categories; usage and change preview; apply versioned changes |
| Admin evidence | Source capture, claim review, migration mapping and import |
| Admin audit/access | Read authorized audit history; assign supported roles |

Example route names: `/api/catalog/products`, `/api/admin/catalog/products`,
`/api/admin/catalog/config`, `/api/admin/catalog/option-sets/{id}/options`.
These are design names, not instructions to immediately replace `/api/products`
or `/api/accessories`.

### 15.2 Product aggregate shape

```json
{
  "id": "opaque-product-id",
  "sku": "STYL-000103",
  "version": 7,
  "name": "Cable Handle Pair",
  "productTypeId": "type-attachments",
  "primaryCategoryId": "category-cable-attachments",
  "model": null,
  "money": { "amountMinor": 1995, "currencyCode": "CAD" },
  "sellingUnitId": "unit-pair",
  "packageQuantity": 2,
  "included": "Two handles",
  "features": [{ "id": "feature-1", "text": "Matching handles", "sortOrder": 0 }],
  "attributes": [],
  "compatibilityProfiles": [],
  "compatibilityAssertions": [],
  "media": [],
  "coverMediaLinkId": null,
  "sources": [],
  "claimReviews": [],
  "internalNotes": null,
  "configRevision": 12
}
```

IDs and facts are illustrative; no source inventory assertions are intended.
Full-field definitions are in the entity sections; this is not a complete fixture.

The public projection excludes `sources`, `claimReviews`, `internalNotes`, actor
fields, storage keys, and private evidence. It may include resolved public type,
category, selling-unit labels and qualified approved attributes. Public currency
codes may remain machine-readable as today without changing `$`-only UI display.

Do not expose a universal admin object and ask the browser to hide sensitive keys.

### 15.3 Error and transaction behavior

- `401/403`: authentication/authorization failure.
- `404`: unknown ID or public-unavailable record under existing rules.
- `409`: duplicate SKU, conflicting reference merge, or idempotency payload mismatch.
- `412`: stale product/config version.
- `422`: structured field errors, e.g. wrong option set, unsupported unit,
  invalid two-decimal price, conflicting pair count, or invalid range.
- `503`: storage/processing unavailable; never report a successful save.

Return error code, safe message, field path, and request ID. The editor preserves
input and focuses a summary/field. For config conflicts, show what changed and
require an explicit reconcile/retry.

Configuration option creation returns the new option and config revision so a
permitted editor can select it without reloading/losing an open product form.
The server still validates the final product against the latest configuration.

## 16. Migration from the current schema

### Essential indexes

- Product: unique SKU; `(productTypeId, primaryCategoryId)`; normalized name/model
  search indexes as catalog size requires; legacy-ID mappings.
- Reference data: unique set/code and scoped aliases; parent/type/category indexes.
- Attributes: unique product/definition; definition/value indexes only when a
  real filter uses them, not speculative indexes on every possible value.
- Media: unique product/asset and product/position; asset usage references for
  deletion checks.
- Reviews: target identity; review meaning/reason and assignment queues.
- Audit/inquiries: entity/request/time and authorized operational retrieval.

Indexes support explicit query needs; they are not permission boundaries.

### 16.1 Mapping

| Current | Target |
| --- | --- |
| Separate product/accessory records | Shared Product plus reviewed productTypeId |
| Numeric `id` | `legacyIdentity` -> new stable Product ID |
| Product `modelSku` | Reviewed SKU assignment and optional Model; preserve original in migration evidence |
| String `category` | Category ID through an approved alias map |
| `price` number | `priceMinor` exact cents; flag invalid/excess-precision legacy data |
| `currency` | currencyCode, unchanged values/default/display policy |
| `shortDescription`, `description` | Same concepts |
| Accessory `notes` | publicUseDescription; never moved to private notes by assumption |
| `features: string[]` | Ordered ProductFeature records |
| `sellingUnit` | Selling-unit option ID; unknown remains null |
| `packageQuantity`, `included` | Same sale-unit concepts |
| `colourOptions` | finishColour, preserving original content |
| `dimensions`, `weight` | Preserved source text first, structured only after review |
| Flat `compatibility` | Legacy compatibility profile/limitations; no automatic verification promotion |
| `photos: string[]`, `image` | Media assets/product links plus cover fallback preserving order |
| `provenance` | SourceRecord/ProductSource and private notes with original precision |
| Current publication fields/rules | Eligibility adapter, unchanged |

`legacyIdentity(system, entityType, oldId, productId)` has unique source tuple.
Do not assume the current offset-based product/accessory numeric IDs can never
collide. Resolve legacy carts/URLs by source context where available; flag ambiguous
old cart identities for re-selection rather than silently binding the wrong item.

### 16.2 Sequence

1. Export/backup catalogs, media references, and source records; record source revision.
2. Seed reference vocabularies and approve category/type mapping.
3. Run a dry mapping on a copy. Report missing SKU, ambiguous Model/SKU, category
   collisions, invalid prices, duplicate IDs, and unsupported source values.
4. Assign SKUs for all Product records deliberately; preserve supplied real SKUs
   only after normalization and global uniqueness checks.
5. Import into the target store transactionally with an immutable legacy map.
6. Compare counts, names, prices, units, descriptions, media order, source privacy,
   and current public eligibility.
7. Switch reads/writes through one adapter boundary; do not leave dual independent
   writers to JSON and database.
8. Keep existing URL/ID compatibility; introduce terminology/UI changes without
   requiring new external links.
9. Retain rollback data and test restoration before production cutover.

Do not automatically parse/infer units, package counts, model compatibility, brand,
condition, or timestamps merely to satisfy target required fields.

## 17. Delivery stages

| Stage | Deliverable | Exit condition |
| --- | --- | --- |
| A: Contract and migration decisions | Approved identity/SKU policy, reference-data rules, storage choice, role model | No unresolved identity/currency/publication migration semantics |
| B: Shared catalog and reference admin | Product core, SKU allocation, categories/types/units, admin option management, legacy adapters | Global uniqueness, atomic edits, retirement/default tests, all legacy data readable |
| C: Content and private sources | Full shared product fields, source records, safe public DTOs, migration review | No mapping loss or private data leakage; desktop/mobile editors both usable |
| D: Technical specifications and compatibility | Controlled definitions, values, profiles, evidence/review, category templates; named reviewer identity before enabling human Verified actions | No duplicate authoritative facts or inferred fit; tested type/unit constraints and real actor attribution |
| E: Media records and metadata | Stable assets, link order, explicit covers, alt text, reference-safe deletion | Legacy galleries and real playback still work |
| F: Operational refinement | Richer audit/review screens as approved; optional inquiry snapshots and collection management | Real operator workflows tested without inventing inventory/checkout features |

Implement only the necessary supported types/options in each stage. The target
schema is not a mandate to build a generic PIM platform before launch.

## 18. Required acceptance tests

### Configurable options

- Owner adds a selling unit; both desktop and phone forms can use it immediately.
- Renaming preserves references; retired options cannot be newly assigned but
  existing products retain their meaning and can receive unrelated edits.
- Duplicate code/alias, wrong-set IDs, category cycles, and inactive defaults fail.
- Changing a unit's meaning with existing products is blocked or requires migration.
- Stale config preview cannot overwrite a newer change.
- Ordinary editors cannot grant permissions or alter currency/publication rules.

### SKU and money

- Product ID is generated once, displayed read-only with Copy, and cannot be
  changed through any admin role or API update.
- Retrieval by Product ID returns the correct related records without crossing
  public/admin authorization boundaries.
- Concurrent create requests cannot receive the same SKU.
- Retried create with the same idempotency key returns one product/SKU.
- Manual SKU collisions are rejected across Equipment and Attachments.
- Renaming/reclassifying preserves SKU; retired/corrected SKUs are not reused.
- Two-decimal input/display, integer-cent arithmetic, and checked limits hold.
- Quantity 2 of a Pair means two pairs; no package-count price multiplication.

### Technical data and evidence

- Wrong-unit dimension, invalid ranges, contradictory typed values, and wrong
  choice-set options are rejected.
- False and zero render correctly; missing numeric facts remain absent.
- Attribute/core/compatibility ownership prevents independently editable duplicates.
- A 75 mm statement is not normalized into a 3 inch fit claim.
- Editing a reviewed value invalidates its review.
- Load/fit claims require the protected evidence policy regardless of label changes.

### Privacy and operations

- Every public response excludes internal notes, source evidence, reviewer identity,
  private media metadata, and migration payloads.
- Shared-token activity is not attributed to a named human.
- Audit records preserve request/version context without secrets/customer-body copies.
- Config/product conflicts preserve editor input and present actionable errors.
- Backup/restore and failed multi-record transactions do not leave dangling references.

### UX and migration

- Equipment/Attachments navigation and admin terminology match the configured types.
- SKU is discoverable in product detail, admin search, and quote context without
  overwhelming mobile cards.
- Desktop retains multi-column browsing/split editing; phones retain accessible
  list/detail and touch controls.
- Existing IDs, URLs, images, videos, descriptions, cents, units, and visibility
  are preserved through the adapter.
- Existing currency and draft/publish behaviors remain unchanged.
- Real iPhone Safari and Android Chrome verify keyboard, media, safe-area, and
  touch behavior beyond automated viewport checks.

## 19. Remaining implementation decisions

The model is specified, but these choices require approval before coding:

1. Adopt SQLite for the expanded configurable model, or retain one atomic JSON
   aggregate temporarily under the same contract.
2. Approve automatic neutral SKU allocation plus privileged manual assignment,
   including prefix/padding and who can correct identifiers.
3. Choose named admin identity integration, or accept temporary shared-token
   attribution limitations explicitly.
4. Approve the initial taxonomy, selling-unit vocabulary, and attribute pilot list
   from real products.
5. Define reviewer evidence standards for compatibility and load-related claims.
6. Decide whether collection management and structured inquiry lines are needed
   immediately or remain later target-schema extensions.

The desired outcome is a **coherent product catalog with configurable business
vocabulary and controlled admin operations**. Flexibility comes from stable
references, typed definitions, and safe migrations, not from allowing every
technical rule to become an editable enum.
