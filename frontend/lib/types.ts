// ============================================================
// SSE Event Contract — shared types giữa Frontend & Backend
// Backend emit JSON theo format này, Frontend parse và route
// đúng component tương ứng.
// ============================================================

export type ThinkingEvent = {
  type: "thinking";
  content: string; // "Tôi đang phân tích yêu cầu..."
  agent: AgentName; // Node nào đang chạy
};

export type ToolCallEvent = {
  type: "tool_call";
  tool: ToolName; // "tavily_search" | "pdf_reader"
  params: Record<string, unknown>; // { query: "AI trends 2025" }
  status: "running" | "done" | "error";
  result_preview?: string; // snippet kết quả (optional, chỉ khi done)
};

export type ResultEvent = {
  type: "result";
  content: string; // Markdown final report, stream từng chunk
  is_final: boolean; // true = chunk cuối cùng
};

export type ArtifactEvent = {
  type: "artifact";
  kind: "summary" | "chart" | "citation_list" | "source_card";
  title: string;
  data: unknown; // tuỳ kind: string | ChartData | Citation[]
};

export type ErrorEvent = {
  type: "error";
  message: string;
  agent?: AgentName;
};

// Union type — stream-parser.ts sẽ switch trên field "type"
export type SSEEvent =
  | ThinkingEvent
  | ToolCallEvent
  | ResultEvent
  | ArtifactEvent
  | ErrorEvent;

// ── Enums ────────────────────────────────────────────────────

export type AgentName = "planner" | "researcher" | "analyst" | "writer";

export type ToolName = "tavily_search" | "pdf_reader" | "exa_search";

// ── Citation (dùng trong ArtifactEvent khi kind = "citation_list") ──

export type Citation = {
  id: number;
  title: string;
  url: string;
  snippet: string;
  published_date?: string;
  credibility_score?: number; // 0–1, do analyst_agent tính
};

// ── Chart data (dùng trong ArtifactEvent khi kind = "chart") ──

export type ChartData = {
  chart_type: "bar" | "line" | "pie";
  labels: string[];
  datasets: {
    label: string;
    data: number[];
  }[];
};
