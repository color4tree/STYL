# STYL Catalog Schema Recommendations — Based on the Admin Forms

**Date:** 1 October 2026  
**Purpose:** Incremental ecommerce and AI-answer improvements for the existing JSON catalog. Companion to STYL_Product_Catalog_Recommended_Changes.md and STYL_Chatbot_Copilot_Implementation.md.

## 1. What was inspected—and what remains unknown

Read-only inspection at https://stylfitness.com/admin covered all three equipment forms (Power Rack, Adjustable Bench, All-in-One Trainer) and five accessory forms (Dip Attachment, Shallow Sockets, Weight Stack Selector Pin, Flat Storage Shelf, Weight Plate Storage Peg B). No field was edited, saved, published, reordered or deleted; no backup/export was performed. The original Equipment → STYL Power Rack view was restored.

**Evidence boundary:** the forms expose labels, control types, values and help text. They do not expose raw JSON, saved property names/types, API requests or the model input. Every schema name and example below is a proposal, not a dump of the current backend. The owner's statement that storage is JSON is the storage basis; the implementation itself was not inspected.

The main change to the earlier advice is important: **compatibility, record-level provenance and accessory package structure already exist.** Extend these and verify the chatbot consumes them; do not recreate them as a second knowledge system.

## 2. Existing capabilities to preserve

| Observed admin capability | Implication |
|---|---|
| Equipment and Accessories management views share a category list | Keep product/management kind separate from merchandising category. A unified internal contract need not merge the existing screens or files. |
| Five compatibility textareas: Upright size, Hole diameter, Hole spacing, Confirmed compatible models, Compatibility limitations | These are existing data sources. Improve typing and interface coverage rather than proposing new duplicate fields. |
| Private source type, source URL, listing ID, captured date and internal notes | Preserve the private/public boundary. Extend provenance selectively; do not pass raw internal notes to customer AI. |
| Accessory Selling unit, Package quantity and package-contents fields | Preserve existing Each/Pair/Set distinctions and confirmed quantities. Equipment may need equivalent fields if useful. |
| Short/full descriptions, feature lists and accessory Public use description | Retain useful presentation copy; separate factual values and safe usage content from unrestricted prose. |
| Published/Draft; optional equipment stock status | Publication and availability are different concepts. Published does not imply in stock. |
| Ordered photo/video list and documented thumbnail/gallery behavior | Retain the current ordering rules while adding optional semantic metadata. |
| Independent CAD/USD prices and optional MSRPs | Localization is working and is not a defect. Preserve all existing rules. |

### Exact pricing behavior observed

The admin help specifies CAD for Canada and unknown locations; USD for identified countries outside Canada. Blank price hides the item in that market. Zero is a valid price. No currency conversion is applied. MSRP is optional, is shown to customers only when greater than price, and does not set checkout/quote price.

Preserve that behavior. In particular, do not reinterpret the field labeled “US price” as US-only when the help explicitly defines the broader non-Canada routing. Equal CAD/USD numbers are not an error. An MSRP equal to price need not be rejected, but must not produce a savings claim or sale badge.

## 3. Highest-priority action: inspect the existing catalog-to-AI adapter

The Dip Attachment form already contains the listed upright sizes and 1-inch hole requirement. The Bench form already contains its approximate product weight. The admin findings therefore do not establish that missing authoring fields caused the failed answers.

Before a broad schema migration, add a read-only diagnostic trace for one failed question:

1. Resolved product identity and selected market.
2. Publication and market-visibility decision.
3. Catalog version and loaded compatibility/specification fields.
4. Public-safe fact object assembled for the response.
5. Exact redacted evidence supplied to Luna, if the answer uses a model call.
6. Model result and final customer-rendered answer.

Check whether the current adapter includes only descriptions/features and omits the existing compatibility/details fields. Also check truncation, stale caches, wrong-product resolution and output postprocessing. These are hypotheses to test, not confirmed bugs.

**Immediate improvement path:** create one server-side public product projection used by product answers. Include the existing compatibility values, specification text, package quantity and relevant limitations even before typed fields are introduced. Do not send entire admin objects. For known scalar facts, use a controlled renderer after product/field selection; do not require the model to rediscover a value in unrelated marketing text.

Unknown stock must not erase an otherwise eligible product answer. Draft and market-hidden records must respect existing publication/visibility rules; do not leak private or hidden commercial data through the bot.

## 4. Proposed incremental product contract

### 4.1 Shared base, category-specific details

Use a shared internal contract across both management views:

- Existing stable product identity; preserve current URLs and IDs.
- Product kind/management partition: equipment or accessory.
- Category identity, separate from kind.
- Name, aliases and optional genuine manufacturer/model/SKU fields.
- Publication state and optional availability.
- Existing market offers and MSRP semantics.
- Presentation content: short description, full description, public use and ordered features.
- Typed specifications plus retained source/display text.
- Compatibility interfaces and limitations.
- Packaging and included components.
- Ordered media metadata.
- Private provenance references.
- Schema version, record revision and last-modified metadata.

Keep the existing storage layout if it works. An adapter can expose a shared contract while equipment and accessories remain in separate JSON collections. A new database, product-information-management platform or mandatory admin application is not needed for the present scope.

### 4.2 Stable identity versus source identity

Do not use a marketplace listing ID as the product ID. The Flat Shelf's private notes establish that one source listing was split into separately priced shelf records. Model this as many product records referencing one source record.

Preserve existing product IDs during migration. If IDs overlap between current collections, resolve this explicitly with a stable identity mapping rather than silently renumbering products. Keep slugs, product IDs, SKUs, manufacturer model numbers and external listing IDs distinct. SKU/model can remain unknown where not established.

Add a family relationship only when useful: Open and Flat shelves can remain separately sellable products with a shared family/source. Peg A and Peg B must remain distinct products; do not merge them merely because their names or lengths resemble each other.

### 4.3 Structured specifications beside original text

Retain current Dimensions, Weight and Material display text. Add typed values incrementally:

- Measurement: amount, unit, measurement scope and approximate/nominal qualifier.
- Material: component plus material; finish is a separate property.
- Capacity: rated quantity, applicable component/configuration, conditions and evidence.
- Package contents: item, quantity and inclusion status.

Examples grounded in the forms:

- Trainer: overall height, upright height, rack width and Smith-bar overall width are separate measurements.
- Shelf: usable storage length and mounting length are separate.
- Selector Pin: component diameter and overall length do not establish required machine-bore diameter or usable insertion length.
- Bench: product mass is not safe load capacity.
- Trainer: maximum stack already includes its micro increment; cable ratio is not itself a manufacturer-verified handle-force figure.
- Jargon such as “stainless-look” describes appearance, not verified composition.

Use a category field registry to define valid keys, types, unit families and scope. Avoid one unrestricted key/value text map as the sole normalized schema. Do not make rack-specific fields mandatory for benches or sockets.

## 5. Compatibility needs interfaces, not only a rack template

The five existing textareas are a good starting point, but they are rack-oriented. Introduce category-aware interfaces while preserving all source text and caveats.

| Product/interface | Structured concepts to add or clarify |
|---|---|
| Power rack | Interface provided: upright dimensions/nominal labels, holes, hole pattern and relevant spans. |
| Dip and other rack attachments | Interface required: listed upright size, hole diameter and any genuinely required mounting geometry. |
| Storage shelf | Mounting span with reference points, bolt pattern and fit limitations. Do not infer span from “3x3.” |
| Storage peg | Separate rack-mount requirements from accepted plate-interface information. |
| Selector pin | Own shaft dimensions plus separately confirmed mating-machine requirements. |
| Socket | Socket opening size and square-drive interface, not rack upright/hole fields. |
| Landmine | Rack-side requirements separate from accepted barbell interface. |

### Proposed compatibility model

- `interfaceType`: rack_mount, shelf_mount, plate_storage, selector_pin, socket_drive, barbell_receiver, or an approved category-specific type.
- `role`: provides, requires or accepts.
- `constraints`: typed attribute/operator/value with source and applicability.
- `limitations`: explicit exclusions and unverified combinations.
- `verifiedPairs`: exact target product/variant and evidence-supported result, conditions and revision applicability.

Conditions within a requirement group are all required (AND). Alternative approved configurations are separate groups (OR). Do not interpret the Dip's dual 3-inch/75-mm wording as two independently verified fit configurations until the owner confirms its meaning.

Classify attributes as published requirements, exact-fit verification details or optional descriptive attributes. Missing verification details may prevent a tested-fit claim, but must not prevent stating published size requirements. Do not invent a required rack-depth check for an attachment whose reviewed requirements do not call for it.

### Answer outcomes

1. **Listed requirements:** direct specification answer.
2. **Conditional match:** a known requirement matches; relevant customer inputs are missing.
3. **Requirements match, exact fit unverified:** all listed constraints match but no verified pairing exists.
4. **Known mismatch:** comparable, approved dimensions/requirements conflict.
5. **Conflicting or insufficient evidence:** answer known facts, identify the specific unresolved part.
6. **Verified fit:** exact approved pairing, scope and conditions support the claim.

A free-text “Confirmed compatible models” value is not automatically a machine-verifiable relationship. Preserve it as merchant-provided wording and convert it to explicit product/model references through review.

## 6. Packaging and variants: build on what already exists

### Packaging

Accessory unit and quantity fields are already structured. Preserve these confirmed cases:

- Selector Pin: Set, quantity 2; package text identifies two pins and private notes confirm the offer covers the set.
- Shallow Sockets: Each, quantity 1; size choices do not mean both sockets are supplied together.
- Flat Shelf and Peg B: Each, quantity 1.
- Dip: unit, quantity and package contents are unspecified; do not auto-fill them.

Clarify what Package quantity counts. Recommended meaning: the number of primary merchandise units in one selling unit; separate included hardware/components have their own quantities. A shelf with fasteners is still one shelf, not a package quantity inflated by counting every fastener. Define category exceptions explicitly.

Add an included-components list with `included`, `excluded` or `unknown` status. Retain human-readable contents. Do not infer a Dip mounting pin from “pin-mounted,” or a photographed bundle from an image.

### Variants and descriptive options

The current Colour/options field mixes colours, size choices and finishes. Separate:

- Selectable option definitions and actual sellable variants.
- Non-selectable finish/material descriptions.
- Supported configurations that do not change the purchased item.

Sockets' 34/36-mm choice is a strong candidate for variant modeling. Confirm existing buyer selection and fulfillment behavior before changing it. Selector Pin colours do not establish whether the buyer chooses a colour or receives an assorted set. Rack colours also require confirmation of actual sale/availability behavior.

Each genuine variant needs a stable identity, option values and explicit applicability of specifications/offers/stock. Do not create invented SKUs or assume parent stock/price automatically applies. If inheritance is used, define override semantics: an absent override can mean inherit, while an explicit unavailable/hidden state must not accidentally inherit a price.

## 7. Provenance and public/private separation

Record-level provenance already exists. Keep it private and extend it only where useful.

- Maintain source-to-product references, including one source supporting multiple products.
- Add reviewer/review date and field-level evidence for safety/fit claims, overrides or conflicting values.
- Keep captured dates unknown where blank. Do not substitute today's inspection date for the original capture date.
- Separate observed, approved, unknown and conflicted facts. Review known fields independently.
- Do not force every established published product through a new global approval block before the bot can state its existing merchant-provided specifications.
- Do not let a speculative normalized value override existing merchant text. Flag a genuine disagreement at the field level.

**Public AI projection:** allowlist the customer-safe product fields. Exclude raw source URLs/listing IDs, private migration notes, unpublished records and any secrets. Only promote a specific reviewed fact from private notes, such as the approved two-pin sale quantity or a shelf's sold-separately photo context. A model should not decide what private information is safe to disclose.

The projection should preserve useful merchant wording and uncertainty without pretending all listed facts are independently manufacturer-tested. Source identifiers shown to customers should map to approved public product/manual references, not internal audit notes.

## 8. Media changes informed by the actual controls

Preserve current behavior: maximum 12 media entries; the first item opens the gallery; first photo is the thumbnail; a first video's generated poster is the fallback when there are no photos. The current “Use as thumbnail and show first” operation changes ordering; do not silently replace that behavior.

Add optional metadata:

- Stable asset ID, media type and display order.
- Product/variant applicability.
- Accessible alt text and a caption.
- Context: this product, installation example, multi-product arrangement, or other reviewed context.
- Related products shown and a public-safe inclusion/exclusion note when needed.
- For video: approved transcript/summary, timestamps and review version where useful.
- Operational metadata: format, dimensions/duration, generated poster and processing state.

The Flat Shelf's notes specifically warn that photos show mixed arrangements while the shelf is sold individually. Promote that approved meaning into visible media/package context instead of exposing the private note. This helps both shopping clarity and image-based answers.

Existing help already recommends keeping important information in text, not only audio. Continue that rule. Gemini video output and Luna image observations are observations, not automatic authoritative specifications. Never infer load ratings, exact fit or included bundles from appearance.

The admin also documents conversion and discarding uploaded originals. Preserve the current pipeline unless deliberately changed; record processing provenance and document the retention decision. Do not promise original-file recovery or new retention behavior without implementing it.

## 9. Ecommerce improvements beyond AI

### Admin parity, without forcing identical forms

Consider exposing optional stock status, SKU/model identity and warranty reference on accessory forms where relevant. Consider package-unit/contents structure and public-use content for equipment. Their absence from the inspected form is not proof that the backend lacks them; inspect the real types first.

### Category and merchandising semantics

Use stable category identities with changeable display labels. Keep product kind, category, tags, family relationships and storefront display order separate. The UI already explains that Featured is a tag, not listing order; preserve that distinction.

### Publication, stock and market visibility

Treat these independently. Not specified stock remains unknown. Published is not an availability guarantee. Blank market price remains hidden and numeric zero remains valid. Use the same visibility/offer rules for the storefront, AI recommendations and transaction/quote flow.

### Safe JSON persistence

Before implementing, inspect whether the current save layer already provides these protections; add only missing behavior:

- Server-side schema validation and structured error messages.
- Schema version and record revision.
- Optimistic concurrency checks so stale admin saves do not overwrite newer edits.
- Atomic writes appropriate to the actual host/storage—not a process-local lock that fails across instances.
- Referential integrity for product/variant/media/source links.
- Reversible archival or an explicit deletion policy preserving references.
- Versioned publication/cache invalidation and rollback.

For money, validate text inputs and preserve null versus zero. If changing numeric representation, migrate to integer minor units or a deliberate decimal representation with tests. Do not infer the current JSON representation from a text input, and do not change currency routing or introduce FX conversion.

## 10. Illustrative additive JSON fragment

**Proposed field names only.** This fragment shows how to retain current Dip wording while adding structured interpretation. It is not the existing JSON schema or a production-ready whole product record. Preserve the real product ID and current field names through an adapter when implementing.

```json
{
  "schemaVersion": 2,
  "compatibility": {
    "merchantText": {
      "uprightSize": "3” × 3” / 75 × 75 mm (both stated)",
      "holeDiameter": "1”",
      "holeSpacing": null,
      "confirmedModels": null,
      "limitations": null
    },
    "interfaces": [
      {
        "type": "rack_mount",
        "role": "requires",
        "constraints": [
          {
            "attribute": "upright_size_label",
            "sourceStatedLabels": ["3 x 3 in", "75 x 75 mm"],
            "interpretationState": "needs_review",
            "physicalDimensions": null,
            "reviewQuestion": "Confirm nominal wording, supported alternatives or variant-specific fit"
          },
          {
            "attribute": "rack_hole_diameter",
            "sourceStatedValue": {"amount": "1", "unit": "in"},
            "classification": "listed_required",
            "evidenceBasis": "merchant_compatibility_field"
          }
        ]
      }
    ],
    "verifiedPairs": []
  },
  "package": {
    "sellingUnit": null,
    "primaryItemQuantity": null,
    "contentsState": "unknown",
    "components": []
  }
}
```

An empty verified-pair list means no verified pairing is recorded, not that the product fits nothing. Unknown Dip packaging remains unknown. A structured interpretation awaiting review must not suppress the clear direct answer that the merchant currently lists those upright sizes and a 1-inch hole requirement.

## 11. Migration and implementation sequence

### Phase A — Inspect and fix the adapter

Inspect actual JSON types, save handlers and public/AI serializers in the repository. Record a mapping from observed admin controls to real keys. Add a public-safe product projection and diagnostic tests. Preserve current merchant text and commerce rules. Stop if the current product ID/market cannot be resolved safely.

### Phase B — Add typed fields without deleting legacy text

Add schema versioning, category-specific measurements and compatibility interfaces. A migration parser may suggest typed values, but ambiguous values remain review tasks. Do not parse a blank as false/zero or silently turn dual nominal units into equivalence. Retain original strings and existing URLs/IDs.

### Phase C — Improve authoring

Add category-aware editors, reusable package components, actual variants, optional admin parity and selective evidence review. Prioritize Dip, Bench, Trainer, Sockets, Selector Pin and Shelf examples. No mandatory platform replacement.

### Phase D — Publish safely and test

Validate, review changed facts, publish one canonical version and invalidate caches. Render product pages and construct AI context from the same approved values. Keep a rollback path. Do not maintain indefinite manual dual-writing of old and new facts; designate one authoring source and derive compatibility views during migration.

## 12. Acceptance criteria

These are proposed tests, not executed application tests:

1. Dip upright-size and 3x3-fit questions include the existing hole requirement rather than returning a false unknown.
2. An unknown pin inclusion or load rating does not suppress known dimensions.
3. Bench product weight is returned from its current Weight field and never used as load capacity.
4. Trainer width scopes and stack/micro relationships remain distinct.
5. Selector Pin is sold as a two-pin set; Sockets as one selected size, not both.
6. Shelf photos cannot create a bundled-inclusions claim.
7. Peg B's caveat is retained even though it currently appears inside Upright size rather than Compatibility limitations.
8. Socket drive size and selector-pin dimensions are not forced into rack-only fields.
9. Blank market price hides the item; zero remains valid; CAD/unknown and non-Canada USD routing remains unchanged.
10. MSRP does not set transactional price or create savings when it is not higher.
11. Unspecified stock is not “in stock”; draft/private data is not leaked.
12. Raw private provenance and migration notes are absent from model input and customer responses.
13. Existing media order/thumbnail behavior remains unchanged.
14. Product-page display, AI projection and offer selection reflect the intended catalog revision and market.
15. Stale/concurrent admin saves and rollback are tested against the actual deployment storage before release.

**Success is not merely more completed fields.** Track false unknowns, unsupported compatibility claims, wrong-product answers, stale answers and private-data leakage separately.

## Source references

- STYL admin, https://stylfitness.com/admin — Equipment → Equipment essentials & details, Equipment details, Compatibility, Photos & videos, Customer-facing descriptions, Features, Featured tag and Internal source / provenance.
- STYL admin, https://stylfitness.com/admin — Accessories → Accessory essentials, Specifications & package contents, Customer-facing descriptions/Public use description, Features, Photos & videos, Compatibility and Internal source / provenance.
- Full forms inspected: STYL Power Rack; STYL Adjustable Bench; STYL All-in-One Trainer; STYL Dip Attachment; STYL Shallow Sockets; STYL Weight Stack Selector Pin; STYL Flat Storage Shelf; STYL Weight Plate Storage Peg B.
- Owner context: JSON storage, small catalog/low traffic, GPT-6 Luna text/images, Gemini video and functioning location-aware pricing.

The admin inspection supports the observations above; it does not establish raw backend schema or the cause of the chatbot's previous failures. Recommendations require repository mapping and testing before implementation.
