import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const appPage = readFileSync(resolve(root, "pages/app.vue"), "utf8");
const indexPage = readFileSync(resolve(root, "pages/index.vue"), "utf8");
const sidebarComponent = readFileSync(
  resolve(root, "components/app/ChatSidebar.vue"),
  "utf8",
);
const settingsComponent = readFileSync(
  resolve(root, "components/app/SettingsDialog.vue"),
  "utf8",
);
const composerComponent = readFileSync(
  resolve(root, "components/app/ChatComposer.vue"),
  "utf8",
);
const conversationMessage = readFileSync(
  resolve(root, "components/app/ConversationMessage.vue"),
  "utf8",
);
const citationComponent = readFileSync(
  resolve(root, "components/CitationList.vue"),
  "utf8",
);
const apiComposable = readFileSync(
  resolve(root, "composables/useApi.ts"),
  "utf8",
);
const runStreamComposable = readFileSync(
  resolve(root, "composables/useRunStream.ts"),
  "utf8",
);
const mainCss = readFileSync(resolve(root, "assets/css/main.css"), "utf8");

describe("app shell", () => {
  it("shows a bounded source quality failure instead of pending", () => {
    expect(settingsComponent).toContain('"index_source_text_corrupt"');
    expect(settingsComponent).toContain('"Source needs OCR"');
    expect(settingsComponent).toContain('"index_ocr_unavailable"');
    expect(settingsComponent).toContain('"Install OCR model"');
    expect(settingsComponent).toContain('"index_ocr_quality_failed"');
    expect(settingsComponent).toContain('"OCR needs review"');
    expect(settingsComponent).toContain(
      '"Source text failed exact-verse quality checks"',
    );
  });

  it("keeps theme and model controls inside a settings dialog", () => {
    expect(settingsComponent).toContain('aria-label="Theme"');
    expect(settingsComponent).toContain('aria-label="Primary response model"');
    expect(settingsComponent).toContain('id="fallback-model"');
    expect(settingsComponent).toContain("<UModal");
    expect(appPage).toContain("settingsOpen");
    expect(appPage).toContain("settingsMessageSection");
    expect(settingsComponent).toContain("messageSection: SettingsSection");
    expect(settingsComponent).toContain("visibleMessage");
    expect(appPage).toContain("saveModelPreference");
    expect(apiComposable).toContain("updateModelPreference");
    expect(appPage).not.toContain('aria-label="Model profile"');
    expect(appPage).not.toContain("Admin default");
  });

  it("keeps scripture indexing progress visible across workspace and settings", () => {
    expect(settingsComponent).toContain('emit("section", section)');
    expect(appPage).toContain("activeIndexingJobs");
    expect(appPage).toContain("scriptureProgressLabel");
    expect(appPage).toContain("scriptureProgressCompactLabel");
    expect(appPage).toContain("library-status");
    expect(appPage).toContain("library-status__compact");
    expect(appPage).toContain("library-progress-panel");
    expect(appPage).toContain("Preparing scripture library");
    expect(appPage).toContain("Open scripture indexing progress");
    expect(appPage).toContain("scheduleScriptureRefresh");
    expect(appPage).toContain("scriptureRefreshDelay");
    expect(appPage).toContain('@section="settingsSection = $event"');
    expect(settingsComponent).toContain("indexingPhase");
    expect(settingsComponent).toContain("index-progress");
    expect(settingsComponent).toContain("OCR pages scanned");
    expect(settingsComponent).toContain("Running local OCR");
    expect(settingsComponent).toContain("Embedding passages");
    const messageThreadStart = appPage.indexOf('class="message-thread"');
    const responseErrorStart = appPage.indexOf('class="response-error"');
    const messageThread = appPage.slice(messageThreadStart, responseErrorStart);
    expect(messageThread).not.toContain("OCR");
    expect(messageThread).not.toContain("Embedding passages");
    expect(messageThread).not.toContain("indexing progress");
  });

  it("exposes production chat history actions", () => {
    expect(sidebarComponent).toContain("Search conversations");
    expect(sidebarComponent).toContain("Rename");
    expect(sidebarComponent).toContain("Archive");
    expect(sidebarComponent).toContain("Delete");
    expect(apiComposable).toContain("renameChat");
    expect(apiComposable).toContain("deleteChat");
    expect(apiComposable).toContain("archiveChat");
  });

  it("keeps archived conversations out of the active composer flow", () => {
    expect(appPage).toContain("Restore it before continuing the conversation.");
    expect(appPage).toContain("activeChat && !isArchivedChat");
    expect(appPage).toContain("restoreActiveArchivedChat");
  });

  it("puts provider setup in settings with explicit remote data consent", () => {
    expect(settingsComponent).toContain("Add connection");
    expect(settingsComponent).toContain("remote_data_consent");
    expect(settingsComponent).toMatch(
      /subscription does not\s+automatically include API access/,
    );
    expect(apiComposable).toContain("createModelConnection");
    expect(apiComposable).toContain("deleteModelConnection");
    expect(settingsComponent).toContain("Remove API connection?");
    expect(settingsComponent).toContain(
      ":required=\"providerDialect === 'openai_compatible'\"",
    );
  });

  it("loads model profiles before resolving saved fallback preferences", () => {
    const profileLoad = appPage.indexOf("await Promise.allSettled");
    const preferenceLoad = appPage.indexOf("await loadModelPreference()");

    expect(profileLoad).toBeGreaterThan(-1);
    expect(preferenceLoad).toBeGreaterThan(profileLoad);
    expect(appPage).toContain("activeModelReady");
    expect(appPage).toContain("activeModelStatusText");
    expect(appPage).toContain("activeModelDetail");
    expect(appPage).toContain("connectionStatusText");
    expect(composerComponent).not.toContain("modelLabel");
  });

  it("keeps model connection health separate from response stream recovery", () => {
    expect(appPage).toContain("return activeModelStatusText.value");
    expect(appPage).toContain('connectionState.value === "offline"');
    expect(appPage).toContain('return "Offline"');
    expect(appPage).not.toMatch(
      /streamDisconnected\.value[\s\S]{0,160}return "Offline"/,
    );
    expect(appPage).toContain("Reconnect response stream");
    expect(appPage).toContain(
      "`${connectionLabel.value} · ${activeModelDetail.value}`",
    );
  });

  it("uses live runtime readiness for the selected local model", () => {
    expect(apiComposable).toContain("readinessSchema");
    expect(appPage).toContain("ollamaAvailable");
    expect(appPage).toContain("loadRuntimeHealth");
    expect(appPage).toContain("scheduleRuntimeHealthRefresh");
  });

  it("keeps the closed mobile drawer inert and exposes its shortcut", () => {
    expect(sidebarComponent).toContain("mobileSemantics");
    expect(sidebarComponent).toContain(':inert="!open"');
    expect(sidebarComponent).toContain(
      `:aria-hidden="!open ? 'true' : undefined"`,
    );
    expect(sidebarComponent).toContain("function closeHistory()");
    expect(sidebarComponent).toContain('@click.stop="closeHistory"');
    expect(appPage).toContain("workspace--history-collapsed");
    expect(appPage).toContain("shellReady && !historyOpen");
    expect(sidebarComponent).toContain("@keydown.esc.stop");
    expect(sidebarComponent).toContain("Ctrl K");
    expect(sidebarComponent).toContain(">New chat<");
    expect(sidebarComponent).toContain("new-chat__label");
    expect(sidebarComponent).toContain('aria-label="Start new conversation"');
    expect(sidebarComponent).toContain("white-space: nowrap");
    expect(appPage).toContain('event.key.toLowerCase() !== "k"');
    expect(appPage).toContain("closeHistoryOnCompactViewport");
    expect(appPage).toContain('matchMedia("(min-width: 861px)")');
  });

  it("uses top-level v1 run endpoints for durable run follow-up", () => {
    expect(apiComposable).toContain("`/runs/${runId}/`");
    expect(apiComposable).toContain("`/runs/${runId}/cancel/`");
    expect(runStreamComposable).toContain("/runs/${runId}/events/");
    expect(apiComposable).not.toContain("`/chats/runs/${runId}/cancel/`");
    expect(runStreamComposable).not.toContain("/chats/runs/${runId}/events/");
  });

  it("keeps refresh auth separate from workspace loading failures", () => {
    expect(appPage).toContain("await api.me()");
    expect(indexPage).toContain("checkingSession.value = false");
    expect(indexPage).toContain('useRoute().path === "/"');
    expect(appPage).toContain("Promise.allSettled");
    expect(indexPage).toContain(
      "An account with this email already exists. Sign in instead.",
    );
    expect(indexPage).toContain(
      "Too many authentication attempts. Wait a moment, then try again.",
    );
    expect(apiComposable).not.toContain('throw new Error("csrf_failed")');
    expect(apiComposable).toContain("class ApiRequestError");
  });

  it("does not store browser bearer tokens", () => {
    const browserSources = [
      appPage,
      indexPage,
      sidebarComponent,
      settingsComponent,
      composerComponent,
      conversationMessage,
      citationComponent,
      apiComposable,
      runStreamComposable,
    ].join("\n");

    expect(apiComposable).toContain('credentials: "include"');
    expect(apiComposable).toContain('"X-CSRFToken"');
    expect(browserSources).not.toContain("localStorage");
    expect(browserSources).not.toContain("sessionStorage");
    expect(browserSources).not.toContain("Authorization");
    expect(browserSources).not.toContain("Bearer");
    expect(browserSources).not.toContain("access_token");
    expect(browserSources).not.toContain("refresh_token");
  });

  it("prevents saved login credentials from autofilling provider fields", () => {
    expect(settingsComponent).toContain('class="provider-form"');
    expect(settingsComponent).toContain('autocomplete="off"');
    expect(settingsComponent).toContain('name="provider-model-id"');
    expect(settingsComponent).toContain('name="provider-api-key"');
    expect(settingsComponent).toContain('autocomplete="new-password"');
  });

  it("frames Moksha AI as scripture-guided support for difficult moments", () => {
    expect(indexPage).toContain("Bring what feels difficult to carry.");
    expect(indexPage).toContain("scripture library");
    expect(appPage).toContain("What is weighing on your mind?");
  });

  it("uses enter-to-send chat prompt semantics and keeps stop beside input", () => {
    expect(composerComponent).toContain("function handleKeydown");
    expect(composerComponent).toContain('event.key !== "Enter"');
    expect(composerComponent).toContain("event.shiftKey");
    expect(composerComponent).toContain('@keydown="handleKeydown"');
    expect(composerComponent).toContain('aria-label="Stop response"');
    expect(composerComponent).not.toContain("Reconnect");
    expect(appPage).not.toContain(
      'class="message-viewport" aria-live="polite"',
    );
  });

  it("renders exact verse and translation as first-class citation fields", () => {
    expect(citationComponent).toContain("Exact verse");
    expect(citationComponent).toContain("citation.sanskrit_text");
    expect(citationComponent).toContain("citation.translation");
    expect(citationComponent).toContain("Retrieved source passage");
    expect(apiComposable).toContain("sanskrit_text");
    expect(apiComposable).toContain("translation");
  });

  it("keeps assistant bubbles visibly framed in light and dark themes", () => {
    expect(mainCss).toContain(
      "--moksha-assistant-bubble: rgb(255 249 234 / 97%)",
    );
    expect(mainCss).toContain("--moksha-assistant-line: rgb(95 73 43 / 34%)");
    expect(mainCss).toContain(
      "--moksha-assistant-bubble: rgb(245 231 205 / 23%)",
    );
    expect(mainCss).toContain(
      "--moksha-assistant-line: rgb(232 199 150 / 38%)",
    );
    expect(mainCss).toContain("--moksha-assistant-shadow");
    expect(conversationMessage).toContain(
      "message--assistant .message__content",
    );
  });

  it("keeps response error icon aligned instead of growing as message text", () => {
    expect(appPage).toContain('class="response-error__message"');
    expect(appPage).toContain(".response-error__message");
    expect(appPage).not.toContain(".response-error span");
  });
});
