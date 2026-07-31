"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function ErrorBoundary({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Keep browser reporting content-free; the digest correlates with server logs.
    console.error("CareerFit route error", { digest: error.digest ?? "" });
  }, [error]);

  return (
    <main className="legal-shell">
      <section className="legal-card" role="alert">
        <span className="section-kicker">Recovery</span>
        <h1>This page could not finish loading</h1>
        <p>Your saved work is still on the server. Retry the page; if the problem continues, sign out and return with a fresh session.</p>
        {error.digest ? <p className="legal-updated">Reference code: {error.digest}</p> : null}
        <div className="form-actions">
          <button className="button primary" onClick={reset} type="button">Try again</button>
          <Link className="button quiet" href="/">Return to opportunities</Link>
        </div>
      </section>
    </main>
  );
}
