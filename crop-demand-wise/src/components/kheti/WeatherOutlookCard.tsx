import { CloudRain, CloudSun, Droplets, Thermometer } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { WeatherOutlook } from "@/lib/mockData";
import { Section, DemoDataBadge } from "./primitives";

export function WeatherOutlookCard({ weather }: { weather: WeatherOutlook }) {
  const stats = [
    { icon: CloudRain, label: "Rainfall", value: weather.rainfall },
    { icon: Thermometer, label: "Temperature", value: `${weather.temperature}°C` },
    { icon: Droplets, label: "Humidity", value: `${weather.humidity}%` },
    { icon: CloudSun, label: "Forecast", value: weather.forecast },
  ];

  return (
    <Section
      title={`${weather.district} weather outlook`}
      description="Expected conditions for your sowing window."
      action={<DemoDataBadge />}
    >
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(({ icon: Icon, label, value }) => (
          <div key={label} className="rounded-lg border border-border bg-muted/50 p-3">
            <dt className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Icon className="h-4 w-4 text-primary" aria-hidden />
              {label}
            </dt>
            <dd className="mt-1 text-lg font-bold text-foreground">{value}</dd>
          </div>
        ))}
      </dl>

      <h3 className="mt-5 text-sm font-semibold text-foreground">Next 7 days</h3>
      <ul className="mt-2 flex gap-2 overflow-x-auto pb-2">
        {weather.days.map((d) => (
          <li
            key={d.day}
            className="min-w-[92px] shrink-0 rounded-lg border border-border bg-card p-3 text-center"
          >
            <p className="text-xs font-semibold text-muted-foreground">{d.day}</p>
            <p className="mt-1 text-lg font-bold text-foreground">{d.temp}°</p>
            <p className="mt-1 text-xs text-info">Rain {d.rainChance}%</p>
          </li>
        ))}
      </ul>

      <Link
        to="/whatif"
        className="mt-4 inline-flex w-full items-center justify-center rounded-lg border border-primary/40 bg-primary/5 px-4 py-3 text-sm font-semibold text-primary transition-colors hover:bg-primary/10 sm:w-auto"
      >
        Test weather scenario
      </Link>
    </Section>
  );
}
