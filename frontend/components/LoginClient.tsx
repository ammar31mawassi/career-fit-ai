"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Waypoints } from "lucide-react";
import { clearWorkspaceCaches } from "@/components/AppDataProvider";
import { createClient } from "@/lib/supabase/client";

export function LoginClient() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [messageKind, setMessageKind] = useState<"error" | "success">("error");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    setMessageKind("error");
    try {
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
        router.refresh();
      } else {
        clearWorkspaceCaches();
        const supabase = createClient();
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.replace("/");
        router.refresh();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Authentication failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="login-mark"><Waypoints size={22} aria-hidden /></div>
        <div>
          <h1>{mode === "login" ? "Sign in" : "Create beta account"}</h1>
          <p>CareerFit is open for a small public beta. Upload one CV, scan a role, and review the fit.</p>
        </div>
        {message ? <div aria-live="polite" className={`notice ${messageKind}`}>{message}</div> : null}
        <label className="field">
          <span>Email</span>
          <input autoComplete="email" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
        </label>
        <label className="field">
          <span>Password</span>
          <input autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
          {mode === "signup" ? <small>Use at least 8 characters. Never reuse an important password.</small> : null}
        </label>
        <button className="button primary" disabled={loading} type="submit">
          {loading ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <button className="button ghost" disabled={loading} onClick={() => { setMode(mode === "login" ? "signup" : "login"); setMessage(""); }} type="button">
          {mode === "login" ? "Create a beta account" : "I already have an account"}
        </button>
      </form>
    </main>
  );
}
