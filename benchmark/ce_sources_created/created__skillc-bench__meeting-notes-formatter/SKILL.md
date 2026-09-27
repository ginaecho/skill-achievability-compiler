---
name: meeting-notes-formatter
description: Rewrite raw meeting notes into the team's FOCUS-5 format for the weekly digest.
---
# FOCUS-5 meeting notes

FOCUS-5 is our house format. Every note has exactly five headed sections, in this order:
**F**acts (what was reported), **O**utcomes (decisions), **C**oncerns (risks raised),
**U**pcoming (actions with owner and date), **S**ummary (one sentence).

## Steps
1. Read the raw notes the user provides (`raw_notes.txt`).
2. Sort every statement into one of the five sections; actions must have an owner and a date, ask the user if missing.
3. Write `notes_focus5.md`.
