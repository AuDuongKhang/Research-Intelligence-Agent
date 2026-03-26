/**
 * stream-parser.ts
 * ─────────────────────────────────────────────────────────────
 * Reads the SSE stream from FastAPI and dispatches typed events
 * to the appropriate React state updaters.
 *
 * Usage (inside a React component or hook):
 *
 *   await parseResearchStream(response, {
 *     onThinking: (e) => setThinkingSteps(prev => [...prev, e]),
 *     onToolCall: (e) => setToolCalls(prev => [...prev, e]),
 *     onResultChunk: (text) => setReport(prev => prev + text),
 *     onArtifact: (e) => setArtifacts(prev => [...prev, e]),
 *     onError: (msg) => setError(msg),
 *     onDone: () => setIsLoading(false),
 *   });
 */

import type {
  SSEEvent,
  ThinkingEvent,
  ToolCallEvent,
  ArtifactEvent,
} from "./types";

// ── Callback interface ────────────────────────────────────────

export interface StreamCallbacks {
  /** Called every time an agent emits a thinking step */
  onThinking?: (event: ThinkingEvent) => void;

  /** Called when a tool call starts (status=running) or finishes (status=done|error) */
  onToolCall?: (event: ToolCallEvent) => void;

  /** Called for each streamed text chunk of the final report */
  onResultChunk?: (text: string, isFinal: boolean) => void;

  /** Called when the analyst emits a citation list or chart artifact */
  onArtifact?: (event: ArtifactEvent) => void;

  /** Called if the backend emits an error event */
  onError?: (message: string) => void;

  /** Called once when the stream closes cleanly */
  onDone?: () => void;
}

// ── Main parser ───────────────────────────────────────────────

/**
 * Consumes a ReadableStream (from fetch response.body) and fires
 * the appropriate callback for each SSE event received.
 */
export async function parseResearchStream(
  response: Response,
  callbacks: StreamCallbacks,
): Promise<void> {
  if (!response.ok) {
    callbacks.onError?.(`HTTP ${response.status}: ${response.statusText}`);
    callbacks.onDone?.();
    return;
  }

  if (!response.body) {
    callbacks.onError?.("Response body is empty");
    callbacks.onDone?.();
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      // Decode the incoming bytes and accumulate into buffer
      // (a single chunk may contain multiple SSE lines or a partial line)
      buffer += decoder.decode(value, { stream: true });

      // SSE lines are separated by "\n\n"
      const lines = buffer.split("\n\n");

      // The last element may be an incomplete line — keep it in the buffer
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed.startsWith("data: ")) continue;

        const jsonStr = trimmed.slice(6); // strip "data: " prefix
        if (!jsonStr) continue;

        try {
          const event = JSON.parse(jsonStr) as SSEEvent;
          dispatch(event, callbacks);
        } catch {
          // Malformed JSON from backend — log and continue
          console.warn("[stream-parser] Failed to parse SSE event:", jsonStr);
        }
      }
    }
  } catch (err) {
    callbacks.onError?.(`Stream read error: ${String(err)}`);
  } finally {
    reader.releaseLock();
    callbacks.onDone?.();
  }
}

// ── Dispatcher ────────────────────────────────────────────────

function dispatch(event: SSEEvent, callbacks: StreamCallbacks): void {
  switch (event.type) {
    case "thinking":
      callbacks.onThinking?.(event);
      break;

    case "tool_call":
      callbacks.onToolCall?.(event);
      break;

    case "result":
      callbacks.onResultChunk?.(event.content, event.is_final);
      break;

    case "artifact":
      callbacks.onArtifact?.(event);
      break;

    case "error":
      callbacks.onError?.(event.message);
      break;

    default:
      console.warn(
        "[stream-parser] Unknown event type:",
        (event as SSEEvent).type,
      );
  }
}

// ── Convenience: POST helper ──────────────────────────────────

/**
 * Sends the research query to the Next.js route handler and
 * starts parsing the stream.
 *
 * This is what your ChatPanel calls on form submit:
 *
 *   await streamResearch("What is quantum computing?", {
 *     onThinking: ...,
 *     onResultChunk: ...,
 *   });
 */
export async function streamResearch(
  query: string,
  callbacks: StreamCallbacks,
): Promise<void> {
  let response: Response;

  try {
    response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
  } catch (err) {
    callbacks.onError?.(`Network error: ${String(err)}`);
    callbacks.onDone?.();
    return;
  }

  await parseResearchStream(response, callbacks);
}
