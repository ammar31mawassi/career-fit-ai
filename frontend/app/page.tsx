import { HomeClient } from "@/components/HomeClient";
import { Shell } from "@/components/Shell";
import { requireOnboardingComplete } from "@/lib/auth";

export default async function Page() {
  await requireOnboardingComplete();
  return (
    <Shell>
      <HomeClient />
    </Shell>
  );
}
