/* global window, document, location, matchMedia, performance, requestAnimationFrame, cancelAnimationFrame */
"use strict";

const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
const colors = {
  ink: "#080f20", white: "#f1f7ff", muted: "#9fb6d3", cyan: "#5be3ed",
  gold: "#ffd579", red: "#ff7188", floor: "#17283d", green: "#9ae6b4"
};
const clamp = (n, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, n));
const smooth = n => { const x = clamp(n); return x * x * (3 - 2 * x); };
const mix = (a, b, n) => a + (b - a) * n;
const phases = [
  { at: 0, label: "EXECUTING", heading: "A busy squad. An impossible quest.", color: colors.cyan },
  { at: 4, label: "RETRYING", heading: "They retry.", color: colors.gold },
  { at: 5, label: "WAITING", heading: "They wait.", color: colors.gold },
  { at: 6, label: "REPLANNING", heading: "They adapt.", color: colors.cyan },
  { at: 7, label: "FINAL ATTEMPT", heading: "All that effort. All those tokens.", color: colors.gold },
  { at: 8.15, label: "FAILED", heading: "Every agent discovers failure.", color: colors.red }
];
const bots = [
  { name: "PLANNER", color: "#b99dff", route: [[320, 473], [755, 434], [1070, 604], [425, 721]], offset: 0.0, end: [540, 717] },
  { name: "SCOUT", color: "#5be3ed", route: [[755, 434], [1110, 452], [850, 717], [320, 473]], offset: 0.5, end: [754, 738] },
  { name: "BUILDER", color: "#ffd579", route: [[425, 721], [760, 530], [1110, 452], [820, 721]], offset: 0.3, end: [964, 717] },
  { name: "CHECKER", color: "#9ae6b4", route: [[1110, 452], [1180, 695], [425, 721], [755, 434]], offset: 0.9, end: [1174, 738] },
  { name: "RUNNER", color: "#ffac83", route: [[820, 721], [320, 473], [920, 552], [1180, 695]], offset: 0.1, end: [1384, 717] },
  { name: "COURIER", color: "#f0a4db", route: [[1180, 695], [755, 434], [425, 721], [1050, 534]], offset: 0.7, end: [1594, 738] }
];

function text(value, x, y, size = 24, color = colors.white, weight = 600, align = "left", mono = false) {
  ctx.font = `${weight} ${size}px ${mono ? '"Cascadia Code", Consolas, monospace' : '"Segoe UI", Arial, sans-serif'}`;
  ctx.textAlign = align;
  ctx.fillStyle = color;
  ctx.fillText(value, x, y);
}
function box(x, y, w, h, fill, stroke, radius = 12) {
  ctx.beginPath(); ctx.roundRect(x, y, w, h, radius);
  ctx.fillStyle = fill; ctx.fill();
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 2; ctx.stroke(); }
}
function path(points, color, width = 3, closed = false, fill = false) {
  ctx.beginPath();
  points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  if (closed) ctx.closePath();
  if (fill) { ctx.fillStyle = color; ctx.fill(); }
  else { ctx.lineWidth = width; ctx.lineJoin = "round"; ctx.lineCap = "round"; ctx.strokeStyle = color; ctx.stroke(); }
}
function ellipse(x, y, rx, ry, color) {
  ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
  ctx.fillStyle = color; ctx.fill();
}
function cross(x, y, size, color, width = 4) {
  path([[x - size, y - size], [x + size, y + size]], color, width);
  path([[x + size, y - size], [x - size, y + size]], color, width);
}
function icon(type, x, y, scale, color) {
  ctx.save(); ctx.translate(x, y); ctx.scale(scale, scale);
  if (type === "search") {
    ctx.beginPath(); ctx.arc(-4, -5, 14, 0, Math.PI * 2); ctx.strokeStyle = color; ctx.lineWidth = 5; ctx.stroke();
    path([[7, 7], [23, 23]], color, 7);
  } else if (type === "build") {
    path([[-10, -18], [-28, 0], [-10, 18]], color, 5);
    path([[10, -18], [28, 0], [10, 18]], color, 5);
    path([[5, -24], [-5, 24]], color, 4);
  } else if (type === "check") {
    path([[-22, 0], [-5, 17], [24, -20]], color, 6);
  } else if (type === "mail") {
    box(-27, -17, 54, 36, "#10203b", color, 3);
    path([[-26, -16], [0, 4], [26, -16]], color, 3);
  } else if (type === "lock") {
    ctx.beginPath(); ctx.arc(0, -10, 12, Math.PI, 0);
    ctx.lineWidth = 5; ctx.strokeStyle = color; ctx.stroke();
    box(-19, -10, 38, 30, color, null, 5);
    ellipse(0, 1, 3, 3, colors.ink); path([[0, 2], [0, 10]], colors.ink, 3);
  } else {
    path([[-19, -17], [-19, 17], [19, 17]], color, 4);
    path([[-19, -17], [19, -17], [19, 17]], color, 4);
    path([[-9, -7], [8, -7]], color, 3);
    path([[-9, 4], [8, 4]], color, 3);
  }
  ctx.restore();
}

function activityClock(t) {
  if (t < 5) return t;
  if (t < 6) return 5;
  return 5 + (t - 6) * 1.4;
}
function routePosition(bot, t) {
  const clock = activityClock(t);
  const index = (clock / 1.15 + bot.offset) % bot.route.length;
  const segment = Math.floor(index);
  const u = clamp((index - segment - 0.13) / 0.74);
  const a = bot.route[segment];
  const b = bot.route[(segment + 1) % bot.route.length];
  const bend = t >= 6 ? 68 * Math.sin(u * Math.PI) : 20 * Math.sin(u * Math.PI);
  return {
    x: mix(a[0], b[0], smooth(u)), y: mix(a[1], b[1], smooth(u)) - bend,
    running: u > 0 && u < 1 && !(t >= 5 && t < 6), dir: b[0] >= a[0] ? 1 : -1
  };
}
function agentAt(bot, i, t) {
  const failAt = 7.88 + i * 0.05;
  let p = routePosition(bot, Math.min(t, 7));
  if (t >= 7) {
    const convergence = smooth((t - 7) / 0.82);
    p = { x: mix(p.x, bot.end[0], convergence), y: mix(p.y, bot.end[1], convergence),
      running: t < 7.82, dir: bot.end[0] >= p.x ? 1 : -1 };
  }
  const failed = t >= failAt;
  return { ...p, name: bot.name, failed, failAt,
    status: failed ? "FAILED" : t >= 5 && t < 6 ? "WAITING" : p.running ? "RUNNING" : "WORKING" };
}
function stateAt(seconds) {
  if (!Number.isFinite(seconds)) throw new TypeError("Frame time must be finite.");
  const t = clamp(seconds, 0, 10);
  let tokens;
  if (t < 4) tokens = Math.round(800 + t * 1350);
  else if (t < 5) tokens = Math.round(6200 + (t - 4) * 1700);
  else if (t < 6) tokens = 7900;
  else if (t < 7) tokens = Math.round(7900 + (t - 6) * 2450);
  else tokens = Math.round(10350 + clamp((t - 7) / 1.15) * 2130);
  return { t, tokens, phase: phases.findLast(p => t >= p.at), waiting: t >= 5 && t < 6,
    failed: t >= 8.15, agents: bots.map((b, i) => agentAt(b, i, t)), goalsReached: 0 };
}

function station(x, y, label, type, color, t, failed) {
  ellipse(x, y + 32, 107, 26, "#070e1f80");
  box(x - 82, y - 4, 164, 39, "#172132", "#405471", 10);
  box(x - 86, y - 29, 172, 43, "#354a68", "#6580a0", 10);
  box(x - 68, y - 119, 136, 99, "#0a1021", failed ? "#515671" : color, 13);
  box(x - 60, y - 111, 120, 78, failed ? "#202337" : "#162f44", null, 9);
  icon(type, x, y - 73, 0.87, failed ? "#6d7489" : color);
  box(x - 36, y - 14, 72, 13, "#0b1727", "#576986", 3);
  for (let j = 0; j < 5; j++) box(x - 28 + j * 12, y - 10, 7, 4, color, null, 1);
  ellipse(x + 66, y + 23, 4, 4, failed ? colors.red : color);
  text(label, x, y + 61, 19, failed ? colors.muted : color, 700, "center", true);
  if (!failed && !(t >= 5 && t < 6)) {
    const f = (t * 1.35 + x / 1000) % 1;
    ctx.save(); ctx.globalAlpha = Math.sin(f * Math.PI) * 0.9;
    text(["+128", "+256", "+512"][Math.floor(t + x) % 3], x + 65, y - 88 - f * 22, 23, colors.gold, 700, "center", true);
    ctx.restore();
  }
}

function floor(t, failed) {
  box(88, 300, 1744, 547, "#0b1424", "#3c4a66", 50);
  box(88, 263, 1744, 547, colors.floor, "#4c6282", 50);
  ctx.save();
  ctx.beginPath(); ctx.roundRect(90, 265, 1740, 543, 48); ctx.clip();
  for (let y = 288; y < 817; y += 66) {
    for (let x = 105; x < 1830; x += 92) {
      box(x, y, 86, 60, (Math.round(x / 92) + Math.round(y / 66)) % 2 ? "#1b2d43" : "#1d3047", null, 5);
    }
  }
  const lanes = [
    [[245, 476], [757, 476], [1110, 476], [1564, 476]],
    [[245, 476], [245, 719], [1152, 719], [1564, 719], [1564, 476]],
    [[757, 476], [757, 719]], [[1110, 476], [1110, 719]]
  ];
  for (const lane of lanes) {
    path(lane, "#0a142470", 18);
    ctx.setLineDash([7, 16]); path(lane, failed ? "#764355" : "#3f6886", 2); ctx.setLineDash([]);
  }
  if (t >= 6 && t < 7.85) {
    ctx.globalAlpha = Math.min(1, (t - 6) * 3);
    ctx.setLineDash([10, 14]);
    path([[320, 475], [570, 597], [935, 533], [1200, 631], [1500, 546]], colors.cyan, 3);
    ctx.setLineDash([]); ctx.globalAlpha = 1;
  }
  ctx.restore();
  for (let x = 145; x < 1810; x += 96) {
    box(x, 820, 34, 5, failed ? "#ca536f" : "#40818f", null, 2);
  }
  text("AGENT WORKSHOP", 128, 297, 17, "#8ea5c3", 700, "left", true);
}

function goal(t, failed) {
  const x = 1595, y = 432;
  ellipse(x, y + 100, 146, 32, "#070e1f80");
  box(x - 121, y - 92, 242, 190, "#101a30", failed ? "#ff7188" : "#638bb5", 19);
  box(x - 108, y - 78, 216, 174, "#182b46", "#365574", 13);
  const fill = ctx.createLinearGradient(x, y - 70, x, y + 94);
  fill.addColorStop(0, failed ? "#6d293e" : "#244c66");
  fill.addColorStop(1, failed ? "#321b30" : "#182a44");
  box(x - 96, y - 68, 192, 156, fill, null, 9);
  for (let j = 0; j < 5; j++) path([[x - 91, y - 38 + j * 27], [x + 91, y - 38 + j * 27]], failed ? "#8d3d52" : "#37617a", 2);
  icon("mail", x, y - 18, 1.23, failed ? "#d18a9e" : "#82bacf");
  ellipse(x, y + 44, 30, 30, "#111b30");
  icon("lock", x, y + 40, 0.82, failed ? colors.red : colors.gold);
  box(x - 145, y - 148, 290, 39, "#12243b", failed ? colors.red : "#5d7e9f", 8);
  text("QUEST: SEND REPORT", x, y - 121, 20, colors.white, 700, "center", true);
  text(failed ? "EMAIL TOOL MISSING" : "DELIVERY GATE", x, y + 135, 19, failed ? colors.red : colors.muted, 700, "center", true);
  if (t >= 7.88) {
    const reveal = smooth((t - 7.88) / 0.2);
    ctx.save(); ctx.globalAlpha = reveal;
    box(x - 112, y - 65, 224, 43, "#451e33", colors.red, 6);
    text("ACCESS IMPOSSIBLE", x, y - 36, 19, colors.red, 800, "center", true);
    ctx.restore();
  }
}

function bubble(x, y, value, color, failed = false) {
  ctx.font = '700 19px "Cascadia Code", Consolas, monospace';
  const w = Math.max(66, ctx.measureText(value).width + 26);
  box(x - w / 2, y - 34, w, 36, failed ? "#3d1d32" : "#0e1c30", color, 9);
  path([[x - 7, y + 2], [x, y + 10], [x + 7, y + 2]], failed ? "#3d1d32" : "#0e1c30", 1, true, true);
  text(value, x, y - 9, 19, color, 700, "center", true);
}

function robot(bot, p, i, t) {
  const { x, y, failed, running } = p;
  const waiting = t >= 5 && t < 6;
  const local = t - p.failAt;
  const shock = failed ? Math.sin(clamp(local / 0.35) * Math.PI) * 24 : 0;
  const slump = failed ? smooth((local - 0.23) / 0.5) : 0;
  const cycle = t * 19 + i * 1.7;
  const stride = running ? Math.sin(cycle) * 16 : 0;
  const bounce = running ? Math.abs(Math.cos(cycle)) * 8 : failed ? 0 : Math.sin(t * 4 + i) * 2;
  ellipse(x, y + 5, 42, 13, "#050c1880");
  ellipse(x, y + 5, 32, 8, `${bot.color}25`);

  if (running) {
    for (let j = 0; j < 3; j++) {
      const f = (t * 3 + j / 3 + i * 0.1) % 1;
      ctx.save(); ctx.globalAlpha = (1 - f) * 0.3;
      ellipse(x - p.dir * (25 + f * 60), y + 4 - f * 10, 4 + f * 9, 3 + f * 3, "#b7c9dc");
      ctx.restore();
    }
  }
  ctx.save(); ctx.translate(x, y - bounce - shock + slump * 6);
  ctx.rotate(failed ? -0.1 * slump : running ? 0.075 * p.dir : 0);
  const dark = "#172038";
  path([[-15, -22], [-16 + stride, -3]], dark, 13);
  path([[15, -22], [16 - stride, -3]], dark, 13);
  box(-28 + stride, -9, 25, 14, bot.color, "#0d1628", 5);
  box(4 - stride, -9, 25, 14, bot.color, "#0d1628", 5);
  const arm = failed ? 16 : running ? stride * 0.65 : waiting ? 7 : -8 + Math.sin(t * 16) * 7;
  path([[-28, -56], [-42, -41 + arm]], bot.color, 12);
  path([[28, -56], [42, -41 - (failed ? -16 : arm)]], bot.color, 12);
  ellipse(-42, -41 + arm, 8, 8, "#e5efff");
  ellipse(42, -41 - (failed ? -16 : arm), 8, 8, "#e5efff");
  box(-28, -67, 56, 46, bot.color, "#0e192c", 13);
  box(-14, -49, 28, 18, "#1b3049", null, 5);
  if (failed) cross(0, -40, 4, colors.red, 3);
  else { ellipse(-5, -40, 3, 3, colors.white); ellipse(5, -40, 3, 3, colors.white); }

  ctx.save(); ctx.translate(0, slump * 8);
  path([[0, -112], [0, -126]], "#8ea8c7", 4);
  ellipse(0, -129, 6, 6, failed ? colors.red : bot.color);
  box(-37, -110, 74, 51, bot.color, "#0a172b", 16);
  box(-28, -99, 56, 28, "#111c31", null, 10);
  if (failed) {
    cross(-13, -86, 4, colors.red, 3);
    cross(13, -86, 4, colors.red, 3);
    path([[-6, -76], [0, -79], [6, -76]], colors.red, 2);
  } else if (waiting) {
    path([[-19, -85], [-9, -85]], colors.gold, 3);
    path([[9, -85], [19, -85]], colors.gold, 3);
  } else {
    const blink = (t * 0.7 + i * 0.19) % 1 > 0.96;
    box(-19 + p.dir * 2, -91, 8, blink ? 3 : 12, colors.white, null, 3);
    box(9 + p.dir * 2, -91, 8, blink ? 3 : 12, colors.white, null, 3);
  }
  ctx.restore();

  if (!failed && !waiting) {
    ctx.save(); ctx.translate(42, -42 - arm); ctx.rotate(0.18);
    box(-9, -19, 25, 31, "#e4effa", "#8aa9c9", 3);
    path([[-3, -10], [9, -10]], "#468295", 2);
    path([[-3, -3], [9, -3]], "#468295", 2);
    ctx.restore();
  }
  ctx.restore();
  text(bot.name, x, y + 32, 17, failed ? "#c195a8" : bot.color, 700, "center", true);
  if (failed) {
    bubble(x, y - 126 - shock, "FAILED", colors.red, true);
    if (local < 0.45) {
      for (let ray = 0; ray < 5; ray++) {
        const a = Math.PI + ray * Math.PI / 4;
        path([[x + Math.cos(a) * 48, y - 98 + Math.sin(a) * 48],
          [x + Math.cos(a) * 61, y - 98 + Math.sin(a) * 61]], colors.gold, 3);
      }
    }
  } else if (waiting) {
    bubble(x, y - 153, ".".repeat(1 + Math.floor((t * 4 + i) % 3)), colors.gold);
  } else {
    const actions = t >= 7 ? ["SEND!", "GO!", "SHIP!", "SEND!", "GO!", "SHIP!"]
      : t >= 6 ? ["NEW PLAN", "REROUTE", "PATCH", "RECHECK", "REROUTE", "TRY AGAIN"]
      : t >= 4 ? ["RETRY", "RETRY", "RETRY", "RETRY", "RETRY", "RETRY"]
      : ["PLAN", "SEARCH", "BUILD", "CHECK", "FETCH", "DELIVER"];
    bubble(x, y - 153 - bounce, actions[i], bot.color);
  }
}

function hud(s) {
  text("SkillC", 88, 65, 29, colors.cyan, 800);
  text("/ THE IMPOSSIBLE QUEST", 197, 65, 19, colors.muted, 700, "left", true);
  text("ORIGINAL GAME ANIMATION", 1832, 64, 17, colors.muted, 600, "right", true);
  text(s.phase.heading, 88, 143, 53, s.failed ? colors.red : colors.white, 750);
  const y = 176;
  box(88, y, 419, 57, "#162740", "#334b69", 12);
  ellipse(115, y + 28, 6, 6, s.phase.color);
  text(s.failed ? "6 / 6 AGENTS FAILED" : s.waiting ? "6 AGENTS WAITING" : "6 AGENTS ON THE MOVE", 136, y + 36, 21, s.phase.color, 700, "left", true);
  box(523, y, 475, 57, "#162740", "#334b69", 12);
  ellipse(553, y + 28, 12, 12, colors.gold);
  text("T", 553, y + 34, 16, "#593d28", 800, "center");
  text("TOKENS SPENT", 577, y + 35, 19, colors.muted, 600, "left", true);
  text(s.tokens.toLocaleString("en-US"), 973, y + 38, 31, s.failed ? colors.red : colors.gold, 800, "right", true);
  box(1014, y, 302, 57, "#162740", "#334b69", 12);
  text("GOALS REACHED", 1034, y + 35, 18, colors.muted, 600, "left", true);
  text("0 / 1", 1296, y + 37, 28, s.failed ? colors.red : colors.white, 700, "right", true);
  box(1332, y, 500, 57, "#162740", s.failed ? "#b1526c" : "#334b69", 12);
  text(s.phase.label, 1582, y + 36, 22, s.phase.color, 700, "center", true);
}

function renderFrame(seconds) {
  const s = stateAt(seconds);
  const { t, failed } = s;
  const background = ctx.createLinearGradient(0, 0, 1920, 1080);
  background.addColorStop(0, "#090f21"); background.addColorStop(1, "#12253b");
  ctx.fillStyle = background; ctx.fillRect(0, 0, 1920, 1080);
  const glow = ctx.createRadialGradient(980, 565, 30, 980, 565, 1040);
  glow.addColorStop(0, failed ? "#87334a28" : "#4d99b41b"); glow.addColorStop(1, "#00000000");
  ctx.fillStyle = glow; ctx.fillRect(0, 0, 1920, 1080);
  hud(s);
  ctx.save();
  if (t >= 8.15 && t < 8.4) {
    const decay = 1 - (t - 8.15) / 0.25;
    ctx.translate(Math.sin(t * 95) * 5 * decay, Math.cos(t * 70) * 3 * decay);
  }
  floor(t, failed);
  const stations = [
    { x: 320, y: 422, label: "01 / PLAN", type: "plan", color: bots[0].color },
    { x: 755, y: 386, label: "02 / SEARCH", type: "search", color: bots[1].color },
    { x: 1110, y: 423, label: "04 / CHECK", type: "check", color: bots[3].color },
    { x: 300, y: 710, label: "03 / BUILD", type: "build", color: bots[2].color }
  ];
  // Painter's order keeps characters behind or in front of each workstation.
  const objects = stations.map(st => ({ depth: st.y, draw: () => station(st.x, st.y, st.label, st.type, st.color, t, failed) }));
  objects.push({ depth: 521, draw: () => goal(t, failed) });
  s.agents.forEach((p, i) => objects.push({ depth: p.y, draw: () => robot(bots[i], p, i, t) }));
  objects.sort((a, b) => a.depth - b.depth).forEach(object => object.draw());
  if (t >= 8.15) {
    const f = smooth((t - 8.15) / 0.35);
    ctx.save(); ctx.globalAlpha = f;
    const y = 453 - (1 - f) * 18;
    box(479, y, 929, 88, "#250f24", "#ff7188", 16);
    cross(519, y + 31, 9, colors.red, 5);
    text("QUEST FAILED", 554, y + 40, 38, colors.red, 850, "left", true);
    text("No email tool. No route to the goal.", 554, y + 74, 23, "#e2b9c9", 500);
    ctx.restore();
  }
  ctx.restore();
  text("ILLUSTRATION / FICTIONAL TOKEN COUNTS", 88, 1034, 16, colors.muted, 500, "left", true);
  text("6 AGENTS   /   1 IMPOSSIBLE GOAL", 1832, 1034, 16, colors.muted, 500, "right", true);
  return s;
}

const play = document.getElementById("play");
const scrub = document.getElementById("scrub");
const output = document.getElementById("time");
let current = 0;
let playing = false;
let started = 0;
let request;
function show(t) {
  current = clamp(t, 0, 10);
  renderFrame(current);
  scrub.value = String(current);
  output.textContent = `${current.toFixed(2)} / 10.00 s`;
}
function pause() {
  playing = false; cancelAnimationFrame(request); play.textContent = "Play";
}
function tick(now) {
  show((now - started) / 1000);
  if (current >= 10) pause();
  else request = requestAnimationFrame(tick);
}
function start() {
  pause();
  if (current >= 10) current = 0;
  started = performance.now() - current * 1000;
  playing = true; play.textContent = "Pause";
  request = requestAnimationFrame(tick);
}
play.addEventListener("click", () => playing ? pause() : start());
document.getElementById("replay").addEventListener("click", () => { show(0); start(); });
scrub.addEventListener("input", () => { pause(); show(Number(scrub.value)); });
window.animation = { renderFrame, stateAt, duration: 10, width: 1920, height: 1080 };
show(0);
if (!new URLSearchParams(location.search).has("render") && !matchMedia("(prefers-reduced-motion: reduce)").matches) start();
