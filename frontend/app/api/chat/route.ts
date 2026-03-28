/**
 * app/api/chat/route.ts
 * ─────────────────────────────────────────────────────────────
 * Next.js Route Handler — SSE relay between browser and FastAPI.
 *
 * Browser  →  POST /api/chat  →  FastAPI :8000/api/research/stream
 *                             ←  SSE stream piped back to browser
 *
 * Why this exists:
 *   - Browser can't call localhost:8000 directly in production
 *   - Centralizes the backend URL in one env variable
 *   - Can add auth headers / rate limiting here later
 */

import { NextRequest } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";

// ── POST /api/chat ────────────────────────────────────────────

export async function POST(req: NextRequest) {
  // 1. Parse and validate the incoming request
  let query: string;
  try {
    const body = await req.json();
    query = body.query?.trim();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  if (!query || query.length < 10) {
    return new Response(
      JSON.stringify({ error: "Query must be at least 10 characters" }),
      { status: 422, headers: { "Content-Type": "application/json" } },
    );
  }

  // 2. Forward the request to FastAPI
  let backendResponse: Response;

  try {
    backendResponse = await fetch(`${BACKEND_URL}/api/research/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
      cache: "no-store",
    });
    const stream = backendResponse.body;
    if (!stream) return new Response("No stream", { status: 500 });
  } catch (err) {
    // FastAPI is not running or unreachable
    return new Response(
      JSON.stringify({ error: `Backend unreachable: ${String(err)}` }),
      { status: 503, headers: { "Content-Type": "application/json" } },
    );
  }

  // 3. Forward non-200 errors from FastAPI back to the browser
  if (!backendResponse.ok) {
    const errorText = await backendResponse.text();
    return new Response(errorText, {
      status: backendResponse.status,
      headers: { "Content-Type": "application/json" },
    });
  }

  // 4. Pipe the SSE stream directly — no buffering
  //    backendResponse.body is a ReadableStream<Uint8Array>
  //    We pass it straight through to the browser.
  return new Response(backendResponse.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no", // prevents nginx from buffering SSE
      Connection: "keep-alive",
    },
  });
}
