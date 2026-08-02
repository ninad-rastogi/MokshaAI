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
const apiComposable = readFileSync(
  resolve(root, "composables/useApi.ts"),
  "utf8",
);
const runStreamComposable = readFileSync(
  resolve(root, "composables/useRunStream.ts"),
  "utf8",
);

describe("app shell", () => {
  it("keeps theme and model controls inside a settings dialog", () => {
    expect(settingsComponent).toContain('aria-label="Theme"');
    expect(settingsComponent).toContain('aria-label="Primary response model"');
    expect(settingsComponent).toContain('id="fallback-model"');
    expect(settingsComponent).toContain("<UModal");
    expect(appPage).toContain("settingsOpen");
    expect(appPage).toContain("saveModelPreference");
    expect(apiComposable).toContain("updateModelPreference");
    expect(appPage).not.toContain('aria-label="Model profile"');
    expect(appPage).not.toContain("Admin default");
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
    expect(appPage).toContain("connectionStatusText");
    expect(composerComponent).not.toContain("modelLabel");
  });

  it("keeps the closed mobile drawer inert and exposes its shortcut", () => {
    expect(sidebarComponent).toContain(':inert="isMobile && !open"');
    expect(sidebarComponent).toContain("function closeHistory()");
    expect(sidebarComponent).toContain('@click.stop="closeHistory"');
    expect(sidebarComponent).toContain("@keydown.esc.stop");
    expect(sidebarComponent).toContain("Ctrl K");
    expect(appPage).toContain('event.key.toLowerCase() !== "k"');
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
    expect(appPage).toContain("Promise.allSettled");
    expect(indexPage).toContain(
      "An account with this email already exists. Sign in instead.",
    );
    expect(apiComposable).toContain("class ApiRequestError");
  });

  it("frames Moksha AI as scripture-guided support for difficult moments", () => {
    expect(indexPage).toContain("Bring what feels difficult to carry.");
    expect(indexPage).toContain("scripture library");
    expect(appPage).toContain("What is weighing on your mind?");
  });

  it("uses enter-to-send chat prompt semantics and keeps stop beside input", () => {
    expect(composerComponent).toContain(':submit-on-enter="true"');
    expect(composerComponent).toContain('aria-label="Stop response"');
    expect(composerComponent).not.toContain("Reconnect");
    expect(appPage).not.toContain(
      'class="message-viewport" aria-live="polite"',
    );
  });
});
