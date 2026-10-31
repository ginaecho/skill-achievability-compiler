# WAF Configuration

Identify the account or zone, existing rulesets, and the system managing them before choosing a deployment method. Use the permission requirements in the selected workflow rather than a copied token-permission list.

| Task | Documentation |
|------|---------------|
| Enable protections and configure them in the dashboard | [WAF get started]([url-1]) |
| Configure custom rules through the API or SDK | [Custom rules API workflow]([url-2]) |
| Configure managed rules through the API or SDK | [Managed rules API workflow]([url-3]) |
| Configure rate limiting through the API or SDK | [Rate limiting API workflow]([url-4]) |
| Manage custom rules with Terraform | [Custom rules Terraform guide]([url-5]) |
| Manage managed rulesets with Terraform | [Managed rules Terraform guide]([url-6]) |
| Manage rate limits with Terraform | [Rate limiting Terraform guide]([url-7]) |
| Decide account versus zone placement and phase | [WAF phases]([url-8]) |

When adopting existing rules into Terraform, follow the selected guide's import instructions and inspect the plan for unintended removals. Keep the existing management tool when it fits the task. For SDK or Pulumi projects, verify the installed package's types before translating the documented API workflow.

Continue with [patterns.md](patterns.md) for protection choices and [gotchas.md](gotchas.md) for diagnostics.
