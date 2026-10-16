"use client";

import { useEffect, useMemo, useState } from "react";
import { Button, Card, ErrorNote, Spinner, inputClass } from "@/components/ui";
import { CheckIcon, CloseIcon, SearchIcon } from "@/components/icons";
import { api } from "@/lib/api";
import { parentOf } from "@/lib/student";
import type { StudentDirectory } from "@/lib/types";

const chip = (on: boolean) =>
  `min-h-11 rounded-xl px-4 py-2 text-base font-semibold ring-1 ring-inset transition-colors ${
    on ? "bg-brand text-white ring-brand" : "bg-surface text-ink ring-line hover:bg-canvas"
  }`;

/**
 * Who a student is, as the routine knows them: an intake, a section of it, a
 * lab group of that, and any retake groups. No sign-in: the choice stays in
 * this browser and in the link.
 */
export default function SectionPicker({
  initial,
  onDone,
  onCancel,
}: {
  initial: string[];
  onDone: (groups: string[]) => void;
  onCancel?: () => void;
}) {
  const [dir, setDir] = useState<StudentDirectory | null>(null);
  const [error, setError] = useState<string | null>(null);

  const start = initial.find((g) => !g.includes(":") && parentOf(g) === null) ?? null;
  const startLab = initial.find((g) => !g.includes(":") && parentOf(g) !== null) ?? null;
  const [section, setSection] = useState<string | null>(start ?? (startLab ? parentOf(startLab) : null));
  const [intake, setIntake] = useState<string | null>(section ? section.split("_")[0] : null);
  const [lab, setLab] = useState<string | null>(startLab);
  const [retakes, setRetakes] = useState<string[]>(initial.filter((g) => g.includes(":")));
  const [query, setQuery] = useState("");

  useEffect(() => {
    api.studentDirectory().then(setDir, () => setError("Could not reach ClassTrack. Try again."));
  }, []);

  const intakes = useMemo(
    () => [...new Set((dir?.sections ?? []).map((s) => s.intake).filter(Boolean))],
    [dir],
  );
  const sections = (dir?.sections ?? []).filter((s) => s.intake === intake);
  const chosen = dir?.sections.find((s) => s.section === section);
  const retakeMatches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return (dir?.retakes ?? [])
      .filter(
        (r) =>
          r.course_code.toLowerCase().includes(q) ||
          (r.course_title ?? "").toLowerCase().includes(q),
      )
      .slice(0, 8);
  }, [dir, query]);

  const toggleRetake = (token: string) =>
    setRetakes((prev) => (prev.includes(token) ? prev.filter((t) => t !== token) : [...prev, token]));

  const groups = [...(section ? [lab ?? section] : []), ...retakes];

  if (error) return <ErrorNote message={error} />;
  if (!dir) return <Spinner label="Loading the routine…" />;

  return (
    <Card className="mx-auto max-w-2xl overflow-hidden">
      <div className="border-b border-line px-5 py-5">
        <h1 className="text-2xl font-bold tracking-tight">Find your routine</h1>
        <p className="mt-1 text-base text-ink-soft">
          {dir.department} · {dir.semester ?? "No semester running"}. No sign-in needed: pick your
          section once and this browser remembers it.
        </p>
      </div>

      <div className="space-y-6 px-5 py-5">
        <Step n={1} title="Your batch">
          <div className="flex flex-wrap gap-2">
            {intakes.map((i) => (
              <button
                key={i}
                type="button"
                className={chip(intake === i)}
                onClick={() => {
                  setIntake(i);
                  setSection(null);
                  setLab(null);
                }}
              >
                {i}
              </button>
            ))}
          </div>
        </Step>

        {intake ? (
          <Step n={2} title="Your section">
            <div className="flex flex-wrap gap-2">
              {sections.map((s) => (
                <button
                  key={s.section}
                  type="button"
                  className={chip(section === s.section)}
                  onClick={() => {
                    setSection(s.section);
                    setLab(null);
                  }}
                >
                  {s.section.split("_")[1]}
                </button>
              ))}
            </div>
          </Step>
        ) : null}

        {chosen && chosen.lab_groups.length > 0 ? (
          <Step n={3} title="Your lab group" hint="For your lab classes. Theory classes are the whole section's.">
            <div className="flex flex-wrap gap-2">
              {chosen.lab_groups.map((g) => (
                <button key={g} type="button" className={chip(lab === g)} onClick={() => setLab(g)}>
                  {g}
                </button>
              ))}
              <button type="button" className={chip(lab === null)} onClick={() => setLab(null)}>
                Not sure
              </button>
            </div>
          </Step>
        ) : null}

        {section ? (
          <Step
            n={chosen && chosen.lab_groups.length > 0 ? 4 : 3}
            title="Retake courses (optional)"
            hint="Taking a course again with another batch? Add its retake group."
          >
            {retakes.length > 0 ? (
              <div className="mb-3 flex flex-wrap gap-2">
                {retakes.map((t) => (
                  <span
                    key={t}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-brand-soft px-3 py-1.5 text-sm font-semibold text-brand"
                  >
                    {t.replace(":", " · ")}
                    <button type="button" aria-label={`Remove ${t}`} onClick={() => toggleRetake(t)}>
                      <CloseIcon className="size-4" />
                    </button>
                  </span>
                ))}
              </div>
            ) : null}
            <div className="relative">
              <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-ink-faint" />
              <input
                className={`${inputClass} min-h-11 pl-10 text-base`}
                placeholder="Course code or title, e.g. CSE447"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            {retakeMatches.length > 0 ? (
              <ul className="mt-2 divide-y divide-line rounded-xl border border-line">
                {retakeMatches.map((r) => (
                  <li key={r.course_code} className="px-3 py-2.5">
                    <p className="text-sm font-semibold">
                      {r.course_code}
                      {r.course_title ? <span className="font-normal text-ink-soft"> · {r.course_title}</span> : null}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {r.groups.flatMap((g) => [g, ...g.lab_groups]).map((g) => (
                        <button
                          key={g.token}
                          type="button"
                          onClick={() => toggleRetake(g.token)}
                          className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-sm font-medium ring-1 ring-inset ${
                            retakes.includes(g.token)
                              ? "bg-brand text-white ring-brand"
                              : "bg-surface text-ink-soft ring-line hover:bg-canvas"
                          }`}
                        >
                          {retakes.includes(g.token) ? <CheckIcon className="size-3.5" /> : null}
                          {g.section}
                        </button>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            ) : query.trim() ? (
              <p className="mt-2 text-sm text-ink-faint">No retake course matches.</p>
            ) : null}
          </Step>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-line bg-canvas px-5 py-4">
        <Button size="lg" disabled={groups.length === 0} onClick={() => onDone(groups)}>
          Show my routine
        </Button>
        {onCancel ? (
          <Button size="lg" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </Card>
  );
}

function Step({
  n,
  title,
  hint,
  children,
}: {
  n: number;
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="mb-3 flex items-start gap-3">
        <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand text-sm font-bold text-white">
          {n}
        </span>
        <div>
          <h2 className="text-lg font-bold leading-7">{title}</h2>
          {hint ? <p className="text-sm text-ink-soft">{hint}</p> : null}
        </div>
      </div>
      <div className="pl-10">{children}</div>
    </section>
  );
}
