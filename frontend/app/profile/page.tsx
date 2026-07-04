import { ProfileClient } from "@/components/ProfileClient";
import { Shell } from "@/components/Shell";
import { requireOnboardingComplete } from "@/lib/auth";

export default async function ProfilePage() {
  await requireOnboardingComplete();
  return (
    <Shell>
      <ProfileClient />
    </Shell>
  );
}
