import type { Metadata } from "next";

/** The student page installs to a home screen as its own app; the staff screens do not. */
export const metadata: Metadata = {
  title: "ClassTrack for students",
  description: "Your section's routine, makeups and notices. No sign-in.",
  manifest: "/students.webmanifest",
  appleWebApp: { capable: true, title: "ClassTrack", statusBarStyle: "default" },
  icons: { apple: "/icons/apple-touch-icon.png" },
};

export default function StudentsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
