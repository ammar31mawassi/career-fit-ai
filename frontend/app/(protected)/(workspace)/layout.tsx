import type { ReactNode } from "react";
import { Shell } from "@/components/Shell";
import { requireOnboardingComplete } from "@/lib/auth";

export default async function WorkspaceLayout({ children }: { children: ReactNode }) {
  await requireOnboardingComplete();
  return <Shell>{children}</Shell>;
}
