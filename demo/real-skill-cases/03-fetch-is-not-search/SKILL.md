---
name: fetch-is-not-search
description: Research an open-ended topic using only the MCP reference fetch tool.
source: https://github.com/modelcontextprotocol/servers/blob/main/src/fetch/README.md
---

# Open-ended research with a retrieval-only tool

The MCP reference server retrieves a supplied URL; it does not discover URLs.
This deployment asks for web search but declares no search capability.

```skillc-pack
{
  "name": "fetch-is-not-search",
  "roles": ["orchestrator", "worker"],
  "capabilities": {
    "fetch_url": {
      "owner": "worker",
      "pre": "url_known",
      "add": ["page_fetched"]
    },
    "synthesize_report": {
      "owner": "orchestrator",
      "pre": "page_fetched",
      "add": ["report_delivered"]
    }
  },
  "protocol": [
    {"act": {"cap": "search_web", "by": "orchestrator"}},
    {"msg": {"from": "orchestrator", "to": "worker", "label": "url_found"}},
    {"act": {"cap": "fetch_url", "by": "worker"}},
    {"msg": {"from": "worker", "to": "orchestrator", "label": "page_content"}},
    {"act": {"cap": "synthesize_report", "by": "orchestrator"}}
  ],
  "goal": "report_delivered"
}
```

