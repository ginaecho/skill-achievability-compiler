# Skills written for one runtime, checked in others

Two small made-up skills for the README examples:

* `pick-an-evening` uses claude.ai's tool names (`ask_user_input_v0`, `web_search`). Copilot CLI
  and Claude Code have the same tools under other names (`ask_user`, `AskUserQuestion`,
  `WebSearch`), so skillc finds it ACHIEVABLE there too; with `--exact-tool-names` it does not.
  VS Code Copilot has no web search.
* `quiz-widget` uses `show_widget`, which only claude.ai has. It is IMPOSSIBLE elsewhere under
  every name.

```console
skillc check examples/runtime-skills/pick-an-evening/SKILL.md
skillc check examples/runtime-skills/pick-an-evening/SKILL.md --exact-tool-names
skillc check examples/runtime-skills/quiz-widget/SKILL.md --profile claude-ai
skillc check examples/runtime-skills/quiz-widget/SKILL.md
```
