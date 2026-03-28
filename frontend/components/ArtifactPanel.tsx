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

import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Card } from "@/components/ui/card";
import { SourceCard } from "./SourceCard";
import type { ArtifactEvent, Citation } from "@/lib/types";

// ── Props ─────────────────────────────────────────────────────

interface ArtifactPanelProps {
  artifacts: ArtifactEvent[];
  isStreaming: boolean;
}

// ── Citation list artifact ────────────────────────────────────

function CitationList({ artifact }: { artifact: ArtifactEvent }) {
  const citations = artifact.data as Citation[];

  if (!citations || citations.length === 0) {
    return (
      <p className="text-sm text-slate-400 px-1 italic">
        No citations available.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {citations.map((citation, idx) => (
        <SourceCard key={citation.id ?? idx} citation={citation} index={idx} />
      ))}
    </div>
  );
}

// ── Summary artifact ──────────────────────────────────────────

function SummaryArtifact({ artifact }: { artifact: ArtifactEvent }) {
  return (
    <Card className="border border-slate-200 px-3 py-3 bg-white shadow-sm">
      <p className="text-[10px] text-slate-400 uppercase tracking-widest font-bold mb-2">
        Summary
      </p>
      <p className="text-sm text-slate-600 leading-relaxed break-words whitespace-pre-wrap">
        {String(artifact.data)}
      </p>
    </Card>
  );
}

// ── Chart placeholder ──────────

function ChartPlaceholder({ artifact }: { artifact: ArtifactEvent }) {
  return (
    <Card className="border border-dashed border-slate-200 px-3 py-6 flex flex-col items-center gap-2 bg-slate-50/50">
      <span className="text-2xl opacity-50">📊</span>
      <p className="text-xs font-bold text-slate-400 uppercase tracking-wider">
        {artifact.title}
      </p>
      <p className="text-[10px] text-slate-300 italic text-center px-4">
        Interactive charts are being generated...
      </p>
    </Card>
  );
}

// ── Artifact router ───────────────────────────────────────────

function ArtifactBlock({ artifact }: { artifact: ArtifactEvent }) {
  return (
    <div className="mb-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
      {/* Artifact header */}
      <div className="flex items-center justify-between mb-3 px-1">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
          {artifact.title}
        </span>
        <Badge
          variant="outline"
          className="text-[9px] px-1.5 py-0 h-4 border-slate-200 text-slate-400 font-bold bg-white"
        >
          {artifact.kind.replace("_", " ").toUpperCase()}
        </Badge>
      </div>

      {/* Render based on kind */}
      {artifact.kind === "citation_list" && (
        <CitationList artifact={artifact} />
      )}
      {artifact.kind === "source_card" && <CitationList artifact={artifact} />}
      {artifact.kind === "summary" && <SummaryArtifact artifact={artifact} />}
      {artifact.kind === "chart" && <ChartPlaceholder artifact={artifact} />}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────

export function ArtifactPanel({ artifacts, isStreaming }: ArtifactPanelProps) {
  const isEmpty = artifacts.length === 0;

  return (
    <div className="flex flex-col h-full bg-slate-50/30">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-white">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-slate-700">
            Verified Artifacts
          </span>
          {isStreaming && isEmpty && (
            <div className="flex gap-1 ml-1">
              <span className="w-1 h-1 rounded-full bg-blue-400 animate-bounce" />
              <span className="w-1 h-1 rounded-full bg-blue-400 animate-bounce [animation-delay:0.2s]" />
              <span className="w-1 h-1 rounded-full bg-blue-400 animate-bounce [animation-delay:0.4s]" />
            </div>
          )}
        </div>
        {!isEmpty && (
          <Badge
            variant="secondary"
            className="text-[10px] bg-slate-100 text-slate-500"
          >
            {artifacts.length} Items
          </Badge>
        )}
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 px-4 py-4">
        {isEmpty ? (
          <div className="flex flex-col items-center justify-center h-64 gap-3 text-center opacity-40">
            <div className="w-12 h-12 rounded-full border-2 border-dashed border-slate-300 flex items-center justify-center text-xl">
              📋
            </div>
            <p className="text-xs font-medium text-slate-400 max-w-[160px]">
              Citations and analysis will appear once the agents begin
              processing.
            </p>
          </div>
        ) : (
          <div className="pb-10">
            {artifacts.map((artifact, idx) => (
              <ArtifactBlock key={idx} artifact={artifact} />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
