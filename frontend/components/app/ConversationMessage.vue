<script setup lang="ts">
import type { Message } from "~/types/api";

defineProps<{
  message: Message;
  streaming?: boolean;
}>();
</script>

<template>
  <article :class="['message', `message--${message.role}`]">
    <div
      v-if="message.role === 'assistant'"
      class="guide-mark"
      aria-hidden="true"
    >
      <img src="/brand/MokshaAI_dark_cropped.png" alt="" />
    </div>
    <div class="message__content">
      <MarkdownBody :content="message.content" />
      <span v-if="streaming" class="stream-caret" aria-label="Generating" />
      <CitationList :citations="message.sources" />
    </div>
  </article>
</template>

<style scoped>
.message {
  display: grid;
  margin: 0 auto;
  max-width: 48rem;
  width: 100%;
}

.message--assistant {
  gap: 0.7rem;
  grid-template-columns: 1.8rem minmax(0, 1fr);
}

.guide-mark {
  align-items: center;
  background: var(--moksha-guide-mark);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.55rem;
  display: flex;
  height: 1.8rem;
  justify-content: center;
  margin-top: 0.05rem;
  overflow: hidden;
  width: 1.8rem;
}

.guide-mark img {
  height: 1.45rem;
  object-fit: contain;
  width: 1.45rem;
}

.message__content {
  color: var(--moksha-ink);
  font-size: 0.9rem;
  line-height: 1.68;
  min-width: 0;
}

.message--user {
  justify-items: end;
}

.message--user .message__content {
  background: var(--moksha-user-bubble);
  border: 1px solid var(--moksha-user-line);
  border-radius: 0.95rem 0.95rem 0.25rem;
  box-shadow: 0 0.55rem 1.2rem rgb(22 28 24 / 7%);
  color: var(--moksha-user-ink);
  max-width: min(35rem, 82%);
  padding: 0.62rem 0.78rem;
}

.stream-caret {
  animation: pulse 1s ease-in-out infinite;
  background: var(--moksha-accent);
  border-radius: 2px;
  display: inline-block;
  height: 0.95rem;
  margin-left: 0.18rem;
  vertical-align: -0.08rem;
  width: 0.12rem;
}

@keyframes pulse {
  50% {
    opacity: 0.25;
  }
}

@media (max-width: 600px) {
  .message--assistant {
    gap: 0.55rem;
    grid-template-columns: 1.6rem minmax(0, 1fr);
  }

  .guide-mark {
    height: 1.6rem;
    width: 1.6rem;
  }

  .guide-mark img {
    height: 1.25rem;
    width: 1.25rem;
  }

  .message__content {
    font-size: 0.86rem;
  }

  .message--user .message__content {
    max-width: 88%;
  }
}
</style>
