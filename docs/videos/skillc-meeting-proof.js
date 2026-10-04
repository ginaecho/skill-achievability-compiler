/* global window, document, location, matchMedia, performance, requestAnimationFrame, cancelAnimationFrame */
"use strict";

const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
const duration = 14;
const C = {
  white: "#f1f7ff", muted: "#a2b8d0", cyan: "#5be3ed", green: "#89e3b5",
  purple: "#b99dff", gold: "#ffd579", red: "#ff7188", edge: "#344e6a", panel: "#102139"
};
const clamp = (n, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, n));
const ease = n => 1 - Math.pow(1 - clamp(n), 3);

// This finite teaching model is not the SkillC implementation or a live mailbox probe.
const mailboxModel = Object.freeze({
  initial: Object.freeze({ scheduled: false, invited_all: false }),
  capabilities: Object.freeze({ schedule_meeting: true, invite_all: false })
});
function reachableStates(model) {
  const states = [{ ...model.initial }];
  for (let i = 0; i < states.length; i++) {
    const state = states[i];
    for (const [capability, field] of [["schedule_meeting", "scheduled"], ["invite_all", "invited_all"]]) {
      if (!model.capabilities[capability] || state[field]) continue;
      const next = { ...state, [field]: true };
      if (!states.some(s => s.scheduled === next.scheduled && s.invited_all === next.invited_all)) states.push(next);
    }
  }
  return states;
}
const reachable = reachableStates(mailboxModel);
const goalReachable = reachable.some(s => s.scheduled && s.invited_all);
function stateAt(seconds) {
  if (!Number.isFinite(seconds)) throw new TypeError("Frame time must be finite.");
  const t = clamp(seconds, 0, duration);
  const stopped = t >= 10.8;
  return {
    t, phase: t < 4.5 ? "COMPILE" : t < 9.3 ? "COMPARE" : stopped ? "STOPPED" : "PROVE",
    scheduleRevealed: t >= 5.05, invitationRevealed: t >= 6.95,
    goalTerms: ["scheduled", "invited_all"], operator: "AND",
    capabilities: mailboxModel.capabilities, reachableStates: reachable,
    goalReachable, verdict: stopped ? (goalReachable ? "ACHIEVABLE" : "IMPOSSIBLE") : null,
    stopped, runtimeActions: 0
  };
}
function text(value, x, y, size = 24, color = C.white, weight = 600, align = "left", mono = false) {
  ctx.font = `${weight} ${size}px ${mono ? '"Cascadia Code", Consolas, monospace' : '"Segoe UI", Arial, sans-serif'}`;
  ctx.textAlign = align; ctx.fillStyle = color; ctx.fillText(value, x, y);
}
function box(x, y, w, h, fill, stroke, radius = 16) {
  ctx.beginPath(); ctx.roundRect(x, y, w, h, radius);
  ctx.fillStyle = fill; ctx.fill();
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 2; ctx.stroke(); }
}
function path(points, color, width = 3, fill = false) {
  ctx.beginPath();
  points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.lineWidth = width; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.strokeStyle = color;
  if (fill) { ctx.closePath(); ctx.fillStyle = color; ctx.fill(); }
  else ctx.stroke();
}
function circle(x, y, radius, fill, stroke) {
  ctx.beginPath(); ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fillStyle = fill; ctx.fill();
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 2; ctx.stroke(); }
}
function check(x, y, color = C.green, scale = 1) {
  path([[x - 11 * scale, y], [x - 2 * scale, y + 9 * scale], [x + 15 * scale, y - 12 * scale]], color, 4 * scale);
}
function cross(x, y, color = C.red, size = 10) {
  path([[x - size, y - size], [x + size, y + size]], color, 4);
  path([[x + size, y - size], [x - size, y + size]], color, 4);
}
function reveal(t, at, draw, length = 0.35) {
  if (t < at) return;
  ctx.save();
  const f = ease((t - at) / length);
  ctx.globalAlpha *= f; ctx.translate(0, 15 * (1 - f)); draw(); ctx.restore();
}
function calendar(x, y, scale, color) {
  ctx.save(); ctx.translate(x, y); ctx.scale(scale, scale);
  box(-37, -34, 74, 68, "#14273c", color, 10);
  path([[-36, -12], [36, -12]], color, 3);
  path([[-20, -42], [-20, -27]], color, 5); path([[20, -42], [20, -27]], color, 5);
  for (let row = 0; row < 2; row++) for (let col = 0; col < 3; col++) box(-24 + col * 19, -2 + row * 17, 10, 9, color, null, 2);
  ctx.restore();
}
function people(x, y, scale, color) {
  ctx.save(); ctx.translate(x, y); ctx.scale(scale, scale);
  for (let i = -1; i <= 1; i++) {
    const py = i === 0 ? -8 : 1;
    circle(i * 29, py - 16, 10, color);
    box(i * 29 - 13, py, 26, 27, color, null, 8);
  }
  ctx.restore();
}
function envelope(x, y, scale, color) {
  ctx.save(); ctx.translate(x, y); ctx.scale(scale, scale);
  box(-49, -32, 98, 64, "#162b42", color, 10);
  path([[-45, -27], [0, 8], [45, -27]], color, 4);
  ctx.restore();
}
function flow(points, t, at, color, active = true) {
  path(points, "#2c4862", 3);
  if (t < at || !active) return;
  const lengths = points.slice(1).map((p, i) => Math.hypot(p[0] - points[i][0], p[1] - points[i][1]));
  const total = lengths.reduce((a, b) => a + b, 0);
  const elapsed = t - at;
  for (let j = 0; j < 3; j++) {
    let d = ((elapsed * 0.7 + j / 3) % 1) * total;
    for (let i = 0; i < lengths.length; i++) {
      if (d <= lengths[i]) {
        const f = d / lengths[i];
        ctx.save(); ctx.shadowBlur = 15; ctx.shadowColor = color;
        circle(points[i][0] + (points[i + 1][0] - points[i][0]) * f,
          points[i][1] + (points[i + 1][1] - points[i][1]) * f, 5, color);
        ctx.restore(); break;
      }
      d -= lengths[i];
    }
  }
}
function tag(value, x, y, w, color = C.cyan) {
  box(x, y, w, 37, "#142a3e", color, 7);
  text(value, x + w / 2, y + 25, 17, color, 700, "center", true);
}

function compileScene(t) {
  text("01 / COMPILE THE GOAL", 96, 264, 20, C.cyan, 700, "left", true);
  box(96, 303, 494, 444, "#102039", C.edge, 22);
  tag("NATURAL-LANGUAGE SKILL", 124, 331, 290, C.purple);
  calendar(172, 443, 0.84, C.purple);
  text("Schedule the meeting", 130, 535, 33, C.white, 650);
  text("and invite everyone.", 130, 581, 33, C.white, 650);
  text("Both outcomes are required.", 130, 681, 23, C.muted, 400);
  flow([[590, 518], [665, 518], [665, 408], [798, 408]], t, 0.55, C.cyan);
  flow([[665, 518], [665, 546], [1293, 546], [1293, 408], [1340, 408]], t, 0.85, C.purple);
  text("FORMALIZE", 639, 635, 17, C.muted, 600, "center", true);
  text("SCHEMA-VALIDATED FORMAL GOAL", 800, 264, 20, C.muted, 700, "left", true);
  reveal(t, 0.6, () => {
    box(800, 303, 434, 216, "#132c3f", C.cyan, 18);
    calendar(858, 364, 0.72, C.cyan);
    text("REQUIREMENT 1", 917, 365, 19, C.cyan, 700, "left", true);
    text("Meeting scheduled", 830, 435, 32, C.white, 650);
    text("scheduled", 830, 480, 24, C.cyan, 500, "left", true);
  });
  reveal(t, 1.45, () => {
    box(1340, 303, 484, 216, "#25213f", C.purple, 18);
    people(1399, 366, 0.72, C.purple);
    text("REQUIREMENT 2", 1460, 365, 19, C.purple, 700, "left", true);
    text("Everyone invited", 1370, 435, 32, C.white, 650);
    text("invited_all", 1370, 480, 24, C.purple, 500, "left", true);
  });
  reveal(t, 2.25, () => {
    path([[1017, 519], [1017, 570], [1287, 570]], C.cyan, 3);
    path([[1582, 519], [1582, 570], [1287, 570]], C.purple, 3);
    circle(1287, 570, 36, "#17354a", C.white);
    text("AND", 1287, 578, 20, C.white, 800, "center", true);
    box(800, 622, 1024, 125, "#0c1a2d", "#4d728b", 16);
    text("GOAL = scheduled AND invited_all", 1312, 675, 30, C.white, 600, "center", true);
    text("Scheduling alone does not satisfy the goal.", 1312, 717, 25, C.muted, 400, "center");
  });
}

function goalStrip(x, y, w, checked) {
  box(x, y, w, 92, "#102039", C.edge, 15);
  text("GOAL", x + 29, y + 56, 22, C.muted, 700, "left", true);
  text("scheduled", x + 173, y + 56, 31, checked ? C.green : C.cyan, 650, "left", true);
  tag("AND", x + 413, y + 29, 78, C.white);
  text("invited_all", x + 541, y + 56, 31, checked ? C.red : C.purple, 650, "left", true);
  text(checked ? "UNREACHABLE" : "BOTH REQUIRED", x + w - 32, y + 56, 23, checked ? C.red : C.muted, 700, "right", true);
}
function compareScene(t) {
  goalStrip(96, 259, 1728, false);
  box(96, 392, 466, 393, "#102039", C.edge, 22);
  text("DECLARED MAILBOX", 329, 432, 20, C.muted, 700, "center", true);
  envelope(329, 519, 1.25, C.cyan);
  text("Available capabilities", 329, 597, 26, C.white, 600, "center");
  reveal(t, 5.05, () => {
    check(137, 646, C.green, 0.8);
    text("Can schedule", 164, 653, 25, C.green, 600);
  });
  reveal(t, 6.95, () => {
    cross(137, 713, C.red, 9);
    text("Cannot invite everyone", 164, 721, 25, C.red, 600);
  });
  flow([[562, 519], [651, 519], [651, 479], [744, 479]], t, 4.8, C.green, t < 6.8);
  flow([[562, 695], [651, 695], [651, 683], [704, 683]], t, 6.5, C.purple, t < 7.3);
  if (t >= 6.95) {
    reveal(t, 6.95, () => {
      box(704, 658, 9, 50, C.red, null, 3);
      cross(727, 683, C.red, 8);
    });
  }
  box(746, 392, 1078, 176, "#102a32", t >= 5.05 ? "#4fa082" : C.edge, 20);
  calendar(810, 459, 0.85, t >= 5.05 ? C.green : C.muted);
  text("MEETING SCHEDULED", 878, 438, 20, C.muted, 700, "left", true);
  reveal(t, 5.05, () => {
    text("Reachable", 878, 486, 35, C.green, 700);
    text("The mailbox has a scheduling action.", 878, 534, 26, C.white, 400);
    circle(1755, 456, 31, "#183e38", C.green); check(1755, 456);
  });
  box(746, 609, 1078, 176, t >= 6.95 ? "#2b1c30" : "#162139", t >= 6.95 ? "#b3506d" : C.edge, 20);
  people(810, 674, 0.85, t >= 6.95 ? C.red : C.muted);
  text("EVERYONE INVITED", 878, 654, 20, C.muted, 700, "left", true);
  reveal(t, 6.95, () => {
    text("Unreachable", 878, 702, 35, C.red, 700);
    text("No available action can make invited_all true.", 878, 750, 26, C.white, 400);
    circle(1755, 671, 31, "#461f33", C.red); cross(1755, 671);
  });
}

function stateNode(x, y, label, detail, color, ghost = false) {
  box(x, y, 226, 112, ghost ? "#281d30" : "#132d3e", color, 14);
  text(label, x + 113, y + 42, 23, color, 700, "center", true);
  text(detail, x + 113, y + 81, 21, C.white, 500, "center", true);
}
function shield(x, y, color) {
  path([[x, y - 34], [x + 31, y - 21], [x + 27, y + 14], [x, y + 34],
    [x - 27, y + 14], [x - 31, y - 21]], "#153b40", 2, true);
  path([[x, y - 34], [x + 31, y - 21], [x + 27, y + 14], [x, y + 34],
    [x - 27, y + 14], [x - 31, y - 21], [x, y - 34]], color, 2);
  check(x, y, color);
}
function idleAgent(x, y, t, stopped) {
  ctx.save(); ctx.translate(x, y);
  const bob = Math.sin(t * 2.5) * 2;
  ctx.beginPath(); ctx.ellipse(0, 18, 56, 13, 0, 0, Math.PI * 2); ctx.fillStyle = "#060e20"; ctx.fill();
  box(-33, -5, 28, 16, "#63859c", null, 5);
  box(5, -5, 28, 16, "#63859c", null, 5);
  box(-34, -67 + bob, 68, 66, "#7299b4", "#15273d", 14);
  box(-17, -47 + bob, 34, 22, "#17324a", null, 5);
  path([[-6, -38 + bob], [-6, -30 + bob]], C.muted, 3);
  path([[6, -38 + bob], [6, -30 + bob]], C.muted, 3);
  path([[-38, -47 + bob], [-49, -15 + bob]], "#7299b4", 11);
  path([[38, -47 + bob], [49, -15 + bob]], "#7299b4", 11);
  box(-46, -126 + bob, 92, 65, "#8aacc5", "#12263d", 17);
  box(-34, -111 + bob, 68, 34, "#11263b", null, 10);
  path([[-23, -94 + bob], [-11, -94 + bob]], C.cyan, 4);
  path([[11, -94 + bob], [23, -94 + bob]], C.cyan, 4);
  path([[0, -127 + bob], [0, -142 + bob]], "#668da5", 4);
  circle(0, -147 + bob, 6, C.cyan);
  text(stopped ? "NOT STARTED" : "AWAITING CHECK", 0, 62, 19, C.muted, 700, "center", true);
  ctx.restore();
}
function proofScene(t) {
  const stopped = t >= 10.8;
  goalStrip(96, 259, 1728, true);
  box(96, 391, 1070, 411, "#0d1d31", C.edge, 22);
  shield(143, 438, C.green);
  text("DETERMINISTIC ACHIEVABILITY CHECKER", 197, 439, 22, C.green, 700, "left", true);
  text("Reachable states in the declared model", 127, 492, 22, C.muted, 400);
  reveal(t, 9.3, () => {
    stateNode(127, 520, "START", "S = 0 / I = 0", C.cyan);
    flow([[353, 576], [444, 576]], t, 9.35, C.green, !stopped);
    text("schedule", 398, 546, 15, C.muted, 600, "center", true);
    stateNode(444, 520, "SCHEDULED", "S = 1 / I = 0", C.green);
    path([[670, 576], [829, 576]], "#854159", 3);
    cross(750, 576, C.red, 13);
    stateNode(829, 520, "GOAL", "S = 1 / I = 1", C.red, true);
  });
  reveal(t, 9.65, () => {
    text("I = invited_all stays false on every modeled path.", 127, 685, 25, C.white, 500);
    text("S AND I can never be true. The goal is unreachable.", 127, 730, 25, C.white, 500);
    text("Model invariant: no action can establish I.", 127, 775, 20, C.muted, 400, "left", true);
  });
  box(1200, 391, 624, 411, "#102039", stopped ? "#448c81" : C.edge, 22);
  text("PRE-EXECUTION GATE", 1512, 437, 21, C.muted, 700, "center", true);
  idleAgent(1660, 665, t, stopped);
  const gate = stopped ? C.red : C.gold;
  box(1481, 506, 17, 212, "#354d68", null, 6);
  box(1325, 519, 173, 31, "#2c2535", gate, 7);
  for (let i = 0; i < 5; i++) path([[1335 + i * 32, 523], [1355 + i * 32, 546]], gate, 6);
  reveal(t, 10.8, () => {
    box(1231, 465, 344, 40, "#351e30", "#af536f", 7);
    text("IMPOSSIBLE", 1403, 493, 27, C.red, 800, "center", true);
    text("STOP", 1385, 607, 38, C.red, 800, "center", true);
    text("No agent execution.", 1512, 774, 26, C.green, 650, "center");
  });
  if (!stopped) text("CHECK FIRST", 1385, 607, 23, C.gold, 700, "center", true);
}

function renderFrame(seconds) {
  const s = stateAt(seconds);
  const { t } = s;
  const background = ctx.createLinearGradient(0, 0, 1920, 1080);
  background.addColorStop(0, "#080f20"); background.addColorStop(1, "#12283e");
  ctx.fillStyle = background; ctx.fillRect(0, 0, 1920, 1080);
  const halo = ctx.createRadialGradient(1130, 490, 30, 1130, 490, 900);
  halo.addColorStop(0, "#4075a121"); halo.addColorStop(1, "#00000000");
  ctx.fillStyle = halo; ctx.fillRect(0, 0, 1920, 1080);
  ctx.save(); ctx.globalAlpha = 0.15;
  for (let x = 32; x < 1920; x += 48) for (let y = 32; y < 1080; y += 48) circle(x, y, 1, "#839dbb");
  ctx.restore();
  text("SkillC", 96, 72, 33, C.cyan, 800);
  text("/ COMPILE BEFORE YOU RUN", 218, 70, 19, C.muted, 700, "left", true);
  tag("0 RUNTIME ACTIONS", 1545, 43, 279, C.green);
  const heading = t < 4.5 ? "One goal. Two requirements." : t < 9.3 ? "Can this mailbox achieve both?"
    : t < 10.8 ? "The goal is provably unreachable." : "SkillC stops before execution.";
  text(heading, 96, 166, 62, s.stopped ? C.green : C.white, 750);
  const subtitle = t < 4.5 ? "Compile the requested outcome into explicit logical conditions."
    : t < 9.3 ? "Compare the formal goal with the capabilities in the declared environment."
    : "The verdict follows from reachable states, not an LLM opinion.";
  text(subtitle, 98, 211, 24, C.muted, 400);
  if (t < 4.5) compileScene(t);
  else if (t < 9.3) reveal(t, 4.5, () => compareScene(t), 0.22);
  else reveal(t, 9.3, () => proofScene(t), 0.22);

  let captions;
  if (t < 4.5) captions = ["SkillC sees that the goal requires", "scheduling the meeting and inviting everyone."];
  else if (t < 6.95) captions = ["This mailbox can schedule,"];
  else if (t < 10.8) captions = ["but it cannot invite everyone."];
  else captions = ["So SkillC stops immediately:", "IMPOSSIBLE"];
  captions.forEach((value, i) => text(value, 960, (captions.length === 1 ? 901 : 867) + i * 49, i === 1 && s.stopped ? 42 : 35,
    i === 1 && s.stopped ? C.red : C.white, i === 1 && s.stopped ? 800 : 500, "center", i === 1 && s.stopped));
  const steps = [[0, 4.5, "COMPILE THE GOAL"], [4.5, 9.3, "CHECK CAPABILITIES"], [9.3, 10.8, "PROVE"], [10.8, 14, "STOP"]];
  for (const [start, end, label] of steps) {
    const x = 96 + start / duration * 1728, w = (end - start) / duration * 1728 - 10;
    box(x, 964, w, 4, "#29445e", null, 2);
    if (t > start) box(x, 964, Math.max(1, w * clamp((t - start) / (end - start))), 4, C.cyan, null, 2);
    text(label, x, 997, 16, t >= start && t < end ? C.white : C.muted, 650, "left", true);
  }
  text("ILLUSTRATIVE DECLARED-MAILBOX MODEL / NOT A LIVE CHECK", 96, 1046, 16, C.muted, 500, "left", true);
  text("CHECKER WORK IS NOT AGENT EXECUTION", 1824, 1046, 16, C.muted, 500, "right", true);
  return s;
}

const play = document.getElementById("play");
const scrub = document.getElementById("scrub");
const output = document.getElementById("time");
let current = 0, playing = false, started = 0, request;
function show(t) {
  current = clamp(t, 0, duration); renderFrame(current); scrub.value = String(current);
  output.textContent = `${current.toFixed(2)} / ${duration.toFixed(2)} s`;
}
function pause() {
  playing = false; cancelAnimationFrame(request); play.textContent = "Play";
}
function tick(now) {
  show((now - started) / 1000);
  if (current >= duration) pause();
  else request = requestAnimationFrame(tick);
}
function start() {
  pause();
  if (current >= duration) current = 0;
  started = performance.now() - current * 1000; playing = true; play.textContent = "Pause";
  request = requestAnimationFrame(tick);
}
play.addEventListener("click", () => playing ? pause() : start());
document.getElementById("replay").addEventListener("click", () => { show(0); start(); });
scrub.addEventListener("input", () => { pause(); show(Number(scrub.value)); });
window.animation = { renderFrame, stateAt, duration, width: 1920, height: 1080 };
show(0);
if (!new URLSearchParams(location.search).has("render") && !matchMedia("(prefers-reduced-motion: reduce)").matches) start();
