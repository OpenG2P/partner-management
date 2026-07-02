#!/usr/bin/env bash
#
# uninstall-partner-management.sh
# -------------------------------
# Cleanly uninstall an OpenG2P Partner Management Helm release and every resource
# it touched, including the PostgreSQL database and role that live inside the
# commons-postgresql instance (which are NOT owned by the Partner Management Helm
# release and therefore survive `helm uninstall`).
#
# What it does, in order:
#   0. Stop in-flight hook Jobs           (so `helm uninstall --wait` doesn't hang)
#   1. helm uninstall <release>           (staff-portal-api, partner-api,
#                                          staff-portal-ui workloads, services,
#                                          helm-owned secrets & configmaps, the
#                                          keycloak client K8s secret, etc.)
#   2. Delete leftover Jobs + their Pods  (postgres-init / keycloak-init /
#                                          db-password-sync keep themselves around
#                                          via hook-delete-policy: before-hook-creation)
#   3. Sweep leftover Secrets/ConfigMaps  (label: app.kubernetes.io/instance)
#   4. Drop Postgres database + role      (via `kubectl exec` into commons-postgresql)
#   5. Delete PVCs by label               (app.kubernetes.io/instance)
#   6. Delete PVs still bound to those PVCs
#
# Database dropped (only the one THIS chart's postgres-init creates):
#   - <release-underscored>            e.g. partner_management
# It does NOT drop registry_db, pbms_db, g2p_bridge, etc. — those belong to other
# components.
#
# Requires: kubectl (cluster admin), helm, bash 4+.
#
# USAGE:
#   ./uninstall-partner-management.sh \
#       --namespace <ns> \
#       [--release <name>]            (default: partner-management)
#       [--postgres-release <name>]   (default: commons-postgresql)
#       [--postgres-namespace <ns>]   (default: same as --namespace)
#       [--keep-pvs]                  (delete PVCs but not PVs)
#       [--dry-run]                   (print actions, change nothing)
#       [--yes]                       (skip interactive confirmation)
#
# EXAMPLES:
#   # Dry run first — no changes made:
#   ./uninstall-partner-management.sh --namespace trial --dry-run
#
#   # For real, with confirmation prompt:
#   ./uninstall-partner-management.sh --namespace trial
#
#   # Non-interactive (CI / scripted):
#   ./uninstall-partner-management.sh --namespace trial --yes

set -euo pipefail

# ---------- defaults ----------
RELEASE="partner-management"
NAMESPACE=""
POSTGRES_RELEASE="commons-postgresql"
POSTGRES_NAMESPACE=""
KEEP_PVS=false
DRY_RUN=false
ASSUME_YES=false

# ---------- cli ----------
usage() { sed -n '2,50p' "$0"; exit 1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --release)            RELEASE="$2";            shift 2 ;;
    --namespace|-n)       NAMESPACE="$2";          shift 2 ;;
    --postgres-release)   POSTGRES_RELEASE="$2";   shift 2 ;;
    --postgres-namespace) POSTGRES_NAMESPACE="$2"; shift 2 ;;
    --keep-pvs)           KEEP_PVS=true;           shift ;;
    --dry-run)            DRY_RUN=true;            shift ;;
    --yes|-y)             ASSUME_YES=true;         shift ;;
    -h|--help)            usage ;;
    *) echo "Unknown argument: $1"; usage ;;
  esac
done

[[ -z "$NAMESPACE" ]] && { echo "ERROR: --namespace is required"; exit 1; }
[[ -z "$POSTGRES_NAMESPACE" ]] && POSTGRES_NAMESPACE="$NAMESPACE"

# ---------- derived: DB / user names (templated exactly like values.yaml) ----------
# values.yaml (global):
#   pmDB:     '{{ printf "%s" .Release.Name | replace "-" "_" }}'
#   pmDBUser: '{{ printf "%s_user" .Release.Name | replace "-" "_" }}'
RELEASE_UNDERSCORED="${RELEASE//-/_}"
PM_DB="${RELEASE_UNDERSCORED}"
PM_USER="${RELEASE_UNDERSCORED}_user"

# ---------- helpers ----------
_red()   { printf "\033[31m%s\033[0m\n" "$*"; }
_green() { printf "\033[32m%s\033[0m\n" "$*"; }
_yellow(){ printf "\033[33m%s\033[0m\n" "$*"; }
_blue()  { printf "\033[34m%s\033[0m\n" "$*"; }

run() {
  # Print + execute, or just print if --dry-run. Never aborts the script on
  # non-zero exit — cleanup commands must be idempotent.
  echo "  \$ $*"
  if [[ "$DRY_RUN" == false ]]; then
    eval "$@" || _yellow "  (command returned non-zero — continuing)"
  fi
}

kexec_psql() {
  # Run SQL as postgres superuser inside the commons-postgresql pod, using
  # PGPASSWORD from the pod's env. Tolerant of failure — script continues.
  local sql="$1"
  local cmd=(kubectl exec -n "$POSTGRES_NAMESPACE" "$PG_POD" -c postgresql -- \
             bash -c "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -U postgres -v ON_ERROR_STOP=0 -c \"$sql\"")
  echo "  \$ psql -U postgres -c \"$sql\""
  if [[ "$DRY_RUN" == false ]]; then
    "${cmd[@]}" || _yellow "  (psql returned non-zero — continuing)"
  fi
}

# ---------- pre-flight ----------
_blue "==> Pre-flight checks"

command -v kubectl >/dev/null || { _red "kubectl not found"; exit 1; }
command -v helm    >/dev/null || { _red "helm not found";    exit 1; }

if kubectl get ns "$NAMESPACE" >/dev/null 2>&1; then
  NAMESPACE_EXISTS=true
  _green "  Namespace '$NAMESPACE' exists"
else
  NAMESPACE_EXISTS=false
  _yellow "  Namespace '$NAMESPACE' does not exist — namespace-scoped cleanup will be skipped"
fi

# Locate commons-postgresql pod. Bitnami's chart gives it these labels.
PG_POD=""
if kubectl get ns "$POSTGRES_NAMESPACE" >/dev/null 2>&1; then
  PG_POD=$(kubectl get pod -n "$POSTGRES_NAMESPACE" \
    -l "app.kubernetes.io/instance=$POSTGRES_RELEASE,app.kubernetes.io/name=postgresql" \
    -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)

  # Fallback: by name.
  if [[ -z "$PG_POD" ]]; then
    if kubectl get pod -n "$POSTGRES_NAMESPACE" "${POSTGRES_RELEASE}-0" >/dev/null 2>&1; then
      PG_POD="${POSTGRES_RELEASE}-0"
    fi
  fi
fi

if [[ -z "$PG_POD" ]]; then
  PG_POD_FOUND=false
  _yellow "  commons-postgresql pod not found — DB / role drop step will be skipped"
  _yellow "  (tried label app.kubernetes.io/instance=$POSTGRES_RELEASE and pod name ${POSTGRES_RELEASE}-0 in namespace '$POSTGRES_NAMESPACE')"
else
  PG_POD_FOUND=true
  _green "  Found Postgres pod: $PG_POD (namespace: $POSTGRES_NAMESPACE)"
fi

if helm -n "$NAMESPACE" status "$RELEASE" >/dev/null 2>&1; then
  _green "  Helm release '$RELEASE' found in namespace '$NAMESPACE'"
  HELM_RELEASE_EXISTS=true
else
  _yellow "  Helm release '$RELEASE' not found — will skip helm uninstall step"
  HELM_RELEASE_EXISTS=false
fi

# ---------- show the blast radius ----------
_blue "==> Plan"
echo
echo "Will DELETE:"
echo "  - Helm release:        $RELEASE (namespace: $NAMESPACE)"
echo "  - Postgres database:   $PM_DB   (dropped INSIDE postgres via the SQL below)"
echo "  - Postgres role:       $PM_USER"
echo "  - namespace resources: Jobs/Secrets/ConfigMaps/PVCs/PVs labeled app.kubernetes.io/instance=$RELEASE"
echo
echo "Will PRESERVE (NOT deleted):"
echo "  - Postgres instance/pod: ${PG_POD:-<not found — DB drop will be skipped>} ($POSTGRES_NAMESPACE)"
echo "      (the script only 'kubectl exec's into it to DROP the database/role above)"
echo "  - Other databases:       registry_db, pbms_db, g2p_bridge, … (owned by other components)"
echo "  - Shared commons IAM (commons-services-iam-staff-portal-api) and Keycloak"
echo

if [[ "$NAMESPACE_EXISTS" == true ]]; then
  for kind in job secret configmap pvc; do
    echo "${kind}s (label app.kubernetes.io/instance=$RELEASE):"
    kubectl -n "$NAMESPACE" get "$kind" -l "app.kubernetes.io/instance=$RELEASE" \
      --no-headers 2>/dev/null | awk '{print "  - " $1}' || echo "  (none)"
  done
else
  echo "(namespace '$NAMESPACE' does not exist — no namespace-scoped resources to preview)"
fi
echo

# ---------- confirmation ----------
if [[ "$DRY_RUN" == true ]]; then
  _yellow "DRY-RUN: no changes will be made."
fi

if [[ "$ASSUME_YES" == false && "$DRY_RUN" == false ]]; then
  _red "This is destructive. Type the release name ('$RELEASE') to confirm:"
  read -r CONFIRM
  if [[ "$CONFIRM" != "$RELEASE" ]]; then
    _red "Confirmation did not match. Aborting."
    exit 1
  fi
fi

# ========== STEP 0: stop in-flight hook Jobs FIRST ==========
_blue "==> [0/6] Stop in-flight Jobs so the uninstall doesn't hang"
if [[ "$NAMESPACE_EXISTS" == true ]]; then
  run "kubectl -n '$NAMESPACE' delete job -l 'app.kubernetes.io/instance=$RELEASE' --ignore-not-found --wait=false"
  run "kubectl -n '$NAMESPACE' delete pod -l 'app.kubernetes.io/instance=$RELEASE' --ignore-not-found --force --grace-period=0 --wait=false"
else
  echo "  (skipped — namespace '$NAMESPACE' not present)"
fi

# ========== STEP 1: helm uninstall ==========
_blue "==> [1/6] Helm uninstall"
if [[ "$HELM_RELEASE_EXISTS" == true ]]; then
  run "helm uninstall '$RELEASE' -n '$NAMESPACE' --wait --timeout 5m || true"
else
  echo "  (skipped — release not present)"
fi

# ========== STEP 2: delete leftover Jobs (and their Pods) ==========
# Subchart / hook Jobs (postgres-init, keycloak-init, db-password-sync) are
# created with `helm.sh/hook-delete-policy: before-hook-creation`, so they are
# NOT cleaned up by `helm uninstall`. Delete them explicitly BEFORE dropping the
# DB, so their Pods close their Postgres connections cleanly.
_blue "==> [2/6] Delete leftover Jobs and their Pods"
if [[ "$NAMESPACE_EXISTS" == true ]]; then
  run "kubectl -n '$NAMESPACE' delete job -l 'app.kubernetes.io/instance=$RELEASE' --ignore-not-found --wait=true --timeout=2m"
  run "kubectl -n '$NAMESPACE' delete pod -l 'app.kubernetes.io/instance=$RELEASE' --ignore-not-found --field-selector=status.phase!=Running"
else
  echo "  (skipped — namespace '$NAMESPACE' not present)"
fi

# ========== STEP 3: sweep leftover Secrets & ConfigMaps ==========
_blue "==> [3/6] Sweep leftover Secrets / ConfigMaps"
if [[ "$NAMESPACE_EXISTS" == true ]]; then
  run "kubectl -n '$NAMESPACE' delete secret    -l 'app.kubernetes.io/instance=$RELEASE' --ignore-not-found"
  run "kubectl -n '$NAMESPACE' delete configmap -l 'app.kubernetes.io/instance=$RELEASE' --ignore-not-found"
else
  echo "  (skipped — namespace '$NAMESPACE' not present)"
fi

# ========== STEP 4: drop Postgres DB & role ==========
_blue "==> [4/6] Drop Postgres database and role"
if [[ "$PG_POD_FOUND" == true ]]; then
  echo "  - Database: $PM_DB"
  kexec_psql "REVOKE CONNECT ON DATABASE \\\"$PM_DB\\\" FROM PUBLIC;"
  kexec_psql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$PM_DB' AND pid <> pg_backend_pid();"
  kexec_psql "DROP DATABASE IF EXISTS \\\"$PM_DB\\\";"

  echo "  - Role: $PM_USER"
  kexec_psql "REASSIGN OWNED BY \\\"$PM_USER\\\" TO postgres;"
  kexec_psql "DROP OWNED BY \\\"$PM_USER\\\";"
  kexec_psql "DROP ROLE IF EXISTS \\\"$PM_USER\\\";"
else
  echo "  (skipped — commons-postgresql pod not reachable; if Postgres is already gone, the DB is gone too)"
fi

# ========== STEP 5: PVCs ==========
# This chart provisions no PVCs today, but the label sweep is kept for
# robustness (and future-proofing) and is a no-op when none exist.
_blue "==> [5/6] Delete PVCs"
if [[ "$NAMESPACE_EXISTS" == true ]]; then
  run "kubectl -n '$NAMESPACE' delete pvc -l 'app.kubernetes.io/instance=$RELEASE' --ignore-not-found"
else
  echo "  (skipped — namespace '$NAMESPACE' not present)"
fi

# ========== STEP 6: PVs ==========
_blue "==> [6/6] Delete PVs"
if [[ "$KEEP_PVS" == true ]]; then
  _yellow "  (skipped — --keep-pvs)"
else
  pv_list=$(kubectl get pv -o json 2>/dev/null | \
    jq -r --arg ns "$NAMESPACE" \
      '.items[] | select(.spec.claimRef.namespace==$ns) | select(.status.phase=="Released" or .status.phase=="Failed") | .metadata.name' \
    2>/dev/null || true)
  pv_labeled=$(kubectl get pv -l "app.kubernetes.io/instance=$RELEASE" \
                 -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || true)
  pv_all=$(echo "$pv_list $pv_labeled" | tr ' ' '\n' | sort -u | tr '\n' ' ' | sed 's/^ *//;s/ *$//')

  if [[ -z "$pv_all" ]]; then
    echo "  (no PVs to delete)"
  else
    for pv in $pv_all; do
      run "kubectl delete pv '$pv' --ignore-not-found"
    done
  fi
fi

echo
_green "==> Done."
if [[ "$DRY_RUN" == true ]]; then
  _yellow "    (dry-run — nothing was actually changed)"
fi
_yellow "Note: the Keycloak realm/client (clientId '${RELEASE}-staff-portal') is left"
_yellow "      intact — it lives in Keycloak, not in this namespace. keycloak-init is"
_yellow "      idempotent, so reinstalling reuses it. The shared commons IAM is untouched."
echo
_green "Data removed by this run:"
_green "  - ALL rows in $PM_DB (partners, partner keys, onboarding/key-update requests)"
