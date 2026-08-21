import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

/**
 * Built from the API's `crop_market_data` figures carried on each recommendation
 * item (`expected_demand_qty` / `expected_supply_qty` / `demand_gap`).
 *
 * There is no demand *history* chart here: the API exposes only the latest market
 * row per crop (`get_market_data` … ORDER BY year DESC LIMIT 1), so a multi-season
 * trend line would have to be invented. It needs a backend endpoint returning the
 * `crop_market_data` series before it can come back.
 */
export interface DemandSupplyRow {
  crop: string;
  demand: number;
  supply: number;
  gap: number;
}

const axisProps = {
  stroke: "var(--color-muted-foreground)",
  fontSize: 12,
  tickLine: false,
  axisLine: false,
} as const;

const tooltipStyle = {
  contentStyle: {
    background: "var(--color-card)",
    border: "1px solid var(--color-border)",
    borderRadius: "10px",
    fontSize: "12px",
    color: "var(--color-foreground)",
  },
} as const;

function compactTick(value: number): string {
  if (Math.abs(value) >= 1_000_000) return `${Math.round(value / 100_000) / 10}M`;
  if (Math.abs(value) >= 1000) return `${Math.round(value / 1000)}k`;
  return String(value);
}

export function DemandSupplyChart({ data, unit }: { data: DemandSupplyRow[]; unit: string }) {
  const { t } = useTranslation();

  return (
    <div>
      <div className="h-72 w-full" role="img" aria-label={describe(t, data, unit)}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -4, bottom: 0 }} barGap={6}>
            <CartesianGrid vertical={false} stroke="var(--color-border)" />
            <XAxis dataKey="crop" {...axisProps} />
            <YAxis {...axisProps} tickFormatter={compactTick} />
            <Tooltip
              {...tooltipStyle}
              formatter={(v: number, n: string) => [
                t("chart.tooltipValue", { value: v.toLocaleString("en-IN"), unit }),
                n,
              ]}
              cursor={{ fill: "var(--color-muted)" }}
            />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            <Bar
              dataKey="demand"
              name={t("metrics.expectedDemand")}
              fill="var(--color-primary)"
              radius={[6, 6, 0, 0]}
            />
            <Bar
              dataKey="supply"
              name={t("metrics.expectedSupply")}
              fill="var(--color-harvest)"
              radius={[6, 6, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {data.map((row) => {
          const positive = row.gap > 0;
          return (
            <li
              key={row.crop}
              className="flex items-center justify-between gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm"
            >
              <span className="font-medium text-foreground">{row.crop}</span>
              <span
                className={
                  positive ? "font-semibold text-success" : "font-semibold text-destructive"
                }
              >
                {positive
                  ? t("chart.gapOpportunity", { gap: row.gap.toLocaleString("en-IN"), unit })
                  : t("chart.gapOversupply", { gap: row.gap.toLocaleString("en-IN"), unit })}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function describe(t: TFunction, data: DemandSupplyRow[], unit: string): string {
  const rows = data.map((d) =>
    t("chart.ariaRow", { crop: d.crop, demand: d.demand, supply: d.supply, gap: d.gap, unit }),
  );
  return [t("chart.aria"), ...rows].join(" ");
}
