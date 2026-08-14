<script setup lang="ts">
import type { DropdownMenuItem } from "@nuxt/ui";
import { useMediaQuery } from "@vueuse/core";
import type { ChatSummary } from "~/types/api";

const props = defineProps<{
  open: boolean;
  chats: ChatSummary[];
  activeChatId: string;
  search: string;
  archived: boolean;
  user: string;
  modelLabel: string;
  loading?: boolean;
}>();

const emit = defineEmits<{
  "update:open": [value: boolean];
  "update:search": [value: string];
  "change-view": [archived: boolean];
  select: [chatId: string];
  create: [];
  rename: [chat: ChatSummary];
  archive: [chat: ChatSummary];
  delete: [chat: ChatSummary];
  settings: [];
  theme: [];
}>();

const filteredChats = computed(() => {
  const needle = props.search.trim().toLowerCase();
  if (!needle) return props.chats;
  return props.chats.filter((chat) => chat.name.toLowerCase().includes(needle));
});

const isMobile = useMediaQuery("(max-width: 860px)");
const mounted = ref(false);
const mobileSemantics = computed(() => mounted.value && isMobile.value);

onMounted(() => {
  mounted.value = true;
});

function closeHistory() {
  emit("update:open", false);
}

function chatActions(chat: ChatSummary): DropdownMenuItem[][] {
  return [
    [
      {
        label: "Rename",
        icon: "i-lucide-pencil",
        onSelect: () => emit("rename", chat),
      },
      {
        label: chat.is_archived ? "Restore" : "Archive",
        icon: chat.is_archived
          ? "i-lucide-archive-restore"
          : "i-lucide-archive",
        onSelect: () => emit("archive", chat),
      },
    ],
    [
      {
        label: "Delete",
        icon: "i-lucide-trash-2",
        color: "error",
        onSelect: () => emit("delete", chat),
      },
    ],
  ];
}
</script>

<template>
  <button
    v-if="open"
    class="sidebar-scrim"
    type="button"
    aria-hidden="true"
    tabindex="-1"
    @click="closeHistory"
  />

  <aside
    :class="['history', { 'history--open': open }]"
    :aria-hidden="!open ? 'true' : undefined"
    :inert="!open"
    :role="mobileSemantics ? 'dialog' : undefined"
    :aria-modal="mobileSemantics && open ? 'true' : undefined"
    aria-label="Conversation history"
    @keydown.esc.stop="closeHistory"
  >
    <div class="history__brand-row">
      <MokshaBrand />
      <UTooltip text="Close history">
        <button
          class="icon-control mobile-close"
          type="button"
          aria-label="Close conversation history"
          @click.stop="closeHistory"
          @pointerdown.stop
        >
          <UIcon name="i-lucide-x" aria-hidden="true" />
        </button>
      </UTooltip>
    </div>

    <button
      class="new-chat"
      type="button"
      aria-label="Start new conversation"
      @click="emit('create')"
    >
      <UIcon
        class="new-chat__icon"
        name="i-lucide-square-pen"
        aria-hidden="true"
      />
      <span class="new-chat__label" title="Start new conversation"
        >New chat</span
      >
      <kbd>Ctrl K</kbd>
    </button>

    <label class="history-search">
      <UIcon name="i-lucide-search" aria-hidden="true" />
      <span class="sr-only">Search conversations</span>
      <input
        :value="search"
        type="search"
        placeholder="Search conversations"
        @input="
          emit('update:search', ($event.target as HTMLInputElement).value)
        "
      />
    </label>

    <div class="history-tabs" role="tablist" aria-label="Conversation history">
      <button
        type="button"
        role="tab"
        :aria-selected="!archived"
        @click="emit('change-view', false)"
      >
        Recent
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="archived"
        @click="emit('change-view', true)"
      >
        Archived
      </button>
    </div>

    <nav class="conversation-list" aria-label="Conversations">
      <div v-if="loading" class="conversation-skeletons" aria-label="Loading">
        <USkeleton v-for="item in 4" :key="item" class="h-12 w-full" />
      </div>

      <div
        v-for="chat in filteredChats"
        v-else
        :key="chat.id"
        :class="[
          'conversation-item',
          { 'conversation-item--active': chat.id === activeChatId },
        ]"
      >
        <button
          class="conversation-item__select"
          type="button"
          :aria-current="chat.id === activeChatId ? 'page' : undefined"
          @click="emit('select', chat.id)"
        >
          <span>{{ chat.name }}</span>
          <small>
            {{ chat.message_count || "No" }}
            {{ chat.message_count === 1 ? "message" : "messages" }}
          </small>
        </button>

        <UDropdownMenu
          :items="chatActions(chat)"
          :content="{ align: 'end', side: 'right', sideOffset: 6 }"
        >
          <UTooltip text="Conversation actions">
            <button
              class="conversation-item__menu"
              type="button"
              :aria-label="`Actions for ${chat.name}`"
            >
              <UIcon name="i-lucide-ellipsis" aria-hidden="true" />
            </button>
          </UTooltip>
        </UDropdownMenu>
      </div>

      <div v-if="!loading && !filteredChats.length" class="history-empty">
        <UIcon
          :name="archived ? 'i-lucide-archive' : 'i-lucide-message-circle'"
          aria-hidden="true"
        />
        <p>
          {{
            archived ? "No archived conversations" : "No conversations found"
          }}
        </p>
        <span>{{
          search
            ? "Try another search."
            : archived
              ? "Chats you archive appear here."
              : "Begin a new conversation."
        }}</span>
      </div>
    </nav>

    <footer class="history-footer">
      <button
        class="account-control"
        type="button"
        aria-label="Open settings"
        @click="emit('settings')"
      >
        <span class="account-avatar">{{ user.slice(0, 1).toUpperCase() }}</span>
        <span class="account-copy">
          <strong>{{ user || "Moksha AI" }}</strong>
          <small>{{ modelLabel }}</small>
        </span>
        <UIcon name="i-lucide-chevrons-up-down" aria-hidden="true" />
      </button>
      <UTooltip text="Change theme">
        <button
          class="icon-control theme-control"
          type="button"
          aria-label="Change theme"
          @click="emit('theme')"
        >
          <UIcon name="i-lucide-sun-moon" aria-hidden="true" />
        </button>
      </UTooltip>
    </footer>
  </aside>
</template>

<style scoped>
.history {
  background: var(--moksha-sidebar);
  border-right: 1px solid var(--moksha-glass-line);
  container-type: inline-size;
  display: grid;
  grid-template-rows: auto auto auto auto minmax(0, 1fr) auto;
  height: 100svh;
  overflow: hidden;
  padding: 0.75rem;
  position: relative;
  z-index: 20;
}

.history::after {
  background: linear-gradient(125deg, rgb(255 255 255 / 7%), transparent 32%);
  content: "";
  inset: 0;
  pointer-events: none;
  position: absolute;
}

.history__brand-row,
.history-footer {
  align-items: center;
  display: flex;
  gap: 0.5rem;
  justify-content: space-between;
  position: relative;
  z-index: 1;
}

.mobile-close {
  display: inline-flex;
}

.new-chat {
  align-items: center;
  background: var(--moksha-glass-raised);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 0.58rem;
  color: var(--moksha-ink);
  display: grid;
  font-size: 0.76rem;
  font-weight: 720;
  gap: 0.42rem;
  grid-template-columns: 0.88rem minmax(0, 1fr) auto;
  height: 2.25rem;
  line-height: 1;
  margin-top: 0.55rem;
  min-width: 0;
  padding: 0 0.58rem;
  text-align: left;
  width: 100%;
}

.new-chat > * {
  min-width: 0;
}

.new-chat__icon {
  flex: 0 0 auto;
  color: var(--moksha-accent);
  height: 0.86rem;
  width: 0.86rem;
}

.new-chat__label {
  display: block;
  font-size: 0.76rem;
  line-height: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

kbd {
  color: var(--moksha-muted);
  font: 650 0.58rem/1 var(--moksha-font);
  min-width: max-content;
  white-space: nowrap;
}

.history-search {
  align-items: center;
  background: var(--moksha-control);
  border: 1px solid transparent;
  border-radius: 0.65rem;
  display: grid;
  gap: 0.5rem;
  grid-template-columns: auto minmax(0, 1fr);
  margin-top: 0.55rem;
  min-height: 2.35rem;
  padding: 0 0.65rem;
}

.history-search:focus-within {
  border-color: var(--moksha-focus);
  box-shadow: 0 0 0 3px var(--moksha-focus-ring);
}

.history-search svg {
  color: var(--moksha-muted);
  height: 0.9rem;
  width: 0.9rem;
}

.history-search input {
  background: transparent;
  border: 0;
  color: var(--moksha-ink);
  font-size: 0.82rem;
  min-width: 0;
  outline: 0;
}

.history-tabs {
  display: grid;
  gap: 0.2rem;
  grid-template-columns: 1fr 1fr;
  margin-top: 0.55rem;
}

.history-tabs button {
  background: transparent;
  border: 0;
  border-radius: 0.5rem;
  color: var(--moksha-muted);
  font-size: 0.76rem;
  font-weight: 670;
  min-height: 2rem;
}

.history-tabs button[aria-selected="true"] {
  background: var(--moksha-control);
  color: var(--moksha-ink);
}

.conversation-list {
  min-height: 0;
  overflow: auto;
  padding: 0.55rem 0.1rem 0.75rem 0;
  position: relative;
  z-index: 1;
}

.conversation-skeletons {
  display: grid;
  gap: 0.45rem;
}

.conversation-item {
  border: 1px solid transparent;
  border-radius: 0.65rem;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 2rem;
  margin-bottom: 0.2rem;
  min-height: 3.2rem;
  position: relative;
}

.conversation-item:hover,
.conversation-item--active {
  background: var(--moksha-control);
}

.conversation-item--active {
  border-color: var(--moksha-glass-line);
  box-shadow: inset 2px 0 var(--moksha-accent);
}

.conversation-item__select,
.conversation-item__menu {
  background: transparent;
  border: 0;
  color: var(--moksha-ink);
}

.conversation-item__select {
  display: grid;
  justify-items: start;
  min-width: 0;
  padding: 0.55rem 0.65rem;
  text-align: left;
}

.conversation-item__select span {
  font-size: 0.82rem;
  font-weight: 650;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}

.conversation-item__select small {
  color: var(--moksha-muted);
  font-size: 0.7rem;
}

.conversation-item__menu {
  align-self: center;
  border-radius: 0.45rem;
  display: grid;
  height: 1.8rem;
  opacity: 0;
  place-items: center;
  width: 1.8rem;
}

.conversation-item:hover .conversation-item__menu,
.conversation-item--active .conversation-item__menu,
.conversation-item__menu:focus-visible {
  opacity: 1;
}

.history-empty {
  align-items: center;
  color: var(--moksha-muted);
  display: flex;
  flex-direction: column;
  padding: 2.2rem 0.8rem;
  text-align: center;
}

.history-empty svg {
  height: 1.1rem;
  width: 1.1rem;
}

.history-empty p {
  color: var(--moksha-ink);
  font-size: 0.8rem;
  font-weight: 680;
  margin: 0.55rem 0 0.15rem;
}

.history-empty span {
  font-size: 0.72rem;
}

.history-footer {
  border-top: 1px solid var(--moksha-glass-line);
  padding-top: 0.65rem;
}

.account-control {
  align-items: center;
  background: transparent;
  border: 0;
  border-radius: 0.6rem;
  color: var(--moksha-ink);
  display: grid;
  flex: 1;
  gap: 0.55rem;
  grid-template-columns: auto minmax(0, 1fr) auto;
  min-height: 2.7rem;
  min-width: 0;
  padding: 0.3rem 0.45rem;
  text-align: left;
}

.account-control:hover {
  background: var(--moksha-control);
}

.account-avatar {
  align-items: center;
  background: var(--moksha-accent-soft);
  border: 1px solid var(--moksha-glass-line);
  border-radius: 50%;
  color: var(--moksha-accent-ink);
  display: flex;
  font-size: 0.72rem;
  font-weight: 760;
  height: 1.8rem;
  justify-content: center;
  width: 1.8rem;
}

.account-copy {
  display: grid;
  min-width: 0;
}

.account-copy strong,
.account-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-copy strong {
  font-size: 0.76rem;
}

.account-copy small {
  color: var(--moksha-muted);
  font-size: 0.67rem;
}

.icon-control {
  align-items: center;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 0.55rem;
  color: var(--moksha-muted);
  display: inline-flex;
  height: 2.2rem;
  justify-content: center;
  width: 2.2rem;
}

.icon-control:hover {
  background: var(--moksha-control);
  border-color: var(--moksha-glass-line);
  color: var(--moksha-ink);
}

.sidebar-scrim {
  display: none;
}

@media (max-width: 860px) {
  .history {
    box-shadow: 1rem 0 3rem rgb(12 15 13 / 24%);
    left: 0;
    max-width: min(19rem, 88vw);
    position: fixed;
    top: 0;
    transform: translateX(-105%);
    transition: transform 220ms cubic-bezier(0.16, 1, 0.3, 1);
    width: min(19rem, 88vw);
  }

  .history--open {
    transform: translateX(0);
  }

  .mobile-close {
    display: inline-flex;
  }

  .sidebar-scrim {
    backdrop-filter: blur(3px);
    background: rgb(8 12 10 / 38%);
    border: 0;
    display: block;
    inset: 0;
    position: fixed;
    z-index: 19;
  }

  .conversation-item__menu {
    opacity: 1;
  }

  .new-chat kbd {
    display: none;
  }
}

@container (max-width: 17rem) {
  .new-chat kbd {
    display: none;
  }
}
</style>
