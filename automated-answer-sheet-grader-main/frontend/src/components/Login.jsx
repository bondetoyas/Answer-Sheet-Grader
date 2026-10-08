import { useState } from "react";
import { API_BASE_URL } from "../lib/api";
import { Alert, Button, Field, Input } from "./ui";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Login failed.");
      onLogin(data.access_token, data.username);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-8">
      <div className="surface-in grid w-full max-w-5xl overflow-hidden rounded-lg border border-[var(--line)] bg-[var(--paper)] shadow-[0_24px_70px_rgba(21,59,49,0.14)] md:min-h-[620px] md:grid-cols-[1.05fr_0.95fr]">
        <section className="login-brand flex min-h-72 flex-col justify-between p-7 text-white sm:p-10 md:min-h-full md:p-12">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--coral)] text-lg font-semibold text-white">
              ✓
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-100">Assessment office</p>
              <p className="mt-0.5 text-sm text-white/70">Teacher workspace</p>
            </div>
          </div>
          <div className="my-10 max-w-md">
            <p className="mb-3 text-xs font-semibold uppercase tracking-[0.18em] text-orange-200">Mark · Review · Record</p>
            <h1 className="text-4xl font-semibold leading-tight sm:text-5xl">Answer Sheet<br />Grader</h1>
            <div className="mt-6 h-1 w-16 rounded-full bg-[var(--coral)]" />
          </div>
          <p className="text-xs text-white/60">A considered workspace for classroom assessment</p>
        </section>

        <section className="flex items-center justify-center px-6 py-10 sm:px-12">
          <div className="w-full max-w-sm">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-800">Teacher access</p>
            <h2 className="mt-3 text-3xl font-semibold text-slate-900">Welcome back</h2>
            <p className="mt-1 text-sm text-slate-500">Sign in to your workspace</p>
            <form onSubmit={submit} className="mt-8 space-y-5">
            <Field label="Username">
              <Input value={username} onChange={(e) => setUsername(e.target.value)}
                autoComplete="username" required autoFocus />
            </Field>
            <Field label="Password">
              <Input type="password" value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password" required />
            </Field>
            {error && <Alert tone="error">{error}</Alert>}
            <Button type="submit" disabled={busy} className="mt-2 w-full py-2.5">
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
          </div>
        </section>
      </div>
    </main>
  );
}
