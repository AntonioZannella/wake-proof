// Rule-based rep counter for MediaPipe Pose landmarks (33 points, normalized x/y, visibility).
// Pure logic, no DOM: runs in the browser and in Node for tests.

const L = { sh: [11, 12], el: [13, 14], wr: [15, 16], hip: [23, 24], knee: [25, 26], ank: [27, 28] };

function angle(a, b, c) { // angle at b, degrees
  const v1x = a.x - b.x, v1y = a.y - b.y, v2x = c.x - b.x, v2y = c.y - b.y;
  const cos = (v1x * v2x + v1y * v2y) / (Math.hypot(v1x, v1y) * Math.hypot(v2x, v2y) || 1);
  return Math.acos(Math.max(-1, Math.min(1, cos))) * 180 / Math.PI;
}
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

// Signals per exercise. Each returns null when needed joints are not visible enough.
// 'main' drives the up/down cycle; 'aux' (optional) must also reach its peak during the rep.
export const EXERCISES = {
  // Knee angle (hip-knee-ankle): ~175 standing, < ~110 at the bottom. We flip it so "peak" = bottom.
  squat: {
    joints: [...L.hip, ...L.knee, ...L.ank],
    signals(p) {
      const k = (angle(p[23], p[25], p[27]) + angle(p[24], p[26], p[28])) / 2;
      return { main: 180 - k };
    },
    defaults: { main: [20, 60] },      // [low, high] thresholds before calibration (degrees of bend)
    minRange: { main: 45 },            // calibration must show at least this much bend
  },
  // Arms: angle at shoulder between hip and wrist (~20 down, ~160 up). Legs: ankle gap / shoulder width.
  jumping_jack: {
    joints: [...L.sh, ...L.wr, ...L.hip, ...L.ank],
    signals(p) {
      const arm = (angle(p[23], p[11], p[15]) + angle(p[24], p[12], p[16])) / 2;
      const legs = dist(p[27], p[28]) / (dist(p[11], p[12]) || 1);
      const bend = 180 - (angle(p[23], p[25], p[27]) + angle(p[24], p[26], p[28])) / 2;
      return { main: arm, aux: legs, bend };
    },
    // Knees must stay fairly straight: rejects squats done with arms overhead.
    veto: ext => ext.bend.max > 50,
    defaults: { main: [60, 120], aux: [0.9, 1.4] },
    minRange: { main: 70, aux: 0.4 },
  },
};

export class RepCounter {
  // opts: aspect = video width/height (landmarks are normalized per axis), minVis, smoothing tau (s)
  // lo/hi: thresholds as fractions of the calibrated range; auxHi lower so tired, smaller leg spreads still count.
  // Defaults tuned on 5 real clips (2026-11-25): see README.md.
  constructor(exercise, { aspect = 1, minVis = 0.3, tau = 0.08, minRepSec = 0.35, lo = 0.3, hi = 0.45, auxHi = 0.4, med = 5 } = {}) {
    this.ex = EXERCISES[exercise];
    if (!this.ex) throw new Error("unknown exercise " + exercise);
    Object.assign(this, { name: exercise, aspect, minVis, tau, minRepSec, loFrac: lo, hiFrac: hi, auxHiFrac: auxHi, medN: med });
    this.th = structuredClone(this.ex.defaults);
    this.reset();
  }
  reset() {
    this.count = 0; this.state = "down"; this.sm = null; this.lastT = null; this.auxHit = false;
    this.repStart = null; this.reps = []; this.cur = null; this.dropped = 0; this.frames = 0; this.hist = [];
  }

  // Feed one frame. lm = 33 landmarks or null/undefined (no person). Returns true if a rep completed.
  update(lm, t) {
    this.frames++;
    // Skip frames where a needed joint is low-confidence or outside the picture (guessed by the model).
    const bad = q => !(q?.visibility >= this.minVis) || q.x < 0 || q.x > 1 || q.y < 0 || q.y > 1;
    if (!lm || this.ex.joints.some(i => bad(lm[i]))) { this.dropped++; return false; }
    const p = lm.map(q => ({ x: q.x * this.aspect, y: q.y }));
    // Median of the last few frames kills one-frame landmark glitches before smoothing.
    if (this.lastT !== null && t - this.lastT > 1) this.hist = [];
    this.hist.push(this.ex.signals(p));
    if (this.hist.length > this.medN) this.hist.shift();
    const raw = {};
    for (const k in this.hist[0]) { const v = this.hist.map(h => h[k]).sort((a, b) => a - b); raw[k] = v[v.length >> 1]; }
    // Exponential smoothing with time-based alpha, so pace / fps changes don't matter.
    if (!this.sm || t - this.lastT > 1) this.sm = { ...raw };
    else {
      const a = 1 - Math.exp(-(t - this.lastT) / this.tau);
      for (const k in raw) this.sm[k] += a * (raw[k] - this.sm[k]);
    }
    this.lastT = t;
    const s = this.sm, th = this.th;
    // Track extremes of the current rep (used by calibration and reported per rep).
    if (this.cur) for (const k in s) { this.cur[k].min = Math.min(this.cur[k].min, s[k]); this.cur[k].max = Math.max(this.cur[k].max, s[k]); }

    if (this.state === "down") {
      if (s.main > th.main[1]) {                  // crossed high threshold: in the "up/deep" phase
        this.state = "up"; this.repStart ??= t;
        this.cur ??= Object.fromEntries(Object.keys(s).map(k => [k, { min: s[k], max: s[k] }]));
        this.auxHit = !th.aux || s.aux > th.aux[1];
      } else if (s.main < th.main[0]) {           // fully down: a new rep window starts here
        this.repStart = t;
        this.cur = Object.fromEntries(Object.keys(s).map(k => [k, { min: s[k], max: s[k] }]));
      }
      return false;
    }
    // state "up"
    if (th.aux && s.aux > th.aux[1]) this.auxHit = true;
    if (s.main < th.main[0]) {                    // back below low threshold: rep complete?
      this.state = "down";
      const dur = t - (this.repStart ?? t);
      const ok = this.auxHit && dur >= this.minRepSec && !(this.cur && this.ex.veto?.(this.cur));
      if (ok) { this.count++; this.reps.push({ t, dur, ext: this.cur }); }
      this.repStart = t; this.auxHit = false;
      this.cur = Object.fromEntries(Object.keys(s).map(k => [k, { min: s[k], max: s[k] }]));
      return ok;
    }
    return false;
  }

  // Calibrate from the extremes of the first n counted reps. Thresholds go to loFrac/hiFrac
  // of the person's own range. Fails if the range is too small (tiny fake movements).
  calibrate(n = 3) {
    const reps = this.reps.slice(0, n);
    if (reps.length < n) return { ok: false, why: `only ${reps.length} reps` };
    const med = a => a.sort((x, y) => x - y)[a.length >> 1];
    const th = {};
    for (const k of Object.keys(this.ex.defaults)) {
      const lo = med(reps.map(r => r.ext[k].min)), hi = med(reps.map(r => r.ext[k].max));
      if (hi - lo < this.ex.minRange[k]) return { ok: false, why: `${k} range ${(hi - lo).toFixed(2)} < ${this.ex.minRange[k]}` };
      th[k] = [lo + this.loFrac * (hi - lo), lo + (k === "aux" ? this.auxHiFrac : this.hiFrac) * (hi - lo)];
    }
    this.th = th;
    return { ok: true, th };
  }
}
