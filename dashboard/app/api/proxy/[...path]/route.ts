import { NextRequest, NextResponse } from "next/server";

const BACKEND =
  process.env.API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "https://coldpilot-api.onrender.com";

export const maxDuration = 120;

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  // Detect SSE stream requests
  if (path.join("/").endsWith("/stream")) {
    return streamProxy(req, path);
  }
  return proxy(req, path);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(req, path);
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(req, path);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  return proxy(req, path);
}

// ── Standard proxy (buffer response) ──
async function proxy(req: NextRequest, pathSegments: string[]) {
  const apiPath = "/api/" + pathSegments.join("/");
  const url = `${BACKEND}${apiPath}`;

  const headers: Record<string, string> = {};
  const ct = req.headers.get("content-type");
  if (ct) headers["Content-Type"] = ct;

  try {
    const body = req.method !== "GET" ? await req.arrayBuffer() : undefined;

    const res = await fetch(url, {
      method: req.method,
      headers,
      body: body ? Buffer.from(body) : undefined,
    });

    const data = await res.arrayBuffer();

    return new NextResponse(Buffer.from(data), {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("Content-Type") || "application/json",
      },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json(
      { error: "Backend unavailable", detail: message },
      { status: 502 },
    );
  }
}

// ── SSE streaming proxy (forward chunks in real-time) ──
async function streamProxy(req: NextRequest, pathSegments: string[]) {
  const apiPath = "/api/" + pathSegments.join("/");
  const qs = req.nextUrl.search || "";
  const url = `${BACKEND}${apiPath}${qs}`;

  try {
    const res = await fetch(url, {
      headers: { Accept: "text/event-stream" },
    });

    if (!res.ok || !res.body) {
      return NextResponse.json(
        { error: "Stream unavailable", status: res.status },
        { status: res.status },
      );
    }

    // Pipe the ReadableStream from the backend straight through
    const stream = new ReadableStream({
      async start(controller) {
        const reader = res.body!.getReader();
        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            controller.enqueue(value);
          }
        } catch {
          // Stream closed or errored — that's normal for SSE
        } finally {
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json(
      { error: "Stream connection failed", detail: message },
      { status: 502 },
    );
  }
}
