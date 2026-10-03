"""Environment topology: what a principal can do, and what an intent can reach.

    model    the provider-neutral graph (skillc.env/1), merge and diff
    facts    three-valued permission / policy / service / tool facts
    azure    read-only Azure probe (live az, or replayed from an export)
    mcp      MCP servers and their tools
    reach    intent -> achievable conditions, verified plan, blockers
    report   text, English plan, HTML
    watch    the scheduled re-probe
"""
