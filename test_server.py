"""End-to-end test of server.py with a simulated person. Posts only TEST lines, never PASS.

Run: /usr/local/bin/python3 test_server.py   (starts its own server on port 8792; takes ~2-3 min)
"""
import json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "http://localhost:8792"
srv = subprocess.Popen([sys.executable, "server.py", "8792"], cwd=HERE, env={**os.environ, "WAKEPROOF_LABEL": "TEST"},
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
fails = 0


def check(name, ok, info=""):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name:45} {info}")


def get(path):
    return json.loads(urllib.request.urlopen(BASE + path).read())


def post(body):
    req = urllib.request.Request(BASE + "/api/result", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    try:
        return json.loads(urllib.request.urlopen(req, timeout=120).read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def simulate(steps, mode):
    out = subprocess.run(["node", "sim_frames.js", mode], input=json.dumps(steps), capture_output=True, text=True, cwd=HERE)
    return json.loads(out.stdout)


try:
    check("page is served", urllib.request.urlopen(BASE + "/index.html").status == 200)
    try:
        urllib.request.urlopen(BASE + "/server.py"); check("server.py hidden", False)
    except urllib.error.HTTPError as e:
        check("server.py hidden", e.code == 404)

    # 1. Honest run: frames from a simulated obedient person; wait real time before sending.
    c = get("/api/challenge")
    sim = simulate(c["steps"], "obey")
    t0 = time.time()
    time.sleep(max(0, sim["frames"][-1]["t"] - sim["frames"][0]["t"] - (time.time() - t0)))
    r = post({"id": c["id"], "frames": sim["frames"], "aspect": sim["aspect"]})
    check("obedient run passes and posts", r.get("pass") and r.get("posted"), str(r))

    # 2. Same challenge id again (replay of the request).
    r = post({"id": c["id"], "frames": sim["frames"], "aspect": sim["aspect"]})
    check("same challenge id refused", not r.get("pass"), r.get("why", ""))

    # 3. Recording from challenge 1 sent for a new challenge.
    c2 = get("/api/challenge")
    r = post({"id": c2["id"], "frames": sim["frames"], "aspect": sim["aspect"]})
    check("old recording on new challenge refused", not r.get("pass"), r.get("why", ""))

    # 4. Fresh challenge, honest frames, but sent too fast (made up, not lived).
    c3 = get("/api/challenge")
    sim3 = simulate(c3["steps"], "obey")
    r = post({"id": c3["id"], "frames": sim3["frames"], "aspect": sim3["aspect"]})
    check("recording longer than real time refused", not r.get("pass"), r.get("why", ""))

    # 5. Page lies: says PASS but frames show someone ignoring cues.
    c4 = get("/api/challenge")
    sim4 = simulate(c4["steps"], "ignore")
    r = post({"id": c4["id"], "frames": sim4["frames"][:60], "aspect": sim4["aspect"]})
    check("ignoring cues refused by server re-check", not r.get("pass"), r.get("why", ""))

    # 6. Topic check: our TEST line reads back as VALID (ntfy needs a moment after a post).
    time.sleep(3)
    out = subprocess.run([sys.executable, "verify.py"], capture_output=True, text=True, cwd=HERE).stdout
    check("verify.py sees the signed TEST line as VALID", "VALID" in out and "| TEST" in out)
    print("--- verify.py output ---\n" + out.strip())
finally:
    srv.terminate()
print("all passed" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)
