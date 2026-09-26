import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, beforeEach } from "node:test";
import ts from "typescript";

const modules = new Map();
const directory = path.dirname(fileURLToPath(import.meta.url));
function loadSource(relative) {
  const filename = path.resolve(directory, "..", relative);
  if (modules.has(filename)) return modules.get(filename);
  const result = { exports: {} };
  const source = ts.transpileModule(fs.readFileSync(filename, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const requireSource = (specifier) => {
    if (!specifier.startsWith(".")) throw new Error(`Unexpected test dependency: ${specifier}`);
    return loadSource(path.relative(path.resolve(directory, ".."), path.resolve(path.dirname(filename), `${specifier}.ts`)));
  };
  new Function("require", "module", "exports", source)(requireSource, result, result.exports);
  modules.set(filename, result.exports);
  return result.exports;
}
const cart = loadSource("src/lib/cart.ts");
const details = loadSource("src/lib/catalogDetails.ts");
let storage;
beforeEach(() => {
  storage = new Map();
  global.window = {
    localStorage: {
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
    },
    dispatchEvent: () => true,
  };
});

test("prices consistently show two decimals without changing currency labels", () => {
  for (const currency of ["CAD", "USD"]) {
    assert.equal(cart.formatPrice(19, currency), "$19.00");
    assert.equal(cart.formatPrice(19.5, currency), "$19.50");
    assert.equal(cart.formatPrice(19.95, currency), "$19.95");
  }
});

test("cart arithmetic uses cents and keeps currencies separate", () => {
  assert.equal(cart.lineAmount(0.1, 3), 0.3);
  assert.deepEqual(cart.getCartTotals([
    { price: 0.1, quantity: 1, currency: "CAD" },
    { price: 0.2, quantity: 1, currency: "CAD" },
    { price: 19.95, quantity: 3, currency: "USD" },
  ]), [["CAD", 0.3], ["USD", 59.85]]);
});

test("selling units persist into cart and quote without private metadata", () => {
  const item = { id: 1001, name: "Handles", price: 19.95, currency: "CAD", sellingUnit: "Pair", packageQuantity: 2, provenance: { notes: "private" } };
  cart.addProductToCart(item, 2);
  assert.equal(cart.readCart()[0].sellingUnit, "Pair");
  assert.equal(cart.readCart()[0].provenance, undefined);
  assert.match(cart.formatCartSummary(), /Handles x 2 pairs \(2 pieces per sale unit\)/);
});

test("legacy cart and image-only catalog items still work", () => {
  storage.set(cart.CART_KEY, JSON.stringify([{ id: 1, name: "Bench", price: 19, quantity: 1 }]));
  assert.equal(cart.getCartCount(cart.readCart()), 1);
  assert.match(cart.formatCartSummary(), /Bench x 1/);
  assert.deepEqual(details.getCatalogPhotos({ image: "/images/bench.jpg" }), ["/images/bench.jpg"]);
  assert.deepEqual(details.getCatalogPhotos({ image: "/images/bench.jpg", photos: [] }), []);
});

test("quantity cap is preserved and invalid additions do not write", () => {
  const item = { id: 1, name: "Bench", price: 19.95 };
  cart.addProductToCart(item, 10);
  cart.addProductToCart(item);
  assert.equal(cart.readCart()[0].quantity, 10);
  assert.throws(() => cart.addProductToCart(item, 0), /valid quantity/);
  assert.throws(() => cart.addProductToCart(item, 1.5), /valid quantity/);
});

test("failed storage does not report successful cart writes", () => {
  window.localStorage.setItem = () => { throw new Error("Storage blocked"); };
  assert.throws(() => cart.addProductToCart({ id: 1, name: "Bench", price: 19 }), /Storage blocked/);
  assert.equal(storage.size, 0);
});
