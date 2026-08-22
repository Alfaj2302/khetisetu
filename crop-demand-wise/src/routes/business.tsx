import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AlertTriangle, CircleAlert, Truck, X } from "lucide-react";
import { Trans, useTranslation } from "react-i18next";

import {
  useBusinessAlerts,
  useBusinessDashboard,
  useBusinessForecast,
  useBusinessInventory,
  useBusinessTransfers,
  useDistricts,
  useProducts,
  useSeasons,
} from "@/services/queries";
import { formatNumber, monthLabel, referenceLabel } from "@/lib/format";
import {
  Disclaimer,
  EmptyState,
  ErrorState,
  LoadingState,
  Metric,
  Pill,
  Section,
} from "@/components/kheti/primitives";
import { tFor } from "@/lib/i18n";
import { readLanguage } from "@/lib/i18n/language";

export const Route = createFileRoute("/business")({
  head: () => {
    const t = tFor(readLanguage());
    return {
      meta: [
        { title: t("business.meta.title") },
        { name: "description", content: t("business.meta.description") },
        { property: "og:title", content: t("business.meta.ogTitle") },
        { property: "og:description", content: t("business.meta.ogDescription") },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary_large_image" },
      ],
    };
  },
  component: Business,
});

type PanelKey = "forecast" | "inventory" | "transfers" | null;

const controlCls =
  "mt-2 w-full rounded-lg border border-border bg-input px-3 py-2.5 text-sm text-foreground focus:border-primary";

function Business() {
  const { t } = useTranslation();
  const [districtId, setDistrictId] = useState<number | null>(null);
  const [seasonId, setSeasonId] = useState<number | null>(null);
  const [year, setYear] = useState(new Date().getFullYear());
  const [panel, setPanel] = useState<PanelKey>(null);

  const districts = useDistricts(null);
  const seasons = useSeasons();
  const products = useProducts();

  useEffect(() => {
    if (districtId === null && districts.data && districts.data.length > 0) {
      setDistrictId(districts.data[0]?.id ?? null);
    }
  }, [districtId, districts.data]);

  useEffect(() => {
    if (seasonId === null && seasons.data && seasons.data.length > 0) {
      setSeasonId(seasons.data[0]?.id ?? null);
    }
  }, [seasonId, seasons.data]);

  // The dashboard endpoint requires all three query params, so hold requests
  // until the selectors have resolved from the reference tables.
  const ready = districtId !== null && seasonId !== null;
  const dashboard = useBusinessDashboard(
    { district_id: districtId ?? 0, season_id: seasonId ?? 0, year },
    ready,
  );
  const forecast = useBusinessForecast({ district_id: districtId, year }, ready);
  const inventory = useBusinessInventory(districtId, ready);
  const transfers = useBusinessTransfers();
  const alerts = useBusinessAlerts(districtId, ready);

  const productName = (productId: number) => {
    const name = products.data?.find((p) => p.id === productId)?.product_name;
    return name ? referenceLabel(t, "products", name) : t("business.productFallback", { id: productId });
  };
  const districtName = (id: number) => {
    const name = districts.data?.find((d) => d.id === id)?.name;
    return name ? referenceLabel(t, "districts", name) : t("business.districtFallback", { id });
  };

  const panelTitle =
    panel === "forecast"
      ? t("business.panels.forecastTitle", {
          district: districtId ? districtName(districtId) : "",
          year,
        })
      : panel === "inventory"
        ? t("business.panels.inventoryTitle", {
            district: districtId ? districtName(districtId) : "",
          })
        : t("business.panels.transfersTitle");

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 md:px-6 md:py-12">
      <div className="min-w-0">
        <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">
          {t("business.title")}
        </h1>
        <p className="mt-2 text-muted-foreground">{t("business.subtitle")}</p>
        {dashboard.data && (
          <div className="mt-3">
            <Pill tone="primary">{referenceLabel(t, "seasons", dashboard.data.season)}</Pill>
          </div>
        )}
      </div>

      {/* Scope selectors */}
      <div className="surface-card mt-6 grid gap-4 p-4 sm:grid-cols-3 md:p-5">
        <div>
          <label className="block text-sm font-semibold text-foreground" htmlFor="b-district">
            {t("fields.district")}
          </label>
          <select
            id="b-district"
            className={controlCls}
            value={districtId ?? ""}
            onChange={(e) => setDistrictId(e.target.value ? Number(e.target.value) : null)}
          >
            {(districts.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {referenceLabel(t, "districts", d.name)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-semibold text-foreground" htmlFor="b-season">
            {t("fields.season")}
          </label>
          <select
            id="b-season"
            className={controlCls}
            value={seasonId ?? ""}
            onChange={(e) => setSeasonId(e.target.value ? Number(e.target.value) : null)}
          >
            {(seasons.data ?? []).map((s) => (
              <option key={s.id} value={s.id}>
                {referenceLabel(t, "seasons", s.name)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-semibold text-foreground" htmlFor="b-year">
            {t("fields.year")}
          </label>
          <input
            id="b-year"
            type="number"
            min={2000}
            max={2100}
            className={controlCls}
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          />
        </div>
      </div>

      {dashboard.isError && (
        <div className="mt-6">
          <ErrorState error={dashboard.error} onRetry={() => void dashboard.refetch()} />
        </div>
      )}

      {dashboard.isPending && ready ? (
        <div className="mt-6">
          <LoadingState label={t("business.loading")} />
        </div>
      ) : dashboard.data ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <Section
            title={t("business.demand.title")}
            description={t("business.demand.description")}
          >
            {dashboard.data.expected_input_demand.length === 0 ? (
              <EmptyState
                title={t("business.demand.emptyTitle")}
                detail={t("business.demand.emptyDetail")}
              />
            ) : (
              <dl className="grid gap-3 sm:grid-cols-3">
                {dashboard.data.expected_input_demand.map((item) => (
                  <Metric
                    key={item.product}
                    label={item.product}
                    value={t("business.quantityWithUnit", {
                      value: formatNumber(item.quantity),
                      unit: item.unit,
                    })}
                  />
                ))}
              </dl>
            )}
          </Section>

          <Section
            title={t("business.intent.title")}
            description={t("business.intent.description")}
          >
            {dashboard.data.farmer_crop_intent.length === 0 ? (
              <EmptyState
                title={t("business.intent.emptyTitle")}
                detail={t("business.intent.emptyDetail")}
              />
            ) : (
              <>
                <ul className="space-y-2">
                  {dashboard.data.farmer_crop_intent.map((item) => {
                    const max = Math.max(
                      ...dashboard.data.farmer_crop_intent.map((entry) => entry.acres),
                      1,
                    );
                    return (
                      <li key={item.crop}>
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-semibold text-foreground">{item.crop}</span>
                          <span className="text-muted-foreground">
                            {t("common.acres", { value: formatNumber(item.acres) })}
                          </span>
                        </div>
                        <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-crop"
                            style={{ width: `${(item.acres / max) * 100}%` }}
                          />
                        </div>
                      </li>
                    );
                  })}
                </ul>
                <p className="mt-3 text-xs text-muted-foreground">{t("business.intent.note")}</p>
              </>
            )}
          </Section>

          <Section
            title={t("business.alerts.title")}
            description={t("business.alerts.description")}
          >
            {alerts.isError ? (
              <ErrorState error={alerts.error} onRetry={() => void alerts.refetch()} />
            ) : (alerts.data ?? []).length === 0 ? (
              <EmptyState
                title={t("business.alerts.emptyTitle")}
                detail={t("business.alerts.emptyDetail")}
              />
            ) : (
              <ul className="space-y-2">
                {(alerts.data ?? []).map((alert, index) => {
                  const isHigh = alert.severity.toLowerCase() === "high";
                  const Icon = isHigh ? CircleAlert : AlertTriangle;
                  return (
                    <li
                      key={`${alert.district}-${alert.product}-${index}`}
                      className={`flex items-start gap-2 rounded-lg border p-3 text-sm ${
                        isHigh
                          ? "border-destructive/40 bg-destructive/5"
                          : "border-warning/40 bg-warning/5"
                      }`}
                    >
                      <Icon
                        className={`mt-0.5 h-4 w-4 shrink-0 ${isHigh ? "text-destructive" : "text-warning"}`}
                        aria-hidden
                      />
                      <span className="text-foreground">
                        <Trans
                          i18nKey="business.alerts.row"
                          values={{
                            district: alert.district,
                            message: alert.message,
                            severity: alert.severity,
                          }}
                          components={{
                            district: <strong />,
                            severity: (
                              <span
                                className={`font-semibold ${isHigh ? "text-destructive" : "text-warning"}`}
                              />
                            ),
                          }}
                        />
                      </span>
                    </li>
                  );
                })}
              </ul>
            )}
          </Section>

          <Section
            title={t("business.action.title")}
            description={t("business.action.description")}
          >
            {dashboard.data.recommended_action === null ? (
              <EmptyState
                title={t("business.action.emptyTitle")}
                detail={t("business.action.emptyDetail")}
              />
            ) : (
              <>
                <p className="text-sm font-semibold text-foreground">
                  {dashboard.data.recommended_action.product}
                </p>
                <dl className="mt-3 grid gap-3 sm:grid-cols-3">
                  <Metric
                    label={t("business.action.forecast")}
                    value={t("business.quantityWithUnit", {
                      value: formatNumber(dashboard.data.recommended_action.forecast),
                      unit: dashboard.data.recommended_action.unit,
                    })}
                  />
                  <Metric
                    label={t("business.action.currentStock")}
                    value={t("business.quantityWithUnit", {
                      value: formatNumber(dashboard.data.recommended_action.current_stock),
                      unit: dashboard.data.recommended_action.unit,
                    })}
                  />
                  <Metric
                    label={t("business.action.safetyStock")}
                    value={t("business.quantityWithUnit", {
                      value: formatNumber(dashboard.data.recommended_action.safety_stock),
                      unit: dashboard.data.recommended_action.unit,
                    })}
                  />
                </dl>
                <p className="mt-4 flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 p-3 text-base font-bold text-primary">
                  <Truck className="h-5 w-5" aria-hidden />
                  {dashboard.data.recommended_action.action}
                  {dashboard.data.recommended_action.recommended_dispatch !== null &&
                    ` ${t("business.quantityWithUnit", {
                      value: formatNumber(dashboard.data.recommended_action.recommended_dispatch),
                      unit: dashboard.data.recommended_action.unit,
                    })}`}
                </p>
              </>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              {(
                [
                  { key: "forecast", labelKey: "business.panels.viewForecast" },
                  { key: "inventory", labelKey: "business.panels.viewInventory" },
                  { key: "transfers", labelKey: "business.panels.viewTransfers" },
                ] as const
              ).map(({ key, labelKey }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setPanel(key)}
                  className="rounded-lg border border-border bg-card px-4 py-3 text-sm font-semibold text-foreground hover:bg-muted"
                >
                  {t(labelKey)}
                </button>
              ))}
            </div>
          </Section>
        </div>
      ) : null}

      <div className="mt-6">
        <Disclaimer>{t("business.disclaimer")}</Disclaimer>
      </div>

      {panel && (
        <div className="fixed inset-0 z-50">
          <button
            type="button"
            aria-label={t("business.panels.closePanel")}
            onClick={() => setPanel(null)}
            className="absolute inset-0 bg-foreground/40"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label={panelTitle}
            className="absolute inset-x-0 bottom-0 max-h-[85vh] overflow-y-auto rounded-t-2xl bg-card p-5 shadow-lift animate-in slide-in-from-bottom sm:inset-y-0 sm:left-auto sm:right-0 sm:max-h-none sm:w-[460px] sm:rounded-none sm:rounded-l-2xl sm:p-6 sm:slide-in-from-right"
          >
            <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
              <h2 className="text-lg font-bold text-foreground">{panelTitle}</h2>
              <button
                type="button"
                onClick={() => setPanel(null)}
                aria-label={t("common.close")}
                className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-muted"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-4">
              {panel === "forecast" &&
                (forecast.isPending ? (
                  <LoadingState />
                ) : forecast.isError ? (
                  <ErrorState error={forecast.error} />
                ) : (forecast.data ?? []).length === 0 ? (
                  <EmptyState
                    title={t("business.panels.forecastEmptyTitle")}
                    detail={t("business.panels.forecastEmptyDetail")}
                  />
                ) : (
                  <dl className="space-y-2">
                    {(forecast.data ?? []).map((row, index) => (
                      <div
                        key={`${row.product_id}-${row.year}-${row.month}-${index}`}
                        className="flex items-center justify-between gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm"
                      >
                        <dt className="min-w-0 text-muted-foreground">
                          {productName(row.product_id)} · {monthLabel(t, row.month)} {row.year}
                        </dt>
                        <dd className="shrink-0 font-semibold text-foreground">
                          {formatNumber(row.predicted_demand)}
                          {row.confidence ? ` · ${row.confidence}` : ""}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ))}

              {panel === "inventory" &&
                (inventory.isPending ? (
                  <LoadingState />
                ) : inventory.isError ? (
                  <ErrorState error={inventory.error} />
                ) : (inventory.data ?? []).length === 0 ? (
                  <EmptyState title={t("business.panels.inventoryEmptyTitle")} />
                ) : (
                  <dl className="space-y-2">
                    {(inventory.data ?? []).map((row, index) => (
                      <div
                        key={`${row.product_id}-${row.batch_no}-${index}`}
                        className="flex items-center justify-between gap-2 rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm"
                      >
                        <dt className="min-w-0 text-muted-foreground">
                          {productName(row.product_id)}
                          {row.batch_no ? ` · ${row.batch_no}` : ""}
                          {row.expiry_date
                            ? ` · ${t("business.panels.expiry", { date: row.expiry_date })}`
                            : ""}
                        </dt>
                        <dd className="shrink-0 font-semibold text-foreground">
                          {formatNumber(row.quantity)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ))}

              {panel === "transfers" &&
                (transfers.isPending ? (
                  <LoadingState />
                ) : transfers.isError ? (
                  <ErrorState error={transfers.error} />
                ) : (transfers.data ?? []).length === 0 ? (
                  <EmptyState
                    title={t("business.panels.transfersEmptyTitle")}
                    detail={t("business.panels.transfersEmptyDetail")}
                  />
                ) : (
                  <ul className="space-y-2">
                    {(transfers.data ?? []).map((row, index) => (
                      <li
                        key={`${row.product_id}-${row.from_district_id}-${row.to_district_id}-${index}`}
                        className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-sm"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="min-w-0 text-muted-foreground">
                            {districtName(row.from_district_id)} →{" "}
                            {districtName(row.to_district_id)}
                          </span>
                          <span className="shrink-0 font-semibold text-foreground">
                            {formatNumber(row.recommended_transfer_qty)}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {productName(row.product_id)} — {row.reason}
                        </p>
                      </li>
                    ))}
                  </ul>
                ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
