<script setup lang="ts">
const props = defineProps<{ content: string }>();
const { renderMarkdown } = useMarkdown();
const html = computed(() => renderMarkdown(props.content));
</script>

<template>
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="markdown-body" v-html="html" />
</template>

<style scoped>
.markdown-body {
  line-height: 1.7;
}

.markdown-body :deep(p) {
  margin: 0 0 0.75rem;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.5rem 0 0.75rem 1.25rem;
}
</style>
