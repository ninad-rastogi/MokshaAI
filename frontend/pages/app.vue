<script setup lang="ts">
import type { ChatSummary, Citation, Message, Scripture } from "~/types/api";

definePageMeta({ ssr: false });

const api = useApi();
const stream = useRunStream();
const user = ref("");
const chats = ref<ChatSummary[]>([]);
const messages = ref<Message[]>([]);
const scriptures = ref<Scripture[]>([]);
const activeChatId = ref("");
const prompt = ref("");
const activeRunId = ref("");
const streamingText = ref("");
const streamingSources = ref<Citation[]>([]);
const statusText = ref("Ready");
const modelProfile = ref("");
const busy = ref(false);
const error = ref("");

const modelOptions = [
  { label: "Admin default", value: "" },
  { label: "Moksha Qwen3 local", value: "moksha-qwen3:4b-instruct-q3km" },
];

const indexedCount = computed(
  () => scriptures.value.filter((scripture) => scripture.is_indexed).length,
);

onMounted(async () => {
  try {
    const profile = await api.me();
    user.value = profile.spiritual_name || profile.email;
    await Promise.all([loadChats(), loadScriptures()]);
    if (!activeChatId.value) await newChat();
  } catch {
    await navigateTo("/");
  }
});

onBeforeUnmount(() => stream.close());

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
        <button type="button" title="New chat" @click="newChat">+</button>
      </div>
      <nav>
        <button
          v-for="chat in chats"
          :key="chat.id"
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
        <div>
          <strong>{{ user }}</strong>
          <span>{{ statusText }}</span>
        </div>
        <div class="toolbar">
          <select v-model="modelProfile" aria-label="Model profile">
            <option
              v-for="option in modelOptions"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>
          <button type="button" :disabled="!activeRunId" @click="connectRun()">
            Reconnect
          </button>
          <button type="button" :disabled="!busy" @click="stopRun">Stop</button>
        </div>
      </header>

      <div class="messages" aria-live="polite">
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
        <textarea id="prompt" v-model="prompt" rows="3" :disabled="busy" />
        <div>
          <p v-if="error" role="alert">{{ error }}</p>
          <button
            type="button"
            :disabled="busy || !messages.length"
            @click="retryLast"
          >
            Retry
          </button>
          <button type="submit" :disabled="busy || !prompt.trim()">Send</button>
        </div>
      </form>
    </section>

    <aside class="status" aria-label="Indexing and account status">
      <section>
        <h2>Scriptures</h2>
        <p>{{ indexedCount }} of {{ scriptures.length }} indexed</p>
        <ul>
          <li v-for="scripture in scriptures" :key="scripture.id">
            <span>{{ scripture.name }}</span>
            <strong>{{ scripture.is_indexed ? "Indexed" : "Pending" }}</strong>
          </li>
        </ul>
      </section>
      <section>
        <h2>Settings</h2>
        <p>
          Theme follows your device preference. Session auth is cookie based.
        </p>
        <button type="button" @click="signOut">Sign out</button>
      </section>
    </aside>
  </main>
</template>

<style scoped>
.workspace {
  display: grid;
  grid-template-columns: minmax(14rem, 18rem) minmax(0, 1fr) minmax(
      15rem,
      20rem
    );
  min-height: 100svh;
}

.history,
.status {
  background: var(--moksha-surface);
  border-color: var(--moksha-line);
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
.toolbar,
.composer div {
  align-items: center;
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
}

button,
select,
textarea {
  background: var(--moksha-surface);
  border: 1px solid var(--moksha-line);
  border-radius: 0.4rem;
  color: var(--moksha-ink);
}

button,
select {
  min-height: 2.5rem;
  padding: 0 0.75rem;
}

nav {
  display: grid;
  gap: 0.35rem;
  margin-top: 1rem;
}

nav button {
  display: grid;
  height: auto;
  justify-items: start;
  min-height: 3.25rem;
  text-align: left;
}

nav button[aria-current="page"] {
  border-color: var(--moksha-accent);
}

small,
.chat__header span,
.status p {
  color: var(--moksha-muted);
}

.chat {
  display: grid;
  grid-template-rows: auto 1fr auto;
  min-width: 0;
}

.chat__header {
  border-bottom: 1px solid var(--moksha-line);
  padding: 0.85rem 1rem;
}

.messages {
  align-content: start;
  display: grid;
  gap: 1rem;
  overflow: auto;
  padding: 1rem;
}

.message {
  border: 1px solid var(--moksha-line);
  border-radius: 0.5rem;
  max-width: 54rem;
  padding: 1rem;
}

.message--user {
  justify-self: end;
}

.message--assistant {
  background: var(--moksha-surface);
  justify-self: start;
}

.composer {
  border-top: 1px solid var(--moksha-line);
  display: grid;
  gap: 0.5rem;
  padding: 1rem;
}

.composer label,
h2 {
  font-size: 1rem;
  margin: 0;
}

textarea {
  min-height: 5rem;
  padding: 0.75rem;
  resize: vertical;
}

.status section {
  border-bottom: 1px solid var(--moksha-line);
  padding: 1rem 0;
}

.status ul {
  display: grid;
  gap: 0.6rem;
  list-style: none;
  margin: 1rem 0 0;
  padding: 0;
}

.status li {
  display: flex;
  gap: 0.75rem;
  justify-content: space-between;
}

@media (max-width: 980px) {
  .workspace {
    grid-template-columns: 1fr;
  }

  .history,
  .status {
    border: 0;
  }

  .history nav {
    grid-auto-flow: column;
    overflow-x: auto;
  }
}
</style>
