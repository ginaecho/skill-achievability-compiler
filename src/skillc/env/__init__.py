"""Environment topology: what a principal can do, and what an intent can reach.

    model    the provider-neutral graph (skillc.env/1), merge and diff
    facts    three-valued permission / policy / service / tool facts
    azure    read-only Azure probe (live az, or replayed from an export)
    azd      the environment an azd project declares in its azure.yaml (offline)
    foundry  read-only probe of a deployed hosted agent's control plane (or a replay)
    mcp      MCP servers and their tools
    selfprobe  the data-plane half read from inside a hosted agent's sandbox; merge_hosted
    reach    intent -> achievable conditions, verified plan, blockers
    report   text, English plan, HTML
    watch    the scheduled re-probe
"""
