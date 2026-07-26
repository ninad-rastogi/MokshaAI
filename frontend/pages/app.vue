<script setup lang="ts">
import type {
  ChatSummary,
  Citation,
  Message,
  ModelProfile,
  Scripture,
} from "~/types/api";

definePageMeta({ ssr: false });

const api = useApi();
const stream = useRunStream();
const colorMode = useColorMode();

const workspace = ref<HTMLElement | null>(null);
const user = ref("");
const chats = ref<ChatSummary[]>([]);
const messages = ref<Message[]>([]);
const scriptures = ref<Scripture[]>([]);
const profiles = ref<ModelProfile[]>([]);
const activeChatId = ref("");
const prompt = ref("");
const activeRunId = ref("");
const streamingText = ref("");
const streamingSources = ref<Citation[]>([]);
const statusText = ref("Ready");
const modelProfile = ref("");
const busy = ref(false);
const error = ref("");
const search = ref("");
const showArchived = ref(false);
const openMenuId = ref("");
const settingsOpen = ref(false);
const historyOpen = ref(false);
const renameChatId = ref("");
const renameName = ref("");
const deleteChatId = ref("");

const themeOptions = [
  { label: "System", value: "system" },
  { label: "Light", value: "light" },
  { label: "Dark", value: "dark" },
] as const;

const fallbackModelOptions = [
  { label: "Moksha Qwen3 local", value: "moksha-qwen3:4b-instruct-q3km" },
];

const modelOptions = computed(() => {
  const remote = profiles.value.map((profile) => ({
    label: profile.is_admin_default ? `${profile.name} default` : profile.name,
    value: profile.id,
  }));
  return [
    { label: "Admin default", value: "" },
    ...remote,
    ...fallbackModelOptions,
  ];
});

const activeChat = computed(
  () => chats.value.find((chat) => chat.id === activeChatId.value) || null,
);

const filteredChats = computed(() => {
  const needle = search.value.trim().toLowerCase();
  if (!needle) return chats.value;
  return chats.value.filter((chat) => chat.name.toLowerCase().includes(needle));
});

const activeModelLabel = computed(
  () =>
    modelOptions.value.find((option) => option.value === modelProfile.value)
      ?.label || "Admin default",
);

const indexedCount = computed(
  () => scriptures.value.filter((scripture) => scripture.is_indexed).length,
);

const statusLabel = computed(() => statusText.value || "Ready");

const statusTone = computed(() => {
  const state = statusLabel.value.toLowerCase();
  if (["running", "queued", "connecting"].includes(state)) return "active";
  if (["failed", "error"].some((item) => state.includes(item))) return "danger";
  if (state === "cancelled") return "muted";
  return "ready";
});

function trackPointer(event: PointerEvent) {
  const bounds = workspace.value?.getBoundingClientRect();
  if (!bounds) return;
  workspace.value?.style.setProperty(
    "--pointer-x",
    `${event.clientX - bounds.left}px`,
  );
  workspace.value?.style.setProperty(
    "--pointer-y",
    `${event.clientY - bounds.top}px`,
  );
}

onMounted(async () => {
  try {
    const profile = await api.me();
    user.value = profile.spiritual_name || profile.email;
  } catch {
    await navigateTo("/");
    return;
  }

  const results = await Promise.allSettled([
    loadChats(),
    loadScriptures(),
    loadProfiles(),
  ]);
  if (results.some((result) => result.status === "rejected")) {
    error.value = "Some workspace data could not load. Refresh or retry.";
  }

  try {
    if (!activeChatId.value) await newChat();
    else await loadMessages();
  } catch {
    error.value = "Could not load this conversation. Refresh or retry.";
  }
});

onBeforeUnmount(() => stream.close());

async function loadProfiles() {
  const page = await api.modelProfiles();
  profiles.value = page.results;
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

async function selectChat(chatId: string) {
  activeChatId.value = chatId;
  openMenuId.value = "";
  historyOpen.value = false;
  streamingText.value = "";
  streamingSources.value = [];
  await loadMessages();
}

async function newChat() {
  showArchived.value = false;
  historyOpen.value = false;
  const chat = await api.createChat();
  chats.value = [chat, ...chats.value];
  await selectChat(chat.id);
}

async function toggleArchived(nextValue: boolean) {
  showArchived.value = nextValue;
  search.value = "";
  await loadChats();
  await loadMessages();
}

function startRename(chat: ChatSummary) {
  renameChatId.value = chat.id;
  renameName.value = chat.name;
  openMenuId.value = "";
}

async function saveRename() {
  const nextName = renameName.value.trim();
  if (!renameChatId.value || !nextName) return;
  const updated = await api.renameChat(renameChatId.value, nextName);
  chats.value = chats.value.map((chat) =>
    chat.id === updated.id ? updated : chat,
  );
  renameChatId.value = "";
  renameName.value = "";
}

async function archiveChat(chat: ChatSummary) {
  openMenuId.value = "";
  const updated = chat.is_archived
    ? await api.unarchiveChat(chat.id)
    : await api.archiveChat(chat.id);
  chats.value = chats.value.filter((item) => item.id !== updated.id);
  if (activeChatId.value === updated.id) {
    activeChatId.value = chats.value[0]?.id || "";
    await loadMessages();
  }
}

function askDelete(chatId: string) {
  deleteChatId.value = chatId;
  openMenuId.value = "";
}

function openSettings() {
  openMenuId.value = "";
  historyOpen.value = false;
  settingsOpen.value = true;
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
    error.value =
      deleteError instanceof Error
        ? "Cancel the active generation before deleting this chat."
        : "Could not delete this chat.";
  }
}

async function send() {
  const message = prompt.value.trim();
  if (!message || !activeChatId.value || busy.value) return;
  prompt.value = "";
  busy.value = true;
  error.value = "";
  streamingText.value = "";
  streamingSources.value = [];
  statusText.value = "Queued";
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
    error.value =
      runError instanceof Error
        ? runError.message
        : "Could not start generation.";
  }
}

async function handleComposerKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  await send();
}

function connectRun(runId = activeRunId.value) {
  if (!runId) return;
  statusText.value = "Connecting";
  stream.connect(runId, (event) => {
    if (event.type === "state") statusText.value = event.state;
    if (event.type === "delta") streamingText.value += event.text;
    if (event.type === "citation") streamingSources.value.push(event.citation);
    if (event.type === "error") {
      error.value = event.message;
      statusText.value = event.code;
    }
    if (event.type === "done") {
      statusText.value = event.state;
      busy.value = false;
      if (streamingText.value) {
        messages.value.push({
          id: Date.now() + 1,
          role: "assistant",
          content: streamingText.value,
          mode: "STREAM",
          sources: streamingSources.value,
          created_at: new Date().toISOString(),
        });
      }
      activeRunId.value = "";
      streamingText.value = "";
      streamingSources.value = [];
      void loadChats();
    }
  });
}

async function stopRun() {
  if (!activeRunId.value) return;
  await api.cancelRun(activeRunId.value);
  stream.close();
  busy.value = false;
  statusText.value = "cancelled";
}

async function retryLast() {
  const lastUser = [...messages.value]
    .reverse()
    .find((message) => message.role === "user");
  if (!lastUser) return;
  prompt.value = lastUser.content;
  await send();
}

async function signOut() {
  await api.sessionLogout();
  await navigateTo("/");
}
</script>

<template>
  <main ref="workspace" class="workspace" @pointermove="trackPointer">
    <button
      v-if="historyOpen"
      class="mobile-scrim"
      type="button"
      aria-label="Close chat history"
      @click="historyOpen = false"
    />
    <aside
      :class="['history', { 'history--open': historyOpen }]"
      aria-label="Chat history"
    >
      <div class="history__top">
        <MokshaBrand />
        <div class="history__actions">
          <button
            class="icon-button mobile-only"
            type="button"
            aria-label="Close chat history"
            title="Close chat history"
            @click="historyOpen = false"
          >
            <UIcon name="i-lucide-x" aria-hidden="true" />
          </button>
          <button
            class="icon-button"
            type="button"
            aria-label="New chat"
            title="New chat"
            @click="newChat"
          >
            <UIcon name="i-lucide-plus" aria-hidden="true" />
          </button>
        </div>
      </div>

      <label class="search">
        <span>Search chats</span>
        <input
          v-model="search"
          placeholder="Search conversations"
          type="search"
        />
      </label>

      <div class="history-tabs" role="tablist" aria-label="Conversation view">
        <button
          type="button"
          :aria-selected="!showArchived"
          @click="toggleArchived(false)"
        >
          Recent
        </button>
        <button
          type="button"
          :aria-selected="showArchived"
          @click="toggleArchived(true)"
        >
          Archived
        </button>
      </div>

      <nav class="chat-list">
        <article
          v-for="chat in filteredChats"
          :key="chat.id"
          class="chat-card"
          :aria-current="chat.id === activeChatId ? 'page' : undefined"
        >
          <button
            class="chat-card__main"
            type="button"
            @click="selectChat(chat.id)"
          >
            <span>{{ chat.name }}</span>
            <small>{{ chat.message_count }} messages</small>
          </button>
          <button
            class="chat-card__menu"
            type="button"
            aria-label="Chat actions"
            title="Chat actions"
            :aria-expanded="openMenuId === chat.id"
            @click="openMenuId = openMenuId === chat.id ? '' : chat.id"
          >
            <UIcon name="i-lucide-ellipsis" aria-hidden="true" />
          </button>
          <div v-if="openMenuId === chat.id" class="chat-menu" role="menu">
            <button type="button" role="menuitem" @click="startRename(chat)">
              <UIcon name="i-lucide-pencil" aria-hidden="true" />
              Rename
            </button>
            <button type="button" role="menuitem" @click="archiveChat(chat)">
              <UIcon
                :name="
                  chat.is_archived
                    ? 'i-lucide-archive-restore'
                    : 'i-lucide-archive'
                "
                aria-hidden="true"
              />
              {{ chat.is_archived ? "Restore" : "Archive" }}
            </button>
            <button
              class="danger"
              type="button"
              role="menuitem"
              @click="askDelete(chat.id)"
            >
              <UIcon name="i-lucide-trash-2" aria-hidden="true" />
              Delete
            </button>
          </div>
        </article>
        <p v-if="!filteredChats.length" class="history-empty">
          {{ showArchived ? "No archived chats." : "No matching chats." }}
        </p>
      </nav>

      <footer class="history-footer">
        <button class="account-button" type="button" @click="openSettings">
          <span>
            <strong>{{ user || "Moksha AI" }}</strong>
            <small>{{ activeModelLabel }}</small>
          </span>
          <UIcon name="i-lucide-settings" aria-hidden="true" />
        </button>
      </footer>
    </aside>

    <section class="chat" aria-label="Chat workspace">
      <header class="chat__header">
        <div class="chat__title-row">
          <button
            class="icon-button mobile-only"
            type="button"
            aria-label="Open chat history"
            title="Open chat history"
            @click="historyOpen = true"
          >
            <UIcon name="i-lucide-panel-left-open" aria-hidden="true" />
          </button>
          <div class="chat__identity">
            <p>{{ activeChat?.name || "New conversation" }}</p>
            <span>Grounded guidance workspace</span>
          </div>
        </div>
        <div class="run-actions">
          <span :class="['status-pill', `status-pill--${statusTone}`]">
            {{ statusLabel }}
          </span>
          <button
            class="ghost-button"
            type="button"
            :disabled="!activeRunId"
            @click="connectRun()"
          >
            <UIcon name="i-lucide-wifi" aria-hidden="true" />
            Reconnect
          </button>
          <button
            class="ghost-button ghost-button--danger"
            type="button"
            :disabled="!busy"
            @click="stopRun"
          >
            <UIcon name="i-lucide-square" aria-hidden="true" />
            Stop
          </button>
        </div>
      </header>

      <div class="messages" aria-live="polite">
        <div v-if="!messages.length && !streamingText" class="empty-state">
          <span class="empty-state__eyebrow">Scripture-grounded counsel</span>
          <p>Bring the question you cannot carry alone.</p>
          <span>
            Share the situation. Moksha AI listens, searches your scripture
            library, and answers with citations when evidence is found.
          </span>
        </div>

        <article
          v-for="message in messages"
          :key="message.id"
          :class="['message', `message--${message.role}`]"
        >
          <MarkdownBody :content="message.content" />
          <CitationList :citations="message.sources" />
        </article>

        <article v-if="streamingText" class="message message--assistant">
          <MarkdownBody :content="streamingText" />
          <CitationList :citations="streamingSources" />
        </article>
      </div>

      <form class="composer" @submit.prevent="send">
        <div class="composer-shell">
          <label for="prompt">Ask Moksha AI</label>
          <textarea
            id="prompt"
            v-model="prompt"
            rows="2"
            :disabled="busy"
            placeholder="Share what is weighing on your mind..."
            @keydown="handleComposerKeydown"
          />
          <div class="composer__bar">
            <p v-if="error" role="alert">{{ error }}</p>
            <span v-else>Enter sends. Shift + Enter adds a new line.</span>
            <button
              class="ghost-button"
              type="button"
              :disabled="busy || !messages.length"
              @click="retryLast"
            >
              <UIcon name="i-lucide-rotate-ccw" aria-hidden="true" />
              Retry
            </button>
            <button
              class="primary-button"
              type="submit"
              :disabled="busy || !prompt.trim()"
            >
              <UIcon name="i-lucide-send" aria-hidden="true" />
              Send
            </button>
          </div>
        </div>
      </form>
    </section>

    <Teleport to="body">
      <div
        v-if="settingsOpen"
        class="modal-backdrop"
        role="presentation"
        @click.self="settingsOpen = false"
      >
        <section class="settings-modal" role="dialog" aria-modal="true">
          <header>
            <div>
              <p>Settings</p>
              <span>{{ user }}</span>
            </div>
            <button
              class="icon-button"
              type="button"
              aria-label="Close settings"
              title="Close settings"
              @click="settingsOpen = false"
            >
              <UIcon name="i-lucide-x" aria-hidden="true" />
            </button>
          </header>

          <label class="field">
            <span>Theme</span>
            <div class="segmented" role="group" aria-label="Theme">
              <button
                v-for="option in themeOptions"
                :key="option.value"
                type="button"
                :aria-pressed="colorMode.preference === option.value"
                @click="colorMode.preference = option.value"
              >
                {{ option.label }}
              </button>
            </div>
          </label>

          <label class="field" for="model-profile">
            <span>Model</span>
            <select id="model-profile" v-model="modelProfile">
              <option
                v-for="option in modelOptions"
                :key="option.value"
                :value="option.value"
              >
                {{ option.label }}
              </option>
            </select>
          </label>

          <section
            class="scripture-panel"
            aria-label="Scripture indexing status"
          >
            <div class="panel__title">
              <h2>Scriptures</h2>
              <span>{{ indexedCount }} / {{ scriptures.length }}</span>
            </div>
            <ul class="scripture-list">
              <li v-for="scripture in scriptures" :key="scripture.id">
                <span>{{ scripture.name }}</span>
                <strong>{{
                  scripture.is_indexed ? "Indexed" : "Pending"
                }}</strong>
              </li>
            </ul>
          </section>

          <button class="ghost-button signout" type="button" @click="signOut">
            <UIcon name="i-lucide-log-out" aria-hidden="true" />
            Sign out
          </button>
        </section>
      </div>

      <div
        v-if="renameChatId"
        class="modal-backdrop"
        role="presentation"
        @click.self="renameChatId = ''"
      >
        <form
          class="small-modal"
          role="dialog"
          aria-modal="true"
          @submit.prevent="saveRename"
        >
          <h2>Rename chat</h2>
          <input v-model="renameName" maxlength="50" required />
          <div>
            <button
              class="ghost-button"
              type="button"
              @click="renameChatId = ''"
            >
              <UIcon name="i-lucide-x" aria-hidden="true" />
              Cancel
            </button>
            <button class="primary-button" type="submit">
              <UIcon name="i-lucide-check" aria-hidden="true" />
              Save
            </button>
          </div>
        </form>
      </div>

      <div
        v-if="deleteChatId"
        class="modal-backdrop"
        role="presentation"
        @click.self="deleteChatId = ''"
      >
        <section class="small-modal" role="dialog" aria-modal="true">
          <h2>Delete chat?</h2>
          <p>This removes the conversation and its messages.</p>
          <div>
            <button
              class="ghost-button"
              type="button"
              @click="deleteChatId = ''"
            >
              <UIcon name="i-lucide-x" aria-hidden="true" />
              Cancel
            </button>
            <button class="danger-button" type="button" @click="confirmDelete">
              <UIcon name="i-lucide-trash-2" aria-hidden="true" />
              Delete
            </button>
          </div>
        </section>
      </div>
    </Teleport>
  </main>
</template>

<style scoped>
.workspace {
  --sidebar-width: clamp(16.5rem, 18vw, 20rem);
  --header-height: 4rem;
  --composer-height: 8.75rem;
  --chrome: rgb(255 250 241 / 72%);
  --chrome-strong: rgb(255 250 241 / 88%);
  --hairline: rgb(119 82 44 / 16%);
  --soft-ring: rgb(220 164 84 / 18%);
  --glow-x: var(--pointer-x, 62vw);
  --glow-y: var(--pointer-y, 30vh);
  background:
    radial-gradient(
      circle at var(--glow-x) var(--glow-y),
      rgb(218 157 82 / 18%),
      transparent 17rem
    ),
    radial-gradient(circle at 84% 8%, rgb(69 116 88 / 16%), transparent 21rem),
    linear-gradient(135deg, #fbf4e7 0%, #f4eadb 44%, #edf1e7 100%);
  color: var(--moksha-ink);
  display: grid;
  grid-template-columns: var(--sidebar-width) minmax(0, 1fr);
  height: 100svh;
  overflow: hidden;
  position: relative;
}

.dark .workspace {
  --chrome: rgb(24 22 18 / 72%);
  --chrome-strong: rgb(30 27 22 / 88%);
  --hairline: rgb(229 181 112 / 16%);
  --soft-ring: rgb(229 181 112 / 12%);
  background:
    radial-gradient(
      circle at var(--glow-x) var(--glow-y),
      rgb(216 151 82 / 18%),
      transparent 17rem
    ),
    radial-gradient(
      circle at 82% 10%,
      rgb(86 144 108 / 16%),
      transparent 22rem
    ),
    linear-gradient(135deg, #11120f 0%, #171410 46%, #111812 100%);
}

.workspace::before,
.workspace::after {
  content: "";
  pointer-events: none;
  position: absolute;
  z-index: 0;
}

.workspace::before {
  background:
    linear-gradient(90deg, var(--soft-ring) 1px, transparent 1px),
    linear-gradient(var(--soft-ring) 1px, transparent 1px);
  background-size: 4rem 4rem;
  inset: 0;
  mask-image: radial-gradient(circle at 76% 18%, black, transparent 48%);
  opacity: 0.28;
}

.workspace::after {
  aspect-ratio: 1;
  background: conic-gradient(
    from 25deg,
    transparent,
    rgb(185 125 57 / 18%),
    transparent 34%,
    rgb(65 107 83 / 14%),
    transparent 70%
  );
  border: 1px solid rgb(181 128 62 / 10%);
  border-radius: 50%;
  filter: blur(0.2px);
  opacity: 0.72;
  right: min(8vw, 7rem);
  top: 7.5rem;
  transform: rotate(18deg);
  width: min(28rem, 35vw);
}

.history,
.chat,
.mobile-scrim,
.modal-backdrop {
  position: relative;
  z-index: 1;
}

.history {
  backdrop-filter: blur(26px) saturate(1.25);
  background: color-mix(in srgb, var(--chrome) 92%, transparent);
  border-right: 1px solid var(--hairline);
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr) auto;
  height: 100svh;
  min-width: 0;
  overflow: hidden;
  padding: 1rem 0.9rem;
}

.history__top,
.history__actions,
.chat__header,
.chat__title-row,
.run-actions,
.composer__bar,
.panel__title,
.settings-modal header,
.small-modal div {
  align-items: center;
  display: flex;
  gap: 0.6rem;
}

.history__top,
.chat__header,
.composer__bar,
.panel__title,
.settings-modal header,
.small-modal div {
  justify-content: space-between;
}

.mobile-only {
  display: none;
}

button,
input,
select,
textarea {
  background: var(--chrome-strong);
  border: 1px solid var(--hairline);
  border-radius: 0.8rem;
  color: var(--moksha-ink);
  font: inherit;
}

button,
select {
  align-items: center;
  display: inline-flex;
  font-size: 0.92rem;
  font-weight: 650;
  gap: 0.42rem;
  justify-content: center;
  min-height: 2.25rem;
  padding: 0 0.75rem;
}

button {
  cursor: pointer;
  transition:
    background 160ms ease,
    border-color 160ms ease,
    box-shadow 160ms ease,
    transform 120ms ease;
}

button:hover:not(:disabled) {
  border-color: color-mix(in srgb, var(--moksha-accent) 42%, var(--hairline));
  box-shadow: 0 0.65rem 1.8rem rgb(94 64 30 / 10%);
  transform: translateY(-1px);
}

button:active:not(:disabled) {
  transform: translateY(0) scale(0.98);
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.44;
}

.icon-button {
  border-radius: 999px;
  height: 2.35rem;
  min-width: 2.35rem;
  padding: 0;
  width: 2.35rem;
}

.icon-button :deep(svg),
button :deep(svg) {
  flex: 0 0 auto;
  height: 1rem;
  width: 1rem;
}

.ghost-button {
  background: color-mix(in srgb, var(--chrome-strong) 62%, transparent);
}

.ghost-button--danger,
.danger {
  color: var(--moksha-danger);
}

.danger-button,
.primary-button {
  border-color: transparent;
  color: var(--moksha-bg);
}

.primary-button {
  background: linear-gradient(135deg, var(--moksha-accent-strong), #b87538);
  box-shadow: 0 0.9rem 1.9rem rgb(140 82 34 / 22%);
}

.danger-button {
  background: var(--moksha-danger);
}

.search {
  display: grid;
  gap: 0.4rem;
  margin-top: 1rem;
}

.search span,
.field > span,
.settings-modal header span,
small,
.chat__identity span,
.composer__bar span,
.panel__title span,
.empty-state > span,
.account-button small,
.history-empty {
  color: var(--moksha-muted);
}

.search span,
.field > span {
  font-size: 0.75rem;
  font-weight: 750;
  text-transform: uppercase;
}

.search input {
  font-size: 0.92rem;
  min-height: 2.45rem;
  padding: 0 0.8rem;
}

.history-tabs,
.segmented {
  background: color-mix(in srgb, var(--moksha-bg) 58%, transparent);
  border: 1px solid var(--hairline);
  border-radius: 0.9rem;
  display: grid;
  gap: 0.25rem;
  grid-template-columns: repeat(2, 1fr);
  margin-top: 0.75rem;
  padding: 0.25rem;
}

.segmented {
  grid-template-columns: repeat(3, 1fr);
  margin-top: 0;
}

.history-tabs button,
.segmented button {
  background: transparent;
  border-color: transparent;
  min-height: 2rem;
}

.history-tabs button[aria-selected="true"],
.segmented button[aria-pressed="true"] {
  background: var(--chrome-strong);
  border-color: var(--hairline);
  box-shadow: 0 0.45rem 1.1rem rgb(90 59 28 / 8%);
}

.chat-list {
  align-content: start;
  display: grid;
  gap: 0.55rem;
  margin-top: 0.75rem;
  min-height: 0;
  overflow: auto;
  padding-right: 0.15rem;
}

.chat-card {
  border: 1px solid transparent;
  border-radius: 0.9rem;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  position: relative;
}

.chat-card[aria-current="page"] {
  background: linear-gradient(
    135deg,
    color-mix(in srgb, var(--moksha-accent) 13%, transparent),
    color-mix(in srgb, var(--moksha-leaf) 8%, transparent)
  );
  border-color: color-mix(in srgb, var(--moksha-accent) 55%, transparent);
}

.chat-card__main {
  align-items: start;
  background: transparent;
  border: 0;
  display: grid;
  height: auto;
  justify-items: start;
  line-height: 1.25;
  min-height: 3.65rem;
  min-width: 0;
  padding: 0.72rem;
  text-align: left;
}

.chat-card__main span,
.chat__identity p,
.settings-modal header p,
.account-button strong {
  font-weight: 760;
}

.chat-card__main span,
.account-button strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.chat-card__menu {
  align-self: center;
  background: transparent;
  border-color: transparent;
  height: 2rem;
  min-width: 2rem;
  padding: 0;
  width: 2rem;
}

.chat-menu {
  backdrop-filter: blur(22px) saturate(1.2);
  background: var(--chrome-strong);
  border: 1px solid var(--hairline);
  border-radius: 0.8rem;
  box-shadow: 0 1rem 2.6rem rgb(48 32 16 / 18%);
  display: grid;
  min-width: 9rem;
  padding: 0.35rem;
  position: absolute;
  right: 0.45rem;
  top: 2.9rem;
  z-index: 5;
}

.chat-menu button {
  background: transparent;
  border-color: transparent;
  justify-content: start;
  text-align: left;
}

.history-empty {
  font-size: 0.92rem;
  margin: 0.8rem 0;
}

.history-footer {
  border-top: 1px solid var(--hairline);
  margin-top: 0.75rem;
  padding-top: 0.75rem;
}

.account-button {
  background: color-mix(in srgb, var(--chrome-strong) 76%, transparent);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  height: auto;
  min-height: 3.2rem;
  padding: 0.55rem 0.65rem;
  text-align: left;
  width: 100%;
}

.account-button span {
  display: grid;
  min-width: 0;
}

.chat {
  display: grid;
  grid-template-rows: var(--header-height) minmax(0, 1fr) auto;
  height: 100svh;
  min-width: 0;
  overflow: hidden;
}

.chat__header {
  backdrop-filter: blur(26px) saturate(1.25);
  background: color-mix(in srgb, var(--chrome) 88%, transparent);
  border-bottom: 1px solid var(--hairline);
  min-height: var(--header-height);
  padding: 0 1.35rem;
  z-index: 2;
}

.chat__title-row,
.chat__identity {
  min-width: 0;
}

.chat__identity p,
h2 {
  font-size: 0.98rem;
  margin: 0;
}

.chat__identity p,
.chat__identity span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat__identity span {
  font-size: 0.82rem;
}

.run-actions {
  justify-content: flex-end;
}

.status-pill {
  background: color-mix(in srgb, var(--chrome-strong) 70%, transparent);
  border: 1px solid var(--hairline);
  border-radius: 999px;
  color: var(--moksha-muted);
  font-size: 0.78rem;
  font-weight: 750;
  padding: 0.28rem 0.65rem;
  text-transform: capitalize;
  white-space: nowrap;
}

.status-pill--active {
  border-color: var(--moksha-focus);
  color: var(--moksha-focus);
}

.status-pill--danger {
  border-color: var(--moksha-danger);
  color: var(--moksha-danger);
}

.status-pill--ready {
  border-color: var(--moksha-leaf);
  color: var(--moksha-leaf);
}

.messages {
  align-content: start;
  display: grid;
  gap: 0.9rem;
  grid-template-columns: minmax(0, min(58rem, 100%));
  justify-content: center;
  min-height: 0;
  overflow: auto;
  padding: 1.25rem clamp(1rem, 4vw, 3.5rem) 1rem;
  scroll-behavior: smooth;
}

.empty-state {
  align-self: center;
  grid-column: 1;
  justify-self: center;
  max-width: 36rem;
  padding-bottom: 4vh;
  text-align: center;
}

.empty-state__eyebrow {
  color: var(--moksha-accent);
  display: inline-block;
  font-size: 0.76rem;
  font-weight: 800;
  margin-bottom: 0.75rem;
  text-transform: uppercase;
}

.empty-state p {
  font-size: clamp(1.85rem, 2.9vw, 3rem);
  font-weight: 780;
  line-height: 1.08;
  margin: 0 0 0.8rem;
}

.empty-state > span:last-child {
  display: block;
  font-size: 1rem;
  line-height: 1.55;
  margin: 0 auto;
  max-width: 31rem;
}

.message {
  backdrop-filter: blur(20px) saturate(1.15);
  border: 1px solid var(--hairline);
  border-radius: 1.05rem;
  box-shadow: 0 0.9rem 2.7rem rgb(54 34 14 / 10%);
  font-size: 0.98rem;
  line-height: 1.62;
  grid-column: 1;
  max-width: min(42rem, 82%);
  padding: 0.82rem 0.95rem;
}

.message--user {
  background: linear-gradient(135deg, #eebf81, #d99b5c);
  color: #201308;
  justify-self: end;
}

.message--assistant {
  background: color-mix(in srgb, var(--chrome-strong) 84%, transparent);
  justify-self: start;
}

.composer {
  backdrop-filter: blur(26px) saturate(1.25);
  background: linear-gradient(
    to top,
    color-mix(in srgb, var(--chrome) 96%, transparent),
    color-mix(in srgb, var(--chrome) 72%, transparent)
  );
  border-top: 1px solid var(--hairline);
  padding: 0.75rem clamp(1rem, 5vw, 4.5rem) 0.95rem;
  z-index: 2;
}

.composer-shell {
  background: color-mix(in srgb, var(--chrome-strong) 80%, transparent);
  border: 1px solid var(--hairline);
  border-radius: 1.1rem;
  box-shadow: 0 1rem 3rem rgb(64 38 15 / 12%);
  display: grid;
  gap: 0.28rem;
  margin: 0 auto;
  max-width: 58rem;
  padding: 0.62rem;
}

.composer label {
  color: var(--moksha-muted);
  font-size: 0.76rem;
  font-weight: 800;
  text-transform: uppercase;
}

textarea,
.small-modal input,
.field select {
  line-height: 1.45;
  width: 100%;
}

textarea {
  background: transparent;
  border-color: transparent;
  font-size: 1rem;
  max-height: 8rem;
  min-height: 2.75rem;
  padding: 0.2rem 0;
  resize: none;
}

textarea:focus {
  outline: none;
}

.composer__bar {
  gap: 0.55rem;
}

.composer__bar p {
  color: var(--moksha-danger);
  margin: 0;
}

.composer__bar span,
.composer__bar p {
  font-size: 0.82rem;
  min-width: 0;
}

.modal-backdrop {
  align-items: center;
  backdrop-filter: blur(8px);
  background: rgb(18 13 8 / 46%);
  display: grid;
  inset: 0;
  justify-items: center;
  padding: 1rem;
  position: fixed;
  z-index: 50;
}

.settings-modal,
.small-modal {
  backdrop-filter: blur(30px) saturate(1.3);
  background: var(--chrome-strong);
  border: 1px solid var(--hairline);
  border-radius: 1.2rem;
  box-shadow: 0 1.8rem 5rem rgb(25 15 7 / 28%);
  display: grid;
  gap: 1rem;
  max-height: min(44rem, 92svh);
  overflow: auto;
  padding: 1.1rem;
  width: min(29rem, 100%);
}

.field,
.scripture-panel {
  display: grid;
  gap: 0.5rem;
}

.field select,
.small-modal input {
  min-height: 2.6rem;
  padding: 0 0.8rem;
}

.scripture-panel {
  border-top: 1px solid var(--hairline);
  padding-top: 1rem;
}

.scripture-list {
  display: grid;
  gap: 0.5rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.scripture-list li {
  align-items: center;
  display: flex;
  font-size: 0.92rem;
  justify-content: space-between;
}

.scripture-list strong {
  color: var(--moksha-leaf);
  font-size: 0.82rem;
}

.signout {
  justify-content: center;
}

.small-modal p {
  color: var(--moksha-muted);
  margin: 0;
}

.mobile-scrim {
  display: none;
}

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .mobile-only {
    display: inline-flex;
  }

  .mobile-scrim {
    background: rgb(18 13 8 / 42%);
    border: 0;
    border-radius: 0;
    display: block;
    inset: 0;
    min-height: 0;
    padding: 0;
    position: fixed;
    z-index: 20;
  }

  .history {
    border-right: 1px solid var(--hairline);
    box-shadow: 1rem 0 3rem rgb(25 15 7 / 22%);
    left: 0;
    max-width: min(21rem, 88vw);
    position: fixed;
    top: 0;
    transform: translateX(-105%);
    transition: transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
    width: min(21rem, 88vw);
    z-index: 30;
  }

  .history--open {
    transform: translateX(0);
  }

  .chat__header {
    gap: 0.8rem;
    grid-template-columns: minmax(0, 1fr) auto;
    padding: 0 0.8rem;
  }

  .run-actions .ghost-button {
    display: none;
  }

  .messages {
    padding: 0.95rem 0.8rem;
  }

  .empty-state {
    max-width: 22rem;
  }

  .empty-state p {
    font-size: clamp(1.75rem, 8vw, 2.15rem);
  }

  .message {
    max-width: 90%;
  }

  .composer {
    padding: 0.65rem 0.7rem max(0.75rem, env(safe-area-inset-bottom));
  }

  .composer__bar {
    align-items: center;
  }

  .composer__bar span,
  .composer__bar p {
    display: none;
  }
}

@media (max-width: 520px) {
  .workspace {
    --header-height: 3.65rem;
  }

  .status-pill {
    display: none;
  }

  .chat__identity p {
    font-size: 0.92rem;
  }

  .chat__identity span {
    font-size: 0.76rem;
  }

  .composer-shell {
    border-radius: 1rem;
    padding: 0.6rem;
  }

  textarea {
    font-size: 0.96rem;
    min-height: 2.35rem;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workspace,
  button,
  .history {
    transition: none !important;
  }

  button:hover:not(:disabled),
  button:active:not(:disabled) {
    transform: none;
  }
}

@media (prefers-reduced-transparency: reduce) {
  .history,
  .chat__header,
  .composer,
  .settings-modal,
  .small-modal,
  .message {
    backdrop-filter: none;
    background: var(--moksha-surface);
  }
}
</style>
