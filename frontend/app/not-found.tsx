import Link from "next/link";

export default function NotFound() {
  return (
    <main className="legal-shell">
      <section className="legal-card">
        <span className="section-kicker">404</span>
        <h1>That page is not part of CareerFit</h1>
        <p>The link may be outdated, or the opportunity may no longer be available.</p>
        <Link className="button primary" href="/">Return to opportunities</Link>
      </section>
    </main>
  );
}
