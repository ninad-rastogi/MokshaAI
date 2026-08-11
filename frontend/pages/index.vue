<script setup lang="ts">
import { ApiRequestError } from "~/composables/useApi";

const api = useApi();
const colorMode = useColorMode();
const email = ref("");
const password = ref("");
const passwordConfirm = ref("");
const mode = ref<"signin" | "register">("signin");
const error = ref("");
const busy = ref(false);
const checkingSession = ref(true);
const showPassword = ref(false);
const authSurface = ref<HTMLElement | null>(null);
let pointerFrame = 0;

onMounted(async () => {
  try {
    const session = await api.sessionStatus();
    if (session.authenticated && session.user) {
      colorMode.preference = session.user.preferred_theme;
      await navigateTo("/app");
    }
  } catch {
    checkingSession.value = false;
  } finally {
    if (useRoute().path === "/") {
      checkingSession.value = false;
    }
  }
});

onBeforeUnmount(() => cancelAnimationFrame(pointerFrame));

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
    if (
      authError.status === 400 &&
      (joined.includes("already exists") ||
        joined.includes("already registered") ||
        joined.includes("unique"))
    ) {
      return "An account with this email already exists. Sign in instead.";
    }
    if (
      authError.status === 400 &&
      (joined.includes("invalid_credentials") ||
        joined.includes("unable to log in") ||
        joined.includes("incorrect"))
    ) {
      return "Email or password is incorrect.";
    }
    if (authError.status === 403) {
      return "Your secure session expired. Refresh the page and try again.";
    }
    if (authError.status >= 500) {
      return "Moksha AI is unavailable right now. Try again in a moment.";
    }
    if (messages.length) {
      return messages[0] || "Authentication could not be completed.";
    }
  }
  return "Authentication could not be completed. Check your connection and try again.";
}

function switchMode(nextMode: "signin" | "register") {
  mode.value = nextMode;
  error.value = "";
  passwordConfirm.value = "";
}

async function submit() {
  if (mode.value === "register" && password.value !== passwordConfirm.value) {
    error.value = "Passwords do not match.";
    return;
  }

  busy.value = true;
  error.value = "";
  try {
    const profile =
      mode.value === "register"
        ? await api.register(email.value, password.value)
        : await api.sessionLogin(email.value, password.value);
    colorMode.preference = profile.preferred_theme;
    await navigateTo("/app");
  } catch (authError) {
    error.value = authErrorMessage(authError);
  } finally {
    busy.value = false;
  }
}

function signInExistingAccount() {
  switchMode("signin");
  nextTick(() => document.querySelector<HTMLInputElement>("#email")?.focus());
}

function toggleTheme() {
  colorMode.preference = colorMode.value === "dark" ? "light" : "dark";
}

function trackPointer(event: PointerEvent) {
  if (!authSurface.value || event.pointerType === "touch") return;
  cancelAnimationFrame(pointerFrame);
  pointerFrame = requestAnimationFrame(() => {
    authSurface.value?.style.setProperty("--pointer-x", `${event.clientX}px`);
    authSurface.value?.style.setProperty("--pointer-y", `${event.clientY}px`);
  });
}
</script>

<template>
  <main
    ref="authSurface"
    class="auth-surface"
    @pointermove.passive="trackPointer"
  >
    <header class="auth-header">
      <MokshaBrand />
      <UTooltip text="Change theme">
        <button
          class="theme-button"
          type="button"
          aria-label="Change theme"
          @click="toggleTheme"
        >
          <UIcon name="i-lucide-sun-moon" aria-hidden="true" />
        </button>
      </UTooltip>
    </header>

    <section
      v-if="checkingSession"
      class="session-check"
      aria-label="Checking session"
    >
      <h1 class="sr-only">Moksha AI</h1>
      <span />
      <p>Returning to your conversations...</p>
    </section>

    <section v-else class="auth-panel" aria-labelledby="welcome-title">
      <div class="auth-panel__intro">
        <span class="intro-mark" aria-hidden="true">
          <img src="/brand/MokshaAI_dark_cropped.png" alt="" />
        </span>
        <p class="intro-kicker">A quiet place to begin</p>
        <h1 id="welcome-title">Bring what feels difficult to carry.</h1>
        <p>
          Speak freely. Moksha AI listens, reflects, and draws from your
          scripture library when relevant guidance is found.
        </p>
      </div>

      <form class="auth-form" @submit.prevent="submit">
        <div
          class="auth-switch"
          role="tablist"
          aria-label="Authentication mode"
        >
          <button
            type="button"
            role="tab"
            :aria-selected="mode === 'signin'"
            @click="switchMode('signin')"
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            :aria-selected="mode === 'register'"
            @click="switchMode('register')"
          >
            Create account
          </button>
        </div>

        <label class="auth-field" for="email">
          <span>Email</span>
          <span class="auth-input">
            <UIcon name="i-lucide-mail" aria-hidden="true" />
            <input
              id="email"
              v-model="email"
              autocomplete="email"
              required
              type="email"
              placeholder="you@example.com"
            />
          </span>
        </label>

        <label class="auth-field" for="password">
          <span>Password</span>
          <span class="auth-input">
            <UIcon name="i-lucide-lock-keyhole" aria-hidden="true" />
            <input
              id="password"
              v-model="password"
              :autocomplete="
                mode === 'register' ? 'new-password' : 'current-password'
              "
              required
              minlength="8"
              :type="showPassword ? 'text' : 'password'"
              placeholder="At least 8 characters"
            />
            <button
              type="button"
              :aria-label="showPassword ? 'Hide password' : 'Show password'"
              @click="showPassword = !showPassword"
            >
              <UIcon
                :name="showPassword ? 'i-lucide-eye-off' : 'i-lucide-eye'"
                aria-hidden="true"
              />
            </button>
          </span>
        </label>

        <label
          v-if="mode === 'register'"
          class="auth-field"
          for="password-confirm"
        >
          <span>Confirm password</span>
          <span class="auth-input">
            <UIcon name="i-lucide-shield-check" aria-hidden="true" />
            <input
              id="password-confirm"
              v-model="passwordConfirm"
              autocomplete="new-password"
              required
              minlength="8"
              :type="showPassword ? 'text' : 'password'"
              placeholder="Repeat your password"
            />
          </span>
        </label>

        <div v-if="error" class="auth-error" role="alert">
          <UIcon name="i-lucide-circle-alert" aria-hidden="true" />
          <span>{{ error }}</span>
          <button
            v-if="error.includes('already exists')"
            type="button"
            @click="signInExistingAccount"
          >
            Sign in
          </button>
        </div>

        <button class="continue-button" :disabled="busy" type="submit">
          <UIcon
            v-if="busy"
            class="spin"
            name="i-lucide-loader-circle"
            aria-hidden="true"
          />
          <span>{{
            busy
              ? mode === "register"
                ? "Creating account..."
                : "Signing in..."
              : mode === "register"
                ? "Create account"
                : "Continue"
          }}</span>
          <UIcon v-if="!busy" name="i-lucide-arrow-right" aria-hidden="true" />
        </button>
      </form>

      <footer class="auth-assurance">
        <UIcon name="i-lucide-shield" aria-hidden="true" />
        <span>Secure browser session. Preferences stay with your account.</span>
      </footer>
    </section>
  </main>
</template>

<style scoped>
.auth-surface {
  --pointer-x: 50vw;
  --pointer-y: 35vh;

  place-items: center center;
  background: linear-gradient(145deg, var(--moksha-bg), var(--moksha-bg-deep));
  display: grid;
  height: 100svh;
  overflow: auto;
  padding: 4.5rem 1rem 1.5rem;
  position: relative;
}

.dark .auth-surface {
  background: linear-gradient(145deg, var(--moksha-bg), var(--moksha-bg-deep));
}

.auth-surface::before {
  background: radial-gradient(
    circle 50px at var(--pointer-x) var(--pointer-y),
    rgb(238 190 117 / 18%),
    rgb(104 162 136 / 5%) 40%,
    transparent 100%
  );
  content: "";
  inset: 0;
  pointer-events: none;
  position: fixed;
}

.auth-header {
  align-items: center;
  display: flex;
  justify-content: space-between;
  left: 0;
  padding: 0.8rem 1.1rem;
  position: fixed;
  right: 0;
  top: 0;
  z-index: 2;
}

.theme-button {
  align-items: center;
  backdrop-filter: blur(18px);
  background: var(--moksha-glass);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.6rem;
  color: var(--moksha-muted);
  display: flex;
  height: 2.15rem;
  justify-content: center;
  width: 2.15rem;
}

.auth-panel {
  backdrop-filter: blur(28px) saturate(1.1);
  background: var(--moksha-glass);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.5rem;
  box-shadow: var(--moksha-shadow-modal);
  display: grid;
  gap: 1.25rem;
  max-width: 27rem;
  overflow: hidden;
  padding: 1.3rem;
  position: relative;
  width: 100%;
}

.auth-panel::after {
  background: linear-gradient(130deg, rgb(255 255 255 / 10%), transparent 32%);
  content: "";
  inset: 0;
  pointer-events: none;
  position: absolute;
}

.auth-panel > * {
  position: relative;
  z-index: 1;
}

.auth-panel__intro {
  text-align: center;
}

.intro-mark {
  background: var(--moksha-guide-mark);
  border-radius: 0.5rem;
  display: block;
  height: 2.8rem;
  margin: 0 auto;
  overflow: hidden;
  position: relative;
  width: 2.8rem;
}

.intro-mark img {
  height: 4.4rem;
  left: 50%;
  max-width: none;
  mix-blend-mode: screen;
  position: absolute;
  top: -0.08rem;
  transform: translateX(-50%);
  width: 4.4rem;
}

.intro-kicker {
  color: var(--moksha-accent) !important;
  font-size: 0.69rem !important;
  font-weight: 740;
  margin-top: 0.8rem !important;
}

.auth-panel h1 {
  font-size: 1.75rem;
  font-weight: 720;
  line-height: 1.16;
  margin: 0.35rem auto 0.55rem;
  max-width: 21rem;
}

.auth-panel__intro > p:last-child {
  color: var(--moksha-muted);
  font-size: 0.78rem;
  line-height: 1.55;
  margin: 0 auto;
  max-width: 23rem;
}

.auth-form {
  display: grid;
  gap: 0.8rem;
}

.auth-switch {
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.65rem;
  display: grid;
  gap: 0.2rem;
  grid-template-columns: 1fr 1fr;
  padding: 0.22rem;
}

.auth-switch button {
  background: transparent;
  border: 1px solid transparent;
  border-radius: 0.48rem;
  color: var(--moksha-muted);
  font-size: 0.75rem;
  font-weight: 650;
  min-height: 2.15rem;
}

.auth-switch button[aria-selected="true"] {
  background: var(--moksha-glass-raised);
  border-color: var(--moksha-glass-line);
  box-shadow: 0 0.25rem 0.7rem rgb(10 17 13 / 8%);
  color: var(--moksha-ink);
}

.auth-field {
  display: grid;
  gap: 0.35rem;
}

.auth-field > span:first-child {
  color: var(--moksha-ink);
  font-size: 0.7rem;
  font-weight: 680;
}

.auth-input {
  align-items: center;
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.62rem;
  display: grid;
  gap: 0.5rem;
  grid-template-columns: auto minmax(0, 1fr) auto;
  min-height: 2.55rem;
  padding: 0 0.65rem;
}

.auth-input:focus-within {
  border-color: var(--moksha-focus);
  box-shadow: 0 0 0 3px var(--moksha-focus-ring);
}

.auth-input > svg {
  color: var(--moksha-muted);
  height: 0.9rem;
  width: 0.9rem;
}

.auth-input input {
  background: transparent;
  border: 0;
  color: var(--moksha-ink);
  font-size: 0.78rem;
  min-width: 0;
  outline: 0;
}

.auth-input button {
  background: transparent;
  border: 0;
  color: var(--moksha-muted);
  display: grid;
  height: 1.8rem;
  place-items: center;
  width: 1.8rem;
}

.auth-error {
  align-items: start;
  background: var(--moksha-error-soft);
  border: 1px solid var(--moksha-error-line);
  border-radius: 0.6rem;
  color: var(--moksha-error);
  display: grid;
  font-size: 0.7rem;
  gap: 0.4rem;
  grid-template-columns: auto minmax(0, 1fr) auto;
  padding: 0.55rem 0.65rem;
}

.auth-error button {
  background: transparent;
  border: 0;
  color: inherit;
  font-size: 0.7rem;
  font-weight: 720;
  padding: 0;
  text-decoration: underline;
}

.continue-button {
  align-items: center;
  background: var(--moksha-primary);
  border: 0;
  border-radius: 0.65rem;
  color: var(--moksha-primary-ink);
  display: grid;
  font-size: 0.78rem;
  font-weight: 720;
  gap: 0.5rem;
  grid-template-columns: auto minmax(0, 1fr) auto;
  min-height: 2.65rem;
  padding: 0 0.8rem;
}

.continue-button:hover:not(:disabled) {
  filter: brightness(1.08);
  transform: translateY(-1px);
}

.continue-button:disabled {
  opacity: 0.62;
}

.auth-assurance {
  align-items: center;
  border-top: 1px solid var(--moksha-glass-line);
  color: var(--moksha-muted);
  display: flex;
  font-size: 0.65rem;
  gap: 0.4rem;
  justify-content: center;
  padding-top: 0.85rem;
}

.session-check {
  align-items: center;
  color: var(--moksha-muted);
  display: flex;
  flex-direction: column;
  font-size: 0.76rem;
  gap: 0.6rem;
}

.session-check span {
  animation: pulse 1.2s ease-in-out infinite;
  background: var(--moksha-accent);
  border-radius: 50%;
  box-shadow: 0 0 0 0.45rem var(--moksha-accent-soft);
  height: 0.55rem;
  width: 0.55rem;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  50% {
    opacity: 0.4;
    transform: scale(0.78);
  }
}

@media (max-width: 520px) {
  .auth-surface {
    align-items: start;
    padding: 4.2rem 0.7rem 1rem;
  }

  .auth-panel {
    border-radius: 0.85rem;
    padding: 1rem;
  }

  .auth-panel h1 {
    font-size: 1.5rem;
  }
}

@media (hover: none), (pointer: coarse) {
  .auth-surface::before {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-surface::before {
    display: none;
  }
}
</style>
