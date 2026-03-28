/**
 * app/api/chat/pdf/route.ts
 * ─────────────────────────────────────────────────────────────
 * Relay for PDF + query — forwards multipart/form-data to FastAPI
 * and pipes the SSE stream back to the browser.
 */

import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

export async function POST(req: NextRequest) {
  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid form data" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const query = formData.get("query");
  const file = formData.get("file");

  if (!query || typeof query !== "string" || query.trim().length < 10) {
    return new Response(
      JSON.stringify({ error: "Query must be at least 10 characters" }),
      { status: 422, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!file || !(file instanceof Blob)) {
    return new Response(JSON.stringify({ error: "PDF file is required" }), {
      status: 422,
      headers: { "Content-Type": "application/json" },
    });
  }

  let backendResponse: Response;
  try {
    // Forward the formData as-is to FastAPI
    backendResponse = await fetch(
      `${BACKEND_URL}/api/research/stream-with-pdf`,
      { method: "POST", body: formData, cache: "no-store" },
    );
  } catch (err) {
    return new Response(
      JSON.stringify({ error: `Backend unreachable: ${String(err)}` }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
  }

  if (!backendResponse.ok) {
    const errorText = await backendResponse.text();
    return new Response(errorText, { status: backendResponse.status });
  }

  return new Response(backendResponse.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
      Connection: "keep-alive",
    },
  });
}
