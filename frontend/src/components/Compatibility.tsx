import { compatibilityFields, emptyCompatibility, type Compatibility } from "@/lib/catalogDetails";

export function CompatibilityEditor({ value, onChange }: { value?: Compatibility; onChange: (value: Compatibility) => void }) {
  const current = { ...emptyCompatibility, ...value };
  return (
    <fieldset className="min-w-0 border-t border-[var(--line)] pt-5 md:col-span-2">
      <legend className="text-lg font-semibold">Compatibility</legend>
      <div className="grid gap-4 md:grid-cols-2">
        {compatibilityFields.map((field) => (
          <label key={field.key} className={`block min-w-0 text-sm font-medium ${field.key === "limitations" ? "md:col-span-2" : ""}`}>
            {field.label}
            <textarea
              value={current[field.key]}
              onChange={(event) => onChange({ ...current, [field.key]: event.target.value })}
              maxLength={field.limit}
              placeholder={field.placeholder}
              rows={2}
              className="mt-2 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 font-normal"
            />
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function CompatibilityDetails({ value }: { value?: Compatibility }) {
  const fields = compatibilityFields.filter((field) => value?.[field.key]?.trim());
  return (
    <section className="my-5 min-w-0 border-t border-[var(--line)] pt-4">
      <h3 className="text-base font-semibold">Compatibility</h3>
      {fields.length ? (
        <dl className="mt-3 space-y-3 text-sm">
          {fields.map((field) => (
            <div key={field.key}>
              <dt className="text-[var(--muted)]">{field.label}</dt>
              <dd className="mt-1 whitespace-pre-line break-words">{value?.[field.key]}</dd>
            </div>
          ))}
        </dl>
      ) : <p className="mt-2 text-sm text-[var(--muted)]">Compatibility not specified. Contact STYL to confirm fit.</p>}
    </section>
  );
}