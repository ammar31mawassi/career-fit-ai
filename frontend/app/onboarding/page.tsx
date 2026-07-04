import { OnboardingClient } from "@/components/OnboardingClient";
import { requireOnboardingPending } from "@/lib/auth";

export default async function OnboardingPage() {
  await requireOnboardingPending();
  return <OnboardingClient />;
}
