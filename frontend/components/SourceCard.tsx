"use client";

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Citation } from "@/lib/types";
import { ExternalLink, ChevronRight } from "lucide-react";

export function SourceCard({
  citation,
  index,
}: {
  citation: Citation;
  index: number;
}) {
  const [isExpanded, setIsExpanded] = useState(false);

  const domain = new URL(citation.url).hostname.replace("www.", "");

  return (
    <Card className="group border border-slate-200 hover:border-blue-200 transition-all duration-200 overflow-hidden bg-white shadow-sm">
      <div className="p-3">
        <div className="flex items-start gap-3">
          <span className="flex-shrink-0 w-5 h-5 rounded bg-slate-100 text-slate-500 text-[10px] font-bold flex items-center justify-center mt-0.5">
            {index + 1}
          </span>

          <div className="flex-1 min-w-0">
            <a
              href={citation.url}
              target="_blank"
              className="text-sm font-semibold text-slate-800 hover:text-blue-600 leading-tight block break-words"
            >
              {citation.title}
            </a>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">
                {domain}
              </span>
              {citation.credibility_score && (
                <span
                  className={`text-[10px] font-bold ${citation.credibility_score > 0.8 ? "text-emerald-500" : "text-amber-500"}`}
                >
                  • {Math.round(citation.credibility_score * 100)}% Trusted
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Collapsible Content */}
        <div className="mt-2">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-1 text-[10px] font-bold text-slate-400 hover:text-slate-600 transition-colors"
          >
            <ChevronRight
              className={`w-3 h-3 transition-transform ${isExpanded ? "rotate-90" : ""}`}
            />
            {isExpanded ? "HIDE SNIPPET" : "VIEW SNIPPET"}
          </button>

          {isExpanded && (
            <div className="mt-2 text-xs text-slate-500 leading-relaxed bg-slate-50 p-2 rounded border border-slate-100 animate-in zoom-in-95 duration-200">
              {citation.snippet}
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}
