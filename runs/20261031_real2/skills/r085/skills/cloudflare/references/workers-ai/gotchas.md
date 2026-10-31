# Workers AI Troubleshooting

Use the actual error, model identifier, integration, and installed versions to choose the relevant reference.

| Symptom or decision | Documentation and checks |
|---------------------|--------------------------|
| Missing binding or types | [Binding configuration]([url-1]) and [Workers TypeScript]([url-2]); check the environment being run |
| Development inference fails | [Workers and Wrangler setup]([url-3]); check account access and binding setup |
| Unknown model, invalid input, or unexpected response | Open the exact model in the [catalog]([url-4]); check its schema, context window, and feature support |
| Inference error or retry decision | [Error codes and HTTP statuses]([url-5]) |
| Throttling or concurrency planning | [Current limits]([url-6]) |
| Usage or cost estimate | [Current pricing]([url-7]); use the selected model's billing units and expected workload |
| Old SDK examples fail | [Native binding]([url-1]), [AI SDK]([url-8]), or [OpenAI compatibility]([url-9]), according to the integration |

Do not copy an error-code mapping, per-request neuron estimate, or context-window range from another model or an older example. Measure latency for the intended workload rather than promising a fixed cold-start or inference time.
