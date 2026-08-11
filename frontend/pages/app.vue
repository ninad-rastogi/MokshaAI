<script setup lang="ts">
import { ApiRequestError } from "~/composables/useApi";
import type {
  ChatSummary,
  Citation,
  Message,
  ModelProfile,
  Scripture,
  UserProfile,
} from "~/types/api";

definePageMeta({ ssr: false });

const api = useApi();
const stream = useRunStream();
const colorMode = useColorMode();

const workspace = ref<HTMLElement | null>(null);
const messageViewport = ref<HTMLElement | null>(null);
const userProfile = ref<UserProfile | null>(null);
const chats = ref<ChatSummary[]>([]);
const messages = ref<Message[]>([]);
const scriptures = ref<Scripture[]>([]);
const profiles = ref<ModelProfile[]>([]);
const ollamaAvailable = ref<boolean | null>(null);
const activeChatId = ref("");
const prompt = ref("");
const lastPrompt = ref("");
const activeRunId = ref("");
const streamingText = ref("");
const streamingSources = ref<Citation[]>([]);
const runState = ref("ready");
const connectionState = ref<"online" | "offline" | "error">("online");
const modelProfile = ref("");
const fallbackModelProfile = ref("");
const busy = ref(false);
const streamDisconnected = ref(false);
const error = ref("");
const search = ref("");
const showArchived = ref(false);
const settingsOpen = ref(false);
const settingsSection = ref<
  "general" | "models" | "connections" | "scriptures" | "account"
>("general");
const historyOpen = ref(false);
const shellReady = ref(false);
const workspaceLoading = ref(true);
const historyLoading = ref(false);
const renameChatId = ref("");
const renameName = ref("");
const deleteChatId = ref("");
const settingsMessage = ref("");
const settingsMessageSection = ref<
  "general" | "models" | "connections" | "scriptures" | "account"
>("general");
const settingsSaving = ref(false);
const probingConnectionId = ref("");
let pointerFrame = 0;
let scriptureRefreshTimer: ReturnType<typeof setTimeout> | undefined;
let runtimeHealthTimer: ReturnType<typeof setTimeout> | undefined;

const starterPrompts = [
  "I feel pulled in too many directions.",
  "How can I act without resentment?",
  "I cannot find peace with a difficult decision.",
];

const userLabel = computed(
  () =>
    userProfile.value?.spiritual_name ||
    userProfile.value?.email ||
    "Moksha AI",
);

const activeChat = computed(
  () => chats.value.find((chat) => chat.id === activeChatId.value) || null,
);

const isArchivedChat = computed(() => activeChat.value?.is_archived === true);

const modelOptions = computed(() =>
  profiles.value.map((profile) => {
    const isLocal = profile.connection_dialect === "builtin_ollama";
    const status = isLocal
      ? ollamaAvailable.value === true
        ? "connected"
        : ollamaAvailable.value === false
          ? "unreachable"
          : profile.connection_status
      : profile.connection_status;
    return {
      label: profile.name.replace(/\s\([0-9a-f]{8}\)$/, ""),
      value: profile.id,
      modelId: profile.model_id,
      category: isLocal ? ("local" as const) : ("api" as const),
      provider: isLocal
        ? "Ollama"
        : profile.connection_dialect === "openai_compatible"
          ? "OpenAI-compatible API"
          : "Ollama-compatible API",
      contextWindow: profile.context_window,
      selectable: ["connected", "degraded"].includes(status),
      status: status || "disconnected",
    };
  }),
);

const activeModelOption = computed(() =>
  modelOptions.value.find((option) => option.value === modelProfile.value),
);

const activeModelReady = computed(
  () => activeModelOption.value?.selectable === true,
);

const activeModelLabel = computed(
  () => activeModelOption.value?.label || "Choose a model",
);

const activeModelStatus = computed(
  () => activeModelOption.value?.status || "disconnected",
);

const activeModelStatusText = computed(() => {
  const labels: Record<string, string> = {
    connected: "Online",
    degraded: "Degraded",
    disconnected: "Offline",
    checking: "Checking",
    auth_invalid: "Key rejected",
    endpoint_invalid: "Endpoint error",
    unreachable: "Offline",
    rate_limited: "Rate limited",
    quota_limited: "Quota limited",
    model_unavailable: "Model unavailable",
  };
  return labels[activeModelStatus.value] || "Offline";
});

const activeModelDetail = computed(() => {
  if (!activeModelOption.value) return "No model selected";
  return `${activeModelOption.value.label} · ${activeModelOption.value.modelId}`;
});

const runLabel = computed(() => {
  const labels: Record<string, string> = {
    queued: "Preparing guidance",
    running: "Reflecting",
    cancelled: "Stopped",
    failed: "Response failed",
  };
  return labels[runState.value] || runState.value;
});

const connectionLabel = computed(() => {
  if (connectionState.value === "error" || error.value) return "Error";
  if (connectionState.value === "offline") return "Offline";
  return activeModelStatusText.value;
});

const connectionStatusText = computed(
  () => `${connectionLabel.value} · ${activeModelDetail.value}`,
);

const connectionTone = computed(() => {
  if (["Online", "Degraded", "Checking"].includes(connectionLabel.value)) {
    return "online";
  }
  if (
    [
      "Error",
      "Key rejected",
      "Endpoint error",
      "Rate limited",
      "Quota limited",
      "Model unavailable",
    ].includes(connectionLabel.value)
  ) {
    return "error";
  }
  return "offline";
});

const streamingMessage = computed<Message>(() => ({
  id: -1,
  role: "assistant",
  content: streamingText.value,
  mode: "STREAM",
  sources: streamingSources.value,
  created_at: new Date().toISOString(),
}));

const activeIndexingJobs = computed(() =>
  scriptures.value
    .map((scripture) => ({
      scripture,
      job: scripture.current_indexing_job,
    }))
    .filter(
      (
        entry,
      ): entry is {
        scripture: Scripture;
        job: NonNullable<Scripture["current_indexing_job"]>;
      } => Boolean(entry.job),
    ),
);

const scriptureRefreshDelay = computed(() =>
  activeIndexingJobs.value.length ? 3000 : 20000,
);

const scriptureProgressLabel = computed(() => {
  if (!scriptures.value.length) return "No collections";
  if (!activeIndexingJobs.value.length) {
    return `${scriptures.value.filter((scripture) => scripture.is_indexed).length}/${scriptures.value.length} ready`;
  }
  const ocrPages = activeIndexingJobs.value.reduce((sum, entry) => {
    if (entry.job.progress >= 70) return sum;
    return sum + entry.job.chunks_indexed;
  }, 0);
  if (ocrPages > 0) {
    const ocrTotal = activeIndexingJobs.value.reduce((sum, entry) => {
      if (entry.job.progress >= 70) return sum;
      return sum + entry.job.source_pages;
    }, 0);
    if (ocrTotal > 0) {
      return `OCR ${ocrPages.toLocaleString()}/${ocrTotal.toLocaleString()} pages`;
    }
    return `OCR ${ocrPages.toLocaleString()} pages`;
  }
  const average = Math.round(
    activeIndexingJobs.value.reduce(
      (sum, entry) => sum + entry.job.progress,
      0,
    ) / activeIndexingJobs.value.length,
  );
  return `${activeIndexingJobs.value.length} indexing · ${average}%`;
});

const scriptureProgressDetail = computed(() => {
  if (!activeIndexingJobs.value.length) {
    return `${scriptures.value.filter((scripture) => scripture.is_indexed).length} of ${scriptures.value.length} scripture collections ready`;
  }
  return activeIndexingJobs.value
    .map((entry) => {
      if (entry.job.progress < 70 && entry.job.chunks_indexed > 0) {
        if (entry.job.source_pages > 0) {
          return `${entry.scripture.name} OCR ${entry.job.chunks_indexed.toLocaleString()} of ${entry.job.source_pages.toLocaleString()} pages`;
        }
        return `${entry.scripture.name} OCR ${entry.job.chunks_indexed.toLocaleString()} pages`;
      }
      return `${entry.scripture.name} ${entry.job.progress}%`;
    })
    .join(", ");
});

const scriptureProgressTone = computed(() =>
  activeIndexingJobs.value.length ? "running" : "idle",
);

onMounted(async () => {
  historyOpen.value = window.matchMedia("(min-width: 861px)").matches;
  shellReady.value = true;

  try {
    userProfile.value = await api.me();
    colorMode.preference = userProfile.value.preferred_theme;
  } catch {
    await navigateTo("/");
    return;
  }

  const results = await Promise.allSettled([
    loadChats(),
    loadScriptures(),
    loadProfiles(),
    loadRuntimeHealth(),
  ]);
  if (results.some((result) => result.status === "rejected")) {
    error.value =
      "Some workspace data could not load. Refresh the page to try again.";
  }
  try {
    await loadModelPreference();
  } catch {
    error.value =
      "Your saved model preference could not load. Refresh the page to try again.";
  }

  await ensureModelPreference();
  try {
    if (!activeChatId.value && !showArchived.value) {
      await createOrSelectDraft();
    } else {
      await loadMessages();
    }
  } catch {
    error.value =
      "Your conversations could not load. Refresh the page to try again.";
  } finally {
    workspaceLoading.value = false;
    scheduleScriptureRefresh();
    scheduleRuntimeHealthRefresh();
    await scrollToLatest("auto");
  }
});

onBeforeUnmount(() => {
  stream.close();
  clearTimeout(scriptureRefreshTimer);
  clearTimeout(runtimeHealthTimer);
  cancelAnimationFrame(pointerFrame);
  window.removeEventListener("keydown", handleWorkspaceShortcut);
});

onMounted(() => {
  window.addEventListener("keydown", handleWorkspaceShortcut);
});

watch(
  () => [messages.value.length, streamingText.value],
  async () => {
    await nextTick();
    await scrollToLatest("smooth");
  },
);

async function loadProfiles() {
  const page = await api.modelProfiles();
  profiles.value = page.results;
}

async function loadRuntimeHealth() {
  try {
    const readiness = await api.readiness();
    ollamaAvailable.value = readiness.ollama;
  } catch {
    ollamaAvailable.value = false;
  }
}

function scheduleRuntimeHealthRefresh() {
  clearTimeout(runtimeHealthTimer);
  runtimeHealthTimer = setTimeout(async () => {
    await loadRuntimeHealth();
    scheduleRuntimeHealthRefresh();
  }, 15000);
}

async function loadModelPreference() {
  const preference = await api.modelPreference();
  modelProfile.value = preference.primary_profile || "";
  fallbackModelProfile.value =
    preference.ordered_fallback_profile_ids.find((profileId) =>
      profiles.value.some((profile) => profile.id === profileId),
    ) || "";
}

async function ensureModelPreference() {
  if (modelProfile.value || !profiles.value.length) return;
  const local =
    profiles.value.find(
      (profile) => profile.connection_dialect === "builtin_ollama",
    ) || profiles.value.find((profile) => profile.is_admin_default);
  const preferred = local || profiles.value[0];
  if (!preferred) return;
  modelProfile.value = preferred.id;
  try {
    await api.updateModelPreference(preferred.id, []);
  } catch {
    settingsMessageSection.value = "models";
    settingsMessage.value =
      "A model is available, but the account preference could not be saved.";
  }
}

async function loadChats() {
  const page = await api.chats(showArchived.value);
  chats.value = page.results;
  if (!chats.value.some((chat) => chat.id === activeChatId.value)) {
    activeChatId.value = chats.value[0]?.id || "";
  }
}

async function loadMessages() {
  if (!activeChatId.value) {
    messages.value = [];
    return;
  }
  const page = await api.messages(activeChatId.value);
  messages.value = page.results;
}

async function loadScriptures() {
  const page = await api.scriptures();
  scriptures.value = page.results;
}

function scheduleScriptureRefresh() {
  clearTimeout(scriptureRefreshTimer);
  scriptureRefreshTimer = setTimeout(async () => {
    try {
      await loadScriptures();
    } catch {
      // Keep last known progress visible while a transient refresh fails.
    } finally {
      scheduleScriptureRefresh();
    }
  }, scriptureRefreshDelay.value);
}

async function selectChat(chatId: string) {
  activeChatId.value = chatId;
  closeHistoryOnCompactViewport();
  error.value = "";
  streamingText.value = "";
  streamingSources.value = [];
  await loadMessages();
  await scrollToLatest("auto");
}

async function createOrSelectDraft() {
  const existingDraft = chats.value.find(
    (chat) => !chat.is_archived && chat.message_count === 0,
  );
  if (existingDraft) {
    await selectChat(existingDraft.id);
    return;
  }
  const chat = await api.createChat();
  chats.value = [chat, ...chats.value];
  await selectChat(chat.id);
}

async function newChat() {
  showArchived.value = false;
  search.value = "";
  closeHistoryOnCompactViewport();
  error.value = "";
  await createOrSelectDraft();
}

function closeHistoryOnCompactViewport() {
  if (!window.matchMedia("(min-width: 861px)").matches) {
    historyOpen.value = false;
  }
}

async function toggleArchived(nextValue: boolean) {
  if (showArchived.value === nextValue) return;
  historyLoading.value = true;
  showArchived.value = nextValue;
  search.value = "";
  messages.value = [];
  try {
    await loadChats();
    await loadMessages();
  } finally {
    historyLoading.value = false;
  }
}

function startRename(chat: ChatSummary) {
  renameChatId.value = chat.id;
  renameName.value = chat.name;
}

async function saveRename() {
  const nextName = renameName.value.trim();
  if (!renameChatId.value || !nextName) return;
  try {
    const updated = await api.renameChat(renameChatId.value, nextName);
    chats.value = chats.value.map((chat) =>
      chat.id === updated.id ? updated : chat,
    );
    renameChatId.value = "";
    renameName.value = "";
  } catch {
    error.value = "This conversation could not be renamed. Try again.";
  }
}

async function archiveChat(chat: ChatSummary) {
  try {
    const updated = chat.is_archived
      ? await api.unarchiveChat(chat.id)
      : await api.archiveChat(chat.id);
    chats.value = chats.value.filter((item) => item.id !== updated.id);
    if (activeChatId.value === updated.id) {
      activeChatId.value = chats.value[0]?.id || "";
      await loadMessages();
    }
  } catch (archiveError) {
    error.value =
      archiveError instanceof ApiRequestError && archiveError.status === 409
        ? "Stop the active response before archiving this conversation."
        : "This conversation could not be updated. Try again.";
  }
}

async function restoreActiveArchivedChat() {
  if (!activeChat.value) return;
  await archiveChat(activeChat.value);
  await toggleArchived(false);
}

function askDelete(chat: ChatSummary) {
  deleteChatId.value = chat.id;
}

async function confirmDelete() {
  if (!deleteChatId.value) return;
  try {
    await api.deleteChat(deleteChatId.value);
    chats.value = chats.value.filter((chat) => chat.id !== deleteChatId.value);
    if (activeChatId.value === deleteChatId.value) {
      activeChatId.value = chats.value[0]?.id || "";
      await loadMessages();
    }
    deleteChatId.value = "";
  } catch (deleteError) {
    deleteChatId.value = "";
    error.value =
      deleteError instanceof ApiRequestError && deleteError.status === 409
        ? "Stop the active response before deleting this conversation."
        : "This conversation could not be deleted. Try again.";
  }
}

async function saveThemePreference(value: "system" | "light" | "dark") {
  colorMode.preference = value;
  settingsMessage.value = "";
  settingsMessageSection.value = "general";
  try {
    userProfile.value = await api.updateMe({ preferred_theme: value });
    settingsMessage.value = "Theme saved to your account.";
  } catch {
    settingsMessage.value = "Theme could not be saved. Try again.";
  }
}

async function toggleTheme() {
  const next = colorMode.value === "dark" ? "light" : "dark";
  await saveThemePreference(next);
}

async function saveModelPreference(profileId: string) {
  settingsMessageSection.value = "models";
  const previous = modelProfile.value;
  const previousFallback = fallbackModelProfile.value;
  modelProfile.value = profileId;
  if (fallbackModelProfile.value === profileId) {
    fallbackModelProfile.value = "";
  }
  settingsMessage.value = "";
  try {
    await api.updateModelPreference(
      profileId,
      fallbackModelProfile.value ? [fallbackModelProfile.value] : [],
    );
    settingsMessage.value = "Primary model saved.";
  } catch {
    modelProfile.value = previous;
    fallbackModelProfile.value = previousFallback;
    settingsMessage.value = "Model preference could not be saved. Try again.";
  }
}

async function saveFallbackModelPreference(profileId: string) {
  settingsMessageSection.value = "models";
  const previous = fallbackModelProfile.value;
  fallbackModelProfile.value =
    profileId && profileId !== modelProfile.value ? profileId : "";
  settingsMessage.value = "";
  try {
    await api.updateModelPreference(
      modelProfile.value,
      fallbackModelProfile.value ? [fallbackModelProfile.value] : [],
    );
    settingsMessage.value = fallbackModelProfile.value
      ? "Fallback model saved."
      : "Fallback model disabled.";
  } catch {
    fallbackModelProfile.value = previous;
    settingsMessage.value =
      "Fallback preference could not be saved. Try again.";
  }
}

async function removeProviderConnection(connectionId: string) {
  settingsMessageSection.value = "connections";
  settingsMessage.value = "";
  settingsSaving.value = true;
  try {
    await api.deleteModelConnection(connectionId);
    await loadProfiles();
    await loadModelPreference();
    await ensureModelPreference();
    settingsMessage.value =
      "Connection removed. Its encrypted credential has been revoked.";
  } catch {
    settingsMessage.value = "Connection could not be removed. Try again.";
  } finally {
    settingsSaving.value = false;
  }
}

async function addProviderConnection(payload: {
  name: string;
  dialect: "openai_compatible" | "ollama_compatible";
  endpoint_url: string;
  model_id: string;
  api_key: string;
  remote_data_consent: boolean;
}) {
  settingsMessageSection.value = "connections";
  settingsMessage.value = "";
  settingsSaving.value = true;
  try {
    await api.createModelConnection(payload);
    await loadProfiles();
    settingsMessage.value =
      "Connection saved. Check it before selecting its model.";
  } catch (providerError) {
    if (providerError instanceof ApiRequestError) {
      if (providerError.status === 400) {
        settingsMessage.value =
          "Connection rejected. Check the HTTPS endpoint, model ID, consent, and API key.";
      } else if (providerError.status === 503) {
        settingsMessage.value =
          "Encrypted key storage is unavailable. Ask an administrator to configure the BYOK master key.";
      } else {
        settingsMessage.value =
          "Provider could not be saved. Try again in a moment.";
      }
    } else {
      settingsMessage.value =
        "Provider could not be saved. Check the connection details.";
    }
  } finally {
    settingsSaving.value = false;
  }
}

async function probeProviderConnection(connectionId: string) {
  settingsMessageSection.value = "connections";
  probingConnectionId.value = connectionId;
  settingsMessage.value = "";
  try {
    const result = await api.probeModelConnection(connectionId);
    await loadProfiles();
    settingsMessage.value =
      result.status === "connected"
        ? "Connection checked successfully. Its model is now selectable."
        : result.detail || "The provider is not ready.";
  } catch (probeError) {
    await loadProfiles();
    settingsMessage.value =
      probeError instanceof ApiRequestError && probeError.status === 503
        ? "The provider could not be reached or did not expose this model."
        : "Connection check failed. Try again.";
  } finally {
    probingConnectionId.value = "";
  }
}

function useStarterPrompt(value: string) {
  prompt.value = value;
  nextTick(() => {
    document
      .querySelector<HTMLTextAreaElement>(".moksha-prompt textarea")
      ?.focus();
  });
}

function handleWorkspaceShortcut(event: KeyboardEvent) {
  if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== "k") {
    return;
  }
  event.preventDefault();
  void createOrSelectDraft();
}

async function send() {
  const message = prompt.value.trim();
  if (
    !message ||
    !activeChatId.value ||
    busy.value ||
    isArchivedChat.value ||
    !activeModelReady.value
  ) {
    if (!activeModelReady.value) {
      settingsMessageSection.value = "models";
      settingsMessage.value =
        "Select a connected model before sending a message.";
      settingsOpen.value = true;
    }
    return;
  }

  prompt.value = "";
  lastPrompt.value = message;
  busy.value = true;
  streamDisconnected.value = false;
  connectionState.value = "online";
  error.value = "";
  streamingText.value = "";
  streamingSources.value = [];
  runState.value = "queued";
  messages.value.push({
    id: Date.now(),
    role: "user",
    content: message,
    mode: "",
    sources: [],
    created_at: new Date().toISOString(),
  });

  try {
    const run = await api.createRun(
      activeChatId.value,
      message,
      modelProfile.value,
      crypto.randomUUID(),
    );
    activeRunId.value = run.id;
    connectRun(run.id);
  } catch (runError) {
    busy.value = false;
    runState.value = "failed";
    error.value = runStartError(runError);
  }
}

function runStartError(runError: unknown) {
  if (runError instanceof ApiRequestError) {
    if (runError.status === 429) {
      return "Moksha AI is at capacity. Wait a moment, then try again.";
    }
    if (runError.status === 409) {
      return "This conversation already has an active response.";
    }
    if (runError.status === 400) {
      return "This message or model selection could not be used.";
    }
  }
  return "The response could not start. Check your connection and try again.";
}

function connectRun(runId = activeRunId.value) {
  if (!runId) return;
  streamDisconnected.value = false;
  stream.connect(runId, {
    onOpen: () => {
      streamDisconnected.value = false;
      connectionState.value = "online";
    },
    onDisconnect: () => {
      if (busy.value) {
        streamDisconnected.value = true;
        connectionState.value = "offline";
      }
    },
    onEvent: (event) => {
      if (event.type === "state") runState.value = event.state;
      if (event.type === "delta") streamingText.value += event.text;
      if (event.type === "citation") {
        streamingSources.value.push(event.citation);
      }
      if (event.type === "error") {
        error.value =
          event.code === "generation_failed"
            ? "Moksha AI could not complete this response. Try again."
            : event.message;
        runState.value = "failed";
        connectionState.value = "error";
      }
      if (event.type === "done") {
        void finishRun(event.state);
      }
    },
  });
}

async function finishRun(state: string) {
  runState.value = state;
  busy.value = false;
  streamDisconnected.value = false;
  connectionState.value = state === "failed" ? "error" : "online";
  activeRunId.value = "";
  stream.close();
  try {
    await Promise.all([loadMessages(), loadChats()]);
  } finally {
    streamingText.value = "";
    streamingSources.value = [];
    await scrollToLatest("smooth");
  }
}

async function stopRun() {
  if (!activeRunId.value) return;
  try {
    await api.cancelRun(activeRunId.value);
  } finally {
    stream.close();
    busy.value = false;
    streamDisconnected.value = false;
    connectionState.value = "online";
    activeRunId.value = "";
    runState.value = "cancelled";
    await loadMessages();
  }
}

async function retryLast() {
  if (!lastPrompt.value || busy.value) return;
  prompt.value = lastPrompt.value;
  await send();
}

async function signOut() {
  await api.sessionLogout();
  await navigateTo("/");
}

function trackPointer(event: PointerEvent) {
  if (!workspace.value || event.pointerType === "touch") return;
  cancelAnimationFrame(pointerFrame);
  pointerFrame = requestAnimationFrame(() => {
    workspace.value?.style.setProperty("--pointer-x", `${event.clientX}px`);
    workspace.value?.style.setProperty("--pointer-y", `${event.clientY}px`);
  });
}

async function scrollToLatest(behavior: ScrollBehavior) {
  await nextTick();
  messageViewport.value?.scrollTo({
    top: messageViewport.value.scrollHeight,
    behavior,
  });
}
</script>

<template>
  <!--
    THESIS: A familiar conversation workspace seen through conservation glass,
    refusing oversized editorial panels and decorative spiritual motifs.
    OWN-WORLD: Mineral green, smoked glass, aged brass, compact Manrope type,
    manuscript-margin details, and pointer-responsive reflected light.
    STORY: Enter safely, share a difficult situation, follow visible response
    state, read grounded counsel, inspect citations, and retain control.
    FIRST VIEWPORT: Fixed compact history at left, quiet title rail above,
    centered conversation, and floating composer always reachable below.
    FORM: Operate mode; conservation reading-room workspace, chosen from seven
    grounded systems; fixed shell with local glass refraction.
  -->
  <main
    ref="workspace"
    :class="[
      'workspace',
      { 'workspace--history-collapsed': shellReady && !historyOpen },
    ]"
    @pointermove.passive="trackPointer"
  >
    <AppChatSidebar
      :open="historyOpen"
      :chats="chats"
      :active-chat-id="activeChatId"
      :search="search"
      :archived="showArchived"
      :user="userLabel"
      :model-label="activeModelLabel"
      :loading="historyLoading"
      @update:open="historyOpen = $event"
      @update:search="search = $event"
      @change-view="toggleArchived"
      @select="selectChat"
      @create="newChat"
      @rename="startRename"
      @archive="archiveChat"
      @delete="askDelete"
      @settings="settingsOpen = true"
      @theme="toggleTheme"
    />

    <section class="chat-shell" aria-label="Conversation workspace">
      <header class="chat-header">
        <div class="chat-header__identity">
          <UTooltip text="Open conversation history">
            <button
              class="header-icon mobile-menu"
              type="button"
              aria-label="Open conversation history"
              @click="historyOpen = true"
            >
              <UIcon name="i-lucide-panel-left" aria-hidden="true" />
            </button>
          </UTooltip>
          <div>
            <h1>{{ activeChat?.name || "New conversation" }}</h1>
            <span v-if="isArchivedChat">Archived conversation</span>
            <span v-else>Private, scripture-grounded guidance</span>
          </div>
        </div>

        <div class="chat-header__actions">
          <span
            :class="[
              'connection-status',
              `connection-status--${connectionTone}`,
            ]"
            role="status"
            :aria-label="connectionStatusText"
          >
            <i aria-hidden="true" />
            <span>{{ connectionLabel }}</span>
            <b aria-hidden="true">·</b>
            <small>{{ activeModelDetail }}</small>
          </span>
          <button
            :class="[
              'library-status',
              `library-status--${scriptureProgressTone}`,
            ]"
            type="button"
            :aria-label="`Scripture library: ${scriptureProgressDetail}`"
            @click="
              settingsSection = 'scriptures';
              settingsOpen = true;
            "
          >
            <UIcon name="i-lucide-library" aria-hidden="true" />
            <span>{{ scriptureProgressLabel }}</span>
          </button>
          <UTooltip v-if="streamDisconnected" text="Reconnect response stream">
            <button
              class="header-icon"
              type="button"
              aria-label="Reconnect response stream"
              @click="connectRun()"
            >
              <UIcon name="i-lucide-refresh-cw" aria-hidden="true" />
            </button>
          </UTooltip>
          <UTooltip text="Settings">
            <button
              class="header-icon desktop-settings"
              type="button"
              aria-label="Open settings"
              @click="settingsOpen = true"
            >
              <UIcon name="i-lucide-settings-2" aria-hidden="true" />
            </button>
          </UTooltip>
        </div>
      </header>

      <div ref="messageViewport" class="message-viewport">
        <span class="sr-only" role="status" aria-live="polite">
          {{ busy ? runLabel : error }}
        </span>
        <div v-if="workspaceLoading" class="conversation-loading">
          <USkeleton class="h-4 w-2/3" />
          <USkeleton class="h-4 w-1/2" />
          <USkeleton class="mt-6 h-4 w-3/4" />
        </div>

        <div
          v-else-if="showArchived && !activeChat"
          class="empty-conversation empty-conversation--utility"
        >
          <span class="empty-mark">
            <UIcon name="i-lucide-archive" aria-hidden="true" />
          </span>
          <h2>No archived conversations</h2>
          <p>Chats you archive will remain available here.</p>
        </div>

        <div v-else-if="isArchivedChat" class="archive-banner">
          <span>
            <UIcon name="i-lucide-archive" aria-hidden="true" />
          </span>
          <div>
            <strong>This conversation is archived</strong>
            <p>Restore it before continuing the conversation.</p>
          </div>
          <button type="button" @click="restoreActiveArchivedChat">
            <UIcon name="i-lucide-archive-restore" aria-hidden="true" />
            Restore
          </button>
          <button
            class="archive-banner__delete"
            type="button"
            @click="activeChat && askDelete(activeChat)"
          >
            <UIcon name="i-lucide-trash-2" aria-hidden="true" />
            Delete
          </button>
        </div>

        <div
          v-if="
            !workspaceLoading &&
            activeChat &&
            !isArchivedChat &&
            !messages.length &&
            !streamingText
          "
          class="empty-conversation"
        >
          <span class="empty-brand-mark" aria-hidden="true">
            <img src="/brand/MokshaAI_dark_cropped.png" alt="" />
          </span>
          <h2>What is weighing on your mind?</h2>
          <p>
            Take your time. Begin wherever the thought feels hardest to hold.
          </p>
          <div class="starter-prompts" aria-label="Conversation starters">
            <button
              v-for="starter in starterPrompts"
              :key="starter"
              type="button"
              @click="useStarterPrompt(starter)"
            >
              <span>{{ starter }}</span>
              <UIcon name="i-lucide-arrow-up-right" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div v-if="messages.length || streamingText" class="message-thread">
          <AppConversationMessage
            v-for="message in messages"
            :key="message.id"
            :message="message"
          />

          <div v-if="busy && !streamingText" class="thinking-row" role="status">
            <span class="thinking-mark" aria-hidden="true">
              <img src="/brand/MokshaAI_dark_cropped.png" alt="" />
            </span>
            <span class="thinking-copy">
              <i />
              <i />
              <i />
              <span>{{ runLabel }}</span>
            </span>
          </div>

          <AppConversationMessage
            v-if="streamingText"
            :message="streamingMessage"
            streaming
          />
        </div>

        <div v-if="error && !workspaceLoading" class="response-error">
          <UIcon name="i-lucide-circle-alert" aria-hidden="true" />
          <span class="response-error__message">{{ error }}</span>
          <button v-if="lastPrompt && !busy" type="button" @click="retryLast">
            Try again
          </button>
          <button type="button" aria-label="Dismiss error" @click="error = ''">
            <UIcon name="i-lucide-x" aria-hidden="true" />
          </button>
        </div>
      </div>

      <footer v-if="activeChat && !isArchivedChat" class="composer-dock">
        <AppChatComposer
          v-model="prompt"
          :busy="busy"
          :error="error"
          :disabled="workspaceLoading || !activeModelReady"
          @submit="send"
          @stop="stopRun"
        />
      </footer>
    </section>

    <AppSettingsDialog
      :open="settingsOpen"
      :user="userLabel"
      :theme="(colorMode.preference as 'system' | 'light' | 'dark') || 'system'"
      :model-profile="modelProfile"
      :fallback-model-profile="fallbackModelProfile"
      :model-options="modelOptions"
      :profiles="profiles"
      :scriptures="scriptures"
      :message="settingsMessage"
      :message-section="settingsMessageSection"
      :saving="settingsSaving"
      :probing-connection-id="probingConnectionId"
      @update:open="settingsOpen = $event"
      @theme="saveThemePreference"
      @model="saveModelPreference"
      @fallback-model="saveFallbackModelPreference"
      @provider="addProviderConnection"
      @probe="probeProviderConnection"
      @remove-connection="removeProviderConnection"
      @section="settingsSection = $event"
      @signout="signOut"
    />

    <UModal
      :open="Boolean(renameChatId)"
      title="Rename conversation"
      description="Choose a short name that will be easy to find later."
      @update:open="!$event && (renameChatId = '')"
    >
      <template #body>
        <form class="compact-dialog" @submit.prevent="saveRename">
          <label>
            <span>Conversation name</span>
            <input v-model="renameName" maxlength="80" required autofocus />
          </label>
          <div>
            <button
              class="secondary-action"
              type="button"
              @click="renameChatId = ''"
            >
              Cancel
            </button>
            <button class="primary-action" type="submit">Save name</button>
          </div>
        </form>
      </template>
    </UModal>

    <UModal
      :open="Boolean(deleteChatId)"
      title="Delete conversation?"
      description="This permanently removes the conversation and its messages."
      @update:open="!$event && (deleteChatId = '')"
    >
      <template #body>
        <div class="compact-dialog">
          <p>This action cannot be undone.</p>
          <div>
            <button
              class="secondary-action"
              type="button"
              @click="deleteChatId = ''"
            >
              Cancel
            </button>
            <button class="danger-action" type="button" @click="confirmDelete">
              Delete conversation
            </button>
          </div>
        </div>
      </template>
    </UModal>
  </main>
</template>

<style scoped>
.workspace {
  --sidebar-width: 15.5rem;
  --header-height: 3.55rem;
  --pointer-x: 50vw;
  --pointer-y: 35vh;

  background: linear-gradient(135deg, var(--moksha-bg), var(--moksha-bg-deep));
  color: var(--moksha-ink);
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  height: 100svh;
  isolation: isolate;
  overflow: hidden;
  position: relative;
}

.dark .workspace {
  background: linear-gradient(135deg, var(--moksha-bg), var(--moksha-bg-deep));
}

.workspace::before {
  background: radial-gradient(
    circle 52px at var(--pointer-x) var(--pointer-y),
    rgb(238 190 117 / 18%),
    rgb(125 171 148 / 5%) 38%,
    transparent 100%
  );
  content: "";
  inset: 0;
  opacity: 0.58;
  pointer-events: none;
  position: fixed;
  transition: opacity 180ms ease;
  z-index: 0;
}

.workspace--history-collapsed {
  grid-template-columns: 0 minmax(0, 1fr);
}

.workspace--history-collapsed :deep(.history) {
  opacity: 0;
  pointer-events: none;
  transform: translateX(-105%);
}

.workspace--history-collapsed .mobile-menu {
  display: inline-flex;
}

.chat-shell {
  display: grid;
  grid-template-rows: var(--header-height) minmax(0, 1fr) auto;
  height: 100svh;
  min-width: 0;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

.chat-header {
  align-items: center;
  backdrop-filter: blur(22px) saturate(1.12);
  background: var(--moksha-header);
  border-bottom: 1px solid var(--moksha-glass-line);
  display: flex;
  justify-content: space-between;
  min-height: var(--header-height);
  padding: 0 0.95rem;
  z-index: 4;
}

.chat-header__identity,
.chat-header__actions,
.chat-header__identity > div {
  min-width: 0;
}

.chat-header__identity,
.chat-header__actions {
  align-items: center;
  display: flex;
  gap: 0.65rem;
}

.chat-header h1 {
  font-size: 0.88rem;
  font-weight: 720;
  margin: 0;
  max-width: min(50vw, 32rem);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-header__identity span {
  color: var(--moksha-muted);
  display: block;
  font-size: 0.66rem;
  margin-top: 0.06rem;
}

.header-icon {
  align-items: center;
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.55rem;
  color: var(--moksha-muted);
  display: inline-flex;
  height: 2rem;
  justify-content: center;
  width: 2rem;
}

.header-icon:hover {
  background: var(--moksha-glass-raised);
  color: var(--moksha-ink);
}

.header-icon svg,
.header-icon .iconify,
.library-status svg,
.library-status .iconify {
  color: currentcolor;
  flex: 0 0 auto;
  height: 1rem;
  stroke-width: 2;
  width: 1rem;
}

.mobile-menu {
  display: none;
}

.connection-status {
  align-items: center;
  color: var(--moksha-muted);
  display: inline-flex;
  font-size: 0.68rem;
  gap: 0.4rem;
  max-width: min(22rem, 38vw);
  min-width: 0;
}

.connection-status i {
  background: var(--moksha-warning);
  border-radius: 50%;
  box-shadow: 0 0 0 3px var(--moksha-accent-soft);
  height: 0.42rem;
  width: 0.42rem;
}

.connection-status--online i {
  background: var(--moksha-success);
  box-shadow: 0 0 0 3px var(--moksha-success-soft);
}

.connection-status--error i {
  background: var(--moksha-error);
  box-shadow: 0 0 0 3px var(--moksha-error-soft);
}

.connection-status span {
  color: var(--moksha-ink);
  font-weight: 680;
}

.connection-status b {
  color: var(--moksha-muted);
  font-weight: 500;
}

.connection-status small {
  color: var(--moksha-muted);
  font-size: inherit;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.library-status {
  align-items: center;
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 999px;
  color: var(--moksha-muted);
  display: inline-flex;
  font-size: 0.68rem;
  font-weight: 680;
  gap: 0.35rem;
  min-height: 1.85rem;
  padding: 0 0.62rem;
  white-space: nowrap;
}

.library-status:hover {
  background: var(--moksha-glass-raised);
  color: var(--moksha-ink);
}

.library-status--running {
  background: var(--moksha-accent-soft);
  border-color: var(--moksha-accent-line);
  color: color-mix(in srgb, var(--moksha-accent-ink) 82%, var(--moksha-ink));
}

.library-status--running svg {
  animation: breathe 1.45s ease-in-out infinite;
}

.message-viewport {
  min-height: 0;
  overflow: auto;
  overscroll-behavior: contain;
  padding: 1.3rem clamp(1rem, 4vw, 3rem) 1.8rem;
  scroll-behavior: smooth;
}

.conversation-loading {
  margin: 4rem auto;
  max-width: 42rem;
}

.empty-conversation {
  align-items: center;
  display: flex;
  flex-direction: column;
  margin: clamp(4rem, 12vh, 7rem) auto 2rem;
  max-width: 37rem;
  text-align: center;
}

.empty-brand-mark {
  background: var(--moksha-guide-mark);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.5rem;
  box-shadow: 0 0.8rem 2rem rgb(16 31 23 / 14%);
  height: 3.2rem;
  overflow: hidden;
  position: relative;
  width: 3.2rem;
}

.empty-brand-mark img {
  height: 5rem;
  left: 50%;
  max-width: none;
  mix-blend-mode: screen;
  position: absolute;
  top: -0.12rem;
  transform: translateX(-50%);
  width: 5rem;
}

.empty-conversation h2 {
  font-size: 1.45rem;
  font-weight: 710;
  line-height: 1.2;
  margin: 1rem 0 0.4rem;
}

.empty-conversation > p {
  color: var(--moksha-muted);
  font-size: 0.82rem;
  line-height: 1.55;
  margin: 0;
}

.starter-prompts {
  display: grid;
  gap: 0.45rem;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-top: 1.35rem;
  width: 100%;
}

.starter-prompts button {
  align-items: end;
  background: var(--moksha-glass);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.5rem;
  color: var(--moksha-ink);
  display: flex;
  font-size: 0.74rem;
  gap: 0.5rem;
  justify-content: space-between;
  line-height: 1.4;
  min-height: 4.1rem;
  padding: 0.65rem;
  text-align: left;
}

.starter-prompts button:hover {
  backdrop-filter: blur(18px);
  background: var(--moksha-glass-raised);
  border-color: var(--moksha-accent-line);
  transform: translateY(-2px);
}

.starter-prompts svg {
  color: var(--moksha-accent);
  flex: 0 0 auto;
}

.empty-conversation--utility .empty-mark {
  align-items: center;
  background: var(--moksha-control);
  border-radius: 0.7rem;
  color: var(--moksha-muted);
  display: flex;
  height: 2.5rem;
  justify-content: center;
  width: 2.5rem;
}

.empty-conversation--utility h2 {
  font-size: 1rem;
}

.message-thread {
  display: grid;
  gap: 1.55rem;
  padding: 0.6rem 0 1rem;
}

.thinking-row {
  display: grid;
  gap: 0.7rem;
  grid-template-columns: 1.8rem minmax(0, 1fr);
  margin: 0 auto;
  max-width: 48rem;
  width: 100%;
}

.thinking-mark {
  background: var(--moksha-guide-mark);
  border-radius: 0.55rem;
  height: 1.8rem;
  overflow: hidden;
  position: relative;
  width: 1.8rem;
}

.thinking-mark img {
  height: 2.8rem;
  left: 50%;
  max-width: none;
  mix-blend-mode: screen;
  position: absolute;
  top: -0.05rem;
  transform: translateX(-50%);
  width: 2.8rem;
}

.thinking-copy {
  align-items: center;
  color: var(--moksha-muted);
  display: flex;
  font-size: 0.7rem;
  gap: 0.28rem;
  min-height: 1.8rem;
}

.thinking-copy > i {
  animation: thinking 1.15s ease-in-out infinite;
  background: var(--moksha-accent);
  border-radius: 50%;
  height: 0.34rem;
  width: 0.34rem;
}

.thinking-copy > i:nth-child(2) {
  animation-delay: 120ms;
}

.thinking-copy > i:nth-child(3) {
  animation-delay: 240ms;
}

.thinking-copy > span {
  margin-left: 0.35rem;
}

.archive-banner,
.response-error {
  align-items: center;
  backdrop-filter: blur(18px);
  background: var(--moksha-glass);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.5rem;
  display: flex;
  gap: 0.65rem;
  margin: 0 auto;
  max-width: 48rem;
  padding: 0.65rem 0.75rem;
}

.archive-banner > span {
  align-items: center;
  background: var(--moksha-control);
  border-radius: 0.55rem;
  color: var(--moksha-muted);
  display: flex;
  height: 2rem;
  justify-content: center;
  width: 2rem;
}

.archive-banner > div {
  flex: 1;
  min-width: 0;
}

.archive-banner strong {
  font-size: 0.78rem;
}

.archive-banner p {
  color: var(--moksha-muted);
  font-size: 0.7rem;
  margin: 0.1rem 0 0;
}

.archive-banner button,
.response-error button {
  align-items: center;
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.55rem;
  color: var(--moksha-ink);
  display: inline-flex;
  font-size: 0.7rem;
  font-weight: 650;
  gap: 0.35rem;
  min-height: 2rem;
  padding: 0 0.6rem;
}

.archive-banner__delete {
  color: var(--moksha-error) !important;
}

.response-error {
  background: var(--moksha-error-soft);
  border-color: var(--moksha-error-line);
  color: var(--moksha-error);
  font-size: 0.72rem;
  margin-top: 1rem;
}

.response-error__message {
  flex: 1;
  min-width: 0;
}

.response-error button:last-child {
  border: 0;
  min-width: 2rem;
  padding: 0;
}

.composer-dock {
  background: linear-gradient(
    to top,
    var(--moksha-bg) 18%,
    color-mix(in srgb, var(--moksha-bg) 78%, transparent) 68%,
    transparent
  );
  padding: 0.48rem clamp(1rem, 4vw, 3rem)
    max(0.48rem, env(safe-area-inset-bottom));
  pointer-events: none;
  z-index: 5;
}

.composer-dock > * {
  pointer-events: auto;
}

.compact-dialog {
  display: grid;
  gap: 1rem;
}

.compact-dialog label {
  display: grid;
  gap: 0.35rem;
}

.compact-dialog label span,
.compact-dialog p {
  color: var(--moksha-muted);
  font-size: 0.76rem;
  margin: 0;
}

.compact-dialog input {
  background: var(--moksha-control);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.6rem;
  color: var(--moksha-ink);
  min-height: 2.55rem;
  padding: 0 0.7rem;
}

.compact-dialog > div {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.primary-action,
.secondary-action,
.danger-action {
  border-radius: 0.55rem;
  font-size: 0.75rem;
  font-weight: 670;
  min-height: 2.35rem;
  padding: 0 0.8rem;
}

.primary-action {
  background: var(--moksha-primary);
  border: 0;
  color: var(--moksha-primary-ink);
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

@keyframes breathe {
  50% {
    opacity: 0.42;
    transform: scale(0.82);
  }
}

@keyframes thinking {
  0%,
  60%,
  100% {
    opacity: 0.38;
    transform: translateY(0);
  }

  30% {
    opacity: 1;
    transform: translateY(-0.32rem);
  }
}

@media (max-width: 860px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .mobile-menu {
    display: inline-flex;
  }

  .desktop-settings {
    display: none;
  }

  .message-viewport {
    padding: 1rem 0.8rem 1.35rem;
  }

  .composer-dock {
    padding-inline: 0.7rem;
  }
}

@media (max-width: 600px) {
  .workspace {
    --header-height: 3.35rem;
  }

  .chat-header {
    padding: 0 0.65rem;
  }

  .chat-header h1 {
    font-size: 0.8rem;
    max-width: 58vw;
  }

  .chat-header__identity span {
    font-size: 0.6rem;
  }

  .connection-status {
    font-size: 0;
    max-width: none;
  }

  .connection-status span,
  .connection-status b,
  .connection-status small,
  .library-status span {
    display: none;
  }

  .library-status .iconify {
    display: inline-block;
  }

  .library-status {
    border-radius: 0.55rem;
    min-height: 2rem;
    padding: 0;
    width: 2rem;
  }

  .empty-conversation {
    margin-top: 3.2rem;
    padding: 0 0.4rem;
  }

  .empty-conversation h2 {
    font-size: 1.2rem;
  }

  .starter-prompts {
    grid-template-columns: 1fr;
    max-width: 22rem;
  }

  .starter-prompts button {
    align-items: center;
    min-height: 3rem;
  }

  .archive-banner {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .archive-banner > div {
    flex-basis: calc(100% - 3rem);
  }

  .archive-banner button {
    flex: 1;
  }
}

@media (hover: none), (pointer: coarse) {
  .workspace::before {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workspace::before {
    display: none;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .chat-header,
  .archive-banner,
  .response-error {
    backdrop-filter: none;
  }
}
</style>
