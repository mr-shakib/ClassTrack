import type { Metadata } from "next";
import "./globals.css";
import Shell from "@/components/Shell";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = {
  title: "ClassTrack — Class Monitoring",
  description:
    "Department class monitoring and makeup management for DIU CSE.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthProvider>
          <Shell>{children}</Shell>
        </AuthProvider>
      </body>
    </html>
  );
}
