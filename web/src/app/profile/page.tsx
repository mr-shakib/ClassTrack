"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Avatar } from "@/components/Avatar";
import {
  AlertIcon,
  BadgeIcon,
  BuildingIcon,
  CheckIcon,
  CircleIcon,
  EyeIcon,
  EyeOffIcon,
  IdCardIcon,
  LockIcon,
  MailIcon,
} from "@/components/icons";
import { Button, ErrorNote, Spinner } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { everyone, useRequireAccess } from "@/lib/auth";
import type { Profile } from "@/lib/types";

const MIN_PASSWORD = 6;

/** Roomier than the admin tables' inputs, smaller than the checking screen's. */
const fieldClass =
  "min-h-12 w-full rounded-xl border border-line bg-surface px-4 text-base text-ink placeholder:text-ink-faint transition focus:border-brand focus:outline-none focus:ring-4 focus:ring-brand/15";

export default function ProfilePage() {
  const { permitted, loading: authLoading } = useRequireAccess(everyone);
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

  // Opened from "Change password" in the header menu: the section only exists
  // once the profile has loaded, so scroll to it then.
  useEffect(() => {
    if (profile && window.location.hash === "#password") {
      document.getElementById("password")?.scrollIntoView({ block: "start" });
    }
  }, [profile]);

  if (authLoading || !permitted) return <Spinner />;
  if (error) return <ErrorNote message={error} />;
  if (!profile) return <Spinner label="Loading your profile…" />;

  const teacher = profile.is_teacher;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Hero profile={profile} />
      <div className={teacher ? "grid items-start gap-6 lg:grid-cols-2" : "mx-auto max-w-2xl"}>
        {teacher ? <ContactEmail profile={profile} onSaved={setProfile} /> : null}
        <ChangePassword />
      </div>
    </div>
  );
}

/** The person: photo or initials on a brand band, and what identifies them here. */
function Hero({ profile }: { profile: Profile }) {
  const facts: { icon: ReactNode; label: string; value: string | null }[] = [
    {
      icon: <IdCardIcon />,
      label: "Signs in with",
      value: profile.sign_in,
    },
    {
      icon: <BadgeIcon />,
      label: profile.roles.length === 1 ? "Role" : "Roles",
      value: profile.roles.join(", "),
    },
    {
      icon: <BuildingIcon />,
      label: "Department",
      value: profile.department ? profile.department.toUpperCase() : null,
    },
  ];

  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-surface shadow-[0_1px_2px_rgba(15,23,42,0.04)]">
      <div className="h-24 bg-gradient-to-r from-brand via-brand to-info sm:h-28" />
      <div className="px-5 pb-6 sm:px-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-6">
          <Avatar
            name={profile.full_name}
            initial={profile.teacher_initial}
            photo={profile.photo_url}
            size="xl"
            className="-mt-12 shadow-md ring-4 ring-surface"
          />
          <div className="min-w-0 sm:pt-4">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{profile.full_name}</h1>
            {/* The role is among the facts below; only a designation adds to it. */}
            {profile.designation ? (
              <p className="mt-0.5 text-base text-ink-soft">{profile.designation}</p>
            ) : null}
          </div>
        </div>

        <dl className="mt-6 grid gap-3 sm:grid-cols-3">
          {facts
            .filter((f) => f.value)
            .map((f) => (
              <div key={f.label} className="flex items-center gap-3 rounded-xl bg-canvas px-4 py-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-surface text-brand ring-1 ring-line">
                  {f.icon}
                </span>
                <div className="min-w-0">
                  <dt className="text-xs font-medium uppercase tracking-wide text-ink-faint">
                    {f.label}
                  </dt>
                  <dd className="truncate text-base font-semibold text-ink">{f.value}</dd>
                </div>
              </div>
            ))}
        </dl>

        <p className="mt-4 text-sm text-ink-faint">
          {profile.teacher_initial
            ? "Your name and designation come from the faculty list. Ask the department office to correct them."
            : "Your name and role are set by an administrator."}
        </p>
      </div>
    </section>
  );
}

function Section({
  id,
  icon,
  tone = "brand",
  title,
  description,
  children,
}: {
  id?: string;
  icon: ReactNode;
  tone?: "brand" | "info";
  title: string;
  description: string;
  children: ReactNode;
}) {
  const tones = { brand: "bg-brand-soft text-brand", info: "bg-info-soft text-info" };
  return (
    <section
      id={id}
      className="scroll-mt-24 rounded-2xl border border-line bg-surface p-5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] sm:p-6"
    >
      <div className="flex items-start gap-4">
        <span className={`flex size-11 shrink-0 items-center justify-center rounded-xl ${tones[tone]}`}>
          {icon}
        </span>
        <div>
          <h2 className="text-lg font-bold">{title}</h2>
          <p className="mt-0.5 text-base text-ink-soft">{description}</p>
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function Notice({ tone, children }: { tone: "ok" | "warn"; children: ReactNode }) {
  const styles = {
    ok: "bg-ok-soft text-ok",
    warn: "bg-warn-soft text-warn",
  };
  return (
    <div className={`flex items-start gap-2.5 rounded-xl px-4 py-3 text-base ${styles[tone]}`}>
      {tone === "ok" ? (
        <CheckIcon className="mt-0.5 size-5 shrink-0" />
      ) : (
        <AlertIcon className="mt-0.5 size-5 shrink-0" />
      )}
      <div className="min-w-0">{children}</div>
    </div>
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
  const [saved, setSaved] = useState(false);

  const current = profile.contact_email;
  const unchanged = email.trim() === (current ?? "");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const next = await api.updateProfile(email);
      onSaved(next);
      setEmail(next.contact_email ?? "");
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the address.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Section
      icon={<MailIcon />}
      tone="info"
      title="Absence emails"
      description="When staff report you absent from a class, ClassTrack emails you."
    >
      {current ? (
        <Notice tone="ok">
          {saved ? "Saved. " : ""}Emails go to <span className="break-all font-semibold">{current}</span>
        </Notice>
      ) : (
        <Notice tone="warn">
          No address on file, so you are not emailed when reported absent. Add one below.
        </Notice>
      )}

      <form onSubmit={submit} className="mt-4 space-y-3">
        <label className="block">
          <span className="mb-1.5 block text-sm font-medium text-ink-soft">
            {current ? "Change the address" : "Email address"}
          </span>
          <input
            required
            type="email"
            autoComplete="email"
            placeholder="name@diu.edu.bd"
            className={fieldClass}
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setSaved(false);
            }}
          />
        </label>
        {error ? <ErrorNote message={error} /> : null}
        <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={busy || unchanged}>
          {busy ? "Saving…" : "Save email"}
        </Button>
      </form>
    </Section>
  );
}

function PasswordField({
  label,
  value,
  onChange,
  autoComplete,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete: "current-password" | "new-password";
}) {
  const [shown, setShown] = useState(false);
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-ink-soft">{label}</span>
      <span className="relative block">
        <input
          required
          type={shown ? "text" : "password"}
          autoComplete={autoComplete}
          className={`${fieldClass} pr-12`}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button
          type="button"
          onClick={() => setShown((v) => !v)}
          aria-label={shown ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          className="absolute inset-y-0 right-0 flex w-12 items-center justify-center rounded-r-xl text-ink-faint hover:text-ink"
        >
          {shown ? <EyeOffIcon /> : <EyeIcon />}
        </button>
      </span>
    </label>
  );
}

function ChangePassword() {
  const empty = { current: "", next: "", confirm: "" };
  const [form, setForm] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // The rules the server applies, shown as they are met.
  const rules = [
    { met: form.next.length >= MIN_PASSWORD, label: `At least ${MIN_PASSWORD} characters` },
    {
      met: form.next !== "" && form.next !== form.current,
      label: "Different from your current password",
    },
    { met: form.confirm !== "" && form.confirm === form.next, label: "Both new passwords match" },
  ];
  const ready = form.current !== "" && rules.every((r) => r.met);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      await api.changePassword(form.current, form.next);
      setForm(empty);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change the password.");
    } finally {
      setBusy(false);
    }
  };

  const set = (key: keyof typeof empty) => (v: string) => {
    setForm((f) => ({ ...f, [key]: v }));
    setDone(false);
  };

  return (
    <Section
      id="password"
      icon={<LockIcon />}
      title="Password"
      description="If the department gave you a default password, replace it with one only you know."
    >
      {done ? (
        <div className="mb-4">
          <Notice tone="ok">Password changed. Use the new one next time you sign in.</Notice>
        </div>
      ) : null}

      <form onSubmit={submit} className="space-y-4">
        <PasswordField
          label="Current password"
          autoComplete="current-password"
          value={form.current}
          onChange={set("current")}
        />
        <PasswordField
          label="New password"
          autoComplete="new-password"
          value={form.next}
          onChange={set("next")}
        />
        <PasswordField
          label="New password again"
          autoComplete="new-password"
          value={form.confirm}
          onChange={set("confirm")}
        />

        <ul className="space-y-1.5 rounded-xl bg-canvas px-4 py-3" aria-label="Password rules">
          {rules.map((r) => (
            <li
              key={r.label}
              className={`flex items-center gap-2 text-sm ${r.met ? "text-ok" : "text-ink-soft"}`}
            >
              {r.met ? (
                <CheckIcon className="size-4 shrink-0" />
              ) : (
                <CircleIcon className="size-4 shrink-0 text-ink-faint" />
              )}
              {r.label}
            </li>
          ))}
        </ul>

        {error ? <ErrorNote message={error} /> : null}

        <Button type="submit" size="lg" className="w-full sm:w-auto" disabled={busy || !ready}>
          {busy ? "Updating…" : "Update password"}
        </Button>
      </form>
    </Section>
  );
}
