// Challenge tests with simulated people. Run: node test_challenge.js
import { Challenge, makeSteps } from "./challenge.js";
import { pose, rand, setSeed, ASPECT, cyc, mulberry as seeded } from "./synth.js";

const POSE_PARAMS = { left_up: { armL: 170, armR: 15 }, right_up: { armL: 15, armR: 170 }, t_pose: { arm: 90 } };

// A simulated person. Watches the challenge state and acts (or misbehaves) with a reaction delay.
function actor({ jjPeriod = 1.2, sqPeriod = 2, react = 1, ignoreCues = false, wrongPose = false, leaveAt = null, alwaysJJ = false } = {}) {
  let cueSeenAt = null, exStart = null, lastStep = -1;
  return (ch, t) => {
    if (leaveAt !== null && t > leaveAt && t < leaveAt + 5) return null;
    if (ch.i !== lastStep) { lastStep = ch.i; exStart = t; cueSeenAt = null; }
    const s = ch.step;
    if (!s) return {};
    const doEx = ex => ex === "squat" ? { knee: 175 - 80 * cyc(((t - exStart) / sqPeriod) % 1) }
      : { arm: 15 + 150 * cyc(((t - exStart) / jjPeriod) % 1), spread: 0.8 + 1.2 * cyc(((t - exStart) / jjPeriod) % 1) };
    if (alwaysJJ && s.kind !== "ready") return doEx("jumping_jack");
    if (s.kind === "ready") return {};
    if (s.kind === "reps" || s.kind === "nonstop") return doEx(s.ex);
    if (!ch.st.cueAt || ignoreCues) return {};
    cueSeenAt ??= t;
    if (t - cueSeenAt < react) return {};
    const want = wrongPose ? (s.pose === "t_pose" ? "left_up" : "t_pose") : s.pose;
    return POSE_PARAMS[want];
  };
}

// Run a challenge live with an actor; returns { result, frames } (frames = the recording).
function live(seed, act, maxT = 400) {
  const ch = new Challenge(makeSteps(seeded(seed)), { aspect: ASPECT });
  const frames = [];
  for (let t = 0; t < maxT && !ch.result; t += 1 / 30) {
    const params = act(ch, t);
    const lm = params && rand() > 0.05 ? pose(params) : null;
    frames.push({ t, lm }); ch.update(lm, t);
  }
  return { result: ch.result ?? { pass: false, why: "never finished" }, frames };
}
function replay(seed, frames) {
  const ch = new Challenge(makeSteps(seeded(seed)), { aspect: ASPECT });
  for (const f of frames) if (ch.update(f.lm, f.t)) break;
  return ch.result ?? { pass: false, why: "recording ran out" };
}

setSeed(11);
let fail = 0;
const check = (name, ok, info) => { if (!ok) fail++; console.log(`${ok ? "PASS" : "FAIL"}  ${name.padEnd(44)} ${info}`); };
const tally = (name, runs, wantPass) => {
  const passes = runs.filter(r => r.pass).length, why = {};
  runs.filter(r => !r.pass).forEach(r => why[r.why] = (why[r.why] || 0) + 1);
  const secs = runs.filter(r => r.pass).map(r => r.secs);
  check(name, wantPass ? passes === runs.length : passes === 0,
    `${passes}/${runs.length} passed` + (secs.length ? `, ${Math.min(...secs).toFixed(0)}-${Math.max(...secs).toFixed(0)} s` : "") + (Object.keys(why).length ? "  fails: " + JSON.stringify(why) : ""));
};

const N = 30;
tally("obedient person", Array.from({ length: N }, (_, i) => live(i + 1, actor()).result), true);
tally("obedient but half-asleep (slow, 3 s reaction)", Array.from({ length: N }, (_, i) => live(i + 100, actor({ jjPeriod: 2.5, sqPeriod: 3.5, react: 3 })).result), true);
tally("ignores pose cues", Array.from({ length: N }, (_, i) => live(i + 200, actor({ ignoreCues: true })).result), false);
tally("does the wrong pose", Array.from({ length: N }, (_, i) => live(i + 300, actor({ wrongPose: true })).result), false);
tally("only jumping jacks the whole time", Array.from({ length: N }, (_, i) => live(i + 400, actor({ alwaysJJ: true })).result), false);
tally("walks out of view for 5 s", Array.from({ length: N }, (_, i) => live(i + 500, actor({ leaveAt: 30 })).result), false);

// Replay attack: record a real passing session, play it to a new challenge.
const recs = Array.from({ length: 20 }, (_, i) => live(i + 600, actor()));
check("recordings used for replay all passed live", recs.every(r => r.result.pass), "");
const reps = [];
recs.forEach((r, i) => { for (let j = 0; j < 20; j++) reps.push(replay(10000 + i * 100 + j, r.frames)); });
tally("replay of an old passing recording (400 tries)", reps, false);

const steps = makeSteps(seeded(1));
console.log("\nexample challenge:", steps.map(s => s.kind === "reps" ? `${s.n} ${s.ex}` : s.kind === "pose" ? `cue ${s.pose} after ${s.delay.toFixed(1)}s` : s.kind === "nonstop" ? `${s.secs}s nonstop ${s.ex}` : s.kind).join(" -> "));
console.log(fail ? `${fail} FAILED` : "all passed");
process.exit(fail ? 1 : 0);
