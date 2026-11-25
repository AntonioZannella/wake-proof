# Arming the wake alarm (for Ollie)

The alarm is OFF unless the GitHub repo variable `ALARM_AT` holds today's date and a time (Eastern).
Every day at about 3:30-4:30 AM Eastern a GitHub job checks it. If it matches today, the job waits
until that time, then emails Antonio every minute until a PASS appears on the wake-up topic.

Token: a GitHub fine-grained personal access token, repository `AntonioZannella/wake-proof` only,
permission **Variables: Read and write**. Keep it in `$GH_TOKEN`.

Arm (for example, tomorrow at 6:30 AM Eastern). Set it the evening before, any time before ~3:30 AM:

```bash
curl -s -X PATCH -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/AntonioZannella/wake-proof/actions/variables/ALARM_AT \
  -d '{"name":"ALARM_AT","value":"2026-11-26 06:30"}'
```

A reply of HTTP 204 means it worked. Disarm: same call with `"value":"off"`.
Check: `curl -s -H "Authorization: Bearer $GH_TOKEN" https://api.github.com/repos/AntonioZannella/wake-proof/actions/variables/ALARM_AT`

Rules: date is `YYYY-MM-DD`, time is 24-hour `HH:MM` Eastern. A date that is not today means no alarm,
so an old value turns itself off. Arm it for the next morning only.
