"use client";

import { useEffect, useState } from "react";
import { CatalogueItem, CatalogueSource } from "@/lib/catalogue";
import { Metadata, labelOf } from "@/lib/metadata";
import { PolicyInput } from "@/lib/types";

// Form state for one policy. List fields are comma-separated text; the API
// trims entries and drops blanks/duplicates.
export interface PolicyRow {
  kind: "controller" | "use_cases";
  data_controller: string;
  grants: string; // scopes (controller) or use cases (use_cases)
  purposes: string;
  subject_id_types: string;
  signing_algs: string[];
  // New rows follow the partner's key algorithms until the user ticks a box.
  algs_from_keys: boolean;
  max_validity_duration: string;
  fetch_type: string;
  max_fetch_frequency: string;
  data_life: string;
}

export const DEFAULT_SIGNING_ALGS = ["EdDSA", "ES256"];

export const emptyPolicy = (kind: PolicyRow["kind"] = "controller"): PolicyRow => ({
  kind,
  data_controller: "",
  grants: "",
  purposes: "",
  subject_id_types: "",
  signing_algs: [...DEFAULT_SIGNING_ALGS],
  algs_from_keys: true,
  max_validity_duration: "",
  fetch_type: "oneshot",
  max_fetch_frequency: "",
  data_life: "",
});

const splitList = (v: string) =>
  v
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

export function policyRowFrom(p: PolicyInput): PolicyRow {
  const isController = !!p.data_controller;
  return {
    kind: isController ? "controller" : "use_cases",
    data_controller: p.data_controller || "",
    grants: (isController ? p.allowed_data_scopes : p.allowed_use_cases).join(", "),
    purposes: p.allowed_purposes.join(", "),
    subject_id_types: p.allowed_subject_id_types.join(", "),
    signing_algs: [...p.allowed_signing_algs],
    algs_from_keys: false,
    max_validity_duration: p.max_validity_duration || "",
    fetch_type: p.fetch_type,
    max_fetch_frequency: p.max_fetch_frequency || "",
    data_life: p.data_life || "",
  };
}

export function toPolicyInput(r: PolicyRow): PolicyInput {
  const isController = r.kind === "controller";
  return {
    data_controller: isController ? r.data_controller.trim() : null,
    allowed_data_scopes: isController ? splitList(r.grants) : [],
    allowed_use_cases: isController ? [] : splitList(r.grants),
    allowed_purposes: splitList(r.purposes),
    allowed_subject_id_types: splitList(r.subject_id_types),
    allowed_signing_algs: r.signing_algs,
    max_validity_duration: r.max_validity_duration.trim() || null,
    fetch_type: r.fetch_type,
    max_fetch_frequency: r.max_fetch_frequency.trim() || null,
    data_life: r.data_life.trim() || null,
  };
}

// The policy's key (null = the use-case policy), for display.
export function controllerLabel(dataController: string | null) {
  return dataController || "Use cases (exchange)";
}

// Blocking problems the API would also reject, so the submit button can say why.
export function policyRowProblem(r: PolicyRow): string | null {
  if (r.kind === "controller" && !r.data_controller.trim()) return "Data controller is required.";
  if (!splitList(r.grants).length)
    return r.kind === "controller"
      ? "At least one scope is required."
      : "At least one use case is required.";
  if (!r.signing_algs.length) return "At least one signing algorithm is required.";
  return null;
}

const OTHER = "__other__";

// The catalogue sources a row's grants come from: the data controller's scope
// sources, or the use-case sources.
function sourcesFor(row: PolicyRow, catalogue: CatalogueSource[]) {
  return row.kind === "controller"
    ? catalogue.filter(
        (s) => s.kind === "scopes" && s.data_controller === row.data_controller.trim(),
      )
    : catalogue.filter((s) => s.kind === "use_cases");
}

// Checkbox list of catalogue items, each with its label and description (and a
// use case's purpose). Selected IDs the catalogue does not list stay visible so
// they can be unticked.
function CatalogueChoices({
  items,
  selected,
  showUnlisted,
  onChange,
}: {
  items: CatalogueItem[];
  selected: string[];
  showUnlisted: boolean;
  onChange: (ids: string[]) => void;
}) {
  const muted = "text-[color:var(--color-text-muted)]";
  const listed = new Set(items.map((i) => i.id));
  const unlisted = showUnlisted ? selected.filter((id) => !listed.has(id)) : [];
  const toggle = (id: string, on: boolean) =>
    onChange(on ? [...selected, id] : selected.filter((x) => x !== id));
  return (
    <div className="space-y-2 max-h-72 overflow-y-auto">
      {items.map((i) => (
        <label key={i.id} className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={selected.includes(i.id)}
            onChange={(e) => toggle(i.id, e.target.checked)}
          />
          <span>
            <span className="font-medium">{i.label || i.id}</span>{" "}
            <span className={muted}>({i.id})</span>
            {i.description && <span className={`block ${muted}`}>{i.description}</span>}
            {i.purpose && <span className={`block ${muted}`}>Purpose: {i.purpose}</span>}
            {!!i.fields?.length && (
              <span className={`block text-xs ${muted}`}>Fields: {i.fields.join(", ")}</span>
            )}
          </span>
        </label>
      ))}
      {unlisted.map((id) => (
        <label key={id} className="flex items-start gap-2 text-sm">
          <input type="checkbox" className="mt-1" checked onChange={() => toggle(id, false)} />
          <span>
            <span className="font-medium">{id}</span>{" "}
            <span className="text-[color:var(--color-danger)]">not in the catalogue</span>
          </span>
        </label>
      ))}
    </div>
  );
}

// Purposes / subject ID types: the Master Data list's checklist when it loaded;
// free text when it is not configured, not in the country's pack (note), or
// could not be read (error: the request will carry a warning).
function CodeListField({
  label,
  value,
  source,
  onChange,
}: {
  label: string;
  value: string;
  source?: CatalogueSource;
  onChange: (v: string) => void;
}) {
  const muted = "text-xs mt-1 text-[color:var(--color-text-muted)]";
  const listed = source && !source.error && !source.note && source.items.length > 0;
  return (
    <div>
      <label className="field-label">{label}</label>
      {listed ? (
        <>
          <CatalogueChoices
            items={source.items}
            selected={splitList(value)}
            showUnlisted
            onChange={(ids) => onChange(ids.join(", "))}
          />
          <p className={muted}>From {source.label}. None ticked = any.</p>
        </>
      ) : (
        <>
          <input
            className="field-input"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="empty = any"
          />
          {source?.error && (
            <p className="text-xs mt-1 text-[color:var(--color-danger)]">
              {source.label}: {source.error}. Enter codes by hand; the request will carry a
              warning.
            </p>
          )}
          {source?.note && <p className={muted}>{source.note}</p>}
        </>
      )}
    </div>
  );
}

const sameSet = (a: string[], b: string[]) =>
  a.length === b.length && a.every((x) => b.includes(x));

export function PolicyEditor({
  row,
  meta,
  catalogue = [],
  onChange,
  onRemove,
  lockKey,
  keyAlgs,
}: {
  row: PolicyRow;
  meta: Metadata;
  // GET /catalogue sources; empty = free-text scopes / use cases.
  catalogue?: CatalogueSource[];
  onChange: (patch: Partial<PolicyRow>) => void;
  onRemove?: () => void;
  // Changing an existing policy: its data controller cannot change.
  lockKey?: boolean;
  // Algorithms of the partner's active (or proposed) keys; undefined = unknown.
  keyAlgs?: string[];
}) {
  const isController = row.kind === "controller";
  const problem = policyRowProblem(row);

  // Pre-fill signing algorithms from the partner's keys (new rows, until edited).
  const keyAlgsAllowed = (keyAlgs ?? []).filter((a) => meta.signing_algorithms.includes(a));
  useEffect(() => {
    if (row.algs_from_keys && keyAlgsAllowed.length && !sameSet(row.signing_algs, keyAlgsAllowed))
      onChange({ signing_algs: keyAlgsAllowed });
  });

  // Data controller: a select of the configured scope sources, plus "Other…".
  const controllers = Array.from(
    new Map(
      catalogue
        .filter((s) => s.kind === "scopes" && s.data_controller)
        .map((s) => [s.data_controller!, s.label] as const),
    ),
  );
  const [otherController, setOtherController] = useState(false);
  const dc = row.data_controller.trim();
  const isOther =
    otherController || (dc !== "" && !controllers.some(([id]) => id === dc));

  // Grants: catalogue choices when the row's sources were read; free text when
  // there is no source or one failed (its error shown).
  const sources = sourcesFor(row, catalogue);
  const failed = sources.filter((s) => s.error);
  const items = Array.from(
    new Map(sources.flatMap((s) => s.items).map((i) => [i.id, i] as const)).values(),
  );
  const pickControllerFirst = isController && controllers.length > 0 && !isOther && dc === "";
  const freeText = !pickControllerFirst && (sources.length === 0 || failed.length > 0);
  const selected = splitList(row.grants);
  const purposes = Array.from(
    new Set(
      items.filter((i) => selected.includes(i.id) && i.purpose).map((i) => i.purpose!),
    ),
  );
  return (
    <div className="border border-[color:var(--color-border)] rounded-md p-3 mb-3 space-y-3">
      <div className="flex gap-3">
        <div className="w-56">
          <label className="field-label">Policy for</label>
          <select
            className="field-input"
            value={row.kind}
            disabled={lockKey}
            onChange={(e) => onChange({ kind: e.target.value as PolicyRow["kind"], grants: "" })}
          >
            <option value="controller">Data controller (registry)</option>
            <option value="use_cases">Use cases (exchange)</option>
          </select>
        </div>
        {isController && (
          <div className="flex-1">
            <label className="field-label">Data controller *</label>
            {controllers.length > 0 && !lockKey && (
              <select
                className="field-input"
                value={isOther ? OTHER : dc}
                onChange={(e) => {
                  const v = e.target.value;
                  setOtherController(v === OTHER);
                  onChange({ data_controller: v === OTHER ? "" : v, grants: "" });
                }}
              >
                <option value="">Select a data controller…</option>
                {controllers.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label === id ? id : `${label} (${id})`}
                  </option>
                ))}
                <option value={OTHER}>Other…</option>
              </select>
            )}
            {(controllers.length === 0 || lockKey || isOther) && (
              <input
                className={`field-input${controllers.length > 0 && !lockKey ? " mt-2" : ""}`}
                value={row.data_controller}
                disabled={lockKey}
                onChange={(e) => onChange({ data_controller: e.target.value })}
                placeholder="e.g. farmer_registry"
              />
            )}
          </div>
        )}
        {onRemove && (
          <button type="button" className="btn-secondary self-end" onClick={onRemove}>
            Remove
          </button>
        )}
      </div>

      <div>
        <label className="field-label">
          {isController ? "Allowed scopes *" : "Allowed use cases *"}
        </label>
        {pickControllerFirst && (
          <p className="text-sm text-[color:var(--color-text-muted)]">
            Select a data controller to see its scopes.
          </p>
        )}
        {items.length > 0 && (
          <CatalogueChoices
            items={items}
            selected={selected}
            showUnlisted={!freeText}
            onChange={(ids) => onChange({ grants: ids.join(", ") })}
          />
        )}
        {sources.length > 0 && !freeText && items.length === 0 && (
          <p className="text-sm text-[color:var(--color-text-muted)]">
            {sources.map((s) => s.label).join(", ")} lists none.
          </p>
        )}
        {failed.map((s) => (
          <p key={s.label} className="text-xs mb-1 text-[color:var(--color-danger)]">
            {s.label}: {s.error}. Enter IDs by hand; the request will carry a warning.
          </p>
        ))}
        {freeText && (
          <>
            <input
              className={`field-input${items.length ? " mt-2" : ""}`}
              value={row.grants}
              onChange={(e) => onChange({ grants: e.target.value })}
              placeholder={
                isController ? "e.g. farmer.basic, farmer.land" : "e.g. loan-profile@1"
              }
            />
            <p className="text-xs mt-1 text-[color:var(--color-text-muted)]">
              Comma-separated.{" "}
              {isController
                ? "Scopes the registry defines."
                : "Each as name@major (the use case's major version)."}
            </p>
          </>
        )}
        {!isController && purposes.length > 0 && (
          <button
            type="button"
            className="btn-secondary mt-2"
            onClick={() => onChange({ purposes: purposes.join(", ") })}
          >
            Set purposes from selected use cases
          </button>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <CodeListField
          label="Purposes"
          value={row.purposes}
          source={catalogue.find((s) => s.kind === "purposes")}
          onChange={(v) => onChange({ purposes: v })}
        />
        <CodeListField
          label="Subject ID types"
          value={row.subject_id_types}
          source={catalogue.find((s) => s.kind === "subject_id_types")}
          onChange={(v) => onChange({ subject_id_types: v })}
        />
      </div>

      <div>
        <label className="field-label">Signing algorithms *</label>
        <div className="flex gap-4">
          {meta.signing_algorithms.map((a) => (
            <label key={a} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={row.signing_algs.includes(a)}
                onChange={(e) =>
                  onChange({
                    algs_from_keys: false,
                    signing_algs: e.target.checked
                      ? [...row.signing_algs, a]
                      : row.signing_algs.filter((x) => x !== a),
                  })
                }
              />
              {a}
              {keyAlgs?.length && !keyAlgs.includes(a) ? (
                <span className="text-[color:var(--color-text-muted)]">(no key)</span>
              ) : null}
            </label>
          ))}
        </div>
        {keyAlgs !== undefined && (
          <p className="text-xs mt-1 text-[color:var(--color-text-muted)]">
            {keyAlgs.length
              ? `The partner's keys: ${keyAlgs.join(", ")}. An algorithm with no key is accepted with a warning.`
              : "No keys to match yet."}
          </p>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="field-label">Max consent validity</label>
          <input
            className="field-input"
            value={row.max_validity_duration}
            onChange={(e) => onChange({ max_validity_duration: e.target.value })}
            placeholder="ISO-8601, e.g. P1Y (empty = no limit)"
          />
        </div>
        <div>
          <label className="field-label">Data life</label>
          <input
            className="field-input"
            value={row.data_life}
            onChange={(e) => onChange({ data_life: e.target.value })}
            placeholder="ISO-8601, e.g. P30D"
          />
        </div>
        <div>
          <label className="field-label">Fetch type</label>
          <select
            className="field-input"
            value={row.fetch_type}
            onChange={(e) => onChange({ fetch_type: e.target.value })}
          >
            {meta.fetch_types.map((f) => (
              <option key={f} value={f}>
                {labelOf(f)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="field-label">Max fetch frequency</label>
          <input
            className="field-input"
            value={row.max_fetch_frequency}
            onChange={(e) => onChange({ max_fetch_frequency: e.target.value })}
            placeholder="ISO-8601, e.g. P1D"
          />
        </div>
      </div>

      {problem && <p className="text-xs text-[color:var(--color-danger)]">{problem}</p>}
    </div>
  );
}

// Read-only summary of one policy (request detail, partner detail).
export function PolicySummary({ policy }: { policy: PolicyInput }) {
  const muted = "text-[color:var(--color-text-muted)]";
  const list = (v: string[]) => (v.length ? v.join(", ") : "any");
  const grants = policy.data_controller ? policy.allowed_data_scopes : policy.allowed_use_cases;
  return (
    <div className="text-sm space-y-1">
      <div>
        <span className={muted}>{policy.data_controller ? "Scopes: " : "Use cases: "}</span>
        {grants.join(", ") || "—"}
      </div>
      <div>
        <span className={muted}>Purposes: </span>
        {list(policy.allowed_purposes)}
        <span className={muted}> · Subject ID types: </span>
        {list(policy.allowed_subject_id_types)}
      </div>
      <div>
        <span className={muted}>Algorithms: </span>
        {policy.allowed_signing_algs.join(", ") || "—"}
        <span className={muted}> · Max validity: </span>
        {policy.max_validity_duration || "no limit"}
      </div>
      <div>
        <span className={muted}>Fetch: </span>
        {labelOf(policy.fetch_type)}
        {policy.max_fetch_frequency ? ` (at most every ${policy.max_fetch_frequency})` : ""}
        <span className={muted}> · Data life: </span>
        {policy.data_life || "—"}
      </div>
    </div>
  );
}
