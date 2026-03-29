// ============================================================
// SSE Event Contract — shared types between Frontend & Backend
// Backend emit JSON like this format, Frontend parse and route
// ============================================================

export type ThinkingEvent = {
  type: "thinking";
  content: string;
  agent: AgentName;
};

export type ToolCallEvent = {
  type: "tool_call";
  tool: ToolName; // "tavily_search" | "pdf_reader"
  params: Record<string, unknown>; // { query: "AI trends 2025" }
  status: "running" | "done" | "error";
  result_preview?: string;
};

export type ResultEvent = {
  type: "result";
  content: string; // Markdown final report
  is_final: boolean; // true = final chunk
};

export type ArtifactEvent = {
  type: "artifact";
  kind: "summary" | "chart" | "citation_list" | "source_card";
  title: string;
  data: unknown; // string | ChartData | Citation[]
};

export type ErrorEvent = {
  type: "error";
  message: string;
  agent?: AgentName;
};

// Union type — stream-parser.ts will switch on field "type"
export type SSEEvent =
  | ThinkingEvent
  | ToolCallEvent
  | ResultEvent
  | ArtifactEvent
  | ErrorEvent;

// ── Enums ────────────────────────────────────────────────────

export type AgentName =
  | "planner"
  | "researcher"
  | "analyst"
  | "writer"
  | "verifier";

export type ToolName = "tavily_search" | "pdf_reader" | "exa_search";

// ── Citation ──

export type Citation = {
  id: number;
  title: string;
  url: string;
  snippet: string;
  published_date?: string;
  credibility_score?: number; // 0–1, do analyst_agent tính
};

// ── Chart data ──

export type ChartData = {
  chart_type: "bar" | "line" | "pie";
  labels: string[];
  datasets: {
    label: string;
    data: number[];
  }[];
};
