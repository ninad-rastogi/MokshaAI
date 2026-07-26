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
  const page = await api.chats();
  chats.value = page.results;
  activeChatId.value = activeChatId.value || chats.value[0]?.id || "";
}

async function loadMessages() {
  if (!activeChatId.value) return;
  const page = await api.messages(activeChatId.value);
  messages.value = page.results;
}

async function loadScriptures() {
  const page = await api.scriptures();
  scriptures.value = page.results;
}

async function selectChat(chatId: string) {
  activeChatId.value = chatId;
  streamingText.value = "";
  streamingSources.value = [];
  await loadMessages();
}

async function newChat() {
  const chat = await api.createChat();
  chats.value = [chat, ...chats.value];
  await selectChat(chat.id);
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
          title="New chat"
          @click="newChat"
        >
          +
        </button>
      </div>

      <nav class="chat-list">
        <button
          v-for="chat in chats"
          :key="chat.id"
          class="chat-card"
          type="button"
          :aria-current="chat.id === activeChatId ? 'page' : undefined"
          @click="selectChat(chat.id)"
        >
          <span>{{ chat.name }}</span>
          <small>{{ chat.message_count }} messages</small>
        </button>
      </nav>
    </aside>

    <section class="chat" aria-label="Chat workspace">
      <header class="chat__header">
        <div class="chat__identity">
          <p>{{ activeChat?.name || "New Spiritual Conversation" }}</p>
          <span>{{ user }}</span>
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
            Reconnect
          </button>
          <button
            class="ghost-button ghost-button--danger"
            type="button"
            :disabled="!busy"
            @click="stopRun"
          >
            Stop
          </button>
        </div>
      </header>

      <div class="messages" aria-live="polite">
        <div v-if="!messages.length && !streamingText" class="empty-state">
          <p>Bring what weighs on you.</p>
          <span
            >Moksha AI will listen, search the scriptures, and answer with
            relevant wisdom and citations.</span
          >
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
          placeholder="Share what you are facing..."
        />
        <div class="composer__bar">
          <p v-if="error" role="alert">{{ error }}</p>
          <span v-else>{{
            modelOptions.find((option) => option.value === modelProfile)?.label
          }}</span>
          <div>
            <button
              class="ghost-button"
              type="button"
              :disabled="busy || !messages.length"
              @click="retryLast"
            >
              Retry
            </button>
            <button
              class="primary-button"
              type="submit"
              :disabled="busy || !prompt.trim()"
            >
              Send
            </button>
          </div>
        </div>
      </form>
    </section>

    <aside class="status" aria-label="Settings and indexing status">
      <section class="panel">
        <h2>Settings</h2>

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

        <button class="ghost-button" type="button" @click="signOut">
          Sign out
        </button>
      </section>

      <section class="panel">
        <div class="panel__title">
          <h2>Scriptures</h2>
          <span>{{ indexedCount }} / {{ scriptures.length }}</span>
        </div>
        <ul class="scripture-list">
          <li v-for="scripture in scriptures" :key="scripture.id">
            <span>{{ scripture.name }}</span>
            <strong>{{ scripture.is_indexed ? "Indexed" : "Pending" }}</strong>
          </li>
        </ul>
      </section>
    </aside>
  </main>
</template>

<style scoped>
.workspace {
  background:
    radial-gradient(
      circle at top left,
      rgb(154 91 35 / 10%),
      transparent 24rem
    ),
    var(--moksha-bg);
  display: grid;
  grid-template-columns: minmax(15rem, 18rem) minmax(0, 1fr) minmax(
      17rem,
      21rem
    );
  min-height: 100svh;
}

.history,
.status {
  background: color-mix(in srgb, var(--moksha-surface) 92%, transparent);
  border-color: var(--moksha-line);
  min-width: 0;
  padding: 1rem;
}

.history {
  border-right: 1px solid var(--moksha-line);
}

.status {
  border-left: 1px solid var(--moksha-line);
}

.history__top,
.chat__header,
.run-actions,
.composer__bar,
.composer__bar > div,
.panel__title {
  align-items: center;
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
}

button,
select,
textarea {
  background: var(--moksha-surface-raised);
  border: 1px solid var(--moksha-line);
  border-radius: 0.5rem;
  color: var(--moksha-ink);
}

button,
select {
  min-height: 2.35rem;
  padding: 0 0.8rem;
}

button {
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.48;
}

.icon-button {
  border-radius: 50%;
  font-size: 1.2rem;
  height: 2.35rem;
  padding: 0;
  width: 2.35rem;
}

.ghost-button {
  background: transparent;
}

.ghost-button--danger {
  color: var(--moksha-danger);
}

.primary-button {
  background: var(--moksha-accent-strong);
  border-color: var(--moksha-accent-strong);
  color: var(--moksha-surface);
}

.chat-list {
  display: grid;
  gap: 0.5rem;
  margin-top: 1rem;
}

.chat-card {
  align-items: start;
  display: grid;
  height: auto;
  justify-items: start;
  line-height: 1.3;
  min-height: 4rem;
  padding: 0.75rem;
  text-align: left;
  width: 100%;
}

.chat-card[aria-current="page"] {
  background: color-mix(
    in srgb,
    var(--moksha-accent) 10%,
    var(--moksha-surface)
  );
  border-color: var(--moksha-accent);
}

.chat-card span,
.chat__identity p {
  font-weight: 700;
}

small,
.chat__identity span,
.composer__bar span,
.panel__title span,
.empty-state span {
  color: var(--moksha-muted);
}

.chat {
  display: grid;
  grid-template-rows: auto 1fr auto;
  min-width: 0;
}

.chat__header {
  backdrop-filter: blur(16px);
  border-bottom: 1px solid var(--moksha-line);
  min-height: 4.75rem;
  padding: 0.9rem 1.5rem;
}

.chat__identity {
  min-width: 0;
}

.chat__identity p,
h2,
.composer label {
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
  font-size: 0.85rem;
  padding: 0.35rem 0.7rem;
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
  padding: 1.5rem;
}

.empty-state {
  align-self: center;
  justify-self: center;
  max-width: 28rem;
  text-align: center;
}

.empty-state p {
  font-family: Charter, Cambria, "Nirmala UI", serif;
  font-size: clamp(2rem, 6vw, 4rem);
  font-weight: 700;
  margin: 0 0 0.5rem;
}

.message {
  border: 1px solid var(--moksha-line);
  border-radius: 0.65rem;
  box-shadow: var(--moksha-shadow);
  line-height: 1.65;
  max-width: min(44rem, 92%);
  padding: 1rem;
}

.message--user {
  background: var(--moksha-accent-strong);
  color: var(--moksha-surface);
  justify-self: end;
}

.message--assistant {
  background: var(--moksha-surface-raised);
  justify-self: start;
}

.composer {
  background: color-mix(in srgb, var(--moksha-surface) 96%, transparent);
  border-top: 1px solid var(--moksha-line);
  display: grid;
  gap: 0.65rem;
  padding: 1rem 1.5rem;
}

textarea {
  line-height: 1.5;
  min-height: 5rem;
  padding: 0.85rem;
  resize: vertical;
}

.composer__bar p {
  color: var(--moksha-danger);
  margin: 0;
}

.panel {
  border-bottom: 1px solid var(--moksha-line);
  display: grid;
  gap: 1rem;
  padding: 1rem 0;
}

.panel:first-child {
  padding-top: 0;
}

.field {
  display: grid;
  gap: 0.45rem;
}

.field > span {
  color: var(--moksha-muted);
  font-size: 0.85rem;
}

.segmented {
  background: var(--moksha-bg);
  border: 1px solid var(--moksha-line);
  border-radius: 0.55rem;
  display: grid;
  gap: 0.25rem;
  grid-template-columns: repeat(3, 1fr);
  padding: 0.25rem;
}

.segmented button {
  background: transparent;
  border-color: transparent;
  min-height: 2rem;
  padding: 0 0.5rem;
}

.segmented button[aria-pressed="true"] {
  background: var(--moksha-surface-raised);
  border-color: var(--moksha-line);
  box-shadow: 0 0.35rem 1rem rgb(0 0 0 / 8%);
}

.status select {
  width: 100%;
}

.scripture-list {
  display: grid;
  gap: 0.6rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

.scripture-list li {
  display: grid;
  gap: 0.25rem;
}

.scripture-list strong {
  color: var(--moksha-leaf);
  font-size: 0.85rem;
}

@media (max-width: 1080px) {
  .workspace {
    grid-template-columns: minmax(13rem, 16rem) minmax(0, 1fr);
  }

  .status {
    border-left: 0;
    border-top: 1px solid var(--moksha-line);
    grid-column: 1 / -1;
  }
}

@media (max-width: 760px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .history,
  .status {
    border: 0;
  }

  .chat__header,
  .composer__bar {
    align-items: stretch;
    flex-direction: column;
  }

  .run-actions,
  .composer__bar > div {
    width: 100%;
  }

  .run-actions > button,
  .composer__bar button {
    flex: 1;
  }

  .chat-list {
    grid-auto-columns: minmax(13rem, 1fr);
    grid-auto-flow: column;
    overflow-x: auto;
  }

  .messages,
  .composer,
  .chat__header {
    padding-left: 1rem;
    padding-right: 1rem;
  }
}
</style>
