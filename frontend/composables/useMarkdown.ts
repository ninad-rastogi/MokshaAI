import DOMPurify from "dompurify";
import { marked } from "marked";

marked.use({ async: false, gfm: true, breaks: true });

export function useMarkdown() {
  function renderMarkdown(markdown: string): string {
    const html = marked.parse(markdown, { async: false }) as string;
    return DOMPurify.sanitize(html, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ["script", "style", "iframe", "object", "embed"],
      FORBID_ATTR: ["style", "onerror", "onload"],
    });
  }

  return { renderMarkdown };
}
