"use client";

/**
 * components/ArtifactPanel.tsx
 * ─────────────────────────────────────────────────────────────
 * Right-side panel that displays artifacts emitted by the analyst
 * and writer agents — primarily the verified citation list.
 *
 * Handles these artifact kinds (from types.ts):
 *   "citation_list" → renders a list of SourceCards
 *   "summary"       → renders a short text summary block
 *   "chart"         → reserved for future use (placeholder shown)
 *
 * Props:
 *   artifacts  — array of ArtifactEvent accumulated from SSE stream
 *   isStreaming — true while the SSE connection is open
 */

import { useState } from "react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { ArtifactEvent, Citation } from "@/lib/types";

// ── Props ─────────────────────────────────────────────────────

interface ArtifactPanelProps {
  artifacts: ArtifactEvent[];
  isStreaming: boolean;
}

// ── Credibility score indicator ───────────────────────────────

function CredibilityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);

  const color =
    pct >= 80 ? "bg-emerald-400" :
    pct >= 60 ? "bg-amber-400"   :
                "bg-red-400";

  const label =
    pct >= 80 ? { text: "High",   style: "bg-emerald-50 text-emerald-700 border-emerald-200" } :
    pct >= 60 ? { text: "Medium", style: "bg-amber-50 text-amber-700 border-amber-200"       } :
                { text: "Low",    style: "bg-red-50 text-red-700 border-red-200"              };

  return (
    <div className="flex items-center gap-2">
      {/* Bar track */}
      <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {/* Badge */}
      <span
        className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium border ${label.style}`}
        style={{ minWidth: 44, justifyContent: "center" }}
      >
        {label.text}
      </span>
    </div>
  );
}

// ── Single citation card ──────────────────────────────────────

function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  const [expanded, setExpanded] = useState(false);

  // Derive a clean domain name for display
  let domain = "";
  try {
    domain = new URL(citation.url).hostname.replace(/^www\./, "");
  } catch {
    domain = citation.url;
  }

  return (
    <Card className="border border-slate-200 overflow-hidden hover:border-slate-300 transition-colors">
      {/* Top row: index + title + external link */}
      <div className="flex items-start gap-3 px-3 pt-3 pb-2">
        {/* Citation number badge */}
        <span className="flex-shrink-0 w-6 h-6 rounded-full bg-slate-100 text-slate-500 text-xs font-semibold flex items-center justify-center mt-0.5">
          {index + 1}
        </span>

        <div className="flex-1 min-w-0">
          {/* Title — clickable external link */}
          <a
            href={citation.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-slate-800 hover:text-blue-600 transition-colors line-clamp-2 leading-snug block"
          >
            {citation.title}
          </a>

          {/* Domain */}
          <p className="text-xs text-slate-400 mt-0.5 truncate">{domain}</p>
        </div>
      </div>

      {/* Credibility bar */}
      {citation.credibility_score !== undefined && (
        <div className="px-3 pb-2">
          <p className="text-xs text-slate-400 mb-1">Credibility</p>
          <CredibilityBar score={citation.credibility_score} />
        </div>
      )}

      <Separator />

      {/* Snippet — collapsible */}
      <div className="px-3 py-2">
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-600 transition-colors mb-1"
        >
          <span
            className="inline-block transition-transform duration-200"
            style={{ transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}
          >
            ▶
          </span>
          {expanded ? "Hide excerpt" : "Show excerpt"}
        </button>

        {expanded && (
          <p className="text-xs text-slate-500 leading-relaxed bg-slate-50 rounded px-2 py-1.5 border border-slate-100">
            {citation.snippet}
          </p>
        )}
      </div>
    </Card>
  );
}

// ── Citation list artifact ────────────────────────────────────

function CitationList({ artifact }: { artifact: ArtifactEvent }) {
  const citations = artifact.data as Citation[];

  if (!citations || citations.length === 0) {
    return (
      <p className="text-sm text-slate-400 px-1">No citations available.</p>
    );
  }

  return (
    <div className="space-y-2">
      {citations.map((citation, idx) => (
        <CitationCard key={citation.id ?? idx} citation={citation} index={idx} />
      ))}
    </div>
  );
}

// ── Summary artifact ──────────────────────────────────────────

function SummaryArtifact({ artifact }: { artifact: ArtifactEvent }) {
  return (
    <Card className="border border-slate-200 px-3 py-3">
      <p className="text-xs text-slate-400 uppercase tracking-wide font-medium mb-2">
        Summary
      </p>
      <p className="text-sm text-slate-600 leading-relaxed">
        {String(artifact.data)}
      </p>
    </Card>
  );
}

// ── Chart placeholder ─────────────────────────────────────────

function ChartPlaceholder({ artifact }: { artifact: ArtifactEvent }) {
  return (
    <Card className="border border-dashed border-slate-200 px-3 py-6 flex flex-col items-center gap-2">
      <span className="text-2xl">📊</span>
      <p className="text-sm text-slate-400">{artifact.title}</p>
      <p className="text-xs text-slate-300">Chart rendering coming soon</p>
    </Card>
  );
}

// ── Artifact router ───────────────────────────────────────────

function ArtifactBlock({ artifact }: { artifact: ArtifactEvent }) {
  return (
    <div className="mb-4">
      {/* Artifact header */}
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          {artifact.title}
        </span>
        <Badge
          variant="outline"
          className="text-xs px-1.5 py-0 h-4 border-slate-200 text-slate-400"
        >
          {artifact.kind}
        </Badge>
      </div>

      {/* Render based on kind */}
      {artifact.kind === "citation_list" && <CitationList artifact={artifact} />}
      {artifact.kind === "summary"       && <SummaryArtifact artifact={artifact} />}
      {artifact.kind === "chart"         && <ChartPlaceholder artifact={artifact} />}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────

export function ArtifactPanel({ artifacts, isStreaming }: ArtifactPanelProps) {
  const isEmpty = artifacts.length === 0;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-700">Artifacts</span>
          {isStreaming && isEmpty && (
            <span className="text-xs text-slate-400 animate-pulse">
              Waiting for analyst...
            </span>
          )}
        </div>
        {!isEmpty && (
          <span className="text-xs text-slate-400">
            {artifacts.length} artifact{artifacts.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 px-4 py-3">
        {isEmpty ? (
          // Empty state
          <div className="flex flex-col items-center justify-center h-40 gap-2">
            <span className="text-2xl">📋</span>
            <p className="text-sm text-slate-400 text-center">
              Citations and summaries will appear here once the analyst finishes.
            </p>
          </div>
        ) : (
          <div>
            {artifacts.map((artifact, idx) => (
              <ArtifactBlock key={idx} artifact={artifact} />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
