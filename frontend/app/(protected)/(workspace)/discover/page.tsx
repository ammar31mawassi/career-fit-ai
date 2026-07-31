import type { Metadata } from "next";
import { DiscoverClient } from "@/components/DiscoverClient";

export const metadata: Metadata = {
  title: "Discover — CareerFit",
  robots: { index: false, follow: false }
};

export default function DiscoverPage() {
  return <DiscoverClient />;
}
