#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="$project_root/.env"

if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared topilmadi. O'rnating: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
    exit 1
fi
if [[ ! -f "$env_file" ]]; then
    echo ".env topilmadi. Avval .env.example faylidan .env yarating." >&2
    exit 1
fi

updated_marker="$(mktemp)"
trap 'rm -f "$updated_marker"' EXIT

cloudflared tunnel --url http://127.0.0.1:8000 2>&1 | while IFS= read -r line; do
    printf '%s\n' "$line"
    if [[ ! -s "$updated_marker" && "$line" =~ (https://[[:alnum:]-]+\.trycloudflare\.com) ]]; then
        webapp_url="${BASH_REMATCH[1]}/app/"
        temp_env="${env_file}.tmp.$$"
        awk -v url="$webapp_url" '
            BEGIN { found = 0 }
            /^WEBAPP_URL=/ { print "WEBAPP_URL=" url; found = 1; next }
            { print }
            END { if (!found) print "WEBAPP_URL=" url }
        ' "$env_file" > "$temp_env"
        mv "$temp_env" "$env_file"
        printf 'updated\n' > "$updated_marker"
        printf 'WEBAPP_URL .env faylida yangilandi: %s\n' "$webapp_url"
        printf 'Tunnel ochiq tursin; backendni qayta ishga tushiring.\n'
    fi
done

if [[ ! -s "$updated_marker" ]]; then
    echo "cloudflared HTTPS trycloudflare.com manzilini bermadi." >&2
    exit 1
fi
