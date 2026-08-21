import type { ReactNode } from "react";
import { Trans, useTranslation } from "react-i18next";
import {
  AlertTriangle,
  BookOpen,
  Check,
  CircleAlert,
  Info,
  KeyRound,
  Loader2,
  ShieldCheck,
} from "lucide-react";

import { ApiError } from "@/services/api";
import type { RiskLevel } from "@/services/api";
import { cn } from "@/lib/utils";

/* ---------------- Badges ---------------- */

export function DemoDataBadge({ label, className }: { label?: string; className?: string }) {
  const { t } = useTranslation();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground",
        className,
      )}
    >
      <Info className="h-3 w-3" aria-hidden />
      {label ?? t("badges.demoData")}
    </span>
  );
}

/**
 * Shown against anything the API flags as not human-verified —
 * `agronomic_guidance.is_verified === false` or RAG's `used_placeholder_data`.
 */
export function UnverifiedBadge({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/40 bg-warning/10 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-warning">
      <AlertTriangle className="h-3 w-3" aria-hidden />
      {label ?? t("badges.unverified")}
    </span>
  );
}

/* ---------------- Section shell ---------------- */

export function Section({
  title,
  description,
  action,
  children,
  className,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("surface-card p-5 md:p-6", className)}>
      <div className="mb-4 grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-foreground md:text-xl">{title}</h2>
          {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/* ---------------- Async states ---------------- */

export function LoadingState({ label }: { label?: string }) {
  const { t } = useTranslation();
  return (
    <div
      className="flex items-center justify-center gap-3 rounded-lg border border-border bg-muted/40 px-4 py-8 text-sm font-medium text-muted-foreground"
      role="status"
    >
      <Loader2 className="h-4 w-4 animate-spin text-primary" aria-hidden />
      {label ?? t("common.loading")}
    </div>
  );
}

/**
 * An empty API response is usually a real state in this system (the batch ML job
 * hasn't run, no forecast rows exist yet), so it gets an explanation rather than
 * a blank panel.
 */
export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/30 px-4 py-8 text-center">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {detail && <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">{detail}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/**
 * 401/403 gets its own panel: the fix is a configuration change, not a retry.
 * Everything else falls through to the generic error message.
 */
export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation();

  if (error instanceof ApiError && error.isAuthError) {
    return (
      <div className="rounded-lg border border-warning/40 bg-warning/5 p-4">
        <p className="flex items-start gap-2 text-sm font-semibold text-foreground">
          <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
          {t("states.authErrorTitle")}
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          {t("states.authErrorReply", { message: error.message })}
        </p>
        <p className="mt-2 text-sm text-muted-foreground">
          <Trans
            i18nKey="states.authErrorDetail"
            components={{ code: <code className="rounded bg-muted px-1 py-0.5 text-xs" /> }}
          />
        </p>
      </div>
    );
  }

  const message = error instanceof Error ? error.message : t("states.errorGeneric");
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4">
      <p className="flex items-start gap-2 text-sm font-semibold text-foreground">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-destructive" aria-hidden />
        {t("states.errorTitle")}
      </p>
      <p className="mt-2 text-sm text-muted-foreground">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-lg border border-border bg-card px-3 py-2 text-sm font-semibold text-foreground hover:bg-muted"
        >
          {t("common.tryAgain")}
        </button>
      )}
    </div>
  );
}

/* ---------------- Risk badge ---------------- */

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  const { t } = useTranslation();
  const map = {
    Low: {
      cls: "border-success/40 bg-success/10 text-success",
      Icon: ShieldCheck,
      labelKey: "risk.low",
    },
    Medium: {
      cls: "border-warning/40 bg-warning/10 text-warning",
      Icon: AlertTriangle,
      labelKey: "risk.medium",
    },
    High: {
      cls: "border-destructive/40 bg-destructive/10 text-destructive",
      Icon: CircleAlert,
      labelKey: "risk.high",
    },
  } as const;
  const { cls, Icon, labelKey } = map[risk];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
        cls,
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden />
      {t(labelKey)}
    </span>
  );
}

export function Pill({
  children,
  tone = "neutral",
  icon: Icon,
}: {
  children: ReactNode;
  tone?: "neutral" | "primary" | "harvest" | "info" | "success";
  icon?: React.ComponentType<{ className?: string }>;
}) {
  const tones = {
    neutral: "border-border bg-muted text-muted-foreground",
    primary: "border-primary/30 bg-primary/10 text-primary",
    harvest: "border-harvest/40 bg-harvest-soft/25 text-foreground",
    info: "border-info/30 bg-info/10 text-info",
    success: "border-success/30 bg-success/10 text-success",
  } as const;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
        tones[tone],
      )}
    >
      {Icon && <Icon className="h-3.5 w-3.5" aria-hidden />}
      {children}
    </span>
  );
}

/* ---------------- Confidence ---------------- */

/**
 * `basis` is the API's own `confidence_basis` string — it names the data that
 * produced the number (years of ACTUAL history, weather availability, calendar
 * coverage), so it is shown verbatim when available.
 */
export function ConfidenceIndicator({
  value,
  basis,
  compact = false,
}: {
  value: number;
  basis?: string | undefined;
  compact?: boolean | undefined;
}) {
  const { t } = useTranslation();
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium text-muted-foreground">{t("confidence.label")}</span>
        <span className="text-sm font-bold text-foreground">{value}%</span>
      </div>
      <div
        className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={t("confidence.aria", { value })}
      >
        <div
          className="h-full rounded-full bg-primary-light transition-[width] duration-500"
          style={{ width: `${value}%` }}
        />
      </div>
      {!compact && (
        <>
          {basis && (
            <p className="mt-2 text-xs font-medium text-foreground">
              {t("confidence.basis", { basis })}
            </p>
          )}
          <p className="mt-1 text-xs text-muted-foreground">{t("confidence.note")}</p>
        </>
      )}
    </div>
  );
}

/* ---------------- Opportunity score ring ---------------- */

export function OpportunityScore({ value, size = 132 }: { value: number; size?: number }) {
  const { t } = useTranslation();
  const stroke = size >= 120 ? 11 : 9;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const label =
    value >= 80
      ? t("opportunity.veryHigh")
      : value >= 70
        ? t("opportunity.high")
        : value >= 55
          ? t("opportunity.moderate")
          : t("opportunity.low");

  return (
    <figure className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={t("opportunity.aria", { value, label })}
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--color-muted)"
            strokeWidth={stroke}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke="var(--color-primary)"
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c - (c * value) / 100}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: "stroke-dashoffset 700ms cubic-bezier(0.22,1,0.36,1)" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className={cn(
              "font-bold leading-none text-foreground",
              size >= 120 ? "text-3xl" : "text-2xl",
            )}
          >
            {value}%
          </span>
          {size >= 120 && (
            <span className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("opportunity.label")}
            </span>
          )}
        </div>
      </div>
      <figcaption className="text-xs font-medium text-primary">{label}</figcaption>
    </figure>
  );
}

/* ---------------- Metric ---------------- */

export function Metric({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "positive" | "negative" | "harvest";
}) {
  const tones = {
    neutral: "text-foreground",
    positive: "text-success",
    negative: "text-destructive",
    harvest: "text-foreground",
  } as const;
  return (
    <div className="rounded-lg border border-border bg-muted/50 p-3">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className={cn("mt-1 text-lg font-bold", tones[tone])}>{value}</dd>
      {hint && <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/* ---------------- Sources ---------------- */

/**
 * Normalized shape: the API returns sources in two flavours — `SourceRef`
 * (crop detail) and `RagSourceRef` (RAG) — so callers map into this.
 */
export interface SourceDisplay {
  id: number;
  title: string;
  detail: string | null;
}

export function SourceList({ sources }: { sources: SourceDisplay[] }) {
  const { t } = useTranslation();

  if (sources.length === 0) {
    return <p className="text-sm text-muted-foreground">{t("sources.none")}</p>;
  }
  return (
    <ul className="grid gap-3 sm:grid-cols-3">
      {sources.map((s) => (
        <li key={s.id} className="rounded-lg border border-border bg-muted/50 p-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <BookOpen className="h-4 w-4 shrink-0 text-primary" aria-hidden />
            <span className="min-w-0 break-words">{s.title}</span>
          </div>
          {s.detail && <p className="mt-1 text-xs text-muted-foreground">{s.detail}</p>}
        </li>
      ))}
    </ul>
  );
}

/* ---------------- Decision trace ---------------- */

export function DecisionTrace({ items }: { items: { title: string; detail: string }[] }) {
  return (
    <ol className="space-y-3">
      {items.map((item) => (
        <li key={item.title} className="flex gap-3">
          <span className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Check className="h-3.5 w-3.5" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">{item.title}</p>
            <p className="text-sm text-muted-foreground">{item.detail}</p>
          </div>
        </li>
      ))}
    </ol>
  );
}

/* ---------------- Disclaimer ---------------- */

export function Disclaimer({ children }: { children: ReactNode }) {
  return (
    <p className="flex gap-2 rounded-lg border border-border bg-muted/60 p-3 text-xs leading-relaxed text-muted-foreground">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" aria-hidden />
      <span>{children}</span>
    </p>
  );
}
