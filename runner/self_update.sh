#!/usr/bin/env bash
# Met a jour le code du runner puis redemarre les services.
# Appele en arriere-plan par POST /api/self-update (ne pas lancer a la main sauf debug).
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/testacevalue}"
BRANCH="${UPDATE_BRANCH:-main}"
STATUS_FILE="${REPO_DIR}/runner/data/last_update.json"
LOG_FILE="${REPO_DIR}/runner/data/self_update.log"
VENV="${REPO_DIR}/.venv"

mkdir -p "${REPO_DIR}/runner/data"
exec >>"${LOG_FILE}" 2>&1

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) self-update start ====="

cd "${REPO_DIR}"

if [[ ! -d .git ]]; then
  echo "Pas de repo git dans ${REPO_DIR}"
  printf '%s\n' "{\"ok\":false,\"error\":\"repo git introuvable\",\"finished_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >"${STATUS_FILE}"
  exit 1
fi

BEFORE="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
BEFORE_MSG="$(git log -1 --pretty=%s 2>/dev/null || echo "")"

echo "commit avant: ${BEFORE} ${BEFORE_MSG}"

git fetch --prune origin "${BRANCH}"
if ! git merge --ff-only "origin/${BRANCH}"; then
  echo "merge ff-only impossible"
  printf '%s\n' "{\"ok\":false,\"error\":\"git merge --ff-only a echoue\",\"before\":\"${BEFORE}\",\"finished_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >"${STATUS_FILE}"
  exit 1
fi

AFTER="$(git rev-parse --short HEAD)"
AFTER_MSG="$(git log -1 --pretty=%s 2>/dev/null || echo "")"
CHANGED="$([[ "${BEFORE}" != "${AFTER}" ]] && echo true || echo false)"

echo "commit apres: ${AFTER} ${AFTER_MSG} changed=${CHANGED}"

if [[ -x "${VENV}/bin/pip" ]]; then
  "${VENV}/bin/pip" install -q -r requirements.txt || echo "pip install a echoue (continue)"
fi

# Refresh tunnel URL file if log is readable
if [[ -f /var/log/cloudflared-aces.log ]]; then
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /var/log/cloudflared-aces.log | tail -1 || true)"
  if [[ -n "${URL:-}" ]]; then
    echo "${URL}" >"${REPO_DIR}/runner/data/public_url.txt"
    echo "public_url=${URL}"
  fi
fi

restart_cmd() {
  if command -v systemctl >/dev/null 2>&1; then
    if [[ "$(id -u)" -eq 0 ]]; then
      systemctl restart "$1"
    else
      sudo -n systemctl restart "$1"
    fi
  else
    echo "systemctl introuvable"
    return 1
  fi
}

# Ecrire le statut AVANT le restart (le process HTTP va mourir).
cat >"${STATUS_FILE}" <<EOF
{
  "ok": true,
  "changed": ${CHANGED},
  "before": "${BEFORE}",
  "after": "${AFTER}",
  "before_message": $(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "${BEFORE_MSG}"),
  "after_message": $(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "${AFTER_MSG}"),
  "branch": "${BRANCH}",
  "restart_tunnel": $([[ "${RESTART_TUNNEL:-}" == "1" ]] && echo true || echo false),
  "finished_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "restart aces-runner..."
restart_cmd aces-runner || {
  echo "restart aces-runner a echoue"
  exit 1
}

if [[ "${RESTART_TUNNEL:-}" == "1" ]]; then
  if systemctl list-unit-files cloudflared-aces.service >/dev/null 2>&1; then
    echo "RESTART_TUNNEL=1 — restart cloudflared-aces (nouvelle URL trycloudflare)"
    restart_cmd cloudflared-aces || {
      echo "restart cloudflared-aces a echoue"
      exit 1
    }
    sleep 3
    if [[ -f /var/log/cloudflared-aces.log ]]; then
      URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /var/log/cloudflared-aces.log | tail -1 || true)"
      if [[ -n "${URL:-}" ]]; then
        echo "${URL}" >"${REPO_DIR}/runner/data/public_url.txt"
        echo "public_url=${URL}"
      fi
    fi
  else
    echo "cloudflared-aces absent — skip tunnel restart"
  fi
elif systemctl list-unit-files cloudflared-aces.service >/dev/null 2>&1; then
  echo "cloudflared-aces present — laisse tourner (URL stable)"
fi

echo "===== $(date -u +%Y-%m-%dT%H:%M:%SZ) self-update done ====="
