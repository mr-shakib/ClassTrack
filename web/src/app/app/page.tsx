"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import QrCode from "@/components/QrCode";
import { Card, Spinner } from "@/components/ui";
import { BellIcon, CalendarIcon, CheckIcon, ClockIcon, DownloadIcon } from "@/components/icons";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AndroidApp } from "@/lib/types";

const FEATURES = [
  {
    icon: ClockIcon,
    title: "Reminded before each class",
    body: "A notification shortly before every class you take, makeups and extra classes included.",
  },
  {
    icon: BellIcon,
    title: "Alerts as they happen",
    body: "Missed classes, reschedules and notices from the department arrive as notifications.",
  },
  {
    icon: CalendarIcon,
    title: "Reschedule from your phone",
    body: "Find an empty room for a missed class, and mark a makeup done after it.",
  },
  {
    icon: CheckIcon,
    title: "Checking, room by room",
    body: "Office staff report classes floor by floor, one tap per room.",
  },
];

const megabytes = (bytes: number) => `${Math.round(bytes / 1_000_000)} MB`;

/** The API sends UTC; shown as a date only. */
const day = (iso: string) =>
  new Date(/(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`).toLocaleDateString([], {
    day: "numeric",
    month: "long",
    year: "numeric",
  });

/** Public: where to get the Android app. Signed out it stands alone, like sign-in. */
export default function AppPage() {
  const { user, loading: authLoading } = useAuth();
  const [app, setApp] = useState<AndroidApp | null>(null);
  const [failed, setFailed] = useState(false);
  const [here, setHere] = useState<string | null>(null);

  useEffect(() => {
    api.androidApp().then(setApp, () => setFailed(true));
    // Known only in the browser: the QR code opens this same page on a phone.
    setHere(`${window.location.origin}/app`);
  }, []);

  const signedOut = !authLoading && !user;

  return (
    <div className={signedOut ? "min-h-dvh bg-canvas px-4 py-8 sm:py-12" : ""}>
      <div className="mx-auto max-w-3xl space-y-4">
        {signedOut ? (
          <div className="flex items-center justify-between">
            <Image
              src="/diu-logo.png"
              alt="Daffodil International University"
              width={756}
              height={289}
              className="h-12 w-auto"
              preload
            />
            <Link href="/login" className="text-sm font-medium text-brand hover:underline">
              Sign in on the web
            </Link>
          </div>
        ) : null}

        <Card className="overflow-hidden">
          <div className="grid gap-6 p-5 sm:p-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
            <div>
              <p className="text-sm font-semibold text-brand">ClassTrack for Android</p>
              <h1 className="mt-1 text-2xl font-semibold text-ink">Your classes, on your phone</h1>
              <p className="mt-2 text-base text-ink-soft">
                The same account as this website: sign in with your initial (or email) and
                password.
              </p>

              <div className="mt-5">
                {app == null && !failed ? (
                  <Spinner label="Looking for the app…" />
                ) : app?.available && app.url ? (
                  <>
                    <a
                      href={app.url}
                      {...(app.store ? { target: "_blank", rel: "noopener noreferrer" } : { download: true })}
                      className="inline-flex min-h-12 items-center gap-2 rounded-xl bg-brand px-5 py-3 text-base font-semibold text-white hover:bg-brand/90"
                    >
                      <DownloadIcon className="size-5" />
                      {app.store ? "Get it on Google Play" : "Download for Android"}
                    </a>
                    {!app.store ? (
                      <p className="mt-2 text-sm text-ink-faint">
                        {[
                          app.version ? `Version ${app.version}` : null,
                          app.size_bytes ? megabytes(app.size_bytes) : null,
                          app.updated_at ? `updated ${day(app.updated_at)}` : null,
                        ]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    ) : null}
                  </>
                ) : (
                  <p className="rounded-lg bg-canvas px-3 py-2 text-sm text-ink-soft">
                    {failed
                      ? "Could not reach the server. Try again in a moment."
                      : "The app will be available here soon."}
                  </p>
                )}
              </div>
            </div>

            {here && app?.available ? (
              <div className="hidden text-center md:block">
                <div className="rounded-xl border border-line bg-white p-2">
                  <QrCode value={here} label="QR code that opens this page on a phone" />
                </div>
                <p className="mt-2 max-w-40 text-xs text-ink-faint">
                  On a computer? Scan this with your phone&apos;s camera.
                </p>
              </div>
            ) : null}
          </div>

          <ul className="grid gap-px border-t border-line bg-line sm:grid-cols-2">
            {FEATURES.map((f) => (
              <li key={f.title} className="flex gap-3 bg-surface p-4">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
                  <f.icon className="size-5" />
                </span>
                <span>
                  <span className="block text-sm font-semibold text-ink">{f.title}</span>
                  <span className="mt-0.5 block text-sm text-ink-soft">{f.body}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>

        {app?.available && !app.store ? (
          <Card className="p-5 sm:p-6">
            <h2 className="text-base font-semibold">Installing it</h2>
            <p className="mt-1 text-sm text-ink-soft">
              The app is not on the Play Store yet, so Android asks a couple of extra questions.
            </p>
            <ol className="mt-4 space-y-3">
              {[
                <>
                  On your phone, tap <strong>Download for Android</strong>. If the browser warns
                  that the file might be harmful, choose <strong>Download anyway</strong>.
                </>,
                <>
                  Open the downloaded file. If Android asks, allow your browser to{" "}
                  <strong>install unknown apps</strong>, then go back.
                </>,
                <>
                  Tap <strong>Install</strong>, open ClassTrack and sign in. Allow notifications
                  if it asks, so reminders reach you.
                </>,
              ].map((step, i) => (
                <li key={i} className="flex gap-3 text-sm text-ink">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand text-xs font-semibold text-white">
                    {i + 1}
                  </span>
                  <span className="pt-0.5">{step}</span>
                </li>
              ))}
            </ol>
            <p className="mt-4 text-sm text-ink-soft">
              <strong className="text-ink">To update</strong>, download the new version from this
              page and install it over the old one. You stay signed in.
            </p>
          </Card>
        ) : null}

        <p className="px-1 text-sm text-ink-faint">
          No iPhone app yet: on an iPhone, keep using this website in Safari.
        </p>
      </div>
    </div>
  );
}
