import assert from "node:assert/strict";
import fs from "node:fs";
import { test } from "node:test";
import ts from "typescript";

const loaded = { exports: {} };
const source = ts.transpileModule(fs.readFileSync(new URL("../src/lib/hero.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
new Function("require", "module", "exports", source)(() => ({ API_BASE: "" }), loaded, loaded.exports);
const { defaultHero, defaultEngineering, parseHero, isEngineeringImage, changedHeroFields } = loaded.exports;
const copy = value => JSON.parse(JSON.stringify(value));

test("ADM-013: legacy banners gain the current engineering defaults without sharing mutable state", () => {
  const legacy = { tag: "Custom", number: "02", eyebrow: "Custom heading", title: "Saved banner", image: "/images/custom.png", priceLabel: "Ignore" };
  const parsed = parseHero(legacy);
  assert.equal(parsed.title, "Saved banner");
  assert.deepEqual(parsed.engineering, defaultEngineering);
  assert.ok(!("priceLabel" in parsed));
  parsed.engineering.items[0].title = "Changed copy";
  assert.equal(defaultEngineering.items[0].title, "Signature shield");
  assert.ok(!("engineering" in legacy));
});

test("ADM-013: four custom engineering images and plain text survive response parsing", () => {
  const hero = copy(defaultHero);
  hero.engineering.heading = "Custom engineering";
  hero.engineering.intro = "";
  hero.engineering.items[0] = { title: "<script>text only</script>", description: "Line one\nLine two", image: "/api/uploads/example.png" };
  assert.deepEqual(parseHero(hero), hero);
});

test("ADM-013: malformed nested data never becomes a normal-looking default section", () => {
  for (const engineering of [null, {}, { ...copy(defaultEngineering), items: [] }, { ...copy(defaultEngineering), heading: "" }]) {
    assert.throws(() => parseHero({ ...defaultHero, engineering }), /Invalid engineering/);
  }
  for (const key of ["title", "image", "description"]) {
    const hero = copy(defaultHero);
    hero.engineering.items[0][key] = null;
    assert.throws(() => parseHero(hero), /Invalid engineering card/);
  }
  const hero = copy(defaultHero);
  hero.engineering.items.push(copy(hero.engineering.items[0]));
  assert.throws(() => parseHero(hero), /Invalid engineering/);
});

test("ADM-013: image previews reject partial, unsafe and video values while allowing local/HTTP images", () => {
  for (const value of ["/images/brand/frame-badge.jpg", "/api/uploads/example.png", "https://example.com/image?id=2", "http://example.com/p.jpg"]) {
    assert.equal(isEngineeringImage(value), true);
  }
  for (const value of ["", "h", "javascript:alert(1)", "data:image/png;base64,A", "//example.com/a.png", "https://u:p@example.com/a.png", "/api/uploads/a.mp4", "/images/a\\b.png", "/images/a\nb.png", "/images/../a.png", "/images/%2e%2e/a.png", "/api/uploads/nested/a.png", "/private/a.png"]) {
    assert.equal(isEngineeringImage(value), false, value);
  }
});

test("ADM-013: saving one section omits unchanged settings in the other section", () => {
  const original = copy(defaultHero);
  const banner = { ...original, title: "Updated banner" };
  assert.deepEqual(changedHeroFields(banner, original), { title: "Updated banner" });
  const engineering = copy(original);
  engineering.engineering.items[0].description = "Updated engineering";
  assert.deepEqual(changedHeroFields(engineering, original), { engineering: engineering.engineering });
  assert.deepEqual(changedHeroFields(original, original), {});
});
