"use client";

import Image from "next/image";
import { useState } from "react";

/** Titles that open many faculty names and say nothing about the person. */
const TITLES = new Set(["dr", "mr", "mrs", "ms", "md", "prof", "engr"]);

/**
 * What an avatar says when there is no photo. A teacher is known by their
 * initial everywhere in this app, so that is what they get; anyone else gets
 * the first and last letters of their name, titles and small words dropped.
 */
export function initialsOf(name: string, initial?: string | null): string {
  if (initial) return initial.slice(0, 3).toUpperCase();
  const words = name
    .replace(/\./g, " ")
    .split(/\s+/)
    .filter((w) => /^[A-Z]/.test(w) && !TITLES.has(w.toLowerCase()));
  if (words.length === 0) return name.trim().slice(0, 1).toUpperCase() || "?";
  const last = words.length > 1 ? words[words.length - 1][0] : "";
  return (words[0][0] + last).toUpperCase();
}

const SIZES = {
  sm: { box: "size-9", px: 36, text: (n: number) => (n > 2 ? "text-[11px]" : "text-sm") },
  md: { box: "size-12", px: 48, text: (n: number) => (n > 2 ? "text-sm" : "text-base") },
  xl: { box: "size-24", px: 96, text: (n: number) => (n > 2 ? "text-2xl" : "text-3xl") },
};

/** A round photo, or the person's initials on brand blue when there is none
 *  or it fails to load. */
export function Avatar({
  name,
  initial,
  photo,
  size = "sm",
  className = "",
}: {
  name: string;
  initial?: string | null;
  photo?: string | null;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const { box, px, text } = SIZES[size];

  if (photo && !failed) {
    return (
      <Image
        src={photo}
        alt=""
        width={px}
        height={px}
        // Served as-is from the faculty site: nothing to gain from resizing.
        unoptimized
        onError={() => setFailed(true)}
        className={`${box} shrink-0 rounded-full bg-canvas object-cover object-top ${className}`}
      />
    );
  }

  const letters = initialsOf(name, initial);
  return (
    <span
      aria-hidden
      className={`${box} ${text(letters.length)} inline-flex shrink-0 select-none items-center justify-center rounded-full bg-brand font-bold tracking-tight text-white ${className}`}
    >
      {letters}
    </span>
  );
}
