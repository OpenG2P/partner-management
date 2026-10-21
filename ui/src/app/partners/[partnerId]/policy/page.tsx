"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useCatalogue } from "@/lib/catalogue";
import { useMetadata } from "@/lib/metadata";
import { PartnerKey, PartnerPolicy, PartnerRequest } from "@/lib/types";
import { PageHeader, BackLink, ErrorBanner } from "@/components/ui";
import {
  PolicyEditor,
  PolicyRow,
  PolicySummary,
  controllerLabel,
  emptyPolicy,
  policyRowFrom,
  policyRowProblem,
  toPolicyInput,
} from "@/components/policy";

// A policy row being edited; `existing` = it changes this active policy's
// data controller (null = the use-case policy), so the key is locked.
interface EditRow {
  row: PolicyRow;
  existing?: string | null;
}

// Revocation key for a data controller (null = the use-case policy).
const keyOf = (dc: string | null) => dc ?? "";

export default function ChangePolicyPage() {
  const params = useParams<{ partnerId: string }>();
  const partnerId = decodeURIComponent(params.partnerId);
  const router = useRouter();
  const meta = useMetadata();
  const catalogue = useCatalogue();

  const [active, setActive] = useState<PartnerPolicy[]>([]);
  // Algorithms of the partner's active keys (pre-fill new policies' algorithms).
  const [keyAlgs, setKeyAlgs] = useState<string[] | undefined>(undefined);
  const [rows, setRows] = useState<EditRow[]>([]);
  const [revoke, setRevoke] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .get<PartnerPolicy[]>(`/partners/${encodeURIComponent(partnerId)}/policies`)
      .then(setActive)
      .catch((e) => setError(e.message));
    api
      .get<PartnerKey[]>(`/partners/${encodeURIComponent(partnerId)}/keys`)
      .then((ks) =>
        setKeyAlgs(
          Array.from(new Set(ks.filter((k) => k.status === "active").map((k) => k.algorithm))).sort(),
        ),
      )
      .catch(() => setKeyAlgs(undefined)); // only a pre-fill: the form works without it
  }, [partnerId]);

  const editing = new Set(
    rows.filter((r) => r.existing !== undefined).map((r) => keyOf(r.existing!)),
  );
  const invalid = rows.some((r) => policyRowProblem(r.row) !== null);
  const empty = rows.length === 0 && revoke.length === 0;

  function setRow(i: number, patch: Partial<PolicyRow>) {
    setRows((rs) => rs.map((r, idx) => (idx === i ? { ...r, row: { ...r.row, ...patch } } : r)));
  }

  function change(p: PartnerPolicy) {
    setRevoke((cur) => cur.filter((k) => k !== keyOf(p.data_controller)));
    setRows((rs) => [...rs, { row: policyRowFrom(p), existing: p.data_controller }]);
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const req = await api.post<PartnerRequest>("/partners/requests/policy", {
        partner_id: partnerId,
        description: description || null,
        policies: rows.map((r) => toPolicyInput(r.row)),
        // "" = the use-case policy (the API stores it as null).
        revoke_data_controllers: revoke,
      });
      router.push(`/requests/${req.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl">
      <BackLink href={`/partners/${encodeURIComponent(partnerId)}`} label={partnerId} />
      <PageHeader
        title="Change policy"
        subtitle={`File a policy request for ${partnerId}: new versions apply, revocations take effect, on approval`}
      />
      <ErrorBanner message={error} />

      <div className="card space-y-4">
        <div>
          <label className="field-label">Active policies</label>
          {active.length === 0 ? (
            <p className="text-sm text-[color:var(--color-text-muted)]">No active policies.</p>
          ) : (
            <div className="space-y-2">
              {active.map((p) => {
                const k = keyOf(p.data_controller);
                return (
                  <div
                    key={p.id}
                    className="border border-[color:var(--color-border)] rounded-md p-3"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="font-medium">
                        {controllerLabel(p.data_controller)}{" "}
                        <span className="text-[color:var(--color-text-muted)] font-normal">
                          v{p.version}
                        </span>
                      </div>
                      <div className="flex items-center gap-3">
                        <label className="flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={revoke.includes(k)}
                            disabled={editing.has(k)}
                            onChange={(e) =>
                              setRevoke((cur) =>
                                e.target.checked ? [...cur, k] : cur.filter((x) => x !== k),
                              )
                            }
                          />
                          Revoke
                        </label>
                        <button
                          type="button"
                          className="btn-secondary"
                          disabled={editing.has(k)}
                          onClick={() => change(p)}
                        >
                          Change
                        </button>
                      </div>
                    </div>
                    <PolicySummary policy={p} />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="border-t border-[color:var(--color-border)] pt-4">
          <div className="flex items-center justify-between mb-2">
            <label className="field-label mb-0">New policy versions</label>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setRows((rs) => [...rs, { row: emptyPolicy() }])}
            >
              + Add policy
            </button>
          </div>
          {rows.length === 0 && (
            <p className="text-sm text-[color:var(--color-text-muted)]">
              Use “Change” on an active policy, or add a policy for another data controller.
            </p>
          )}
          {rows.map((r, i) => (
            <PolicyEditor
              key={i}
              row={r.row}
              meta={meta}
              catalogue={catalogue}
              lockKey={r.existing !== undefined}
              keyAlgs={keyAlgs}
              onChange={(patch) => setRow(i, patch)}
              onRemove={() => setRows((rs) => rs.filter((_, idx) => idx !== i))}
            />
          ))}
        </div>

        <div>
          <label className="field-label">Description</label>
          <textarea
            className="field-input"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Why the policy is changing"
          />
        </div>

        <div className="flex gap-3 pt-2">
          <button className="btn-primary" disabled={busy || invalid || empty} onClick={submit}>
            {busy ? "Submitting…" : "Submit request"}
          </button>
          <button className="btn-secondary" onClick={() => router.back()}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
