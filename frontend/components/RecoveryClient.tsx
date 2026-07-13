"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { KeyRound, Waypoints } from "lucide-react";
import { createClient } from "@/lib/supabase/client";

export function RecoveryClient() {
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [success, setSuccess] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (password !== confirmation) {
      setMessage("The passwords do not match.");
      return;
    }
    setLoading(true);
    setMessage("");
    const { error } = await createClient().auth.updateUser({ password });
    if (error) {
      setMessage("This recovery link is invalid or expired. Request a new link from the sign-in page.");
    } else {
      setSuccess(true);
      setMessage("Password updated. You can return to CareerFit.");
    }
    setLoading(false);
  }

  return (
    <main className="login-shell compact-auth-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="login-mark"><Waypoints size={22} aria-hidden /></div>
        <div><span className="section-kicker"><KeyRound size={12} /> Account recovery</span><h1>Choose a new password</h1><p>Use at least eight characters and do not reuse an important password.</p></div>
        {message ? <div className={`notice ${success ? "success" : "error"}`} role="status">{message}</div> : null}
        {!success ? <>
          <label className="field"><span>New password</span><input autoComplete="new-password" minLength={8} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} /></label>
          <label className="field"><span>Confirm new password</span><input autoComplete="new-password" minLength={8} onChange={(event) => setConfirmation(event.target.value)} required type="password" value={confirmation} /></label>
          <button className="button primary" disabled={loading} type="submit">{loading ? "Updating…" : "Update password"}</button>
        </> : <Link className="button primary" href="/">Return to CareerFit</Link>}
        <Link className="auth-text-link" href="/login">Back to sign in</Link>
      </form>
    </main>
  );
}
