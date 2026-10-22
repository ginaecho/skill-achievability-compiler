# Real skills, end to end (recording)

**Shows:** five natural-language `SKILL.md` files from Anthropic's public skills repository compiled by
a model into packs, gated by the schema, and decided by the checker. **Audience:** anyone asking
"does it work on real skills?". **Time:** 2 minutes (the video).

## Watch it

Play `skillc-real-skills-demo.mp4`, or read `transcript.txt`. `results.json` and `generated-packs/` are
the recorded outputs, so you can show them without calling a model.

## Record it again

This calls a model, so it needs `SKILLC_ALLOW_MODEL_CALLS=1`, set on purpose for one run you agreed to.
Requests go through the URL guard (see `CLAUDE.md`).

```powershell
$env:SKILLC_ALLOW_MODEL_CALLS = "1"
$env:AZURE_OPENAI_ENDPOINT = "<your Azure OpenAI endpoint>"
python scripts\make_real_skill_demo.py --provider azure-openai --model YOUR_DEPLOYMENT
```

## Reference
This demo starts from five **natural-language** `SKILL.md` files in Anthropic's
official skills repository. It does not contain embedded or hand-written JSON
packs. For each case the runner:

1. downloads the source and license at pinned commit `3b3fad96`;
2. sends the natural-language skill to the selected untrusted LLM compactor;
3. passes the generated JSON through `skillc`'s deterministic schema gate;
4. saves the accepted pack under `generated-packs/`;
5. runs the trusted checker and records its verdict.

| Natural-language source | License |
|---|---|
| `skills/webapp-testing/SKILL.md` | Apache-2.0 |
| `skills/mcp-builder/SKILL.md` | Apache-2.0 |
| `skills/frontend-design/SKILL.md` | Apache-2.0 |
| `skills/slack-gif-creator/SKILL.md` | Apache-2.0 |
| `skills/algorithmic-art/SKILL.md` | Apache-2.0 |

Azure OpenAI authentication uses `AZURE_OPENAI_API_KEY` when set; otherwise it
uses the current `az login` identity. Anthropic remains available with
`--provider anthropic` and `ANTHROPIC_API_KEY`.

Generated artifacts:

- `natural-language/<skill>/SKILL.md`: pinned upstream inputs.
- `generated-packs/<skill>.json`: actual untrusted LLM outputs accepted by the
  schema gate.
- `results.json`: source hashes, compaction attempts, pack summaries, verdicts,
  witnesses/frontiers, provider, and model.
- `transcript.txt`: exact human-readable pipeline transcript.
- `skillc-real-skills-demo.mp4`: terminal-style recording made from that
  transcript.

Source research and license notes are in
[`docs/archive/REAL_SKILL_DEMO_SOURCES.md`](../../docs/archive/REAL_SKILL_DEMO_SOURCES.md).
