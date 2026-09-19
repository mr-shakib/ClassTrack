"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Tally } from "@/lib/types";

/**
 * Chart marks for the report outcomes.
 *
 * These are status colours, not a categorical palette: each one means the same
 * thing it means on a badge. Validated as a set (lightness band, chroma floor,
 * colour-blind separation, contrast) against the page surface. The teal is a
 * step brighter than the text token, which reads grey as a filled mark.
 */
export const SERIES = [
  { key: "conducted", label: "On time", color: "#047857" },
  { key: "late", label: "Late", color: "#d97706" },
  { key: "missed", label: "Missed", color: "#b91c1c" },
  { key: "not_checked", label: "Not checked", color: "#6d28d9" },
  { key: "rescheduled", label: "Rescheduled", color: "#0891b2" },
  // Neutral, not a status: upcoming or not yet settled. Drawn so a day of
  // unsettled classes does not read as a day with none.
  { key: "pending", label: "Pending", color: "#cbd5e1" },
] as const;

type SeriesKey = (typeof SERIES)[number]["key"];

const AXIS = { fontSize: 12, fill: "#64748b" };
const GRID = "#eef2f6";
const SURFACE = "#ffffff";

/** The legend: always shown, above the plot, text in ink with a swatch beside it. */
export function Legend({ keys }: { keys?: SeriesKey[] }) {
  const shown = keys ? SERIES.filter((s) => keys.includes(s.key)) : SERIES;
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-soft">
      {shown.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: s.color }} aria-hidden />
          {s.label}
        </li>
      ))}
    </ul>
  );
}

interface TooltipPayload {
  payload?: Record<string, unknown>;
}

function OutcomeTooltip({
  active,
  payload,
  title,
}: {
  active?: boolean;
  payload?: TooltipPayload[];
  title: (row: Record<string, unknown>) => string;
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  const tally = row as unknown as Tally;
  return (
    <div className="min-w-44 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
      <p className="mb-1.5 font-semibold text-ink">{title(row)}</p>
      <table className="w-full">
        <tbody>
          {SERIES.map((s) => (
            <tr key={s.key}>
              <td className="py-0.5 pr-3 text-ink-soft">
                <span
                  className="mr-1.5 inline-block size-2 rounded-sm align-middle"
                  style={{ background: s.color }}
                  aria-hidden
                />
                {s.label}
              </td>
              <td className="text-right font-semibold tabular-nums text-ink">
                {tally[s.key]}
              </td>
            </tr>
          ))}
          <tr className="border-t border-line">
            <td className="pt-1 pr-3 text-ink-soft">Conduct rate</td>
            <td className="pt-1 text-right font-semibold tabular-nums text-ink">
              {tally.conduct_rate}%
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

/**
 * Outcomes stacked per category -- per day, per floor, per slot. Horizontal
 * when the categories are long labels (floors), vertical for time.
 */
export function OutcomeBars<T extends Tally>({
  data,
  category,
  label = (row) => String(row[category]),
  horizontal = false,
  height = 280,
}: {
  data: T[];
  category: keyof T & string;
  label?: (row: T) => string;
  horizontal?: boolean;
  height?: number;
}) {
  const title = (row: Record<string, unknown>) => label(row as unknown as T);
  const autoHeight = horizontal ? Math.max(160, data.length * 34 + 40) : height;
  return (
    <div className="space-y-2">
      <Legend />
      <div style={{ height: autoHeight }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout={horizontal ? "vertical" : "horizontal"}
            margin={{ top: 4, right: 12, bottom: 0, left: horizontal ? 8 : -12 }}
            barCategoryGap={horizontal ? 8 : "18%"}
          >
            <CartesianGrid
              stroke={GRID}
              vertical={horizontal}
              horizontal={!horizontal}
            />
            {horizontal ? (
              <>
                <XAxis type="number" tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey={category as string}
                  tick={AXIS}
                  axisLine={false}
                  tickLine={false}
                  width={92}
                  tickFormatter={(v, i) => (data[i] ? label(data[i]) : String(v))}
                />
              </>
            ) : (
              <>
                <XAxis
                  dataKey={category as string}
                  tick={AXIS}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v, i) => (data[i] ? label(data[i]) : String(v))}
                  minTickGap={8}
                />
                <YAxis tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
              </>
            )}
            <Tooltip
              cursor={{ fill: "rgba(15,23,42,0.05)" }}
              content={<OutcomeTooltip title={title} />}
            />
            {SERIES.map((s) => (
              <Bar
                key={s.key}
                dataKey={s.key}
                name={s.label}
                stackId="outcome"
                fill={s.color}
                // A surface-coloured edge leaves a 2px gap between segments.
                stroke={SURFACE}
                strokeWidth={1}
                maxBarSize={horizontal ? 22 : 36}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/**
 * Where every class in the period stands, as one bar split by outcome.
 * Part-to-whole at a glance; the counts are written beside it, not only drawn.
 */
export function OutcomeShare({ tally }: { tally: Tally }) {
  const parts = SERIES.map((s) => ({
    key: s.key,
    label: s.label,
    color: s.color,
    value: tally[s.key],
  })).filter((p) => p.value > 0);
  const total = parts.reduce((sum, p) => sum + p.value, 0);
  if (total === 0) return <p className="text-sm text-ink-faint">No classes in this period.</p>;

  return (
    <div className="space-y-3">
      <div className="flex h-5 w-full gap-0.5 overflow-hidden rounded-md" role="img"
        aria-label={parts.map((p) => `${p.label} ${p.value}`).join(", ")}>
        {parts.map((p) => (
          <div
            key={p.key}
            className="h-full first:rounded-l-md last:rounded-r-md"
            style={{ width: `${(p.value / total) * 100}%`, background: p.color, minWidth: 3 }}
            title={`${p.label}: ${p.value} (${Math.round((p.value / total) * 100)}%)`}
          />
        ))}
      </div>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-3 lg:grid-cols-6">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-2">
            <span className="size-2.5 shrink-0 rounded-sm" style={{ background: p.color }} aria-hidden />
            <span className="text-ink-soft">{p.label}</span>
            <span className="ml-auto font-semibold tabular-nums text-ink sm:ml-0">
              {p.value}
              <span className="ml-1 font-normal text-ink-faint">
                {Math.round((p.value / total) * 100)}%
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * How many course-sections have held how many classes, with the ones under the
 * minimum drawn in the "missed" red. The minimum is a real line in the data --
 * the bins split exactly on it.
 */
export function HeldDistribution({
  held,
  minimum,
}: {
  held: number[];
  minimum: number;
}) {
  const width = Math.max(2, Math.ceil(minimum / 3));
  const bins: { label: string; count: number; short: boolean }[] = [];
  for (let lo = 0; lo < minimum; lo += width) {
    const hi = Math.min(lo + width, minimum) - 1;
    bins.push({
      label: lo === hi ? `${lo}` : `${lo}–${hi}`,
      count: held.filter((h) => h >= lo && h <= hi).length,
      short: true,
    });
  }
  bins.push({
    label: `${minimum}+`,
    count: held.filter((h) => h >= minimum).length,
    short: false,
  });

  return (
    <div className="space-y-2">
      <ul className="flex flex-wrap gap-x-4 text-xs text-ink-soft">
        <li className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-[#b91c1c]" aria-hidden />
          Below {minimum} held
        </li>
        <li className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm bg-[#047857]" aria-hidden />
          {minimum} or more
        </li>
      </ul>
      <div style={{ height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={bins} margin={{ top: 16, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke={GRID} vertical={false} />
            <XAxis dataKey="label" tick={AXIS} axisLine={false} tickLine={false} />
            <YAxis tick={AXIS} axisLine={false} tickLine={false} allowDecimals={false} />
            <Tooltip
              cursor={{ fill: "rgba(15,23,42,0.05)" }}
              content={({ active, payload }) => {
                const row = payload?.[0]?.payload as (typeof bins)[number] | undefined;
                if (!active || !row) return null;
                return (
                  <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
                    <p className="font-semibold text-ink">{row.label} classes held</p>
                    <p className="text-ink-soft">
                      {row.count} course-section{row.count === 1 ? "" : "s"}
                    </p>
                  </div>
                );
              }}
            />
            <Bar
              dataKey="count"
              radius={[4, 4, 0, 0]}
              maxBarSize={48}
              isAnimationActive={false}
              label={{ position: "top", fontSize: 11, fill: "#475569" }}
            >
              {bins.map((b) => (
                <Cell key={b.label} fill={b.short ? "#b91c1c" : "#047857"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** One measure per teacher, largest first -- e.g. who missed the most. */
export function TeacherBars({
  rows,
  value,
  color,
  unit,
}: {
  rows: { teacher_initial: string; teacher_name: string | null; value: number }[];
  value: string;
  color: string;
  unit: string;
}) {
  if (rows.length === 0) return <p className="text-sm text-ink-faint">Nobody, in this period.</p>;
  return (
    <div style={{ height: Math.max(140, rows.length * 30 + 24) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 0, right: 32, bottom: 0, left: 4 }}>
          <XAxis type="number" hide allowDecimals={false} />
          <YAxis
            type="category"
            dataKey="teacher_initial"
            tick={AXIS}
            axisLine={false}
            tickLine={false}
            width={52}
          />
          <Tooltip
            cursor={{ fill: "rgba(15,23,42,0.05)" }}
            content={({ active, payload }) => {
              const row = payload?.[0]?.payload as (typeof rows)[number] | undefined;
              if (!active || !row) return null;
              return (
                <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-lg">
                  <p className="font-semibold text-ink">
                    {row.teacher_name ?? row.teacher_initial} ({row.teacher_initial})
                  </p>
                  <p className="text-ink-soft">
                    {row.value} {unit}
                  </p>
                </div>
              );
            }}
          />
          <Bar
            dataKey="value"
            name={value}
            fill={color}
            radius={[0, 4, 4, 0]}
            maxBarSize={18}
            isAnimationActive={false}
            label={{ position: "right", fontSize: 11, fill: "#475569" }}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
