import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { mkdtemp, readFile, rmdir, unlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, isAbsolute, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const directory = dirname(fileURLToPath(import.meta.url));
const root = resolve(directory, "..", "..");
const python = process.argv[2];
assert.ok(python && isAbsolute(python), "Pass the configured Python interpreter's absolute path.");
const packPath = join(directory, "meeting-mailbox.pack.json");
const packSource = await readFile(packPath, "utf8");
const pack = JSON.parse(packSource);
const checkerPath = join(root, "src", "skillc", "checker.py");
const checkerSource = await readFile(checkerPath, "utf8");
const hash = value => createHash("sha256").update(value).digest("hex");

function run(file, json, expectedExit) {
  const args = ["-m", "skillc.cli", "check", file, ...(json ? ["--json"] : [])];
  const result = spawnSync(python, args, { cwd: directory, encoding: "utf8", windowsHide: true });
  if (result.error) throw result.error;
  assert.equal(result.status, expectedExit, `Unexpected exit.\n${result.stdout}\n${result.stderr}`);
  assert.equal(result.stderr.trim(), "", result.stderr);
  return { stdout: result.stdout, exitCode: result.status };
}

const textRun = run("meeting-mailbox.pack.json", false, 1);
const jsonRun = run("meeting-mailbox.pack.json", true, 1);
const verdict = JSON.parse(jsonRun.stdout);
assert.equal(verdict.verdict, "IMPOSSIBLE");
assert.equal(verdict.reason, "GOAL_UNSAT");
assert.deepEqual(verdict.frontier, ["invited_all"]);
assert.equal(verdict.refuted, true);
assert.equal(verdict.unknown, false);

const scratch = await mkdtemp(join(tmpdir(), "skillc-meeting-controls-"));
const controlPath = join(scratch, "control.json");
try {
  const scheduleOnly = { ...pack, goal: "scheduled" };
  await writeFile(controlPath, JSON.stringify(scheduleOnly));
  assert.equal(JSON.parse(run(controlPath, true, 0).stdout).verdict, "ACHIEVABLE");
  const repaired = {
    ...pack,
    capabilities: {
      ...pack.capabilities,
      invite_everyone: { owner: "assistant", pre: "scheduled", add: ["invited_all"] }
    },
    protocol: [...pack.protocol, { act: { cap: "invite_everyone", by: "assistant" } }]
  };
  await writeFile(controlPath, JSON.stringify(repaired));
  assert.equal(JSON.parse(run(controlPath, true, 0).stdout).verdict, "ACHIEVABLE");
} finally {
  await unlink(controlPath);
  await rmdir(scratch);
}

const lines = checkerSource.split(/\r?\n/);
function excerpt(start, end, include) {
  const begin = lines.findIndex(line => line.includes(start));
  assert.ok(begin >= 0, `Missing source marker: ${start}`);
  const finish = lines.findIndex((line, i) => i >= begin && line.includes(end));
  assert.ok(finish >= begin, `Missing source marker: ${end}`);
  return lines.slice(begin, finish + 1)
    .map((text, i) => ({ number: begin + i + 1, text }))
    .filter(line => include(line.text));
}
const closure = excerpt("def establishable_atoms(", "return frozenset(out)", line =>
  /^(def |    out |    for |        out |    return )/.test(line));
const refutation = excerpt("    def _gamma_refutation(", "frontier=dead)", line =>
  /can = establishable_atoms|if isinstance\(f, str\)|return z3.Bool\(f\)|if "and" in f|return z3.And|if _sat\(\[enc|return None|dead = tuple|return Verdict\(False|frontier=dead/.test(line));
assert.equal(closure.length, 5);
assert.equal(refutation.length, 10);
const evidence = {
  capturedAt: new Date().toISOString(),
  command: "python -m skillc.cli check meeting-mailbox.pack.json --json",
  workingDirectory: "docs\\videos",
  provenance: "Real local SkillC CLI output for a hand-authored demonstration pack. Not a live mailbox probe.",
  packSource,
  packSha256: hash(packSource),
  checkerSha256: hash(checkerSource),
  checkerFile: "src\\skillc\\checker.py",
  closure,
  refutation,
  verdict,
  textStdout: textRun.stdout,
  jsonStdout: jsonRun.stdout,
  exitCode: jsonRun.exitCode,
  controls: { scheduleOnly: "ACHIEVABLE", invitationCapabilityAdded: "ACHIEVABLE" }
};
await writeFile(join(directory, "meeting-mailbox.verdict.json"), jsonRun.stdout);
await writeFile(join(directory, "meeting-terminal-evidence.js"),
  `window.MEETING_TERMINAL_EVIDENCE = ${JSON.stringify(evidence, null, 2)};\n`);
console.log(textRun.stdout.trim());
console.log("Confirmed exit 1, frontier invited_all, and both achievable control cases.");
console.log("Saved exact CLI output and source excerpts for the terminal animation.");
