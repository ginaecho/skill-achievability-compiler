---
name: ics-calendar-builder
description: Turn a conference schedule spreadsheet into an importable .ics calendar file.
---
# Schedule to calendar

1. Read `schedule.csv` (title, date, start, end, room, speaker).
2. Build one VEVENT per session with the Python `ics` package, time zone Europe/Berlin, room as LOCATION and speaker in DESCRIPTION.
3. Write `conference.ics` and validate that it parses back with the same number of events.
