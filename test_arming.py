"""Offline checks for one-way arming: parsing, keep-alive re-post, hourly lookahead, earlier ARM wins."""
import io, json, os, time
from datetime import datetime
os.environ["NTFY_POST_URL"] = "https://example.invalid/t"
os.environ["DRY_RUN"] = "1"
import server, alarm

T = "2026-11-26"
cases = [(["ARM 2026-11-26 06:30"], "2026-11-26 06:30"), (["ARM 2026-11-26 06:30", "OFF"], "2026-11-26 06:30"),
         (["ARM 2026-11-26 06:30", "ARM 2026-11-26 11:00"], "2026-11-26 06:30"),
         (["ARM 2026-11-26 06:30", "ARM 2026-11-26 5:45"], "2026-11-26 05:45"),
         (["ARM 2026-11-26 06:30", "ARM 2026-11-28 06:30"], "2026-11-26 06:30"), (["ARM 2026-11-25 06:30"], "off"),
         (["OFF"], "off"), ([], "off"), (["ARM 2026-11-26 25:00"], "off"), (["2026-11-26 | 11:00 UTC | PASS | sig=ab"], "off")]
for m, want in cases:
    assert server.pick_arm(m, T) == want, (m, want)

# keep-alive: old ARM is re-posted, fresh ARM and "off" are not
posts = []
def fake_open(rows):
    def op(req, timeout=0):
        if isinstance(req, str):
            return io.BytesIO("\n".join(json.dumps(r) for r in rows).encode())
        posts.append(req.data.decode()); return io.BytesIO(b"{}")
    return op
tomorrow = "2099-01-01"
for age, rows_msg, want_posts in [(7 * 3600, f"ARM {tomorrow} 6:30", [f"ARM {tomorrow} 06:30"]),
                                  (1 * 3600, f"ARM {tomorrow} 06:30", []), (7 * 3600, "OFF", [])]:
    posts.clear()
    server.urllib.request.urlopen = fake_open([{"time": time.time() - age, "message": rows_msg}])
    server.armed()
    assert posts == want_posts, (age, rows_msg, posts)

# job confirmation: posted once when the job sees an ARM, not again, not for a plain check
for job, rows, want in [(True, [f"ARM {tomorrow} 06:30"], 1), (False, [f"ARM {tomorrow} 06:30"], 0),
                        (True, [f"ARM {tomorrow} 06:30", f"CONFIRMED {tomorrow} 06:30 seen by alarm job at x"], 0),
                        (True, ["OFF"], 0)]:
    posts.clear()
    server.urllib.request.urlopen = fake_open([{"time": time.time(), "message": m} for m in rows])
    server.armed(job=job)
    assert sum(p.startswith("CONFIRMED") for p in posts) == want, (job, rows, posts)

# hourly lookahead: an alarm 5 h away is left to a later run (returns without waiting)
alarm.alarm_start = lambda: time.time() + 5 * 3600
t0 = time.time(); alarm.main(); assert time.time() - t0 < 1

# while waiting, a newer earlier ARM moves the alarm sooner; then PASS stops it
calls = iter([time.time() + 2, time.time() + 0.5])
seen = []
alarm.alarm_start = lambda: next(calls, None)
real_sleep = time.sleep
alarm.time.sleep = lambda s: (seen.append(s), real_sleep(min(s, 0.6)))
alarm.status = lambda since: {"active": False, "passed": True}
alarm.main()
assert seen and seen[0] <= 2.1, seen
print(f"{len(cases)} parse cases, 3 keep-alive cases, 4 confirm cases, lookahead, earlier-ARM: all ok")
