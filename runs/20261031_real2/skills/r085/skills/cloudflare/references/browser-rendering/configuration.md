# Browser Run Configuration

Check the project's runtime, installed client and Wrangler versions, and compatibility date before adapting setup instructions. Cloudflare's packages for Workers and standard clients connecting over CDP have different setup requirements.

| Task | Documentation |
|------|---------------|
| Start a project or configure REST authentication | [Get started]([url-1]) — Quick Actions and browser session setup |
| Configure a Worker or choose a development mode | [Wrangler reference]([url-2]) — browser bindings, compatibility requirements, and local/remote development |
| Install or update a Workers browser client | [Puppeteer]([url-3]) or [Playwright]([url-4]) — package-specific setup and supported versions |
| Connect from a script, server, or CI outside Workers | [CDP]([url-5]) — authentication and client integration guides |

Development support depends on the selected interface. Follow its current guidance rather than applying one remote-mode requirement to all Browser Run workflows.
