export const measurementKinds = ["length", "width", "height", "depth", "diameter", "weight", "load_capacity", "resistance", "increment"] as const;
export const measurementScopes = ["overall", "product", "rack", "upright", "smith_bar", "usable_storage", "mounting", "shaft", "insertion", "stack", "drive", "socket_opening"] as const;
export const lengthUnits = ["mm", "cm", "m", "in", "ft"] as const;
export const massUnits = ["kg", "lb"] as const;
export const measurementUnits = [...lengthUnits, ...massUnits] as const;
export const qualifiers = ["exact", "approximate", "nominal"] as const;
export const interfaceKinds = ["rack_mount", "shelf_mount", "plate_storage", "selector_pin", "socket_drive", "barbell_receiver"] as const;
export const interfaceRoles = ["provides", "requires", "accepts"] as const;
export const constraintAttributes = ["uprightSize", "holeDiameter", "holeSpacing", "requiredDepth", "mountingSpan", "shaftDiameter", "insertionLength", "driveSize", "openingSize", "barbellDiameter"] as const;
export const constraintOperators = ["listed", "eq", "min", "max"] as const;
export const componentStatuses = ["included", "excluded", "unknown"] as const;

export type Measurement = {
  kind: (typeof measurementKinds)[number];
  scope: (typeof measurementScopes)[number];
  amount: string;
  unit: (typeof measurementUnits)[number];
  qualifier: (typeof qualifiers)[number];
  note: string;
};
export type InterfaceConstraint = {
  attribute: (typeof constraintAttributes)[number];
  operator: (typeof constraintOperators)[number];
  value: string;
  unit: "" | (typeof lengthUnits)[number];
};
export type CatalogInterface = {
  kind: (typeof interfaceKinds)[number];
  role: (typeof interfaceRoles)[number];
  constraints: InterfaceConstraint[];
  limitations: string;
};
export type CatalogFacts = {
  schemaVersion: 1;
  reviewed: boolean;
  options: { colors: string[]; sizes: string[]; finish: string; note: string };
  measurements: Measurement[];
  materials: { component: string; value: string }[];
  interfaces: CatalogInterface[];
  components: { name: string; quantity: number | null; status: (typeof componentStatuses)[number] }[];
  packageNote: string;
};
export type FactIssue = { path: string; message: string };
export const FACT_LIMITS = { options: 24, optionLabel: 100, measurements: 64, materials: 32, interfaces: 16, constraints: 24, components: 64, label: 300, text: 2000, packageNote: 4000, decimal: 64, quantity: 1000000 } as const;

export function emptyCatalogFacts(): CatalogFacts {
  return { schemaVersion: 1, reviewed: false, options: { colors: [], sizes: [], finish: "", note: "" }, measurements: [], materials: [], interfaces: [], components: [], packageNote: "" };
}

export function factLabel(value: string): string {
  const words = value.replace(/([a-z])([A-Z])/g, "$1 $2").replaceAll("_", " ").toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function unitsForMeasurement(kind: Measurement["kind"]): readonly Measurement["unit"][] {
  return (["weight", "load_capacity", "resistance", "increment"] as string[]).includes(kind) ? massUnits : lengthUnits;
}

export function suggestedInterfaces(category: string): readonly CatalogInterface["kind"][] {
  if (/socket|wrench|tool/i.test(category)) return ["socket_drive"];
  if (/pin|selector/i.test(category)) return ["selector_pin"];
  if (/shelf|storage/i.test(category)) return ["shelf_mount", "plate_storage"];
  if (/barbell|bar holder|landmine/i.test(category)) return ["barbell_receiver"];
  if (/rack|smith|attachment/i.test(category)) return ["rack_mount"];
  return [];
}

function record(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function optionKey(value: string): string {
  // Fold ligatures/sharp s and final sigma without conflating dotless i with i.
  return [...value.trim()].map(character => character === "\u0131" ? character : character.toUpperCase().toLowerCase().replaceAll("ß", "ss")).join("");
}

function normalizeCatalogFacts(value: CatalogFacts): CatalogFacts {
  return {
    ...value,
    options: { colors: value.options.colors.map(label => label.trim()), sizes: value.options.sizes.map(label => label.trim()), finish: value.options.finish.trim(), note: value.options.note.trim() },
    measurements: value.measurements.map(row => ({ ...row, note: row.note.trim() })),
    materials: value.materials.map(row => ({ component: row.component.trim(), value: row.value.trim() })),
    interfaces: value.interfaces.map(row => ({ ...row, constraints: row.constraints.map(constraint => ({ ...constraint, value: constraint.value.trim() })), limitations: row.limitations.trim() })),
    components: value.components.map(row => ({ ...row, name: row.name.trim() })),
    packageNote: value.packageNote.trim(),
  };
}

export function validateCatalogFacts(value: unknown): FactIssue[] {
  const issues: FactIssue[] = [];
  const issue = (path: string, message: string) => issues.push({ path, message });
  const object = (v: unknown, path: string, keys: readonly string[]): v is Record<string, unknown> => {
    if (!record(v)) { issue(path, "Expected product facts fields."); return false; }
    if (Object.keys(v).some(key => !keys.includes(key))) issue(path, "Unknown facts field. Reload or contact the site administrator.");
    return true;
  };
  const text = (v: unknown, path: string, limit: number = FACT_LIMITS.text, required = false, multiline = false) => {
    if (typeof v !== "string") { issue(path, "Enter text for this field."); return; }
    if (/[\p{Cc}\p{Cf}\p{Cs}]/u.test(multiline ? v.replace(/[\r\n\t]/g, "") : v)) {
      issue(path, multiline ? "Remove hidden or unsupported characters. Normal line breaks and tabs are allowed." : "Remove hidden characters and line breaks from this label.");
      return;
    }
    const trimmed = v.trim();
    if ([...trimmed].length > limit || (required && !trimmed.length)) issue(path, required ? `Enter a value (up to ${limit} characters).` : `Use text up to ${limit} characters.`);
  };
  const note = (v: unknown, path: string, limit: number = FACT_LIMITS.text) => text(v, path, limit, false, true);
  const choice = (v: unknown, values: readonly string[], path: string) => {
    if (typeof v !== "string" || !values.includes(v)) issue(path, "Select a supported value.");
  };
  const decimal = (v: unknown, path: string) => {
    if (typeof v !== "string" || v.length > FACT_LIMITS.decimal || !/^\d+(?:\.\d+)?$/.test(v) || /[^0-9.]/.test(v) || !/[1-9]/.test(v)) {
      issue(path, "Enter a positive decimal, such as 25.4 (no fractions or exponent notation).");
    }
  };
  const array = (v: unknown, path: string, max: number): v is unknown[] => {
    if (!Array.isArray(v) || v.length > max) { issue(path, `Use no more than ${max} entries.`); return false; }
    return true;
  };
  if (!object(value, "", ["schemaVersion", "reviewed", "options", "measurements", "materials", "interfaces", "components", "packageNote"])) return issues;
  if (value.schemaVersion !== 1) issue("schemaVersion", "Unsupported product facts version.");
  if (typeof value.reviewed !== "boolean") issue("reviewed", "Choose whether these facts have been reviewed.");
  if (object(value.options, "options", ["colors", "sizes", "finish", "note"])) {
    for (const key of ["colors", "sizes"] as const) {
      const items = value.options[key];
      if (array(items, `options.${key}`, FACT_LIMITS.options)) {
        const seen = new Set<string>();
        items.forEach((v, i) => {
          text(v, `options.${key}.${i}`, FACT_LIMITS.optionLabel, true);
          if (typeof v !== "string") return;
          const normalized = optionKey(v);
          if (seen.has(normalized)) issue(`options.${key}.${i}`, "Remove repeated option labels; capitalization and surrounding spaces do not make them different.");
          seen.add(normalized);
        });
      }
    }
    text(value.options.finish, "options.finish", FACT_LIMITS.label);
    note(value.options.note, "options.note");
  }
  if (array(value.measurements, "measurements", FACT_LIMITS.measurements)) value.measurements.forEach((v, i) => {
    const path = `measurements.${i}`;
    if (!object(v, path, ["kind", "scope", "amount", "unit", "qualifier", "note"])) return;
    choice(v.kind, measurementKinds, `${path}.kind`);
    choice(v.scope, measurementScopes, `${path}.scope`);
    decimal(v.amount, `${path}.amount`);
    choice(v.unit, measurementUnits, `${path}.unit`);
    if (typeof v.kind === "string" && measurementKinds.includes(v.kind as Measurement["kind"]) && !unitsForMeasurement(v.kind as Measurement["kind"]).includes(v.unit as Measurement["unit"])) issue(`${path}.unit`, "Choose a unit from the correct length or weight family.");
    choice(v.qualifier, qualifiers, `${path}.qualifier`);
    note(v.note, `${path}.note`);
  });
  if (array(value.materials, "materials", FACT_LIMITS.materials)) value.materials.forEach((v, i) => {
    const path = `materials.${i}`;
    if (!object(v, path, ["component", "value"])) return;
    text(v.component, `${path}.component`, FACT_LIMITS.label, true);
    text(v.value, `${path}.value`, FACT_LIMITS.label, true);
  });
  if (array(value.interfaces, "interfaces", FACT_LIMITS.interfaces)) value.interfaces.forEach((v, i) => {
    const path = `interfaces.${i}`;
    if (!object(v, path, ["kind", "role", "constraints", "limitations"])) return;
    choice(v.kind, interfaceKinds, `${path}.kind`);
    choice(v.role, interfaceRoles, `${path}.role`);
    note(v.limitations, `${path}.limitations`);
    if (array(v.constraints, `${path}.constraints`, FACT_LIMITS.constraints)) v.constraints.forEach((c, n) => {
      const cp = `${path}.constraints.${n}`;
      if (!object(c, cp, ["attribute", "operator", "value", "unit"])) return;
      choice(c.attribute, constraintAttributes, `${cp}.attribute`);
      choice(c.operator, constraintOperators, `${cp}.operator`);
      text(c.value, `${cp}.value`, FACT_LIMITS.label, true);
      choice(c.unit, ["", ...lengthUnits], `${cp}.unit`);
    });
  });
  if (array(value.components, "components", FACT_LIMITS.components)) value.components.forEach((v, i) => {
    const path = `components.${i}`;
    if (!object(v, path, ["name", "quantity", "status"])) return;
    text(v.name, `${path}.name`, FACT_LIMITS.label, true);
    if (v.quantity !== null && (!Number.isSafeInteger(v.quantity) || Number(v.quantity) < 1 || Number(v.quantity) > FACT_LIMITS.quantity)) issue(`${path}.quantity`, `Enter a whole number from 1 to ${FACT_LIMITS.quantity}, or leave blank if unknown.`);
    choice(v.status, componentStatuses, `${path}.status`);
  });
  note(value.packageNote, "packageNote", FACT_LIMITS.packageNote);
  return issues;
}

export function isCatalogFacts(value: unknown): value is CatalogFacts {
  return validateCatalogFacts(value).length === 0;
}

export function parseCatalogFacts(value: unknown): CatalogFacts | null {
  if (value === undefined || value === null) return null;
  if (!isCatalogFacts(value)) throw new Error("Invalid product facts response. Your saved data has not been changed.");
  return normalizeCatalogFacts(value);
}

export function editCatalogFacts(current: CatalogFacts, change: Partial<CatalogFacts>): CatalogFacts {
  const next = { ...current, ...change };
  const compare = (value: CatalogFacts) => JSON.stringify(value, (_key, entry) => typeof entry === "number" && !Number.isFinite(entry) ? String(entry) : entry);
  return compare(next) === compare(current) ? current : { ...next, reviewed: false };
}

export function catalogFactsPatch(value: CatalogFacts | null | undefined, touched: boolean): { catalogFacts?: CatalogFacts | null } {
  if (!touched) return {};
  if (value != null && !isCatalogFacts(value)) throw new Error("Correct the reviewed product facts fields before saving.");
  return { catalogFacts: value ? normalizeCatalogFacts(value) : null };
}

export function reviewedFactRows(value: unknown): [string, string][] {
  if (!isCatalogFacts(value) || !value.reviewed) return [];
  const rows: [string, string][] = [];
  const add = (label: string, text: string) => { if (text.trim()) rows.push([label, text]); };
  add("Colors", value.options.colors.join(", "));
  add("Sizes", value.options.sizes.join(", "));
  add("Finish", value.options.finish);
  add("Option notes", value.options.note);
  for (const m of value.measurements) add(`${factLabel(m.scope)} ${factLabel(m.kind).toLowerCase()}`, `${m.qualifier === "exact" ? "" : `${factLabel(m.qualifier)} `}${m.amount} ${m.unit}${m.note ? ` — ${m.note}` : ""}`);
  for (const material of value.materials) add(material.component ? `${material.component} material` : "Material", material.value);
  for (const int of value.interfaces) {
    const label = `${factLabel(int.kind)} interface (${int.role})`;
    const constraints = int.constraints.map(c => `${factLabel(c.attribute)}: ${c.operator === "min" ? "at least " : c.operator === "max" ? "at most " : c.operator === "listed" ? "listed as " : ""}${c.value}${c.unit ? ` ${c.unit}` : ""}`);
    add(label, [...constraints, int.limitations].filter(Boolean).join("\n") || "No dimensions specified; fit is not confirmed.");
  }
  for (const c of value.components) add(`${factLabel(c.status)} component`, `${c.name}${c.quantity === null ? " (quantity not specified)" : ` × ${c.quantity}`}`);
  add("Package note", value.packageNote);
  return rows;
}
