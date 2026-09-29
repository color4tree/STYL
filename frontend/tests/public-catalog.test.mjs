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
  const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const requireSource = specifier => {
    if (specifier === "react/jsx-runtime") return nativeRequire(specifier);
    const base = specifier.startsWith("@/") ? path.join(root, "src", specifier.slice(2)) : path.resolve(path.dirname(filename), specifier);
    return load(path.relative(root, `${base}.ts`));
  };
  new Function("require", "module", "exports", compiled)(requireSource, loaded, loaded.exports);
  modules.set(filename, loaded.exports);
  return loaded.exports;
}

const catalog = load("src/lib/publicCatalog.ts");
const Price = load("src/components/CatalogPrice.tsx").default;
const fixture = { id: 3, name: "Equipment", category: "Racks", price: 20, currency: "CAD", slug: "safe-rack" };

test("USR-017: three catalog views default to All products without changing legacy detail paths", () => {
  assert.deepEqual(catalog.catalogViews.map(entry => entry.label), ["All products", "Equipment", "Accessories"]);
  for (const value of [null, "", "invalid", "ALL"]) assert.equal(catalog.catalogView(value), "all");
  assert.equal(catalog.catalogView("equipment"), "equipment");
  assert.equal(catalog.catalogView("accessories"), "accessories");
  assert.equal(catalog.catalogItemHref(fixture, "product"), "/products/safe-rack");
  assert.equal(catalog.catalogItemHref({ ...fixture, slug: undefined }, "accessory"), "/accessories/3");
  assert.equal(catalog.catalogItemHref({ ...fixture, slug: "a/b" }, "product"), "/products/a%2Fb");
});

test("SYS-020: legacy and nullable MSRP items remain valid, invalid public price data does not", () => {
  for (const msrp of [undefined, null, 0, 10, 20, 25.50]) assert.equal(catalog.isPublicCatalogItem({ ...fixture, msrp }), true);
  for (const msrp of [-1, Infinity, NaN, "25", true]) assert.equal(catalog.isPublicCatalogItem({ ...fixture, msrp }), false);
  for (const change of [{ price: -1 }, { price: NaN }, { id: 0 }, { currency: "EUR" }, { photos: [3] }]) {
    assert.equal(catalog.isPublicCatalogItem({ ...fixture, ...change }), false);
  }
});

test("SYS-020: optional MSRP is crossed out only above actual Price, including free sale prices", () => {
  for (const currency of ["CAD", "USD"]) {
    const markup = renderToStaticMarkup(createElement(Price, { price: 19.95, currency, msrp: 30 }));
    assert.ok(markup.includes(`<s>${currency} $30.00</s>`));
    assert.ok(markup.includes(`${currency} $19.95`));
    assert.match(markup, /<p data-analytics-price="true"[^>]*data-testid="catalog-price"/);
    for (const msrp of [undefined, null, 0, 10, 19.95, NaN, Infinity]) {
      assert.ok(!renderToStaticMarkup(createElement(Price, { price: 19.95, currency, msrp })).includes("<s>"));
    }
  }
  const free = renderToStaticMarkup(createElement(Price, { price: 0, currency: "CAD", msrp: 10, sellingUnit: "Pair" }));
  assert.ok(free.includes("<s>CAD $10.00</s>"));
  assert.ok(free.includes("CAD $0.00"));
  assert.ok(free.includes("pair"));
});
