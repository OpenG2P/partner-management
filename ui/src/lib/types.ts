export interface PartnerRequest {
  id: string;
  request_type: "onboarding" | "key_update";
  partner_id: string;
  name?: string | null;
  org_name?: string | null;
  description?: string | null;
  jwks_url?: string | null;
  proposed_keys: ProposedKey[];
  revoke_kids: string[];
  status: "created" | "approved" | "rejected";
  submitted_by?: string | null;
  reviewed_by?: string | null;
  review_notes?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface ProposedKey {
  kid: string;
  algorithm: string;
  public_key?: string;
  key_fingerprint?: string | null;
  not_before?: string | null;
  not_after?: string | null;
}

export interface Partner {
  id: string;
  partner_id: string;
  name: string;
  org_name?: string | null;
  description?: string | null;
  jwks_url?: string | null;
  status: "created" | "active" | "disabled";
  created_by?: string | null;
  approved_by?: string | null;
  created_at: string;
  updated_at?: string | null;
}

export interface AuditEvent {
  id: string;
  created_at: string;
  actor_name?: string | null;
  actor_id?: string | null;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  partner_id: string;
  request_id?: string | null;
  details: Record<string, unknown>;
}

export interface PartnerKey {
  id: string;
  partner_id: string;
  kid: string;
  algorithm: string;
  public_key: string;
  key_fingerprint?: string | null;
  status: "pending" | "active" | "revoked";
  not_before?: string | null;
  not_after?: string | null;
  created_at: string;
}
