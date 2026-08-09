# Moksha AI Frontend

## Purpose

Nuxt 4, Vue 3, strict TypeScript product frontend for Moksha AI.

## Architecture And Data Flow

The browser uses Django session cookies and CSRF for first-party auth. Chat requests create durable generation runs through `/api/v1/chats/{chat_id}/runs/`, then consume typed Server-Sent Events from `/api/v1/runs/{run_id}/events/`.

## Files And Entrypoints

- `pages/index.vue`: SSR welcome and auth entry.
- `pages/app.vue`: authenticated chat workspace.
- `composables/useApi.ts`: schema-validated API client.
- `composables/useRunStream.ts`: handwritten SSE adapter.
- `components/app/`: compact chat shell, history actions, composer, settings.
- `openapi.json`: generated canonical v1 REST schema.
- `types/openapi.d.ts`: generated REST types; never hand-edit.

## Interfaces

Consumes Django `/api/v1`. Sessions survive refresh through HttpOnly cookies
and `/auth/me/`. History supports search, rename, archive, restore, and delete.
Enter sends; Shift+Enter inserts a newline. Composer and navigation remain
fixed while only message history scrolls. Archived chats have no composer.

## Configuration

Set `NUXT_PUBLIC_API_BASE` only when API is not same-origin. Theme, primary
profile, optional fallback, and provider connections persist through account
APIs, not local storage. System/light/dark theme follows account preference.
`NUXT_API_PROXY` defaults to `http://127.0.0.1:8000` for direct local Nuxt
access. Caddy routes `/api/v1/*` directly to Django in deployed environments.

## Commands

- `npm run dev`
- `npm run build`
- `npm run typecheck`
- `npm run lint`
- `npm run stylelint`
- `npm run format`
- `npm run test`
- `npm run generate:types`
- `npm run build`

## Tests

Use Vitest/Vue Test Utils for components and
`python ../scripts/live_ui_walkthrough.py` for Chrome journeys at desktop and
mobile sizes. Walkthrough must cover auth/refresh, Enter and Shift+Enter,
stream/cancel/reconnect states, history actions, every settings section,
preference persistence, archived behavior, focus, reduced motion, and axe.

## Dependencies

Nuxt UI 4, Tailwind through Nuxt UI, Zod, Marked, DOMPurify.

## Security

Markdown rendering disables raw HTML through sanitization. Auth uses cookies and CSRF, not browser local-storage tokens.

## Failure Modes And Troubleshooting

- 401 after refresh: inspect session/CSRF cookies and `/auth/me/`; do not add a
  token-storage fallback.
- Streaming disconnect: replay from last validated event ID; completed durable
  DB checkpoint is final fallback.
- Native select theme mismatch: use Nuxt UI menu/listbox styling, not unstyled
  platform select.
- Page scroll or hidden composer: shell must stay `100svh`; only message/history
  viewports scroll.

## Related Docs

See the root README and `chat/README.md`.
