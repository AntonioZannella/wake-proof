"""Wake Proof server: serves the page, issues challenges, re-checks results, posts PASS to ntfy.

Run:  /usr/local/bin/python3 server.py [port]
The ntfy topic is read at runtime from the hidden secrets file named in the gated memory note.
Nothing secret is printed, logged, or sent to the page.
"""
import hashlib, hmac, json, os, re, secrets, subprocess, sys, time, urllib.request
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
NOTE = os.path.expanduser("~/.claude/projects/-Users-antoniozannella-Downloads-claude-code/memory/ntfy-burner-account.md")
CHALLENGE_TTL = 15 * 60          # s a challenge stays valid
open_challenges = {}             # id -> (steps, issued_at)


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
        line = f"{stamp:%Y-%m-%d} | {stamp:%H:%M} UTC | {os.environ.get('WAKEPROOF_LABEL', 'PASS')}"
        try:
            url = secret_post_url()
            msg = f"{line} | sig={sign(line, url)}"
            urllib.request.urlopen(urllib.request.Request(url, data=msg.encode(), method="POST"), timeout=15)
            posted = True
        except Exception:
            posted = False
        return self.send_json({"pass": True, "line": line, "posted": posted})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8791))
    print(f"Wake Proof on http://localhost:{port}")
    ThreadingHTTPServer(("", port), Handler).serve_forever()
