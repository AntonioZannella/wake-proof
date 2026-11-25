#!/bin/bash
# Sets NTFY_POST_URL on the Render service from the hidden file, without ever showing it,
# then starts a new deploy. Asks for a Render API key (typed hidden) and the service id (srv-...).
set -euo pipefail
NOTE="$HOME/.claude/projects/-Users-antoniozannella-Downloads-claude-code/memory/ntfy-burner-account.md"
P=$(grep -A1 "Where the secrets are" "$NOTE" | grep -o '`[^`]*`' | head -1 | tr -d '`'); P="${P/#\~/$HOME}"
URL=$(grep -i '^post:' "$P" | sed 's/^[^:]*: *//' | awk '{print $1}')
[ -n "$URL" ] || { echo "secret not found"; exit 1; }

read -rsp "Render API key (hidden): " KEY; echo
read -rp "Render service id (starts with srv-): " SRV

code=$(curl -s -o /dev/null -w "%{http_code}" -X PUT \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  --data-binary @- "https://api.render.com/v1/services/$SRV/env-vars/NTFY_POST_URL" <<<"{\"value\":\"$URL\"}")
echo "set secret: HTTP $code"
[ "$code" = 200 ] || exit 1
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" -d '{}' "https://api.render.com/v1/services/$SRV/deploys")
echo "start deploy: HTTP $code"
