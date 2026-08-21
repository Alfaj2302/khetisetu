/**
 * The farmer's form input, plus the last ranking the API returned for it.
 *
 * Everything the API needs is an id (`district_id`, `previous_crop_id`,
 * `sowing_month` as 1-12), so that is what this holds — display names come from
 * the reference queries at render time.
 *
 * The ranking response is kept here rather than refetched on /recommendations
 * because POST /farmer/crop-recommendation also writes a `farmer_crop_intent`
 * row: refetching it on every visit to the results screen would record a
 * duplicate row each time.
 */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

import type { CropRecommendationResponse } from "@/services/api";

export interface FarmerProfile {
  stateId: number | null;
  districtId: number | null;
  landAcres: number;
  irrigation: boolean;
  previousCropId: number | null;
  /** 1-12, matching the API's `sowing_month`. */
  sowingMonth: number;
}

/**
 * Land/irrigation/month get sensible starting values; the ids start null and are
 * filled from /states and /districts once those load, so nothing here hardcodes
 * a row id that may not exist in the caller's database.
 */
export const DEFAULT_FARMER: FarmerProfile = {
  stateId: null,
  districtId: null,
  landAcres: 5,
  irrigation: true,
  previousCropId: null,
  sowingMonth: 6,
};

interface FarmStore {
  farmer: FarmerProfile;
  setFarmer: (update: Partial<FarmerProfile>) => void;
  /** Null until the farmer has submitted the form at least once. */
  recommendation: CropRecommendationResponse | null;
  setRecommendation: (result: CropRecommendationResponse | null) => void;
}

const FarmContext = createContext<FarmStore | null>(null);

export function FarmProvider({ children }: { children: ReactNode }) {
  const [farmer, setFarmerState] = useState<FarmerProfile>(DEFAULT_FARMER);
  const [recommendation, setRecommendation] = useState<CropRecommendationResponse | null>(null);

  const value = useMemo<FarmStore>(
    () => ({
      farmer,
      setFarmer: (update) => setFarmerState((prev) => ({ ...prev, ...update })),
      recommendation,
      setRecommendation,
    }),
    [farmer, recommendation],
  );

  return <FarmContext.Provider value={value}>{children}</FarmContext.Provider>;
}

export function useFarm(): FarmStore {
  const ctx = useContext(FarmContext);
  if (!ctx) throw new Error("useFarm must be used inside FarmProvider");
  return ctx;
}
