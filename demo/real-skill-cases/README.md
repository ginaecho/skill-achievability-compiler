# Real-skill compiler demo

These five cases are small, manually declared achievability packs grounded in
first-party skill files or product documentation. They preserve each source's
workflow goal and named tool requirements, but they do not copy or execute the
upstream skill. `skillc` checks the declared structure before any real tool runs.

| Case | Primary source | Expected verdict |
|---|---|---|
| `01-docx-render-verify` | Anthropic `docx` skill | `ACHIEVABLE` |
| `02-github-pr-review` | GitHub Copilot cloud agent and GitHub MCP tools | `ACHIEVABLE` |
| `03-fetch-is-not-search` | MCP reference `fetch` server | `IMPOSSIBLE [MISSING_CAPABILITY]` |
| `04-protected-deployment` | GitHub Actions protected environments | `IMPOSSIBLE [BLOCKED_GUARD]` |
| `05-xlsx-recalc-required` | Anthropic `xlsx` skill | `IMPOSSIBLE [GOAL_UNSAT]` |

Run and record the complete demo from the repository root:

```powershell
python scripts\make_real_skill_demo.py
```

Generated artifacts:

- `results.json`: structured commands, outputs, exit codes, and expectations.
- `transcript.txt`: human-readable terminal transcript.
- `skillc-real-skills-demo.mp4`: terminal-style video made from those exact runs.

Source research and license notes are in
[`docs/REAL_SKILL_DEMO_SOURCES.md`](../../docs/REAL_SKILL_DEMO_SOURCES.md).

