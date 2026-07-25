<script setup lang="ts">
import type { Citation } from "~/types/api";

defineProps<{ citations: Citation[] }>();
</script>

<template>
  <details v-if="citations.length" class="citations">
    <summary>Citations</summary>
    <ol>
      <li
        v-for="citation in citations"
        :key="`${citation.file_name}-${citation.page}-${citation.score}`"
      >
        <strong>{{ citation.scripture }}</strong>
        <span>{{ citation.file_name }}, p. {{ citation.page }}</span>
        <small>score {{ citation.score.toFixed(2) }}</small>
        <p>{{ citation.excerpt }}</p>
      </li>
    </ol>
  </details>
</template>

<style scoped>
.citations {
  border-top: 1px solid var(--moksha-line);
  margin-top: 0.85rem;
  padding-top: 0.75rem;
}

summary {
  cursor: pointer;
  font-weight: 700;
}

ol {
  display: grid;
  gap: 0.75rem;
  margin: 0.75rem 0 0;
  padding-left: 1.25rem;
}

li span,
small {
  color: var(--moksha-muted);
  display: block;
}

p {
  margin: 0.25rem 0 0;
}
</style>
