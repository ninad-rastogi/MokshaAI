<template>
  <NuxtLink to="/" class="brand" aria-label="Moksha AI home">
    <img
      src="/brand/MokshaAI_light_cropped.png"
      alt=""
      class="brand__mark light-mark"
    />
    <img
      src="/brand/MokshaAI_dark_cropped.png"
      alt=""
      class="brand__mark dark-mark"
    />
    <span>Moksha AI</span>
  </NuxtLink>
</template>

<style scoped>
.brand {
  align-items: center;
  color: var(--moksha-ink);
  display: inline-flex;
  font-size: 1.125rem;
  font-weight: 700;
  gap: 0.65rem;
  text-decoration: none;
}

.brand__mark {
  height: 2.25rem;
  width: 2.25rem;
}

.dark .light-mark,
.dark-mark {
  display: none;
}

.dark .dark-mark {
  display: block;
}
</style>
