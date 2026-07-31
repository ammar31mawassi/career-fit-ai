"use client";

import Link from "next/link";
import { useState } from "react";
import { Download, ShieldCheck, Trash2 } from "lucide-react";
import { deleteCareerFitAccount, getAccountExport } from "@/lib/api";
import { clearWorkspaceCaches } from "@/lib/workspace-session";

export function AccountControls() {
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");

  async function exportData() {
    setExporting(true);
    setError("");
    setStatus("");
    try {
      const data = await getAccountExport();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `careerfit-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 0);
      setStatus("Your data export download has started.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not export your data.");
    } finally {
      setExporting(false);
    }
  }

  async function removeAccount() {
    if (confirmation !== "DELETE") return;
    setDeleting(true);
    setError("");
    setStatus("");
    try {
      await deleteCareerFitAccount();
      clearWorkspaceCaches();
      // The Auth identity no longer exists, so a remote Supabase sign-out
      // would only return 403. Clear the local SSR cookies and redirect.
      window.location.replace("/auth/deleted");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not delete your account.");
      setDeleting(false);
    }
  }

  return (
    <section className="panel account-panel">
      <div className="section-heading">
        <div><span className="section-kicker">Data ownership</span><h2>Your data, your decision</h2><p>Download a portable copy or permanently remove your CareerFit account and private files.</p></div>
        <ShieldCheck size={20} aria-hidden />
      </div>
      {error ? <div className="notice error compact-notice" role="alert">{error}</div> : null}
      {status ? <div className="notice compact-notice" role="status">{status}</div> : null}
      <div className="account-actions">
        <button className="button" disabled={exporting || deleting} onClick={() => void exportData()} type="button"><Download size={15} /> {exporting ? "Preparing export…" : "Export my data"}</button>
        <Link className="button quiet" href="/privacy">Read the privacy policy</Link>
      </div>
      <details className="danger-zone">
        <summary><Trash2 size={15} /> Delete account</summary>
        <div>
          <p>This permanently removes your profile, extracted facts, saved jobs, feedback, and uploaded files. This cannot be undone.</p>
          <label className="field"><span>Type DELETE to confirm</span><input autoComplete="off" onChange={(event) => setConfirmation(event.target.value)} value={confirmation} /></label>
          <button className="button danger" disabled={deleting || confirmation !== "DELETE"} onClick={() => void removeAccount()} type="button"><Trash2 size={15} /> {deleting ? "Deleting account…" : "Permanently delete account"}</button>
        </div>
      </details>
    </section>
  );
}
