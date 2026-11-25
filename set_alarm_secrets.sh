#!/bin/bash
# Stores the alarm's email settings in the GitHub repo (secrets are encrypted; nobody can read
# them back, not even you). The alarm is off until Ollie posts an ARM message. Needs: gh auth login. Run from anywhere.
set -euo pipefail
REPO=AntonioZannella/wake-proof
read -rp  "Sender Gmail address (burner): " GU
read -rsp "Its 16-letter app password (hidden): " GP; echo
read -rp  "Send the wake-up emails to: " TO
printf %s "$GU" | gh secret set GMAIL_USER --repo "$REPO"
printf %s "${GP// /}" | gh secret set GMAIL_APP_PASSWORD --repo "$REPO"
printf %s "$TO" | gh secret set ALERT_TO --repo "$REPO"
echo "saved. Test it: GitHub -> Actions -> Wake alarm -> Run workflow (alarm_time: now, max_minutes: 3)"
