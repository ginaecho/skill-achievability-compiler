---
name: aspire-target-deployment
description: Publish an Aspire application and deploy it to an Azure or Kubernetes target.
allowed-tools: [aspire_publish, aspire_deploy_azure, kubectl_apply]
---

# Aspire Target Deployment

Use this procedure after an Aspire app has already been verified locally and stopped, and the goal is to ship it to a configured target.

Tools: `aspire_publish`, `aspire_deploy_azure`, `kubectl_apply`.

## Workflow

1. Use `aspire_publish` to generate the deployment artifacts for the AppHost.
2. Choose one target path for the release: `aspire_deploy_azure` for Azure or `kubectl_apply` for Kubernetes.
3. Apply the selected deployment path and capture the resulting target status.
4. Report which target received the deployed application.

You are finished when the Aspire application is **deployed to Azure** or **deployed to Kubernetes**.
