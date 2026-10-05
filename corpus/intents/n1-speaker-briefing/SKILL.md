---
name: speaker-briefing-flow
description: Reserve a stage, brief speakers, and publish the event schedule.
allowed-tools: [reserve_stage, send_briefing, publish_schedule]
---
# Prepare speaker stage schedule

Use this procedure for event operations before a speaker session.

Tools: `reserve_stage`, `send_briefing`, `publish_schedule`.

## Workflow
1. Run `reserve_stage` for the session stage.
2. Run `send_briefing` for the speaker information.
3. Run `publish_schedule` for the event schedule.

You are finished when the stage is **reserved**, the speaker is **briefed**, and the schedule is **published**.
