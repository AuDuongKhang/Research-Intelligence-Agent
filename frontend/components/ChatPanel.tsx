"use client";

/**
 * components/ChatPanel.tsx
 * ─────────────────────────────────────────────────────────────
 * Root component for the Research Intelligence UI.
 *
 * Layout (three-column):
 * ┌──────────────────┬─────────────────────────┬─────────────┐
 * │  Reasoning Log   │     Report / Chat        │  Artifacts  │
 * │  (left panel)    │     (center panel)       │  (right)    │
 * │  30% width       │     45% width            │  25% width  │
 * └──────────────────┴─────────────────────────┴─────────────┘
 *
 * State flow:
 *   user submits query
 *     → streamResearch() opens SSE connection
 *     → callbacks update thinkingSteps / toolCalls / report / artifacts
 *     → child components re-render reactively
 */

import { useState, useRef, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import { ReasoningLog } from "@/components/ReasoningLog";
import { ArtifactPanel } from "@/components/ArtifactPanel";
import { ScrollArea } from "@/components/ui/scroll-area";
import { streamResearch } from "@/lib/stream-parser";
import type { ThinkingEvent, ToolCallEvent, ArtifactEvent } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;         // user: raw query | assistant: accumulated markdown
  isStreaming?: boolean;   // true while the SSE stream is still open
}

// ── Agent step indicator (shown in header while running) ──────

const AGENT_STEPS = ["Planner", "Researcher", "Analyst", "Writer"] as const;

function AgentPipeline({ currentAgent }: { currentAgent: string | null }) {
  if (!currentAgent) return null;

  const active = currentAgent.charAt(0).toUpperCase() + currentAgent.slice(1);

  return (
    <div className="flex items-center gap-1.5">
      {AGENT_STEPS.map((step, idx) => {
        const stepIdx  = AGENT_STEPS.indexOf(step);
        const activeIdx = AGENT_STEPS.findIndex(
          s => s.toLowerCase() === currentAgent.toLowerCase()
        );
        const isDone    = stepIdx < activeIdx;
        const isActive  = step === active;

        return (
          <div key={step} className="flex items-center gap-1.5">
            <div className="flex items-center gap-1">
              {/* Status dot */}
              <span
                className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  isDone   ? "bg-emerald-400" :
                  isActive ? "bg-blue-400 animate-pulse" :
                             "bg-slate-200"
                }`}
              />
              <span
                className={`text-xs ${
                  isDone   ? "text-emerald-600" :
                  isActive ? "text-blue-600 font-medium" :
                             "text-slate-300"
                }`}
              >
                {step}
              </span>
            </div>
            {/* Connector */}
            {idx < AGENT_STEPS.length - 1 && (
              <span className="text-slate-200 text-xs">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Query input form ──────────────────────────────────────────

interface QueryInputProps {
  onSubmit: (query: string) => void;
  isStreaming: boolean;
}

function QueryInput({ onSubmit, isStreaming }: QueryInputProps) {
  const [value, setValue] = useState("");

  const handleSubmit = () => {
    const trimmed = value.trim();
    if (!trimmed || trimmed.length < 10 || isStreaming) return;
    onSubmit(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="border-t border-slate-200 bg-white px-4 py-3">
      <div className="flex gap-3 items-end">
        <textarea
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a research question... (e.g. What are the latest breakthroughs in quantum computing?)"
          disabled={isStreaming}
          rows={2}
          className="flex-1 resize-none rounded-lg border border-slate-200 bg-slate-50 px-3 py-2
                     text-sm text-slate-800 placeholder:text-slate-400
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                     disabled:opacity-50 disabled:cursor-not-allowed
                     transition-colors"
        />
        <button
          onClick={handleSubmit}
          disabled={isStreaming || value.trim().length < 10}
          className="flex-shrink-0 h-10 px-4 rounded-lg text-sm font-medium
                     bg-blue-600 text-white hover:bg-blue-700
                     disabled:opacity-40 disabled:cursor-not-allowed
                     transition-colors flex items-center gap-2"
        >
          {isStreaming ? (
            <>
              <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Running
            </>
          ) : (
            <>
              <span>Research</span>
              <span className="text-blue-200 text-xs">↵</span>
            </>
          )}
        </button>
      </div>
      <p className="text-xs text-slate-400 mt-1.5 pl-0.5">
        Press Enter to submit · Shift+Enter for new line · Min 10 characters
      </p>
    </div>
  );
}

// ── Center panel: report stream ───────────────────────────────

function ReportPanel({ messages }: { messages: Message[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  return (
    <ScrollArea className="flex-1 px-4 py-4">
      {messages.length === 0 ? (
        // Landing state
        <div className="flex flex-col items-center justify-center h-64 gap-3 text-center">
          <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center text-2xl">
            🔬
          </div>
          <div>
            <p className="text-sm font-medium text-slate-700">Research Intelligence</p>
            <p className="text-xs text-slate-400 mt-1 max-w-xs">
              Ask a question and watch the agents search, analyze, and synthesize
              a cited report in real-time.
            </p>
          </div>
          {/* Example queries */}
          <div className="flex flex-col gap-1.5 w-full max-w-sm mt-2">
            {[
              "Latest breakthroughs in quantum computing 2025",
              "How does CRISPR gene editing work and its current applications",
              "Impact of large language models on software development",
            ].map(q => (
              <button
                key={q}
                onClick={() => {
                  const textarea = document.querySelector("textarea");
                  if (textarea) {
                    const setter = Object.getOwnPropertyDescriptor(
                      window.HTMLTextAreaElement.prototype, "value"
                    )?.set;
                    setter?.call(textarea, q);
                    textarea.dispatchEvent(new Event("input", { bubbles: true }));
                  }
                }}
                className="text-left text-xs text-blue-600 hover:text-blue-700 bg-blue-50
                           hover:bg-blue-100 rounded-md px-3 py-2 transition-colors border
                           border-blue-100 hover:border-blue-200"
              >
                {q} →
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {messages.map(msg => (
            <div key={msg.id}>
              {msg.role === "user" ? (
                // User message bubble
                <div className="flex justify-end">
                  <div className="max-w-[80%] bg-blue-600 text-white rounded-2xl
                                  rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed">
                    {msg.content}
                  </div>
                </div>
              ) : (
                // Assistant report — rendered as Markdown
                <div className="flex justify-start">
                  <div className="max-w-full w-full">
                    {/* Agent label */}
                    <div className="flex items-center gap-1.5 mb-2">
                      <div className="w-6 h-6 rounded-full bg-slate-100 flex items-center justify-center text-xs">
                        🔬
                      </div>
                      <span className="text-xs text-slate-400 font-medium">
                        Research Intelligence
                      </span>
                      {msg.isStreaming && (
                        <span className="text-xs text-blue-400 animate-pulse">
                          · Writing report...
                        </span>
                      )}
                    </div>

                    {/* Markdown report */}
                    <div className="prose prose-sm prose-slate max-w-none
                                    prose-headings:font-semibold prose-headings:text-slate-800
                                    prose-p:text-slate-600 prose-p:leading-relaxed
                                    prose-a:text-blue-600 prose-a:no-underline hover:prose-a:underline
                                    prose-code:bg-slate-100 prose-code:px-1 prose-code:rounded
                                    prose-blockquote:border-l-blue-300 prose-blockquote:text-slate-500
                                    prose-strong:text-slate-700">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>

                    {/* Streaming cursor */}
                    {msg.isStreaming && (
                      <span className="inline-block w-2 h-4 bg-blue-400 rounded-sm
                                       animate-pulse ml-0.5 align-middle" />
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </ScrollArea>
  );
}

// ── Main component ────────────────────────────────────────────

export function ChatPanel() {
  // ── State ──────────────────────────────────────────────────
  const [messages, setMessages]           = useState<Message[]>([]);
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingEvent[]>([]);
  const [toolCalls, setToolCalls]         = useState<ToolCallEvent[]>([]);
  const [artifacts, setArtifacts]         = useState<ArtifactEvent[]>([]);
  const [isStreaming, setIsStreaming]      = useState(false);
  const [currentAgent, setCurrentAgent]   = useState<string | null>(null);
  const [error, setError]                 = useState<string | null>(null);

  // ── Submit handler ─────────────────────────────────────────
  const handleSubmit = useCallback(async (query: string) => {
    // Reset state from previous run
    setThinkingSteps([]);
    setToolCalls([]);
    setArtifacts([]);
    setError(null);
    setCurrentAgent("planner");
    setIsStreaming(true);

    // Add user message
    const userMsgId = crypto.randomUUID();
    const assistantMsgId = crypto.randomUUID();

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: "user", content: query },
      { id: assistantMsgId, role: "assistant", content: "", isStreaming: true },
    ]);

    // ── Stream callbacks ──────────────────────────────────────
    await streamResearch(query, {

      onThinking: (event) => {
        setCurrentAgent(event.agent);
        setThinkingSteps(prev => [...prev, event]);
      },

      onToolCall: (event) => {
        setToolCalls(prev => {
          // Update existing running entry → done/error transition
          const idx = prev.findIndex(
            t =>
              t.tool   === event.tool &&
              t.status === "running"  &&
              JSON.stringify(t.params) === JSON.stringify(event.params)
          );
          if (idx !== -1) {
            const updated = [...prev];
            updated[idx] = event;
            return updated;
          }
          return [...prev, event];
        });
      },

      onResultChunk: (text, isFinal) => {
        if (!isFinal && text) {
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantMsgId
                ? { ...m, content: m.content + text }
                : m
            )
          );
        }
      },

      onArtifact: (event) => {
        setArtifacts(prev => [...prev, event]);
      },

      onError: (message) => {
        setError(message);
        setIsStreaming(false);
        setCurrentAgent(null);
        // Mark assistant message as no longer streaming
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMsgId ? { ...m, isStreaming: false } : m
          )
        );
      },

      onDone: () => {
        setIsStreaming(false);
        setCurrentAgent(null);
        // Mark assistant message as complete
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantMsgId ? { ...m, isStreaming: false } : m
          )
        );
      },
    });
  }, []);

  // ── Layout ─────────────────────────────────────────────────
  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden">

      {/* ── Left panel: Reasoning Log (30%) ─────────────────── */}
      <div className="w-[30%] min-w-[260px] max-w-[380px] flex flex-col
                      bg-white border-r border-slate-200">
        <ReasoningLog
          thinkingSteps={thinkingSteps}
          toolCalls={toolCalls}
          isStreaming={isStreaming}
        />
      </div>

      {/* ── Center panel: Report (flex-1) ────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-3
                        border-b border-slate-200 bg-white">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-slate-700">
              Research Report
            </span>
            {isStreaming && <AgentPipeline currentAgent={currentAgent} />}
          </div>
          {error && (
            <span className="text-xs text-red-500 bg-red-50 px-2 py-1 rounded border border-red-100">
              {error}
            </span>
          )}
        </div>

        {/* Messages */}
        <ReportPanel messages={messages} />

        {/* Input */}
        <QueryInput onSubmit={handleSubmit} isStreaming={isStreaming} />
      </div>

      {/* ── Right panel: Artifacts (25%) ─────────────────────── */}
      <div className="w-[25%] min-w-[220px] max-w-[320px] flex flex-col
                      bg-white border-l border-slate-200">
        <ArtifactPanel
          artifacts={artifacts}
          isStreaming={isStreaming}
        />
      </div>
    </div>
  );
}
