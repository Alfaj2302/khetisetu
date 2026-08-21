import { CloudRain, CloudSun, Droplets, Thermometer } from "lucide-react";
import { Link } from "@tanstack/react-router";

import type { WeatherResponse } from "@/services/api";
import { formatPct, formatTemp, weekdayLabel } from "@/lib/format";
import { EmptyState, Section } from "./primitives";

/**
 * `current` is averaged from `weather_history` for the district/month;
 * `next_7_days` reads `weather_forecast`, which is only populated by a live
 * weather-API integration that doesn't exist yet — so an empty strip there is
 * expected, not broken.
 */
export function WeatherOutlookCard({
  weather,
  districtName,
}: {
  weather: WeatherResponse;
  districtName: string;
}) {
  const stats = [
    { icon: CloudRain, label: "Rainfall", value: weather.current.rainfall },
    { icon: Thermometer, label: "Temperature", value: formatTemp(weather.current.temperature_c) },
    { icon: Droplets, label: "Humidity", value: formatPct(weather.current.humidity_pct) },
    { icon: CloudSun, label: "Forecast", value: weather.current.forecast },
  ];

  return (
    <Section
      title={`${districtName} weather outlook`}
      description="Averaged from recorded weather history for your sowing month."
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
      {weather.next_7_days.length > 0 ? (
        <ul className="mt-2 flex gap-2 overflow-x-auto pb-2">
          {weather.next_7_days.map((day) => (
            <li
              key={day.date}
              className="min-w-[92px] shrink-0 rounded-lg border border-border bg-card p-3 text-center"
            >
              <p className="text-xs font-semibold text-muted-foreground">
                {weekdayLabel(day.date)}
              </p>
              <p className="mt-1 text-lg font-bold text-foreground">
                {formatTemp(day.temperature_c)}
              </p>
              <p className="mt-1 text-xs text-info">
                {day.rain_probability_pct === null ? "Rain —" : `Rain ${day.rain_probability_pct}%`}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <div className="mt-2">
          <EmptyState
            title="No daily forecast available"
            detail="Short-range forecasts come from the API's weather_forecast table, which is filled by a live weather integration that isn't connected yet."
          />
        </div>
      )}

      <Link
        to="/whatif"
        className="mt-4 inline-flex w-full items-center justify-center rounded-lg border border-primary/40 bg-primary/5 px-4 py-3 text-sm font-semibold text-primary transition-colors hover:bg-primary/10 sm:w-auto"
      >
        Test weather scenario
      </Link>
    </Section>
  );
}
