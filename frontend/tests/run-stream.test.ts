import { describe, expect, it } from "vitest";

import { parseRunEvent } from "../composables/useRunStream";

describe("run stream parser", () => {
  it("accepts typed state, delta, citation, usage, error, and done events", () => {
    expect(parseRunEvent("state", "1-0", '{"state":"running"}')).toEqual({
      type: "state",
      id: "1-0",
      state: "running",
    });
    expect(parseRunEvent("delta", "2-0", '{"text":"Hello"}')).toEqual({
      type: "delta",
      id: "2-0",
      text: "Hello",
    });
    expect(
      parseRunEvent(
        "citation",
        "3-0",
        JSON.stringify({
          scripture: "Katha Upanishad",
          page: 42,
          file_name: "katha-upanishad.pdf",
          score: 0.91,
          excerpt: "उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।",
          sanskrit_text: "उत्तिष्ठत जाग्रत प्राप्य वरान्निबोधत।",
          translation: "Arise, awake, and learn from the wise.",
        }),
      ),
    ).toMatchObject({
      type: "citation",
      id: "3-0",
      citation: {
        scripture: "Katha Upanishad",
        file_name: "katha-upanishad.pdf",
        translation: "Arise, awake, and learn from the wise.",
      },
    });
    expect(parseRunEvent("usage", "4-0", '{"total_tokens":9}')).toEqual({
      type: "usage",
      id: "4-0",
      usage: { total_tokens: 9 },
    });
    expect(
      parseRunEvent(
        "error",
        "5-0",
        '{"code":"rate_limited","message":"Retry later."}',
      ),
    ).toEqual({
      type: "error",
      id: "5-0",
      code: "rate_limited",
      message: "Retry later.",
    });
    expect(parseRunEvent("done", "6-0", '{"state":"completed"}')).toEqual({
      type: "done",
      id: "6-0",
      state: "completed",
    });
  });

  it("rejects malformed or unknown stream payloads", () => {
    expect(() =>
      parseRunEvent("state", "1-0", '{"state":"thinking"}'),
    ).toThrow();
    expect(() => parseRunEvent("delta", "2-0", '{"text":42}')).toThrow();
    expect(() =>
      parseRunEvent("citation", "3-0", '{"scripture":"Only"}'),
    ).toThrow();
  });
});
