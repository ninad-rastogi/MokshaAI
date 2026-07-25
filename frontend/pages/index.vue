<script setup lang="ts">
const api = useApi();
const email = ref("");
const password = ref("");
const mode = ref<"signin" | "register">("signin");
const error = ref("");
const busy = ref(false);

async function submit() {
  busy.value = true;
  error.value = "";
  try {
    if (mode.value === "register") {
      await api.register(email.value, password.value);
    }
    await api.sessionLogin(email.value, password.value);
    await navigateTo("/app");
  } catch {
    error.value =
      "Could not complete authentication. Check your account and try again.";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <main class="welcome">
    <section class="welcome__panel" aria-labelledby="welcome-title">
      <MokshaBrand />
      <div>
        <h1 id="welcome-title">A quieter scripture-grounded chat workspace</h1>
        <p>
          Ask with care, keep citations close, and continue your conversations
          across devices without sending browser bearer tokens to storage.
        </p>
      </div>
      <form class="auth" @submit.prevent="submit">
        <div
          class="auth__switch"
          role="tablist"
          aria-label="Authentication mode"
        >
          <button
            type="button"
            :aria-selected="mode === 'signin'"
            @click="mode = 'signin'"
          >
            Sign in
          </button>
          <button
            type="button"
            :aria-selected="mode === 'register'"
            @click="mode = 'register'"
          >
            Register
          </button>
        </div>
        <label>
          Email
          <input v-model="email" autocomplete="email" required type="email" />
        </label>
        <label>
          Password
          <input
            v-model="password"
            autocomplete="current-password"
            required
            minlength="8"
            type="password"
          />
        </label>
        <p v-if="error" role="alert">{{ error }}</p>
        <button class="primary" :disabled="busy" type="submit">
          {{ busy ? "Working..." : "Continue" }}
        </button>
      </form>
    </section>
  </main>
</template>

<style scoped>
.welcome {
  align-items: center;
  display: grid;
  min-height: 100svh;
  padding: 1.25rem;
}

.welcome__panel {
  display: grid;
  gap: 2rem;
  margin: 0 auto;
  max-width: 36rem;
  width: 100%;
}

h1 {
  font-size: clamp(2.1rem, 7vw, 4.5rem);
  line-height: 1;
  margin: 0;
}

p {
  color: var(--moksha-muted);
  font-size: 1.05rem;
  line-height: 1.65;
}

.auth {
  border-top: 1px solid var(--moksha-line);
  display: grid;
  gap: 1rem;
  padding-top: 1.25rem;
}

.auth__switch {
  display: flex;
  gap: 0.5rem;
}

button,
input {
  border: 1px solid var(--moksha-line);
  border-radius: 0.4rem;
  min-height: 2.75rem;
}

.auth__switch button {
  background: transparent;
  color: var(--moksha-ink);
  padding: 0 1rem;
}

.auth__switch button[aria-selected="true"],
.primary {
  background: var(--moksha-ink);
  color: var(--moksha-bg);
}

label {
  display: grid;
  font-weight: 700;
  gap: 0.4rem;
}

input {
  background: var(--moksha-surface);
  color: var(--moksha-ink);
  padding: 0 0.85rem;
}
</style>
