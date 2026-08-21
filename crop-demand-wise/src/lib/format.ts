/**
 * Shared formatting for API values.
 *
 * The functions that produce words take the caller's `t` rather than reading a
 * module-level i18n instance, so they stay pure and safe to call during SSR.
 *
 * Digits stay in the "en-IN" format (Latin digits, Indian grouping) in every
 * language: `mr-IN` would render them in Devanagari, which reads as a different
 * number to farmers used to the printed mandi rates.
 */
import type { TFunction } from "i18next";

import { localeOf, type SupportedLanguage } from "./i18n";

const NUMBER_LOCALE = "en-IN";

/** Month label keys, indexed by the API's month number minus one. */
const MONTH_KEYS = [
  "months.1",
  "months.2",
  "months.3",
  "months.4",
  "months.5",
  "months.6",
  "months.7",
  "months.8",
  "months.9",
  "months.10",
  "months.11",
  "months.12",
] as const;

/** Quantities arrive as plain numbers with a separate `unit` field. */
export function formatQty(
  t: TFunction,
  value: number | null | undefined,
  unit?: string | null,
): string {
  if (value === null || value === undefined) return t("common.notAvailable");
  const rounded = Math.round(value * 10) / 10;
  return `${rounded.toLocaleString(NUMBER_LOCALE)}${unit ? ` ${unit}` : ""}`;
}

export function formatSignedQty(
  t: TFunction,
  value: number | null | undefined,
  unit?: string | null,
): string {
  if (value === null || value === undefined) return t("common.notAvailable");
  return `${value > 0 ? "+" : ""}${formatQty(t, value, unit)}`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return (Math.round(value * 10) / 10).toLocaleString(NUMBER_LOCALE);
}

export function monthLabel(t: TFunction, month: number): string {
  const key = MONTH_KEYS[month - 1];
  return key ? t(key) : String(month);
}

/** "June", "June–July", or "June, August, October" for a set of month numbers. */
export function monthRangeLabel(t: TFunction, months: number[]): string {
  if (months.length === 0) return t("common.notAvailable");
  const sorted = [...months].sort((a, b) => a - b);
  const first = sorted[0] as number;
  const last = sorted[sorted.length - 1] as number;
  if (sorted.length === 1) return monthLabel(t, first);
  const isContiguous = sorted.every((m, i) => m === first + i);
  if (isContiguous) return `${monthLabel(t, first)}–${monthLabel(t, last)}`;
  return sorted.map((month) => monthLabel(t, month)).join(", ");
}

/** `growing_period_weeks` is a [min, max] pair from the API. */
export function weeksRangeLabel(t: TFunction, weeks: number[]): string {
  const min = weeks[0];
  const max = weeks[weeks.length - 1];
  if (min === undefined || max === undefined) return t("common.notAvailable");
  return min === max ? t("format.weeks", { count: min }) : t("format.weeksRange", { min, max });
}

/** ISO date from `next_7_days[].date` → short weekday in the active language. */
export function weekdayLabel(isoDate: string, language: SupportedLanguage): string {
  const date = new Date(`${isoDate}T00:00:00`);
  if (Number.isNaN(date.getTime())) return isoDate;
  return date.toLocaleDateString(localeOf(language), { weekday: "short" });
}

export function formatTemp(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value)}°C`;
}

export function formatPct(value: number | null | undefined): string {
  return value === null || value === undefined ? "—" : `${Math.round(value)}%`;
}
