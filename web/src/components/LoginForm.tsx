"use client";

import { useEffect, useState } from "react";

import { Button, ErrorNotice, Field, inputClass } from "@/components/ui";
import { api, errorMessage, json } from "@/lib/api";
import type { Me } from "@/lib/types";

type Mode = "code" | "password";
const RESEND_SECONDS = 30;

/** Email-code sign-in (default) with a password fallback. Calls onSignedIn with the user. */
export function LoginForm({ onSignedIn }: { onSignedIn: (me: Me) => void }) {
  const [mode, setMode] = useState<Mode>("code");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  const sendCode = () =>
    run(async () => {
      await api("/auth/code", { method: "POST", body: json({ email }) });
      setCodeSent(true);
      setCode("");
      setCooldown(RESEND_SECONDS);
    });

  const verifyCode = () =>
    run(async () => onSignedIn(await api<Me>("/auth/code/verify", { method: "POST", body: json({ email, code }) })));

  const signInWithPassword = () =>
    run(async () => onSignedIn(await api<Me>("/auth/login", { method: "POST", body: json({ email, password }) })));

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setCodeSent(false);
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-5">
      <div className="mb-5 grid grid-cols-2 rounded-lg bg-surface-2 p-1 text-sm">
        {(["code", "password"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => switchMode(m)}
            className={`rounded-md py-1.5 font-medium transition ${mode === m ? "bg-surface shadow-sm" : "text-muted hover:text-text"}`}
          >
            {m === "code" ? "Email code" : "Password"}
          </button>
        ))}
      </div>

      {mode === "password" ? (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            signInWithPassword();
          }}
        >
          <Field label="Email">
            <input className={inputClass} type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          <Field label="Password">
            <input className={inputClass} type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </Field>
          {error && <ErrorNotice message={error} />}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      ) : !codeSent ? (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            sendCode();
          }}
        >
          <Field label="Work email">
            <input className={inputClass} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </Field>
          {error && <ErrorNotice message={error} />}
          <Button type="submit" disabled={busy} className="w-full">
            {busy ? "Sending…" : "Email me a sign-in code"}
          </Button>
          <p className="text-xs text-muted">No password needed. The code works once and expires in 10 minutes.</p>
        </form>
      ) : (
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            verifyCode();
          }}
        >
          <p className="text-sm">
            If <span className="font-medium">{email}</span> has an account, we sent it a 6-digit code.
          </p>
          <Field label="Sign-in code">
            <input
              className={`${inputClass} text-center font-mono text-lg tracking-[0.5em]`}
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="\d{6}"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              autoFocus
              required
            />
          </Field>
          {error && <ErrorNotice message={error} />}
          <Button type="submit" disabled={busy || code.length !== 6} className="w-full">
            {busy ? "Checking…" : "Sign in"}
          </Button>
          <div className="flex justify-between text-xs">
            <button type="button" onClick={() => switchMode("code")} className="text-muted underline hover:text-text">
              Use a different email
            </button>
            <button
              type="button"
              onClick={sendCode}
              disabled={busy || cooldown > 0}
              className="text-muted underline hover:text-text disabled:no-underline disabled:opacity-60"
            >
              {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
