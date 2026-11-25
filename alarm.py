"""Wake-up email alarm. Runs in GitHub Actions (or anywhere) with the Mac off.

At ALARM_TIME (America/New_York) it emails ALERT_TO every minute until a challenge is started on the
site. While a challenge runs, it waits. A PASS on the ntfy topic stops it; a FAIL (or a challenge left
unfinished) starts the emails again. Gives up after MAX_MINUTES.

Env: ALARM_TIME "HH:MM" (Eastern), SITE (https://wake-proof.onrender.com), GMAIL_USER,
GMAIL_APP_PASSWORD, ALERT_TO, MAX_MINUTES (default 90), DRY_RUN=1 to print instead of sending,
EVERY (seconds between checks, default 60).
"""
import json, os, smtplib, sys, time, urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SITE = os.environ.get("SITE", "https://wake-proof.onrender.com").rstrip("/")
EVERY = int(os.environ.get("EVERY", 60))
DRY = os.environ.get("DRY_RUN") == "1"


def alarm_start():
    """Unix time to start, or None if the alarm is not armed for today.
    ALARM_TIME "HH:MM" or "now" is for manual test runs. Otherwise the site's /api/armed decides."""
    t = os.environ.get("ALARM_TIME", "").strip()
    if t == "now":
        return time.time()
    if not t:   # scheduled run: only Ollie's ARM message on the topic arms it (read through the site)
        at = get_json(f"{SITE}/api/armed").get("alarm_at") or ""
        print(f"site says armed for: {at or 'unknown (could not reach site)'}", flush=True)
        try:
            day, t = at.split()
            datetime.strptime(day, "%Y-%m-%d")
        except ValueError:
            return None
        if day != datetime.now(ET).strftime("%Y-%m-%d"):
            return None
    try:
        h, m = map(int, t.split(":"))
    except ValueError:
        return None
    return datetime.now(ET).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def get_json(url):
    for _ in range(3):   # the free site may be asleep: first call can take up to a minute
        try:
            return json.loads(urllib.request.urlopen(url, timeout=90).read())
        except Exception as e:
            err = e
            time.sleep(5)
    return {"why": type(err).__name__}


def status(since):
    return {"active": False, "passed": None, **get_json(f"{SITE}/api/status?since={int(since)}")}


def send(subject, body):
    if DRY:
        print(f"  [dry run] email: {subject}", flush=True)
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = os.environ["GMAIL_USER"], os.environ["ALERT_TO"], subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"])
        s.send_message(msg)


def main():
    start = alarm_start()
    if start is None:
        print("not armed for today; no alarm"); return
    wait = start - time.time()
    if wait < -2 * 3600:
        print("alarm time was more than 2 h ago; nothing to do"); return
    if wait > 0:
        print(f"waiting {wait / 60:.0f} min until {datetime.fromtimestamp(start, ET):%H:%M} Eastern", flush=True)
        time.sleep(wait)
    deadline = time.time() + 60 * int(os.environ.get("MAX_MINUTES", 90))
    sent = 0
    while time.time() < deadline:
        st = status(start)
        now = datetime.now(ET).strftime("%H:%M:%S")
        if st.get("passed"):
            print(f"{now} PASS found, stopping after {sent} emails", flush=True)
            return
        if st.get("active"):
            print(f"{now} challenge running, not emailing", flush=True)
        else:
            sent += 1
            note = "" if st.get("passed") is not None else " (could not check the topic)"
            print(f"{now} no PASS yet, email #{sent}{note}", flush=True)
            send(f"WAKE UP #{sent}: start the challenge",
                 f"No PASS yet{note}. Open {SITE} and tap Start challenge.\nThese emails stop when you pass.")
        time.sleep(EVERY)
    send("Wake alarm gave up", f"No PASS within {os.environ.get('MAX_MINUTES', 90)} minutes of the alarm.")
    print("gave up", flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
