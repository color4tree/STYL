"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  componentStatuses, constraintAttributes, constraintOperators, editCatalogFacts, emptyCatalogFacts,
  FACT_LIMITS, factLabel, interfaceKinds, interfaceRoles, lengthUnits, measurementKinds, measurementScopes, measurementUnits,
  qualifiers, suggestedInterfaces, unitsForMeasurement, validateCatalogFacts,
  type CatalogFacts, type CatalogInterface, type FactIssue, type InterfaceConstraint, type Measurement,
} from "@/lib/catalogFacts";

const inputClass = "mt-2 min-h-12 min-w-0 w-full max-w-full rounded-xl border border-[var(--line)] bg-white px-3 py-3 text-sm";
const buttonClass = "min-h-12 min-w-12 max-w-full whitespace-normal rounded-full border border-[var(--line)] px-4 py-3 text-sm disabled:opacity-50";
const gridClass = "grid min-w-0 gap-4 sm:grid-cols-2";
type FieldProps = { prefix: string; path: string; label: string; issues: FactIssue[] };

function FieldError({ prefix, path, issues }: Omit<FieldProps, "label">) {
  const error = issues.find(issue => issue.path === path);
  return error ? <p id={`${prefix}-${path}-error`} role="alert" className="mt-1 text-sm text-red-700">{error.message}</p> : null;
}

function TextField({ prefix, path, label, issues, value, onChange, multiline = false, numeric = false, maxLength = FACT_LIMITS.text }: FieldProps & {
  value: string; onChange: (value: string) => void; multiline?: boolean; numeric?: boolean; maxLength?: number;
}) {
  const invalid = issues.some(issue => issue.path === path);
  // Browser maxlength counts UTF-16 units; validation uses the server's character bounds.
  const props = { id: `${prefix}-${path}`, value, onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => onChange(event.target.value), maxLength: maxLength * 2, className: inputClass, "aria-invalid": invalid, "aria-describedby": invalid ? `${prefix}-${path}-error` : undefined };
  return <div className="min-w-0 [overflow-wrap:anywhere]"><label htmlFor={props.id} className="text-sm font-medium">{label}</label>
    {multiline ? <textarea {...props} rows={3} /> : <input {...props} inputMode={numeric ? "decimal" : undefined} />}
    <FieldError prefix={prefix} path={path} issues={issues} />
  </div>;
}

function SelectField<T extends string>({ prefix, path, label, issues, value, values, onChange }: FieldProps & {
  value: T; values: readonly T[]; onChange: (value: T) => void;
}) {
  const invalid = issues.some(issue => issue.path === path);
  return <div className="min-w-0 [overflow-wrap:anywhere]"><label htmlFor={`${prefix}-${path}`} className="text-sm font-medium">{label}</label>
    <select id={`${prefix}-${path}`} value={value} onChange={event => onChange(event.target.value as T)} className={inputClass} aria-invalid={invalid} aria-describedby={invalid ? `${prefix}-${path}-error` : undefined}>
      {values.map(option => <option key={option} value={option}>{option ? (measurementUnits as readonly string[]).includes(option) ? option : option === "eq" ? "Equals" : option === "min" ? "At least" : option === "max" ? "At most" : option === "listed" ? "Listed text" : factLabel(option) : "Not specified"}</option>)}
    </select><FieldError prefix={prefix} path={path} issues={issues} />
  </div>;
}

function QuantityField({ value, onChange, ...props }: FieldProps & { value: number | null; onChange: (value: number | null) => void }) {
  const [draft, setDraft] = useState({ value, text: value === null ? "" : String(value) });
  if (!Object.is(value, draft.value)) setDraft({ value, text: value === null ? "" : String(value) });
  return <TextField {...props} value={draft.text} numeric maxLength={10} onChange={text => {
    const quantity = text === "" ? null : /^\d+$/.test(text) ? Number(text) : Number.NaN;
    setDraft({ value: quantity, text });
    onChange(quantity);
  }} />;
}

export default function CatalogFactsEditor({ value, category, onChange, validationAttempt = 0, reviewedAt }: {
  value?: CatalogFacts | null; category: string; onChange: (value: CatalogFacts | null) => void; validationAttempt?: number; reviewedAt?: string | null;
}) {
  const prefix = useId();
  const panel = useRef<HTMLDetailsElement>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const issues = value ? validateCatalogFacts(value) : [];
  const field = (path: string, label: string): FieldProps => ({ prefix, path, label, issues });
  const change = (update: Partial<CatalogFacts>) => { if (value) onChange(editCatalogFacts(value, update)); };

  useEffect(() => {
    if (!validationAttempt || !panel.current) return;
    const invalid = panel.current.querySelector<HTMLElement>('[aria-invalid="true"]');
    if (invalid) { panel.current.open = true; invalid.focus(); }
  }, [validationAttempt]);

  const measurement = (index: number, update: Partial<Measurement>) => value && change({ measurements: value.measurements.map((row, n) => n === index ? { ...row, ...update } : row) });
  const interfaceRow = (index: number, update: Partial<CatalogInterface>) => value && change({ interfaces: value.interfaces.map((row, n) => n === index ? { ...row, ...update } : row) });
  const constraint = (i: number, n: number, update: Partial<InterfaceConstraint>) => value && interfaceRow(i, { constraints: value.interfaces[i].constraints.map((row, x) => x === n ? { ...row, ...update } : row) });
  const suggestions = suggestedInterfaces(category);

  return <details ref={panel} className="mt-6 min-w-0 max-w-full border-t border-[var(--line)] pt-4 [overflow-wrap:anywhere]" data-testid="catalog-facts-editor">
    <summary className="min-h-12 cursor-pointer py-3 text-lg font-semibold">Reviewed product facts</summary>
    <p className="mb-4 text-sm text-[var(--muted)]">Informational only. These facts do not create sellable variants, change prices, or confirm tested fit. Leave unknown facts blank; nothing is inferred from photos or source listings.</p>
    {!value ? <>
      <p className="mb-3 text-sm">No typed facts in this draft. Existing descriptions and specifications are preserved.</p>
      <button type="button" className={buttonClass} onClick={() => { setConfirmClear(false); onChange(emptyCatalogFacts()); }}>Add product facts</button>
    </> : <div className="min-w-0 space-y-6">
      <div className="rounded-xl bg-[var(--bg)] p-3">
        <label className="flex min-h-12 items-center gap-3 text-sm font-medium">
          <input type="checkbox" className="h-5 w-5 shrink-0" checked={value.reviewed} disabled={issues.length > 0} onChange={event => onChange({ ...value, reviewed: event.target.checked })} />
          Merchant-reviewed for customer answers
        </label>
        <p className="text-sm text-[var(--muted)]">{value.reviewed ? "Reviewed facts will be available to customers after saving." : "Unreviewed draft: excluded from customer display and AI answers."} Editing a typed value clears review; review again before publishing facts.</p>
        {issues.length > 0 ? <p className="mt-2 text-sm text-red-700">Correct the highlighted facts before review or saving. Remove unused rows instead of saving incomplete values.</p> : null}
        {reviewedAt ? <p className="mt-2 text-xs text-[var(--muted)]">Last saved review: {reviewedAt}</p> : null}
      </div>

      <fieldset className="min-w-0 space-y-4"><legend className="mb-3 font-semibold">Informational options</legend>
        <div className={gridClass}>
          {(["colors", "sizes"] as const).map(key => <TextField key={key} {...field(`options.${key}`, `${factLabel(key)} (one per line)`)} value={value.options[key].join("\n")} multiline maxLength={(FACT_LIMITS.optionLabel + 1) * FACT_LIMITS.options - 1}
            issues={issues.map(issue => issue.path.startsWith(`options.${key}.`) ? { ...issue, path: `options.${key}` } : issue)}
            onChange={text => change({ options: { ...value.options, [key]: text === "" ? [] : text.split("\n") } })} />)}
          <TextField {...field("options.finish", "Finish")} value={value.options.finish} maxLength={FACT_LIMITS.label} onChange={finish => change({ options: { ...value.options, finish } })} />
          <TextField {...field("options.note", "Option note")} value={value.options.note} onChange={note => change({ options: { ...value.options, note } })} multiline />
        </div>
      </fieldset>

      <fieldset className="min-w-0 space-y-4"><legend className="mb-3 font-semibold">Scoped measurements</legend>
        {value.measurements.map((row, i) => <div key={i} className="min-w-0 space-y-4 rounded-xl border border-[var(--line)] p-3">
          <h3 className="text-sm font-medium">Measurement {i + 1}</h3>
          <div className={gridClass}>
            <SelectField {...field(`measurements.${i}.kind`, `Measurement ${i + 1} kind`)} value={row.kind} values={measurementKinds} onChange={kind => measurement(i, { kind })} />
            <SelectField {...field(`measurements.${i}.scope`, `Measurement ${i + 1} scope`)} value={row.scope} values={measurementScopes} onChange={scope => measurement(i, { scope })} />
            <TextField {...field(`measurements.${i}.amount`, `Measurement ${i + 1} amount`)} value={row.amount} numeric maxLength={FACT_LIMITS.decimal} onChange={amount => measurement(i, { amount })} />
            <SelectField {...field(`measurements.${i}.unit`, `Measurement ${i + 1} unit`)} value={row.unit} values={[...new Set([row.unit, ...unitsForMeasurement(row.kind)])]} onChange={unit => measurement(i, { unit })} />
            <SelectField {...field(`measurements.${i}.qualifier`, `Measurement ${i + 1} qualifier`)} value={row.qualifier} values={qualifiers} onChange={qualifier => measurement(i, { qualifier })} />
            <TextField {...field(`measurements.${i}.note`, `Measurement ${i + 1} note`)} value={row.note} onChange={note => measurement(i, { note })} />
          </div>
          <button type="button" className={buttonClass} onClick={() => change({ measurements: value.measurements.filter((_, n) => n !== i) })}>Remove measurement {i + 1}</button>
        </div>)}
        <button type="button" className={buttonClass} disabled={value.measurements.length >= FACT_LIMITS.measurements} onClick={() => change({ measurements: [...value.measurements, { kind: "length", scope: "overall", amount: "", unit: "mm", qualifier: "exact", note: "" }] })}>Add measurement</button>
      </fieldset>

      <fieldset className="min-w-0 space-y-4"><legend className="mb-3 font-semibold">Materials</legend>
        <p className="text-sm text-[var(--muted)]">Name the component the material describes, or enter Product for an overall material. Omit unknown materials.</p>
        {value.materials.map((row, i) => <div key={i} className="min-w-0 space-y-3 rounded-xl border border-[var(--line)] p-3">
          <div className={gridClass}>
            <TextField {...field(`materials.${i}.component`, `Material ${i + 1} component`)} value={row.component} maxLength={FACT_LIMITS.label} onChange={component => change({ materials: value.materials.map((v, n) => n === i ? { ...v, component } : v) })} />
            <TextField {...field(`materials.${i}.value`, `Material ${i + 1} value`)} value={row.value} maxLength={FACT_LIMITS.label} onChange={text => change({ materials: value.materials.map((v, n) => n === i ? { ...v, value: text } : v) })} />
          </div>
          <button type="button" className={buttonClass} onClick={() => change({ materials: value.materials.filter((_, n) => n !== i) })}>Remove material {i + 1}</button>
        </div>)}
        <button type="button" className={buttonClass} disabled={value.materials.length >= FACT_LIMITS.materials} onClick={() => change({ materials: [...value.materials, { component: "", value: "" }] })}>Add material</button>
      </fieldset>

      <fieldset className="min-w-0 space-y-4"><legend className="mb-3 font-semibold">Interfaces and requirements</legend>
        <p className="text-sm text-[var(--muted)]">{suggestions.length ? `Suggested for this category: ${suggestions.map(factLabel).join(", ")}. ` : ""}Select an interface explicitly. Every interface is available in every category; matching dimensions alone does not confirm fit.</p>
        {value.interfaces.map((row, i) => <div key={i} className="min-w-0 space-y-4 rounded-xl border border-[var(--line)] p-3">
          <div className={gridClass}>
            <SelectField {...field(`interfaces.${i}.kind`, `Interface ${i + 1} kind`)} value={row.kind} values={interfaceKinds} onChange={kind => interfaceRow(i, { kind })} />
            <SelectField {...field(`interfaces.${i}.role`, `Interface ${i + 1} role`)} value={row.role} values={interfaceRoles} onChange={role => interfaceRow(i, { role })} />
          </div>
          {row.constraints.map((c, n) => <div key={n} className="min-w-0 space-y-3 border-t border-[var(--line)] pt-3">
            <div className={gridClass}>
              <SelectField {...field(`interfaces.${i}.constraints.${n}.attribute`, `Interface ${i + 1} constraint ${n + 1} attribute`)} value={c.attribute} values={constraintAttributes} onChange={attribute => constraint(i, n, { attribute })} />
              <SelectField {...field(`interfaces.${i}.constraints.${n}.operator`, `Interface ${i + 1} constraint ${n + 1} comparison`)} value={c.operator} values={constraintOperators} onChange={operator => constraint(i, n, { operator })} />
              <TextField {...field(`interfaces.${i}.constraints.${n}.value`, `Interface ${i + 1} constraint ${n + 1} value`)} value={c.value} maxLength={FACT_LIMITS.label} onChange={text => constraint(i, n, { value: text })} />
              <SelectField {...field(`interfaces.${i}.constraints.${n}.unit`, `Interface ${i + 1} constraint ${n + 1} unit`)} value={c.unit} values={["", ...lengthUnits]} onChange={unit => constraint(i, n, { unit })} />
            </div>
            <button type="button" className={buttonClass} onClick={() => interfaceRow(i, { constraints: row.constraints.filter((_, index) => index !== n) })}>Remove interface {i + 1} constraint {n + 1}</button>
          </div>)}
          <button type="button" className={buttonClass} disabled={row.constraints.length >= FACT_LIMITS.constraints} onClick={() => interfaceRow(i, { constraints: [...row.constraints, { attribute: row.kind === "socket_drive" ? "driveSize" : row.kind === "selector_pin" ? "shaftDiameter" : row.kind === "barbell_receiver" ? "barbellDiameter" : "mountingSpan", operator: "listed", value: "", unit: "" }] })}>Add interface {i + 1} constraint</button>
          <TextField {...field(`interfaces.${i}.limitations`, `Interface ${i + 1} limitations`)} value={row.limitations} onChange={limitations => interfaceRow(i, { limitations })} multiline />
          <button type="button" className={buttonClass} onClick={() => change({ interfaces: value.interfaces.filter((_, n) => n !== i) })}>Remove interface {i + 1}</button>
        </div>)}
        <div className="min-w-0"><label className="block text-sm font-medium" htmlFor={`${prefix}-new-interface`}>Add interface (choose kind)</label>
          <select id={`${prefix}-new-interface`} value="" disabled={value.interfaces.length >= FACT_LIMITS.interfaces} className={inputClass} onChange={event => {
            if (interfaceKinds.includes(event.target.value as CatalogInterface["kind"])) change({ interfaces: [...value.interfaces, { kind: event.target.value as CatalogInterface["kind"], role: "requires", constraints: [], limitations: "" }] });
          }}><option value="">Select interface to add</option>{interfaceKinds.map(kind => <option key={kind} value={kind}>{factLabel(kind)}{suggestions.includes(kind) ? " (suggested)" : ""}</option>)}</select>
        </div>
      </fieldset>

      <fieldset className="min-w-0 space-y-4"><legend className="mb-3 font-semibold">Package components</legend>
        <p className="text-sm text-[var(--muted)]">Component counts are separate from the primary selling unit and package quantity. Blank quantity means unknown.</p>
        {value.components.map((row, i) => <div key={i} className="min-w-0 space-y-3 rounded-xl border border-[var(--line)] p-3">
          <div className={gridClass}>
            <TextField {...field(`components.${i}.name`, `Component ${i + 1} name`)} value={row.name} maxLength={FACT_LIMITS.label} onChange={name => change({ components: value.components.map((v, n) => n === i ? { ...v, name } : v) })} />
            <QuantityField {...field(`components.${i}.quantity`, `Component ${i + 1} quantity (optional)`)} value={row.quantity} onChange={quantity => change({ components: value.components.map((v, n) => n === i ? { ...v, quantity } : v) })} />
            <SelectField {...field(`components.${i}.status`, `Component ${i + 1} status`)} value={row.status} values={componentStatuses} onChange={status => change({ components: value.components.map((v, n) => n === i ? { ...v, status } : v) })} />
          </div>
          <button type="button" className={buttonClass} onClick={() => change({ components: value.components.filter((_, n) => n !== i) })}>Remove component {i + 1}</button>
        </div>)}
        <button type="button" className={buttonClass} disabled={value.components.length >= FACT_LIMITS.components} onClick={() => change({ components: [...value.components, { name: "", quantity: null, status: "unknown" }] })}>Add component</button>
        <TextField {...field("packageNote", "Package note")} value={value.packageNote} maxLength={FACT_LIMITS.packageNote} onChange={packageNote => change({ packageNote })} multiline />
      </fieldset>

      {confirmClear ? <div className="space-y-3 rounded-xl border border-red-200 p-3">
        <p className="text-sm">Remove all typed facts on the next save? Legacy specifications and descriptions will not be changed.</p>
        <div className="flex flex-wrap gap-3"><button type="button" className={buttonClass} onClick={() => { setConfirmClear(false); onChange(null); }}>Confirm clear facts</button>
          <button type="button" className={buttonClass} onClick={() => setConfirmClear(false)}>Keep facts</button></div>
      </div> : <button type="button" className={buttonClass} onClick={() => setConfirmClear(true)}>Clear typed facts</button>}
    </div>}
  </details>;
}
