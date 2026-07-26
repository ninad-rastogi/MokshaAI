import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const appPage = readFileSync(resolve(root, "pages/app.vue"), "utf8");

describe("app shell", () => {
  it("keeps theme and model controls inside settings", () => {
    expect(appPage).toContain('aria-label="Theme"');
    expect(appPage).toContain('id="model-profile"');
    expect(appPage).toContain("<h2>Settings</h2>");
    expect(appPage).not.toContain('aria-label="Model profile"');
  });
});
