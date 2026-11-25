// Fake MediaPipe landmarks for tests. Not used by the page.
let seed = 7;
export const setSeed = s => { gen = mulberry(s); };
// mulberry32: exact 32-bit math (a float LCG loses precision and gets stuck).
export const mulberry = s => () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 2 ** 32; };
let gen = mulberry(seed);
export const rand = () => gen();
const gauss = () => Math.sqrt(-2 * Math.log(rand() + 1e-9)) * Math.cos(2 * Math.PI * rand());
export const ASPECT = 360 / 640;

// Pose params: knee angle, arm angle (0 = down, 90 = sideways, 180 = up) per side, foot spread.
// Index 11/13/15/23/25/27 = the person's LEFT side (MediaPipe convention); it sits on image right.
export function pose({ knee = 175, arm = 15, armL, armR, spread = 0.8 }, noise = 0.004) {
  const lm = Array.from({ length: 33 }, () => ({ x: 0.28, y: 0.3 }));
  const cx = 0.28, shW = 0.12, thigh = 0.13, shin = 0.13, armLen = 0.2, torso = 0.2;
  const half = (180 - knee) / 2 * Math.PI / 180;
  let shY = 0;
  for (const [side, s, a] of [[1, 0, armL ?? arm], [-1, 1, armR ?? arm]]) {
    const ank = { x: cx + side * spread * shW / 2, y: 0.88 };
    const kneeP = { x: ank.x + shin * Math.sin(half), y: ank.y - shin * Math.cos(half) };
    const hip = { x: cx + side * 0.05, y: kneeP.y - thigh * Math.cos(half) };
    const sh = { x: cx + side * shW / 2, y: hip.y - torso };
    const r = a * Math.PI / 180;
    const wr = { x: sh.x + side * armLen * Math.sin(r), y: sh.y + armLen * Math.cos(r) };
    const el = { x: (sh.x + wr.x) / 2, y: (sh.y + wr.y) / 2 };
    Object.assign(lm, { [11 + s]: sh, [13 + s]: el, [15 + s]: wr, [23 + s]: hip, [25 + s]: kneeP, [27 + s]: ank });
    shY = sh.y;
  }
  lm[0] = { x: cx, y: shY - 0.08 };  // nose
  return lm.map(p => ({ x: (p.x + noise * gauss()) / ASPECT, y: p.y + noise * gauss(), visibility: 0.6 + 0.4 * rand() }));
}

// Clip from rep durations; f(phase 0..1) -> pose params.
export function clip(durations, f, { fps = 30, drop = 0.05, rest = 1 } = {}) {
  const frames = []; let t = 0;
  const push = params => { frames.push({ t, lm: rand() < drop ? null : pose(params) }); t += 1 / fps; };
  for (let i = 0; i < rest * fps; i++) push(f(0));
  for (const d of durations) for (let i = 0; i < d * fps; i++) push(f(i / (d * fps)));
  for (let i = 0; i < rest * fps; i++) push(f(0));
  return frames;
}
export const cyc = ph => (1 - Math.cos(2 * Math.PI * ph)) / 2;   // 0 -> 1 -> 0
export const squat = depth => ph => ({ knee: 175 - (175 - depth) * cyc(ph) });
export const jj = (armTop = 165, spreadTop = 2.0) => ph => ({ arm: 15 + (armTop - 15) * cyc(ph), spread: 0.8 + (spreadTop - 0.8) * cyc(ph) });
