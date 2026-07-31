"use client";

export default function GlobalError({
  error,
  reset
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body>
        <main className="legal-shell">
          <section className="legal-card" role="alert">
            <h1>CareerFit needs a fresh start</h1>
            <p>The application shell could not load. Your server-side data has not been removed.</p>
            {error.digest ? <p>Reference code: {error.digest}</p> : null}
            <button className="button primary" onClick={reset} type="button">Reload CareerFit</button>
          </section>
        </main>
      </body>
    </html>
  );
}
