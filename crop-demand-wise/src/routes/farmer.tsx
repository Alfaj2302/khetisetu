import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Droplets, Loader2, MapPin, Sprout } from "lucide-react";
import { toast } from "sonner";
import { useFarm } from "@/lib/farm-store";
import { CROP_OPTIONS, DISTRICTS, MONTHS, STATES } from "@/lib/mockData";
import { DemoDataBadge } from "@/components/kheti/primitives";

export const Route = createFileRoute("/farmer")({
  head: () => ({
    meta: [
      { title: "Tell us about your farm | KhetiSetu" },
      {
        name: "description",
        content:
          "Share your location, land size, irrigation and sowing plan so KhetiSetu can suggest crop opportunities.",
      },
      { property: "og:title", content: "Tell us about your farm | KhetiSetu" },
      { property: "og:description", content: "Simple farm inputs, clear crop opportunities." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: FarmerInput,
});

const STEPS = ["Farm", "Conditions", "Crop", "Results"];

const labelCls = "block text-sm font-semibold text-foreground";
const controlCls =
  "mt-2 w-full rounded-lg border border-border bg-input px-4 py-3 text-base text-foreground transition-colors focus:border-primary";

function FarmerInput() {
  const { farmer, setFarmer, setHasAnalyzed } = useFarm();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [landError, setLandError] = useState<string | null>(null);

  const districts = DISTRICTS[farmer.state] ?? [];
  const activeStep = loading ? 4 : 3;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!Number.isFinite(farmer.landAcres) || farmer.landAcres <= 0 || farmer.landAcres > 500) {
      setLandError("Please enter land between 0.1 and 500 acres.");
      return;
    }
    setLandError(null);
    setLoading(true);
    window.setTimeout(() => {
      setHasAnalyzed(true);
      toast.success("Farm analysed", { description: "Showing your top crop opportunities." });
      navigate({ to: "/recommendations" });
    }, 1600);
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 md:px-6 md:py-12">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">Let's understand your farm.</h1>
          <p className="mt-2 text-muted-foreground">
            Five short questions. We use them to check season rules, weather and demand for your district.
          </p>
        </div>
        <DemoDataBadge />
      </div>

      {/* Progress */}
      <ol className="mt-6 grid grid-cols-4 gap-2" aria-label="Progress">
        {STEPS.map((s, i) => {
          const done = i + 1 <= activeStep;
          return (
            <li key={s} className="min-w-0">
              <div className={`h-1.5 rounded-full ${done ? "bg-primary" : "bg-border"}`} aria-hidden />
              <p className={`mt-2 truncate text-xs font-semibold ${done ? "text-primary" : "text-muted-foreground"}`}>
                {i + 1} {s}
              </p>
            </li>
          );
        })}
      </ol>

      {loading ? (
        <div className="surface-card mt-8 flex flex-col items-center gap-4 p-10 text-center">
          <Loader2 className="h-9 w-9 animate-spin text-primary" aria-hidden />
          <h2 className="text-xl font-bold text-foreground" role="status">
            Analyzing your farm...
          </h2>
          <p className="max-w-sm text-sm text-muted-foreground">
            Checking crop season, demand, weather and supply conditions.
          </p>
          <ul className="mt-2 w-full max-w-sm space-y-2 text-left text-sm text-muted-foreground">
            {["Reading your farm context", "Matching the crop calendar", "Comparing demand and supply"].map((t) => (
              <li key={t} className="rounded-lg border border-border bg-muted/50 px-3 py-2">
                {t}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-8 space-y-4">
          {/* Step 1: location */}
          <fieldset className="surface-card p-5 md:p-6">
            <legend className="px-1 text-base font-bold text-foreground">Where is your farm?</legend>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelCls} htmlFor="state">
                  State
                </label>
                <select
                  id="state"
                  className={controlCls}
                  value={farmer.state}
                  onChange={(e) => {
                    const state = e.target.value;
                    const first = DISTRICTS[state]?.[0] ?? "";
                    setFarmer({ state, district: first });
                  }}
                >
                  {STATES.map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelCls} htmlFor="district">
                  District
                </label>
                <select
                  id="district"
                  className={controlCls}
                  value={farmer.district}
                  onChange={(e) => setFarmer({ district: e.target.value })}
                >
                  {districts.map((d) => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
              </div>
            </div>
            <p className="mt-4 inline-flex items-center gap-2 rounded-lg border border-border bg-muted/60 px-3 py-2 text-sm font-medium text-foreground">
              <MapPin className="h-4 w-4 text-primary" aria-hidden />
              {farmer.district}, {farmer.state}
            </p>
          </fieldset>

          {/* Step 2: land + irrigation */}
          <fieldset className="surface-card p-5 md:p-6">
            <legend className="px-1 text-base font-bold text-foreground">Your land and water</legend>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelCls} htmlFor="land">
                  How much land do you have?
                </label>
                <div className="mt-2 flex items-stretch overflow-hidden rounded-lg border border-border bg-input focus-within:border-primary">
                  <input
                    id="land"
                    type="number"
                    inputMode="decimal"
                    min={0.1}
                    max={500}
                    step={0.5}
                    value={farmer.landAcres}
                    aria-describedby="land-help"
                    aria-invalid={landError ? true : undefined}
                    onChange={(e) => setFarmer({ landAcres: Number(e.target.value) })}
                    className="w-full bg-transparent px-4 py-3 text-base text-foreground outline-none"
                  />
                  <span className="flex items-center border-l border-border bg-muted px-4 text-sm font-semibold text-muted-foreground">
                    Acres
                  </span>
                </div>
                <p id="land-help" className={`mt-2 text-xs ${landError ? "text-destructive" : "text-muted-foreground"}`}>
                  {landError ?? "Enter the area you plan to sow, in acres."}
                </p>
              </div>

              <div>
                <span className={labelCls} id="irrigation-label">
                  Is irrigation available?
                </span>
                <div
                  role="radiogroup"
                  aria-labelledby="irrigation-label"
                  className="mt-2 grid grid-cols-2 gap-2 rounded-lg border border-border bg-input p-1"
                >
                  {[true, false].map((val) => (
                    <button
                      key={String(val)}
                      type="button"
                      role="radio"
                      aria-checked={farmer.irrigation === val}
                      onClick={() => setFarmer({ irrigation: val })}
                      className={`inline-flex items-center justify-center gap-2 rounded-md px-4 py-3 text-sm font-semibold transition-colors ${
                        farmer.irrigation === val
                          ? "bg-primary text-primary-foreground"
                          : "text-muted-foreground hover:bg-muted"
                      }`}
                    >
                      <Droplets className="h-4 w-4" aria-hidden />
                      {val ? "Yes" : "No"}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </fieldset>

          {/* Step 3: crop + sowing */}
          <fieldset className="surface-card p-5 md:p-6">
            <legend className="px-1 text-base font-bold text-foreground">Your crop plan</legend>
            <div className="mt-3 grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelCls} htmlFor="prev-crop">
                  What did you grow previously?
                </label>
                <select
                  id="prev-crop"
                  className={controlCls}
                  value={farmer.previousCrop}
                  onChange={(e) => setFarmer({ previousCrop: e.target.value })}
                >
                  {CROP_OPTIONS.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className={labelCls} htmlFor="sowing">
                  When are you planning to sow?
                </label>
                <select
                  id="sowing"
                  className={controlCls}
                  value={farmer.sowingMonth}
                  onChange={(e) => setFarmer({ sowingMonth: e.target.value })}
                >
                  {MONTHS.map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </div>
            </div>
          </fieldset>

          <button
            type="submit"
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-6 py-4 text-base font-semibold text-primary-foreground shadow-card transition-colors hover:bg-primary-dark active:bg-primary-dark sm:w-auto"
          >
            <Sprout className="h-5 w-5" aria-hidden /> Find Best Crops
          </button>
        </form>
      )}
    </div>
  );
}
