import type { Metadata } from "next";
import { Manrope, Newsreader } from "next/font/google";
import type { ReactNode } from "react";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap"
});

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-editorial",
  display: "swap",
  style: ["normal", "italic"]
});

export const metadata: Metadata = {
  title: "CareerFit — Know where you fit",
  description: "Evidence-led job matching and resume guidance."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html data-scroll-behavior="smooth" lang="en">
      <body className={`${manrope.variable} ${newsreader.variable}`}>{children}</body>
    </html>
  );
}
