# Arming the wake alarm (for Ollie)

No key or token needed. Post one line to the wake topic you already have:

```bash
curl -s -d "ARM 2026-11-26 06:30" "$WAKE_TOPIC_URL"
```

- Format: `ARM YYYY-MM-DD HH:MM`, date of the morning, 24-hour time, Eastern.
- When: any time before the alarm, even days ahead. The alarm job checks every hour and the site
  keeps the ARM line alive, so it does not expire. Arm at least about an hour ahead to be safe.
- There is no OFF. Once armed, only Antonio's PASS stops the emails. If several ARM messages exist,
  the earliest time wins, so a later message can only make the alarm sooner, never cancel or delay it.
- Confirm right after posting: `curl -s https://wake-proof.onrender.com/api/armed` must show
  `{"alarm_at": "2026-11-26 06:30"}` (the first call can take up to a minute while the site wakes).
  This is the same check the alarm job uses. If it shows "off" or a different time, post again.
- Second check, about 1 hour after posting (the alarm job runs once an hour, at :17): read the
  wake topic. A line `CONFIRMED 2026-11-26 06:30 seen by alarm job at ... ET` means the job itself
  saw the ARM. No CONFIRMED line after 90 minutes means something is wrong: tell Antonio.
- Do not print the topic address in chat. ARM lines are not PASS lines.
