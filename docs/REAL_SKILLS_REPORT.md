# Real-skill scan report

`skillc 0.3.0` run over the public skills corpus ([anthropics/skills](https://github.com/anthropics/skills)): 42 `SKILL.md` files, checked under each capability profile.  Regenerate with `python3 scripts/make_report.py <dir>`.

A verdict is always *relative to a capability context*: `IMPOSSIBLE [MISSING_CAPABILITY]` means the skill's instructions invoke a tool that this runtime does not grant -- the skill cannot be carried out as written there.  It is not a defect of the skill.

| skill | claude-ai | claude-code |
|---|---|---|
| `examples/algorithmic-art` | ACHIEVABLE | ACHIEVABLE |
| `examples/artifact-emulator` | ACHIEVABLE | ACHIEVABLE |
| `examples/benepass-reimbursement` | ACHIEVABLE | IMPOSSIBLE (`read_page`, `upload_file`) |
| `examples/brand-guidelines` | ACHIEVABLE | ACHIEVABLE |
| `examples/built-in-browser` | ACHIEVABLE | IMPOSSIBLE (`tabs_context`) |
| `examples/call-to-book` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/cancel-unsubscribe` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/canvas-design` | ACHIEVABLE | ACHIEVABLE |
| `examples/chrome-browser` | ACHIEVABLE | IMPOSSIBLE (`tabs_context_mcp`) |
| `examples/computer-use` | ACHIEVABLE | ACHIEVABLE |
| `examples/deep-research` | ACHIEVABLE | ACHIEVABLE |
| `examples/doc-coauthoring` | ACHIEVABLE | IMPOSSIBLE (`create_file`, `str_replace`) |
| `examples/docs` | ACHIEVABLE | ACHIEVABLE |
| `examples/event-planning` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/file-expenses` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/file-form` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/financial-calculator` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/google-workspace` | ACHIEVABLE | ACHIEVABLE |
| `examples/grocery-shopping` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/hire-help` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/import-memory` | ACHIEVABLE | ACHIEVABLE |
| `examples/internal-comms` | ACHIEVABLE | ACHIEVABLE |
| `examples/learn` | ACHIEVABLE | IMPOSSIBLE (`read_me`, `show_widget`) |
| `examples/mcp-builder` | ACHIEVABLE | ACHIEVABLE |
| `examples/meal-delivery` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/morning` | ACHIEVABLE | ACHIEVABLE |
| `examples/paint` | ACHIEVABLE | IMPOSSIBLE (`bash_tool`, `present_files`) |
| `examples/prescription-refill` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/return-refund` | ACHIEVABLE | IMPOSSIBLE (`ask_user_input_v0`) |
| `examples/setup-writing-style` | ACHIEVABLE | IMPOSSIBLE (`search_mcp_registry`) |
| `examples/skill-creator` | ACHIEVABLE | ACHIEVABLE |
| `examples/slack-gif-creator` | ACHIEVABLE | ACHIEVABLE |
| `examples/theme-factory` | ACHIEVABLE | ACHIEVABLE |
| `examples/web-artifacts-builder` | ACHIEVABLE | ACHIEVABLE |
| `public/docx` | ACHIEVABLE | ACHIEVABLE |
| `public/file-reading` | ACHIEVABLE | ACHIEVABLE |
| `public/frontend-design` | ACHIEVABLE | ACHIEVABLE |
| `public/pdf` | ACHIEVABLE | ACHIEVABLE |
| `public/pdf-reading` | ACHIEVABLE | ACHIEVABLE |
| `public/pptx` | ACHIEVABLE | ACHIEVABLE |
| `public/product-self-knowledge` | ACHIEVABLE | ACHIEVABLE |
| `public/xlsx` | ACHIEVABLE | ACHIEVABLE |

**Totals:** 42/42 achievable under `claude-ai`, 24/42 achievable under `claude-code`

## With equivalent tool names (the default since skillc counts them)

The table above was measured with exact tool names (now `--exact-tool-names`). skillc now
also counts a tool that does the same job under another name
(`src/skillc/data/tool_equivalents.json`). The corpus (claude.ai's built-in skills folder)
is not available in this repository, so the totals below are derived from the recorded
frontiers above, not re-run. The derivation is exact for these skills because, as the
real-skill tests check, granting a refuted skill's frontier tools always flips it to
ACHIEVABLE: a skill flips exactly when every frontier tool has a Claude Code equivalent.

* Flip to ACHIEVABLE (12): `call-to-book`, `cancel-unsubscribe`, `event-planning`,
  `file-expenses`, `file-form`, `financial-calculator`, `grocery-shopping`, `hire-help`,
  `meal-delivery`, `prescription-refill`, `return-refund` (`ask_user_input_v0` =
  `AskUserQuestion`) and `doc-coauthoring` (`create_file` = `Write`, `str_replace` = `Edit`).
* Stay IMPOSSIBLE (6), a tool Claude Code lacks under every name: `benepass-reimbursement`
  (`read_page`, `upload_file`), `built-in-browser` (`tabs_context`), `chrome-browser`
  (`tabs_context_mcp`), `learn` (`read_me`, `show_widget`), `paint` (`present_files`; its
  `bash_tool` is Claude Code's `Bash`), `setup-writing-style` (`search_mcp_registry`).

**Totals with equivalents:** 42/42 achievable under `claude-ai`, 36/42 achievable under
`claude-code`. Regenerating the table with `scripts/make_report.py` now uses equivalents.
