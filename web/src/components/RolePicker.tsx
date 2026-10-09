"use client";

import type { RoleInfo, RoleKind, User } from "@/lib/types";

const KIND_TAG: Partial<Record<RoleKind, { label: string; className: string }>> = {
  TEACHER: { label: "teacher", className: "bg-brand-soft text-brand" },
  STAFF: { label: "floor staff", className: "bg-info-soft text-info" },
};

/** The no-escalation rule, as the API applies it: a role can only be given by
 *  someone who holds every permission in it. */
export const canGrant = (me: User, role: RoleInfo) =>
  role.permissions.every((p) => me.permissions.includes(p));

/** Pick one or more roles. Teacher roles appear only for a teacher account; a
 *  role this admin cannot give is shown, greyed, with the reason. */
export function RolePicker({
  me,
  roles,
  selected,
  onChange,
  teacherAccount,
}: {
  me: User;
  roles: RoleInfo[];
  selected: number[];
  onChange: (ids: number[]) => void;
  teacherAccount: boolean;
}) {
  // A teacher account may hold any role; anyone else, no teacher role.
  const offered = roles.filter((r) => teacherAccount || r.kind !== "TEACHER");
  return (
    <div className="flex flex-wrap gap-2">
      {offered.map((r) => {
        const on = selected.includes(r.id);
        const allowed = canGrant(me, r);
        const tag = KIND_TAG[r.kind];
        return (
          <button
            key={r.id}
            type="button"
            aria-pressed={on}
            disabled={!allowed}
            title={
              allowed
                ? r.description || undefined
                : "It grants permissions you do not have, so you cannot give or take it."
            }
            onClick={() => onChange(on ? selected.filter((id) => id !== r.id) : [...selected, r.id])}
            className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium ring-1 ring-inset transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
              on
                ? "bg-brand text-white ring-brand"
                : "bg-surface text-ink-soft ring-line hover:bg-canvas"
            }`}
          >
            {r.name}
            {tag ? (
              <span
                className={`rounded px-1 text-[11px] font-semibold ${
                  on ? "bg-white/20 text-white" : tag.className
                }`}
              >
                {tag.label}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
