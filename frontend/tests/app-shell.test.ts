import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const appPage = readFileSync(resolve(root, "pages/app.vue"), "utf8");
const indexPage = readFileSync(resolve(root, "pages/index.vue"), "utf8");
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
    expect(appPage).toContain('aria-label="Theme"');
    expect(appPage).toContain('id="model-profile"');
    expect(appPage).toContain('role="dialog"');
    expect(appPage).toContain("settingsOpen");
    expect(appPage).not.toContain('aria-label="Model profile"');
  });

  it("exposes production chat history actions", () => {
    expect(appPage).toContain("Search conversations");
    expect(appPage).toContain("Rename");
    expect(appPage).toContain("Archive");
    expect(appPage).toContain("Delete");
    expect(apiComposable).toContain("renameChat");
    expect(apiComposable).toContain("deleteChat");
    expect(apiComposable).toContain("archiveChat");
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
    expect(indexPage).toContain("Account already exists. Sign in instead.");
    expect(apiComposable).toContain("class ApiRequestError");
  });

  it("frames Moksha AI as scripture-guided support for difficult moments", () => {
    expect(indexPage).toContain("A quieter place for hard moments.");
    expect(indexPage).toContain("expand the library as your study deepens");
    expect(appPage).toContain("Bring the question you cannot carry alone.");
  });
});
