import { type NextRequest, NextResponse } from "next/server";
import {
  allowedBackendRequestHeaders,
  allowedBackendResponseHeaders
} from "@/lib/bff-policy.mjs";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const maxDuration = 60;
const BACKEND_TIMEOUT_MS = 55_000;

type RouteContext = { params: Promise<{ path: string[] }> };

async function forward(request: NextRequest, context: RouteContext) {
  const backendUrl = process.env.BACKEND_API_URL?.replace(/\/$/, "");
  if (!backendUrl) {
    return NextResponse.json({ detail: "Backend URL is not configured." }, { status: 503 });
  }
  const supabase = await createClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) {
    return NextResponse.json({ detail: "Authentication required." }, { status: 401 });
  }

  const { path } = await context.params;
  const destination = new URL(`${backendUrl}/${path.map(encodeURIComponent).join("/")}`);
  destination.search = request.nextUrl.search;

  const headers = allowedBackendRequestHeaders(request.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (process.env.BACKEND_API_KEY) {
    headers.set("X-Internal-API-Key", process.env.BACKEND_API_KEY);
  }
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const timeoutSignal = AbortSignal.timeout(BACKEND_TIMEOUT_MS);
  const signal = AbortSignal.any([request.signal, timeoutSignal]);
  let response: Response;
  try {
    response = await fetch(destination, {
      method: request.method,
      headers,
      body: hasBody ? request.body : undefined,
      redirect: "manual",
      cache: "no-store",
      signal,
      duplex: hasBody ? "half" : undefined
    } as RequestInit & { duplex?: "half" });
  } catch (error) {
    const timedOut = timeoutSignal.aborted && !request.signal.aborted;
    return NextResponse.json(
      {
        detail: timedOut
          ? "The backend did not respond in time."
          : "The backend is temporarily unavailable.",
        code: timedOut ? "BACKEND_TIMEOUT" : "BACKEND_UNAVAILABLE"
      },
      {
        status: timedOut ? 504 : 502,
        headers: { "Cache-Control": "private, no-store" }
      }
    );
  }

  const responseHeaders = allowedBackendResponseHeaders(response.headers);
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: responseHeaders
  });
}

export const GET = forward;
export const POST = forward;
export const PUT = forward;
export const PATCH = forward;
export const DELETE = forward;
export const HEAD = forward;
