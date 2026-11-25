// Re-run a recorded challenge from scratch. stdin: {steps, frames:[{t, lm}], aspect}. stdout: result JSON.
// The server uses this so the verdict comes from the landmarks, not from the page saying "PASS".
import { Challenge } from "./challenge.js";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const { steps, frames, aspect } = JSON.parse(input);
const ch = new Challenge(steps, { aspect });
let r = null;
for (const f of frames) if ((r = ch.update(f.lm, f.t))) break;
console.log(JSON.stringify(r ?? { pass: false, why: "recording ended before the challenge finished" }));
