"""Check the ntfy topic for a validly signed PASS line dated today (UTC).

Prints only the PASS lines it found and whether each signature is valid. Never prints the topic,
server, or file path. Exit 0 if a valid PASS dated today exists, else 1.
"""
import json, sys, urllib.request
from datetime import datetime, timezone
from server import secret_post_url, sign

url = secret_post_url()
today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
try:
    raw = urllib.request.urlopen(url + "/json?poll=1&since=24h", timeout=15).read().decode()
except Exception:
    print("could not read the topic"); sys.exit(2)
found = False
for row in raw.splitlines():
    msg = json.loads(row).get("message", "")
    if " | sig=" not in msg:
        print(f"unsigned: {msg[:60]}"); continue
    line, sig = msg.rsplit(" | sig=", 1)
    ok = sig == sign(line, url)
    print(f"{'VALID  ' if ok else 'FORGED '} {line}")
    found |= ok and line.startswith(today) and line.endswith("| PASS")
print(f"valid PASS dated today ({today} UTC): {'yes' if found else 'no'}")
sys.exit(0 if found else 1)
