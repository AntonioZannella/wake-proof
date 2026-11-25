// Random exercise challenge. Pure logic: feed it landmarks + time, it says what to do next
// and finally PASS or FAIL. The sequence is drawn only when the challenge starts, so a
// recording made earlier does not know which reps, counts or pose cues are coming.
import { RepCounter } from "./counter.js";

const JOINTS = [0, 11, 12, 15, 16, 23, 24, 25, 26, 27, 28];
const ok = q => q?.visibility >= 0.3 && q.x >= 0 && q.x <= 1 && q.y >= 0 && q.y <= 1;
const angle = (a, b, c) => {
  const v1x = a.x - b.x, v1y = a.y - b.y, v2x = c.x - b.x, v2y = c.y - b.y;
  return Math.acos(Math.max(-1, Math.min(1, (v1x * v2x + v1y * v2y) / (Math.hypot(v1x, v1y) * Math.hypot(v2x, v2y) || 1)))) * 180 / Math.PI;
};

// Pose cues. Index 11/15/23 = the person's LEFT side (MediaPipe convention).
export const POSES = {
  left_up:  { say: "Raise your LEFT hand above your head", test: p => p[15].y < p[0].y && p[16].y > p[12].y },
  right_up: { say: "Raise your RIGHT hand above your head", test: p => p[16].y < p[0].y && p[15].y > p[11].y },
  t_pose:   { say: "Arms straight out to the sides (T)", test: p => [[23, 11, 15], [24, 12, 16]].every(([h, s, w]) => { const a = angle(p[h], p[s], p[w]); return a > 65 && a < 120; }) },
};
const armsDown = p => p[15].y > p[11].y && p[16].y > p[12].y;
const NAMES = { jumping_jack: "jumping jacks", squat: "squats" };

export const RULES = {
  readyHold: 1.5,      // s standing still in full view before anything starts
  cueDelay: [1.5, 5],  // s random wait before a pose cue
  cueWindow: 5,        // s to reach the pose after the cue
  poseHold: 0.6,       // s the pose must be held
  repSecs: 4, repSlack: 10, // rep step time limit = n * repSecs + repSlack (+ calibration)
  maxGap: 3,           // s without a fully visible person = FAIL
  nonstopSecs: 20, nonstopGap: 4,  // final step: keep doing reps, no pause longer than nonstopGap
};

// rng() -> [0,1). Browser/Node default: crypto.
export const cryptoRng = () => crypto.getRandomValues(new Uint32Array(1))[0] / 2 ** 32;

export function makeSteps(rng = cryptoRng) {
  const pick = a => a[Math.floor(rng() * a.length)];
  const n = () => 4 + Math.floor(rng() * 4);          // 4..7 reps
  const first = pick(["jumping_jack", "squat"]), second = first === "squat" ? "jumping_jack" : "squat";
  const cue = () => ({ kind: "pose", pose: pick(Object.keys(POSES)), delay: RULES.cueDelay[0] + rng() * (RULES.cueDelay[1] - RULES.cueDelay[0]) });
  return [
    { kind: "ready" },
    { kind: "reps", ex: first, n: n() }, cue(),
    { kind: "reps", ex: second, n: n() }, cue(),
    { kind: "reps", ex: pick([first, second]), n: n() }, cue(),
    { kind: "nonstop", ex: pick([first, second]), secs: RULES.nonstopSecs },
  ];
}

export class Challenge {
  constructor(steps, { aspect = 0.5625 } = {}) {
    this.steps = steps; this.aspect = aspect; this.i = -1;
    this.result = null; this.counters = {}; this.calibrated = {}; this.lastSeen = null; this.t0 = null;
    this.prompt = ""; this.detail = "";
  }
  get step() { return this.steps[this.i]; }
  fail(why) { this.result = { pass: false, why }; this.prompt = "FAIL"; this.detail = why; }
  next(t) {
    this.i++; this.st = { start: t };
    if (this.i >= this.steps.length) { this.result = { pass: true, secs: t - this.t0 }; this.prompt = "PASS"; this.detail = ""; return; }
    const s = this.step;
    if (s.kind === "reps" || s.kind === "nonstop") {
      const c = this.counters[s.ex] ??= new RepCounter(s.ex, { aspect: this.aspect });
      c.reset();                                  // keeps calibrated thresholds
      this.st.calibrating = !this.calibrated[s.ex];
      this.st.lastRep = t;
    }
  }

  // Feed one frame. Returns the current result (null while running).
  update(lm, t) {
    if (this.result) return this.result;
    if (this.t0 === null) { this.t0 = t; this.next(t); }
    const full = lm && JOINTS.every(j => ok(lm[j]));
    if (full) this.lastSeen = t;
    else if (this.i > 0 && t - (this.lastSeen ?? t) > RULES.maxGap) { this.fail("left the picture"); return this.result; }
    const p = full ? lm.map(q => ({ x: q.x * this.aspect, y: q.y })) : null;
    const s = this.step, st = this.st, el = t - st.start;

    if (s.kind === "ready") {
      this.prompt = "Stand so your whole body is in view"; this.detail = "";
      const standing = p && 180 - angle(p[23], p[25], p[27]) < 30 && armsDown(p);
      if (!standing) st.since = null;
      else if ((t - (st.since ??= t)) >= RULES.readyHold) this.next(t);
      return this.result;
    }

    if (s.kind === "reps" || s.kind === "nonstop") {
      const c = this.counters[s.ex];
      if (c.update(lm, t)) {
        st.lastRep = t;
        if (st.calibrating && c.count === 3) {
          const r = c.calibrate(3);
          c.count = 0;
          if (r.ok) { st.calibrating = false; this.calibrated[s.ex] = true; st.start = t; }
          else { c.reset(); this.detail = "Calibration failed: do full reps"; }
        }
      }
      const limit = st.calibrating ? 3 * RULES.repSecs + RULES.repSlack + s.n * RULES.repSecs : s.n * RULES.repSecs + RULES.repSlack;
      if (s.kind === "reps") {
        this.prompt = st.calibrating ? `Do ${NAMES[s.ex]}: 3 to calibrate, then ${s.n}` : `Do ${s.n} ${NAMES[s.ex]}`;
        this.detail = st.calibrating ? `calibrating ${c.count}/3` : `${c.count} / ${s.n}`;
        if (!st.calibrating && c.count >= s.n) this.next(t);
        else if (t - st.start > (st.calibrating ? 3 * RULES.repSecs + RULES.repSlack : limit)) this.fail(`too slow: ${NAMES[s.ex]}`);
      } else {
        const left = s.secs - (t - st.start);
        this.prompt = st.calibrating ? `Do ${NAMES[s.ex]}: 3 to calibrate, then nonstop` : `Nonstop ${NAMES[s.ex]}`;
        this.detail = st.calibrating ? `calibrating ${c.count}/3` : `${Math.max(0, Math.ceil(left))} s left, ${c.count} reps`;
        if (t - st.lastRep > RULES.nonstopGap + (st.calibrating ? RULES.repSecs : 0)) this.fail(`stopped moving (${NAMES[s.ex]})`);
        else if (!st.calibrating && left <= 0) this.next(t);
      }
      return this.result;
    }

    if (s.kind === "pose") {
      const want = POSES[s.pose];
      if (!st.cueAt) {                              // waiting: arms down, then cue at a random moment
        this.prompt = "Arms down, wait for the cue"; this.detail = "";
        if (el >= s.delay && p && armsDown(p)) st.cueAt = t;
        else if (el > s.delay + RULES.cueWindow * 2) this.fail("arms never came down for the cue");
        return this.result;
      }
      this.prompt = want.say; this.detail = "";
      if (p) for (const [k, other] of Object.entries(POSES)) {
        if (!other.test(p)) { if (k === s.pose) st.holdSince = null; else st[k] = null; continue; }
        if (k === s.pose) { if (t - (st.holdSince ??= t) >= RULES.poseHold) return this.next(t), this.result; }
        else if (t - (st[k] ??= t) >= RULES.poseHold) { this.fail(`wrong pose: ${k}`); return this.result; }
      }
      if (t - st.cueAt > RULES.cueWindow) this.fail(`missed cue: ${s.pose}`);
      return this.result;
    }
  }
}
