// Test helper: stdin = steps JSON, argv[2] = "obey" | "ignore". Prints {frames, aspect} of a simulated
// person running that challenge live, with frames in the same compact form the page sends.
import { Challenge } from "./challenge.js";
import { pose, ASPECT, cyc } from "./synth.js";

let input = ""; for await (const c of process.stdin) input += c;
const steps = JSON.parse(input), obey = process.argv[2] !== "ignore";
const POSE = { left_up: { armL: 170, armR: 15 }, right_up: { armL: 15, armR: 170 }, t_pose: { arm: 90 } };
const r4 = v => Math.round(v * 1e4) / 1e4;
const ch = new Challenge(steps, { aspect: ASPECT });
const frames = []; let li = -1, start = 0, cueSeen = null;
for (let t = 0; t < 400 && !ch.result; t += 1 / 30) {
  if (ch.i !== li) { li = ch.i; start = t; cueSeen = null; }
  const s = ch.step; let prm = {};
  if (s?.kind === "reps" || s?.kind === "nonstop") {
    const ph = ((t - start) / (s.ex === "squat" ? 2 : 1.2)) % 1;
    prm = s.ex === "squat" ? { knee: 175 - 80 * cyc(ph) } : { arm: 15 + 150 * cyc(ph), spread: 0.8 + 1.2 * cyc(ph) };
  } else if (s?.kind === "pose" && ch.st.cueAt && obey) { cueSeen ??= t; if (t - cueSeen > 1) prm = POSE[s.pose]; }
  const lm = pose(prm).map(q => ({ x: r4(q.x), y: r4(q.y), visibility: r4(q.visibility) }));
  frames.push({ t: r4(t), lm }); ch.update(lm, r4(t));
}
console.log(JSON.stringify({ frames, aspect: ASPECT, result: ch.result }));
