/* global window, document, location, matchMedia, performance, requestAnimationFrame, cancelAnimationFrame */
"use strict";

const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
const duration = 12;
const skills = Object.freeze([
  { name: "PDF", runs: 4, compaction: 22011, runtime: 157454, evidence: "M" },
  { name: "XLSX", runs: 4, compaction: 32028, runtime: 209766, evidence: "M" },
  { name: "DOCX", runs: 4, compaction: 22024, runtime: 121589, evidence: "E" },
  { name: "Bulk RNA-seq", runs: 4, compaction: 26596, runtime: 2474309, evidence: "E" },
  { name: "Data-quality auditor", runs: 2, compaction: 23310, runtime: 1067664, evidence: "E" },
  { name: "Google Workspace CLI", runs: 4, compaction: 25099, runtime: 3641064, evidence: "E" },
  { name: "Kubernetes operator", runs: 4, compaction: 24569, runtime: 3951603, evidence: "E" },
  { name: "Writing skills", runs: 4, compaction: 33558, runtime: 3149738, evidence: "E" }
].map(row => Object.freeze({
  ...row,
  saved: row.runtime - row.compaction,
  ratio: row.compaction / row.runtime,
  reduction: ((1 - row.compaction / row.runtime) * 100).toFixed(2)
})));
const totals = Object.freeze(skills.reduce((sum, row) => ({
  runs: sum.runs + row.runs,
  runtime: sum.runtime + row.runtime,
  compaction: sum.compaction + row.compaction,
  saved: sum.saved + row.saved,
  measured: sum.measured + (row.evidence === "M" ? row.compaction : 0),
  estimated: sum.estimated + (row.evidence === "E" ? row.compaction : 0)
}), { runs: 0, runtime: 0, compaction: 0, saved: 0, measured: 0, estimated: 0 }));
const reduction = ((1 - totals.compaction / totals.runtime) * 100).toFixed(2);
const number = n => n.toLocaleString("en-US");
const clamp = (n, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, n));
const ease = n => 1 - (1 - clamp(n)) ** 3;

function stateAt(seconds) {
  if (!Number.isFinite(seconds)) throw new TypeError("Frame time must be finite.");
  return { t: clamp(seconds, 0, duration), skills, totals, reduction };
}
function text(value, x, y, size, color = "#eef7ff", weight = 600, align = "left") {
  ctx.font = `${weight} ${size}px "Segoe UI", Arial, sans-serif`;
  ctx.textAlign = align;
  ctx.fillStyle = color;
  ctx.fillText(value, x, y);
}
function renderFrame(seconds) {
  const s = stateAt(seconds);
  const background = ctx.createLinearGradient(0, 0, 1920, 1080);
  background.addColorStop(0, "#081322");
  background.addColorStop(1, "#142c37");
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, 1920, 1080);
  text("SkillC / Savings by skill", 80, 90, 54, "#eef7ff", 750);
  text(`${totals.runs} unsuccessful agent runs / ${skills.length} skill categories`, 80, 145, 34, "#c0d3df");
  text(`${reduction}%`, 1840, 100, 88, "#8ce4b7", 800, "right");
  text("TOTAL TOKENS SAVED", 1840, 145, 30, "#8ce4b7", 650, "right");

  text("SKILL", 80, 223, 28, "#c0d3df");
  text("RUNS", 565, 223, 28, "#c0d3df", 600, "center");
  text("WITHOUT SkillC", 900, 217, 28, "#f5ac9c", 700, "right");
  text("Runtime tokens", 900, 254, 28, "#c0d3df", 500, "right");
  text("WITH SkillC", 1230, 217, 28, "#8ce4b7", 700, "right");
  text("Compaction tokens", 1230, 254, 28, "#c0d3df", 500, "right");
  text("TOKENS SAVED (%)", 1840, 223, 28, "#8ce4b7", 700, "right");
  skills.forEach((row, i) => {
    const y = 312 + i * 71;
    text(row.name, 80, y, 32);
    text(String(row.runs), 565, y, 34, "#c0d3df", 600, "center");
    text(number(row.runtime), 900, y, 34, "#f5ac9c", 650, "right");
    text(number(row.compaction), 1230, y, 32, "#8ce4b7", 650, "right");
    ctx.fillStyle = "#314858";
    ctx.fillRect(1290, y - 28, 320, 34);
    const reveal = ease((s.t - i * 0.12) / 0.9);
    ctx.fillStyle = "#8ce4b7";
    ctx.fillRect(1290, y - 28, 320 * (1 - row.ratio) * reveal, 34);
    text(`${row.reduction}%`, 1840, y + 3, 40, "#8ce4b7", 750, "right");
    ctx.fillStyle = "#263e4a";
    ctx.fillRect(80, y + 24, 1760, 1);
  });
  ctx.fillStyle = "#1c3541";
  ctx.beginPath();
  ctx.roundRect(64, 879, 1792, 126, 16);
  ctx.fill();
  text(`${number(totals.runtime)} runtime tokens  ->  ${number(totals.compaction)} compaction tokens`,
    960, 931, 40, "#eef7ff", 700, "center");
  text(`${number(totals.saved)} tokens saved`, 960, 979, 34, "#8ce4b7", 650, "center");
  text("PDF/XLSX compaction measured; other compaction estimated. All runtime measured.",
    960, 1050, 28, "#c0d3df", 500, "center");
  return s;
}

const play = document.getElementById("play");
const scrub = document.getElementById("scrub");
const output = document.getElementById("time");
let current = 0, playing = false, started = 0, request;
function show(t) {
  current = clamp(t, 0, duration);
  renderFrame(current);
  scrub.value = String(current);
  output.textContent = `${current.toFixed(2)} / ${duration.toFixed(2)} s`;
}
function pause() {
  playing = false;
  cancelAnimationFrame(request);
  play.textContent = "Play";
}
function tick(now) {
  show((now - started) / 1000);
  if (current >= duration) pause();
  else request = requestAnimationFrame(tick);
}
function start() {
  pause();
  if (current >= duration) current = 0;
  started = performance.now() - current * 1000;
  playing = true;
  play.textContent = "Pause";
  request = requestAnimationFrame(tick);
}
play.addEventListener("click", () => playing ? pause() : start());
document.getElementById("replay").addEventListener("click", () => { show(0); start(); });
scrub.addEventListener("input", () => { pause(); show(Number(scrub.value)); });
window.animation = { renderFrame, stateAt, duration, width: 1920, height: 1080 };
show(0);
if (!new URLSearchParams(location.search).has("render") && !matchMedia("(prefers-reduced-motion: reduce)").matches) start();
