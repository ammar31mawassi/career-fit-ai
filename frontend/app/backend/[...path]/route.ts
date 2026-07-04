import { type NextRequest, NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

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

  const headers = new Headers(request.headers);
  for (const name of [
    "connection",
    "content-length",
    "cookie",
    "expect",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade"
  ]) {
    headers.delete(name);
  }
  headers.set("Authorization", `Bearer ${token}`);
  if (process.env.BACKEND_API_KEY) {
    headers.set("X-Internal-API-Key", process.env.BACKEND_API_KEY);
  }
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const response = await fetch(destination, {
    method: request.method,
    headers,
    body: hasBody ? request.body : undefined,
    redirect: "manual",
    cache: "no-store",
    duplex: hasBody ? "half" : undefined
  } as RequestInit & { duplex?: "half" });

  const responseHeaders = new Headers(response.headers);
  responseHeaders.delete("content-encoding");
  responseHeaders.delete("content-length");
  responseHeaders.set("Cache-Control", "private, no-store");
  responseHeaders.set("Vary", "Cookie");
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

