import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { safeSameOriginRedirect } from "@/lib/auth-policy.mjs";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const next = safeSameOriginRedirect(request.url, url.searchParams.get("next"));
  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(next);
  }
  return NextResponse.redirect(new URL("/login?recovery_error=1", url.origin));
}
