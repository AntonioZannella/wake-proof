# Wake Proof

Camera exercise checker. Plain code decides PASS/FAIL; no AI judge.

## Files
- `index.html` - phone page: camera, skeleton, FPS, rep counter with 3-rep calibration.
- `counter.js` - rule-based rep counter (pure logic, browser + Node).
- `test_counter.js` - synthetic-landmark tests: `node test_counter.js`.
- `clips/` - test clips (H.264, 360x640, 30 fps) converted from IMG_3688-3692.MOV.

## Stage 1 (2026-11-25): iPhone 13 Pro, Safari, GPU
| model | FPS | inference |
|---|---|---|
| full | 60 | 14 ms |
| heavy | 19.4 | 48 ms |
Chosen: full.

## Stage 2 (2026-11-25): counter accuracy on real clips (full model)
Rules: jumping jack = arm angle at shoulder crosses high then low threshold, legs must spread
during the rep, knees must stay fairly straight. Squat = knee bend crosses high then low threshold.
Thresholds come from your own first 3 reps (calibration). Median-of-5 + smoothing; frames with
low-confidence or out-of-picture joints are skipped.

Clip mapping is assumed from the order recorded (jj10, jj10-slow, sq10, sq10-sloppy, fake).

| clip | true reps | counted as jumping jack | counted as squat |
|---|---|---|---|
| 3688 jumping jacks | 10 (+1 arm-only raise at start) | 10 | 1 (while walking into place) |
| 3689 slow jumping jacks | 11 (confirmed by Antonio) | 11 | 0 |
| 3690 squats | 10 | 0 | 10 |
| 3691 sloppy squats | ~10 (1 partly hidden) | 0 | 9 |
| 3692 fake | 0 | 0 | 0 (legs mostly not visible) |

Cross-calibration (thresholds from one clip, tested on all others): no jumping jacks counted on
squat clips, no squats counted on jumping-jack clips, except 1 false squat at the start of 3688.
Synthetic tests: 13/13 pass (pace 0.8-6 s/rep, 15-60 fps, 5-15% dropped frames, half squats,
arm-only waving, leg-only, squats with arms overhead, standing still).

Known limits: calibration on deep squats then doing shallow ones misses reps (calibrate each
session). Walking in/out of frame can make 1 false rep; Stage 3 starts counting only after a
ready check. The fake clip mostly tested "legs not visible", not a clever fake.

## Stage 3 (2026-11-25): random challenge (`challenge.js`, `test_challenge.js`)
Drawn with `crypto` only when you tap Start challenge:
ready (whole body in view, standing, arms down, 1.5 s) -> reps of exercise A (4-7, first time
also 3 calibration reps) -> pose cue -> reps of B -> pose cue -> reps of A or B -> pose cue ->
20 s nonstop reps (no pause over 4 s).
Pose cue: arms down, then after a random 1.5-5 s wait the page says LEFT hand up, RIGHT hand up,
or T. Reach it within 5 s and hold 0.6 s. Holding a different cue pose for 0.6 s = FAIL.
FAIL also if: no full body in view for 3 s, a rep step takes longer than n x 4 s + 10 s.
Prompts are read aloud.

Results (`node test_challenge.js`, simulated people, 30 runs each):
- obedient: 30/30 pass, 66-112 s; half-asleep (slow reps, 3 s reaction): 30/30 pass, 99-132 s
- ignores cues 0/30, wrong pose 0/30, only jumping jacks 0/30, walks out 5 s 0/30
- replaying an old passing recording into a new challenge: 0/400 pass
Real clips (5 clips, all 120 orders, played 3x back to back, 5 new challenges each): 0/600 pass;
none got past the first pose cue.

Live run on iPhone 13 Pro (2026-11-25): PASS; Antonio says all prompts, including left/right,
felt right.

## Stage 4 (2026-11-25): server re-check, signed line, ntfy (`server.py`, `verify_run.js`, `verify.py`)
- `server.py` serves the page, draws the challenge (`GET /api/challenge`, one-use id, 15 min),
  and takes the recording (`POST /api/result`). It re-runs the recorded landmarks through the same
  challenge code with node; the page saying PASS counts for nothing. Refused: unknown/used id,
  recording longer than the real time since the challenge was issued, any re-check failure.
- On PASS it posts `YYYY-MM-DD | HH:MM UTC | PASS | sig=<16 hex>` to the ntfy topic. The signature
  is an HMAC keyed from the secret topic address. The topic is read at runtime from the hidden
  file; it is never printed, logged, or sent to the page. Video-file runs never post.
- The ntfy login in the hidden file does not work (account never created); the topic is public
  but unguessable, so the topic name is the secret and the signature catches typed lines.
- `verify.py` reads the topic and prints each line as VALID or FORGED, and whether a valid PASS
  dated today exists.

Tested (`python3 test_server.py`, posts a TEST line, never PASS): obedient simulated run passes
and posts; reused id refused; old recording on a new challenge refused; recording faster than real
time refused; ignoring cues refused by the re-check; verify.py reads the TEST line back as VALID.
Not tested: a forged line on the topic (not posted, so Ollie never sees a fake PASS); a live
phone run through server.py.

Limits: Antonio owns this Mac and can read or edit server.py. A programmer could fake a landmark
recording that follows the cues (test helper `sim_frames.js` does exactly that). Ollie cannot
check the signature without the key. Stage 5 moves the check off this Mac.

## Render hosting (2026-11-25): Mac can be off
- `Dockerfile` (node:20-slim + python3) runs `server.py`; Render sets `PORT`.
- Secret: env `NTFY_POST_URL` on the Render service. `set_render_secret.sh` copies it from the
  hidden file through the Render API without showing it (asks for an API key and the srv- id).
- Live at https://wake-proof.onrender.com (service srv-dc3ekik0916s738jloig).
- Tested 2026-11-25: set_render_secret.sh (HTTP 200/201); a simulated run against Render passed
  the server re-check and posted a TEST line that verify.py reads back VALID. First try failed
  with URLError: the slim image lacked ca-certificates (fixed in the Dockerfile).
- Remove the WAKEPROOF_LABEL=TEST env var on Render before a real PASS can post.
- Free tier sleeps after 15 min idle; first load takes up to about a minute.

## Wake alarm (2026-11-25): emails until you pass (`alarm.py`, `.github/workflows/alarm.yml`)
- OFF by default. GitHub Actions starts at 08:30 UTC daily and asks the site `GET /api/armed`.
  It exits unless Ollie posted "ARM YYYY-MM-DD HH:MM" (Eastern) for today to the wake topic (see
  OLLIE.md). Arming is one-way: there is no OFF, and among ARM messages the earliest time wins, so a
  later message can only move the alarm sooner. Then it sleeps until that time, then
  every minute: PASS posted since the alarm time -> stop; challenge running -> wait; else email.
  Gives up after MAX_MINUTES (90).
- Snooze-proof: "Start challenge" only asks the server for a challenge after the camera sees your
  whole body standing for 1.5 s. Emails pause only while the page keeps sending heartbeats (last
  2.5 s of frames every 5 s) that show you upright and in view; a pause lasts 20 s per heartbeat.
  FAIL or walking away stops heartbeats, so emails resume within 20 s.
- Server: `GET /api/status?since=<unix>` -> {active, passed}; `POST /api/heartbeat`.
- Setup: `set_alarm_secrets.sh` or the GitHub website (Settings -> Secrets and variables -> Actions).
- Tested locally (`test_alarm.py`, dry run, TEST label): emails at alarm; tapping Start with no
  proof does not pause; heartbeats from someone lying down are refused; upright heartbeats pause
  (0 emails); emails resume after a FAIL; PASS stops the alarm. Page gate checked in the browser.
  Not tested: real Gmail sending, the GitHub Actions run, the Render deploy of these changes.
- Limits: GitHub may start scheduled jobs late (hence the early start) and disables schedules in
  repos with no activity for 60 days. Someone who writes code could fake heartbeats.
