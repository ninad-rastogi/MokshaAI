<script setup lang="ts">
import { ApiRequestError } from "~/composables/useApi";

const api = useApi();
const email = ref("");
const password = ref("");
const mode = ref<"signin" | "register">("signin");
const error = ref("");
const busy = ref(false);

function collectMessages(payload: unknown): string[] {
  if (typeof payload === "string") return [payload];
  if (!payload || typeof payload !== "object") return [];
  return Object.values(payload as Record<string, unknown>).flatMap((value) => {
    if (Array.isArray(value)) return value.map(String);
    if (typeof value === "string") return [value];
    return collectMessages(value);
  });
}

function authErrorMessage(authError: unknown) {
  if (authError instanceof ApiRequestError) {
    const messages = collectMessages(authError.payload);
    const joined = messages.join(" ").toLowerCase();
    if (authError.status === 400 && joined.includes("already exists")) {
      return "Account already exists. Sign in instead.";
    }
    if (joined.includes("invalid_credentials")) {
      return "Email or password is incorrect.";
    }
    if (messages.length) {
      return messages[0] || "Could not complete authentication.";
    }
  }
  return "Could not complete authentication. Check your account and try again.";
}

async function submit() {
  busy.value = true;
  error.value = "";
  try {
    if (mode.value === "register") {
      await api.register(email.value, password.value);
    }
    await api.sessionLogin(email.value, password.value);
    await navigateTo("/app");
  } catch (authError) {
    error.value = authErrorMessage(authError);
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
        <p class="eyebrow">Ancient scripture for difficult moments</p>
        <h1 id="welcome-title">When life feels heavy, ask for guidance.</h1>
        <p>
          Moksha AI listens with patience and answers through Indian spiritual
          wisdom, grounding counsel in cited verses like Krishna guiding Arjuna
          through confusion, fear, and duty.
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
  font-size: clamp(2.4rem, 7vw, 4.8rem);
  letter-spacing: 0;
  line-height: 0.95;
  margin: 0;
}

p {
  color: var(--moksha-muted);
  font-size: 1.05rem;
  line-height: 1.65;
}

.eyebrow {
  color: var(--moksha-accent);
  font-size: 0.9rem;
  font-weight: 800;
  letter-spacing: 0;
  margin: 0 0 0.85rem;
  text-transform: uppercase;
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
