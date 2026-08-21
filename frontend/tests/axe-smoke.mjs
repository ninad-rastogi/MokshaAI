import AxeBuilder from "@axe-core/playwright";
import { chromium } from "playwright";

const baseUrl = process.env.MOKSHA_FRONTEND_BASE_URL || "http://127.0.0.1:8450";

const now = "2026-08-02T12:00:00Z";
const chat = {
  id: "chat-axe",
  name: "Finding steadiness under pressure",
  is_archived: false,
  created_at: now,
  updated_at: now,
  message_count: 2,
};
const user = {
  id: 1,
  email: "axe@example.com",
  spiritual_name: "Ninad",
  preferred_theme: "system",
  created_at: now,
};
const localProfile = {
  id: "model-local",
  name: "Moksha local",
  model_id: "qwen3:4b",
  connection: null,
  connection_status: "connected",
  connection_dialect: "builtin_ollama",
  is_enabled: true,
  is_admin_default: true,
  context_window: 8192,
  max_output_tokens: 1024,
  temperature: 0.2,
};

function fulfill(route, payload, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  });
}

async function installMockApi(page) {
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();

    if (path.endsWith("/auth/csrf/")) {
      await fulfill(route, { csrfToken: "mock-csrf" });
    } else if (path.endsWith("/auth/ready/")) {
      await fulfill(route, {
        status: "ready",
        database: true,
        redis: true,
        ollama: true,
        embedding: true,
        disk: true,
      });
    } else if (path.endsWith("/auth/me/")) {
      await fulfill(route, user);
    } else if (path.endsWith("/auth/session/")) {
      await fulfill(route, { authenticated: true, user });
    } else if (path.endsWith("/chats/") && method === "GET") {
      await fulfill(route, { next: null, previous: null, results: [chat] });
    } else if (path.endsWith("/messages/")) {
      await fulfill(route, {
        next: null,
        previous: null,
        results: [
          {
            id: 1,
            role: "user",
            content: "I feel pulled in too many directions.",
            mode: "",
            sources: [],
            created_at: now,
          },
          {
            id: 2,
            role: "assistant",
            content:
              "Begin with the next honest duty and keep the outcome light.",
            mode: "grounded",
            sources: [],
            created_at: now,
          },
        ],
      });
    } else if (path.endsWith("/models/profiles/")) {
      await fulfill(route, {
        next: null,
        previous: null,
        results: [localProfile],
      });
    } else if (path.endsWith("/models/preferences/me/")) {
      await fulfill(route, {
        primary_profile: localProfile.id,
        primary_profile_detail: localProfile,
        ordered_fallback_profile_ids: [],
        updated_at: now,
      });
    } else if (path.endsWith("/scriptures/")) {
      await fulfill(route, { next: null, previous: null, results: [] });
    } else if (path.endsWith("/auth/session/logout/")) {
      await route.fulfill({ status: 204, body: "" });
    } else if (path.endsWith("/auth/session/login/")) {
      await fulfill(route, user);
    } else if (path.endsWith("/auth/register/")) {
      await fulfill(route, user, 201);
    } else {
      await fulfill(route, { detail: `Unhandled ${method} ${path}` }, 404);
    }
  });
}

async function scan(page, label) {
  const result = await new AxeBuilder({ page })
    .exclude("[data-allow-a11y-warning]")
    .analyze();
  if (result.violations.length) {
    const summary = result.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      description: violation.description,
      nodes: violation.nodes.map((node) => node.target),
    }));
    throw new Error(
      `${label} axe violations:\n${JSON.stringify(summary, null, 2)}`,
    );
  }
  console.log(`${label}: axe clean`);
}

const launchOptions = {
  headless: true,
  args: ["--disable-extensions", "--ignore-certificate-errors"],
};
if (process.env.PLAYWRIGHT_CHANNEL) {
  launchOptions.channel = process.env.PLAYWRIGHT_CHANNEL;
}

async function launchBrowser() {
  try {
    return await chromium.launch(launchOptions);
  } catch (error) {
    if (process.env.PLAYWRIGHT_CHANNEL) throw error;
    if (!String(error).includes("Executable doesn't exist")) throw error;
    return chromium.launch({ ...launchOptions, channel: "chrome" });
  }
}

const browser = await launchBrowser();
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
});
const page = await context.newPage();
await installMockApi(page);

try {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await scan(page, "auth");

  await page.goto(`${baseUrl}/app`, { waitUntil: "networkidle" });
  await page.getByLabel("Message Moksha AI").waitFor();
  await scan(page, "app desktop");

  await page.locator(".desktop-settings").click();
  await page.locator(".settings-dialog").waitFor();
  await scan(page, "settings");

  await page.keyboard.press("Escape");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: "networkidle" });
  await scan(page, "app mobile");
} finally {
  await context.close();
  await browser.close();
}
