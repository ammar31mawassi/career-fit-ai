import { redirect } from "next/navigation";
import { LoginClient } from "@/components/LoginClient";
import { createClient } from "@/lib/supabase/server";

export default async function LoginPage() {
  try {
    const supabase = await createClient();
    const { data } = await supabase.auth.getUser();
    if (data.user) redirect("/");
  } catch {
    // Missing env is shown by the client form.
  }
  return <LoginClient />;
}

