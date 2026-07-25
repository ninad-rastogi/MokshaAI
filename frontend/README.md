# Moksha AI Frontend

## Purpose

Nuxt 4, Vue 3, strict TypeScript product frontend for Moksha AI.

## Architecture And Data Flow

The browser uses Django session cookies and CSRF for first-party auth. Chat requests create durable generation runs through `/api/v1/chats/{chat_id}/runs/`, then consume typed Server-Sent Events from `/api/v1/chats/runs/{run_id}/events/`.

## Files And Entrypoints

- `pages/index.vue`: SSR welcome and auth entry.
- `pages/app.vue`: authenticated chat workspace.
- `composables/useApi.ts`: schema-validated API client.
- `composables/useRunStream.ts`: handwritten SSE adapter.

## Interfaces

Consumes the Django `/api/v1` REST API. Browser code must not store bearer tokens in local storage.

## Configuration

Set `NUXT_PUBLIC_API_BASE` when the API is not served from the same origin.

## Commands

- `npm run dev`
- `npm run build`
- `npm run typecheck`
- `npm run lint`
- `npm run test`

## Tests

Use Vitest for component logic and Playwright for critical browser journeys.

## Dependencies

Nuxt UI 4, Tailwind through Nuxt UI, Zod, Marked, DOMPurify.

## Security

Markdown rendering disables raw HTML through sanitization. Auth uses cookies and CSRF, not browser local-storage tokens.

## Failure Modes And Troubleshooting

If streaming disconnects, reconnect with the last seen event id. If the API returns 401, return to the welcome screen and sign in again.

## Related Docs

See the root README and `chat/README.md`.
