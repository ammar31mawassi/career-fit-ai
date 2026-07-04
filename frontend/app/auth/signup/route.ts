import { timingSafeEqual } from "node:crypto";
import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

function safeEqual(left: string, right: string) {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  return leftBuffer.length === rightBuffer.length && timingSafeEqual(leftBuffer, rightBuffer);
}

export async function POST(request: Request) {
  const form = await request.formData();
  const email = String(form.get("email") ?? "").trim().toLowerCase();
  const password = String(form.get("password") ?? "");
  const inviteCode = String(form.get("invite_code") ?? "");
  const expectedInvite = process.env.APP_INVITE_CODE;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRole = process.env.SUPABASE_SECRET_KEY ?? process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!expectedInvite || !url || !serviceRole) {
    return NextResponse.json({ detail: "Invite signup is not configured." }, { status: 503 });
  }
  if (!safeEqual(inviteCode, expectedInvite)) {
    return NextResponse.json({ detail: "Invalid invite code." }, { status: 403 });
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
