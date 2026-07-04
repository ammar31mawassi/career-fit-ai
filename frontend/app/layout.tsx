import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppDataProvider } from "@/components/AppDataProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerFit — Know where you fit",
  description: "Evidence-led job matching and resume guidance."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body><AppDataProvider>{children}</AppDataProvider></body>
    </html>
  );
}
