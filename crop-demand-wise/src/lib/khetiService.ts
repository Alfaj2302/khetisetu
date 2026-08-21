/**
 * Mock service layer.
 * Every function returns local demo data. Replace the bodies with real fetch
 * calls (POST /recommend, GET /crops, POST /scenario, POST /ask) later —
 * the signatures and types stay the same.
 */
import {
  AGRI_BUSINESS,
  DEMAND_SUPPLY,
  MOCK_ANSWERS,
  RECOMMENDATIONS,
  SOURCES,
  WEATHER,
  type CropRecommendation,
  type DemandSupplyRow,
  type FarmerProfile,
  type SourceRef,
  type WeatherOutlook,
} from "./mockData";

export function getCropRecommendations(_farmer: FarmerProfile): CropRecommendation[] {
  return RECOMMENDATIONS;
}

export function getCropDetails(id: string): CropRecommendation | undefined {
  return RECOMMENDATIONS.find((r) => r.id === id.toLowerCase());
}

export function getDemandSupply(): DemandSupplyRow[] {
  return DEMAND_SUPPLY;
}

export function getWeather(_district?: string): WeatherOutlook {
  return WEATHER;
}

export function getSources(): SourceRef[] {
  return SOURCES;
}

export function getAgriBusinessData() {
  return AGRI_BUSINESS;
}

export interface ScenarioCropResult {
  id: string;
  crop: string;
  baseScore: number;
  score: number;
  delta: number;
}

export interface ScenarioResult {
  rainfallDelta: number;
  crops: ScenarioCropResult[];
  leader: ScenarioCropResult;
  changed: boolean;
  explanation: string;
}

/** Rainfall sensitivity per crop: how strongly a % rainfall change moves the score. */
const RAINFALL_SENSITIVITY: Record<string, number> = {
  tomato: 0.77,
  onion: -0.07,
  chilli: 0.45,
};

export function getScenarioResult(rainfallDelta: number): ScenarioResult {
  const crops: ScenarioCropResult[] = RECOMMENDATIONS.map((rec) => {
    const sensitivity = RAINFALL_SENSITIVITY[rec.id] ?? 0.3;
    const raw = rec.opportunityScore + rainfallDelta * sensitivity;
    const score = Math.max(20, Math.min(97, Math.round(raw)));
    return {
      id: rec.id,
      crop: rec.crop,
      baseScore: rec.opportunityScore,
      score,
      delta: score - rec.opportunityScore,
    };
  }).sort((a, b) => b.score - a.score);

  const leader = crops[0] as ScenarioCropResult;
  const baseLeader = RECOMMENDATIONS[0];
  const changed = leader.id !== baseLeader?.id;

  let explanation: string;
  if (rainfallDelta === 0) {
    explanation =
      "This is the baseline scenario using the current expected rainfall for your district.";
  } else if (changed) {
    explanation = `${rainfallDelta < 0 ? "Lower" : "Higher"} rainfall reduces ${baseLeader?.crop} suitability. ${leader.crop} becomes the safer alternative under this scenario.`;
  } else {
    explanation = `${rainfallDelta < 0 ? "Lower" : "Higher"} rainfall shifts the scores, but ${leader.crop} still leads under this scenario.`;
  }

  return { rainfallDelta, crops, leader, changed, explanation };
}

export interface AskResult {
  answer: string;
  sources: SourceRef[];
}

export function askKhetiSetu(question: string): AskResult {
  const q = question.toLowerCase();
  const hit = MOCK_ANSWERS.find((entry) => entry.match.some((m) => q.includes(m)));
  return {
    answer:
      hit?.answer ??
      "This demo assistant answers questions about your current crop recommendation — for example why a crop was ranked first, how weather changes the ranking, or what indicative inputs a crop needs. Try one of the suggested questions below.",
    sources: SOURCES,
  };
}
