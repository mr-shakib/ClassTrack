"use client";

import Image from "next/image";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { homeFor, useAuth } from "@/lib/auth";
import { Button, Card, ErrorNote, Field, inputClass } from "@/components/ui";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
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
      router.replace(homeFor(user));
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
            <Field
              label="Email, initial or employee ID"
              hint="Teachers sign in with their initial, e.g. SRH. Staff may use their employee ID."
            >
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
      </div>
    </div>
  );
}
