"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Waypoints } from "lucide-react";
import { createClient } from "@/lib/supabase/client";

export function LoginClient() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setMessage("");
    try {
      if (mode === "signup") {
        const body = new FormData();
        body.set("email", email);
        body.set("password", password);
        body.set("invite_code", inviteCode);
        const response = await fetch("/auth/signup", { method: "POST", body });
        if (!response.ok) {
          const payload = await response.json();
          throw new Error(payload.detail ?? "Signup failed.");
        }
        const supabase = createClient();
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push("/onboarding");
        router.refresh();
      } else {
        const supabase = createClient();
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        router.push("/");
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
          <h1>{mode === "login" ? "Sign in" : "Create invite account"}</h1>
          <p>CareerFit is invite-only for the first beta.</p>
        </div>
        {message ? <div className={message.startsWith("Account") ? "notice success" : "notice error"}>{message}</div> : null}
        <label className="field">
          <span>Email</span>
          <input autoComplete="email" onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
        </label>
        <label className="field">
          <span>Password</span>
          <input autoComplete={mode === "login" ? "current-password" : "new-password"} minLength={8} onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
        </label>
        {mode === "signup" ? (
          <label className="field">
            <span>Invite code</span>
            <input onChange={(event) => setInviteCode(event.target.value)} required value={inviteCode} />
          </label>
        ) : null}
        <button className="button primary" disabled={loading} type="submit">
          {loading ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
        </button>
        <button className="button ghost" onClick={() => setMode(mode === "login" ? "signup" : "login")} type="button">
          {mode === "login" ? "I have an invite" : "I already have an account"}
        </button>
      </form>
    </main>
  );
}
