#!/usr/bin/env bash
# Affiche l'URL publique Cloudflare a mettre dans Vercel RUNNER_URL.
set -euo pipefail

URL_FILE="/opt/testacevalue/runner/data/public_url.txt"
# Toujours preferer la derniere URL du log (public_url.txt peut etre perime).
URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /var/log/cloudflared-aces.log 2>/dev/null | tail -1 || true)"
if [[ -z "${URL:-}" && -f "$URL_FILE" ]]; then
  URL="$(cat "$URL_FILE")"
fi
if [[ -z "${URL:-}" ]]; then
  echo "URL introuvable. cloudflared tourne ? sudo systemctl status cloudflared-aces"
  exit 1
fi
echo "$URL"
echo
echo "Vercel → RUNNER_URL = $URL"
