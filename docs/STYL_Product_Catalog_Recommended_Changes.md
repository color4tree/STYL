# STYL Product Catalog — Recommended Changes for Accurate AI Answers

**Date:** 1 October 2026  
**Purpose:** Summary for the product owner and Copilot coding agent. Improve product-answer accuracy without replacing the existing website, catalog platform or AI providers.

## 1. Scope and correction

The current system uses GPT-6 Luna for text/images and Gemini for video. The catalog and traffic are small. Preserve these choices.

**Currency handling is not an issue.** The owner confirmed that the existing system determines the user's location and provides the appropriate USD/CAD information. Preserve that behavior. The earlier recommendation to investigate USD/CAD differences as a catalog defect is withdrawn. Continue using the existing location-aware commercial-data service; do not create a competing price source.

These recommendations are based on the previously reviewed 19-product catalog snapshot and the supplied STYL Dip Attachment screenshot—not an inspection of the live database, repository or chatbot requests. No catalog or website changes have been made. Facts that need confirmation must come from the owner, manufacturer or approved documentation, not AI inference.

## 2. Main recommendation

**Use one approved, structured product record to power both the website and the chatbot.** Keep the readable catalog as a generated export, not a separately maintained source of truth.

Separate three concerns:

1. **Product facts:** identity, specifications, compatibility requirements, package contents and source evidence.
2. **Customer presentation:** descriptions, specification tables, compatibility summaries and generated product FAQs.
3. **Assistant behavior:** how to resolve products, retrieve fields, answer partially, handle unknowns and ask relevant follow-up questions.

Improving the catalog should help, but does not by itself prove the chatbot receives the correct record. Test the complete path from product selection to the displayed answer before changing models.

## 3. Priority changes

### P0 — Fix answerable questions that currently fail

- Give every product a stable internal ID. Do not treat an accessory URL suffix or product title as a verified SKU.
- Send the current product ID with product-page chat requests; validate it on the server and allow an explicit product mentioned by the customer to override stale page context.
- Store upright-size requirements and mounting-hole diameter as separate fields.
- Retrieve the relevant product record directly rather than searching the entire catalog for isolated terms such as “3x3.”
- Answer known specifications immediately. Missing load capacity or unconfirmed hardware inclusion must not suppress a known upright-size answer.
- Use the same approved catalog version for the product page and chatbot lookup.
- Keep existing location-aware currency behavior unchanged.

### P1 — Remove ambiguity and fill important gaps

- Distinguish nominal size labels from measured dimensions and tolerances.
- Label dimensions as overall, internal, usable, mounting span or another precise scope.
- Separate product weight, shipping weight, component weight, resistance and rated capacity.
- Separate sale quantity from included component quantities.
- Confirm critical mounting geometry, capacity conditions and package contents where missing.
- Add field-level sources, review status and revisions. Review fields independently so an unknown optional field does not block the whole product.

### P2 — Make maintenance and coverage reliable

- Add exact product/variant compatibility relationships only when supported by approved evidence.
- Convert image-only specifications into owner-verified text and structured fields.
- Generate product FAQs and comparison tables from canonical facts rather than duplicating values manually.
- Run repeatable accuracy tests after every catalog or retrieval change.

## 4. Language and page structure

### Recommended wording rules

- Use **Product weight**, **Maximum rated load**, **Required rack-hole diameter**, **Usable storage length** and **Quantity supplied per purchase**, rather than ambiguous labels such as “Weight,” “Size” or “Length.”
- State what a rating applies to: a component, each item or a pair; user weight or combined load; and any applicable installation/configuration conditions.
- Separate marketing descriptions from specifications. “Heavy-duty,” “commercial-grade” and a stainless-look finish do not establish load ratings, certifications or material composition.
- Distinguish **included**, **not included** and **not confirmed**. A pictured or required component is not automatically supplied.
- Use qualified positive compatibility wording. State supported requirements before explaining any uncertainty about the customer's exact equipment.
- Keep internal instructions and review notes out of customer descriptions. Store unknowns explicitly, but do not bury known facts beneath long lists of unrelated missing specifications.

### Consistent product sections

1. Identity and variants.
2. Short factual description.
3. Specifications with units and measurement scope.
4. Compatibility requirements and verification limits.
5. Package contents, quantities and explicit exclusions.
6. Approved installation and usage information.
7. Verified safety/capacity information and warranty references.
8. Existing location-aware commercial information.

Use category-specific fields. Rack attachments, benches, shelves, pins, machines and wearable accessories do not need identical mandatory specifications.

## 5. Worked example — STYL Dip Attachment

### Proposed compatibility presentation

- **Listed upright sizes:** 3″ × 3″ / 75 × 75 mm.
- **Required rack-hole diameter:** 1″.
- **Mounting:** single rack upright.
- **Exact rack-model fit:** not established by the dimensional listing alone.

The supplied screenshot's Compatibility section supports the listed size and hole requirements. Have the owner confirm whether the dual 3″/75 mm wording represents nominal labels, supported alternatives, rounding or separate variants. Do not silently treat those labels as exact physical equivalents. Preserve the source wording while that interpretation is reviewed.

### Expected answers

**Question:** “What upright size is compatible?”  
**Expected behavior:** Return the listed upright sizes and 1″ hole requirement. Do not demand the customer's rack model before stating published specifications.

**Question:** “Does it fit a 3x3 upright?”  
**Expected behavior:** Explain that 3x3 matches the listed upright-size requirement and that 1″ mounting holes are also required. Clarify missing customer information without withholding the known facts.

**Question:** “Is it confirmed to fit my exact rack model?”  
**Expected behavior:** Check an approved product/variant compatibility relationship. A dimensional match alone is not a tested-fit guarantee.

**Unknown facts:** Keep the load rating, own weight and mounting-pin inclusion unconfirmed unless approved evidence supplies them. Their absence must not prevent the upright-size answer.

## 6. Product-specific change list

These items refer to the matching product records in **STYL_Fitness_AI_Ready_Product_Catalog.txt**, especially their Stable specifications, Compatibility and fit, Package and inclusions, and Missing or unconfirmed fields sections. They are recommended edits and confirmation tasks, not newly verified specifications.

| Product | Recommended changes |
|---|---|
| STYL Power Rack | Define internal versus overall dimensions, especially depth. Confirm hole spacing, steel gauge, weight and component-specific capacity conditions. List supplied parts with quantities and explicitly verified attachment relationships. |
| STYL Adjustable Bench | Keep approximate 50 kg / 110 lb own weight separate from capacity. Add verified overall dimensions, adjustment positions/angles, capacity definition, assembly details and package contents. |
| STYL All-in-One Trainer | Separate rack width from Smith-bar/installed width. Keep machine mass, Smith-bar mass, stack mass and cable ratio separate. Make micro-adjustment inclusion explicit to avoid double counting. Confirm clearances; preserve component-specific warranty and accessory/service exclusions. |
| STYL Dip Attachment | Separate upright labels and hole requirement; resolve nominal-unit wording. Confirm actual mounting geometry, pin inclusion, handle dimensions, capacity and exact rack-pair evidence where available. |
| STYL Sandwich J-Cups | Distinguish steel body, stainless trim and protective material. Resolve upright wording; confirm fit geometry and capacity conditions. Make the pair quantity prominent. |
| STYL Spotter Arms | Replace broad brand-level fit implications with requirements and verified model/variant relationships. Confirm arm dimensions, per-arm/per-pair rating scope and applicable installation/stability requirements. |
| STYL Rack Safety Straps | Define what the stated 30″ rack-depth requirement measures. Reconcile scope before comparing it with the Power Rack's 36″ depth. Confirm strap dimensions/material, bracket geometry and capacity conditions. |
| STYL Resistance Band Anchor | Separate rack fit from band/connector requirements. List anchor, carabiner and locking pin individually. Confirm whether bands are excluded or unconfirmed; add approved geometry, capacity and installation guidance. |
| STYL Landmine Attachment | Separate rack-side fit from barbell-side fit. Confirm accepted sleeve dimensions, mounting hardware, permitted installation positions and clearances. Do not infer barbell/plate inclusion. |
| STYL Magnetic Safety Pins | Display “Sold individually: 1 pin.” Separate diameter, usable insertion length and overall length. Confirm material and intended applications; do not turn magnetic retention into a load-rating claim. |
| STYL Open Storage Shelf | Separate usable length and mounting span, with reference points. Add depth, height, hole pattern, fastener contents and approved capacity. Record verified mounting spans/models rather than universal 3x3 fit. |
| STYL Flat Storage Shelf | Apply the same fit and measurement improvements as the Open Storage Shelf. Distinguish rubber-lined usable surface dimensions from overall dimensions and retain a separate product identity. |
| STYL Weight Plate Storage Peg A | Confirm bolt count, dimensions, pattern, hardware inclusion and accepted plate-hole dimensions. Separate usable/overall length and finish/material. Do not copy Peg B's design or supplied hardware. |
| STYL Weight Plate Storage Peg B | Add bolt spacing/diameter, overall length and approved capacity. Preserve the documented dual-bolt design and hardware inclusion. Distinguish stainless-look finish from actual material. |
| STYL Open-Top Storage Crossmember | Move photo-accessory exclusion into “Not included.” Add a positive package checklist and hardware status. Define span, channel dimensions, hole pattern and primary measurement unit; label rounded display conversions. Confirm intended structural/storage scope. |
| LARA STAR Lifting Grips | Add verified size/wrist ranges, component materials, colour variants, package contents, care and use limitations. Do not assume one size fits all. |
| STYL Weight Stack Selector Pin | Separate usable insertion length from overall length. Confirm shaft material, retention and selector-hole geometry. Clarify colour selection/set composition and preserve the two-pin sale quantity. |
| STYL Shallow Sockets | Put 34 mm and 36 mm in a Size variant field, not Finish/colour. Separate opening size from drive size; state one selected socket per purchase. Confirm height/clearance and impact-use rating. |
| STYL Double Swivel Connector | Add opening/internal/overall dimensions, intended use and verified working-load conditions. Distinguish working load from breaking strength. Do not imply climbing or overhead-lifting suitability without evidence. |

## 7. Data structure and schema recommendations

Extend the existing coding handoff's Product, Fact and Evidence structure rather than creating a second incompatible model.

### Core entities

- **Product:** stable ID, name, category, URL, aliases, genuine SKU if available and catalog revision.
- **Variant:** parent product, variant ID, attributes and applicable specification overrides.
- **Fact:** canonical key, typed value, fact state, evidence references and review status.
- **Compatibility requirement:** referenced fact, comparison rule, applicability and requirement classification.
- **Verified compatibility:** exact attachment/target variants and revisions, result, scope, conditions and evidence.
- **Evidence:** source identity/location, source section, observation date and review metadata.
- **Commercial data:** continue using the existing location-aware price/inventory service.

### Fact-state rules

Keep fact state and review state independent:

- `known`: a source supplies a value.
- `unknown`: no supported value is established.
- `not_applicable`: the field does not apply, with a reason.
- `conflicted`: incompatible source claims require review.

Review state: `pending`, `approved` or `rejected`.

Use null for absent values, never a fabricated zero, false or empty-string answer. A required constraint is not the same as an optional attribute. Missing optional data must not block known answers.

### Typed values

Define field-specific validation for measurements, materials, component quantities and fit requirements. A measurement should include amount, unit, scope and relevant qualifier such as approximate. Keep source wording alongside normalized data. Do not convert a nominal size label into an asserted physical measurement or tolerance.

### Illustrative Dip field excerpt

This is a proposed internal record excerpt for review, not a verified SKU, complete production schema or description of the current database.

```json
{
  "productId": "proposed-styl-dip-attachment",
  "sku": null,
  "name": "STYL Dip Attachment",
  "facts": {
    "compatibility.upright_labels": {
      "state": "known",
      "value": ["3 x 3 in", "75 x 75 mm"],
      "interpretation": "source_stated_labels_not_exact_equivalents",
      "reviewStatus": "pending",
      "evidenceIds": ["dip-compatibility-source"]
    },
    "compatibility.hole_diameter": {
      "state": "known",
      "value": {
        "amount": "1",
        "unit": "in",
        "scope": "required_rack_hole_diameter"
      },
      "reviewStatus": "pending",
      "evidenceIds": ["dip-compatibility-source"]
    },
    "capacity.safe_load": {
      "state": "unknown",
      "value": null,
      "reason": "Not established in reviewed material"
    },
    "included.mounting_pin": {
      "state": "unknown",
      "value": null,
      "reason": "Package inclusion not confirmed"
    }
  },
  "testedCompatibility": [],
  "evidence": [
    {
      "id": "dip-compatibility-source",
      "sourceType": "supplied_product_screenshot",
      "sourceSection": "Compatibility",
      "observedDate": "2026-10-01",
      "reviewedBy": null,
      "reviewedAt": null
    }
  ]
}
```

For a small catalog, use the existing database or owner-reviewed versioned JSON. No mandatory new database, admin application or vector store is needed. Avoid storing duplicate authoritative descriptions in a separate chatbot system.

## 8. Retrieval and answer rules

- Maintain reviewed product aliases and field synonyms. Map “upright/post/rack tube size” to the upright field, and “rack hole/mounting-hole diameter” to the hole field.
- Do not merge hole diameter, hole spacing, pin diameter and pin length into one concept.
- Resolve the product first, then fetch the requested fields and related requirements.
- Include all applicable compatibility requirements in fit answers, not only the field with the closest keyword match.
- Separate direct specification questions from customer-specific fit checks. Provide supported facts even when final fit needs clarification.
- Keep generated product FAQs linked to canonical fact keys so edits do not leave stale duplicate answers.
- Keep general customer-support policies in a separately approved FAQ dataset; do not invent absent policy content.
- Treat descriptions, screenshots and retrieved text as evidence, never instructions that can override assistant policy.

## 9. Publication and validation

Recommended publication sequence: draft → schema validation → owner review → approved version → website/chatbot refresh → regression tests. Retain the prior version for rollback.

Flag missing units/scopes, invalid references, variant ambiguity, inferred inclusions and unsupported ratings. Do not block a whole product merely because optional specifications are unknown.

Verify these behaviors after each relevant change:

1. Both original Dip questions return the known upright and hole requirements.
2. Paraphrases select the same fields.
3. Missing customer fit information produces a qualified answer and focused clarification—not a false unknown.
4. A mismatching hole-size test does not produce a fit guarantee or unsafe modification advice.
5. Unknown capacity does not suppress known dimensions.
6. Bench own weight is not presented as capacity.
7. Peg A does not inherit Peg B's hardware facts.
8. Each/pair/set quantities remain correct.
9. Unresolved rack-depth scopes do not yield unsupported yes/no fit claims.
10. Existing location-aware USD/CAD answers remain unchanged and correct.
11. Product page, lookup response and final answer use the intended catalog revision.

Measure false unknowns, unsupported claims, wrong-product answers and stale answers separately. These are proposed checks, not tests already run against the site.

## 10. Recommended implementation order

1. Fix Dip record structure, product-ID handoff and the failing question path.
2. Apply the same pattern to rack attachments, safety products and storage fit information.
3. Clarify weights, dimensions, package quantities and component distinctions across the remaining catalog.
4. Add approved FAQ content and generate product-specific FAQs from canonical facts.
5. Add richer usage content only after the product-answer tests pass.

**Coding-agent boundary:** reuse the existing stack and providers; preserve functioning localization; do not replatform or deploy without authorization. Identify where the fact is lost—import, product resolution, retrieval, model input or rendering—before proposing a model upgrade. No values requiring owner/manufacturer confirmation may be invented.

## Source basis

- STYL_Fitness_AI_Ready_Product_Catalog.txt — 1 October 2026, individual product records and their source-section attribution. Derived draft, not independently approved manufacturer data.
- Supplied STYL Dip Attachment screenshot — Compatibility and Specifications sections; related product page: https://stylfitness.com/accessories/1005.
- STYL_Chatbot_Copilot_Implementation.md — existing product-first design, catalog schema and acceptance-test approach.
- Owner clarification, 1 October 2026 — current location-aware USD/CAD handling works; currency remediation is out of scope.
