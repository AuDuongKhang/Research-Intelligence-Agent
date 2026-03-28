"use client";

import { Card } from "@/components/ui/card";
import { ToolCallEvent } from "@/lib/types";

const TOOL_STYLES: Record<string, { icon: string; color: string }> = {
  tavily_search: { icon: "⚡", color: "text-blue-600" },
  pdf_reader: { icon: "📄", color: "text-orange-600" },
  exa_search: { icon: "🔍", color: "text-purple-600" },
};

function StatusBadge({ status }: { status: ToolCallEvent["status"] }) {
  const styles = {
    running: "bg-blue-50 text-blue-600 border-blue-200 animate-pulse",
    done: "bg-emerald-50 text-emerald-600 border-emerald-200",
    error: "bg-red-50 text-red-600 border-red-200",
  };
  const labels = { running: "Running...", done: "Done", error: "Error" };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${styles[status]}`}
    >
      {labels[status]}
    </span>
  );
}

export function ToolCallCard({ event }: { event: ToolCallEvent }) {
  const toolStyle = TOOL_STYLES[event.tool] ?? {
    icon: "🔧",
    color: "text-slate-600",
  };

  return (
    <Card className="border border-slate-200 bg-slate-50/50 overflow-hidden my-2 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-sm">{toolStyle.icon}</span>
          <span className={`text-xs font-mono font-bold ${toolStyle.color}`}>
            {event.tool}()
          </span>
        </div>
        <StatusBadge status={event.status} />
      </div>

      {/* Body */}
      <div className="p-3 space-y-2">
        <div>
          <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">
            Arguments
          </p>
          <pre className="text-[11px] text-slate-600 font-mono p-2 bg-white rounded border border-slate-100 whitespace-pre-wrap break-words">
            {JSON.stringify(event.params, null, 2)}
          </pre>
        </div>

        {event.result_preview && (
          <div className="animate-in fade-in slide-in-from-top-1 duration-300">
            <p className="text-[10px] text-slate-400 uppercase font-bold mb-1">
              Output Preview
            </p>
            <div className="text-[11px] text-slate-600 bg-white p-2 rounded border border-slate-100 italic">
              {event.result_preview}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
