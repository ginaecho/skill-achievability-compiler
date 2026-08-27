# End-to-end real-skill compiler demo

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

Run and record the complete demo from the repository root:

```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://YOUR-RESOURCE.openai.azure.com/openai/v1"
python scripts\make_real_skill_demo.py --provider azure-openai --model YOUR_DEPLOYMENT
```

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
[`docs/REAL_SKILL_DEMO_SOURCES.md`](../../docs/REAL_SKILL_DEMO_SOURCES.md).
