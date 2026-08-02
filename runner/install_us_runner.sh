#!/usr/bin/env bash
# Installe le runner Bet365 US + tunnel Cloudflare.
# Usage: sudo RUNNER_SECRET=1793 bash runner/install_us_runner.sh
#
# Region Oracle : US (Ashburn / Phoenix / San Jose) — egress US obligatoire pour va.bet365.com.
set -euo pipefail

REPO_DIR="/opt/testacevalue"
SECRET="${RUNNER_SECRET:-1793}"
VENV="${REPO_DIR}/.venv"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Relance avec sudo."
  exit 1
fi

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  echo "Repo absent dans ${REPO_DIR}. Clone d'abord:"
  echo "  sudo git clone https://github.com/Noe-InTech/testacevalue.git ${REPO_DIR}"
  exit 1
fi

echo "==> Mise a jour du code"
cd "${REPO_DIR}"
git pull --ff-only origin main || git pull --ff-only

echo "==> Dependances Python"
if [[ ! -d "${VENV}" ]]; then
  apt-get update -qq
  apt-get install -y -qq python3-venv python3-pip
  python3 -m venv "${VENV}"
fi
"${VENV}/bin/pip" install -q -r requirements.txt

echo "==> cloudflared"
if ! command -v cloudflared >/dev/null 2>&1; then
  curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
  dpkg -i /tmp/cloudflared.deb
fi

echo "==> ufw (SSH + runner local)"
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw allow 8787/tcp >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1 || true

echo "==> systemd aces-runner-us (RUNNER_ROLE=us)"
install -m 644 "${REPO_DIR}/runner/aces-runner-us.service" /etc/systemd/system/aces-runner.service
sed -i "s/CHANGE_ME/${SECRET}/" /etc/systemd/system/aces-runner.service

echo "==> systemd cloudflared-aces"
install -m 644 "${REPO_DIR}/runner/cloudflared-aces.service" /etc/systemd/system/cloudflared-aces.service

echo "==> self-update script + sudoers"
install -m 755 "${REPO_DIR}/runner/self_update.sh" "${REPO_DIR}/runner/self_update.sh"
install -m 440 "${REPO_DIR}/runner/sudoers-aces-update" /etc/sudoers.d/aces-update
visudo -cf /etc/sudoers.d/aces-update >/dev/null

systemctl daemon-reload
systemctl enable aces-runner cloudflared-aces
systemctl restart aces-runner
sleep 2
systemctl restart cloudflared-aces

echo "==> Attente URL tunnel Cloudflare (max 45s)"
PUBLIC_URL=""
for _ in $(seq 1 45); do
  PUBLIC_URL="$(journalctl -u cloudflared-aces -n 80 --no-pager 2>/dev/null \
    | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true)"
  if [[ -n "${PUBLIC_URL}" ]]; then
    break
  fi
  sleep 1
done

mkdir -p "${REPO_DIR}/runner/data"
if [[ -n "${PUBLIC_URL}" ]]; then
  echo "${PUBLIC_URL}" > "${REPO_DIR}/runner/data/public_url.txt"
  chmod 644 "${REPO_DIR}/runner/data/public_url.txt"
fi

echo
echo "=============================================="
echo "Runner US local : http://127.0.0.1:8787"
echo "Role            : us (Bet365 uniquement)"
if [[ -n "${PUBLIC_URL}" ]]; then
  echo "URL publique    : ${PUBLIC_URL}"
  echo
  echo "Sur le runner EU, ajoute :"
  echo "  US_RUNNER_URL=${PUBLIC_URL}"
  echo "  US_RUNNER_SECRET=${SECRET}"
  echo
  echo "Sur Vercel (optionnel, diagnostic) :"
  echo "  US_RUNNER_URL=${PUBLIC_URL}"
else
  echo "URL tunnel pas encore visible. Relance :"
  echo "  sudo journalctl -u cloudflared-aces -n 50 --no-pager | grep trycloudflare"
fi
echo "=============================================="
systemctl --no-pager --full status aces-runner cloudflared-aces | sed -n '1,12p'

echo
echo "==> Probe Bet365 geo (doit rester US, pas .fr)"
"${VENV}/bin/python" - <<'PY'
from bet365_us_client import probe_bet365_us_reachable
import json
print(json.dumps(probe_bet365_us_reachable(), indent=2))
PY
