"use client";

/**
 * components/ReasoningLog.tsx
 * ─────────────────────────────────────────────────────────────
 * Displays the agent's internal reasoning process in real-time.
 *
 * Shows two types of events interleaved in chronological order:
 *   - ThinkingEvent  → a text log line with agent badge
 *   - ToolCallEvent  → an expandable card showing tool name + params + result
 *
 * Props:
 *   thinkingSteps  — array of ThinkingEvent accumulated from SSE stream
 *   toolCalls      — array of ToolCallEvent accumulated from SSE stream
 *   isStreaming    — true while the SSE connection is open
 */

import { useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { ThinkingEvent, ToolCallEvent, AgentName } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────

// We merge both event types into a single timeline list
type LogEntry =
  | { kind: "thinking"; timestamp: number; data: ThinkingEvent }
  | { kind: "tool_call"; timestamp: number; data: ToolCallEvent };

interface ReasoningLogProps {
  thinkingSteps: ThinkingEvent[];
  toolCalls: ToolCallEvent[];
  isStreaming: boolean;
}

// ── Agent color map ───────────────────────────────────────────

const AGENT_STYLES: Record<
  AgentName,
  { badge: string; dot: string; label: string }
> = {
  planner: {
    badge: "bg-violet-100 text-violet-700 border-violet-200",
    dot: "bg-violet-400",
    label: "Planner",
  },
  researcher: {
    badge: "bg-blue-100 text-blue-700 border-blue-200",
    dot: "bg-blue-400",
    label: "Researcher",
  },
  analyst: {
    badge: "bg-amber-100 text-amber-700 border-amber-200",
    dot: "bg-amber-400",
    label: "Analyst",
  },
  writer: {
    badge: "bg-emerald-100 text-emerald-700 border-emerald-200",
    dot: "bg-emerald-400",
    label: "Writer",
  },
};

const TOOL_STYLES: Record<string, { icon: string; color: string }> = {
  tavily_search: { icon: "⚡", color: "text-blue-600" },
  pdf_reader: { icon: "📄", color: "text-orange-600" },
  exa_search: { icon: "🔍", color: "text-purple-600" },
};

// ── Tool call status badge ────────────────────────────────────

function StatusBadge({ status }: { status: ToolCallEvent["status"] }) {
  const styles = {
    running: "bg-blue-50 text-blue-600 border-blue-200 animate-pulse",
    done: "bg-emerald-50 text-emerald-600 border-emerald-200",
    error: "bg-red-50 text-red-600 border-red-200",
  };
  const labels = { running: "Running...", done: "Done", error: "Error" };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${styles[status]}`}
    >
      {labels[status]}
    </span>
  );
}

// ── Single thinking step ──────────────────────────────────────

function ThinkingStep({ event }: { event: ThinkingEvent }) {
  const style = AGENT_STYLES[event.agent] ?? AGENT_STYLES.planner;

  return (
    <div className="flex items-start gap-3 py-2">
      {/* Timeline dot */}
      <div className="mt-1.5 flex-shrink-0">
        <div className={`w-2 h-2 rounded-full ${style.dot}`} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${style.badge}`}
          >
            {style.label}
          </span>
        </div>
        <p className="text-sm text-slate-600 leading-relaxed break-words">
          {event.content}
        </p>
      </div>
    </div>
  );
}

// ── Single tool call card ─────────────────────────────────────

function ToolCallCard({ event }: { event: ToolCallEvent }) {
  const toolStyle = TOOL_STYLES[event.tool] ?? {
    icon: "🔧",
    color: "text-slate-600",
  };

  return (
    <div className="py-2">
      <Card className="border border-slate-200 bg-slate-50 overflow-hidden">
        {/* Header row */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <span className="text-base">{toolStyle.icon}</span>
            <span
              className={`text-sm font-mono font-medium ${toolStyle.color}`}
            >
              {event.tool}()
            </span>
          </div>
          <StatusBadge status={event.status} />
        </div>

        {/* Params block */}
        <div className="px-3 py-2">
          <p className="text-xs text-slate-400 uppercase tracking-wide mb-1 font-medium">
            Parameters
          </p>
          <pre
            className="text-xs text-slate-600 font-mono whitespace-pre-wrap break-all 
               bg-white rounded border border-slate-100 px-2 py-1.5 overflow-x-hidden"
          >
            {JSON.stringify(event.params, null, 2)}
          </pre>
        </div>

        {/* Result preview (only when done or error) */}
        {event.result_preview && (
          <div className="px-3 pb-2">
            <p className="text-xs text-slate-400 uppercase tracking-wide mb-1 font-medium">
              Result
            </p>
            <p className="text-xs text-slate-600 bg-white rounded border border-slate-100 px-2 py-1.5">
              {event.result_preview}
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}

// ── Streaming indicator ───────────────────────────────────────

function StreamingIndicator() {
  return (
    <div className="flex items-center gap-2 py-2">
      <div className="flex gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:0ms]" />
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:150ms]" />
        <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:300ms]" />
      </div>
      <span className="text-xs text-slate-400">Agents working...</span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────

export function ReasoningLog({
  thinkingSteps,
  toolCalls,
  isStreaming,
}: ReasoningLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const isEmpty = thinkingSteps.length === 0 && toolCalls.length === 0;
  const activeAgent =
    thinkingSteps.length > 0
      ? thinkingSteps[thinkingSteps.length - 1].agent
      : null;
  const style = activeAgent ? AGENT_STYLES[activeAgent] : null;

  useEffect(() => {
    const viewport = scrollRef.current?.querySelector(
      "[data-radix-scroll-area-viewport]",
    );
    if (viewport) {
      const isAtBottom =
        viewport.scrollHeight - viewport.scrollTop <=
        viewport.clientHeight + 100;

      if (isAtBottom) {
        viewport.scrollTo({
          top: viewport.scrollHeight,
          behavior: "smooth",
        });
      }
    }
  }, [thinkingSteps.length, toolCalls.length]);

  // Merge thinking steps and tool calls into a single timeline.
  // We use array index as a stable timestamp proxy since both
  // arrays are append-only and received in chronological order.
  const timeline: LogEntry[] = [
    ...thinkingSteps.map((data, i) => ({
      kind: "thinking" as const,
      // Space out thinking events so tool calls interleave correctly.
      // Thinking steps are emitted before their corresponding tool_call,
      // so we give them a slightly earlier virtual timestamp.
      timestamp: i * 10,
      data,
    })),
    ...toolCalls.map((data, i) => ({
      kind: "tool_call" as const,
      timestamp: i * 10 + 5,
      data,
    })),
  ].sort((a, b) => a.timestamp - b.timestamp);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-2 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
        <span className="text-xs font-medium text-slate-500">
          Current Phase:
        </span>
        {activeAgent ? (
          <Badge className={`${style?.badge} animate-pulse`}>
            {style?.label.toUpperCase()}
          </Badge>
        ) : (
          <span className="text-xs text-slate-400 italic">Waiting...</span>
        )}
      </div>
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-700">
            Reasoning Log
          </span>
          {isStreaming && (
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          )}
        </div>
        <span className="text-xs text-slate-400">
          {thinkingSteps.length + toolCalls.length} events
        </span>
      </div>

      {/* Agent legend */}
      {!isEmpty && (
        <>
          <div className="flex flex-wrap gap-1.5 px-4 py-2 border-b border-slate-100">
            {(
              Object.entries(AGENT_STYLES) as [
                AgentName,
                (typeof AGENT_STYLES)[AgentName],
              ][]
            ).map(([key, style]) => (
              <span
                key={key}
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border ${style.badge}`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
                {style.label}
              </span>
            ))}
          </div>
          <Separator />
        </>
      )}

      {/* Timeline */}
      <ScrollArea className="flex-1 px-4">
        {isEmpty && !isStreaming ? (
          // Empty state
          <div className="flex flex-col items-center justify-center h-40 gap-2">
            <span className="text-2xl">🔍</span>
            <p className="text-sm text-slate-400 text-center">
              Submit a query to see the agents reasoning process here.
            </p>
          </div>
        ) : (
          <div className="py-2 space-y-0.5">
            {timeline.map((entry, idx) => (
              <div key={idx}>
                {entry.kind === "thinking" ? (
                  <ThinkingStep event={entry.data} />
                ) : (
                  <ToolCallCard event={entry.data} />
                )}
                {/* Light separator between entries */}
                {idx < timeline.length - 1 && (
                  <div className="ml-5 border-l border-slate-100 h-2" />
                )}
              </div>
            ))}

            {/* Live streaming indicator */}
            {isStreaming && <StreamingIndicator />}

            {/* Auto-scroll anchor */}
            <div ref={bottomRef} />
          </div>
        )}
      </ScrollArea>
    </div>
  );
}

// export function ReasoningLog({
//   thinkingSteps,
//   toolCalls,
//   isStreaming,
// }: ReasoningLogProps) {
//   const bottomRef = useRef<HTMLDivElement>(null);
//   const isEmpty = thinkingSteps.length === 0 && toolCalls.length === 0;

//   // Auto-scroll to bottom as new events arrive
//   useEffect(() => {
//     bottomRef.current?.scrollIntoView({ behavior: "smooth" });
//   }, [thinkingSteps.length, toolCalls.length]);

//   // Merge thinking steps and tool calls into a single timeline.
//   // We use array index as a stable timestamp proxy since both
//   // arrays are append-only and received in chronological order.
//   const timeline: LogEntry[] = [
//     ...thinkingSteps.map((data, i) => ({
//       kind: "thinking" as const,
//       // Space out thinking events so tool calls interleave correctly.
//       // Thinking steps are emitted before their corresponding tool_call,
//       // so we give them a slightly earlier virtual timestamp.
//       timestamp: i * 10,
//       data,
//     })),
//     ...toolCalls.map((data, i) => ({
//       kind: "tool_call" as const,
//       timestamp: i * 10 + 5,
//       data,
//     })),
//   ].sort((a, b) => a.timestamp - b.timestamp);

//   return (
//     <div className="flex flex-col h-full">
//       {/* Header */}
//       <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
//         <div className="flex items-center gap-2">
//           <span className="text-sm font-semibold text-slate-700">
//             Reasoning Log
//           </span>
//           {isStreaming && (
//             <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
//           )}
//         </div>
//         <span className="text-xs text-slate-400">
//           {thinkingSteps.length + toolCalls.length} events
//         </span>
//       </div>

//       {/* Agent legend */}
//       {!isEmpty && (
//         <>
//           <div className="flex flex-wrap gap-1.5 px-4 py-2 border-b border-slate-100">
//             {(
//               Object.entries(AGENT_STYLES) as [
//                 AgentName,
//                 (typeof AGENT_STYLES)[AgentName],
//               ][]
//             ).map(([key, style]) => (
//               <span
//                 key={key}
//                 className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs border ${style.badge}`}
//               >
//                 <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
//                 {style.label}
//               </span>
//             ))}
//           </div>
//           <Separator />
//         </>
//       )}

//       {/* Timeline */}
//       <ScrollArea className="flex-1 px-4">
//         {isEmpty && !isStreaming ? (
//           // Empty state
//           <div className="flex flex-col items-center justify-center h-40 gap-2">
//             <span className="text-2xl">🔍</span>
//             <p className="text-sm text-slate-400 text-center">
//               Submit a query to see the agents reasoning process here.
//             </p>
//           </div>
//         ) : (
//           <div className="py-2 space-y-0.5">
//             {timeline.map((entry, idx) => (
//               <div key={idx}>
//                 {entry.kind === "thinking" ? (
//                   <ThinkingStep event={entry.data} />
//                 ) : (
//                   <ToolCallCard event={entry.data} />
//                 )}
//                 {/* Light separator between entries */}
//                 {idx < timeline.length - 1 && (
//                   <div className="ml-5 border-l border-slate-100 h-2" />
//                 )}
//               </div>
//             ))}

//             {/* Live streaming indicator */}
//             {isStreaming && <StreamingIndicator />}

//             {/* Auto-scroll anchor */}
//             <div ref={bottomRef} />
//           </div>
//         )}
//       </ScrollArea>
//     </div>
//   );
// }
