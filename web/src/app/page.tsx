"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { HOME_FOR, useAuth } from "@/lib/auth";
import { Spinner } from "@/components/ui";

/** Sends each role to its own home. */
export default function Index() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? HOME_FOR[user.role] : "/login");
  }, [user, loading, router]);

  return (
    <div className="grid min-h-[50dvh] place-items-center">
      <Spinner />
    </div>
  );
}
