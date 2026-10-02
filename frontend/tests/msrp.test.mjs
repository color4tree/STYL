import assert from "node:assert/strict";
import fs from "node:fs";
import { createRequire } from "node:module";
import { test } from "node:test";
import { Children, isValidElement } from "react";
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
const fields = loadSource("src/app/admin/AdminFields.tsx");
const defaults = {
  prefix: "product",
  prices: { CAD: "29.95", USD: "19.95" },
  msrps: { CAD: "", USD: "" },
  onPricesChange: () => {},
  onMsrpsChange: () => {},
};
const pricing = (props = {}) => fields.CountryPricingInputs({ ...defaults, ...props });
function findElements(node, predicate) {
  return Children.toArray(node).flatMap((element) => !isValidElement(element) ? [] : [
    ...(predicate(element) ? [element] : []),
    ...findElements(element.props.children, predicate),
  ]);
}
const priceFields = (tree) => findElements(tree, (element) => element.type === fields.PriceInput);
const input = (field) => findElements(fields.PriceInput(field.props), (element) => element.type === "input")[0];

test("ADM-012: one accessible Country pricing group pairs each country's price and MSRP with legacy IDs", () => {
  for (const prefix of ["product", "accessory"]) {
    const tree = pricing({ prefix });
    const markup = renderToStaticMarkup(tree);
    assert.equal((markup.match(/<fieldset\b/g) ?? []).length, 1);
    assert.match(markup, /<legend[^>]*>Country pricing<\/legend>/);
    const rows = findElements(tree, (element) => element.type === "div");
    assert.equal(rows.length, 2);
    for (const [index, currency] of ["CAD", "USD"].entries()) {
      const pair = priceFields(rows[index]);
      assert.deepEqual(pair.map((field) => field.props.id), [
        `${prefix}-price-${currency.toLowerCase()}`, `${prefix}-msrp-${currency.toLowerCase()}`,
      ]);
      assert.deepEqual(pair.map((field) => field.props.label), [
        currency === "CAD" ? "Canada price (CAD)" : "US price (USD)", `${currency} MSRP`,
      ]);
      for (const field of pair) {
        assert.ok(markup.includes(`<label for="${field.props.id}">${field.props.label}</label>`));
        assert.equal(input(field).props.inputMode, "decimal");
      }
    }
  }
});

test("ADM-012: blank MSRP is optional, zero selling prices remain valid, and pricing guidance stays visible", () => {
  const markup = renderToStaticMarkup(pricing({ prices: { CAD: "0", USD: "0.00" } }));
  assert.match(markup, /Optional; shown only when higher than Price\. Does not affect checkout\/quote pricing\./);
  assert.match(markup, /A blank price hides this item in that market; zero is a valid price\. No currency conversion is applied\./);
  assert.doesNotMatch(markup, /Needs attention|aria-invalid="true"|\brequired=/);
  assert.equal((markup.match(/aria-invalid="false"/g) ?? []).length, 4);
});

test("ADM-012: missing selling-price notices do not depend on optional MSRP", () => {
  for (const [prices, missing] of [
    [{ CAD: "", USD: "0" }, "Canada"],
    [{ CAD: "0", USD: "" }, "US / other countries"],
    [{ CAD: "", USD: "" }, "Canada and US"],
  ]) {
    const markup = renderToStaticMarkup(pricing({ prices, msrps: { CAD: "49.95", USD: "39.95" } }));
    assert.ok(markup.includes(`Needs attention: ${missing} price missing.`));
    assert.equal((markup.match(/role="status"/g) ?? []).length, 1);
    assert.doesNotMatch(markup, /aria-invalid="true"/);
  }
});

test("ADM-012: invalid price and MSRP share validation and link the correct accessible error without blur data loss", () => {
  for (const kind of ["price", "msrp"]) {
    for (const currency of ["CAD", "USD"]) {
      for (const invalid of ["-1", "19.955", "Infinity", "NaN", "1e2", " ", "9".repeat(400)]) {
        const key = kind === "price" ? "prices" : "msrps";
        const values = { CAD: "29.95", USD: "19.95", [currency]: invalid };
        const changes = [];
        const tree = pricing({
          [key]: values,
          onPricesChange: (value) => changes.push(value),
          onMsrpsChange: (value) => changes.push(value),
        });
        const field = priceFields(tree).find((element) => element.props.id === `product-${kind}-${currency.toLowerCase()}`);
        const control = input(field);
        assert.equal(control.props["aria-invalid"], true);
        assert.equal(control.props["aria-describedby"], `${field.props.id}-error`);
        assert.equal(control.props.value, invalid);
        const error = findElements(fields.PriceInput(field.props), (element) => element.type === "span")[0];
        assert.equal(error.props.id, control.props["aria-describedby"]);
        assert.equal(error.props.children, kind === "price" ? fields.priceError : fields.msrpError);
        assert.equal(fields.parseMarketPrices(values), null);
        control.props.onBlur();
        assert.deepEqual(changes, []);
        assert.equal(values[currency], invalid);
      }
    }
  }
});

test("ADM-012: every shared input changes only its own market and kind without mutating source values", () => {
  for (const target of ["price-cad", "msrp-cad", "price-usd", "msrp-usd"]) {
    const prices = Object.freeze({ CAD: "29.95", USD: "19.95" });
    const msrps = Object.freeze({ CAD: "49.95", USD: "39.95" });
    const changes = [];
    const tree = pricing({
      prices, msrps,
      onPricesChange: (value) => changes.push(["price", value]),
      onMsrpsChange: (value) => changes.push(["msrp", value]),
    });
    const field = priceFields(tree).find((element) => element.props.id === `product-${target}`);
    const [kind, currency] = target.split("-");
    const original = kind === "price" ? prices : msrps;
    for (const value of ["0", "", "invalid"]) {
      input(field).props.onChange({ target: { value } });
      assert.deepEqual(changes.pop(), [kind, { ...original, [currency.toUpperCase()]: value }]);
    }
  }
});

test("ADM-012: shared controls preserve cent normalization on blur and never normalize empty optional fields", () => {
  for (const value of ["", "0", ".25", "49.5", "49.95"]) {
    const changes = [];
    const tree = pricing({
      prices: { CAD: value, USD: value }, msrps: { CAD: value, USD: value },
      onPricesChange: (next) => changes.push(["price", next]),
      onMsrpsChange: (next) => changes.push(["msrp", next]),
    });
    for (const field of priceFields(tree)) {
      const control = input(field);
      assert.equal(control.props["aria-invalid"], false);
      assert.equal(control.props["aria-describedby"], undefined);
      control.props.onBlur();
      if (value === "") assert.deepEqual(changes, []);
      else {
        const [, kind, currency] = field.props.id.split("-");
        assert.deepEqual(changes.pop(), [kind, { CAD: value, USD: value, [currency.toUpperCase()]: Number(value).toFixed(2) }]);
      }
    }
  }
});
