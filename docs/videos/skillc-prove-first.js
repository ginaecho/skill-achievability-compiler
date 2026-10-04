/* global window, document, location, matchMedia, performance, requestAnimationFrame, cancelAnimationFrame */
"use strict";

const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
const logo = document.getElementById("microsoft-logo");
const duration = 10;
const colors = {
  ink: "#173c46", muted: "#526e73", green: "#157967", mint: "#adedd3",
  pink: "#f6acb3", peach: "#ffddbe", paper: "#fffefb", yellow: "#f8c95d"
};
const clamp = n => Math.max(0, Math.min(1, n));
const smooth = n => { const x = clamp(n); return x * x * (3 - 2 * x); };
const mix = (a, b, n) => a + (b - a) * n;

function stateAt(seconds) {
  if (!Number.isFinite(seconds)) throw new TypeError("Frame time must be finite.");
  const t = Math.max(0, Math.min(duration, seconds));
  const proved = t >= 6;
  return {
    t, phase: t < 2 ? "PAUSE" : proved ? "PROCEED" : "PROVE",
    checked: [t >= 3, t >= 4.2, proved], proved,
    runnerX: t < 2 ? mix(250, 520, smooth(t / 1.6))
      : proved ? mix(520, 740, smooth((t - 6.5) / 1.8)) : 520,
    headline: "Don't run first, prove first",
    moving: t < 1.6 || (t > 6.5 && t < 8.3),
    admitted: proved
  };
}
function text(value, x, y, size, color = colors.ink, weight = 600, align = "left") {
  ctx.font = `${weight} ${size}px "Segoe UI", Arial, sans-serif`;
  ctx.textAlign = align; ctx.fillStyle = color; ctx.fillText(value, x, y);
}
function box(x, y, w, h, fill, radius = 24, stroke) {
  ctx.beginPath(); ctx.roundRect(x, y, w, h, radius);
  ctx.fillStyle = fill; ctx.fill();
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 3; ctx.stroke(); }
}
function ellipse(x, y, rx, ry, color) {
  ctx.beginPath(); ctx.ellipse(x, y, rx, ry, 0, 0, Math.PI * 2);
  ctx.fillStyle = color; ctx.fill();
}
function line(points, color, width = 6) {
  ctx.beginPath();
  points.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y));
  ctx.lineWidth = width; ctx.strokeStyle = color; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.stroke();
}
function check(x, y, size, color = colors.green) {
  line([[x - size * .6, y], [x - size * .15, y + size * .45], [x + size * .65, y - size * .55]], color, size * .2);
}
function sparkle(x, y, size, color, rotation = 0) {
  ctx.save(); ctx.translate(x, y); ctx.rotate(rotation);
  ctx.beginPath(); ctx.moveTo(0, -size);
  ctx.quadraticCurveTo(size * .2, -size * .2, size, 0);
  ctx.quadraticCurveTo(size * .2, size * .2, 0, size);
  ctx.quadraticCurveTo(-size * .2, size * .2, -size, 0);
  ctx.quadraticCurveTo(-size * .2, -size * .2, 0, -size);
  ctx.fillStyle = color; ctx.fill(); ctx.restore();
}
function shield(s) {
  const bob = Math.sin(s.t * 2.4) * 9;
  const lift = s.proved ? Math.sin(clamp((s.t - 6) / .9) * Math.PI) * 24 : 0;
  ellipse(1430, 787, 189, 27, "#2d74651a");
  ctx.save(); ctx.translate(1430, 561 + bob - lift);
  const wave = Math.sin(s.t * 7) * (s.proved ? 16 : 6);
  line([[-124, 51], [-176, 64], [-190, 24]], colors.green, 24);
  ellipse(-190, 19, 25, 26, colors.mint);
  line([[131, 30], [185, -12], [203, -60 + wave]], colors.green, 24);
  ellipse(203, -65 + wave, 28, 29, colors.mint);
  line([[-65, 158], [-73, 204]], colors.green, 24);
  line([[65, 158], [76, 204]], colors.green, 24);
  ellipse(-82, 208, 39, 20, colors.ink); ellipse(87, 208, 39, 20, colors.ink);
  const fill = ctx.createLinearGradient(-140, -190, 140, 190);
  fill.addColorStop(0, "#ceffe7"); fill.addColorStop(1, "#69cea6");
  ctx.save(); ctx.shadowColor = "#23795d25"; ctx.shadowBlur = 35; ctx.shadowOffsetY = 14;
  ctx.beginPath(); ctx.moveTo(0, -202);
  ctx.bezierCurveTo(46, -168, 108, -155, 154, -143);
  ctx.lineTo(148, 12);
  ctx.bezierCurveTo(145, 103, 83, 164, 0, 201);
  ctx.bezierCurveTo(-83, 164, -145, 103, -148, 12);
  ctx.lineTo(-154, -143);
  ctx.bezierCurveTo(-108, -155, -46, -168, 0, -202);
  ctx.closePath(); ctx.fillStyle = fill; ctx.fill();
  ctx.strokeStyle = colors.green; ctx.lineWidth = 7; ctx.stroke(); ctx.restore();
  line([[-120, -126], [-116, -52]], "#ffffffab", 8);
  const blink = s.t % 3.7 > 3.52;
  if (s.proved || blink) {
    for (const x of [-52, 52]) {
      ctx.beginPath(); ctx.arc(x, -15, 16, Math.PI * 1.13, Math.PI * 1.87);
      ctx.strokeStyle = colors.ink; ctx.lineWidth = 8; ctx.stroke();
    }
  } else {
    ellipse(-52, -24, 12, 20, colors.ink); ellipse(52, -24, 12, 20, colors.ink);
    ellipse(-49, -31, 4, 6, "#fff"); ellipse(55, -31, 4, 6, "#fff");
  }
  ellipse(-86, 16, 24, 12, colors.pink); ellipse(86, 16, 24, 12, colors.pink);
  ctx.beginPath(); ctx.arc(0, 5, 28, .15 * Math.PI, .85 * Math.PI);
  ctx.strokeStyle = colors.ink; ctx.lineWidth = 6; ctx.stroke();
  box(-77, 76, 154, 48, "#ffffffbb", 24);
  text("SkillC", 0, 109, 31, colors.green, 800, "center");
  check(0, -119, 35);
  ctx.restore();
}
function runner(s) {
  const step = s.moving ? Math.sin(s.t * 19) : 0;
  const bounce = s.moving ? Math.abs(step) * 10 : Math.sin(s.t * 2) * 3;
  ellipse(s.runnerX, 776, 79, 13, "#173c4615");
  ctx.save(); ctx.translate(s.runnerX, 690 - bounce);
  line([[-28, 45], [-34 - step * 16, 70]], colors.ink, 14);
  line([[28, 45], [34 + step * 16, 70]], colors.ink, 14);
  box(-61 - step * 16, 65, 46, 18, colors.ink, 9);
  box(17 + step * 16, 65, 46, 18, colors.ink, 9);
  line([[-49, 0], [-75, 20 + step * 15]], colors.ink, 13);
  line([[49, 0], [74, 6 - step * 15]], colors.ink, 13);
  ellipse(-75, 20 + step * 15, 13, 14, colors.peach);
  ellipse(74, 6 - step * 15, 13, 14, colors.peach);
  box(-43, -12, 86, 65, colors.peach, 24, colors.ink);
  ctx.save(); ctx.rotate(s.phase === "PROVE" ? -.07 : step * .035);
  box(-67, -106, 134, 104, colors.peach, 31, colors.ink);
  box(-53, -88, 106, 64, colors.ink, 22);
  ellipse(-21, -59, 7, 11, "#fffefb"); ellipse(21, -59, 7, 11, "#fffefb");
  ctx.beginPath(); ctx.arc(0, -52, 13, .15 * Math.PI, .85 * Math.PI);
  ctx.strokeStyle = "#fffefb"; ctx.lineWidth = 3; ctx.stroke();
  line([[0, -107], [0, -126]], colors.ink, 6);
  ellipse(0, -132, 10, 10, s.proved ? colors.green : colors.pink);
  ctx.restore();
  if (s.proved) check(0, 21, 18);
  else { ellipse(-8, 20, 4, 4, colors.ink); ellipse(8, 20, 4, 4, colors.ink); }
  ctx.restore();
  const message = s.phase === "PAUSE" ? "Ready, set..." : s.proved ? "Proof first. Got it!" : "Oh! Let's check.";
  box(s.runnerX - 139, 474, 278, 59, colors.paper, 24, "#e4ddd1");
  text(message, s.runnerX, 512, 24, colors.ink, 650, "center");
  text("LITTLE AGENT", s.runnerX, 823, 18, colors.muted, 700, "center");
}
function proofCard(s) {
  const enter = smooth((s.t - 1.6) / .6);
  ctx.save(); ctx.globalAlpha = enter;
  ctx.translate(1030, 568 + (1 - enter) * 24);
  ctx.rotate(-.035);
  ctx.shadowColor = "#173c4612"; ctx.shadowBlur = 30; ctx.shadowOffsetY = 15;
  box(-139, -126, 278, 326, colors.paper, 28, "#c5ded3");
  ctx.shadowColor = "transparent";
  box(-69, -145, 138, 36, colors.mint, 13);
  text("PREFLIGHT", 0, -70, 22, colors.green, 800, "center");
  const labels = ["Goal", "Tools", "Proof"];
  labels.forEach((label, i) => {
    const y = -21 + i * 61;
    box(-104, y - 19, 32, 32, s.checked[i] ? "#d8f5e7" : "#f0f2ed", 9);
    if (s.checked[i]) check(-88, y - 3, 20);
    text(label, -50, y + 5, 27, colors.ink, 650);
    if (!s.checked[i] && i === s.checked.filter(Boolean).length) {
      ctx.beginPath(); ctx.arc(85, y - 3, 9, s.t * 5, s.t * 5 + Math.PI * 1.5);
      ctx.strokeStyle = colors.green; ctx.lineWidth = 3; ctx.stroke();
    }
  });
  box(-103, 145, 206, 33, s.proved ? colors.green : "#edf3ed", 16);
  text(s.proved ? "CHECKED!" : "Before execution", 0, 168, 18, s.proved ? "#fff" : colors.muted, 700, "center");
  ctx.restore();
}
function gate(s) {
  const fade = 1 - smooth((s.t - 6) / .4);
  ctx.save(); ctx.globalAlpha = fade;
  line([[711, 645], [711, 763]], "#d4997f", 8);
  box(665, 572, 92, 81, "#ffebe0", 24, "#e1ad94");
  line([[697, 594], [697, 631]], "#ae6555", 9);
  line([[724, 594], [724, 631]], "#ae6555", 9);
  ctx.restore();
}
function renderFrame(seconds) {
  const s = stateAt(seconds);
  const background = ctx.createLinearGradient(0, 0, 1920, 1080);
  background.addColorStop(0, "#fffaf0"); background.addColorStop(1, "#edf8f2");
  ctx.fillStyle = background; ctx.fillRect(0, 0, 1920, 1080);
  ellipse(1460, 541, 362, 342, "#dbf3e8");
  ellipse(1720, 310, 89, 89, "#ffe8d4");
  ellipse(110, 940, 230, 230, "#ffead93d");
  for (let i = 0; i < 22; i++) {
    ellipse(96 + (i * 173) % 1740, 180 + (i * 113) % 700, 3, 3, "#548b7421");
  }
  ellipse(139, 110, 12, 12, colors.green);
  text("SkillC", 169, 125, 46, colors.ink, 800);
  text("SMALL SHIELD. BIG PEACE OF MIND.", 128, 173, 19, colors.muted, 700);
  box(1529, 68, 263, 86, "#fff", 19);
  if (logo.complete && logo.naturalWidth) ctx.drawImage(logo, 1557, 89, 207, 44);
  text("Don't run first.", 128, 293, 103, colors.ink, 800);
  ctx.save(); ctx.globalAlpha = .35 + .65 * smooth((s.t - 1.5) / .8);
  text("Prove first.", 128, 411, 112, colors.green, 800);
  ctx.restore();
  line([[138, 437], [685, 437]], "#a6dfc0", 7);
  text(s.proved ? "A little proof. A smarter start." : "Big adventures deserve a little preflight.", 128, 891, 34, colors.ink, 650);
  line([[151, 773], [879, 773]], "#c9ddd2", 3);
  if (s.proved) {
    line([[635, 767], [718, 767]], colors.green, 4);
    line([[705, 756], [718, 767], [705, 778]], colors.green, 4);
  }
  gate(s); runner(s); proofCard(s); shield(s);
  const speech = s.proved ? "Now we're ready!" : s.phase === "PROVE" ? "Proof before poof!" : "One tiny check!";
  box(1240, 217, 376, 81, colors.paper, 30, "#c5ded3");
  text(speech, 1428, 269, 31, colors.green, 700, "center");
  line([[1402, 299], [1412, 317], [1433, 299]], "#c5ded3", 3);
  const celebration = s.proved ? smooth((s.t - 6) / .4) : .35;
  for (let i = 0; i < 9; i++) {
    const angle = i * Math.PI * 2 / 9;
    const pulse = 1 + Math.sin(s.t * 3 + i) * .18;
    sparkle(1430 + Math.cos(angle) * 270, 542 + Math.sin(angle) * 222,
      (i % 2 ? 11 : 20) * pulse * celebration,
      [colors.yellow, "#67bda3", "#e9a6ae"][i % 3], s.t * .16);
  }
  ["01  Pause", "02  Prove", "03  Proceed"].forEach((label, i) => {
    const active = i === (s.phase === "PAUSE" ? 0 : s.proved ? 2 : 1);
    const x = 1145 + i * 220;
    box(x, 849, 202, 61, active ? colors.green : "#ffffffa6", 30);
    text(label, x + 101, 889, 25, active ? "#fff" : colors.muted, 700, "center");
  });
  text("Illustrative preflight. Guarantees are relative to the declared model.", 960, 991, 21, colors.muted, 500, "center");
  text("Independent hackathon concept. Not endorsed by Microsoft.", 960, 1031, 19, colors.muted, 500, "center");
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
  current = Math.max(0, Math.min(duration, t));
  renderFrame(current);
  scrub.value = String(current);
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
  started = performance.now() - current * 1000;
  playing = true; play.textContent = "Pause";
  request = requestAnimationFrame(tick);
}
play.disabled = true;
document.getElementById("replay").disabled = true;
scrub.disabled = true;
const logoReady = new Promise((resolve, reject) => {
  const loaded = () => logo.naturalWidth ? resolve() : reject(new Error("Microsoft logo could not load."));
  if (logo.complete) loaded();
  else {
    logo.addEventListener("load", loaded, { once: true });
    logo.addEventListener("error", () => reject(new Error("Microsoft logo could not load.")), { once: true });
  }
});
const ready = Promise.all([logoReady, document.fonts.ready]).then(() => {
  show(0);
  play.disabled = false;
  document.getElementById("replay").disabled = false;
  scrub.disabled = false;
  if (!new URLSearchParams(location.search).has("render") && !matchMedia("(prefers-reduced-motion: reduce)").matches) start();
});
ready.catch(error => {
  output.textContent = `Animation could not load: ${error.message}`;
  console.error("SkillC animation failed to initialize.", error);
});
play.addEventListener("click", () => playing ? pause() : start());
document.getElementById("replay").addEventListener("click", () => { pause(); show(0); start(); });
scrub.addEventListener("input", () => { pause(); show(Number(scrub.value)); });
window.animation = { renderFrame, stateAt, ready, duration, width: 1920, height: 1080 };
