/* global window, document, location, matchMedia, performance, requestAnimationFrame, cancelAnimationFrame */
"use strict";

const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
const evidence = window.MEETING_TERMINAL_EVIDENCE;
if (!evidence || evidence.verdict.verdict !== "IMPOSSIBLE" ||
    evidence.verdict.reason !== "GOAL_UNSAT" || evidence.exitCode !== 1) {
  throw new Error("Missing or unexpected checker evidence. Run capture-meeting-terminal.mjs first.");
}
const duration = 18;
const C = {
  white: "#eef5ff", muted: "#9eafc7", cyan: "#65ddeb", purple: "#c4a6fa",
  green: "#8ce2b8", red: "#ff7b94", gold: "#ffd285", edge: "#334a66"
};
const clamp = (n, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, n));
const ease = n => 1 - (1 - clamp(n)) ** 3;
const verdict = evidence.verdict;
const terminalExcerpt = JSON.stringify({
  verdict: verdict.verdict,
  reason: verdict.reason,
  frontier: verdict.frontier,
  refuted: verdict.refuted,
  unknown: verdict.unknown
}, null, 2);
const terminalLines = terminalExcerpt.split("\n");
function stateAt(seconds) {
  if (!Number.isFinite(seconds)) throw new TypeError("Frame time must be finite.");
  const t = clamp(seconds, 0, duration);
  return {
    t, phase: t < 5 ? "PACK" : t < 9 ? "CLOSURE" : t < 12.8 ? "PROOF" : "REFUTED",
    verdict: t >= 8.6 ? verdict.verdict : null,
    reason: t >= 8.95 ? verdict.reason : null,
    frontier: t >= 9.65 ? verdict.frontier : [],
    exitCode: t >= 12.8 ? evidence.exitCode : null,
    outputLines: clamp(Math.floor((t - 8.25) / 0.35) + 1, 0, terminalLines.length),
    explanation: "No declared capability establishes invited_all.",
    sourceMode: t < 5 ? "pack" : t < 9 ? "closure" : "refutation"
  };
}
function text(value, x, y, size = 24, color = C.white, weight = 500, mono = false, align = "left") {
  ctx.font = `${weight} ${size}px ${mono ? '"Cascadia Code", Consolas, monospace' : '"Segoe UI", Arial, sans-serif'}`;
  ctx.textAlign = align; ctx.fillStyle = color; ctx.fillText(value, x, y);
}
function box(x, y, w, h, fill, stroke, radius = 12) {
  ctx.beginPath(); ctx.roundRect(x, y, w, h, radius);
  ctx.fillStyle = fill; ctx.fill();
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1.5; ctx.stroke(); }
}
function dot(x, y, r, color) {
  ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
}
function line(x1, y1, x2, y2, color, width = 2) {
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2);
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.stroke();
}
function wrap(value, maxWidth, size, mono = false) {
  ctx.font = `400 ${size}px ${mono ? '"Cascadia Code", Consolas, monospace' : '"Segoe UI", Arial, sans-serif'}`;
  const result = [];
  let current = "";
  for (const word of value.split(" ")) {
    const next = current ? `${current} ${word}` : word;
    if (ctx.measureText(next).width > maxWidth && current) { result.push(current); current = word; }
    else current = next;
  }
  if (current) result.push(current);
  return result;
}
function code(value, x, y, size) {
  const parts = value.split(/("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:def|for|in|return|if|else|True|False|None|true|false)\b)/g);
  ctx.font = `500 ${size}px "Cascadia Code", Consolas, monospace`;
  let cursor = x;
  for (const part of parts) {
    const color = /^["']/.test(part) ? C.green
      : /^(def|for|in|return|if|else|True|False|None|true|false)$/.test(part) ? C.purple : "#d3dfef";
    text(part, cursor, y, size, color, 500, true);
    cursor += ctx.measureText(part).width;
  }
}
function editor(s) {
  const x = 88, y = 238, w = 938, h = 597;
  box(x, y, w, h, "#0d182a", C.edge, 16);
  const mode = s.sourceMode;
  const tab = mode === "pack" ? "meeting-mailbox.pack.json" : "src / skillc / checker.py";
  text(tab, x + 28, y + 34, 21, C.white, 600, true);
  text(mode === "pack" ? "INPUT" : "SOURCE EXCERPT", x + w - 23, y + 34, 16, C.cyan, 700, true, "right");
  line(x, y + 53, x + w, y + 53, C.edge);
  const rows = mode === "pack"
    ? evidence.packSource.trimEnd().split(/\r?\n/).map((text, i) => ({ text, number: i + 1 }))
    : mode === "closure" ? evidence.closure : evidence.refutation;
  const fontSize = mode === "pack" ? 22 : mode === "closure" ? 25 : 20;
  const rowHeight = mode === "pack" ? 24 : mode === "closure" ? 43 : 28;
  const startY = y + 84;
  rows.forEach((row, i) => {
    const value = mode === "refutation" ? row.text.replace(/^ {8}/, "") : row.text;
    const active = mode === "pack"
      ? (s.t < 1.8 ? value.includes('"goal"') : s.t < 3.6 ? value.includes('"add"') : value.includes('"init_true"'))
      : mode === "closure"
        ? (s.t < 6.4 ? value.includes("init_true") : s.t < 7.8 ? value.includes("c.add") : value.includes("return"))
        : (s.t < 10.2 ? value.includes("z3.Bool(f)") : s.t < 11.5 ? value.includes("z3.And") : value.includes("GOAL_UNSAT") || value.includes("frontier="));
    if (active) {
      box(x + 10, startY + i * rowHeight - fontSize, w - 20, rowHeight, "#203448", null, 3);
      box(x + 10, startY + i * rowHeight - fontSize, 3, rowHeight, C.cyan, null, 1);
    }
    text(String(row.number).padStart(3), x + 61, startY + i * rowHeight, 17, active ? C.cyan : "#647c98", 400, true, "right");
    code(value, x + 83, startY + i * rowHeight, fontSize);
  });
  if (mode !== "pack") {
    const ey = mode === "closure" ? 590 : 618;
    box(x + 24, ey, w - 48, 192 - (ey - 590), "#102a36", "#355e6b", 12);
    text("EXPLANATION / THIS PACK", x + 45, ey + 30, 16, C.cyan, 700, true);
    if (mode === "closure") {
      text("Initially true:  { }", x + 45, ey + 70, 25, C.white, 500, true);
      text("Capability adds: { scheduled }", x + 45, ey + 112, 25, C.green, 500, true);
      text("invited_all has no establisher.", x + 45, ey + 153, 26, C.red, 650);
    } else {
      text("invited_all  ->  False", x + 45, ey + 73, 27, C.red, 650, true);
      text("scheduled AND False  ->  UNSAT", x + 45, ey + 121, 28, C.white, 650, true);
    }
    text("Original source lines shown; intervening lines omitted.", x + 27, 815, 16, C.muted, 400);
  }
}
function terminal(s) {
  const x = 1050, y = 238, w = 782;
  box(x, y, w, 597, "#080f1b", C.edge, 16);
  dot(x + 26, y + 27, 5, "#ff7b94"); dot(x + 44, y + 27, 5, "#ffd285"); dot(x + 62, y + 27, 5, "#8ce2b8");
  text("TERMINAL", x + 83, y + 34, 20, C.white, 600, true);
  text("CAPTURED OUTPUT", x + w - 24, y + 34, 16, C.green, 650, true, "right");
  line(x, y + 53, x + w, y + 53, C.edge);
  text("PS docs\\videos>", x + 25, y + 87, 18, C.cyan, 500, true);
  const command = evidence.command;
  const typed = command.slice(0, Math.floor(clamp((s.t - 0.6) / 1.8) * command.length));
  text(typed, x + 25, y + 120, 18, C.white, 500, true);
  if (s.t < 8.2 && Math.floor(s.t * 2) % 2 === 0) {
    ctx.font = '500 18px "Cascadia Code", Consolas, monospace';
    box(x + 28 + ctx.measureText(typed).width, y + 104, 8, 19, C.cyan, null, 0);
  }
  if (s.t < 8.2) {
    text("Inspect the pack and checker before Enter.", x + 28, y + 219, 25, C.muted, 400);
    text("The meeting agent is not being run.", x + 28, y + 260, 24, C.muted, 400);
    box(x + 25, 750, w - 50, 55, "#142438", C.edge, 9);
    text("CODE WALKTHROUGH / OUTPUT PENDING", x + w / 2, 785, 19, C.cyan, 650, true, "center");
    return;
  }
  text("--json excerpt / other fields omitted", x + 25, y + 166, 16, C.muted, 400, true);
  for (let i = 0; i < s.outputLines; i++) {
    const row = terminalLines[i];
    const emphasized = /IMPOSSIBLE|GOAL_UNSAT|invited_all/.test(row);
    if (emphasized) box(x + 18, y + 187 + i * 27, w - 36, 27, "#2a1b2c", null, 2);
    text(row, x + 29, y + 208 + i * 27, 22, emphasized ? C.red : "#d0def0", emphasized ? 650 : 400, true);
  }
  if (s.t >= 11.6) {
    const f = ease((s.t - 11.6) / 0.3);
    ctx.save(); ctx.globalAlpha = f;
    text("CHECKER DETAIL (verbatim, wrapped)", x + 25, 709, 15, C.muted, 600, true);
    const detail = wrap(verdict.detail, w - 52, 16);
    detail.forEach((row, i) => text(row, x + 25, 733 + i * 21, 16, "#b8cadd", 400));
    ctx.restore();
  }
}
function renderFrame(seconds) {
  const s = stateAt(seconds);
  const bg = ctx.createLinearGradient(0, 0, 1920, 1080);
  bg.addColorStop(0, "#090f20"); bg.addColorStop(1, "#14293e");
  ctx.fillStyle = bg; ctx.fillRect(0, 0, 1920, 1080);
  text("SkillC", 88, 69, 33, C.cyan, 800);
  text("/ THE CODE BEHIND THE VERDICT", 211, 67, 19, C.muted, 650, true);
  box(1415, 36, 417, 44, "#143333", "#438d78", 8);
  text("REAL CHECKER / DEMO INPUT", 1623, 65, 19, C.green, 700, true, "center");
  const title = s.t < 5 ? "The goal is written in code."
    : s.t < 9 ? "What can this mailbox make true?"
    : s.t < 12.8 ? "No invitation capability. No satisfying goal." : "IMPOSSIBLE. The blocker is explicit.";
  text(title, 88, 155, s.t >= 9 && s.t < 12.8 ? 52 : 57, s.t >= 12.8 ? C.green : C.white, 750);
  const subtitle = s.t < 5 ? "A hand-authored formal pack, checked by the actual local SkillC CLI."
    : s.t < 9 ? "The checker collects predicates that are initially true or added by declared capabilities."
    : s.t < 12.8 ? "An unestablishable predicate is false even in the permissive goal model."
    : "GOAL_UNSAT / frontier: invited_all / process exit code: 1";
  text(subtitle, 91, 204, 24, C.muted, 400);
  editor(s);
  terminal(s);
  if (s.t >= 12.8) {
    box(88, 859, 1744, 76, "#17312e", "#4b9880", 12);
    text("EXIT 1", 119, 908, 28, C.red, 750, true);
    line(267, 875, 267, 919, "#4b7668");
    text("IMPOSSIBLE [GOAL_UNSAT]", 301, 908, 29, C.white, 700, true);
    text("frontier: invited_all", 1786, 908, 29, C.green, 650, true, "right");
  }
  const steps = [[0, 5, "FORMAL PACK"], [5, 9, "CHECKER SOURCE"], [9, 12.8, "REAL CLI OUTPUT"], [12.8, 18, "REFUTATION"]];
  for (const [start, end, label] of steps) {
    const x = 88 + start / duration * 1744, w = (end - start) / duration * 1744 - 10;
    box(x, 968, w, 4, "#29425c", null, 2);
    if (s.t > start) box(x, 968, Math.max(1, w * clamp((s.t - start) / (end - start))), 4, C.cyan, null, 2);
    text(label, x, 1002, 16, s.t >= start && s.t < end ? C.white : C.muted, 650, true);
  }
  text("ACTUAL LOCAL OUTPUT / HAND-AUTHORED PACK / NOT A LIVE MAILBOX PROBE", 88, 1047, 15, C.muted, 500, true);
  text("EDITED TIMING FOR EXPLANATION", 1832, 1047, 15, C.muted, 500, true, "right");
  return s;
}

const play = document.getElementById("play"), scrub = document.getElementById("scrub"), output = document.getElementById("time");
let current = 0, playing = false, started = 0, request;
function show(t) {
  current = clamp(t, 0, duration); renderFrame(current); scrub.value = String(current);
  output.textContent = `${current.toFixed(2)} / ${duration.toFixed(2)} s`;
}
function pause() { playing = false; cancelAnimationFrame(request); play.textContent = "Play"; }
function tick(now) {
  show((now - started) / 1000);
  if (current >= duration) pause();
  else request = requestAnimationFrame(tick);
}
function start() {
  pause(); if (current >= duration) current = 0;
  started = performance.now() - current * 1000; playing = true; play.textContent = "Pause";
  request = requestAnimationFrame(tick);
}
play.addEventListener("click", () => playing ? pause() : start());
document.getElementById("replay").addEventListener("click", () => { show(0); start(); });
scrub.addEventListener("input", () => { pause(); show(Number(scrub.value)); });
window.animation = { renderFrame, stateAt, duration, width: 1920, height: 1080, terminalExcerpt };
show(0);
if (!new URLSearchParams(location.search).has("render") && !matchMedia("(prefers-reduced-motion: reduce)").matches) start();
