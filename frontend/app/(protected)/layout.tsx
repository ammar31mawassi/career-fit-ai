import type { ReactNode } from "react";
import { AppDataProvider } from "@/components/AppDataProvider";
import { requireUser } from "@/lib/auth";

// Every route in this group depends on the request's Supabase session. Making
// that contract explicit prevents build-time prerendering from evaluating
// authenticated pages without runtime configuration.
export const dynamic = "force-dynamic";

export default async function ProtectedLayout({ children }: { children: ReactNode }) {
  await requireUser();
  return <AppDataProvider>{children}</AppDataProvider>;
}
