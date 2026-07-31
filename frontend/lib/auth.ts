import { redirect } from "next/navigation";
import { cache } from "react";
import { createClient } from "@/lib/supabase/server";

export const requireUser = cache(async function requireUser() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) {
    redirect("/login");
  }
  return data.user;
});

export async function requireOnboardingComplete() {
  const user = await requireUser();
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("profiles")
    .select("onboarding_completed")
    .eq("user_id", user.id)
    .maybeSingle();
  if (error) {
    throw new Error("CareerFit could not verify your onboarding state.");
  }
  if (!data?.onboarding_completed) {
    redirect("/onboarding");
  }
  return user;
}

export async function requireOnboardingPending() {
  const user = await requireUser();
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("profiles")
    .select("onboarding_completed")
    .eq("user_id", user.id)
    .maybeSingle();
  if (error) {
    throw new Error("CareerFit could not verify your onboarding state.");
  }
  if (data?.onboarding_completed) {
    redirect("/");
  }
  return user;
}
