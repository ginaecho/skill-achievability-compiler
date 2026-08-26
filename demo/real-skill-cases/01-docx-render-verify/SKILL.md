---
name: docx-render-verify
description: Create a DOCX file, render it, and inspect the rendered pages before delivery.
source: https://github.com/anthropics/skills/blob/main/skills/docx/SKILL.md
---

# DOCX render-and-verify workflow

This is a compact declaration of the source skill's create, render, and visual
verification chain. It does not reproduce the proprietary skill body.

```skillc-pack
{
  "name": "docx-render-verify",
  "roles": ["document_agent"],
  "capabilities": {
    "write_docx": {
      "owner": "document_agent",
      "add": ["draft_written"]
    },
    "render_docx": {
      "owner": "document_agent",
      "pre": "draft_written",
      "add": ["rendered"]
    },
    "inspect_rendered_pages": {
      "owner": "document_agent",
      "pre": "rendered",
      "add": ["verified"]
    }
  },
  "protocol": [
    {"act": {"cap": "write_docx", "by": "document_agent"}},
    {"act": {"cap": "render_docx", "by": "document_agent"}},
    {"act": {"cap": "inspect_rendered_pages", "by": "document_agent"}},
    {"goal": {"and": ["draft_written", "verified"]}}
  ],
  "goal": {"and": ["draft_written", "verified"]}
}
```

