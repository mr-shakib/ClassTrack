import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy policy · ClassTrack",
  description: "What ClassTrack and its Android app keep, why, and how to have it removed.",
};

const CONTACT = "contactshakibhere@gmail.com";
const UPDATED = "16 October 2026";

/** Public: the privacy policy the website and the Android app link to, and Google Play lists. */
export default function PrivacyPage() {
  return (
    <div className="min-h-dvh bg-canvas px-4 py-8 sm:py-12">
      <article className="mx-auto max-w-2xl">
        <div className="mb-6 flex items-center justify-between">
          <Image
            src="/diu-logo.png"
            alt="Daffodil International University"
            width={756}
            height={289}
            className="h-10 w-auto"
          />
          <Link href="/students" className="text-sm font-medium text-brand hover:underline">
            ClassTrack
          </Link>
        </div>

        <div className="rounded-2xl border border-line bg-surface p-6 sm:p-8">
          <h1 className="text-2xl font-bold tracking-tight">Privacy policy</h1>
          <p className="mt-1 text-sm text-ink-faint">Last updated {UPDATED}</p>

          <div className="mt-6 space-y-6 text-[15px] leading-relaxed text-ink-soft [&_h2]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-ink [&_li]:ml-5 [&_li]:list-disc [&_strong]:text-ink">
            <section>
              <p>
                ClassTrack monitors whether the classes of the Department of Computer Science and
                Engineering, Daffodil International University, are held as the routine says, and
                tells students and teachers when a class changes. It was built for the department
                by Shakib Howlader. This policy covers the website at class.bitstreamhq.com and
                the ClassTrack app for Android.
              </p>
            </section>

            <section>
              <h2>Students</h2>
              <p>Students use ClassTrack without an account. We do not collect their names, ID numbers, email addresses or any other personal information.</p>
              <ul className="mt-2 space-y-1">
                <li>
                  The section, lab group and retake groups a student picks are kept only on their
                  phone, or in their browser for the website.
                </li>
                <li>
                  To send class changes and reminders, the app asks Google&apos;s Firebase Cloud
                  Messaging to deliver to the phone the notices for those groups. Firebase gives
                  the phone a token for that; we do not link it to any person.
                </li>
                <li>
                  Class Alarm can ring from the phone itself, using Android&apos;s alarm
                  permission. The alarms are set on the phone and nothing about them is sent to us.
                </li>
              </ul>
            </section>

            <section>
              <h2>Teachers, office staff and administrators</h2>
              <p>
                Their accounts are created by the department. To run the department&apos;s
                monitoring, ClassTrack keeps:
              </p>
              <ul className="mt-2 space-y-1">
                <li>
                  <strong>Account details:</strong> name, how they sign in (initial, email or
                  employee ID), their roles, and a password, which is stored only as a secure hash.
                </li>
                <li>
                  <strong>Faculty details</strong> from the department&apos;s faculty list: a
                  teacher&apos;s designation, office room and photo, and an email address for
                  absence reports.
                </li>
                <li>
                  <strong>Monitoring records:</strong> the checks staff make (which class, the
                  result, when, by whom, and any remark), reschedule requests and decisions, extra
                  classes, notes teachers send to students, and a log of who changed what.
                </li>
                <li>
                  <strong>Their phone&apos;s push token,</strong> while they are signed in on the
                  app, so notifications reach them. It is deleted when they sign out.
                </li>
              </ul>
              <p className="mt-2">
                Students see a class&apos;s time, room, teacher&apos;s name and office, and whether
                it is on, moved or cancelled. They never see whether a teacher was late, absent,
                or how a class was checked.
              </p>
            </section>

            <section>
              <h2>On the phone</h2>
              <p>
                The app keeps the screens it last loaded, so they open without a signal, and keeps
                a check made without a signal until it can be sent. The sign-in is kept in the
                phone&apos;s secure storage. Signing out deletes what the account loaded and any
                check still waiting; uninstalling the app deletes everything.
              </p>
            </section>

            <section>
              <h2>Who else handles it</h2>
              <ul className="space-y-1">
                <li>Google Firebase Cloud Messaging, to deliver push notifications.</li>
                <li>An email delivery service, to email a teacher when staff report them absent.</li>
              </ul>
              <p className="mt-2">
                We do not sell any data, show ads, or use analytics or tracking. Everything is sent
                over an encrypted connection (HTTPS).
              </p>
            </section>

            <section>
              <h2>How long it is kept</h2>
              <p>
                Monitoring records are the department&apos;s records of its semesters and are kept
                for as long as the department needs them. An account&apos;s push token goes at
                sign-out; a student&apos;s choices stay on their phone until they change them or
                remove the app.
              </p>
            </section>

            <section>
              <h2>Your choices</h2>
              <p>
                Notifications and Class Alarm can be turned off in the app or in the phone&apos;s
                settings. To ask what is kept about you, to correct it, or to have your account and
                its data deleted, email{" "}
                <a href={`mailto:${CONTACT}`} className="font-medium text-brand hover:underline">
                  {CONTACT}
                </a>
                . Records the department must keep about its classes may be kept, without your
                account.
              </p>
            </section>

            <section>
              <h2>Children</h2>
              <p>
                ClassTrack is for university students and staff. It is not meant for children
                under 13 and does not knowingly collect their information.
              </p>
            </section>

            <section>
              <h2>Changes</h2>
              <p>
                If this policy changes, the new version is posted here with a new date.
                Questions: <a href={`mailto:${CONTACT}`} className="font-medium text-brand hover:underline">{CONTACT}</a>.
              </p>
            </section>
          </div>
        </div>
      </article>
    </div>
  );
}
