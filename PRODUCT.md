# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Moksha AI primarily serves people carrying confusion, pressure, grief, fear,
loneliness, or other difficult life situations who want to be heard and seek
practical spiritual guidance. Users may write in English, Hindi, or Sanskrit
contexts. Staff maintain scripture collections, indexing, and approved model
availability through Django admin.

## Product Purpose

Moksha AI offers a private, listening-first conversation and grounds its counsel
in relevant passages from indexed Indian scriptures. It should help users
reflect and choose a constructive next step without pretending to replace human,
medical, or emergency support. Success means useful guidance, traceable citations,
durable conversations, and an interface calm enough to use during hard moments.

## Positioning

Unlike a generic chatbot adopting a spiritual tone, Moksha AI searches a
versioned scripture library and cites qualifying evidence. Every valid
collection added to the library must be discoverable without source-specific
code changes.

## Operating Context

Users authenticate with a browser session, create and revisit conversations,
stream an answer, inspect citations, rename/archive/delete chats, select an
available local or connected model, manage theme and account preferences, and
optionally connect a provider using its API endpoint and API key. Browser
preferences must survive refresh and follow the signed-in account.

## Capabilities and Constraints

- Nuxt 4 and Vue 3 provide the public and authenticated web interface.
- Django 6 and DRF own product data, browser session/CSRF authentication, and
  Django admin.
- Caddy is the only published edge.
- Browser code never stores bearer tokens in local storage.
- Generated Markdown disables raw HTML and is sanitized before rendering.
- Responses may cite any qualified scripture added to the versioned corpus.
- Remote providers require explicit data consent. Consumer subscriptions must
  never be described as API access.
- Archived chats are read-only until restored.
- Explicit cancellation stops generation; a browser disconnect does not.

## Brand Commitments

The product name is Moksha AI. Preserve the existing lotus/Om mark while its
production brand asset remains available. Identity should feel contemporary,
soothing, and premium with an ancient Indian undertone. Glass depth, restrained
warm metal, and subtle pointer-responsive light are binding design requirements.
Literal temple decoration, large cursor blobs, background grids, oversized
typography, and pasted explanations of the product concept are explicitly wrong.

## Evidence on Hand

- Existing light and dark brand marks:
  `frontend/public/brand/MokshaAI_light_cropped.png` and
  `frontend/public/brand/MokshaAI_dark_cropped.png`.
- Real chats, messages, scripture status, citations, generation lifecycle, model
  profiles, and user preferences come from the Django API.
- No testimonials, commercial claims, or production benchmark claims are
  available and none should be fabricated.

## Product Principles

1. Listen before advising.
2. Distinguish scripture-grounded evidence from unsupported certainty.
3. Keep critical conversation actions familiar and immediately reachable.
4. Preserve user trust through durable sessions, explicit state, and honest errors.
5. Let ancient wisdom shape detail and material, not reduce the interface to a
   religious motif.

## Accessibility & Inclusion

Keyboard navigation, visible focus, semantic status, reduced motion,
reduced-transparency fallback, responsive mobile behavior, and legible
English/Devanagari text are required. Color never carries status alone.
