import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Droplets, Loader2, MapPin, Sprout } from "lucide-react";
import { toast } from "sonner";

import { useFarm } from "@/lib/farm-store";
import { MONTHS } from "@/lib/constants";
import {
  useCropRecommendationMutation,
  useCrops,
  useDistricts,
  useStates,
} from "@/services/queries";
import { ErrorState, LoadingState } from "@/components/kheti/primitives";

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
  "mt-2 w-full rounded-lg border border-border bg-input px-4 py-3 text-base text-foreground transition-colors focus:border-primary disabled:cursor-not-allowed disabled:text-muted-foreground";

function FarmerInput() {
  const { farmer, setFarmer, setRecommendation } = useFarm();
  const navigate = useNavigate();
  const [landError, setLandError] = useState<string | null>(null);

  const states = useStates();
  const districts = useDistricts(farmer.stateId);
  const crops = useCrops();
  const recommend = useCropRecommendationMutation();

  // Default to the first state the API returns rather than a hardcoded id, so
  // this works against any seeded database.
  useEffect(() => {
    if (farmer.stateId === null && states.data && states.data.length > 0) {
      setFarmer({ stateId: states.data[0]?.id ?? null });
    }
  }, [farmer.stateId, states.data, setFarmer]);

  // Keep the district valid for the selected state.
  useEffect(() => {
    if (!districts.data) return;
    const stillValid = districts.data.some((d) => d.id === farmer.districtId);
    if (!stillValid) setFarmer({ districtId: districts.data[0]?.id ?? null });
  }, [districts.data, farmer.districtId, setFarmer]);

  const referenceError = states.error ?? districts.error ?? crops.error;
  const referenceLoading = states.isPending || districts.isPending || crops.isPending;
  const activeStep = recommend.isPending ? 4 : 3;

  function submit(event: React.FormEvent) {
    event.preventDefault();

    if (farmer.districtId === null) {
      toast.error("Select a district first");
      return;
    }
    if (!Number.isFinite(farmer.landAcres) || farmer.landAcres <= 0 || farmer.landAcres > 500) {
      setLandError("Please enter land between 0.1 and 500 acres.");
      return;
    }
    setLandError(null);

    recommend.mutate(
      {
        district_id: farmer.districtId,
        land_area_acres: farmer.landAcres,
        irrigation_available: farmer.irrigation,
        previous_crop_id: farmer.previousCropId,
        sowing_month: farmer.sowingMonth,
      },
      {
        onSuccess: (result) => {
          setRecommendation(result);
          if (result.recommendations.length === 0) {
            toast.warning("No eligible crops found", {
              description: `The crop calendar has no entry for ${result.district.name} in this sowing month.`,
            });
          } else {
            toast.success("Farm analysed", { description: "Showing your top crop opportunities." });
          }
          navigate({ to: "/recommendations" });
        },
      },
    );
  }

  const districtName = districts.data?.find((d) => d.id === farmer.districtId)?.name;
  const stateName = states.data?.find((s) => s.id === farmer.stateId)?.name;

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 md:px-6 md:py-12">
      <div className="min-w-0">
        <h1 className="text-2xl font-extrabold text-foreground md:text-3xl">
          Let's understand your farm.
        </h1>
        <p className="mt-2 text-muted-foreground">
          Five short questions. We use them to check season rules, weather and demand for your
          district.
        </p>
      </div>

      {/* Progress */}
      <ol className="mt-6 grid grid-cols-4 gap-2" aria-label="Progress">
        {STEPS.map((step, i) => {
          const done = i + 1 <= activeStep;
          return (
            <li key={step} className="min-w-0">
              <div
                className={`h-1.5 rounded-full ${done ? "bg-primary" : "bg-border"}`}
                aria-hidden
              />
              <p
                className={`mt-2 truncate text-xs font-semibold ${done ? "text-primary" : "text-muted-foreground"}`}
              >
                {i + 1} {step}
              </p>
            </li>
          );
        })}
      </ol>

      {recommend.isPending ? (
        <div className="surface-card mt-8 flex flex-col items-center gap-4 p-10 text-center">
          <Loader2 className="h-9 w-9 animate-spin text-primary" aria-hidden />
          <h2 className="text-xl font-bold text-foreground" role="status">
            Analyzing your farm...
          </h2>
          <p className="max-w-sm text-sm text-muted-foreground">
            Checking crop season, demand, weather and supply conditions.
          </p>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-8 space-y-4">
          {referenceError && (
            <ErrorState
              error={referenceError}
              onRetry={() => {
                void states.refetch();
                void districts.refetch();
                void crops.refetch();
              }}
            />
          )}

          {/* Step 1: location */}
          <fieldset className="surface-card p-5 md:p-6">
            <legend className="px-1 text-base font-bold text-foreground">
              Where is your farm?
            </legend>
            {referenceLoading ? (
              <div className="mt-3">
                <LoadingState label="Loading states and districts…" />
              </div>
            ) : (
              <>
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  <div>
                    <label className={labelCls} htmlFor="state">
                      State
                    </label>
                    <select
                      id="state"
                      className={controlCls}
                      value={farmer.stateId ?? ""}
                      onChange={(e) =>
                        setFarmer({
                          stateId: e.target.value ? Number(e.target.value) : null,
                          districtId: null,
                        })
                      }
                    >
                      {(states.data ?? []).map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.name}
                        </option>
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
                      value={farmer.districtId ?? ""}
                      onChange={(e) =>
                        setFarmer({ districtId: e.target.value ? Number(e.target.value) : null })
                      }
                    >
                      {(districts.data ?? []).map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name}
                          {d.also_known_as ? ` (${d.also_known_as})` : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                {districtName && stateName && (
                  <p className="mt-4 inline-flex items-center gap-2 rounded-lg border border-border bg-muted/60 px-3 py-2 text-sm font-medium text-foreground">
                    <MapPin className="h-4 w-4 text-primary" aria-hidden />
                    {districtName}, {stateName}
                  </p>
                )}
              </>
            )}
          </fieldset>

          {/* Step 2: land + irrigation */}
          <fieldset className="surface-card p-5 md:p-6">
            <legend className="px-1 text-base font-bold text-foreground">
              Your land and water
            </legend>
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
                <p
                  id="land-help"
                  className={`mt-2 text-xs ${landError ? "text-destructive" : "text-muted-foreground"}`}
                >
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
                  disabled={crops.isPending}
                  value={farmer.previousCropId ?? ""}
                  onChange={(e) =>
                    setFarmer({ previousCropId: e.target.value ? Number(e.target.value) : null })
                  }
                >
                  <option value="">Not sure / first season</option>
                  {(crops.data ?? []).map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
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
                  onChange={(e) => setFarmer({ sowingMonth: Number(e.target.value) })}
                >
                  {MONTHS.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </fieldset>

          {recommend.isError && (
            <ErrorState error={recommend.error} onRetry={() => recommend.reset()} />
          )}

          <button
            type="submit"
            disabled={farmer.districtId === null || referenceLoading}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-6 py-4 text-base font-semibold text-primary-foreground shadow-card transition-colors hover:bg-primary-dark active:bg-primary-dark disabled:bg-muted disabled:text-muted-foreground sm:w-auto"
          >
            <Sprout className="h-5 w-5" aria-hidden /> Find Best Crops
          </button>
        </form>
      )}
    </div>
  );
}
