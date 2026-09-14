"use client";

import Image from "next/image";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { HOME_FOR, useAuth } from "@/lib/auth";
import { Button, Card, ErrorNote, Field, inputClass } from "@/components/ui";

const DEMO = [
  ["admin@diu.edu", "Super admin"],
  ["hod@diu.edu", "Head of department"],
  ["staff1@diu.edu", "Office staff"],
  ["teacher@diu.edu", "Teacher"],
];

/**
 * Seeded demo accounts, for local development only. A deployed site has its
 * passwords changed after seeding, so offering them there only produces
 * "Invalid credentials" -- and it would advertise the admin addresses.
 * Inlined at build time: `npm run dev` shows it, every production build hides it.
 */
const SHOW_DEMO = process.env.NODE_ENV !== "production";

export default function LoginPage() {
  const [email, setEmail] = useState(SHOW_DEMO ? "staff1@diu.edu" : "");
  const [password, setPassword] = useState(SHOW_DEMO ? "classtrack" : "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const { refresh } = useAuth();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = await api.login(email, password);
      await refresh();
      router.replace(HOME_FOR[user.role]);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not sign in. Try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-dvh place-items-center bg-canvas p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <Image
            src="/diu-logo.png"
            alt="Daffodil International University"
            width={756}
            height={289}
            className="mx-auto mb-4 h-20 w-auto"
            preload
          />
          <h1 className="text-xl font-semibold">ClassTrack</h1>
          <p className="mt-1 text-sm text-ink-soft">
            Class monitoring &amp; makeup management
          </p>
          <p className="text-xs text-ink-faint">Department of CSE, DIU</p>
        </div>

        <Card className="p-5">
          <form onSubmit={submit} className="space-y-4">
            <Field label="Email or teacher initial" hint="Teachers sign in with their initial, e.g. SRH.">
              <input
                type="text"
                autoCapitalize="none"
                className={inputClass}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
              />
            </Field>
            <Field label="Password">
              <input
                type="password"
                className={inputClass}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </Field>

            {error ? <ErrorNote message={error} /> : null}

            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </Card>

        {SHOW_DEMO ? (
          <Card className="mt-4 p-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-faint">
              Demo accounts · password <code className="text-ink-soft">classtrack</code>
            </p>
            <div className="grid gap-1">
              {DEMO.map(([addr, label]) => (
                <button
                  key={addr}
                  type="button"
                  onClick={() => {
                    setEmail(addr);
                    setPassword("classtrack");
                  }}
                  className="flex items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-canvas"
                >
                  <span className="text-ink-soft">{label}</span>
                  <code className="text-xs text-ink-faint">{addr}</code>
                </button>
              ))}
            </div>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
