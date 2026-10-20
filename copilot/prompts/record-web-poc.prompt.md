---
agent: "agent"
description: "Inspects a web service or localhost PoC, injects dummy data, and records an MP4 and GIF walkthrough using the poc-recorder MCP. Usage: /record-web-poc <url> [output_path]"
argument-hint: "<url> [output_path]"
tools: ['poc-recorder/*']
---

# Record Web PoC

You are the general Copilot agent executing the `/record-web-poc` workflow using the `poc-recorder` MCP server tools.

## Mandatory Flow

1. Call `inspect-page` on the target URL (e.g. `http://localhost:47891`) to discover its title, headings, tabs, buttons, inputs, and `localStorage` keys.
2. Design a clean, client-ready walkthrough choreography (`steps`) that exercises the core tabs, filters, modals, and interactions of the web application.
3. If dummy data is requested, inject synthetic corporate/demo data via `local_storage`, `mock_routes`, `html_replacements`, or `post_load_js` so real data is never shown.
4. Call `record-poc` with `format: "both"` (or the user's preferred format) to produce `.mp4` and `.gif` files.
5. Return the generated artifact paths, file sizes, step summary, and total duration.
