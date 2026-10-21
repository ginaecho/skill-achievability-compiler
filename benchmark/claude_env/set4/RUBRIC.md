# Blind annotation rubric for set4 (requirement availability against a declared runtime)

You are labelling one natural-language document (a SKILL.md or an agent.md written by a
person) against one declared runtime. Nothing else: do not run skillc, do not read any file
outside this folder and the runtime manifest you are given, do not look at other annotators'
files.

## What to produce

One JSON file per case, `truth/<case>.json`:

```json
{
 "case": "c001",
 "runtime": "claude-code-cloud",
 "primary_task": "one sentence: what the document is for, for one representative request",
 "requirements": [
  {"kind": "program|egress|credential|connector|tool|platform|hardware|other",
   "name": "terraform",
   "hard": true,
   "evidence": "the line or phrase of the document that makes it required",
   "status": "available|installable|unavailable|unknown",
   "basis": "which sentence of the runtime manifest decides the status"}
 ],
 "verdict": "ACHIEVABLE|BLOCKED",
 "blocking": ["kind:name", "..."],
 "notes": "ambiguities, and what the verdict would be under the other reading"
}
```

## How to decide

1. **Primary task.** State the document's core deliverable for one representative request.
   Optional, conditional or follow-up work (extra diagnostics, notifications, publishing the
   core request does not ask for) is not part of it. Reasoning, planning and writing text in
   the reply are done by the agent itself and need no requirement.
2. **Requirements.** List every program, host, credential, connector, tool, platform or
   hardware the document relies on. Mark `hard: true` only when the primary task cannot be
   done without it as the document is written (a "must", a numbered required step, the only
   way to produce the deliverable). Alternatives count as one requirement satisfied by any of
   them: say so in `evidence`.
3. **Status against the runtime manifest.** `available`: the manifest lists it (a tool, a
   connector, a granted resource) or it is standard software of the stated platform.
   `installable`: a program obtainable from a package registry the manifest says is reachable.
   `unavailable`: the manifest says it is lacking, forbids it, or the host is outside the
   stated egress allow-list. `unknown`: the manifest does not say; write what you would need
   to check. Quote the deciding manifest sentence in `basis`.
4. **Verdict.** `BLOCKED` if any `hard: true` requirement is `unavailable`. Otherwise
   `ACHIEVABLE`. `unknown` statuses do not block; list them in `notes`.
5. **Notes.** Where the document can be read two ways (the earlier set's annotators found
   this common), say which reading you took and what the other reading would give.

Be literal and strict. Do not guess what the author "really meant"; label what the document
says.
