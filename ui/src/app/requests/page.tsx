"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { PartnerRequest } from "@/lib/types";
import { PageHeader, StatusPill, ErrorBanner, Empty, fmtDate } from "@/components/ui";

const FILTERS = ["", "created", "approved", "rejected"];

export default function RequestsPage() {
  const [rows, setRows] = useState<PartnerRequest[]>([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .get<{ requests: PartnerRequest[] }>(
        `/partners/requests${status ? `?status=${status}` : ""}`
      )
      .then((d) => setRows(d.requests))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [status]);

  return (
    <div>
      <PageHeader
        title="Requests"
        subtitle="Onboarding and key-rotation requests awaiting review"
        action={
          <Link href="/onboard" className="btn-primary">
            + Onboard partner
          </Link>
        }
      />

      <div className="flex gap-2 mb-4">
        {FILTERS.map((f) => (
          <button
            key={f || "all"}
            onClick={() => setStatus(f)}
            className={status === f ? "btn-primary" : "btn-secondary"}
          >
            {f || "All"}
          </button>
        ))}
      </div>

      <ErrorBanner message={error} />

      {loading ? (
        <Empty message="Loading…" />
      ) : rows.length === 0 ? (
        <Empty message="No requests found." />
      ) : (
        <div className="card p-0 overflow-hidden">
          <table className="data-table">
            <thead>
              <tr>
                <th>Partner ID</th>
                <th>Type</th>
                <th>Keys</th>
                <th>Status</th>
                <th>Submitted by</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td className="font-medium">{r.partner_id}</td>
                  <td>{r.request_type === "onboarding" ? "Onboarding" : "Key update"}</td>
                  <td>
                    +{r.proposed_keys?.length || 0}
                    {r.revoke_kids?.length ? ` / −${r.revoke_kids.length}` : ""}
                  </td>
                  <td>
                    <StatusPill status={r.status} />
                  </td>
                  <td>{r.submitted_by || "—"}</td>
                  <td>{fmtDate(r.created_at)}</td>
                  <td>
                    <Link
                      href={`/requests/${r.id}`}
                      className="text-sm underline underline-offset-2"
                    >
                      Review
                    </Link>
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
