import { describe, expect, it } from "vitest";

import { useMarkdown } from "../composables/useMarkdown";

describe("markdown renderer", () => {
  it("escapes raw HTML while preserving safe markdown formatting", () => {
    const { renderMarkdown } = useMarkdown();
    const html = renderMarkdown(
      [
        "**steady** guidance",
        "",
        '<img src=x onerror="alert(1)">',
        '<script>alert("bad")</script>',
        "[source](javascript:alert(1))",
      ].join("\n"),
    );

    expect(html).toContain("<strong>steady</strong>");
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<script");
    expect(html).not.toContain("onerror");
    expect(html).not.toContain("javascript:");
    expect(html).toContain("&lt;img");
    expect(html).toContain("&lt;script");
  });
});
