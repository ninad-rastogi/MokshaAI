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
  streamingText.value = "";
  streamingSources.value = [];
  await loadMessages();
}

async function newChat() {
  showArchived.value = false;
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
  <main class="workspace">
    <aside class="history" aria-label="Chat history">
      <div class="history__top">
        <MokshaBrand />
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
    </aside>

    <section class="chat" aria-label="Chat workspace">
      <header class="chat__header">
        <div class="chat__identity">
          <p>{{ activeChat?.name || "New conversation" }}</p>
          <span>{{ activeModelLabel }}</span>
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
          <button
            class="icon-button"
            type="button"
            aria-label="Settings"
            title="Settings"
            @click="openSettings"
          >
            <UIcon name="i-lucide-settings" aria-hidden="true" />
          </button>
        </div>
      </header>

      <div class="messages" aria-live="polite">
        <div v-if="!messages.length && !streamingText" class="empty-state">
          <p>Bring the question you cannot carry alone.</p>
          <span>
            Moksha AI listens first, then searches your scripture library for
            grounded guidance with citations.
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
        <label for="prompt">Ask Moksha AI</label>
        <textarea
          id="prompt"
          v-model="prompt"
          rows="3"
          :disabled="busy"
          placeholder="Share what is weighing on your mind..."
        />
        <div class="composer__bar">
          <p v-if="error" role="alert">{{ error }}</p>
          <span v-else
            >Scripture-grounded answers. Citations shown when found.</span
          >
          <div>
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
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--moksha-ember) 10%, transparent),
      transparent 35%
    ),
    linear-gradient(
      220deg,
      color-mix(in srgb, var(--moksha-leaf) 16%, transparent),
      transparent 42%
    ),
    var(--moksha-bg);
  display: grid;
  grid-template-columns: minmax(17rem, 21rem) minmax(0, 1fr);
  min-height: 100svh;
}

.history,
.chat__header,
.composer,
.settings-modal,
.small-modal {
  backdrop-filter: blur(22px);
  background: var(--moksha-glass);
  border-color: var(--moksha-glass-line);
}

.history {
  border-right: 1px solid var(--moksha-glass-line);
  display: grid;
  grid-template-rows: auto auto auto 1fr;
  min-width: 0;
  padding: 1rem;
}

.history__top,
.chat__header,
.run-actions,
.composer__bar,
.composer__bar > div,
.panel__title,
.settings-modal header,
.small-modal div {
  align-items: center;
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
}

button,
input,
select,
textarea {
  background: var(--moksha-surface-raised);
  border: 1px solid var(--moksha-line);
  border-radius: 0.65rem;
  color: var(--moksha-ink);
}

button,
select {
  align-items: center;
  display: inline-flex;
  gap: 0.45rem;
  justify-content: center;
  min-height: 2.5rem;
  padding: 0 0.85rem;
}

button {
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.icon-button {
  border-radius: 999px;
  height: 2.5rem;
  min-width: 2.5rem;
  padding: 0;
  width: 2.5rem;
}

.icon-button :deep(svg),
button :deep(svg) {
  flex: 0 0 auto;
  height: 1.05rem;
  width: 1.05rem;
}

.ghost-button {
  background: color-mix(in srgb, var(--moksha-surface-raised) 42%, transparent);
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
  background: var(--moksha-accent-strong);
}

.danger-button {
  background: var(--moksha-danger);
}

.search {
  display: grid;
  gap: 0.45rem;
  margin-top: 1rem;
}

.search span,
.field > span,
.settings-modal header span,
small,
.chat__identity span,
.composer__bar span,
.panel__title span,
.empty-state span {
  color: var(--moksha-muted);
}

.search span,
.field > span {
  font-size: 0.82rem;
  font-weight: 700;
}

.search input {
  min-height: 2.55rem;
  padding: 0 0.8rem;
}

.history-tabs,
.segmented {
  background: color-mix(in srgb, var(--moksha-bg) 72%, transparent);
  border: 1px solid var(--moksha-line);
  border-radius: 0.75rem;
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
  min-height: 2.15rem;
}

.history-tabs button[aria-selected="true"],
.segmented button[aria-pressed="true"] {
  background: var(--moksha-surface-raised);
  border-color: var(--moksha-line);
  box-shadow: var(--moksha-shadow-soft);
}

.chat-list {
  align-content: start;
  display: grid;
  gap: 0.55rem;
  margin-top: 0.85rem;
  overflow: auto;
}

.chat-card {
  border: 1px solid transparent;
  border-radius: 0.85rem;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  position: relative;
}

.chat-card[aria-current="page"] {
  background: color-mix(in srgb, var(--moksha-accent) 14%, var(--moksha-glass));
  border-color: var(--moksha-accent);
}

.chat-card__main {
  align-items: start;
  background: transparent;
  border: 0;
  display: grid;
  height: auto;
  justify-items: start;
  line-height: 1.3;
  min-height: 4.3rem;
  min-width: 0;
  padding: 0.8rem;
  text-align: left;
}

.chat-card__main span,
.chat__identity p,
.settings-modal header p {
  font-weight: 800;
}

.chat-card__main span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.chat-card__menu {
  align-self: center;
  background: transparent;
  border-color: transparent;
  height: 2.2rem;
  min-width: 2.2rem;
  padding: 0;
  width: 2.2rem;
}

.chat-menu {
  background: var(--moksha-surface-raised);
  border: 1px solid var(--moksha-line);
  border-radius: 0.75rem;
  box-shadow: var(--moksha-shadow);
  display: grid;
  min-width: 9rem;
  padding: 0.35rem;
  position: absolute;
  right: 0.5rem;
  top: 3.2rem;
  z-index: 5;
}

.chat-menu button {
  background: transparent;
  border-color: transparent;
  justify-content: start;
  text-align: left;
}

.history-empty {
  color: var(--moksha-muted);
  margin: 1rem 0;
}

.chat {
  display: grid;
  grid-template-rows: auto 1fr auto;
  min-width: 0;
}

.chat__header {
  border-bottom: 1px solid var(--moksha-glass-line);
  min-height: 4.75rem;
  padding: 0.85rem 1.5rem;
}

.chat__identity {
  min-width: 0;
}

.chat__identity p,
h2 {
  font-size: 1rem;
  margin: 0;
}

.chat__identity p,
.chat__identity span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-pill {
  border: 1px solid var(--moksha-line);
  border-radius: 999px;
  color: var(--moksha-muted);
  font-size: 0.84rem;
  padding: 0.35rem 0.75rem;
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
  gap: 1rem;
  overflow: auto;
  padding: 1.5rem max(1.5rem, 8vw);
}

.empty-state {
  align-self: center;
  justify-self: center;
  max-width: 36rem;
  text-align: center;
}

.empty-state p {
  font-family: Charter, Cambria, "Nirmala UI", serif;
  font-size: clamp(1.8rem, 4.2vw, 3.15rem);
  font-weight: 800;
  line-height: 1.05;
  margin: 0 0 0.8rem;
}

.message {
  border: 1px solid var(--moksha-glass-line);
  border-radius: 1rem;
  box-shadow: var(--moksha-shadow-soft);
  line-height: 1.65;
  max-width: min(46rem, 92%);
  padding: 1rem;
}

.message--user {
  background: var(--moksha-user-bubble);
  color: var(--moksha-user-ink);
  justify-self: end;
}

.message--assistant {
  background: var(--moksha-glass);
  justify-self: start;
}

.composer {
  border-top: 1px solid var(--moksha-glass-line);
  display: grid;
  gap: 0.65rem;
  padding: 1rem max(1.5rem, 8vw);
}

.composer label {
  font-weight: 800;
}

textarea,
.small-modal input,
.field select {
  line-height: 1.5;
  padding: 0.85rem;
  width: 100%;
}

textarea {
  min-height: 5rem;
  resize: vertical;
}

.composer__bar p {
  color: var(--moksha-danger);
  margin: 0;
}

.modal-backdrop {
  align-items: center;
  background: rgb(0 0 0 / 48%);
  display: grid;
  inset: 0;
  justify-items: center;
  padding: 1rem;
  position: fixed;
  z-index: 50;
}

.settings-modal,
.small-modal {
  border: 1px solid var(--moksha-glass-line);
  border-radius: 1rem;
  box-shadow: var(--moksha-shadow);
  display: grid;
  gap: 1rem;
  max-height: min(48rem, 92svh);
  overflow: auto;
  padding: 1.25rem;
  width: min(32rem, 100%);
}

.field,
.scripture-panel {
  display: grid;
  gap: 0.55rem;
}

.scripture-panel {
  border-top: 1px solid var(--moksha-line);
  padding-top: 1rem;
}

.scripture-list {
  display: grid;
  gap: 0.55rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.scripture-list li {
  align-items: center;
  display: flex;
  justify-content: space-between;
}

.scripture-list strong {
  color: var(--moksha-leaf);
  font-size: 0.85rem;
}

.signout {
  justify-content: center;
}

.small-modal p {
  color: var(--moksha-muted);
  margin: 0;
}

@media (max-width: 880px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .history {
    border-bottom: 1px solid var(--moksha-line);
    border-right: 0;
    max-height: 18rem;
  }

  .run-actions,
  .composer__bar {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .run-actions > button,
  .composer__bar button {
    flex: 1;
  }

  .messages,
  .composer,
  .chat__header {
    padding-left: 1rem;
    padding-right: 1rem;
  }
}
</style>
