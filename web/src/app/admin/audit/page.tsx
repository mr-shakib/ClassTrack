"use client";

import { useCallback, useEffect, useState } from "react";
import { Card, EmptyState, ErrorNote, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useRequireRole } from "@/lib/auth";
import type { AuditEntry } from "@/lib/types";

const ACTION_LABEL: Record<string, string> = {
  check_submitted: "Check submitted",
  status_finalised: "Status finalised",
  teacher_responded: "Teacher responded",
  makeup_created: "Makeup created",
  online_decided: "Online decision",
  makeup_completed: "Makeup completed",
  cancelled: "Class cancelled",
  routine_ingested: "Routine parsed",
  routine_activated: "Routine activated",
  settings_changed: "Rules changed",
  holiday_added: "Calendar day added",
  holiday_removed: "Calendar day removed",
};

export default function AuditPage() {
  const { permitted, loading: authLoading } = useRequireRole(["HOD", "SUPER_ADMIN"]);
  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(
        await api.audit({ entity_type: filter || undefined, limit: 200 }),
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the audit log.");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    if (permitted) void load();
  }, [permitted, load]);

  if (authLoading || !permitted) return <Spinner />;

  return (
    <div className="space-y-4">
      <Card className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-ink-soft">Entity</span>
          {["", "class_instance", "makeup_class", "routine", "setting", "holiday"].map(
            (t) => (
              <button
                key={t || "all"}
                onClick={() => setFilter(t)}
                className={`rounded-lg px-2.5 py-1.5 text-sm font-medium transition-colors ${
                  filter === t
                    ? "bg-brand-soft text-brand"
                    : "text-ink-soft hover:bg-canvas"
                }`}
              >
                {t ? t.replace("_", " ") : "all"}
              </button>
            ),
          )}
        </div>
      </Card>

      {error ? <ErrorNote message={error} /> : null}

      <Card>
        <div className="border-b border-line px-4 py-3">
          <h2 className="text-sm font-semibold">
            Audit trail ({rows.length})
          </h2>
          <p className="text-xs text-ink-faint">
            Append-only. Records are never edited or deleted.
          </p>
        </div>
        {loading ? (
          <Spinner />
        ) : rows.length === 0 ? (
          <EmptyState title="No audit entries" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs uppercase tracking-wide text-ink-faint">
                  <th className="px-4 py-2 font-medium">When</th>
                  <th className="px-4 py-2 font-medium">Actor</th>
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">Entity</th>
                  <th className="px-4 py-2 font-medium">Change</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="whitespace-nowrap px-4 py-2 tabular-nums text-ink-faint">
                      {new Date(r.created_at).toLocaleString([], {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-4 py-2">
                      {r.actor_name === "System" ? (
                        <span className="rounded bg-canvas px-1.5 py-0.5 text-xs font-medium text-ink-faint">
                          System
                        </span>
                      ) : (
                        <span className="text-ink-soft">{r.actor_name ?? "—"}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 font-medium">
                      {ACTION_LABEL[r.action] ?? r.action}
                    </td>
                    <td className="whitespace-nowrap px-4 py-2 text-ink-faint">
                      {r.entity_type.replace("_", " ")} #{r.entity_id}
                    </td>
                    <td className="px-4 py-2 text-xs text-ink-soft">
                      <Change before={r.before} after={r.after} />
                      {r.reason ? (
                        <div className="mt-0.5 italic text-ink-faint">{r.reason}</div>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function Change({
  before,
  after,
}: {
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
}) {
  const b = before?.status ?? before?.makeup_status ?? before?.teacher_response;
  const a = after?.status ?? after?.makeup_status ?? after?.teacher_response;
  if (a == null && b == null) {
    return <span className="text-ink-faint">—</span>;
  }
  return (
    <span className="tabular-nums">
      <span className="text-ink-faint">{String(b ?? "—")}</span>
      <span className="mx-1">→</span>
      <span className="font-medium text-ink">{String(a ?? "—")}</span>
    </span>
  );
}
