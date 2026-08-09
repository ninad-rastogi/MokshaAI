<script setup lang="ts">
const props = defineProps<{
  modelValue: string;
  busy: boolean;
  error: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: string];
  submit: [];
  stop: [];
}>();

function submit() {
  if (!props.modelValue.trim() || props.busy || props.disabled) return;
  emit("submit");
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  submit();
}
</script>

<template>
  <div class="composer-wrap">
    <form
      class="moksha-prompt"
      aria-label="Message composer"
      @submit.prevent="submit"
    >
      <textarea
        :value="modelValue"
        class="moksha-prompt__textarea"
        :disabled="disabled"
        rows="1"
        placeholder="Share what is on your mind..."
        aria-label="Message Moksha AI"
        @input="
          emit(
            'update:modelValue',
            ($event.target as HTMLTextAreaElement).value,
          )
        "
        @keydown="handleKeydown"
      />
      <div class="moksha-prompt__footer">
        <div class="composer-meta">
          <span
            v-if="busy"
            class="thinking-chip"
            role="status"
            aria-label="Moksha AI is thinking"
          >
            <i />
            <i />
            <i />
            Thinking
          </span>
          <span class="composer-hint">Shift + Enter for a new line</span>
        </div>

        <UTooltip :text="busy ? 'Stop response' : 'Send message'">
          <button
            v-if="busy"
            class="composer-action composer-action--stop"
            type="button"
            aria-label="Stop response"
            @click="emit('stop')"
          >
            <UIcon name="i-lucide-square" aria-hidden="true" />
          </button>
          <button
            v-else
            class="composer-action"
            type="submit"
            aria-label="Send message"
            :disabled="disabled || !modelValue.trim()"
          >
            <UIcon name="i-lucide-arrow-up" aria-hidden="true" />
          </button>
        </UTooltip>
      </div>
    </form>

    <p v-if="error" class="composer-error" role="alert">
      <UIcon name="i-lucide-circle-alert" aria-hidden="true" />
      {{ error }}
    </p>
    <p v-else class="composer-note">
      Moksha AI may err. Verify important guidance and citations.
    </p>
  </div>
</template>

<style scoped>
.composer-wrap {
  margin: 0 auto;
  max-width: 44rem;
  width: 100%;
}

:deep(.moksha-prompt) {
  background: transparent;
}

.moksha-prompt {
  background: var(--moksha-composer);
  backdrop-filter: blur(24px) saturate(1.08);
  border: 1px solid var(--moksha-assistant-line);
  border-radius: 0.72rem;
  box-shadow: var(--moksha-shadow-composer);
  display: grid;
  gap: 0.25rem;
  overflow: hidden;
  padding: 0.45rem;
}

.moksha-prompt:focus-within {
  border-color: var(--moksha-focus);
  box-shadow:
    0 0 0 3px var(--moksha-focus-ring),
    var(--moksha-shadow-composer);
}

.moksha-prompt__textarea {
  background: transparent;
  border: 0;
  color: var(--moksha-ink);
  font-size: 0.86rem;
  line-height: 1.5;
  max-height: 8rem;
  min-height: 1.65rem;
  outline: 0;
  padding: 0.1rem 0.2rem;
  resize: none;
}

.moksha-prompt__textarea::placeholder {
  color: var(--moksha-placeholder);
}

.moksha-prompt__footer {
  align-items: center;
  display: flex;
  justify-content: space-between;
  min-height: 2rem;
}

.composer-meta {
  align-items: center;
  display: flex;
  gap: 0.8rem;
  min-width: 0;
}

.composer-hint {
  color: var(--moksha-muted);
  font-size: 0.68rem;
}

.thinking-chip {
  align-items: center;
  color: var(--moksha-muted);
  display: inline-flex;
  font-size: 0.68rem;
  gap: 0.25rem;
}

.thinking-chip > i {
  animation: dot-bounce 1.05s ease-in-out infinite;
  background: var(--moksha-accent);
  border-radius: 50%;
  height: 0.28rem;
  width: 0.28rem;
}

.thinking-chip > i:nth-child(2) {
  animation-delay: 120ms;
}

.thinking-chip > i:nth-child(3) {
  animation-delay: 240ms;
}

.composer-action {
  align-items: center;
  background: var(--moksha-primary);
  border: 0;
  border-radius: 0.45rem;
  color: var(--moksha-primary-ink);
  display: inline-flex;
  height: 2rem;
  justify-content: center;
  width: 2rem;
}

.composer-action:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.composer-action:disabled {
  background: var(--moksha-disabled);
  color: var(--moksha-muted);
}

.composer-action--stop {
  background: var(--moksha-error-soft);
  color: var(--moksha-error);
}

.composer-action svg {
  height: 0.92rem;
  width: 0.92rem;
}

.composer-note,
.composer-error {
  align-items: center;
  display: flex;
  font-size: 0.65rem;
  gap: 0.3rem;
  justify-content: center;
  margin: 0.24rem 0 0;
  min-height: 1rem;
  text-align: center;
}

.composer-note {
  color: var(--moksha-muted);
}

.composer-error {
  color: var(--moksha-error);
}

@keyframes dot-bounce {
  0%,
  60%,
  100% {
    opacity: 0.42;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-0.22rem);
  }
}

@media (max-width: 600px) {
  .composer-hint {
    display: none;
  }

  .moksha-prompt {
    border-radius: 0.7rem;
    padding: 0.42rem;
  }

  .composer-note,
  .composer-error {
    font-size: 0.68rem;
    padding: 0 0.5rem;
  }
}
</style>
