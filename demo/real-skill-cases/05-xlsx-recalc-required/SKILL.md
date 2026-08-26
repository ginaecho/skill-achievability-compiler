---
name: xlsx-recalculation-required
description: Write a spreadsheet with formulas in a sandbox that lacks recalculation and verification.
source: https://github.com/anthropics/skills/blob/main/skills/xlsx/SKILL.md
---

# Spreadsheet formula verification

The source skill requires recalculation before a formula-bearing workbook may
ship. This restricted deployment can write formulas but cannot establish the
required verified result.

```skillc-pack
{
  "name": "xlsx-recalculation-required",
  "roles": ["spreadsheet_agent"],
  "capabilities": {
    "write_formulas": {
      "owner": "spreadsheet_agent",
      "add": ["draft_written"]
    }
  },
  "protocol": [
    {"act": {"cap": "write_formulas", "by": "spreadsheet_agent"}}
  ],
  "goal": {"and": ["draft_written", "verified"]}
}
```

