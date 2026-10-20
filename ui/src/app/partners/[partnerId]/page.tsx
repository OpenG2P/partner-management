"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { AuditEvent, Partner, PartnerKey, PartnerPolicy } from "@/lib/types";
import { PolicySummary, controllerLabel } from "@/components/policy";
import {
  PageHeader,
  StatusPill,
  BackLink,
  ErrorBanner,
  fmtDate,
} from "@/components/ui";

export default function PartnerDetailPage() {
  const params = useParams<{ partnerId: string }>();
  const partnerId = decodeURIComponent(params.partnerId);
  const [partner, setPartner] = useState<Partner | null>(null);
  const [keys, setKeys] = useState<PartnerKey[]>([]);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  // Every version; the active ones are shown first, the rest under history.
  const [policies, setPolicies] = useState<PartnerPolicy[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, k, pol, a] = await Promise.all([
        api.get<Partner>(`/partners/${encodeURIComponent(partnerId)}`),
        api.get<PartnerKey[]>(`/partners/${encodeURIComponent(partnerId)}/keys`),
        api.get<PartnerPolicy[]>(
          `/partners/${encodeURIComponent(partnerId)}/policies?all_versions=true`
        ),
        api.get<{ events: AuditEvent[] }>(
          `/partners/${encodeURIComponent(partnerId)}/audit`
        ),
      ]);
      setPartner(p);
      setKeys(k);
      setPolicies(pol);
      setAudit(a.events);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [partnerId]);

  useEffect(() => {
    load();
  }, [load]);

  async function toggle(action: "disable" | "enable") {
    setBusy(true);
    setError(null);
    try {
      await api.post(`/partners/${encodeURIComponent(partnerId)}/${action}`);
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!partner) {
    return (
      <div>
        <BackLink href="/partners" label="Partners" />
        <ErrorBanner message={error} />
        {!error && <p className="mt-4">Loading…</p>}
      </div>
    );
  }

  const activePolicies = policies.filter((p) => p.status === "active");
  const otherPolicies = policies.filter((p) => p.status !== "active");

  return (
    <div>
      <BackLink href="/partners" label="Partners" />
      <PageHeader
        title={partner.partner_id}
        subtitle={partner.name}
        action={
          <div className="flex items-center gap-3">
            <StatusPill status={partner.status} />
            {partner.status === "disabled" ? (
              <button className="btn-primary" disabled={busy} onClick={() => toggle("enable")}>
                Enable
              </button>
            ) : (
              <button className="btn-danger" disabled={busy} onClick={() => toggle("disable")}>
                Disable
              </button>
            )}
          </div>
        }
      />

      <ErrorBanner message={error} />

      <div className="card mb-4">
        <div className="grid grid-cols-2 gap-x-8 gap-y-2">
          <Detail label="Organisation" value={partner.org_name} />
          <Detail label="JWKS URL" value={partner.jwks_url} />
          <Detail label="Created by" value={partner.created_by} />
          <Detail label="Approved by" value={partner.approved_by} />
          <Detail label="Created" value={fmtDate(partner.created_at)} />
          <Detail label="Description" value={partner.description} />
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <h2 className="text-lg">Keys</h2>
        <Link
          href={`/onboard?mode=key-update&partner_id=${encodeURIComponent(partner.partner_id)}`}
          className="btn-secondary"
        >
          Rotate / add keys
        </Link>
      </div>

      {keys.length === 0 ? (
        <div className="card text-[color:var(--color-text-muted)]">No keys.</div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="data-table">
            <thead>
              <tr>
                <th>Key ID</th>
                <th>Algorithm</th>
                <th>Fingerprint</th>
                <th>Status</th>
                <th>Not before</th>
                <th>Not after</th>
              </tr>
            </thead>
            <tbody>
              {keys.map((k) => (
                <tr key={k.id}>
                  <td className="font-medium">{k.kid}</td>
                  <td>{k.algorithm}</td>
                  <td title={k.key_fingerprint || ""}>
                    {k.key_fingerprint ? k.key_fingerprint.slice(0, 16) + "…" : "—"}
                  </td>
                  <td>
                    <StatusPill status={k.status} />
                  </td>
                  <td>{fmtDate(k.not_before)}</td>
                  <td>{fmtDate(k.not_after)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between mt-6 mb-3">
        <h2 className="text-lg">Policies</h2>
        {partner.status === "active" && (
          <Link
            href={`/partners/${encodeURIComponent(partner.partner_id)}/policy`}
            className="btn-secondary"
          >
            Change policy
          </Link>
        )}
      </div>

      {activePolicies.length === 0 ? (
        <div className="card text-[color:var(--color-text-muted)]">No active policies.</div>
      ) : (
        <div className="space-y-3">
          {activePolicies.map((p) => (
            <div key={p.id} className="card">
              <div className="flex items-center justify-between mb-2">
                <div className="font-medium">
                  {controllerLabel(p.data_controller)}{" "}
                  <span className="text-[color:var(--color-text-muted)] font-normal">
                    v{p.version} · since {fmtDate(p.effective_from)}
                    {p.approved_by ? ` · approved by ${p.approved_by}` : ""}
                  </span>
                </div>
                <StatusPill status={p.status} />
              </div>
              <PolicySummary policy={p} />
            </div>
          ))}
        </div>
      )}

      {otherPolicies.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            className="text-sm underline underline-offset-2"
            onClick={() => setShowHistory((v) => !v)}
          >
            {showHistory ? "Hide" : "Show"} policy version history ({otherPolicies.length})
          </button>
          {showHistory && (
            <div className="card p-0 overflow-hidden mt-3">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Policy for</th>
                    <th>Version</th>
                    <th>Status</th>
                    <th>Grants</th>
                    <th>Created</th>
                    <th>Request</th>
                  </tr>
                </thead>
                <tbody>
                  {otherPolicies.map((p) => (
                    <tr key={p.id}>
                      <td className="font-medium">{controllerLabel(p.data_controller)}</td>
                      <td>v{p.version}</td>
                      <td>
                        <StatusPill status={p.status} />
                      </td>
                      <td className="text-[color:var(--color-text-muted)]">
                        {(p.data_controller ? p.allowed_data_scopes : p.allowed_use_cases).join(", ")}
                      </td>
                      <td>{fmtDate(p.created_at)}</td>
                      <td>
                        <Link
                          href={`/requests/${p.request_id}`}
                          className="text-sm underline underline-offset-2"
                        >
                          View
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <h2 className="text-lg mt-6 mb-3">History</h2>
      {audit.length === 0 ? (
        <div className="card text-[color:var(--color-text-muted)]">No activity yet.</div>
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>By</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {audit.map((e) => (
                <tr key={e.id}>
                  <td className="whitespace-nowrap">{fmtDate(e.created_at)}</td>
                  <td className="font-medium">{e.action}</td>
                  <td>{e.actor_name || "—"}</td>
                  <td className="text-[color:var(--color-text-muted)]">
                    {Object.keys(e.details || {}).length
                      ? JSON.stringify(e.details)
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function Detail({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <div className="text-xs text-[color:var(--color-text-muted)]">{label}</div>
      <div className="break-words">{value || "—"}</div>
    </div>
  );
}
