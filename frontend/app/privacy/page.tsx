import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Privacy — CareerFit" };

export default function PrivacyPage() {
  return (
    <main className="legal-shell">
      <article className="legal-card">
        <span className="section-kicker">CareerFit public beta</span>
        <h1>Privacy, in plain language</h1>
        <p className="legal-updated">Last updated July 13, 2026</p>
        <section><h2>What we store</h2><p>Your account email, uploaded CV and optional LinkedIn PDF, pasted profile information, GitHub URL and public repository summaries, extracted profile facts, your confirmations or corrections, saved job descriptions, match results, and application stages.</p></section>
        <section><h2>Why we use it</h2><p>CareerFit uses this information only to build your evidence profile, compare it with jobs, generate resume guidance, improve extraction quality from explicit user feedback, protect the beta from abuse, and operate the service.</p></section>
        <section><h2>Automated decisions</h2><p>The match score is guidance, not an employment decision. It is produced by a deterministic evidence model. You can inspect its evidence, correct profile facts, and should verify every recommendation before using it.</p></section>
        <section><h2>Files and access</h2><p>Uploaded files are stored in a private Supabase bucket. User-owned database rows are scoped by account. CareerFit does not scrape private LinkedIn data and does not sell personal information.</p></section>
        <section><h2>Your controls</h2><p>The Profile page lets you export your data as JSON and permanently delete your account, database records, and uploaded files. You can also reject individual extracted facts.</p></section>
        <section><h2>Beta limitations</h2><p>This is a small public beta. Avoid uploading identity documents, financial information, medical information, or anything not required for job matching.</p></section>
        <Link className="button primary" href="/">Return to CareerFit</Link>
      </article>
    </main>
  );
}
