<script setup lang="ts">
import type { Citation } from "~/types/api";

defineProps<{ citations: Citation[] }>();
</script>

<template>
  <details v-if="citations.length" class="citations">
    <summary>
      <UIcon name="i-lucide-book-open-text" aria-hidden="true" />
      {{ citations.length }}
      {{
        citations.length === 1 ? "scripture reference" : "scripture references"
      }}
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
        <blockquote>{{ citation.excerpt }}</blockquote>
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
  color: var(--moksha-muted);
  font-size: 0.72rem;
  line-height: 1.55;
  margin: 0.5rem 0 0;
}
</style>
