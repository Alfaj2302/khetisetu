import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DemandSupplyRow } from "@/lib/mockData";

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

export function DemandSupplyChart({ data }: { data: DemandSupplyRow[] }) {
  return (
    <div>
      <div className="h-72 w-full" role="img" aria-label={demandSupplyDescription(data)}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }} barGap={6}>
            <CartesianGrid vertical={false} stroke="var(--color-border)" />
            <XAxis dataKey="crop" {...axisProps} />
            <YAxis {...axisProps} tickFormatter={(v: number) => `${v / 1000}k`} />
            <Tooltip {...tooltipStyle} formatter={(v: number, n: string) => [`${v.toLocaleString("en-IN")} q`, n]} cursor={{ fill: "var(--color-muted)" }} />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            <Bar dataKey="demand" name="Expected demand" fill="var(--color-primary)" radius={[6, 6, 0, 0]} />
            <Bar dataKey="supply" name="Expected supply" fill="var(--color-harvest)" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2">
        {data.map((row) => {
          const positive = row.gap > 0;
          return (
            <li key={row.crop} className="flex items-center justify-between rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm">
              <span className="font-medium text-foreground">{row.crop}</span>
              <span className={positive ? "font-semibold text-success" : "font-semibold text-destructive"}>
                {positive ? "▲ Opportunity" : "▼ Possible oversupply"} {positive ? "+" : ""}
                {row.gap.toLocaleString("en-IN")} q
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function demandSupplyDescription(data: DemandSupplyRow[]) {
  return (
    "Bar chart comparing expected demand and expected supply. " +
    data
      .map((d) => `${d.crop}: demand ${d.demand} quintals, supply ${d.supply} quintals, gap ${d.gap}`)
      .join(". ")
  );
}

export function DemandTrendChart({
  data,
}: {
  data: { season: string; demand: number; projected?: boolean }[];
}) {
  const historical = data.map((d) => ({ ...d, historical: d.projected ? null : d.demand }));
  const lastHistoricalIndex = data.findIndex((d) => d.projected) - 1;
  const merged = historical.map((d, i) => ({
    ...d,
    projectedLine: d.projected || i === lastHistoricalIndex ? d.demand : null,
  }));

  return (
    <div>
      <div
        className="h-64 w-full"
        role="img"
        aria-label={`Line chart of demand across seasons. ${data.map((d) => `${d.season}: ${d.demand} quintals${d.projected ? " (projected)" : ""}`).join(". ")}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={merged} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--color-border)" />
            <XAxis dataKey="season" {...axisProps} />
            <YAxis {...axisProps} tickFormatter={(v: number) => `${v / 1000}k`} />
            <Tooltip {...tooltipStyle} formatter={(v: number) => [`${v.toLocaleString("en-IN")} q`, "Demand"]} />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            <Line
              type="monotone"
              dataKey="historical"
              name="Historical demand"
              stroke="var(--color-primary)"
              strokeWidth={3}
              dot={{ r: 4 }}
              connectNulls
            />
            <Line
              type="monotone"
              dataKey="projectedLine"
              name="Projected (demo)"
              stroke="var(--color-harvest)"
              strokeWidth={3}
              strokeDasharray="6 6"
              dot={{ r: 4 }}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Solid line = recorded historical demand. Dashed line = projected demo value, not an observed fact.
      </p>
    </div>
  );
}
