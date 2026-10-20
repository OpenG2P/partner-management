"use client";

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

export function PolicyEditor({
  row,
  meta,
  onChange,
  onRemove,
  lockKey,
}: {
  row: PolicyRow;
  meta: Metadata;
  onChange: (patch: Partial<PolicyRow>) => void;
  onRemove?: () => void;
  // Changing an existing policy: its data controller cannot change.
  lockKey?: boolean;
}) {
  const isController = row.kind === "controller";
  const problem = policyRowProblem(row);
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
            <input
              className="field-input"
              value={row.data_controller}
              disabled={lockKey}
              onChange={(e) => onChange({ data_controller: e.target.value })}
              placeholder="e.g. farmer_registry"
            />
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
        <input
          className="field-input"
          value={row.grants}
          onChange={(e) => onChange({ grants: e.target.value })}
          placeholder={isController ? "e.g. farmer.basic, farmer.land" : "e.g. loan-profile@1"}
        />
        <p className="text-xs mt-1 text-[color:var(--color-text-muted)]">
          Comma-separated.{" "}
          {isController
            ? "Scopes the registry defines."
            : "Each as name@major (the use case's major version)."}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="field-label">Purposes</label>
          <input
            className="field-input"
            value={row.purposes}
            onChange={(e) => onChange({ purposes: e.target.value })}
            placeholder="empty = any"
          />
        </div>
        <div>
          <label className="field-label">Subject ID types</label>
          <input
            className="field-input"
            value={row.subject_id_types}
            onChange={(e) => onChange({ subject_id_types: e.target.value })}
            placeholder="empty = any"
          />
        </div>
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
                    signing_algs: e.target.checked
                      ? [...row.signing_algs, a]
                      : row.signing_algs.filter((x) => x !== a),
                  })
                }
              />
              {a}
            </label>
          ))}
        </div>
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
