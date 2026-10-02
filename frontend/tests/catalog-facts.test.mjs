import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { test } from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const nativeRequire = createRequire(import.meta.url);
const modules = new Map();
function load(relative) {
  const filename = path.join(root, relative);
  if (modules.has(filename)) return modules.get(filename);
  const loaded = { exports: {} };
  modules.set(filename, loaded.exports);
  const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const requireSource = specifier => {
    if (specifier === "react" || specifier === "react/jsx-runtime") return nativeRequire(specifier);
    const base = specifier.startsWith("@/") ? path.join(root, "src", specifier.slice(2)) : path.resolve(path.dirname(filename), specifier);
    return load(path.relative(root, `${base}.ts`));
  };
  new Function("require", "module", "exports", compiled)(requireSource, loaded, loaded.exports);
  modules.set(filename, loaded.exports);
  return loaded.exports;
}
const facts = load("src/lib/catalogFacts.ts");
const api = load("src/lib/api.ts");
const catalog = load("src/lib/publicCatalog.ts");
const Editor = load("src/components/CatalogFactsEditor.tsx").default;
const revision = "a".repeat(64);
const fixture = () => ({
  ...facts.emptyCatalogFacts(),
  reviewed: true,
  options: { colors: ["Black", "White"], sizes: ["Small"], finish: "Powder coat", note: "Informational only" },
  measurements: [
    { kind: "width", scope: "rack", amount: "1200.50", unit: "mm", qualifier: "nominal", note: "" },
    { kind: "width", scope: "smith_bar", amount: "1500", unit: "mm", qualifier: "exact", note: "" },
    { kind: "length", scope: "usable_storage", amount: "30", unit: "cm", qualifier: "approximate", note: "Usable portion" },
  ],
  materials: [{ component: "Frame", value: "Steel" }],
  interfaces: [{ kind: "socket_drive", role: "requires", constraints: [{ attribute: "driveSize", operator: "eq", value: "0.5", unit: "in" }], limitations: "Fit is not confirmed" }],
  components: [{ name: "Socket", quantity: 1, status: "included" }, { name: "Handle", quantity: null, status: "excluded" }],
});
const publicItem = { id: 1, name: "Typed test", category: "Handle", price: 19.95, currency: "CAD", slug: "typed-test" };

test("FACT-001: empty legacy metadata remains absent, including merely rendering the editor", () => {
  assert.equal(facts.parseCatalogFacts(undefined), null);
  assert.equal(facts.parseCatalogFacts(null), null);
  assert.deepEqual(facts.catalogFactsPatch(undefined, false), {});
  let edits = 0;
  const html = renderToStaticMarkup(createElement(Editor, { category: "Handle", onChange: () => edits++ }));
  assert.match(html, /Reviewed product facts/);
  assert.match(html, /Add product facts/);
  assert.doesNotMatch(html, /Add measurement/);
  assert.equal(edits, 0);
  assert.equal("catalogFacts" in api.catalogAdminMetadata({ id: 1 }), false);
});

test("FACT-002: runtime validation rejects unknown schema, keys and malformed nested fields", () => {
  assert.equal(facts.isCatalogFacts(fixture()), true);
  for (const value of [undefined, null, [], {}, { ...fixture(), schemaVersion: 2 }, { ...fixture(), reviewed: "true" }, { ...fixture(), sourceUrl: "unexpected" }, { ...fixture(), options: { ...fixture().options, variants: [] } }, { ...fixture(), measurements: [{ ...fixture().measurements[0], scope: "banana" }] }]) {
    assert.equal(facts.isCatalogFacts(value), false);
  }
  assert.throws(() => facts.parseCatalogFacts({ ...fixture(), schemaVersion: 5 }), /Invalid product facts/);
});

test("FACT-003: amounts remain exact decimal strings, with positive numbers and unit families enforced", () => {
  const source = fixture();
  assert.equal(facts.parseCatalogFacts(source).measurements[0].amount, "1200.50");
  for (const amount of ["0", "-1", "", " 1", "1e3", "1/2", "Infinity", "NaN", ".5", "1.", "1\n", "1\r", 20, true]) {
    assert.ok(facts.validateCatalogFacts({ ...source, measurements: [{ ...source.measurements[0], amount }] }).some(issue => issue.path === "measurements.0.amount"));
  }
  for (const kind of ["length", "diameter", "width"]) {
    assert.ok(facts.validateCatalogFacts({ ...source, measurements: [{ ...source.measurements[0], kind, unit: "kg" }] }).some(issue => issue.path === "measurements.0.unit"));
  }
  for (const kind of ["weight", "load_capacity", "resistance", "increment"]) {
    assert.deepEqual(facts.unitsForMeasurement(kind), ["kg", "lb"]);
  }
});

test("FACT-004: lists, labels and component quantities are bounded; interface constraints preserve listed text", () => {
  for (const quantity of [0, -1, 1.5, Number.NaN, Infinity, "2", facts.FACT_LIMITS.quantity + 1]) {
    assert.ok(facts.validateCatalogFacts({ ...fixture(), components: [{ name: "Pin", quantity, status: "included" }] }).some(issue => issue.path === "components.0.quantity"));
  }
  assert.equal(facts.isCatalogFacts({ ...fixture(), components: [{ name: "Pin", quantity: null, status: "unknown" }] }), true);
  assert.equal(facts.isCatalogFacts({ ...fixture(), materials: Array(facts.FACT_LIMITS.materials + 1).fill({ component: "Product", value: "Steel" }) }), false);
  assert.equal(facts.isCatalogFacts({ ...fixture(), options: { ...fixture().options, colors: ["x".repeat(facts.FACT_LIMITS.optionLabel + 1)] } }), false);
  const int = fixture().interfaces[0];
  assert.equal(facts.isCatalogFacts({ ...fixture(), interfaces: [{ ...int, constraints: [{ ...int.constraints[0], value: "1/2 nominal", unit: "" }] }] }), true);
});

test("FACT-005: editing values clears review while unchanged values do not dirty facts", () => {
  const current = fixture();
  assert.equal(facts.editCatalogFacts(current, { packageNote: "" }), current);
  const next = facts.editCatalogFacts(current, { packageNote: "Two separate cartons" });
  assert.equal(next.reviewed, false);
  assert.equal(current.reviewed, true);
  assert.equal(current.packageNote, "");
  assert.deepEqual(facts.catalogFactsPatch(next, true), { catalogFacts: next });
  assert.deepEqual(facts.catalogFactsPatch(current, false), {});
  assert.deepEqual(facts.catalogFactsPatch(null, true), { catalogFacts: null });
});

test("FACT-006: admin create is v2, updates use pinned revisions and never resubmit server review stamps", () => {
  const original = { ...publicItem, ...api.catalogAdminMetadata({ schemaVersion: 1, revision, catalogFacts: fixture(), catalogFactsReviewedAt: "2026-10-02T01:00:00Z" }), colourOptions: "Raw legacy options", packageQuantity: 4 };
  const untouched = api.catalogMutationPayload(original, true, false);
  assert.equal(untouched.expectedRevision, revision);
  assert.equal(untouched.schemaVersion, 2);
  assert.equal(untouched.colourOptions, "Raw legacy options");
  assert.equal(untouched.packageQuantity, 4);
  for (const key of ["revision", "catalogFacts", "catalogFactsReviewedAt"]) assert.equal(key in untouched, false);
  const changed = api.catalogMutationPayload(original, true, true);
  assert.deepEqual(changed.catalogFacts, fixture());
  const created = api.catalogMutationPayload({ ...publicItem }, false, false);
  assert.equal(created.schemaVersion, 2);
  assert.equal("expectedRevision" in created, false);
  assert.equal("catalogFacts" in created, false);
  assert.equal(original.catalogFactsReviewedAt, "2026-10-02T01:00:00Z");
});

test("FACT-007: omitted mock revisions stay unavailable, no guessed optimistic-lock tokens", () => {
  const metadata = api.catalogAdminMetadata({ id: 1 });
  assert.equal(metadata.schemaVersion, 1);
  assert.equal(metadata.revision, undefined);
  assert.throws(() => api.catalogMutationPayload(metadata, true, false), /no usable revision/);
  for (const value of ["", "1", "z".repeat(64), "a".repeat(63), `${revision}\n`, 123]) assert.equal(api.isCatalogRevision(value), false);
  assert.throws(() => api.catalogAdminMetadata({ revision: "invalid" }), /Invalid catalog revision/);
});

test("FACT-008: public typed facts must be reviewed and valid; unreviewed drafts never become rows", () => {
  assert.equal(catalog.isPublicCatalogItem({ ...publicItem, catalogFacts: fixture() }), true);
  assert.equal(catalog.isPublicCatalogItem({ ...publicItem, catalogFacts: { ...fixture(), reviewed: false } }), false);
  assert.equal(catalog.isPublicCatalogItem({ ...publicItem, catalogFacts: { ...fixture(), extra: true } }), false);
  assert.deepEqual(facts.reviewedFactRows({ ...fixture(), reviewed: false }), []);
  assert.deepEqual(facts.reviewedFactRows({ ...fixture(), schemaVersion: 2 }), []);
});

test("FACT-009: scoped labels, separate options and interfaces do not imply tested fit or commercial variants", () => {
  const rows = facts.reviewedFactRows(fixture());
  assert.ok(rows.some(([label, value]) => label === "Rack width" && value === "Nominal 1200.50 mm"));
  assert.ok(rows.some(([label]) => label === "Smith bar width"));
  assert.ok(rows.some(([label]) => label === "Usable storage length"));
  assert.ok(rows.some(([label, value]) => label === "Socket drive interface (requires)" && value.includes("Drive size: 0.5 in")));
  for (const label of ["Colors", "Sizes", "Finish"]) assert.ok(rows.some(([name]) => name === label));
  assert.ok(rows.some(([label, value]) => label === "Excluded component" && value.includes("quantity not specified")));
  assert.equal(fixture().components[0].quantity, 1);
  assert.deepEqual(facts.suggestedInterfaces("Sockets"), ["socket_drive"]);
  assert.deepEqual(facts.suggestedInterfaces("Racks"), ["rack_mount"]);
  assert.deepEqual(facts.suggestedInterfaces("Handle"), []);
});

test("FACT-010: reviewed equivalents take precedence while original listing references remain intact", () => {
  const item = {
    ...publicItem, dimensions: "Legacy overall size", weight: "Raw 999 kg", material: "Raw material",
    colourOptions: "Raw combined options", included: "Raw package", modelSku: "SKU kept", warranty: "Warranty kept",
    description: "Original presentation text", notes: "Unrelated original notes", packageQuantity: 4,
    catalogFacts: { ...fixture(), measurements: [
      { kind: "width", scope: "overall", amount: "100", unit: "cm", qualifier: "exact", note: "" },
      { kind: "weight", scope: "product", amount: "12.50", unit: "kg", qualifier: "exact", note: "" },
    ], materials: [{ component: "Product", value: "Steel" }] },
  };
  const before = JSON.stringify(item);
  const rows = catalog.catalogSpecifications(item, "product");
  for (const label of ["Dimensions", "Weight", "Colour / options", "What's included"]) assert.ok(!rows.some(([key]) => key === label));
  assert.deepEqual(rows.filter(([key]) => key === "Product material"), [["Product material", "Steel"]]);
  assert.ok(!rows.some(([key]) => key === "Material"));
  assert.ok(rows.some(([key, value]) => key === "Model / SKU" && value === "SKU kept"));
  assert.ok(rows.some(([key, value]) => key === "Warranty" && value === "Warranty kept"));
  for (const [label, value] of [
    ["Original listing dimensions", item.dimensions], ["Original listing weight", item.weight],
    ["Original listing material", item.material], ["Original listing options", item.colourOptions],
    ["Original listing contents", item.included],
  ]) assert.deepEqual(rows.filter(([key]) => key === label), [[label, value]]);
  assert.deepEqual(rows.slice(0, facts.reviewedFactRows(item.catalogFacts).length), facts.reviewedFactRows(item.catalogFacts));
  assert.deepEqual(rows.filter(([key]) => key === "Original listing details"), [["Original listing details", "Reviewed values above take precedence."]]);
  assert.equal(JSON.stringify(item), before);
});

test("FACT-011: narrowly scoped subcomponent facts retain unrelated overall legacy measurements and models", () => {
  const item = { ...publicItem, dimensions: "Overall dimensions retained", weight: "Overall weight retained", compatibility: { uprightSize: "Raw upright", holeDiameter: "Raw hole", holeSpacing: "Raw spacing", models: "Legacy listed model", limitations: "Legacy limitation" }, catalogFacts: fixture() };
  const rows = catalog.catalogSpecifications(item, "accessory");
  assert.ok(rows.some(([name, value]) => name === "Dimensions" && value === item.dimensions));
  assert.deepEqual(catalog.catalogCompatibility(item), item.compatibility);
  item.catalogFacts.interfaces = [{ kind: "rack_mount", role: "requires", constraints: [{ attribute: "holeDiameter", operator: "eq", value: "25", unit: "mm" }], limitations: "" }];
  assert.equal(catalog.catalogCompatibility(item).holeDiameter, "");
  assert.equal(catalog.catalogCompatibility(item).models, "Legacy listed model");
  assert.equal(item.compatibility.holeDiameter, "Raw hole");
});

test("FACT-012: editor renders accessible typed fields and errors without inferring or mutating facts", () => {
  const value = fixture();
  value.measurements[0].amount = "-1";
  const before = JSON.stringify(value);
  const html = renderToStaticMarkup(createElement(Editor, { value, category: "Sockets", onChange: () => assert.fail("Render must not mutate data") }));
  assert.match(html, /Merchant-reviewed for customer answers/);
  assert.match(html, /aria-invalid="true"/);
  assert.match(html, /positive decimal/);
  assert.match(html, /Socket drive \(suggested\)/);
  assert.match(html, /Component 1 quantity \(optional\)/);
  assert.match(html, /min-h-12/);
  assert.equal(JSON.stringify(value), before);
});

test("FACT-015: finalized server bounds, Unicode labels and exact decimal strings are preserved", () => {
  const bounds = facts.FACT_LIMITS;
  assert.deepEqual(bounds, { options: 24, optionLabel: 100, measurements: 64, materials: 32, interfaces: 16, constraints: 24, components: 64, label: 300, text: 2000, packageNote: 4000, decimal: 64, quantity: 1000000 });
  const source = fixture();
  for (const amount of ["01", "0000.0100", "9".repeat(64), `0.${"0".repeat(61)}1`]) {
    const parsed = facts.parseCatalogFacts({ ...source, measurements: [{ ...source.measurements[0], amount }] });
    assert.equal(parsed.measurements[0].amount, amount);
  }
  assert.equal(facts.isCatalogFacts({ ...source, measurements: [{ ...source.measurements[0], amount: "9".repeat(65) }] }), false);
  for (const [key, count, entry] of [
    ["measurements", 64, source.measurements[0]],
    ["materials", 32, source.materials[0]],
    ["interfaces", 16, source.interfaces[0]],
    ["components", 64, { ...source.components[0], quantity: 1000000 }],
  ]) {
    assert.equal(facts.isCatalogFacts({ ...source, [key]: Array(count).fill(entry) }), true, key);
    assert.equal(facts.isCatalogFacts({ ...source, [key]: Array(count + 1).fill(entry) }), false, key);
  }
  const options = { ...source.options, colors: Array.from({ length: 24 }, (_, index) => `${String.fromCharCode(65 + index)}${"😀".repeat(99)}`), finish: "x".repeat(300), note: "n".repeat(2000) };
  assert.equal(facts.isCatalogFacts({ ...source, options, packageNote: "p".repeat(4000) }), true);
  assert.equal(facts.isCatalogFacts({ ...source, options: { ...options, sizes: Array(25).fill("S") } }), false);
  assert.equal(facts.isCatalogFacts({ ...source, options: { ...options, finish: "x".repeat(301) } }), false);
  assert.equal(facts.isCatalogFacts({ ...source, packageNote: "p".repeat(4001) }), false);
  assert.equal(facts.isCatalogFacts({ ...source, materials: [{ component: "", value: "Steel" }] }), false);
  assert.equal(facts.isCatalogFacts({ ...source, materials: [{ component: "Product", value: "s".repeat(300) }] }), true);
  const int = source.interfaces[0];
  assert.equal(facts.isCatalogFacts({ ...source, interfaces: [{ ...int, constraints: Array(24).fill(int.constraints[0]) }] }), true);
  assert.equal(facts.isCatalogFacts({ ...source, interfaces: [{ ...int, constraints: Array(25).fill(int.constraints[0]) }] }), false);
  const invalidQuantity = facts.editCatalogFacts({ ...source, components: [{ name: "Pin", quantity: null, status: "unknown" }] }, { components: [{ name: "Pin", quantity: NaN, status: "unknown" }] });
  assert.ok(facts.validateCatalogFacts(invalidQuantity).some(issue => issue.path === "components.0.quantity"));
  assert.equal(invalidQuantity.reviewed, false);
});

test("FACT-016: trimmed option labels reject case-insensitive duplicates and hidden controls", () => {
  const source = fixture();
  for (const labels of [["Black", " black "], ["Straße", "STRASSE"], ["ΟΣ", "ος"], ["ﬃ", "ffi"]]) {
    for (const key of ["colors", "sizes"]) {
      assert.ok(facts.validateCatalogFacts({ ...source, options: { ...source.options, [key]: labels } }).some(issue => issue.path === `options.${key}.1` && issue.message.includes("repeated")), labels.join("/"));
    }
  }
  assert.equal(facts.isCatalogFacts({ ...source, options: { ...source.options, colors: ["ı", "i"] } }), true);
  for (const hidden of ["\u0000", "\u001f", "\u007f", "\u0085", "\u200b", "\u200e", "\ufeff", "\ud800", "\udfff", "\n", "\r", "\t"]) {
    const variants = [
      { ...source, options: { ...source.options, colors: [`Black${hidden}`] } },
      { ...source, options: { ...source.options, finish: `Matte${hidden}` } },
      { ...source, materials: [{ component: `Frame${hidden}`, value: "Steel" }] },
      { ...source, components: [{ name: `Pin${hidden}`, quantity: null, status: "unknown" }] },
      { ...source, interfaces: [{ ...source.interfaces[0], constraints: [{ ...source.interfaces[0].constraints[0], value: `Listed${hidden}` }] }] },
    ];
    for (const value of variants) assert.equal(facts.isCatalogFacts(value), false, JSON.stringify(hidden));
  }
  assert.equal(facts.isCatalogFacts({ ...source, materials: [{ component: "   ", value: "Steel" }] }), false);
  assert.equal(facts.isCatalogFacts({ ...source, options: { ...source.options, colors: ["   "] } }), false);
});

test("FACT-017: notes allow ordinary line breaks/tabs, labels trim on save, and amounts never trim", () => {
  const source = fixture();
  const multiline = "First line\r\n\tSecond line\nThird line";
  const value = {
    ...source,
    options: { colors: [" Black ", "White"], sizes: [" Small "], finish: " Matte ", note: multiline },
    materials: [{ component: " Frame ", value: " Steel " }],
    measurements: [{ ...source.measurements[0], amount: "0001.500", note: multiline }],
    interfaces: [{ ...source.interfaces[0], constraints: [{ ...source.interfaces[0].constraints[0], value: " 0.5 " }], limitations: multiline }],
    components: [{ name: " Pin ", quantity: null, status: "unknown" }],
    packageNote: multiline,
  };
  const before = JSON.stringify(value);
  const parsed = facts.parseCatalogFacts(value);
  assert.deepEqual(parsed.options, { colors: ["Black", "White"], sizes: ["Small"], finish: "Matte", note: multiline });
  assert.deepEqual(parsed.materials, [{ component: "Frame", value: "Steel" }]);
  assert.equal(parsed.components[0].name, "Pin");
  assert.equal(parsed.interfaces[0].constraints[0].value, "0.5");
  assert.equal(parsed.interfaces[0].limitations, multiline);
  assert.equal(parsed.measurements[0].note, multiline);
  assert.equal(parsed.measurements[0].amount, "0001.500");
  assert.equal(parsed.packageNote, multiline);
  assert.deepEqual(facts.catalogFactsPatch(value, true), { catalogFacts: parsed });
  assert.equal(JSON.stringify(value), before);
  assert.deepEqual(facts.catalogFactsPatch(value, false), {});
  for (const amount of [" 1", "1 ", "\t1", "1\n"]) assert.equal(facts.isCatalogFacts({ ...value, measurements: [{ ...value.measurements[0], amount }] }), false);
  for (const hidden of ["\u0000", "\u000b", "\u001f", "\u007f", "\u0085", "\u200b", "\ufeff", "\ud800"]) {
    const invalid = `First${hidden}second`;
    for (const variant of [
      { ...value, options: { ...value.options, note: invalid } },
      { ...value, measurements: [{ ...value.measurements[0], note: invalid }] },
      { ...value, interfaces: [{ ...value.interfaces[0], limitations: invalid }] },
      { ...value, packageNote: invalid },
    ]) assert.equal(facts.isCatalogFacts(variant), false);
  }
});

test("FACT-018: partial width, finish and one excluded component keep other original dimensions, options and contents", () => {
  const item = {
    ...publicItem,
    dimensions: "Width 90 cm; height 210 cm; depth 70 cm. Reference Drawing A.",
    included: "Two brackets, safety clips and mounting bolts.",
    colourOptions: "Red or blue; sizes Small, Medium and Large.",
    material: "Steel frame with rubber grips.",
    weight: "18 kg",
    warranty: "Original warranty retained",
    catalogFacts: {
      ...facts.emptyCatalogFacts(), reviewed: true,
      options: { colors: [], sizes: [], finish: "Powder coat", note: "" },
      measurements: [{ kind: "width", scope: "overall", amount: "100", unit: "cm", qualifier: "exact", note: "" }],
      materials: [{ component: "Product", value: "Steel" }],
      components: [{ name: "Bench", quantity: null, status: "excluded" }],
    },
  };
  const before = JSON.stringify(item);
  for (const itemType of ["product", "accessory"]) {
    const rows = catalog.catalogSpecifications(item, itemType);
    const typed = facts.reviewedFactRows(item.catalogFacts);
    assert.deepEqual(rows.slice(0, typed.length), typed);
    assert.deepEqual(rows.filter(([label]) => label === "Original listing dimensions"), [["Original listing dimensions", item.dimensions]]);
    assert.deepEqual(rows.filter(([label]) => label === "Original listing contents"), [["Original listing contents", item.included]]);
    assert.deepEqual(rows.filter(([label]) => label === "Original listing options"), [["Original listing options", item.colourOptions]]);
    assert.deepEqual(rows.filter(([label]) => label === "Original listing material"), [["Original listing material", item.material]]);
    assert.deepEqual(rows.filter(([label]) => label === "Weight"), [["Weight", "18 kg"]]);
    assert.equal(rows.filter(([label]) => label === "Original listing details").length, 1);
    assert.ok(rows.findIndex(([label]) => label === "Original listing details") >= typed.length);
    for (const label of ["Dimensions", "Material", "Colour / options", "Finish / colour", "What's included"]) assert.ok(!rows.some(([name]) => name === label));
    const unreviewed = catalog.catalogSpecifications({ ...item, catalogFacts: { ...item.catalogFacts, reviewed: false } }, itemType);
    assert.ok(!unreviewed.some(([label]) => label.startsWith("Original listing")));
    assert.deepEqual(unreviewed.filter(([label]) => label === "Dimensions"), [["Dimensions", item.dimensions]]);
    assert.deepEqual(unreviewed.filter(([label]) => label === "What's included"), [["What's included", item.included]]);
  }
  assert.equal(JSON.stringify(item), before);
});
