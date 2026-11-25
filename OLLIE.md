# Arming the wake alarm (for Ollie)

No key or token needed. Post one line to the wake topic you already have:

```bash
curl -s -d "ARM 2026-11-26 06:30" "$WAKE_TOPIC_URL"
```

- Format: `ARM YYYY-MM-DD HH:MM`, date of the morning, 24-hour time, Eastern.
- When: between about 6 PM the evening before and 3 AM. The topic keeps messages about 12 hours,
  and the alarm job checks at about 3:30-4:30 AM Eastern.
- There is no OFF. Once armed, only Antonio's PASS stops the emails. If several ARM messages exist,
  the earliest time wins, so a later message can only make the alarm sooner, never cancel or delay it.
- Do not print the topic address in chat. ARM lines are not PASS lines.
