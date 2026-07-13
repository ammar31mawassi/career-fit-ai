"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, ShieldCheck, Sparkles, Waypoints } from "lucide-react";
import { clearWorkspaceCaches } from "@/components/AppDataProvider";
import { createClient } from "@/lib/supabase/client";
import { getProfile } from "@/lib/api";

export function LoginClient() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup" | "reset">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"error" | "success">("error");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const parameters = new URLSearchParams(window.location.search);
    if (parameters.get("deleted")) {
      setMessage("Your account and CareerFit data were permanently deleted.");
      setMessageKind("success");
    } else if (parameters.get("recovery_error")) {
      setMessage("That recovery link is invalid or expired. Request a new one below.");
      setMessageKind("error");
      setMode("reset");
    }
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    setMessageKind("error");
    try {
      if (mode === "reset") {
        const { error } = await createClient().auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/auth/callback?next=/recover`
        });
        if (error) throw error;
        setMessage("If an account exists for that email, a recovery link is on its way.");
        setMessageKind("success");
        return;
      }
      if (mode === "signup") {
        clearWorkspaceCaches();
        const body = new FormData();
        body.set("email", email);
        body.set("password", password);
        const response = await fetch("/auth/signup", { method: "POST", body });
        if (!response.ok) {
          const payload = await response.json().catch(() => ({})) as { detail?: string };
          throw new Error(payload.detail ?? "Signup failed.");
        }
        const payload = await response.json() as { requiresEmailConfirmation?: boolean };
        if (payload.requiresEmailConfirmation) {
          setMessage("Account created. Check your email to confirm it, then sign in.");
          setMessageKind("success");
          setPassword("");
          setMode("login");
          return;
        }
        const supabase = createClient();
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.replace("/onboarding");
      } else {
        clearWorkspaceCaches();
        const supabase = createClient();
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        const profile = await getProfile();
        router.replace(profile.onboarding_completed ? "/" : "/onboarding");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-showcase">
        <div className="brand login-brand"><span className="brand-mark"><Waypoints size={18} /></span><span className="brand-copy"><strong>CareerFit</strong><small>Evidence-led matching</small></span></div>
        <div><span className="eyebrow"><Sparkles size={14} /> Your career signal, clarified</span><h1>Know why a role fits.<br /><em>Know what to improve.</em></h1><p>Turn your CV into an evidence profile, compare it with a real job, and leave with resume changes you can actually use.</p></div>
        <ul className="login-proof-list">
          <li><CheckCircle2 size={17} /><span><strong>Evidence before keywords</strong>Every score points back to your profile.</span></li>
          <li><CheckCircle2 size={17} /><span><strong>You control the facts</strong>Confirm, correct, reject, export, or delete.</span></li>
          <li><ShieldCheck size={17} /><span><strong>Private by design</strong>Your uploaded documents stay in private storage.</span></li>
        </ul>
      </section>
      <form className="login-card" onSubmit={submit}>
        <div className="login-mark"><Waypoints size={22} aria-hidden /></div>
        <div>
          <h2>{mode === "login" ? "Welcome back" : mode === "signup" ? "Create beta account" : "Reset your password"}</h2>
          <p>{mode === "reset" ? "Enter your email and we will send a secure recovery link." : "CareerFit is open for a small public beta. Upload one CV, scan a role, and review the fit."}</p>
        </div>
        {message ? <div aria-live="polite" className={`notice ${messageKind}`}>{message}</div> : null}
        <label className="field">
          <span>Email</span>
          <input autoComplete="email" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
        </label>
        {mode !== "reset" ? <label className="field">
          <span>Password</span>
          <input autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
          {mode === "signup" ? <small>Use at least 8 characters. Never reuse an important password.</small> : null}
        </label> : null}
        <button className="button primary" disabled={loading} type="submit">
          {loading ? "Working..." : mode === "login" ? "Sign in" : mode === "signup" ? "Create account" : "Send recovery link"}
        </button>
        <div className="auth-mode-actions">
          <button className="auth-text-link" disabled={loading} onClick={() => { setMode(mode === "signup" ? "login" : "signup"); setMessage(""); }} type="button">{mode === "signup" ? "I already have an account" : "Create a beta account"}</button>
          {mode === "login" ? <button className="auth-text-link" disabled={loading} onClick={() => { setMode("reset"); setMessage(""); }} type="button">Forgot password?</button> : null}
          {mode === "reset" ? <button className="auth-text-link" disabled={loading} onClick={() => { setMode("login"); setMessage(""); }} type="button">Back to sign in</button> : null}
        </div>
        <p className="auth-privacy-copy">By continuing, you agree to use this beta responsibly. <Link href="/privacy">Read how your data is handled.</Link></p>
      </form>
    </main>
  );
}
