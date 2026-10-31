# Containers troubleshooting

Use the current documentation to diagnose behavior instead of relying on copied timeout values, resource limits, or lifecycle recipes.

| Symptom or concern | Documentation to read |
| --- | --- |
| Startup timeout or unavailable port | [Start and stop]([url-1]), [Container properties]([url-2]), and [first-deploy provisioning]([url-3]) |
| WebSocket forwarding fails | [WebSocket example]([url-4]) and [request methods]([url-5]) |
| Background work stops on idle expiry | [Activity renewal]([url-6]) and [idle expiry hook]([url-7]) |
| Scheduled callbacks do not run | [Scheduling and alarm ownership]([url-8]) |
| Shutdown cleanup or filesystem data loss | [Container shutdown and disk lifecycle]([url-9]) |
| Out-of-memory errors or resource exhaustion | [FAQ]([url-10]) and [limits and instance types]([url-11]) |
| Instance count exceeded or unexpected request distribution | [Wrangler configuration]([url-12]) and [scaling and routing]([url-13]) |
| Worker and container image versions differ after deployment | [Deployment behavior]([url-14]) and [rollouts]([url-15]) |
| Local behavior differs from deployed behavior | [Local development]([url-16]) |
| Logs, cold starts, or runtime availability questions | [FAQ]([url-10]) |
