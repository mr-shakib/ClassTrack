"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";
import { ago } from "@/lib/student";
import type { ClassInstance, StudentNotice, TeacherGroup } from "@/lib/types";
import { MessageIcon } from "./icons";
import { Button, Card, ErrorNote, inputClass } from "./ui";

const BODY_MAX = 500;

/** Things a teacher often tells a section before a class. */
const QUICK = [
  "Please bring your laptops.",
  "We will have a quiz in this class.",
  "Please read the shared material before the class.",
];

/**
 * Section Notices, from the teacher: a note to the students of any of their
 * sections. It reaches the students' Updates and, on the app, their phones.
 */
export function MessageStudentsCard() {
  const [groups, setGroups] = useState<TeacherGroup[] | null>(null);
  const [sent, setSent] = useState<StudentNotice[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [g, s] = await Promise.all([api.myStudentGroups(), api.myStudentNotices()]);
      setGroups(g);
      setSent(s.slice(0, 3));
    } catch {
      setGroups([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (groups == null || groups.length === 0) return null;

  const toggle = (token: string) =>
    setChosen((prev) => {
      const next = new Set(prev);
      if (next.has(token)) next.delete(token);
      else next.add(token);
      return next;
    });

  const send = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.writeToMyStudents({ body: body.trim(), targets: [...chosen] });
      setNotice("Sent. Your students see it in ClassTrack, and on their phones if they have the app.");
      setBody("");
      setChosen(new Set());
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <div className="border-b border-line px-4 py-4 sm:px-5">
        <h2 className="flex items-center gap-2 text-xl font-bold">
          <MessageIcon className="size-5 text-brand" />
          Message your students
        </h2>
        <p className="mt-1 text-base text-ink-soft">
          A note to any of your sections. They see it in ClassTrack, and on their phone if they
          have the app.
        </p>
      </div>
      <div className="space-y-4 px-4 py-4 sm:px-5">
        <div className="flex flex-wrap gap-2">
          {groups.map((g) => (
            <button
              key={g.token}
              type="button"
              onClick={() => toggle(g.token)}
              className={`rounded-lg px-3 py-2 text-sm font-semibold ring-1 ring-inset ${
                chosen.has(g.token) ? "bg-brand text-white ring-brand" : "bg-surface text-ink ring-line hover:bg-canvas"
              }`}
            >
              {g.course_code} · {g.section}
            </button>
          ))}
        </div>
        <textarea
          className={`${inputClass} min-h-24 text-base`}
          maxLength={BODY_MAX}
          rows={3}
          placeholder="e.g. Assignment 2 is due next Sunday."
          value={body}
          onChange={(e) => setBody(e.target.value)}
        />
        {error ? <ErrorNote message={error} /> : null}
        {notice ? <p className="rounded-lg bg-ok-soft px-3 py-2 text-sm text-ok">{notice}</p> : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button size="lg" onClick={send} disabled={busy || chosen.size === 0 || !body.trim()}>
            {busy ? "Sending…" : chosen.size === 0 ? "Choose a section" : `Send to ${chosen.size} section${chosen.size === 1 ? "" : "s"}`}
          </Button>
          <span className="text-xs text-ink-faint">
            {body.length}/{BODY_MAX}
          </span>
        </div>
        {sent.length > 0 ? (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">Sent lately</p>
            <ul className="mt-1 divide-y divide-line">
              {sent.map((n) => (
                <li key={n.id} className="py-2 text-sm">
                  <span className="font-medium">{n.title}</span>
                  <span className="text-ink-faint"> · {ago(n.created_at)}</span>
                  <p className="line-clamp-2 text-ink-soft">{n.body}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

/** A heads-up about one class: it shows on the class, and reaches its section. */
export function HeadsUp({ instance }: { instance: ClassInstance }) {
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.writeToMyStudents({ body: body.trim(), instance_id: instance.id });
      setDone(true);
      setOpen(false);
      setBody("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not send.");
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-semibold text-brand ring-1 ring-inset ring-brand/30 hover:bg-brand-soft"
      >
        <MessageIcon className="size-4" />
        {done ? "Note sent · send another" : "Note to students"}
      </button>
    );
  }

  return (
    <div className="mt-2 w-full space-y-2 rounded-xl border border-brand/25 bg-brand-soft/50 p-3">
      <p className="text-sm font-semibold">
        Heads-up to section {instance.section} about this class
      </p>
      <div className="flex flex-wrap gap-1.5">
        {QUICK.map((q) => (
          <button
            key={q}
            type="button"
            onClick={() => setBody(q)}
            className="rounded-lg bg-surface px-2.5 py-1 text-xs font-medium ring-1 ring-inset ring-line hover:bg-canvas"
          >
            {q}
          </button>
        ))}
      </div>
      <textarea
        className={`${inputClass} min-h-20`}
        maxLength={BODY_MAX}
        rows={2}
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      {error ? <ErrorNote message={error} /> : null}
      <div className="flex gap-2">
        <Button onClick={send} disabled={busy || !body.trim()}>
          {busy ? "Sending…" : "Send"}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
