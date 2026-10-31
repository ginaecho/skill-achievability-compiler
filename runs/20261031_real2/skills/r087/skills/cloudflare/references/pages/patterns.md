# Pages Project Decisions

Keep project-specific choices here; fetch framework adapters, configuration, and code examples from the docs.

| Task | Documentation |
| --- | --- |
| Maintain a framework deployment | [Framework guides]([url-1]) |
| Deploy from an external build pipeline | [Direct Upload]([url-2]) |
| Manage multiple apps in one repository | [Monorepos]([url-3]) |
| Evaluate backend locality | [Smart Placement]([url-4]) |
| Plan a move to Workers | [Migrate from Pages to Workers]([url-5]) |

Check the existing build command, adapter, and output ownership together. Evaluate placement using the application’s backend dependencies and measured latency. For a migration, inventory routes, middleware, bindings, static rules, and deployment settings before following the migration guide.

See [Pages Functions patterns](../pages-functions/patterns.md) for request-level decisions.
