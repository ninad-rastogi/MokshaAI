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
  it("keeps theme and model controls inside settings", () => {
    expect(appPage).toContain('aria-label="Theme"');
    expect(appPage).toContain('id="model-profile"');
    expect(appPage).toContain("<h2>Settings</h2>");
    expect(appPage).not.toContain('aria-label="Model profile"');
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
    expect(indexPage).toContain("When life feels heavy, ask for guidance.");
    expect(indexPage).toContain("Krishna guiding Arjuna");
    expect(appPage).toContain("Bring what weighs on you.");
  });
});
