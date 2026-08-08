import { z } from "zod";
import type { Citation } from "~/types/api";

export type RunEvent =
  | { type: "state"; id: string; state: string }
  | { type: "delta"; id: string; text: string }
  | { type: "citation"; id: string; citation: Citation }
  | { type: "usage"; id: string; usage: Record<string, unknown> }
  | { type: "error"; id: string; code: string; message: string }
  | { type: "done"; id: string; state: string };

type RunStreamHandlers = {
  onEvent: (event: RunEvent) => void;
  onOpen?: () => void;
  onDisconnect?: () => void;
};

const runStateSchema = z.enum([
  "queued",
  "running",
  "completed",
  "failed",
  "cancelled",
]);

const citationSchema = z.object({
  scripture: z.string(),
  page: z.union([z.number(), z.string()]),
  file_name: z.string(),
  score: z.number(),
  excerpt: z.string(),
  source_text: z.string().optional(),
  verse_text: z.string().optional(),
  sanskrit_text: z.string().optional(),
  translation: z.string().optional(),
});

const eventSchemas = {
  state: z.object({ state: runStateSchema }),
  delta: z.object({ text: z.string() }),
  citation: citationSchema,
  usage: z.record(z.unknown()),
  error: z.object({ code: z.string(), message: z.string() }),
  done: z.object({ state: runStateSchema }),
} satisfies Record<RunEvent["type"], z.ZodTypeAny>;

export function parseRunEvent(
  type: RunEvent["type"],
  id: string,
  dataText: string,
): RunEvent {
  const data: unknown = JSON.parse(dataText);
  switch (type) {
    case "state": {
      const parsed = eventSchemas.state.parse(data);
      return { type, id, state: parsed.state };
    }
    case "delta": {
      const parsed = eventSchemas.delta.parse(data);
      return { type, id, text: parsed.text };
    }
    case "citation": {
      const parsed = eventSchemas.citation.parse(data);
      return { type, id, citation: parsed };
    }
    case "usage": {
      const parsed = eventSchemas.usage.parse(data);
      return { type, id, usage: parsed };
    }
    case "error": {
      const parsed = eventSchemas.error.parse(data);
      return { type, id, code: parsed.code, message: parsed.message };
    }
    case "done": {
      const parsed = eventSchemas.done.parse(data);
      return { type, id, state: parsed.state };
    }
  }
}

export function useRunStream() {
  const config = useRuntimeConfig();
  let source: EventSource | null = null;
  let lastEventId = "";
  let currentRunId = "";

  function connect(runId: string, handlers: RunStreamHandlers) {
    close(false);
    if (currentRunId !== runId) {
      currentRunId = runId;
      lastEventId = "";
    }
    const query = lastEventId
      ? `?last_event_id=${encodeURIComponent(lastEventId)}`
      : "";
    source = new EventSource(
      `${config.public.apiBase}/runs/${runId}/events/${query}`,
      {
        withCredentials: true,
      },
    );
    source.onopen = () => handlers.onOpen?.();
    source.onerror = () => handlers.onDisconnect?.();

    const parse = (event: MessageEvent, type: RunEvent["type"]) => {
      try {
        const eventId = event.lastEventId || lastEventId;
        const parsed = parseRunEvent(type, eventId, event.data);
        lastEventId = parsed.id || lastEventId;
        handlers.onEvent(parsed);
      } catch {
        handlers.onEvent({
          type: "error",
          id: lastEventId,
          code: "invalid_sse_event",
          message: "Response stream sent an invalid event.",
        });
        close(false);
        handlers.onDisconnect?.();
      }
    };

    for (const type of [
      "state",
      "delta",
      "citation",
      "usage",
      "error",
      "done",
    ] as const) {
      source.addEventListener(type, (event) =>
        parse(event as MessageEvent, type),
      );
    }
  }

  function close(reset = true) {
    source?.close();
    source = null;
    if (reset) {
      currentRunId = "";
      lastEventId = "";
    }
  }

  return { connect, close };
}
