import { createHash } from "node:crypto";
import { AuthError, createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { isAllowedSameOriginRequest } from "@/lib/auth-policy.mjs";

const SIGNUP_WINDOW_SECONDS = 60 * 60;
const SIGNUP_IP_LIMIT = 5;
const SIGNUP_EMAIL_LIMIT = 3;

type LimitResult = {
  allowed: boolean;
  remaining: number;
  retry_after: number;
};

type RateLimitClient = {
  rpc: (
    functionName: string,
    parameters: Record<string, string | number>
  ) => PromiseLike<{ data: unknown; error: { message: string } | null }>;
};

function clientAddress(request: Request) {
  if (process.env.VERCEL === "1") {
    return (
      request.headers.get("x-vercel-forwarded-for")?.split(",")[0]?.trim() ||
      "unknown"
    );
  }
  return request.headers.get("x-real-ip") || "local";
}

function privateBucketKey(scope: string, value: string) {
  const digest = createHash("sha256").update(value).digest("hex");
  return `signup:${scope}:${digest}`;
}

function rateLimitResponse(retryAfter: number) {
  return NextResponse.json(
    { detail: "Too many signup attempts. Try again later." },
    { status: 429, headers: { "Retry-After": String(Math.max(1, retryAfter)) } }
  );
}

async function consumeLimit(
  supabase: RateLimitClient,
  bucketKey: string,
  limit: number
) {
  const { data, error } = await supabase.rpc("consume_rate_limit", {
    p_bucket_key: bucketKey,
    p_limit: limit,
    p_window_seconds: SIGNUP_WINDOW_SECONDS
  });
  if (error) throw new Error("Signup protection is temporarily unavailable.");
  const result = (Array.isArray(data) ? data[0] : data) as LimitResult | null;
  if (!result || typeof result.allowed !== "boolean") {
    throw new Error("Signup protection is temporarily unavailable.");
  }
  return result;
}

export async function POST(request: Request) {
  if (
    !isAllowedSameOriginRequest(
      request.url,
      request.headers.get("origin"),
      process.env.NEXT_PUBLIC_SITE_URL
    )
  ) {
    return NextResponse.json(
      { detail: "Cross-site signup requests are not allowed." },
      { status: 403, headers: { "Cache-Control": "no-store" } }
    );
  }

  const form = await request.formData();
  const email = String(form.get("email") ?? "").trim().toLowerCase();
  const password = String(form.get("password") ?? "");
  if (!email || email.length > 320 || password.length < 8 || password.length > 128) {
    return NextResponse.json(
      { detail: "Use a valid email and a password with at least 8 characters." },
      { status: 400 }
    );
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const secretKey = process.env.SUPABASE_SECRET_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !publishableKey || !secretKey) {
    return NextResponse.json({ detail: "Public signup is not configured." }, { status: 503 });
  }

  const admin = createClient(url, secretKey, {
    auth: { autoRefreshToken: false, persistSession: false }
  });
  try {
    const limiter = admin as unknown as RateLimitClient;
    const ipLimit = await consumeLimit(limiter, privateBucketKey("ip", clientAddress(request)), SIGNUP_IP_LIMIT);
    if (!ipLimit.allowed) return rateLimitResponse(ipLimit.retry_after);
    const emailLimit = await consumeLimit(limiter, privateBucketKey("email", email), SIGNUP_EMAIL_LIMIT);
    if (!emailLimit.allowed) return rateLimitResponse(emailLimit.retry_after);
  } catch {
    return NextResponse.json(
      { detail: "Signup protection is temporarily unavailable. Try again shortly." },
      { status: 503 }
    );
  }

  const publicClient = createClient(url, publishableKey, {
    auth: { autoRefreshToken: false, persistSession: false }
  });
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, "");
  const { data, error } = await publicClient.auth.signUp({
    email,
    password,
    options: siteUrl ? { emailRedirectTo: `${siteUrl}/onboarding` } : undefined
  });
  if (error) {
    const response = NextResponse.json(
      { detail: signupErrorMessage(error) },
      { status: error.status === 429 ? 429 : 400 }
    );
    response.headers.set("Cache-Control", "no-store");
    return response;
  }
  const response = NextResponse.json({ ok: true, requiresEmailConfirmation: !data.session });
  response.headers.set("Cache-Control", "no-store");
  return response;
}

export function signupErrorMessage(error: Pick<AuthError, "code" | "message" | "status">) {
  if (error.code === "signup_disabled" || /signups? not allowed/i.test(error.message)) {
    return "Account creation is temporarily unavailable. The beta signup service is disabled.";
  }
  if (error.status === 429 || error.code === "over_email_send_rate_limit") {
    return "The signup email limit was reached. Try again later.";
  }
  if (error.code === "weak_password") {
    return "Choose a stronger password with at least 8 characters.";
  }
  return "Could not create the account. Check the email and password, then try again.";
}
