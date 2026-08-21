import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { DEFAULT_FARMER, type FarmerProfile } from "./mockData";

interface FarmStore {
  farmer: FarmerProfile;
  setFarmer: (update: Partial<FarmerProfile>) => void;
  hasAnalyzed: boolean;
  setHasAnalyzed: (v: boolean) => void;
}

const FarmContext = createContext<FarmStore | null>(null);

export function FarmProvider({ children }: { children: ReactNode }) {
  const [farmer, setFarmerState] = useState<FarmerProfile>(DEFAULT_FARMER);
  const [hasAnalyzed, setHasAnalyzed] = useState(false);

  const value = useMemo<FarmStore>(
    () => ({
      farmer,
      setFarmer: (update) => setFarmerState((prev) => ({ ...prev, ...update })),
      hasAnalyzed,
      setHasAnalyzed,
    }),
    [farmer, hasAnalyzed],
  );

  return <FarmContext.Provider value={value}>{children}</FarmContext.Provider>;
}

export function useFarm(): FarmStore {
  const ctx = useContext(FarmContext);
  if (!ctx) throw new Error("useFarm must be used inside FarmProvider");
  return ctx;
}
