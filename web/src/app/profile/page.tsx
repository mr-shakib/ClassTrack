"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Card, ErrorNote, Field, Spinner, bigInputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { ROLE_LABELS, useRequireRole } from "@/lib/auth";
import type { Profile, Role } from "@/lib/types";

/** Every signed-in user has a profile, whatever their role. */
const EVERYONE = Object.keys(ROLE_LABELS) as Role[];

const MIN_PASSWORD = 6;

export default function ProfilePage() {
  const { permitted, loading: authLoading } = useRequireRole(EVERYONE);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setProfile(await api.profile());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load your profile.");
    }
  }, []);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  if (authLoading || !permitted) return <Spinner />;

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Your profile</h1>

      {error ? <ErrorNote message={error} /> : null}
      {!profile && !error ? <Spinner /> : null}

      {profile ? (
        <>
          <Details profile={profile} />
          {profile.role === "TEACHER" ? (
            <ContactEmail profile={profile} onSaved={setProfile} />
          ) : null}
          <ChangePassword />
        </>
      ) : null}
    </div>
  );
}

function Details({ profile }: { profile: Profile }) {
  const rows: [string, string | null][] = [
    ["Name", profile.full_name],
    ["Role", ROLE_LABELS[profile.role]],
    [profile.teacher_initial ? "Sign in with initial" : "Sign in with", profile.sign_in],
    ["Designation", profile.designation],
    ["Department", profile.department?.toUpperCase() ?? null],
  ];
  return (
    <Card className="p-5">
      <dl className="divide-y divide-line">
        {rows
          .filter(([, value]) => value)
          .map(([label, value]) => (
            <div key={label} className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-2.5">
              <dt className="text-base text-ink-soft">{label}</dt>
              <dd className="break-all text-base font-semibold text-ink">{value}</dd>
            </div>
          ))}
      </dl>
      <p className="mt-3 text-sm text-ink-faint">
        Your name and designation come from the faculty list. Ask the department office to
        correct them.
      </p>
    </Card>
  );
}

function ContactEmail({
  profile,
  onSaved,
}: {
  profile: Profile;
  onSaved: (p: Profile) => void;
}) {
  const [email, setEmail] = useState(profile.contact_email ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const unchanged = email.trim() === (profile.contact_email ?? "");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await api.updateProfile(email);
      onSaved(saved);
      setEmail(saved.contact_email ?? "");
      setNotice("Saved. Absence reports will go to this address.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the address.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5">
      <h2 className="text-xl font-bold">Email for absence reports</h2>
      <p className="mt-1 text-base text-ink-soft">
        {profile.contact_email
          ? "When staff report you absent from a class, ClassTrack emails you here."
          : "No address on file, so you get no email when staff report you absent. Add one."}
      </p>
      <form onSubmit={submit} className="mt-4 space-y-4">
        <Field label="Email" size="lg">
          <input
            required
            type="email"
            autoComplete="email"
            className={bigInputClass}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        {error ? <ErrorNote message={error} /> : null}
        {notice ? <p className="text-base text-ok">{notice}</p> : null}
        <Button type="submit" size="lg" disabled={busy || unchanged}>
          {busy ? "Saving…" : "Save email"}
        </Button>
      </form>
    </Card>
  );
}

function ChangePassword() {
  const empty = { current: "", next: "", confirm: "" };
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const mismatch = form.confirm !== "" && form.confirm !== form.next;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.next !== form.confirm) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.changePassword(form.current, form.next);
      setForm(empty);
      setNotice("Password changed. Use the new one next time you sign in.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change the password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5">
      <h2 className="text-xl font-bold">Change password</h2>
      <p className="mt-1 text-base text-ink-soft">
        If the department gave you a default password, replace it with one only you know.
      </p>
      <form onSubmit={submit} className="mt-4 space-y-4">
        <Field label="Current password" size="lg">
          <input
            required
            type="password"
            autoComplete="current-password"
            className={bigInputClass}
            value={form.current}
            onChange={(e) => setForm({ ...form, current: e.target.value })}
          />
        </Field>
        <Field label="New password" size="lg" hint={`At least ${MIN_PASSWORD} characters.`}>
          <input
            required
            minLength={MIN_PASSWORD}
            type="password"
            autoComplete="new-password"
            className={bigInputClass}
            value={form.next}
            onChange={(e) => setForm({ ...form, next: e.target.value })}
          />
        </Field>
        <Field
          label="New password again"
          size="lg"
          hint={mismatch ? "The two new passwords do not match." : undefined}
        >
          <input
            required
            type="password"
            autoComplete="new-password"
            aria-invalid={mismatch}
            className={bigInputClass}
            value={form.confirm}
            onChange={(e) => setForm({ ...form, confirm: e.target.value })}
          />
        </Field>
        {error ? <ErrorNote message={error} /> : null}
        {notice ? <p className="text-base text-ok">{notice}</p> : null}
        <Button
          type="submit"
          size="lg"
          disabled={busy || form.next.length < MIN_PASSWORD || form.next !== form.confirm}
        >
          {busy ? "Saving…" : "Change password"}
        </Button>
      </form>
    </Card>
  );
}
