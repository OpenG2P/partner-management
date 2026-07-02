"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { PartnerRequest } from "@/lib/types";
import { PageHeader, ErrorBanner } from "@/components/ui";

const ALGS = ["auto", "RS256", "ES256", "EdDSA"];

interface KeyRow {
  public_key: string;
  kid: string;
  algorithm: string;
}

const emptyKey = (): KeyRow => ({ public_key: "", kid: "", algorithm: "auto" });

function OnboardForm() {
  const router = useRouter();
  const params = useSearchParams();
  const mode = params.get("mode") === "key-update" ? "key-update" : "onboarding";
  const presetPartner = params.get("partner_id") || "";

  const [partnerId, setPartnerId] = useState(presetPartner);
  const [name, setName] = useState("");
  const [orgName, setOrgName] = useState("");
  const [description, setDescription] = useState("");
  const [jwksUrl, setJwksUrl] = useState("");
  const [importJwks, setImportJwks] = useState(false);
  const [revokeKids, setRevokeKids] = useState("");
  const [keys, setKeys] = useState<KeyRow[]>([emptyKey()]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const isUpdate = mode === "key-update";

  function setKey(i: number, patch: Partial<KeyRow>) {
    setKeys((ks) => ks.map((k, idx) => (idx === i ? { ...k, ...patch } : k)));
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const cleanKeys = keys
        .filter((k) => k.public_key.trim())
        .map((k) => ({
          public_key: k.public_key.trim(),
          ...(k.kid.trim() ? { kid: k.kid.trim() } : {}),
          ...(k.algorithm !== "auto" ? { algorithm: k.algorithm } : {}),
        }));

      let req: PartnerRequest;
      if (isUpdate) {
        req = await api.post<PartnerRequest>("/partners/requests/key-update", {
          partner_id: partnerId,
          description,
          jwks_url: jwksUrl || null,
          import_from_jwks_url: importJwks,
          keys: cleanKeys,
          revoke_kids: revokeKids
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        });
      } else {
        req = await api.post<PartnerRequest>("/partners/requests/onboarding", {
          partner_id: partnerId,
          name,
          org_name: orgName || null,
          description,
          jwks_url: jwksUrl || null,
          import_from_jwks_url: importJwks,
          keys: cleanKeys,
        });
      }
      router.push(`/requests/${req.id}`);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-3xl">
      <PageHeader
        title={isUpdate ? "Rotate / add keys" : "Onboard a partner"}
        subtitle={
          isUpdate
            ? "File a key-update request for an existing partner"
            : "Register a new partner and its initial public key(s)"
        }
      />
      <ErrorBanner message={error} />

      <div className="card space-y-4">
        <div>
          <label className="field-label">Partner ID *</label>
          <input
            className="field-input"
            value={partnerId}
            disabled={isUpdate && !!presetPartner}
            onChange={(e) => setPartnerId(e.target.value)}
            placeholder="e.g. PARTNER_G2P_BRIDGE"
          />
        </div>

        {!isUpdate && (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="field-label">Name *</label>
              <input
                className="field-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div>
              <label className="field-label">Organisation</label>
              <input
                className="field-input"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
              />
            </div>
          </div>
        )}

        <div>
          <label className="field-label">Description</label>
          <textarea
            className="field-input"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={isUpdate ? "e.g. Scheduled quarterly key rotation" : "Reason for onboarding"}
          />
        </div>

        <div className="border-t border-[color:var(--color-border)] pt-4">
          <div className="flex items-center justify-between mb-2">
            <label className="field-label mb-0">Public keys</label>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setKeys((ks) => [...ks, emptyKey()])}
            >
              + Add key
            </button>
          </div>

          {keys.map((k, i) => (
            <div key={i} className="border border-[color:var(--color-border)] rounded-md p-3 mb-3">
              <div className="flex gap-3 mb-2">
                <div className="flex-1">
                  <label className="field-label">Key ID (optional)</label>
                  <input
                    className="field-input"
                    value={k.kid}
                    onChange={(e) => setKey(i, { kid: e.target.value })}
                    placeholder="defaults to fingerprint"
                  />
                </div>
                <div className="w-40">
                  <label className="field-label">Algorithm</label>
                  <select
                    className="field-input"
                    value={k.algorithm}
                    onChange={(e) => setKey(i, { algorithm: e.target.value })}
                  >
                    {ALGS.map((a) => (
                      <option key={a} value={a}>
                        {a}
                      </option>
                    ))}
                  </select>
                </div>
                {keys.length > 1 && (
                  <button
                    type="button"
                    className="btn-secondary self-end"
                    onClick={() => setKeys((ks) => ks.filter((_, idx) => idx !== i))}
                  >
                    Remove
                  </button>
                )}
              </div>
              <label className="field-label">PEM (SPKI or X.509 certificate) or JWK JSON</label>
              <textarea
                className="field-input font-mono text-xs"
                rows={5}
                value={k.public_key}
                onChange={(e) => setKey(i, { public_key: e.target.value })}
                placeholder="-----BEGIN PUBLIC KEY-----&#10;...&#10;-----END PUBLIC KEY-----"
              />
            </div>
          ))}
        </div>

        <div className="border-t border-[color:var(--color-border)] pt-4">
          <label className="field-label">JWKS URL (optional)</label>
          <input
            className="field-input"
            value={jwksUrl}
            onChange={(e) => setJwksUrl(e.target.value)}
            placeholder="https://partner.example.org/.well-known/jwks.json"
          />
          <label className="flex items-center gap-2 mt-2 text-sm">
            <input
              type="checkbox"
              checked={importJwks}
              onChange={(e) => setImportJwks(e.target.checked)}
            />
            Import keys from this JWKS URL now (fetched once and stored)
          </label>
        </div>

        {isUpdate && (
          <div>
            <label className="field-label">Revoke key IDs (comma-separated, optional)</label>
            <input
              className="field-input"
              value={revokeKids}
              onChange={(e) => setRevokeKids(e.target.value)}
              placeholder="old-key-1, old-key-2"
            />
          </div>
        )}

        <div className="flex gap-3 pt-2">
          <button className="btn-primary" disabled={busy} onClick={submit}>
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

export default function OnboardPage() {
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <OnboardForm />
    </Suspense>
  );
}
