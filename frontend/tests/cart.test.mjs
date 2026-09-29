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
const ordering = loadSource("src/lib/catalogOrder.ts");
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

test("prices consistently show their currency and two decimals", () => {
  for (const currency of ["CAD", "USD"]) {
    assert.equal(cart.formatPrice(19, currency), `${currency} $19.00`);
    assert.equal(cart.formatPrice(19.5, currency), `${currency} $19.50`);
    assert.equal(cart.formatPrice(19.95, currency), `${currency} $19.95`);
  }
});

test("SYS-020: MSRP never replaces selling price in cart totals or quote text", () => {
  const next = cart.addProductToCart({ id: 777, name: "MSRP fixture", price: 19.95, msrp: 99, currency: "CAD" }, 2);
  assert.deepEqual(cart.getCartTotals(next), [["CAD", 39.90]]);
  assert.equal(next[0].price, 19.95);
  assert.match(cart.formatCartSummary(next), /CAD \$19\.95/);
  assert.doesNotMatch(cart.formatCartSummary(next), /99\.00/);
});

test("saved cart is repriced and unavailable regional items are removed", () => {
  const saved = [
    { id: 1, name: "Rack", price: 4000, currency: "USD", quantity: 2 },
    { id: 2, name: "Canada unavailable", price: 19, currency: "USD", quantity: 1 },
  ];
  assert.deepEqual(cart.reconcileCart(saved, [{ id: 1, name: "Rack", price: 4005, currency: "CAD" }]), [
    { id: 1, name: "Rack", price: 4005, currency: "CAD", quantity: 2 },
  ]);
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
  assert.match(cart.formatCartSummary(), /1\. Handles\n   Quantity: 2 pairs\n   Contents: 2 pieces per pair/);
});

test("legacy cart and image-only catalog items still work", () => {
  storage.set(cart.CART_KEY, JSON.stringify([{ id: 1, name: "Bench", price: 19, quantity: 1 }]));
  assert.equal(cart.getCartCount(cart.readCart()), 1);
  assert.match(cart.formatCartSummary(), /1\. Bench\n   Quantity: 1 sale unit/);
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

test("USR-013: quote items have numbered blocks, explicit units and independent currency prices", () => {
  assert.equal(cart.formatCartSummary([
    { id: 1, name: "Bench", price: 750, currency: "CAD", quantity: 1 },
    { id: 2, name: "Grips", price: 39, currency: "CAD", quantity: 2, sellingUnit: "Pair", packageQuantity: 2 },
    { id: 3, name: "Plate set", price: 99.5, currency: "USD", quantity: 3, sellingUnit: "Set", packageQuantity: 4 },
    { id: 4, name: "Handle", price: 10, currency: "CAD", quantity: 1, sellingUnit: "Each", packageQuantity: 1 },
  ]), [
    "Interested in:", "",
    "1. Bench", "   Quantity: 1 sale unit", "   Unit price: CAD $750.00 per sale unit", "",
    "2. Grips", "   Quantity: 2 pairs", "   Contents: 2 pieces per pair", "   Unit price: CAD $39.00 per pair", "",
    "3. Plate set", "   Quantity: 3 sets", "   Contents: 4 pieces per set", "   Unit price: USD $99.50 per set", "",
    "4. Handle", "   Quantity: 1 item", "   Contents: 1 piece per item", "   Unit price: CAD $10.00 per item",
  ].join("\n"));
});

test("USR-013: empty quote selection remains explicit without invented items", () => {
  assert.equal(cart.formatCartSummary([]), "No items selected yet.");
});

test("ADM-011: listing positions move without mutating IDs or dropping records", () => {
  const ids = [1, 2, 3];
  assert.deepEqual(ordering.moveCatalogId(ids, 3, 0), [3, 1, 2]);
  assert.deepEqual(ordering.moveCatalogId(ids, 1, 2), [2, 3, 1]);
  assert.deepEqual(ids, [1, 2, 3]);
  assert.throws(() => ordering.moveCatalogId(ids, 8, 0), /existing item/);
  assert.throws(() => ordering.moveCatalogId(ids, 1, 3), /valid listing position/);
  assert.throws(() => ordering.moveCatalogId(ids, 1, 0.5), /valid listing position/);
  assert.deepEqual(ordering.orderByIds([{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }], [3, 1, 2]), [{ id: 3 }, { id: 1 }, { id: 2 }, { id: 4 }]);
});
