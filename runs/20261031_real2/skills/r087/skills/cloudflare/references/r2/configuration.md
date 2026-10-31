# R2 Configuration

Fetch the task's documentation before editing Wrangler configuration or bucket settings.

| Task | Current documentation |
|------|-----------------------|
| Create a bucket and bind it to a Worker | [Workers API setup]([url-1]) |
| Choose local simulation or a remote bucket during development | [Supported bindings per development mode]([url-2]) and [local development]([url-3]) |
| Create S3 credentials and scope permissions | [R2 authentication]([url-4]) |
| Set the S3 endpoint and SDK region | [AWS SDK for JavaScript v3]([url-5]) |
| Choose placement hints or a jurisdiction | [Data location]([url-6]) |
| Configure browser origins, methods, and headers | [CORS]([url-7]) |
| Set expiration, storage transitions, or incomplete-upload cleanup | [Object lifecycles]([url-8]) |
| Choose or change storage classes | [Storage classes]([url-9]) and [pricing]([url-10]) |
| Send object events to a queue | [Event notifications]([url-11]) |
| Configure public access or a custom domain | [Public buckets]([url-12]) |
| Manage bucket settings with Wrangler | [R2 commands]([url-13]) |

Choose the development bucket deliberately: a remote binding accesses real data. Scope S3 credentials to the required buckets and operations; Workers bindings use their own access mechanism. Review lifecycle prefixes and retention needs before applying deletion rules, and evaluate retrieval and minimum-storage charges before choosing a storage class.
