// Synthetic-landmark tests for counter.js. Run: node test_counter.js
import { RepCounter } from "./counter.js";
import { rand, ASPECT, clip, squat, jj, cyc } from "./synth.js";

// Session = 3 calibration reps, calibrate, then the test part. Returns reps counted after calibration.
function session(ex, calibFrames, testFrames) {
  const c = new RepCounter(ex, { aspect: ASPECT });
  for (const f of calibFrames) c.update(f.lm, f.t);
  const cal = c.calibrate(3);
  if (!cal.ok) return { cal };
  const before = c.count, t0 = calibFrames.at(-1).t + 0.5;
  for (const f of testFrames) c.update(f.lm, f.t + t0);
  return { cal, n: c.count - before };
}

const R = (n, lo, hi) => Array.from({ length: n }, () => lo + (hi - lo) * rand());
const cases = [
  // [name, exercise, calib clip, test clip, expected count]
  ["squat normal", "squat", clip([2, 2, 2], squat(95)), clip(R(10, 1.8, 2.5), squat(95)), 10],
  ["squat slow+varied depth", "squat", clip([3, 3, 3], squat(100)), clip(R(10, 1.5, 6), ph => squat(90 + 25 * rand())(ph), { drop: 0.15 }), 10],
  ["squat 15fps", "squat", clip([2, 2, 2], squat(95), { fps: 15 }), clip(R(10, 1.5, 3), squat(95), { fps: 15 }), 10],
  ["half squats (fake)", "squat", clip([2, 2, 2], squat(95)), clip(R(10, 1, 2), squat(150)), 0],
  ["standing jitter (squat)", "squat", clip([2, 2, 2], squat(95)), clip([], squat(95), { rest: 20 }), 0],
  ["jj normal", "jumping_jack", clip([1, 1, 1], jj()), clip(R(10, 0.8, 1.3), jj()), 10],
  ["jj slow sloppy", "jumping_jack", clip([2, 2, 2], jj(140, 1.6)), clip(R(10, 1.5, 4), jj(130, 1.5), { drop: 0.15 }), 10],
  ["jj 60fps", "jumping_jack", clip([1, 1, 1], jj(), { fps: 60 }), clip(R(10, 0.8, 1.2), jj(), { fps: 60 }), 10],
  ["arm waving, legs still (fake)", "jumping_jack", clip([1, 1, 1], jj()), clip(R(10, 0.8, 1.5), jj(165, 0.8)), 0],
  ["legs only, arms down (fake)", "jumping_jack", clip([1, 1, 1], jj()), clip(R(10, 0.8, 1.5), jj(15, 2.0)), 0],
  ["squats, arms overhead (fake jj)", "jumping_jack", clip([1, 1, 1], jj()), clip(R(10, 1.5, 2.5), ph => ({ ...squat(95)(ph), arm: 15 + 150 * cyc(ph), spread: 1.4 })), 0],
  ["standing jitter (jj)", "jumping_jack", clip([1, 1, 1], jj()), clip([], jj(), { rest: 20 }), 0],
];

let fail = 0;
for (const [name, ex, cal, test, want] of cases) {
  const r = session(ex, cal, test);
  const ok = r.cal.ok && r.n === want;
  if (!ok) fail++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${name.padEnd(30)} want ${want}  got ${r.cal.ok ? r.n : "calib failed: " + r.cal.why}`);
}
// Calibration must refuse tiny movements.
const tiny = session("squat", clip([2, 2, 2], squat(150)), []);
console.log(`${tiny.cal.ok ? "FAIL" : "PASS"}  tiny-calibration rejected        (${tiny.cal.why ?? "accepted!"})`);
if (tiny.cal.ok) fail++;
console.log(fail ? `${fail} FAILED` : "all passed");
process.exit(fail ? 1 : 0);
