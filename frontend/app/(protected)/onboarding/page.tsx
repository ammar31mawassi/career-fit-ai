import type { Metadata } from "next";
import { OnboardingClient } from "@/components/OnboardingClient";
import { requireOnboardingPending } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Set up your profile — CareerFit",
  robots: { index: false, follow: false }
};

export default async function OnboardingPage() {
  await requireOnboardingPending();
  return <OnboardingClient />;
}
