"""Adapters that attach the runtime monitor to agent frameworks.

Each module here imports its framework inside itself, so that the core package keeps its
two dependencies and a missing framework is an ImportError of that module only:

  agent_framework   Microsoft Agent Framework middleware (`skillc[agent-framework]`), the
                    attachment for Foundry hosted agents (docs/HOSTED_AGENT.md).
"""
