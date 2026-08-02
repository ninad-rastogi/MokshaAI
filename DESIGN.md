# Moksha AI Design System

## Purpose

Moksha AI provides a private, listening-first space for people carrying difficult
thoughts or emotions. The interface must feel calm during hard moments, preserve
familiar chat workflows, and make scripture-grounded evidence, model state, and
account state easy to inspect without presenting the product as a substitute for
human, medical, or emergency support.

This document records the production design implemented in the Nuxt interface.
Treat the CSS variables in `frontend/assets/css/main.css` and the listed Vue
components as the source of truth.

## Design Principles

1. **Listen before advising.** Lead with an open prompt and quiet space, not a
   feature tour or religious spectacle.
2. **Make trust visible.** Show citations, generation state, model readiness,
   session security, archived state, consent, and honest errors near the action
   they affect.
3. **Keep work familiar.** Use a history rail, compact header, centered message
   thread, docked composer, standard icons, and explicit destructive
   confirmations.
4. **Use spiritual character through detail.** Preserve the lotus/Om mark and
   use forest neutrals, warm metal accents, manuscript-like reading measure, and
   restrained material depth. Avoid literal temple decoration.
5. **Prefer calm density.** Keep type and controls compact, maintain generous
   reading line height, and reserve larger type for welcome and empty states.
6. **Adapt without losing structure.** Mobile layouts preserve the same actions
   and settings hierarchy while changing placement and density.

## Visual Direction

The visual language is contemporary, soothing, and premium with an ancient
Indian undertone. Light mode uses cool mineral greens and off-whites; dark mode
uses near-black forest surfaces. Warm bronze/gold carries emphasis, while deep
green or warm gold carries primary actions according to theme.

Backgrounds use shallow linear tonal shifts. Glass depth comes from translucent
tokenized surfaces, one-pixel borders, selective blur, and soft shadows. The
brand mark appears as a compact identity or guide marker, never as oversized
decoration. Do not introduce background grids, large cursor blobs, gradient
orbs, oversized typography, or pasted product explanations.

## Typography

- Primary stack: `"Manrope Variable"`, `"Noto Sans Devanagari Variable"`,
  `"Nirmala UI"`, `"Segoe UI"`, `sans-serif`.
- Manrope carries the contemporary interface. Noto Sans Devanagari and system
  fallbacks keep Hindi, Sanskrit, and mixed-script content legible.
- Body and message copy use regular sentence case, zero letter spacing, and no
  synthesized font styles.
- Message text is `0.9rem/1.68` on desktop and `0.86rem` on small screens.
  Composer text is `0.9rem/1.5`.
- Operational labels generally range from `0.65rem` to `0.82rem`; section
  headings use about `1rem`; empty-state headings use `1.2rem` to `1.45rem`.
  The authentication heading is the largest production type at `1.75rem`
  (`1.5rem` below 520px).
- Use weights from roughly 620 to 760 for hierarchy. Use uppercase only for
  small model-group labels; keep letter spacing at `0`.
- Use monospace only for technical identifiers such as model IDs.

## Color Tokens

Use semantic tokens rather than literal colors in components.

| Role | Light | Dark |
| --- | --- | --- |
| Background / deep | `#edf0ed` / `#e3e8e4` | `#101411` / `#0b100d` |
| Ink / muted / placeholder | `#17211c` / `#5c6861` / `#748078` | `#edf3ed` / `#9baaa0` / `#7f8f85` |
| Line | `#c9d0cb` | `#28352e` |
| Surface / raised | `#f5f7f4` / `#fcfcfa` | `#111915` / `#18221d` |
| Sidebar | `rgb(245 247 244 / 88%)` | `rgb(18 24 20 / 90%)` |
| Header | `rgb(250 251 248 / 82%)` | `rgb(18 24 20 / 84%)` |
| Modal | `rgb(250 251 248 / 99%)` | `rgb(20 27 22 / 99%)` |
| Settings navigation | `rgb(235 239 235 / 92%)` | `rgb(14 20 16 / 94%)` |
| Control | `rgb(255 255 255 / 62%)` | `rgb(255 255 255 / 5%)` |
| Glass / raised | `rgb(251 252 249 / 68%)` / `rgb(255 255 253 / 86%)` | `rgb(25 33 28 / 70%)` / `rgb(255 255 255 / 8%)` |
| Glass line | `rgb(40 58 48 / 16%)` | `rgb(222 235 225 / 13%)` |
| Composer | `rgb(252 252 249 / 91%)` | `rgb(24 31 27 / 94%)` |
| Accent / accent ink | `#9b6527` / `#6e410f` | `#d7a060` / `#f0c58d` |
| Primary / primary ink | `#244c3c` / `#f7fbf7` | `#d8b178` / `#1b211d` |
| User bubble / ink | `#dce6df` / `#17251e` | `#264638` / `#f0f5f0` |
| Guide mark | `#17352a` | `#d8b178` |
| Focus | `#8b5c25` | `#d7a060` |
| Success / warning / error / info | `#2e7252` / `#9a641e` / `#a23f3f` / `#28647c` | `#7fc29d` / `#e2ad60` / `#ef9292` / `#81c3dc` |
| Disabled | `#d8ded9` | `#2b3731` |

Soft, line, and focus-ring variants accompany accent, success, error, and info
tokens. Selection uses the soft accent. Status must pair color with an icon,
dot, label, or state text.

## Spacing and Sizing

- Base corner radius is `0.5rem`. Most controls and list rows use
  `0.45rem`-`0.7rem`; the asymmetric user bubble is the deliberate exception.
- Use compact gaps of `0.2rem`-`0.45rem` within controls, `0.5rem`-`0.85rem`
  between related elements, and `1rem`-`1.55rem` between major content groups.
- Compact icon controls are normally `1.8rem`-`2.2rem` square. Inputs and
  command buttons are normally `2.35rem`-`2.7rem` high.
- Message rows, status banners, and the composer share a `48rem` maximum width.
  User messages cap at `35rem` or 82% of the thread width, increasing to 88% on
  small screens.
- Desktop history is `15.5rem` wide. The header is `3.55rem` high, reduced to
  `3.35rem` below 600px.
- Authentication uses a `27rem` panel. Settings use a `46rem` by at most
  `42rem` dialog with a `10.5rem` navigation column.
- Use `100svh`, `minmax(0, 1fr)`, bounded measures, ellipsis, and safe-area
  padding to prevent dynamic content from shifting or escaping the shell.

## Layout Behavior

The application is a fixed-height workspace. Desktop uses a persistent history
rail and a three-row chat shell: header, independently scrolling message
viewport, and docked composer. The page body does not scroll.

Messages remain centered within the reading measure. Assistant responses use a
guide mark plus unframed content; user messages align right in a distinct
bubble. The composer sits over a tonal fade and retains bottom safe-area space.
Authentication centers one focused panel beneath a fixed brand/theme header.

Empty, loading, archived, disconnected, streaming, error, and confirmation
states are first-class layouts. Do not replace them with generic toast-only
feedback.

## Glass and Material

- Apply glass only to structural or interactive layers: authentication panel,
  header, composer, settings dialog, banners, selected/raised controls, and
  modal overlay.
- Build depth with a tokenized translucent fill, `--moksha-glass-line`,
  restrained blur/saturation, and one shadow. Do not nest decorative cards.
- Typical blur ranges from 18px to 30px. The modal overlay darkens and blurs the
  background; the composer and modal receive the strongest elevation shadows.
- Use 1px borders and shallow highlights. Avoid glossy glare, heavy bevels,
  thick borders, and multiple competing shadows.
- Under `prefers-reduced-transparency`, structural surface tokens become opaque.
  The chat header and banners also remove backdrop blur. New glass components
  must provide an equally legible opaque fallback.

## Motion and Pointer Light

Authentication and workspace backgrounds carry a subtle 50-52px radial
reflection centered on CSS pointer coordinates. Pointer updates run through
`requestAnimationFrame`, ignore touch input, and never intercept events. Hide
the reflection for coarse/no-hover pointers and for reduced motion.

Motion communicates state: short 1px-2px hover lift, a 220ms mobile-rail slide,
breathing generation dots, spinner rotation, and streaming caret pulse. Keep
motion local and brief; never use large cursor-following shapes or ornamental
parallax.

`prefers-reduced-motion: reduce` globally reduces animation and transition
durations to `0.01ms`, disables smooth scrolling, and removes pointer light.
Every new transition or animation must remain understandable when effectively
instant.

## Component Patterns

- **Authentication:** sign-in/create-account tabs, labeled fields, password
  reveal icon, contextual alert, one primary continuation action, and session
  assurance.
- **History rail:** brand, new conversation command, search, Recent/Archived
  tabs, compact conversation rows, overflow actions, account/model summary, and
  theme control. `Ctrl/Cmd+K` creates or selects a draft.
- **Header:** truncated conversation title, short trust/state subtitle,
  generation status, reconnect action, and settings action.
- **Conversation:** assistant content is open and readable; user content is a
  right-aligned bubble. Citations stay attached to assistant content.
- **Composer:** auto-growing prompt up to five rows, model state, keyboard hint,
  icon-only send/stop action with tooltip and accessible name, and persistent
  caution or error text.
- **Controls:** use Lucide icons for familiar actions, segmented controls or
  radio groups for exclusive choices, native checkbox/radio/select controls
  where appropriate, and labeled text buttons for clear commands.
- **Destructive actions:** use error color, state permanence in plain language,
  and require a confirmation modal.

## Settings Information Architecture

Keep these five sections and their order:

1. **General:** account-synced System/Light/Dark appearance and device-governed
   motion.
2. **Models:** local and API model groups, availability state, primary model,
   optional fallback, context information, and billing caveat.
3. **Connections:** connected provider status, connection check/removal, API
   dialect, HTTPS endpoint, model ID, API key, and explicit remote-data consent.
4. **Scriptures:** indexed collection count, collection metadata, and
   Indexed/Pending state.
5. **Account:** signed-in identity, session security, and sign out.

Keep model choice separate from provider credentials. Do not imply that a
consumer subscription grants API access. Keep consent adjacent to connection
creation and explain that prompts and retrieved context may leave the device.

## Responsive Breakpoints

- **860px:** replace the persistent history rail with an inert, modal-style
  off-canvas dialog and scrim; expose the header menu; keep item actions visible.
- **680px:** make settings full-screen; change the left navigation to five
  horizontally scrollable icon-and-label tabs; stack fields and setting rows.
- **600px:** tighten header and messages, hide secondary keyboard hints, reduce
  assistant mark/type, stack starter prompts, wrap archive actions, and preserve
  the composer.
- **520px:** top-align the authentication surface, reduce padding and heading
  size, and let the panel use the narrow viewport.

Use capability queries in addition to width: coarse/no-hover input removes
pointer light, and device accessibility preferences control motion and
transparency.

## Accessibility

- Preserve semantic landmarks, headings, labels, native form semantics, modal
  behavior, tab/radio state, `aria-current`, `aria-live`, `role="status"`, and
  `role="alert"`.
- Every icon-only action needs an accessible name and, when useful, a tooltip.
  Decorative icons and brand crops use `aria-hidden` or empty alternative text.
- Global keyboard focus is a 2px theme-aware outline with 2px offset; composite
  fields add a 3px soft focus ring.
- Keep hidden mobile navigation both `aria-hidden` and `inert`. Support keyboard
  operation and do not reveal required actions only on hover.
- Never encode state by color alone. Pair it with text and an icon or dot.
- Maintain readable contrast in both themes, English/Devanagari fallbacks,
  reduced-motion behavior, reduced-transparency behavior, and bottom safe-area
  spacing.

## Content Voice

Use warm, direct, listening-first language: "What is weighing on your mind?",
"Take your time", and "Begin wherever the thought feels hardest to hold."
Prefer short sentences, familiar verbs, and concrete next actions.

Name system state honestly: "Reflecting", "Connection interrupted", "Indexed",
or "Restore it before continuing". Errors should explain what happened and
offer a nearby recovery action. State limitations plainly, including "Moksha AI
may err" and remote-data or billing implications. Do not fabricate testimonials,
benchmarks, certainty, or commercial claims.

## Do and Don't

**Do**

- Reuse semantic tokens, the 48rem reading measure, compact controls, and
  existing responsive thresholds.
- Keep citations, consent, model readiness, archived state, and session state
  visible where decisions occur.
- Use the lotus/Om mark as restrained identity and assistant provenance.
- Design loading, empty, failure, disabled, streaming, and destructive states
  with the primary workflow.

**Don't**

- Turn the product into a temple motif, generic wellness landing page, or
  card-filled dashboard.
- Add oversized headlines, background grids, gradient orbs, large cursor blobs,
  decorative SVG scenes, or unexplained spiritual symbolism.
- Nest cards, use glass on every surface, or create depth with many shadows.
- Hide critical actions behind hover on touch layouts or use color as the only
  status signal.
- Store browser bearer tokens, render unsafe HTML, imply unsupported certainty,
  or describe consumer subscriptions as API access.

## Verification Evidence

This specification was derived from the implementation present on 2026-07-30:

- `PRODUCT.md` defines audience, purpose, product principles, brand commitments,
  constraints, and accessibility requirements.
- `frontend/assets/css/main.css` defines the font imports, complete light/dark
  semantic token sets, global focus, reduced-motion, and
  reduced-transparency behavior.
- `frontend/pages/index.vue` implements the authentication surface, compact
  welcome hierarchy, pointer light, theme action, accessible form states, and
  520px adaptation.
- `frontend/pages/app.vue` implements the fixed workspace, 15.5rem rail,
  48rem conversation measure, pointer light, state layouts, keyboard shortcut,
  and 860px/600px behavior.
- `frontend/components/app/*.vue` implements the history rail, message geometry,
  composer, five-section settings hierarchy, glass treatments, semantic states,
  and 680px settings adaptation.

Verification is static source inspection, not a claim of browser screenshot,
contrast-ratio, screen-reader, or end-to-end runtime validation. Future visual
changes should be checked in light and dark themes at widths above and below
860px, 680px, 600px, and 520px, with keyboard-only, coarse pointer,
`prefers-reduced-motion`, and `prefers-reduced-transparency` modes.
