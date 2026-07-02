"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { Partner, PartnerKey } from "@/lib/types";
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
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [p, k] = await Promise.all([
        api.get<Partner>(`/partners/${encodeURIComponent(partnerId)}`),
        api.get<PartnerKey[]>(`/partners/${encodeURIComponent(partnerId)}/keys`),
      ]);
      setPartner(p);
      setKeys(k);
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
