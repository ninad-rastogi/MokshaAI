import DOMPurify from "dompurify";
import { marked } from "marked";

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
    return DOMPurify.sanitize(html, {
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
    });
  }

  return { renderMarkdown };
}
