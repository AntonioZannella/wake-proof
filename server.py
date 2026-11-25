"""Wake Proof server: serves the page, issues challenges, re-checks results, posts PASS to ntfy.

Run:  /usr/local/bin/python3 server.py [port]
The ntfy topic is read at runtime from the hidden secrets file named in the gated memory note.
Nothing secret is printed, logged, or sent to the page.
"""
import hashlib, hmac, json, os, re, secrets, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
NOTE = os.path.expanduser("~/.claude/projects/-Users-antoniozannella-Downloads-claude-code/memory/ntfy-burner-account.md")
CHALLENGE_TTL = 15 * 60          # s a challenge stays valid
HEARTBEAT_SECS = 20              # s one good heartbeat pauses the alarm emails
heartbeats = {}                  # challenge id -> time of last good heartbeat
UPRIGHT_JOINTS = [0, 11, 12, 23, 24, 25, 26, 27, 28]


def upright(lm):
    """Whole body in the picture and standing (head above shoulders above hips above ankles, tall)."""
    if not lm or any(not (lm[j]["visibility"] >= 0.3 and 0 <= lm[j]["x"] <= 1 and 0 <= lm[j]["y"] <= 1) for j in UPRIGHT_JOINTS):
        return False
    y = lambda *js: sum(lm[j]["y"] for j in js) / len(js)
    nose, sh, hip, ank = y(0), y(11, 12), y(23, 24), y(27, 28)
    return nose < sh < hip < ank and ank - nose > 0.25   # 0.25 still allows a deep squat
open_challenges = {}             # id -> (steps, issued_at)
last_post = 0                    # time of the last successful post by this server


def secret_post_url():
    if os.environ.get("NTFY_POST_URL"):      # hosted (Render): secret setting
        return os.environ["NTFY_POST_URL"].strip()
    note = open(NOTE).read()                 # this Mac: hidden file named in the memory note
    path = re.search(r"Where the secrets are.*?`([^`]+)`", note, re.S).group(1)
    for line in open(os.path.expanduser(path)):
        if line.lower().startswith("post:"):
            return line.split(":", 1)[1].strip().split()[0]
    raise RuntimeError("no post address in secrets file")


def sign(line, url):
    key = hashlib.sha256(b"wake-proof-sig|" + url.encode()).digest()
    return hmac.new(key, line.encode(), hashlib.sha256).hexdigest()[:16]


LABEL = os.environ.get("WAKEPROOF_LABEL", "PASS")


def passed_since(ts):
    """True if the topic has a validly signed '| PASS' line (or the test label) posted after ts."""
    url = secret_post_url()
    raw = urllib.request.urlopen(f"{url}/json?poll=1&since={int(ts)}", timeout=15).read().decode()
    for row in raw.splitlines():
        msg = json.loads(row).get("message", "")
        if " | sig=" in msg:
            line, sig = msg.rsplit(" | sig=", 1)
            if line.endswith("| " + LABEL) and hmac.compare_digest(sig, sign(line, url)):
                return True
    return False


ARM_RE = re.compile(r"^\s*ARM\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})\s*$", re.I)


def pick_arm(messages, today):
    """One-way arming: there is no OFF. Among 'ARM YYYY-MM-DD HH:MM' messages dated today or later,
    the EARLIEST wins, so a later message can only move the alarm sooner, never cancel or delay it.
    Only a PASS stops a running alarm. Returns 'YYYY-MM-DD HH:MM' or 'off'."""
    arms = [f"{m[1]} {int(m[2]):02d}:{m[3]}" for m in map(ARM_RE.match, messages)
            if m and int(m[2]) < 24 and int(m[3]) < 60 and m[1] >= today]
    return min(arms, default="off")


REFRESH_SECS = 6 * 3600          # ntfy.sh keeps messages ~12 h; re-post an ARM older than this


def post(url, text):
    urllib.request.urlopen(urllib.request.Request(url, data=text.encode(), method="POST"), timeout=15)


def armed(job=False, every=False):
    url = secret_post_url()
    raw = urllib.request.urlopen(f"{url}/json?poll=1&since=12h", timeout=15).read().decode()
    rows = [json.loads(r) for r in raw.splitlines() if r.strip()]
    today = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    at = pick_arm([r.get("message", "") for r in rows], today)
    # Keep every future ARM alive (the hourly alarm job calls this), so alarms can be set weeks ahead.
    newest = {}
    for r in rows:
        a = pick_arm([r.get("message", "")], today)
        if a != "off":
            newest[a] = max(newest.get(a, 0), r.get("time", 0))
    for a, t in newest.items():
        if time.time() - t > REFRESH_SECS:
            post(url, f"ARM {a}")
    if at != "off":
        # Proof for Ollie that the GitHub alarm job itself saw this ARM (posted once per alarm time).
        if job and not any(r.get("message", "").startswith(f"CONFIRMED {at} ") for r in rows):
            now = datetime.now(ZoneInfo("America/New_York"))
            post(url, f"CONFIRMED {at} seen by alarm job at {now:%Y-%m-%d %H:%M} ET")
    return (at, sorted(newest)) if every else at


def node(script_args, stdin=None):
    out = subprocess.run(["node", *script_args], input=stdin, capture_output=True, text=True, cwd=HERE, timeout=60)
    if out.returncode:
        raise RuntimeError("node failed")
    return out.stdout


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=HERE, **k)

    def log_message(self, fmt, *args):     # keep logs short; never contains secrets
        sys.stderr.write("%s %s\n" % (self.command, self.path.split("?")[0]))

    def send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/armed"):
            # For the alarm job: Ollie arms by posting "ARM YYYY-MM-DD HH:MM" (Eastern) to the topic. No OFF.
            try:
                at, every = armed(job="from=job" in self.path, every=True)
                return self.send_json({"alarm_at": at, "all": every})
            except Exception:
                return self.send_json({"alarm_at": None, "why": "could not read topic"}, 502)
        if self.path.startswith("/api/status"):
            # For the alarm job: is a challenge running right now, and has a PASS arrived since ?since=<unix>?
            # A started challenge counts as running for ACTIVE_SECS unless its result came in first.
            try:
                since = float(self.path.split("since=", 1)[1].split("&")[0])
            except (IndexError, ValueError):
                since = time.time() - 12 * 3600
            now = time.time()
            # Only a challenge whose page keeps proving "upright and in view" pauses the emails.
            active = any(cid in open_challenges and now - t < HEARTBEAT_SECS for cid, t in heartbeats.items())
            try:   # last_post covers the few seconds before ntfy shows a fresh post
                passed = last_post >= since or passed_since(since)
            except Exception:
                return self.send_json({"active": active, "passed": None, "why": "could not read topic"}, 502)
            return self.send_json({"active": active, "passed": passed})
        if self.path.startswith("/api/challenge"):
            steps = json.loads(node(["--input-type=module", "-e",
                "import {makeSteps} from './challenge.js'; console.log(JSON.stringify(makeSteps()))"]))
            cid = secrets.token_hex(16)
            now = time.time()
            for k in [k for k, (_, t) in open_challenges.items() if now - t > CHALLENGE_TTL]:
                del open_challenges[k]
            open_challenges[cid] = (steps, now)
            return self.send_json({"id": cid, "steps": steps})
        if self.path.split("?")[0] in ("/server.py", "/package.json") or "/." in self.path:
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        if self.path == "/api/heartbeat":
            # Page sends its last ~2 s of frames every few seconds during a challenge.
            try:
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                frames = data["frames"]
                ok = (data["id"] in open_challenges and len(frames) >= 10
                      and frames[-1]["t"] - frames[0]["t"] >= 1.5
                      and sum(upright(f["lm"]) for f in frames) >= 0.6 * len(frames))
            except Exception:
                ok = False
            if ok:
                heartbeats[data["id"]] = time.time()
            return self.send_json({"ok": ok})
        if self.path != "/api/result":
            return self.send_error(404)
        try:
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            steps, issued = open_challenges.pop(data["id"])      # one use only
        except Exception:
            return self.send_json({"pass": False, "why": "unknown or used challenge"}, 400)
        now = time.time()
        frames = data.get("frames") or []
        if now - issued > CHALLENGE_TTL or not frames:
            return self.send_json({"pass": False, "why": "challenge expired"})
        # The recording cannot be longer than the real time since the challenge was issued.
        if frames[-1]["t"] - frames[0]["t"] > now - issued + 2:
            return self.send_json({"pass": False, "why": "recording longer than real time"})
        try:
            r = json.loads(node(["verify_run.js"], json.dumps({"steps": steps, "frames": frames, "aspect": data.get("aspect", 0.5625)})))
        except Exception:
            return self.send_json({"pass": False, "why": "server check failed"}, 500)
        if not r.get("pass"):
            return self.send_json({"pass": False, "why": "server re-check: " + r.get("why", "?")})
        stamp = datetime.now(timezone.utc)
        # Tests set WAKEPROOF_LABEL=TEST so a simulated run never posts a real PASS.
        line = f"{stamp:%Y-%m-%d} | {stamp:%H:%M} UTC | {LABEL}"
        try:
            url = secret_post_url()
            msg = f"{line} | sig={sign(line, url)}"
            urllib.request.urlopen(urllib.request.Request(url, data=msg.encode(), method="POST"), timeout=15)
            posted, err = True, None
            global last_post
            last_post = time.time()
        except Exception as e:     # report only the error type and HTTP status, never the address
            posted, err = False, f"{type(e).__name__} {getattr(e, 'code', '') or ''}".strip()
        return self.send_json({"pass": True, "line": line, "posted": posted, "post_error": err})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8791))
    print(f"Wake Proof on http://localhost:{port}")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
