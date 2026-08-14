<script setup lang="ts">
import type { ModelProfile, Scripture } from "~/types/api";

type SettingsSection =
  "general" | "models" | "connections" | "scriptures" | "account";

type ModelOption = {
  label: string;
  value: string;
  modelId: string;
  category: "local" | "api";
  provider: string;
  contextWindow: number;
  selectable: boolean;
  status: string;
};

const props = defineProps<{
  open: boolean;
  user: string;
  theme: "system" | "light" | "dark";
  modelProfile: string;
  fallbackModelProfile: string;
  modelOptions: ModelOption[];
  profiles: ModelProfile[];
  scriptures: Scripture[];
  message: string;
  messageSection: SettingsSection;
  saving?: boolean;
  probingConnectionId?: string;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
  theme: [value: "system" | "light" | "dark"];
  model: [profileId: string];
  "fallback-model": [profileId: string];
  provider: [
    payload: {
      name: string;
      dialect: "openai_compatible" | "ollama_compatible";
      endpoint_url: string;
      model_id: string;
      api_key: string;
      remote_data_consent: boolean;
    },
  ];
  probe: [connectionId: string];
  "remove-connection": [connectionId: string];
  section: [value: SettingsSection];
  signout: [];
}>();

const activeSection = ref<SettingsSection>("general");
const providerName = ref("");
const providerDialect = ref<"openai_compatible" | "ollama_compatible">(
  "openai_compatible",
);
const providerEndpoint = ref("");
const providerModel = ref("");
const providerKey = ref("");
const providerConsent = ref(false);
const removeConnectionId = ref("");

const sections: {
  id: SettingsSection;
  label: string;
  icon: string;
}[] = [
  { id: "general", label: "General", icon: "i-lucide-sliders-horizontal" },
  { id: "models", label: "Models", icon: "i-lucide-cpu" },
  { id: "connections", label: "Connections", icon: "i-lucide-plug" },
  { id: "scriptures", label: "Scriptures", icon: "i-lucide-library" },
  { id: "account", label: "Account", icon: "i-lucide-user-round" },
];

const indexedCount = computed(
  () => props.scriptures.filter((scripture) => scripture.is_indexed).length,
);

const connectedProfiles = computed(() =>
  props.profiles.filter(
    (profile) => profile.connection_dialect !== "builtin_ollama",
  ),
);

const connectionPendingRemoval = computed(() =>
  connectedProfiles.value.find(
    (profile) => profile.connection === removeConnectionId.value,
  ),
);

const visibleMessage = computed(() =>
  props.messageSection === activeSection.value ? props.message : "",
);

const localModelOptions = computed(() =>
  props.modelOptions.filter((option) => option.category === "local"),
);

const apiModelOptions = computed(() =>
  props.modelOptions.filter((option) => option.category === "api"),
);

const fallbackOptions = computed(() =>
  props.modelOptions.filter(
    (option) => option.value !== props.modelProfile && option.selectable,
  ),
);

function scriptureDetail(scripture: Scripture) {
  const job = scripture.current_indexing_job;
  if (job) {
    const volumeTotal = job.source_volumes || scripture.total_volumes;
    const volumeText = volumeTotal
      ? `${job.volumes_processed} of ${volumeTotal} source volumes scanned by OCR`
      : `${job.volumes_processed} source volumes scanned by OCR`;
    const pageTotal = job.source_pages || scripture.total_pages;
    const pagesScanned = job.chunks_indexed;
    const ocrStillRunning =
      pageTotal > 0 ? pagesScanned < pageTotal : job.progress <= 70;
    if (pagesScanned > 0) {
      if (job.source_pages > 0) {
        const suffix = ocrStillRunning ? " · waiting for embedding" : "";
        return `${volumeText} · ${pagesScanned.toLocaleString()} of ${job.source_pages.toLocaleString()} OCR pages scanned${suffix}`;
      }
      return `${volumeText} · ${pagesScanned.toLocaleString()} OCR pages scanned · waiting for embedding`;
    }
    if (ocrStillRunning) {
      const pages = pageTotal;
      return `${volumeText} · ${pages.toLocaleString()} pages queued for OCR/text extraction`;
    }
    if (job.source_pages > 0) {
      return `${volumeText} · ${pagesScanned.toLocaleString()} of ${job.source_pages.toLocaleString()} OCR pages scanned`;
    }
    return `${volumeText} · Preparing passages for embedding`;
  }
  if (
    scripture.latest_indexing_failure?.failure_code === "index_ocr_unavailable"
  ) {
    return "Local OCR engine or language model is not installed";
  }
  if (
    scripture.latest_indexing_failure?.failure_code ===
    "index_ocr_quality_failed"
  ) {
    return "OCR output failed exact-verse quality checks";
  }
  if (
    scripture.latest_indexing_failure?.failure_code ===
    "index_source_text_corrupt"
  ) {
    return "Source text failed exact-verse quality checks";
  }
  return `${scripture.total_volumes} volumes, ${scripture.total_pages.toLocaleString()} pages`;
}

function scriptureStatus(scripture: Scripture) {
  if (scripture.is_indexed) return "Indexed";
  const job = scripture.current_indexing_job;
  if (!job) {
    const failureCode = scripture.latest_indexing_failure?.failure_code;
    if (failureCode === "index_source_text_corrupt") return "Source needs OCR";
    if (failureCode === "index_ocr_unavailable") return "Install OCR model";
    if (failureCode === "index_ocr_quality_failed") return "OCR needs review";
    return scripture.latest_indexing_failure ? "Index failed" : "Pending";
  }
  if (job.status === "PENDING") return "Queued";
  if (isOcrRunning(scripture)) {
    return `OCR ${indexingDisplayPercent(scripture)}%`;
  }
  return `Indexing ${indexingDisplayPercent(scripture)}%`;
}

function indexingPhase(scripture: Scripture) {
  const job = scripture.current_indexing_job;
  if (!job) return "";
  if (job.status === "PENDING") return "Waiting for worker";
  if (isOcrRunning(scripture)) return "Running local OCR";
  if (job.progress < 70) return "Reading source volumes";
  if (job.progress < 85) return "Embedding passages";
  if (job.progress < 100) return "Qualifying retrieval";
  return "Activating index";
}

function isOcrRunning(scripture: Scripture) {
  const job = scripture.current_indexing_job;
  if (!job) return false;
  const pageTotal = job.source_pages || scripture.total_pages;
  return (
    job.chunks_indexed > 0 && pageTotal > 0 && job.chunks_indexed < pageTotal
  );
}

function indexingDisplayPercent(scripture: Scripture) {
  const job = scripture.current_indexing_job;
  if (!job) return scripture.is_indexed ? 100 : 0;
  if (isOcrRunning(scripture) && job.source_pages > 0) {
    return Math.max(
      1,
      Math.min(99, Math.round((job.chunks_indexed / job.source_pages) * 100)),
    );
  }
  return job.progress;
}

function formatContextWindow(tokens: number) {
  if (tokens >= 1000 && tokens % 1000 === 0) return `${tokens / 1000}K context`;
  if (tokens >= 1024 && tokens % 1024 === 0) return `${tokens / 1024}K context`;
  return `${tokens.toLocaleString()} token context`;
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    configured: "Configured",
    disconnected: "Not checked",
    checking: "Checking",
    connected: "Connected",
    degraded: "Degraded",
    auth_invalid: "Key rejected",
    endpoint_invalid: "Invalid endpoint",
    unreachable: "Unreachable",
    rate_limited: "Rate limited",
    quota_limited: "Quota limited",
    model_unavailable: "Model unavailable",
  };
  return labels[status] || status.replaceAll("_", " ");
}

function selectSection(section: SettingsSection) {
  activeSection.value = section;
  emit("section", section);
}

function submitProvider() {
  emit("provider", {
    name: providerName.value.trim(),
    dialect: providerDialect.value,
    endpoint_url: providerEndpoint.value.trim(),
    model_id: providerModel.value.trim(),
    api_key: providerKey.value,
    remote_data_consent: providerConsent.value,
  });
}

watch(
  () => props.message,
  (message) => {
    if (!message.toLowerCase().includes("connection saved")) return;
    providerName.value = "";
    providerEndpoint.value = "";
    providerModel.value = "";
    providerKey.value = "";
    providerConsent.value = false;
  },
);
</script>

<template>
  <UModal
    :open="open"
    title="Settings"
    description="Manage your Moksha AI experience"
    :ui="{
      content: 'settings-dialog',
      header: 'settings-dialog__header',
      body: 'settings-dialog__body',
      overlay: 'settings-dialog__overlay',
    }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div class="settings-layout">
        <nav class="settings-nav" aria-label="Settings sections">
          <button
            v-for="section in sections"
            :key="section.id"
            type="button"
            :aria-current="activeSection === section.id ? 'page' : undefined"
            @click="selectSection(section.id)"
          >
            <UIcon :name="section.icon" aria-hidden="true" />
            {{ section.label }}
          </button>
        </nav>

        <div class="settings-content">
          <section v-if="activeSection === 'general'" class="settings-section">
            <header>
              <h2>Appearance</h2>
              <p>Choose how Moksha AI looks on this account.</p>
            </header>

            <div class="setting-row setting-row--stack">
              <div>
                <strong>Theme</strong>
                <span>Saved across your signed-in devices.</span>
              </div>
              <div class="theme-choice" role="radiogroup" aria-label="Theme">
                <button
                  v-for="option in [
                    {
                      label: 'System',
                      value: 'system',
                      icon: 'i-lucide-monitor',
                    },
                    { label: 'Light', value: 'light', icon: 'i-lucide-sun' },
                    { label: 'Dark', value: 'dark', icon: 'i-lucide-moon' },
                  ] as const"
                  :key="option.value"
                  type="button"
                  role="radio"
                  :aria-checked="theme === option.value"
                  @click="emit('theme', option.value)"
                >
                  <UIcon :name="option.icon" aria-hidden="true" />
                  {{ option.label }}
                </button>
              </div>
            </div>

            <div class="setting-row">
              <div>
                <strong>Motion</strong>
                <span>Subtle light responds to your pointer.</span>
              </div>
              <span class="setting-value"
                >Follows device accessibility settings</span
              >
            </div>
          </section>

          <section v-if="activeSection === 'models'" class="settings-section">
            <header>
              <h2>Response models</h2>
              <p>Choose where new responses are generated.</p>
            </header>

            <div
              v-if="modelOptions.length"
              class="model-groups"
              role="radiogroup"
              aria-label="Primary response model"
            >
              <section v-if="localModelOptions.length" class="model-group">
                <h3>On this computer</h3>
                <div class="model-list">
                  <button
                    v-for="option in localModelOptions"
                    :key="option.value"
                    class="model-option"
                    type="button"
                    role="radio"
                    :disabled="!option.selectable"
                    :aria-checked="modelProfile === option.value"
                    @click="emit('model', option.value)"
                  >
                    <span class="model-option__icon">
                      <UIcon name="i-lucide-hard-drive" aria-hidden="true" />
                    </span>
                    <span class="model-option__copy">
                      <strong>{{ option.label }}</strong>
                      <small class="model-option__id">{{
                        option.modelId
                      }}</small>
                      <small
                        >Local / {{ option.provider }} /
                        {{ formatContextWindow(option.contextWindow) }}</small
                      >
                    </span>
                    <span
                      :class="[
                        'connection-state',
                        `connection-state--${option.status}`,
                      ]"
                    >
                      <i aria-hidden="true" />
                      {{ statusLabel(option.status) }}
                    </span>
                    <UIcon
                      v-if="modelProfile === option.value"
                      class="selected-check"
                      name="i-lucide-check"
                      aria-hidden="true"
                    />
                  </button>
                </div>
              </section>

              <section v-if="apiModelOptions.length" class="model-group">
                <h3>API connections</h3>
                <div class="model-list">
                  <button
                    v-for="option in apiModelOptions"
                    :key="option.value"
                    class="model-option"
                    type="button"
                    role="radio"
                    :disabled="!option.selectable"
                    :aria-checked="modelProfile === option.value"
                    @click="emit('model', option.value)"
                  >
                    <span class="model-option__icon">
                      <UIcon name="i-lucide-cloud" aria-hidden="true" />
                    </span>
                    <span class="model-option__copy">
                      <strong>{{ option.label }}</strong>
                      <small class="model-option__id">{{
                        option.modelId
                      }}</small>
                      <small
                        >{{ option.provider }} /
                        {{ formatContextWindow(option.contextWindow) }}</small
                      >
                    </span>
                    <span
                      :class="[
                        'connection-state',
                        `connection-state--${option.status}`,
                      ]"
                    >
                      <i aria-hidden="true" />
                      {{ statusLabel(option.status) }}
                    </span>
                    <UIcon
                      v-if="modelProfile === option.value"
                      class="selected-check"
                      name="i-lucide-check"
                      aria-hidden="true"
                    />
                  </button>
                </div>
              </section>
            </div>

            <div v-else class="settings-empty">
              <UIcon name="i-lucide-cpu" aria-hidden="true" />
              <strong>No available models</strong>
              <span>
                Install a local model or add an API connection to continue.
              </span>
            </div>

            <div v-if="modelOptions.length" class="fallback-setting">
              <label for="fallback-model">Fallback model</label>
              <span>
                Optional. Used only when the primary fails before a response
                begins.
              </span>
              <select
                id="fallback-model"
                :value="fallbackModelProfile"
                @change="
                  emit(
                    'fallback-model',
                    ($event.target as HTMLSelectElement).value,
                  )
                "
              >
                <option value="">No fallback</option>
                <option
                  v-for="option in fallbackOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }} / {{ option.modelId }}
                </option>
              </select>
              <small>
                A failed remote attempt may still be billed by its provider.
              </small>
            </div>

            <p class="settings-callout">
              <UIcon name="i-lucide-info" aria-hidden="true" />
              Your selections are saved to this account and apply to future
              responses. Existing chats stay intact.
            </p>
          </section>

          <section
            v-if="activeSection === 'connections'"
            class="settings-section"
          >
            <header>
              <h2>API connections</h2>
              <p>Use a provider-issued API key with an HTTPS endpoint.</p>
            </header>

            <ul
              v-if="connectedProfiles.length"
              class="connected-profiles"
              aria-label="Connected providers"
            >
              <li v-for="profile in connectedProfiles" :key="profile.id">
                <span class="model-option__icon">
                  <UIcon name="i-lucide-cloud" aria-hidden="true" />
                </span>
                <span>
                  <strong>{{ profile.name }}</strong>
                  <small>{{ profile.model_id }}</small>
                </span>
                <span
                  :class="[
                    'connection-state',
                    `connection-state--${profile.connection_status}`,
                  ]"
                >
                  <i aria-hidden="true" />
                  {{ statusLabel(profile.connection_status) }}
                </span>
                <button
                  v-if="profile.connection"
                  class="probe-action"
                  type="button"
                  :disabled="probingConnectionId === profile.connection"
                  @click="emit('probe', profile.connection)"
                >
                  <UIcon
                    :name="
                      probingConnectionId === profile.connection
                        ? 'i-lucide-loader-circle'
                        : 'i-lucide-refresh-cw'
                    "
                    :class="{
                      spin: probingConnectionId === profile.connection,
                    }"
                    aria-hidden="true"
                  />
                  {{
                    probingConnectionId === profile.connection
                      ? "Checking..."
                      : "Check"
                  }}
                </button>
                <button
                  v-if="profile.connection"
                  class="remove-connection-action"
                  type="button"
                  :aria-label="`Remove ${profile.name}`"
                  @click="removeConnectionId = profile.connection"
                >
                  <UIcon name="i-lucide-trash-2" aria-hidden="true" />
                </button>
              </li>
            </ul>

            <form
              class="provider-form"
              autocomplete="off"
              @submit.prevent="submitProvider"
            >
              <div class="provider-form__heading">
                <strong>Add connection</strong>
                <span>
                  A ChatGPT, Claude, or other app subscription does not
                  automatically include API access.
                </span>
              </div>

              <label class="field">
                <span>Provider name</span>
                <input
                  v-model="providerName"
                  required
                  autocomplete="organization"
                  name="provider-name"
                  placeholder="Example: OpenAI"
                />
              </label>

              <fieldset class="field">
                <legend>API type</legend>
                <div class="dialect-choice">
                  <label>
                    <input
                      v-model="providerDialect"
                      type="radio"
                      value="openai_compatible"
                    />
                    OpenAI-compatible
                  </label>
                  <label>
                    <input
                      v-model="providerDialect"
                      type="radio"
                      value="ollama_compatible"
                    />
                    Ollama-compatible
                  </label>
                </div>
              </fieldset>

              <div class="field-grid">
                <label class="field">
                  <span>HTTPS endpoint</span>
                  <input
                    v-model="providerEndpoint"
                    required
                    autocomplete="url"
                    inputmode="url"
                    name="provider-endpoint"
                    placeholder="https://api.provider.com/v1"
                  />
                </label>
                <label class="field">
                  <span>Model ID</span>
                  <input
                    v-model="providerModel"
                    required
                    autocomplete="off"
                    autocapitalize="none"
                    name="provider-model-id"
                    placeholder="Provider model identifier"
                    spellcheck="false"
                  />
                </label>
              </div>

              <label class="field">
                <span>API key</span>
                <input
                  v-model="providerKey"
                  :required="providerDialect === 'openai_compatible'"
                  autocomplete="new-password"
                  name="provider-api-key"
                  type="password"
                  :placeholder="
                    providerDialect === 'openai_compatible'
                      ? 'Encrypted before storage'
                      : 'Optional for this endpoint'
                  "
                />
              </label>

              <label class="consent">
                <input v-model="providerConsent" required type="checkbox" />
                <span>
                  I understand that prompts and retrieved context may be sent to
                  this provider.
                </span>
              </label>

              <button class="primary-action" type="submit" :disabled="saving">
                <UIcon
                  :name="
                    saving ? 'i-lucide-loader-circle' : 'i-lucide-plug-zap'
                  "
                  :class="{ spin: saving }"
                  aria-hidden="true"
                />
                {{ saving ? "Saving connection..." : "Add connection" }}
              </button>
            </form>
          </section>

          <section
            v-if="activeSection === 'scriptures'"
            class="settings-section"
          >
            <header>
              <h2>Scripture library</h2>
              <p>
                {{ indexedCount }} of {{ scriptures.length }} collections ready
                for grounded retrieval.
              </p>
            </header>

            <ul class="scripture-list">
              <li v-for="scripture in scriptures" :key="scripture.id">
                <span class="scripture-icon">
                  <UIcon name="i-lucide-book-open" aria-hidden="true" />
                </span>
                <span>
                  <strong>{{ scripture.name }}</strong>
                  <small>
                    {{ scriptureDetail(scripture) }}
                  </small>
                  <span
                    v-if="scripture.current_indexing_job"
                    class="index-progress"
                    :aria-label="`${scripture.name} ${scriptureStatus(scripture)}`"
                  >
                    <span>
                      <b
                        :style="{
                          width: `${indexingDisplayPercent(scripture)}%`,
                        }"
                      />
                    </span>
                    <em>{{ indexingPhase(scripture) }}</em>
                  </span>
                </span>
                <span
                  :class="[
                    'index-state',
                    {
                      'index-state--ready': scripture.is_indexed,
                      'index-state--running': scripture.current_indexing_job,
                      'index-state--failed':
                        !scripture.is_indexed &&
                        !scripture.current_indexing_job &&
                        scripture.latest_indexing_failure,
                    },
                  ]"
                >
                  <UIcon
                    :name="
                      scripture.is_indexed
                        ? 'i-lucide-circle-check'
                        : scripture.current_indexing_job
                          ? 'i-lucide-loader-circle'
                          : scripture.latest_indexing_failure
                            ? 'i-lucide-triangle-alert'
                            : 'i-lucide-clock-3'
                    "
                    aria-hidden="true"
                  />
                  {{ scriptureStatus(scripture) }}
                </span>
              </li>
            </ul>

            <div v-if="!scriptures.length" class="settings-empty">
              <UIcon name="i-lucide-library" aria-hidden="true" />
              <strong>No scripture collections discovered</strong>
              <span
                >Staff can add and index collections from Django admin.</span
              >
            </div>
          </section>

          <section v-if="activeSection === 'account'" class="settings-section">
            <header>
              <h2>Account</h2>
              <p>Your browser session and saved preferences.</p>
            </header>

            <div class="account-summary">
              <span>{{ user.slice(0, 1).toUpperCase() }}</span>
              <div>
                <strong>{{ user }}</strong>
                <small>Signed in</small>
              </div>
            </div>

            <div class="setting-row">
              <div>
                <strong>Session security</strong>
                <span>Protected by secure session and CSRF cookies.</span>
              </div>
              <span class="connection-state connection-state--connected">
                <i aria-hidden="true" />
                Active
              </span>
            </div>

            <button
              class="signout-action"
              type="button"
              @click="emit('signout')"
            >
              <UIcon name="i-lucide-log-out" aria-hidden="true" />
              Sign out
            </button>
          </section>

          <p v-if="visibleMessage" class="settings-message" role="status">
            <UIcon
              :name="
                visibleMessage.toLowerCase().includes('could not')
                  ? 'i-lucide-circle-alert'
                  : 'i-lucide-circle-check'
              "
              aria-hidden="true"
            />
            {{ visibleMessage }}
          </p>
        </div>
      </div>
    </template>
  </UModal>

  <UModal
    :open="Boolean(removeConnectionId)"
    title="Remove API connection?"
    description="This revokes the stored credential and removes its models from your account."
    @update:open="!$event && (removeConnectionId = '')"
  >
    <template #body>
      <div class="remove-connection-dialog">
        <p>
          <strong>{{ connectionPendingRemoval?.name }}</strong> will no longer
          be available for new responses.
        </p>
        <div>
          <button
            class="secondary-action"
            type="button"
            @click="removeConnectionId = ''"
          >
            Cancel
          </button>
          <button
            class="danger-action"
            type="button"
            :disabled="saving"
            @click="
              emit('remove-connection', removeConnectionId);
              removeConnectionId = '';
            "
          >
            Remove connection
          </button>
        </div>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
:global(.settings-dialog__overlay) {
  backdrop-filter: blur(16px) saturate(0.88);
  background: rgb(7 11 9 / 68%);
}

:global(.settings-dialog) {
  background: var(--moksha-modal);
  border: 1px solid var(--moksha-glass-line);
  backdrop-filter: blur(30px) saturate(1.08);
  border-radius: 0.5rem;
  box-shadow: var(--moksha-shadow-modal);
  height: min(42rem, calc(100svh - 3rem));
  max-width: 46rem;
  overflow: hidden;
  width: min(46rem, calc(100vw - 2rem));
}

:global(.settings-dialog__header) {
  background: var(--moksha-modal);
  border-bottom: 1px solid var(--moksha-glass-line);
  min-height: 4rem;
  padding: 0.8rem 1rem;
}

:global(.settings-dialog__body) {
  min-height: 0;
  overflow: hidden;
  padding: 0;
}

.settings-layout {
  display: grid;
  grid-template-columns: 10.5rem minmax(0, 1fr);
  height: 100%;
  min-height: 0;
}

.settings-nav {
  background: var(--moksha-settings-nav);
  border-right: 1px solid var(--moksha-glass-line);
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  padding: 0.7rem;
}

.settings-nav button {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 0.55rem;
  color: var(--moksha-muted);
  display: flex;
  font-size: 0.79rem;
  font-weight: 620;
  gap: 0.55rem;
  min-height: 2.3rem;
  padding: 0 0.65rem;
  text-align: left;
}

.settings-nav button:hover {
  background: var(--moksha-control);
  color: var(--moksha-ink);
}

.settings-nav button[aria-current="page"] {
  background: var(--moksha-accent-soft);
  color: var(--moksha-accent-ink);
  font-weight: 700;
}

.settings-content {
  min-height: 0;
  overflow: auto;
  padding: 1.25rem 1.35rem 1.5rem;
  position: relative;
}

.settings-section {
  display: grid;
  gap: 1.15rem;
}

.settings-section > header h2 {
  color: var(--moksha-ink);
  font-size: 1rem;
  font-weight: 730;
  margin: 0;
}

.settings-section > header p {
  color: var(--moksha-muted);
  font-size: 0.78rem;
  margin: 0.25rem 0 0;
}

.setting-row {
  align-items: center;
  border-bottom: 1px solid var(--moksha-glass-line);
  display: flex;
  gap: 1rem;
  justify-content: space-between;
  padding: 0.85rem 0;
}

.setting-row--stack {
  align-items: stretch;
  flex-direction: column;
}

.setting-row > div:first-child,
.provider-form__heading {
  display: grid;
  gap: 0.18rem;
}

.setting-row strong,
.provider-form__heading strong {
  color: var(--moksha-ink);
  font-size: 0.82rem;
}

.setting-row span,
.provider-form__heading span,
.setting-value {
  color: var(--moksha-muted);
  font-size: 0.73rem;
}

.setting-value {
  max-width: 14rem;
  text-align: right;
}

.theme-choice {
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.65rem;
  display: grid;
  gap: 0.2rem;
  grid-template-columns: repeat(3, 1fr);
  padding: 0.22rem;
}

.theme-choice button {
  align-items: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 0.48rem;
  color: var(--moksha-muted);
  display: flex;
  font-size: 0.76rem;
  font-weight: 650;
  gap: 0.4rem;
  justify-content: center;
  min-height: 2.2rem;
}

.theme-choice button[aria-checked="true"] {
  background: var(--moksha-glass-raised);
  border-color: var(--moksha-glass-line);
  box-shadow: 0 0.25rem 0.7rem rgb(12 17 14 / 8%);
  color: var(--moksha-ink);
}

.model-list,
.connected-profiles,
.scripture-list {
  display: grid;
  gap: 0.45rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.model-groups {
  display: grid;
  gap: 1rem;
}

.model-group {
  display: grid;
  gap: 0.4rem;
}

.model-group h3 {
  color: var(--moksha-muted);
  font-size: 0.67rem;
  font-weight: 760;
  letter-spacing: 0;
  margin: 0;
  text-transform: uppercase;
}

.model-option,
.connected-profiles li,
.scripture-list li {
  align-items: center;
  background: var(--moksha-control);
  border: 1px solid transparent;
  border-radius: 0.7rem;
  color: var(--moksha-ink);
  display: grid;
  gap: 0.65rem;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  min-height: 3.45rem;
  padding: 0.55rem 0.65rem;
  text-align: left;
}

.model-option__copy {
  display: grid;
  gap: 0.06rem;
  min-width: 0;
}

.model-option__id {
  color: var(--moksha-ink) !important;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-option:hover {
  border-color: var(--moksha-glass-line);
}

.model-option:disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.model-option:disabled:hover {
  border-color: transparent;
}

.model-option[aria-checked="true"] {
  background: var(--moksha-accent-soft);
  border-color: var(--moksha-accent-line);
}

.model-option__icon,
.scripture-icon {
  align-items: center;
  background: var(--moksha-glass-raised);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.55rem;
  color: var(--moksha-accent);
  display: flex;
  height: 2rem;
  justify-content: center;
  width: 2rem;
}

.model-option > span:nth-child(2),
.connected-profiles li > span:nth-child(2),
.scripture-list li > span:nth-child(2) {
  display: grid;
  gap: 0.12rem;
  min-width: 0;
}

.model-option strong,
.connected-profiles strong,
.scripture-list strong {
  font-size: 0.78rem;
}

.model-option small,
.connected-profiles small,
.scripture-list small {
  color: var(--moksha-muted);
  font-size: 0.68rem;
}

.selected-check {
  color: var(--moksha-accent);
}

.connection-state,
.index-state {
  align-items: center;
  color: var(--moksha-muted);
  display: inline-flex;
  font-size: 0.66rem;
  gap: 0.35rem;
  text-transform: capitalize;
  white-space: nowrap;
}

.connection-state i {
  background: currentcolor;
  border-radius: 50%;
  height: 0.38rem;
  width: 0.38rem;
}

.connection-state--connected,
.index-state--ready {
  color: var(--moksha-success);
}

.connection-state--configured {
  color: var(--moksha-accent);
}

.index-state--running {
  color: var(--moksha-accent);
}

.index-state--failed {
  color: var(--moksha-error);
}

.connection-state--degraded,
.connection-state--checking,
.connection-state--rate_limited,
.connection-state--quota_limited {
  color: var(--moksha-warning);
}

.connection-state--auth_invalid,
.connection-state--endpoint_invalid,
.connection-state--unreachable,
.connection-state--model_unavailable {
  color: var(--moksha-error);
}

.settings-callout {
  align-items: start;
  background: var(--moksha-info-soft);
  border-radius: 0.65rem;
  color: var(--moksha-info);
  display: flex;
  font-size: 0.72rem;
  gap: 0.45rem;
  margin: 0;
  padding: 0.65rem 0.75rem;
}

.fallback-setting {
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.7rem;
  display: grid;
  gap: 0.3rem;
  padding: 0.75rem;
}

.fallback-setting label {
  color: var(--moksha-ink);
  font-size: 0.78rem;
  font-weight: 700;
}

.fallback-setting > span,
.fallback-setting > small {
  color: var(--moksha-muted);
  font-size: 0.68rem;
}

.fallback-setting select {
  appearance: auto;
  background: var(--moksha-glass-raised);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.55rem;
  color: var(--moksha-ink);
  font-size: 0.76rem;
  min-height: 2.35rem;
  padding: 0 0.65rem;
  width: 100%;
}

.fallback-setting select:focus {
  border-color: var(--moksha-focus);
  box-shadow: 0 0 0 3px var(--moksha-focus-ring);
  outline: 0;
}

.fallback-setting option {
  background: var(--moksha-modal);
  color: var(--moksha-ink);
}

.connected-profiles li {
  grid-template-columns: auto minmax(0, 1fr) auto auto;
}

.probe-action {
  align-items: center;
  background: var(--moksha-glass-raised);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.5rem;
  color: var(--moksha-ink);
  display: inline-flex;
  font-size: 0.68rem;
  font-weight: 680;
  gap: 0.3rem;
  min-height: 1.9rem;
  padding: 0 0.55rem;
}

.remove-connection-action {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 0.45rem;
  color: var(--moksha-muted);
  display: inline-flex;
  height: 1.9rem;
  justify-content: center;
  width: 1.9rem;
}

.remove-connection-action:hover {
  background: var(--moksha-error-soft);
  color: var(--moksha-error);
}

.probe-action:disabled {
  color: var(--moksha-muted);
}

.provider-form {
  border-top: 1px solid var(--moksha-glass-line);
  display: grid;
  gap: 0.8rem;
  padding-top: 1.15rem;
}

.field {
  border: 0;
  display: grid;
  gap: 0.35rem;
  margin: 0;
  min-width: 0;
  padding: 0;
}

.field > span,
.field legend {
  color: var(--moksha-ink);
  font-size: 0.72rem;
  font-weight: 680;
}

.field input {
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.58rem;
  color: var(--moksha-ink);
  font-size: 0.78rem;
  min-height: 2.45rem;
  padding: 0 0.7rem;
  width: 100%;
}

.field input:focus {
  border-color: var(--moksha-focus);
  box-shadow: 0 0 0 3px var(--moksha-focus-ring);
  outline: 0;
}

.field-grid {
  display: grid;
  gap: 0.7rem;
  grid-template-columns: 1.2fr 0.8fr;
}

.dialect-choice {
  display: flex;
  gap: 0.5rem;
}

.dialect-choice label,
.consent {
  align-items: center;
  color: var(--moksha-muted);
  display: flex;
  font-size: 0.72rem;
  gap: 0.4rem;
}

.dialect-choice input,
.consent input {
  accent-color: var(--moksha-accent);
  flex: 0 0 auto;
  height: 0.9rem;
  width: 0.9rem;
}

.consent {
  align-items: start;
}

.consent input {
  margin-top: 0.13rem;
}

.primary-action,
.signout-action {
  align-items: center;
  border-radius: 0.6rem;
  display: inline-flex;
  font-size: 0.76rem;
  font-weight: 680;
  gap: 0.45rem;
  justify-content: center;
  min-height: 2.4rem;
  padding: 0 0.85rem;
  width: fit-content;
}

.primary-action {
  background: var(--moksha-primary);
  border: 0;
  color: var(--moksha-primary-ink);
}

.signout-action {
  background: var(--moksha-error-soft);
  border: 1px solid var(--moksha-error-line);
  color: var(--moksha-error);
}

.scripture-list li {
  grid-template-columns: auto minmax(0, 1fr) auto;
}

.index-state {
  gap: 0.3rem;
}

.index-progress {
  display: grid;
  gap: 0.22rem;
  margin-top: 0.2rem;
}

.index-progress > span {
  background: var(--moksha-glass-raised);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 999px;
  height: 0.42rem;
  overflow: hidden;
}

.index-progress b {
  background: linear-gradient(
    90deg,
    var(--moksha-accent),
    var(--moksha-success)
  );
  border-radius: inherit;
  display: block;
  height: 100%;
  transition: width 220ms ease;
}

.index-progress em {
  color: var(--moksha-muted);
  font-size: 0.64rem;
  font-style: normal;
}

.settings-empty {
  align-items: center;
  color: var(--moksha-muted);
  display: flex;
  flex-direction: column;
  padding: 2rem;
  text-align: center;
}

.settings-empty strong {
  color: var(--moksha-ink);
  font-size: 0.8rem;
  margin-top: 0.5rem;
}

.settings-empty span {
  font-size: 0.72rem;
  margin-top: 0.2rem;
}

.account-summary {
  align-items: center;
  background: var(--moksha-control);
  border-radius: 0.7rem;
  display: flex;
  gap: 0.7rem;
  padding: 0.7rem;
}

.account-summary > span {
  align-items: center;
  background: var(--moksha-accent-soft);
  border-radius: 50%;
  color: var(--moksha-accent-ink);
  display: flex;
  font-weight: 760;
  height: 2.3rem;
  justify-content: center;
  width: 2.3rem;
}

.account-summary div {
  display: grid;
}

.account-summary strong {
  font-size: 0.8rem;
}

.account-summary small {
  color: var(--moksha-muted);
  font-size: 0.7rem;
}

.settings-message {
  align-items: center;
  background: var(--moksha-glass-raised);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.6rem;
  bottom: 0.6rem;
  box-shadow: 0 0.5rem 1.4rem rgb(11 16 13 / 12%);
  color: var(--moksha-ink);
  display: flex;
  font-size: 0.72rem;
  gap: 0.4rem;
  margin: 0;
  padding: 0.5rem 0.65rem;
  position: sticky;
}

.remove-connection-dialog {
  display: grid;
  gap: 1rem;
}

.remove-connection-dialog p {
  color: var(--moksha-muted);
  font-size: 0.78rem;
  margin: 0;
}

.remove-connection-dialog > div {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.secondary-action,
.danger-action {
  border-radius: 0.5rem;
  font-size: 0.75rem;
  font-weight: 680;
  min-height: 2.3rem;
  padding: 0 0.8rem;
}

.secondary-action {
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  color: var(--moksha-ink);
}

.danger-action {
  background: var(--moksha-error);
  border: 0;
  color: #fff;
}

.spin {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 680px) {
  :global(.settings-dialog) {
    border-radius: 0;
    height: 100svh;
    max-height: none;
    width: 100vw;
  }

  .settings-layout {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
  }

  .settings-nav {
    border-bottom: 1px solid var(--moksha-glass-line);
    border-right: 0;
    display: grid;
    gap: 0.15rem;
    grid-template-columns: repeat(5, minmax(3.2rem, 1fr));
    overflow-x: auto;
    padding: 0.4rem;
  }

  .settings-nav button {
    flex-direction: column;
    font-size: 0.68rem;
    gap: 0.15rem;
    min-height: 3rem;
    padding: 0.25rem;
  }

  .settings-content {
    padding: 1rem;
  }

  .field-grid {
    grid-template-columns: 1fr;
  }

  .setting-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .setting-value {
    max-width: none;
    text-align: left;
  }

  .model-option {
    grid-template-columns: auto minmax(0, 1fr) auto;
  }

  .connection-state {
    grid-column: 2;
  }

  .selected-check {
    grid-column: 3;
    grid-row: 1 / span 2;
  }

  .scripture-list li {
    align-items: start;
    grid-template-columns: auto minmax(0, 1fr);
  }

  .scripture-list .index-state {
    grid-column: 2;
  }
}
</style>
