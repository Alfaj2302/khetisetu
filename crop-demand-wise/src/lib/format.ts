/** Shared formatting for API values. */
import { MONTHS } from "./constants";

/** Quantities arrive as plain numbers with a separate `unit` field. */
export function formatQty(value: number | null | undefined, unit?: string | null): string {
  if (value === null || value === undefined) return "Not available";
  const rounded = Math.round(value * 10) / 10;
  return `${rounded.toLocaleString("en-IN")}${unit ? ` ${unit}` : ""}`;
}

export function formatSignedQty(value: number | null | undefined, unit?: string | null): string {
  if (value === null || value === undefined) return "Not available";
  return `${value > 0 ? "+" : ""}${formatQty(value, unit)}`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return (Math.round(value * 10) / 10).toLocaleString("en-IN");
}

export function monthLabel(month: number): string {
  return MONTHS.find((m) => m.value === month)?.label ?? String(month);
}

/** "June", "June–July", or "June, August, October" for a set of month numbers. */
export function monthRangeLabel(months: number[]): string {
  if (months.length === 0) return "Not available";
  const sorted = [...months].sort((a, b) => a - b);
  const first = sorted[0] as number;
  const last = sorted[sorted.length - 1] as number;
  if (sorted.length === 1) return monthLabel(first);
  const isContiguous = sorted.every((m, i) => m === first + i);
  if (isContiguous) return `${monthLabel(first)}–${monthLabel(last)}`;
  return sorted.map(monthLabel).join(", ");
}

/** `growing_period_weeks` is a [min, max] pair from the API. */
export function weeksRangeLabel(weeks: number[]): string {
  const min = weeks[0];
  const max = weeks[weeks.length - 1];
  if (min === undefined || max === undefined) return "Not available";
  return min === max ? `${min} weeks` : `${min}–${max} weeks`;
}

/** ISO date from `next_7_days[].date` → short weekday. */
export function weekdayLabel(isoDate: string): string {
  const date = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return isoDate;
  return date.toLocaleDateString("en-IN", { weekday: "short" });
}

export function formatTemp(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value)}°C`;
}

export function formatPct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value)}%`;
}
