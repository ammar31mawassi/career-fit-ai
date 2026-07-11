import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

type Bucket = { count: number; resetAt: number };

const SIGNUP_WINDOW_MS = 60 * 60 * 1000;
const SIGNUP_IP_LIMIT = 5;
const SIGNUP_EMAIL_LIMIT = 3;
const buckets = new Map<string, Bucket>();

function clientKey(request: Request) {
  const forwarded = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim();
  return forwarded || request.headers.get("x-real-ip") || "unknown";
}

function checkLimit(key: string, limit: number, windowMs: number) {
  const now = Date.now();
  const current = buckets.get(key);
  if (!current || current.resetAt <= now) {
    buckets.set(key, { count: 1, resetAt: now + windowMs });
    return { ok: true, remaining: limit - 1, retryAfter: 0 };
  }
  if (current.count >= limit) {
    return {
      ok: false,
      remaining: 0,
      retryAfter: Math.max(1, Math.ceil((current.resetAt - now) / 1000))
    };
  }
  current.count += 1;
  return { ok: true, remaining: limit - current.count, retryAfter: 0 };
}

function rateLimitResponse(retryAfter: number) {
  return NextResponse.json(
    { detail: "Too many signup attempts. Try again later." },
    { status: 429, headers: { "Retry-After": String(retryAfter) } }
  );
}

export async function POST(request: Request) {
  const form = await request.formData();
  const email = String(form.get("email") ?? "").trim().toLowerCase();
  const password = String(form.get("password") ?? "");
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRole = process.env.SUPABASE_SECRET_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY;

  const ipLimit = checkLimit(`signup:ip:${clientKey(request)}`, SIGNUP_IP_LIMIT, SIGNUP_WINDOW_MS);
  if (!ipLimit.ok) {
    return rateLimitResponse(ipLimit.retryAfter);
  }
  if (email) {
    const emailLimit = checkLimit(`signup:email:${email}`, SIGNUP_EMAIL_LIMIT, SIGNUP_WINDOW_MS);
    if (!emailLimit.ok) {
      return rateLimitResponse(emailLimit.retryAfter);
    }
  }

  if (!url || !serviceRole) {
    return NextResponse.json({ detail: "Public signup is not configured." }, { status: 503 });
  }
  if (!email || password.length < 8) {
    return NextResponse.json({ detail: "Use a valid email and a password with at least 8 characters." }, { status: 400 });
  }

  const supabase = createClient(url, serviceRole, {
    auth: { autoRefreshToken: false, persistSession: false }
  });
  const { error } = await supabase.auth.admin.createUser({
    email,
    password,
    email_confirm: true
  });
  if (error) {
    return NextResponse.json({ detail: error.message }, { status: 400 });
  }
  return NextResponse.json({ ok: true });
}
