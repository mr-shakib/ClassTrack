"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { homeFor, useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui";

/** Sends each role to its own home. */
export default function Index() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? homeFor(user) : "/login");
  }, [user, loading, router]);

  return (
    <div className="grid min-h-[50dvh] place-items-center">
      <Spinner />
    </div>
  );
}
