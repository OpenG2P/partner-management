# OpenG2P Partner Management

Central registry of OpenG2P **partners** and their **public keys**, with a
simple staff-run admin portal.

All OpenG2P modules (g2p-bridge, consent-manager, …) fetch partner public keys
from this service to verify partner signatures, instead of each maintaining its
own partner table.

## Layout

```
partner-management/
├── core/api/        FastAPI package (openg2p-partner-management-api) with two
│                    entrypoints: staff_portal_main (staff-portal-api) and
│                    partner_main (partner-api). Shared models + DB.
├── ui/              Staff portal (Next.js, OpenG2P/AWE branding, IAM login)
├── docker/          Dockerfiles: staff-portal-api, partner-api, staff-portal-ui
├── deployment/      Helm chart (deployment/charts/partner-management)
└── .github/         CI workflows (docker build, helm publish, tests)
```

Following the national-social-registry pattern, the backend is split into two
deployables that share one package and one database:

* **staff-portal-api** — the staff/admin-facing API (onboarding, approvals,
  partner management), guarded by a Keycloak **staff**-realm JWT + the
  `partner_manager` role. The UI calls this for all domain operations.
* **partner-api** — the unauthenticated key-fetch API other OpenG2P modules
  call. No caller signature; internal gateway only.

Staff **login** is handled by the shared `commons-services-iam-staff-portal-api`
(the UI's `IAM_URL`), exactly as national-social-registry wires it.

## Concepts

- **Partner** — a third party, addressed by an admin-supplied `partner_id`.
  Lifecycle: `created` → (admin approves) `active` → `disabled`.
- **Partner key** — a public key (`kid`, algorithm, PEM), lifecycle
  `active`/`revoked`. Multiple active keys allow zero-downtime rotation.
- **Request** — an admin-facing workflow record for `onboarding` or `key_update`
  (rotation). Carries a free-text description; approving it applies the keys.
- **Key fetch** — unauthenticated APIs return a partner's active public keys by
  `partner_id`/`kid`, plus a per-partner JWKS. Fail-closed: unknown or disabled
  partners get a uniform `404 not available`.

See [`core/api/README.md`](core/api/README.md) for the API, and the GitBook
under *Platform Services → Partner Management* for full documentation.

## Key formats & algorithms

Keys are accepted as PEM (SubjectPublicKeyInfo or X.509 certificate) or JWK, and
stored canonically as PEM. Supported algorithms: **RS256, ES256, EdDSA** — the
union of what g2p-bridge and consent-manager verify today.

## License

Mozilla Public License 2.0 — see [LICENSE](LICENSE).
