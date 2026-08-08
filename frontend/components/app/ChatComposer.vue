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
</script>

<template>
  <div class="composer-wrap">
    <UChatPrompt
      :model-value="modelValue"
      class="moksha-prompt"
      :disabled="disabled"
      :loading="busy"
      :maxrows="5"
      :rows="1"
      :submit-on-enter="true"
      variant="naked"
      placeholder="Share what is on your mind..."
      aria-label="Message Moksha AI"
      :ui="{
        root: 'moksha-prompt__root',
        base: 'moksha-prompt__textarea',
      }"
      @update:model-value="emit('update:modelValue', $event)"
      @submit="submit"
    >
      <template #footer>
        <div class="composer-meta">
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
      </template>
    </UChatPrompt>

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
  background: var(--moksha-composer) !important;
  backdrop-filter: blur(24px) saturate(1.08);
  border: 1px solid var(--moksha-assistant-line) !important;
  border-radius: 0.72rem;
  box-shadow: var(--moksha-shadow-composer) !important;
  overflow: hidden;
}

:deep(.moksha-prompt:focus-within) {
  border-color: var(--moksha-focus);
  box-shadow:
    0 0 0 3px var(--moksha-focus-ring),
    var(--moksha-shadow-composer) !important;
}

:deep(.moksha-prompt__root) {
  background: transparent;
  border: 0;
  box-shadow: none;
  min-height: 3.2rem;
  padding: 0.38rem 0.46rem 0.34rem;
}

:deep(.moksha-prompt__textarea) {
  color: var(--moksha-ink);
  font-size: 0.86rem;
  line-height: 1.5;
  min-height: 1.6rem;
  padding: 0.15rem 0.2rem;
}

:deep(.moksha-prompt__textarea::placeholder) {
  color: var(--moksha-placeholder);
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

@media (max-width: 600px) {
  .composer-hint {
    display: none;
  }

  :deep(.moksha-prompt__root) {
    min-height: 3.15rem;
  }

  .composer-note,
  .composer-error {
    font-size: 0.68rem;
    padding: 0 0.5rem;
  }
}
</style>
