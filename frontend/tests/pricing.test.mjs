import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
function loadSource(relative) {
  const source = ts.transpileModule(fs.readFileSync(new URL(`../${relative}`, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const result = { exports: {} };
  const requireSource = (specifier) => specifier.startsWith("@/")
    ? loadSource(`src/${specifier.slice(2)}.ts`)
    : require(specifier);
  new Function("require", "module", "exports", source)(requireSource, result, result.exports);
  return result.exports;
}
const pricing = loadSource("src/lib/pricing.ts");
const fields = loadSource("src/app/admin/AdminFields.tsx");

test("ADM-012: legacy and missing MSRP never inherit selling prices or currency", () => {
  for (const item of [{}, { msrps: null }, { price: 29.95, currency: "CAD" }, { prices: { CAD: 29.95, USD: 19.95 } }]) {
    assert.deepEqual(pricing.getMarketMsrps(item), { CAD: null, USD: null });
  }
  assert.deepEqual(pricing.getMarketMsrps({ msrps: { CAD: 49.95 } }), { CAD: 49.95, USD: null });
  assert.deepEqual(pricing.getMarketMsrps({ msrps: { USD: 0 } }), { CAD: null, USD: 0 });
});

test("ADM-012: independent MSRP values format without conversion or mutating source", () => {
  const msrps = { CAD: 120, USD: 79.5 };
  const normalized = pricing.getMarketMsrps({ msrps });
  assert.deepEqual(pricing.priceInputs(normalized), { CAD: "120.00", USD: "79.50" });
  normalized.CAD = null;
  assert.deepEqual(msrps, { CAD: 120, USD: 79.5 });
  assert.deepEqual(pricing.priceInputs({ CAD: null, USD: 0 }), { CAD: "", USD: "0.00" });
});

test("ADM-012: shared price and MSRP validation accepts cents and explicit blank clearing", () => {
  for (const [input, expected] of [["19", 19], ["19.5", 19.5], ["19.95", 19.95], ["0", 0], [".25", 0.25]]) {
    assert.equal(fields.parsePrice(input), expected);
    assert.deepEqual(fields.parseMarketPrices({ CAD: input, USD: "" }), { CAD: expected, USD: null });
  }
  assert.deepEqual(fields.parseMarketPrices({ CAD: "", USD: "12.50" }), { CAD: null, USD: 12.5 });
  assert.deepEqual(fields.parseMarketPrices({ CAD: "", USD: "" }), { CAD: null, USD: null });
});

test("ADM-012: either invalid market blocks the entire map without changing input", () => {
  for (const invalid of ["-1", "NaN", "Infinity", "19.955", "1e2", " ", "9".repeat(400)]) {
    for (const currency of ["CAD", "USD"]) {
      const text = { CAD: "29.95", USD: "19.95", [currency]: invalid };
      const original = { ...text };
      assert.equal(fields.parseMarketPrices(text), null);
      assert.deepEqual(text, original);
    }
  }
});

test("ADM-012: optional MSRP inputs keep exact labels and never flag missing markets", () => {
  const markup = renderToStaticMarkup(fields.MarketPriceInputs({
    value: { CAD: "", USD: "" }, onChange: () => {}, prefix: "test-msrp", kind: "msrp",
  }));
  assert.match(markup, /CAD MSRP/);
  assert.match(markup, /USD MSRP/);
  assert.match(markup, /Optional; shown only when higher than Price\. Does not affect checkout\/quote pricing\./);
  assert.doesNotMatch(markup, /Needs attention|aria-invalid="true"/);
  const priceMarkup = renderToStaticMarkup(fields.MarketPriceInputs({
    value: { CAD: "", USD: "19.95" }, onChange: () => {}, prefix: "test-price",
  }));
  assert.match(priceMarkup, /Canada price \(CAD\)/);
  assert.match(priceMarkup, /US price \(USD\)/);
  assert.match(priceMarkup, /Needs attention/);
});

test("ADM-012: admin summary labels only present MSRPs independently of selling price", () => {
  const prices = { CAD: 29.95, USD: 19.95 };
  const empty = renderToStaticMarkup(fields.MarketPriceSummary({ prices, msrps: { CAD: null, USD: null } }));
  assert.doesNotMatch(empty, /MSRP|Needs attention/);
  const present = renderToStaticMarkup(fields.MarketPriceSummary({ prices, msrps: { CAD: 0, USD: 19.95 } }));
  assert.match(present, /MSRP · CAD \$0\.00 · USD \$19\.95/);
  assert.doesNotMatch(present, /Needs attention|<s>|<del>/);
});
