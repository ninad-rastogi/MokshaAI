<template>
  <NuxtLink to="/" class="brand" aria-label="Moksha AI home">
    <span class="brand__mark" aria-hidden="true">
      <img src="/brand/MokshaAI_light_cropped.png" alt="" class="light-mark" />
      <img src="/brand/MokshaAI_dark_cropped.png" alt="" class="dark-mark" />
    </span>
    <span class="brand__name">Moksha AI</span>
  </NuxtLink>
</template>

<style scoped>
.brand {
  align-items: center;
  color: var(--moksha-ink);
  display: inline-flex;
  font-size: 0.93rem;
  font-weight: 760;
  gap: 0.48rem;
  text-decoration: none;
}

.brand__mark {
  display: block;
  height: 1.8rem;
  overflow: hidden;
  position: relative;
  width: 1.8rem;
}

.brand__mark img {
  height: 2.9rem;
  left: 50%;
  max-width: none;
  mix-blend-mode: multiply;
  position: absolute;
  top: -0.08rem;
  transform: translateX(-50%);
  width: 2.9rem;
}

.dark .light-mark,
.dark-mark {
  display: none;
}

.dark .dark-mark {
  display: block;
  mix-blend-mode: screen;
}

.brand__name {
  white-space: nowrap;
}
</style>
