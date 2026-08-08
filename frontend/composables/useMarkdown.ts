import DOMPurify from "dompurify";
import { marked } from "marked";

const allowedHrefProtocols = ["http:", "https:", "mailto:"];

function escapeHtml(value: string) {
  return value.replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;",
      })[character] || character,
  );
}

function isSafeHref(value: string) {
  const trimmed = value.trim();
  if (trimmed.startsWith("/") || trimmed.startsWith("#")) return true;
  try {
    return allowedHrefProtocols.includes(new URL(trimmed).protocol);
  } catch {
    return false;
  }
}

function sanitizeWithoutDom(html: string) {
  return html
    .replace(/\s(?:on[a-z]+|style)=(".*?"|'.*?'|[^\s>]+)/gi, "")
    .replace(/\shref=(".*?"|'.*?'|[^\s>]+)/gi, (attribute) => {
      const raw = attribute
        .replace(/^\shref=/i, "")
        .replace(/^['"]|['"]$/g, "");
      return isSafeHref(raw) ? attribute : "";
    })
    .replace(/\b(?:javascript|vbscript|data):/gi, "");
}

function sanitizeHtml(html: string) {
  const purifier = DOMPurify as unknown as {
    sanitize?: (source: string, config: Record<string, unknown>) => string;
  };
  if (typeof purifier.sanitize !== "function") {
    return sanitizeWithoutDom(html);
  }
  return sanitizeWithoutDom(
    purifier.sanitize(html, {
      USE_PROFILES: { html: true },
      ALLOWED_TAGS: [
        "a",
        "blockquote",
        "br",
        "code",
        "del",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "li",
        "ol",
        "p",
        "pre",
        "strong",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
      ],
      ALLOWED_ATTR: ["href", "title"],
      FORBID_ATTR: ["style", "onerror", "onload"],
    }),
  );
}

marked.use({
  async: false,
  gfm: true,
  breaks: true,
  renderer: {
    html({ text }) {
      return escapeHtml(text);
    },
  },
});

export function useMarkdown() {
  function renderMarkdown(markdown: string): string {
    const html = marked.parse(markdown, { async: false }) as string;
    return sanitizeHtml(html);
  }

  return { renderMarkdown };
}
