---
name: skillc-check
description: "Check a task with skillc before acting, and stop and re-plan when skillc finds the plan cannot succeed here. Use for any task that runs commands, writes or edits files, sends messages, or changes anything outside the conversation, and whenever the user mentions skillc."
---

# skillc check: stop, explain, re-plan

skillc decides, without a model, whether a plan can succeed in this runtime
(Microsoft Scout on this PC). It gives a proof when a plan cannot succeed, and it says
who can fix the problem. Use its tools from the `skillc` MCP server.

## Steps

1. **Start.** Call `skillc_start` with the user's request, in the user's words. Read
   all of the answer: it tells you how to write the plan, which operations need the
   user's approval, whether the plan is owned by the host (strict mode), and which
   requirements of the request this runtime cannot meet.
2. **Plan before you act.** Write the plan in SkillC Controlled English (the grammar
   is in the answer of `skillc_start`) and submit it with `skillc_check_plan`. Do not
   run commands, write files or send messages until a plan gets `DECISION: allow`.
   In strict mode the host already supplied the plan: do not try to replace it.
3. **Get approval for protected operations.** When `skillc_start` lists protected
   operations (for example `teams_message`), first call `skillc_request_approval` with
   the tool, every destination (comma-separated) and the exact content. skillc asks
   the user directly; you cannot approve it yourself. Use the returned `APPROVAL`
   once. Any change to the content, recipients or source needs a new approval.
4. **Check each action.** Before each action, call `skillc_check_action` with the tool
   (for example `powershell`, `write`, `edit`, `browser`, `workiq`,
   `m_send_teams_message`; in strict mode the plan's Tool name) and the command or
   exact content. For a protected operation also pass `approval` and `destinations`.
   Then perform exactly that action, unchanged. After it, call `skillc_report_result`
   with what it printed, errors included.
5. **Check a change of course.** When your reasoning turns to a new approach, call
   `skillc_check_reasoning` with one or two sentences of what you now intend.

## What to do with an answer

Every answer starts with a line such as
`DECISION: deny   NEXT: ask_user   USER_NEEDS: aws_account`.

| answer | what you do |
|---|---|
| `DECISION: allow` | Go ahead, exactly as checked. |
| `DECISION: warn` | skillc asks a question or reports a fact. Answer it for yourself. If what it found is part of your intent, change the plan before you go on. |
| `DECISION: deny`, `NEXT: replan` | Do not take that step. Change the plan as the answer says and submit it again. |
| `DECISION: deny`, `NEXT: ask_user` | Do not take that step, and do not try to get around it. Tell the user, in plain words, what skillc found and what is missing (`USER_NEEDS`). Ask how to proceed: provide what is missing, or accept a smaller goal. |

Always tell the user when skillc stopped a step, with skillc's reason. Do not hide a
refusal, and do not do the same work by another route that skillc did not check.
Never run `skillc` commands, edit skillc's state, or change its configuration to
obtain an approval or an allow: that is circumventing the user's control.

## Example plan

```
Skill `weekly-report`.
Roles: `agent`.
Tool `read_notes` (owner `agent`): via `read`; adds `notes_read`.
Tool `write_report` (owner `agent`): via `write`; requires `notes_read`; adds `report_written`.
Tool `send_to_team` (owner `agent`): via `teams_message`; effect `writes_external`; requires `report_written`; adds `sent`.
Goal: `report_written`.
Protocol:
  - `agent` uses `read_notes`.
  - `agent` uses `write_report`.
  - `agent` chooses one of (observed):
    - branch `send`:
      - `agent` uses `send_to_team`.
    - branch `skip`: none.
```
