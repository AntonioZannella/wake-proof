"""Alarm test against a local server (posts one TEST line, sends no email). ~3.5 min.
Run: NTFY_POST_URL set (see README) then /usr/local/bin/python3 test_alarm.py
Phases: alarm emails -> tap Start but no proof (snooze attempt) -> proof from someone lying down ->
real upright proof (paused) -> proof stops after a FAIL -> new challenge passed -> alarm stops.
"""
import json, os, subprocess, sys, threading, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
B = "http://localhost:8795"
env = {**os.environ, "WAKEPROOF_LABEL": "TEST"}
srv = subprocess.Popen([sys.executable, "server.py", "8795"], cwd=HERE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
alarm = subprocess.Popen([sys.executable, "-u", "alarm.py"], cwd=HERE, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         env={**env, "SITE": B, "ALARM_TIME": "now", "EVERY": "3", "MAX_MINUTES": "6", "DRY_RUN": "1"})
log = []   # (time, line) from the alarm
threading.Thread(target=lambda: [log.append((time.time(), l.strip())) for l in alarm.stdout], daemon=True).start()


def call(path, body=None):
    req = urllib.request.Request(B + path, data=json.dumps(body).encode() if body else None)
    return json.loads(urllib.request.urlopen(req, timeout=120).read())


def sim(steps, mode):
    return json.loads(subprocess.run(["node", "sim_frames.js", mode], input=json.dumps(steps), capture_output=True, text=True, cwd=HERE).stdout)


def beat(cid, frames, stop):
    """Send the page's heartbeat: last 2.5 s of frames, every 4 s, walking through the recording."""
    i = 75
    while not stop.is_set() and i < len(frames):
        call("/api/heartbeat", {"id": cid, "frames": frames[i - 75:i]}); i += 120; stop.wait(4)


lying = lambda frames: [{"t": f["t"], "lm": [{"x": q["y"], "y": q["x"] * 0.3 + 0.5, "visibility": q["visibility"]} for q in f["lm"]]} for f in frames]
phases = {}
def phase(name, secs, fn=None):
    t0 = time.time(); r = fn() if fn else None; time.sleep(max(0, secs - (time.time() - t0))); phases[name] = (t0, time.time()); return r

try:
    phase("alarm", 8)
    c1 = call("/api/challenge"); s1 = sim(c1["steps"], "obey")
    phase("snooze: tapped Start, no proof", 30)
    phase("lying in bed proof", 30, lambda: [print("lying heartbeat ok:", call("/api/heartbeat", {"id": c1["id"], "frames": lying(s1["frames"][:75])})["ok"])])
    stop = threading.Event(); th = threading.Thread(target=beat, args=(c1["id"], s1["frames"], stop)); th.start()
    phase("upright proof", 30); stop.set(); th.join()
    phase("after FAIL (proof stopped)", 35)
    c2 = call("/api/challenge"); t0 = time.time(); s2 = sim(c2["steps"], "obey")
    stop = threading.Event(); th = threading.Thread(target=beat, args=(c2["id"], s2["frames"], stop)); th.start()
    time.sleep(max(0, s2["frames"][-1]["t"] - (time.time() - t0)) + 1); stop.set(); th.join()
    print("result 2:", call("/api/result", {"id": c2["id"], "frames": s2["frames"], "aspect": s2["aspect"]}))
    alarm.wait(30)
    time.sleep(0.5)
    emails = lambda a, b: sum(1 for t, l in log if a <= t <= b and "email #" in l)
    ok = True
    for name, (a, b) in phases.items():
        n = emails(a + 4, b) if name != "after FAIL (proof stopped)" else emails(a + 24, b)  # allow lag / 20 s hold
        want = name != "upright proof"
        ok &= (n > 0) == want
        print(f"{'ok  ' if (n > 0) == want else 'BAD '} {name:32} emails: {n}  (want {'some' if want else 'none'})")
    stopped = log and "PASS found" in log[-1][1]
    print(f"{'ok  ' if stopped else 'BAD '} alarm stopped on PASS: {log[-1][1] if log else '-'}")
    print("ALARM TEST", "PASSED" if ok and stopped else "FAILED")
finally:
    alarm.kill(); srv.terminate()
