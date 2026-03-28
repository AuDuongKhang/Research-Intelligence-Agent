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
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { ToolCallCard } from "./ToolCallCard";
import type { ThinkingEvent, ToolCallEvent, AgentName } from "@/lib/types";

type LogEntry =
  | { kind: "thinking"; timestamp: number; data: ThinkingEvent }
  | { kind: "tool_call"; timestamp: number; data: ToolCallEvent };

interface ReasoningLogProps {
  thinkingSteps: ThinkingEvent[];
  toolCalls: ToolCallEvent[];
  isStreaming: boolean;
}

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

function ThinkingStep({ event }: { event: ThinkingEvent }) {
  const style = AGENT_STYLES[event.agent] ?? AGENT_STYLES.planner;
  return (
    <div className="flex items-start gap-3 py-2 animate-in fade-in slide-in-from-left-2 duration-300">
      <div className="mt-2 flex-shrink-0 w-1.5 h-1.5 rounded-full bg-slate-300" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <Badge
            variant="outline"
            className={`text-[10px] font-bold ${style.badge}`}
          >
            {style.label}
          </Badge>
        </div>
        <p className="text-sm text-slate-600 leading-relaxed break-words whitespace-pre-wrap">
          {event.content}
        </p>
      </div>
    </div>
  );
}

export function ReasoningLog({
  thinkingSteps,
  toolCalls,
  isStreaming,
}: ReasoningLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeAgent =
    thinkingSteps.length > 0
      ? thinkingSteps[thinkingSteps.length - 1].agent
      : null;

  useEffect(() => {
    const viewport = scrollRef.current?.querySelector(
      "[data-radix-scroll-area-viewport]",
    );
    if (viewport) {
      const isAtBottom =
        viewport.scrollHeight - viewport.scrollTop <=
        viewport.clientHeight + 150;
      if (isAtBottom) {
        viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" });
      }
    }
  }, [thinkingSteps.length, toolCalls.length]);

  const timeline: LogEntry[] = [
    ...thinkingSteps.map((data, i) => ({
      kind: "thinking" as const,
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
    <div className="flex flex-col h-full bg-white overflow-hidden">
      {/* Current Status Header */}
      <div className="px-4 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
            Active Phase
          </span>
          {isStreaming && (
            <span className="flex h-2 w-2 rounded-full bg-blue-500 animate-ping" />
          )}
        </div>
        {activeAgent ? (
          <div className="flex items-center gap-2">
            <div
              className={`w-2 h-2 rounded-full ${AGENT_STYLES[activeAgent].dot}`}
            />
            <span className="text-sm font-bold text-slate-700 uppercase italic">
              Agent {activeAgent} is working...
            </span>
          </div>
        ) : (
          <span className="text-xs text-slate-400 italic">Standing by</span>
        )}
      </div>

      {/* Main Log Area */}
      <ScrollArea ref={scrollRef} className="flex-1 min-h-0 px-4">
        <div className="py-4 space-y-1">
          {timeline.map((entry, idx) => (
            <div key={idx}>
              {entry.kind === "thinking" ? (
                <ThinkingStep event={entry.data} />
              ) : (
                <ToolCallCard event={entry.data} />
              )}
            </div>
          ))}

          {isStreaming && (
            <div className="flex items-center gap-2 py-4 ml-4">
              <span className="w-1 h-1 rounded-full bg-slate-300 animate-bounce [animation-delay:-0.3s]" />
              <span className="w-1 h-1 rounded-full bg-slate-300 animate-bounce [animation-delay:-0.15s]" />
              <span className="w-1 h-1 rounded-full bg-slate-300 animate-bounce" />
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
