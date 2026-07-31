import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { LoginClient } from "@/components/LoginClient";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Sign in — CareerFit",
  robots: { index: false, follow: false }
};

export default async function LoginPage() {
  let authenticated = false;
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    authenticated = Boolean(data.user);
  } catch {
    // Missing env is shown by the client form.
  }
  if (authenticated) redirect("/");
  return <LoginClient />;
}
