import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = { title: "Privacy — CareerFit" };

export default function PrivacyPage() {
  return (
    <main className="legal-shell">
      <article className="legal-card">
        <span className="section-kicker">CareerFit public beta</span>
        <h1>Privacy, in plain language</h1>
        <p className="legal-updated">Last updated July 21, 2026</p>
        <section><h2>What we store</h2><p>Your account email, uploaded CV and optional LinkedIn PDF, pasted profile information, GitHub URL and public repository summaries, extracted profile facts, your confirmations or corrections, saved job descriptions, match results, application stages, job-discovery preferences, and notification delivery status.</p></section>
        <section><h2>Why we use it</h2><p>CareerFit uses this information to build your evidence profile, compare it with jobs, generate resume guidance, improve extraction quality from explicit user feedback, protect the beta from abuse, and operate the service. Privacy-safe operational and onboarding-funnel metrics record stages, methods, timing, counts, decisions such as confirm or skip, and error codes—not CV text, question answers, fact values, or evidence excerpts.</p></section>
        <section><h2>Community job recommendations</h2><p>Job descriptions scanned by users may enter a shared job catalog. Recommendation scoring is opt-in: only people who enable discovery are shortlisted by career interests and logistics before their private profile is scored. The person who scanned the job cannot see another candidate, profile, evidence, or score. You can dismiss recommendations or disable discovery at any time.</p></section>
        <section><h2>Israel discovery beta</h2><p>For explicitly enrolled test accounts, CareerFit can periodically import public job titles, companies, locations, descriptions, requirements, and application links from Goozali&apos;s public job table. Recruiter names, email addresses, phone numbers, and LinkedIn profiles are not stored. Eligibility is configured by account ID and is never inferred from a name, CV, or location.</p></section>
        <section><h2>Job emails</h2><p>Email alerts require a separate opt-in and are limited to higher-confidence matches. Messages use your verified account email, include an unsubscribe link, and do not include CV excerpts or raw profile evidence. Disabling email leaves in-app recommendations available.</p></section>
        <section><h2>Automated decisions</h2><p>The match score is guidance, not an employment decision. It is produced by a deterministic evidence model. You can inspect its evidence, correct profile facts, and should verify every recommendation before using it.</p></section>
        <section><h2>Files and access</h2><p>Uploaded files are stored in a private Supabase bucket. User-owned database rows are scoped by account. CareerFit does not scrape private LinkedIn data and does not sell personal information.</p></section>
        <section><h2>Unfinished setup</h2><p>CV analysis starts when you select a file so you can keep completing setup. If onboarding is not completed within 24 hours, the scheduled cleanup removes the uploaded sources, extracted facts, questions, interests, and profile-review labels from that unfinished preview while keeping the account available to start again.</p></section>
        <section><h2>Your controls</h2><p>Onboarding does not finish until you explicitly confirm or skip both the extracted-fact review and the priority clarification. The Discover page controls discovery enrollment and career fields. The Profile page lets you export your data—including profile corrections, requirement corrections, discovery enrollment, and notification history—as JSON and permanently delete your account, database records, and uploaded files.</p></section>
        <section><h2>Beta limitations</h2><p>This is a small public beta. Avoid uploading identity documents, financial information, medical information, or anything not required for job matching.</p></section>
        <Link className="button primary" href="/">Return to CareerFit</Link>
      </article>
    </main>
  );
}
