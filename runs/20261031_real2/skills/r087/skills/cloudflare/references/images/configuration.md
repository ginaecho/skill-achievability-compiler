# Images Configuration

Inspect the project's Wrangler configuration, dependency versions, existing bindings, and credential storage before changing setup. Preserve its configuration format and generate binding types through its existing tooling.

| Task | Documentation |
|------|---------------|
| Add the optimization binding | [Binding setup]([url-1]) |
| Configure hosted-image management in a Worker | [Hosted binding setup]([url-2]) |
| Choose local or remote development for the optimization binding | [Local binding development]([url-3]) |
| Upload through the dashboard or API | [Upload methods]([url-4]) |
| Create named presets for hosted images | [Create predefined variants]([url-5]) |
| Enable dynamic options for hosted-image URLs | [Enable flexible variants]([url-6]) |
| Find account hash and delivery URL components | [Serve uploaded images]([url-7]) |
| Configure private access and generate signed URLs | [Serve private images]([url-8]) |
| Set hosted-image cache lifetime | [Browser TTL]([url-9]) |

Keep API tokens and signing keys in the project's secret mechanism. Verify private-delivery requirements when choosing variants, and follow the documented signing procedure rather than maintaining a custom signing recipe here. Confirm that the selected local test mode covers the features being changed. Continue with [API selection](api.md) or [patterns](patterns.md).
