# Workers AI API

Fetch the selected model's page from the [model catalog]([url-1]) for request fields, output format, dimensions, and examples. Text, embeddings, images, audio, and translation do not share one response schema.

| Task | Documentation |
|------|---------------|
| Invoke inference through a Worker binding | [Workers bindings]([url-2]) |
| Invoke inference over HTTP | [REST API reference]([url-3]) |
| Stream text or use SDK abstractions | [Vercel AI SDK]([url-4]), or the selected model's streaming example |
| Define tools and handle tool results | [Function calling]([url-5]) |
| Request structured output | [JSON mode]([url-6]) |

Use the response and stream format documented for the chosen integration. Do not assume native binding streams are parsed objects or apply OpenAI response parsing to every model. Check the model's batching support and limits before combining inputs in one request.
