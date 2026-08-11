<script setup lang="ts">
import type { Citation } from "~/types/api";

defineProps<{ citations: Citation[] }>();
</script>

<template>
  <details v-if="citations.length" class="citations" open>
    <summary>
      <UIcon name="i-lucide-book-open-text" aria-hidden="true" />
      {{ citations.length }}
      {{ citations.length === 1 ? "source quotation" : "source quotations" }}
      <UIcon class="chevron" name="i-lucide-chevron-down" aria-hidden="true" />
    </summary>
    <ol>
      <li
        v-for="citation in citations"
        :key="`${citation.file_name}-${citation.page}-${citation.score}`"
      >
        <header>
          <span>
            <strong>{{ citation.scripture }}</strong>
            <small>{{ citation.file_name }}</small>
          </span>
          <span class="page-reference">Page {{ citation.page }}</span>
        </header>
        <blockquote
          v-if="citation.sanskrit_text || citation.verse_text"
          class="verse-panel"
          aria-label="Exact cited verse"
        >
          <strong>Exact verse</strong>
          <UIcon name="i-lucide-quote" aria-hidden="true" />
          <span class="verse-text">
            {{ citation.sanskrit_text || citation.verse_text }}
          </span>
        </blockquote>
        <p v-if="citation.translation" class="translation-panel">
          <strong>Translation</strong>
          <span>{{ citation.translation }}</span>
        </p>
        <details class="source-details">
          <summary>Retrieved source passage</summary>
          <p>{{ citation.source_text || citation.excerpt }}</p>
        </details>
      </li>
    </ol>
  </details>
</template>

<style scoped>
.citations {
  border-top: 1px solid var(--moksha-glass-line);
  margin-top: 1rem;
  padding-top: 0.75rem;
}

summary {
  align-items: center;
  color: var(--moksha-accent);
  cursor: pointer;
  display: flex;
  font-size: 0.7rem;
  font-weight: 700;
  gap: 0.35rem;
  list-style: none;
  width: fit-content;
}

summary::-webkit-details-marker {
  display: none;
}

summary svg {
  height: 0.85rem;
  width: 0.85rem;
}

.chevron {
  transition: transform 160ms ease;
}

details[open] .chevron {
  transform: rotate(180deg);
}

ol {
  display: grid;
  gap: 0.45rem;
  list-style: none;
  margin: 0.65rem 0 0;
  padding: 0;
}

li {
  background: var(--moksha-control);
  border-radius: 0.65rem;
  padding: 0.65rem 0.7rem;
}

li header {
  align-items: start;
  display: flex;
  gap: 0.6rem;
  justify-content: space-between;
}

li header > span:first-child {
  display: grid;
}

li strong {
  font-size: 0.72rem;
}

li small {
  color: var(--moksha-muted);
  font-size: 0.64rem;
}

.page-reference {
  background: var(--moksha-accent-soft);
  border-radius: 0.4rem;
  color: var(--moksha-accent-ink);
  font-size: 0.62rem;
  font-weight: 680;
  padding: 0.2rem 0.38rem;
  white-space: nowrap;
}

blockquote,
.translation-panel,
.source-details {
  background: var(--moksha-assistant-bubble);
  border: 1px solid var(--moksha-assistant-line);
  border-radius: 0.55rem;
  color: var(--moksha-ink);
  margin: 0.5rem 0 0;
}

blockquote {
  align-items: start;
  display: grid;
  font-size: 0.82rem;
  gap: 0.5rem;
  grid-template-columns: auto minmax(0, 1fr);
  line-height: 1.7;
  padding: 0.7rem 0.75rem;
}

blockquote strong,
.translation-panel strong,
.source-details summary {
  color: var(--moksha-accent);
  font-size: 0.62rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

blockquote strong {
  grid-column: 1 / -1;
}

blockquote svg {
  color: var(--moksha-accent);
  height: 0.78rem;
  margin-top: 0.12rem;
  width: 0.78rem;
}

.verse-text,
.translation-panel span,
.source-details p {
  white-space: pre-wrap;
}

.verse-text {
  font-family:
    "Noto Sans Devanagari Variable", "Nirmala UI", Mangal, var(--moksha-font);
  font-size: 0.95rem;
  font-weight: 580;
  letter-spacing: 0;
}

.translation-panel {
  display: grid;
  font-size: 0.8rem;
  gap: 0.4rem;
  line-height: 1.65;
  padding: 0.65rem 0.75rem;
}

.source-details {
  padding: 0.48rem 0.6rem;
}

.source-details summary {
  cursor: pointer;
  list-style: none;
}

.source-details summary::-webkit-details-marker {
  display: none;
}

.source-details p {
  color: var(--moksha-muted);
  font-size: 0.7rem;
  line-height: 1.5;
  margin: 0.45rem 0 0;
}
</style>
