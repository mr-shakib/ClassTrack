"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import StudentNoticeForm from "@/components/student/StudentNoticeForm";
import { Button, Card, EmptyState, ErrorNote, Field, Spinner, inputClass } from "@/components/ui";
import { ApiError, api } from "@/lib/api";
import { adminTab, useAuth, useRequireAccess } from "@/lib/auth";
import type { Audience, Recipient, SentNotification } from "@/lib/types";

const AUDIENCES: { key: Audience; label: string }[] = [
  { key: "everyone", label: "Everyone" },
  { key: "teachers", label: "All teachers" },
  { key: "staff", label: "Office staff" },
  { key: "chosen", label: "Chosen people" },
];

const TITLE_MAX = 120;
const BODY_MAX = 1000;

/** The API sends naive UTC; read it as UTC, not as the browser's local time. */
const when = (iso: string) =>
  new Date(/(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`).toLocaleString([], {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

const people = (n: number) => `${n} ${n === 1 ? "person" : "people"}`;

export default function NotificationsPage() {
  const { permitted, loading: authLoading } = useRequireAccess(adminTab("/admin/notifications"));
  const [readers, setReaders] = useState<"staff" | "students">("staff");

  if (authLoading || !permitted) return <Spinner />;

  return (
    <div className="space-y-4">
      <div className="flex gap-1.5" role="tablist" aria-label="Who to write to">
        {(
          [
            ["staff", "Teachers & staff"],
            ["students", "Students"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={readers === key}
            onClick={() => setReaders(key)}
            className={`rounded-lg px-3.5 py-2 text-sm font-semibold transition-colors ${
              readers === key ? "bg-ink text-white" : "text-ink-soft hover:bg-surface"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {readers === "staff" ? <StaffNotifications /> : <StudentNoticeForm />}
    </div>
  );
}

/** To teachers and staff: their bell, and their phones. */
function StaffNotifications() {
  const { user } = useAuth();
  const [recipients, setRecipients] = useState<Recipient[] | null>(null);
  const [sent, setSent] = useState<SentNotification[] | null>(null);
  const [audience, setAudience] = useState<Audience>("teachers");
  const [chosen, setChosen] = useState<Set<number>>(new Set());
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([api.notificationRecipients(), api.sentNotifications()]);
      setRecipients(r);
      setSent(s);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /** Who the chosen audience reaches, as the API resolves it: a group leaves out the sender. */
  const reach = useMemo(() => {
    const all = recipients ?? [];
    const others = all.filter((r) => r.id !== user?.id);
    const list =
      audience === "everyone"
        ? others
        : audience === "teachers"
          ? others.filter((r) => r.is_teacher)
          : audience === "staff"
            ? others.filter((r) => r.is_staff)
            : all.filter((r) => chosen.has(r.id));
    return { count: list.length, phones: list.filter((r) => r.on_phone).length };
  }, [recipients, audience, chosen, user?.id]);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    const all = recipients ?? [];
    if (!q) return all;
    return all.filter(
      (r) =>
        r.full_name.toLowerCase().includes(q) ||
        (r.teacher_initial ?? "").toLowerCase() === q ||
        r.roles.toLowerCase().includes(q),
    );
  }, [recipients, query]);

  const toggle = (id: number) =>
    setChosen((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const label = AUDIENCES.find((a) => a.key === audience)!.label;
  const ready = title.trim() !== "" && body.trim() !== "" && reach.count > 0;

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ready) return;
    const to = audience === "chosen" ? people(reach.count) : `${label.toLowerCase()} (${people(reach.count)})`;
    if (!window.confirm(`Send “${title.trim()}” to ${to}? It cannot be taken back.`)) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.sendNotification({
        title,
        body,
        audience,
        user_ids: audience === "chosen" ? [...chosen] : undefined,
      });
      setNotice(
        `Sent to ${people(result.sent_to)}. ` +
          (result.on_phones > 0
            ? `${result.on_phones} of them also get it on their phone.`
            : "None of them has the app on a phone yet; they see it in their notifications."),
      );
      setTitle("");
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
    <div className="grid max-w-5xl gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <Card className="p-4">
        <h2 className="text-sm font-semibold">Send a notification</h2>
        <p className="mt-1 text-sm text-ink-soft">
          It appears in each reader&apos;s notifications here and in the app, and on their phone
          if they have signed in on the app there.
        </p>

        <form onSubmit={send} className="mt-4 space-y-4">
          <div>
            <span className="mb-1 block text-sm font-medium text-ink-soft">To</span>
            <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="To">
              {AUDIENCES.map((a) => (
                <button
                  key={a.key}
                  type="button"
                  role="radio"
                  aria-checked={audience === a.key}
                  onClick={() => setAudience(a.key)}
                  className={`rounded-lg px-3 py-1.5 text-sm font-medium ring-1 ring-inset transition-colors ${
                    audience === a.key
                      ? "bg-brand text-white ring-brand"
                      : "bg-surface text-ink-soft ring-line hover:bg-canvas"
                  }`}
                >
                  {a.label}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-ink-faint">
              {recipients == null
                ? "Counting…"
                : `${people(reach.count)}, ${reach.phones} with the app on a phone.`}
              {audience !== "chosen" ? " You are left out of a group you send to." : ""}
            </p>
          </div>

          {audience === "chosen" ? (
            <div className="rounded-lg border border-line">
              <div className="border-b border-line p-2">
                <input
                  className={inputClass}
                  placeholder="Search by name, initial or role"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              {recipients == null ? (
                <Spinner />
              ) : (
                <ul className="max-h-72 divide-y divide-line overflow-y-auto">
                  {matches.length === 0 ? (
                    <li className="px-3 py-4 text-sm text-ink-faint">Nobody matches.</li>
                  ) : (
                    matches.map((r) => (
                      <li key={r.id}>
                        <label className="flex cursor-pointer items-center gap-3 px-3 py-2 hover:bg-canvas">
                          <input
                            type="checkbox"
                            checked={chosen.has(r.id)}
                            onChange={() => toggle(r.id)}
                            className="size-4 accent-brand"
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium">
                              {r.full_name}
                              {r.teacher_initial ? (
                                <span className="ml-1.5 text-ink-faint">{r.teacher_initial}</span>
                              ) : null}
                            </span>
                            <span className="block truncate text-xs text-ink-faint">{r.roles}</span>
                          </span>
                          {r.on_phone ? (
                            <span className="shrink-0 rounded bg-ok-soft px-1.5 py-0.5 text-xs text-ok">
                              App
                            </span>
                          ) : null}
                        </label>
                      </li>
                    ))
                  )}
                </ul>
              )}
              {chosen.size > 0 ? (
                <div className="flex items-center justify-between border-t border-line px-3 py-2 text-xs text-ink-soft">
                  <span>{people(chosen.size)} chosen</span>
                  <button type="button" className="font-medium text-brand" onClick={() => setChosen(new Set())}>
                    Clear
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}

          <Field label="Title" hint={`${title.length}/${TITLE_MAX}`}>
            <input
              className={inputClass}
              maxLength={TITLE_MAX}
              placeholder="e.g. Classes on Thursday are cancelled"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </Field>

          <Field label="Message" hint={`${body.length}/${BODY_MAX}`}>
            <textarea
              className={`${inputClass} min-h-28`}
              maxLength={BODY_MAX}
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </Field>

          {error ? <ErrorNote message={error} /> : null}
          {notice ? (
            <div className="rounded-lg border border-ok/20 bg-ok-soft px-3 py-2 text-sm text-ok">
              {notice}
            </div>
          ) : null}

          <Button type="submit" disabled={busy || !ready}>
            {busy
              ? "Sending…"
              : audience === "chosen"
                ? `Send to ${people(reach.count)}`
                : `Send to ${label.toLowerCase()}`}
          </Button>
        </form>
      </Card>

      <div className="space-y-4">
        <Card className="p-4">
          <h2 className="text-sm font-semibold">On a phone</h2>
          <div className="mt-3 rounded-2xl bg-canvas p-3">
            <div className="flex items-center gap-2 text-xs text-ink-faint">
              <span className="grid size-5 place-items-center rounded-md bg-brand text-[10px] font-bold text-white">
                C
              </span>
              ClassTrack · now
            </div>
            <p className="mt-1.5 break-words text-sm font-semibold">
              {title.trim() || "The title"}
            </p>
            <p className="mt-0.5 line-clamp-4 whitespace-pre-line break-words text-sm text-ink-soft">
              {body.trim() || "The message, as the phone shows it."}
            </p>
          </div>
        </Card>

        <Card className="p-4">
          <h2 className="text-sm font-semibold">Sent</h2>
          {sent == null ? (
            <Spinner />
          ) : sent.length === 0 ? (
            <EmptyState title="Nothing sent yet" />
          ) : (
            <ul className="mt-2 divide-y divide-line">
              {sent.map((n) => (
                <li key={n.id} className="py-2.5">
                  <p className="break-words text-sm font-medium">{n.title}</p>
                  <p className="mt-0.5 line-clamp-2 whitespace-pre-line break-words text-sm text-ink-soft">
                    {n.body}
                  </p>
                  <p className="mt-1 text-xs text-ink-faint">
                    {AUDIENCES.find((a) => a.key === n.audience)?.label ?? n.audience} ·{" "}
                    {people(n.sent_to)} · {n.sent_by ?? "—"} · {when(n.created_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
