import type { Citation } from "~/types/api";

export type RunEvent =
  | { type: "state"; id: string; state: string }
  | { type: "delta"; id: string; text: string }
  | { type: "citation"; id: string; citation: Citation }
  | { type: "usage"; id: string; usage: Record<string, unknown> }
  | { type: "error"; id: string; code: string; message: string }
  | { type: "done"; id: string; state: string };

export function useRunStream() {
  const config = useRuntimeConfig();
  let source: EventSource | null = null;
  let lastEventId = "";

  function connect(runId: string, onEvent: (event: RunEvent) => void) {
    close();
    const query = lastEventId
      ? `?last_event_id=${encodeURIComponent(lastEventId)}`
      : "";
    source = new EventSource(
      `${config.public.apiBase}/runs/${runId}/events/${query}`,
      {
        withCredentials: true,
      },
    );

    const parse = (event: MessageEvent, type: RunEvent["type"]) => {
      lastEventId = event.lastEventId || lastEventId;
      const data = JSON.parse(event.data);
      if (type === "state")
        onEvent({ type, id: lastEventId, state: data.state });
      if (type === "delta") onEvent({ type, id: lastEventId, text: data.text });
      if (type === "citation")
        onEvent({ type, id: lastEventId, citation: data as Citation });
      if (type === "usage") onEvent({ type, id: lastEventId, usage: data });
      if (type === "error")
        onEvent({
          type,
          id: lastEventId,
          code: data.code,
          message: data.message,
        });
      if (type === "done")
        onEvent({ type, id: lastEventId, state: data.state });
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

  function close() {
    source?.close();
    source = null;
  }

  return { connect, close };
}
