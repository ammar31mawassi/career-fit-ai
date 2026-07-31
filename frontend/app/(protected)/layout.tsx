import type { ReactNode } from "react";
import { AppDataProvider } from "@/components/AppDataProvider";
import { requireUser } from "@/lib/auth";

export default async function ProtectedLayout({ children }: { children: ReactNode }) {
  await requireUser();
  return <AppDataProvider>{children}</AppDataProvider>;
}
