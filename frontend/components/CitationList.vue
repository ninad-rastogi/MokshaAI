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
        <blockquote aria-label="Exact retrieved source passage">
          <strong>Source passage</strong>
          <UIcon name="i-lucide-quote" aria-hidden="true" />
          <span>{{ citation.excerpt }}</span>
        </blockquote>
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

blockquote {
  align-items: start;
  background: var(--moksha-assistant-bubble);
  border: 1px solid var(--moksha-assistant-line);
  border-radius: 0.55rem;
  color: var(--moksha-ink);
  display: grid;
  font-size: 0.72rem;
  gap: 0.4rem;
  grid-template-columns: auto minmax(0, 1fr);
  line-height: 1.55;
  margin: 0.5rem 0 0;
  padding: 0.55rem 0.6rem;
}

blockquote strong {
  color: var(--moksha-accent);
  font-size: 0.62rem;
  grid-column: 1 / -1;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

blockquote svg {
  color: var(--moksha-accent);
  height: 0.78rem;
  margin-top: 0.12rem;
  width: 0.78rem;
}
</style>
