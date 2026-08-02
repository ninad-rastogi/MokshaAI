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
      lastEventId = event.lastEventId || lastEventId;
      const data = JSON.parse(event.data);
      if (type === "state")
        handlers.onEvent({ type, id: lastEventId, state: data.state });
      if (type === "delta")
        handlers.onEvent({ type, id: lastEventId, text: data.text });
      if (type === "citation")
        handlers.onEvent({
          type,
          id: lastEventId,
          citation: data as Citation,
        });
      if (type === "usage")
        handlers.onEvent({ type, id: lastEventId, usage: data });
      if (type === "error")
        handlers.onEvent({
          type,
          id: lastEventId,
          code: data.code,
          message: data.message,
        });
      if (type === "done")
        handlers.onEvent({ type, id: lastEventId, state: data.state });
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
