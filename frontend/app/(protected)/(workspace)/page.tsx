import type { Metadata } from "next";
import { HomeClient } from "@/components/HomeClient";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default function Page() {
  return <HomeClient />;
}
