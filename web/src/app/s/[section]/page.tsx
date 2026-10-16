"use client";

import { useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Spinner } from "@/components/ui";

/** A short link to share in a section's group chat: /s/63_A. */
export default function SectionLink() {
  const { section } = useParams<{ section: string }>();
  const router = useRouter();

  useEffect(() => {
    router.replace(`/students?g=${encodeURIComponent(decodeURIComponent(section).toUpperCase())}`);
  }, [section, router]);

  return <Spinner />;
}
