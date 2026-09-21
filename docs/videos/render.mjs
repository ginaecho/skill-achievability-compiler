import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

const directory = dirname(fileURLToPath(import.meta.url));
const scene = process.argv[2] ?? "agent-runtime-cost";
assert.ok(["agent-runtime-cost", "agents-game", "skillc-meeting-proof", "skillc-meeting-terminal", "skillc-prove-first", "skillc-impact", "skillc-impact_v2"].includes(scene), `Unknown animation: ${scene}`);
const verifyOnly = process.argv.includes("--verify-only");
const fps = 30;
const output = join(directory, `${scene}.mp4`);
const browser = await chromium.launch({
  headless: true,
  ...(process.env.BROWSER_EXECUTABLE
    ? { executablePath: process.env.BROWSER_EXECUTABLE }
    : { channel: "msedge" })
});
let encoder;
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto(`${pathToFileURL(join(directory, `${scene}.html`))}?render`);
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => window.animation.ready);
  const duration = await page.evaluate(() => window.animation.duration);
  assert.ok(Number.isFinite(duration) && duration > 0);
  const frames = Math.round(duration * fps);
  assert.equal(frames / fps, duration);
  assert.deepEqual(await page.locator("#scene").evaluate(c => [c.width, c.height]), [1920, 1080]);
  if (scene === "skillc-impact_v2") {
    assert.equal(duration, 12);
    const stats = await page.evaluate(() => window.animation.stateAt(5));
    const expected = [
      ["PDF", 4, 22011, 157454, "M", "86.02"],
      ["XLSX", 4, 32028, 209766, "M", "84.73"],
      ["DOCX", 4, 22024, 121589, "E", "81.89"],
      ["Bulk RNA-seq", 4, 26596, 2474309, "E", "98.93"],
      ["Data-quality auditor", 2, 23310, 1067664, "E", "97.82"],
      ["Google Workspace CLI", 4, 25099, 3641064, "E", "99.31"],
      ["Kubernetes operator", 4, 24569, 3951603, "E", "99.38"],
      ["Writing skills", 4, 33558, 3149738, "E", "98.93"]
    ];
    assert.deepEqual(stats.skills.map(r => [r.name, r.runs, r.compaction, r.runtime, r.evidence, r.reduction]), expected);
    assert.deepEqual(stats.totals, {
      runs: 30, runtime: 14773187, compaction: 209195, saved: 14563992, measured: 54039, estimated: 155156
    });
    assert.equal(stats.reduction, "98.58");
    const drawn = await page.evaluate(() => {
      const context = document.getElementById("scene").getContext("2d");
      const originalText = context.fillText, originalRect = context.fillRect;
      const labels = [], bars = [], bounds = [];
      try {
        context.fillText = function (value, x, y, ...rest) {
          const width = this.measureText(value).width;
          const left = this.textAlign === "right" ? x - width : this.textAlign === "center" ? x - width / 2 : x;
          bounds.push({ left, right: left + width, y });
          labels.push(value);
          return originalText.call(this, value, x, y, ...rest);
        };
        context.fillRect = function (x, y, w, h) {
          if (h === 34) bars.push([x, y, w, h]);
          return originalRect.call(this, x, y, w, h);
        };
        window.animation.renderFrame(5);
      } finally { context.fillText = originalText; context.fillRect = originalRect; }
      return { labels, bars, bounds };
    });
    for (const row of stats.skills) {
      for (const label of [row.name, row.runtime.toLocaleString("en-US"),
        row.compaction.toLocaleString("en-US"), `${row.reduction}%`]) {
        assert.ok(drawn.labels.includes(label), `Missing per-skill label: ${label}`);
      }
      assert.equal(row.saved, row.runtime - row.compaction);
    }
    assert.ok(drawn.labels.includes("30 unsuccessful agent runs / 8 skill categories"));
    assert.ok(drawn.labels.includes("PDF/XLSX compaction measured; other compaction estimated. All runtime measured."));
    assert.ok(drawn.labels.every(label => !/\[(M|E)\]/.test(label)), "Evidence markers must not appear on the cover.");
    assert.ok(drawn.bounds.every(b => b.left >= 64 && b.right <= 1856 && b.y <= 1050), "Text must fit the frame.");
    assert.deepEqual(drawn.bars, stats.skills.flatMap((row, i) => [
      [1290, 284 + i * 71, 320, 34],
      [1290, 284 + i * 71, 320 * (1 - row.ratio), 34]
    ]), "Every percentage bar must use the same 0-100% scale.");
    const frames = await page.evaluate(() => [0, 2, 11.9].map(t => {
      window.animation.renderFrame(t);
      return document.getElementById("scene").toDataURL("image/png");
    }));
    assert.notEqual(frames[0], frames[1]);
    assert.equal(frames[1], frames[2], "Hold the complete comparison after the reveal.");
    assert.equal(await page.evaluate(() => {
      try { window.animation.stateAt(NaN); return false; }
      catch (error) { return error instanceof TypeError; }
    }), true);
  } else if (scene === "skillc-impact") {
    assert.equal(duration, 6);
    const stats = await page.evaluate(() => window.animation.stateAt(5));
    assert.equal(stats.runs, 46);
    assert.equal(stats.correctResults, 0);
    assert.equal(stats.without, 15841106);
    assert.equal(stats.withSkillC, 209195);
    assert.equal(stats.measured, 54039);
    assert.equal(stats.estimated, 155156);
    assert.equal(stats.withSkillC, stats.measured + stats.estimated);
    assert.equal(stats.saved, "98.7");
    assert.equal(stats.percent, "1.32");
    assert.equal(stats.leverage, "75.7");
    assert.equal(stats.subsetWithout, 367220);
    assert.equal(stats.subsetSaved, "85.28");
    const drawn = await page.evaluate(() => {
      const context = document.getElementById("scene").getContext("2d");
      const original = context.fillText;
      const originalRect = context.roundRect;
      const labels = [];
      const sizes = [];
      const bars = [];
      try {
        context.fillText = function (text, ...args) {
          sizes.push(Number(this.font.match(/([\d.]+)px/)[1]));
          labels.push(text); return original.call(this, text, ...args);
        };
        context.roundRect = function (...args) {
          bars.push(args); return originalRect.apply(this, args);
        };
        window.animation.renderFrame(5);
      } finally {
        context.fillText = original;
        context.roundRect = originalRect;
      }
      return { labels, sizes, bars };
    });
    assert.deepEqual(drawn.labels, [
      "46 REAL AGENT RUNS", "98.7%", "TOKENS SAVED WITH SkillC",
      "WITHOUT SkillC CHECK", "15,841,106 tokens",
      "WITH SkillC CHECK", "209,195 tokens"
    ]);
    assert.ok(drawn.sizes.every(size => size >= 48), "No small text may appear on the cover.");
    assert.deepEqual(drawn.bars, [
      [160, 645, 1600, 96, 12],
      [160, 870, 1600, 96, 12],
      [160, 645, 1600, 96, 12],
      [160, 870, 1600 * stats.ratio, 96, 12]
    ], "Both token bars must share a baseline and scale, using the actual token ratio.");
    const held = await page.evaluate(() => [2, 5.9].map(t => {
      window.animation.renderFrame(t);
      return document.getElementById("scene").toDataURL("image/png");
    }));
    assert.equal(held[0], held[1], "Cover must hold still after the introductory reveal.");
  } else if (scene === "skillc-prove-first") {
    assert.equal(duration, 10);
    const states = await page.evaluate(() =>
      [0, 1.6, 2, 3, 4.2, 5.99, 6, 8.3, 10].map(t => window.animation.stateAt(t)));
    assert.deepEqual(states.map(s => s.phase),
      ["PAUSE", "PAUSE", "PROVE", "PROVE", "PROVE", "PROVE", "PROCEED", "PROCEED", "PROCEED"]);
    assert.deepEqual(states.map(s => s.checked.filter(Boolean).length), [0, 0, 0, 1, 2, 2, 3, 3, 3]);
    assert.ok(states.every(s => s.headline === "Don't run first, prove first"));
    assert.ok(states.filter(s => s.t >= 1.6 && s.t < 6).every(s => s.runnerX === 520 && !s.moving));
    assert.ok(states.every(s => s.admitted === s.checked.every(Boolean)));
    assert.equal(states.at(-1).runnerX, 740);
    assert.equal(await page.locator("#microsoft-logo").evaluate(image => image.complete && image.naturalWidth > 0), true);
    const frames = await page.evaluate(() => [0, 3.5, 9].map(time => {
      window.animation.renderFrame(time);
      return document.getElementById("scene").toDataURL("image/png");
    }));
    assert.equal(new Set(frames).size, 3, "Animation stages must render distinct frames.");
    const invalidInputRejected = await page.evaluate(() => {
      try { window.animation.stateAt(NaN); return false; }
      catch (error) { return error instanceof TypeError; }
    });
    assert.ok(invalidInputRejected);
  } else if (scene === "skillc-meeting-terminal") {
    assert.equal(duration, 18);
    const evidence = await page.evaluate(() => window.MEETING_TERMINAL_EVIDENCE);
    const hash = value => createHash("sha256").update(value).digest("hex");
    assert.equal(hash(await readFile(join(directory, "meeting-mailbox.pack.json"))), evidence.packSha256,
      "Pack changed: recapture the CLI evidence.");
    assert.equal(hash(await readFile(join(directory, "..", "..", "src", "skillc", "checker.py"))), evidence.checkerSha256,
      "Checker changed: recapture the source and CLI evidence.");
    assert.deepEqual(JSON.parse(evidence.jsonStdout), evidence.verdict);
    assert.deepEqual(JSON.parse(await readFile(join(directory, "meeting-mailbox.verdict.json"), "utf8")), evidence.verdict);
    assert.equal(evidence.verdict.verdict, "IMPOSSIBLE");
    assert.equal(evidence.verdict.reason, "GOAL_UNSAT");
    assert.deepEqual(evidence.verdict.frontier, ["invited_all"]);
    assert.equal(evidence.exitCode, 1);
    assert.deepEqual(evidence.controls, { scheduleOnly: "ACHIEVABLE", invitationCapabilityAdded: "ACHIEVABLE" });
    const displayed = JSON.parse(await page.evaluate(() => window.animation.terminalExcerpt));
    for (const [key, value] of Object.entries(displayed)) assert.deepEqual(value, evidence.verdict[key]);
    const states = await page.evaluate(() => [0, 5, 9, 12.8, 18].map(t => window.animation.stateAt(t)));
    assert.deepEqual(states.map(s => s.phase), ["PACK", "CLOSURE", "PROOF", "REFUTED", "REFUTED"]);
    assert.equal(states[0].outputLines, 0);
    assert.equal(states.at(-1).outputLines, (await page.evaluate(() => window.animation.terminalExcerpt)).split("\n").length);
    assert.equal(states.at(-1).exitCode, 1);
    const captionRegions = await page.evaluate(() => {
      const context = document.getElementById("scene").getContext("2d");
      const original = context.fillText;
      const frames = [];
      try {
        for (const time of [1, 7, 11, 17]) {
          const drawn = [];
          context.fillText = function (value, x, y, ...rest) {
            if (y >= 850 && y <= 935) drawn.push(value);
            return original.call(this, value, x, y, ...rest);
          };
          window.animation.renderFrame(time);
          frames.push(drawn);
        }
      } finally {
        context.fillText = original;
      }
      return frames;
    });
    assert.deepEqual(captionRegions.slice(0, 3), [[], [], []], "Narration captions must not be drawn.");
    assert.deepEqual(captionRegions[3], ["EXIT 1", "IMPOSSIBLE [GOAL_UNSAT]", "frontier: invited_all"]);
  } else if (scene === "skillc-meeting-proof") {
    assert.equal(duration, 14);
    const states = await page.evaluate(() =>
      [0, 4.49, 4.5, 5.5, 7.5, 9.3, 10.79, 10.8, 14].map(t => window.animation.stateAt(t)));
    assert.deepEqual(states.map(s => s.phase),
      ["COMPILE", "COMPILE", "COMPARE", "COMPARE", "COMPARE", "PROVE", "PROVE", "STOPPED", "STOPPED"]);
    for (const state of states) {
      assert.deepEqual(state.goalTerms, ["scheduled", "invited_all"]);
      assert.equal(state.operator, "AND");
      assert.deepEqual(state.capabilities, { schedule_meeting: true, invite_all: false });
      assert.deepEqual(state.reachableStates, [
        { scheduled: false, invited_all: false }, { scheduled: true, invited_all: false }
      ]);
      assert.equal(state.goalReachable, false);
      assert.equal(state.runtimeActions, 0);
      assert.equal(state.verdict, state.stopped ? "IMPOSSIBLE" : null);
    }
    assert.equal(states[3].scheduleRevealed, true);
    assert.equal(states[3].invitationRevealed, false);
    assert.equal(states[4].invitationRevealed, true);
    assert.equal(states.at(-1).stopped, true);
  } else {
    assert.equal(duration, 10);
    const states = await page.evaluate(() =>
      [0, 4, 5, 5.9, 6, 7, 8.2, 10].map(t => window.animation.stateAt(t)));
    assert.deepEqual(states.map(s => s.phase.label),
      ["EXECUTING", "RETRYING", "WAITING", "WAITING", "REPLANNING", "FINAL ATTEMPT", "FAILED", "FAILED"]);
    assert.equal(states[2].tokens, states[3].tokens, "Backoff must not spend additional tokens.");
    assert.equal(states.at(-1).tokens, 12480);
    assert.equal(states.at(-1).failed, true);
    assert.ok(states.every((s, i) => !i || s.tokens >= states[i - 1].tokens));
    if (scene === "agents-game") {
      assert.equal(states.at(-1).agents.length, 6);
      assert.ok(states.at(-1).agents.every(agent => agent.status === "FAILED"));
      assert.ok(states[2].agents.every(agent => agent.status === "WAITING"));
      assert.deepEqual(states[2].agents.map(a => [a.x, a.y]), states[3].agents.map(a => [a.x, a.y]));
      const activity = await page.evaluate(() =>
        [0.5, 1, 2, 3, 4.5, 6.5, 7.5].map(t => window.animation.stateAt(t)));
      for (let i = 0; i < 6; i++) {
        assert.ok(activity.some(s => s.agents[i].running), `Agent ${i} must visibly run.`);
        const positions = activity.map(s => `${s.agents[i].x},${s.agents[i].y}`);
        assert.ok(new Set(positions).size >= 4, `Agent ${i} must move between stations.`);
      }
      assert.ok(states.every(s => s.goalsReached === 0));
      const bottomOverlays = await page.evaluate(() => {
        const context = document.getElementById("scene").getContext("2d");
        const original = context.fillText;
        const originalRect = context.roundRect;
        const drawn = [];
        const progressBars = [];
        try {
          context.fillText = function (value, x, y, ...rest) {
            if (y >= 880 && y <= 970) drawn.push(value);
            return original.call(this, value, x, y, ...rest);
          };
          context.roundRect = function (x, y, w, h, ...rest) {
            if (y >= 980 && y <= 1000) progressBars.push([x, y, w, h]);
            return originalRect.call(this, x, y, w, h, ...rest);
          };
          for (let frame = 0; frame <= 300; frame++) window.animation.renderFrame(frame / 30);
        } finally {
          context.fillText = original;
          context.roundRect = originalRect;
        }
        return { captions: drawn, progressBars };
      });
      assert.deepEqual(bottomOverlays.captions, [], "Game narration captions must not appear in any frame.");
      assert.deepEqual(bottomOverlays.progressBars, [], "The bottom progress bar must not appear in any frame.");
    }
  }
  for (const t of [0, 4.5, 5.5, 6.5, 9, duration - 0.1]) {
    await page.evaluate(time => window.animation.renderFrame(time), t);
    assert.deepEqual(errors, []);
  }
  await page.locator("#scrub").fill("5.5");
  assert.equal(await page.locator("#time").textContent(), `5.50 / ${duration.toFixed(2)} s`);
  assert.equal(await page.locator("#play").textContent(), "Play");
  await page.locator("#play").click();
  assert.equal(await page.locator("#play").textContent(), "Pause");
  await page.locator("#play").click();
  assert.equal(await page.locator("#play").textContent(), "Play");
  for (const width of [390, 1280, 1920]) {
    await page.setViewportSize({ width, height: 1080 });
    const fits = await page.locator("#scene").evaluate(canvas =>
      canvas.getBoundingClientRect().right <= innerWidth && document.documentElement.scrollWidth <= innerWidth);
    assert.ok(fits, `Preview must fit a ${width}px viewport without horizontal scrolling.`);
  }
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(pathToFileURL(join(directory, `${scene}.html`)).href);
  await page.evaluate(() => window.animation.ready);
  assert.equal(await page.locator("#play").textContent(), "Play");
  assert.equal(await page.locator("#scrub").inputValue(), "0");
  console.log(`${scene}: timeline, model, playback, responsive layout and reduced-motion checks passed.`);

  if (!verifyOnly) {
    encoder = spawn("ffmpeg", [
      "-hide_banner", "-loglevel", "error", "-y",
      "-f", "image2pipe", "-framerate", String(fps), "-vcodec", "png", "-i", "pipe:0",
      "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
      "-pix_fmt", "yuv420p", "-movflags", "+faststart", output
    ], { stdio: ["pipe", "inherit", "inherit"] });
    const completed = new Promise((resolve, reject) => {
      encoder.once("error", reject);
      encoder.once("close", code => code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}`)));
      encoder.stdin.once("error", reject);
    });
    // Observe early encoder failure even while browser frames are being rendered.
    let encoderError;
    completed.catch(error => { encoderError = error; });
    for (let frame = 0; frame < frames; frame++) {
      if (encoderError) throw encoderError;
      const png = await page.evaluate(time => {
        window.animation.renderFrame(time);
        return document.getElementById("scene").toDataURL("image/png").split(",")[1];
      }, frame / fps);
      if (!encoder.stdin.write(Buffer.from(png, "base64"))) {
        await Promise.race([once(encoder.stdin, "drain"), completed]);
      }
      if (frame % fps === 0) console.log(`Rendered ${frame / fps} / ${duration} seconds`);
    }
    encoder.stdin.end();
    await completed;
    const poster = await page.evaluate(time => {
      window.animation.renderFrame(time);
      return document.getElementById("scene").toDataURL("image/png").split(",")[1];
    }, duration - 1);
    await writeFile(join(directory, `${scene}-poster.png`), Buffer.from(poster, "base64"));
    assert.deepEqual(errors, []);
    console.log(`Exported ${output} (1920x1080, 30 fps, ${duration} seconds, silent).`);
  }
  assert.deepEqual(errors, []);
} finally {
  if (encoder && encoder.exitCode === null) encoder.kill();
  await browser.close();
}
