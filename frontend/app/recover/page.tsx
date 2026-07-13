import type { Metadata } from "next";
import { RecoveryClient } from "@/components/RecoveryClient";

export const metadata: Metadata = { title: "Recover account — CareerFit" };

export default function RecoverPage() {
  return <RecoveryClient />;
}
