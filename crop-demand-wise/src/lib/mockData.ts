/**
 * KhetiSetu demo data.
 * All values here are SYNTHETIC DEMO DATA used for the prototype.
 * Types are shaped so a real backend (POST /recommend, /scenario, /ask …)
 * can replace the mock service layer without touching UI components.
 */

export type RiskLevel = "Low" | "Medium" | "High";
export type DemandLevel = "Low" | "Medium" | "High";

export interface FarmerProfile {
  state: string;
  district: string;
  landAcres: number;
  irrigation: boolean;
  previousCrop: string;
  sowingMonth: string;
}

export interface CropRecommendation {
  id: string;
  crop: string;
  opportunityScore: number;
  demandLevel: DemandLevel;
  demandChangeLabel: string;
  expectedDemand: number;
  expectedSupply: number;
  demandGap: number;
  weatherSuitability: number;
  weatherLabel: string;
  risk: RiskLevel;
  confidence: number;
  explanation: string;
  risks: string[];
  sowingWindow: string;
  growingPeriod: string;
  trace: { title: string; detail: string }[];
  demandHistory: { season: string; demand: number; projected?: boolean }[];
  inputs: { name: string; dose: string; stage: string }[];
}

export interface DemandSupplyRow {
  crop: string;
  demand: number;
  supply: number;
  gap: number;
}

export interface WeatherOutlook {
  district: string;
  rainfall: string;
  temperature: number;
  humidity: number;
  forecast: string;
  days: { day: string; temp: number; rainChance: number }[];
}

export interface SourceRef {
  category: string;
  source: string;
  icon: "book" | "chart" | "cloud";
}

export const STATES = ["Maharashtra", "Karnataka", "Madhya Pradesh", "Gujarat"];

export const DISTRICTS: Record<string, string[]> = {
  Maharashtra: ["Nashik", "Pune", "Nagpur", "Aurangabad", "Solapur"],
  Karnataka: ["Belagavi", "Hubballi", "Mysuru"],
  "Madhya Pradesh": ["Indore", "Bhopal", "Ujjain"],
  Gujarat: ["Rajkot", "Junagadh", "Surat"],
};

export const CROP_OPTIONS = [
  "Cotton",
  "Onion",
  "Tomato",
  "Soybean",
  "Maize",
  "Wheat",
  "Potato",
  "Chilli",
];

export const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export const DEFAULT_FARMER: FarmerProfile = {
  state: "Maharashtra",
  district: "Nashik",
  landAcres: 5,
  irrigation: true,
  previousCrop: "Onion",
  sowingMonth: "June",
};

export const RECOMMENDATIONS: CropRecommendation[] = [
  {
    id: "tomato",
    crop: "Tomato",
    opportunityScore: 84,
    demandLevel: "High",
    demandChangeLabel: "+18% vs seasonal average",
    expectedDemand: 10000,
    expectedSupply: 6500,
    demandGap: 3500,
    weatherSuitability: 87,
    weatherLabel: "Good",
    risk: "Medium",
    confidence: 82,
    explanation:
      "Tomato is currently ranked highly because historical demand in Nashik has increased over recent seasons, expected weather conditions are favourable, and the projected demand gap is positive.",
    risks: ["Rainfall variability", "Market demand uncertainty"],
    sowingWindow: "June–July",
    growingPeriod: "8–12 weeks",
    trace: [
      { title: "Historical demand", detail: "Demand increased over the last 3 seasons" },
      {
        title: "Seasonal suitability",
        detail: "Tomato is eligible for the selected sowing window",
      },
      { title: "Weather", detail: "Expected conditions are favourable" },
      { title: "Demand gap", detail: "Expected demand is higher than expected supply" },
      { title: "Farmer context", detail: "Irrigation is available on your farm" },
    ],
    demandHistory: [
      { season: "Kharif 2023", demand: 7600 },
      { season: "Kharif 2024", demand: 8400 },
      { season: "Kharif 2025", demand: 9100 },
      { season: "Kharif 2026", demand: 10000, projected: true },
    ],
    inputs: [
      { name: "Urea", dose: "~45 kg / acre", stage: "Split across vegetative stage" },
      { name: "DAP", dose: "~50 kg / acre", stage: "Basal at transplanting" },
      { name: "NPK 19:19:19", dose: "~10 kg / acre", stage: "Flowering & fruit set" },
    ],
  },
  {
    id: "onion",
    crop: "Onion",
    opportunityScore: 76,
    demandLevel: "High",
    demandChangeLabel: "+10% vs seasonal average",
    expectedDemand: 12000,
    expectedSupply: 10500,
    demandGap: 1500,
    weatherSuitability: 82,
    weatherLabel: "Good",
    risk: "Low",
    confidence: 79,
    explanation:
      "Onion remains a steady option for Nashik. Demand has grown moderately, storage infrastructure in the district is strong, and the crop tolerates a wider range of rainfall conditions.",
    risks: ["Price volatility at harvest", "Storage losses"],
    sowingWindow: "June–August",
    growingPeriod: "14–16 weeks",
    trace: [
      { title: "Historical demand", detail: "Steady demand growth over the last 3 seasons" },
      { title: "Seasonal suitability", detail: "Sowing window matches the Kharif calendar" },
      { title: "Weather", detail: "Tolerant to moderate rainfall variation" },
      { title: "Demand gap", detail: "Expected demand exceeds supply by 1,500 q" },
      { title: "Farmer context", detail: "You grew Onion previously — rotation caution applies" },
    ],
    demandHistory: [
      { season: "Kharif 2023", demand: 10200 },
      { season: "Kharif 2024", demand: 10900 },
      { season: "Kharif 2025", demand: 11400 },
      { season: "Kharif 2026", demand: 12000, projected: true },
    ],
    inputs: [
      { name: "Urea", dose: "~40 kg / acre", stage: "Two splits after transplanting" },
      { name: "DAP", dose: "~45 kg / acre", stage: "Basal application" },
      { name: "NPK 10:26:26", dose: "~25 kg / acre", stage: "Bulb development" },
    ],
  },
  {
    id: "chilli",
    crop: "Chilli",
    opportunityScore: 68,
    demandLevel: "Medium",
    demandChangeLabel: "+6% vs seasonal average",
    expectedDemand: 4200,
    expectedSupply: 3300,
    demandGap: 900,
    weatherSuitability: 74,
    weatherLabel: "Moderate",
    risk: "Medium",
    confidence: 71,
    explanation:
      "Chilli shows a smaller but positive demand gap. Returns can be attractive, though the crop is more sensitive to pest pressure and needs consistent irrigation.",
    risks: ["Pest pressure", "Labour availability at picking"],
    sowingWindow: "June–July",
    growingPeriod: "10–14 weeks",
    trace: [
      { title: "Historical demand", detail: "Mild demand growth in the region" },
      { title: "Seasonal suitability", detail: "Eligible for the selected sowing window" },
      { title: "Weather", detail: "Moderate suitability — needs steady irrigation" },
      { title: "Demand gap", detail: "Expected demand exceeds supply by 900 q" },
      { title: "Farmer context", detail: "Irrigation availability supports this crop" },
    ],
    demandHistory: [
      { season: "Kharif 2023", demand: 3500 },
      { season: "Kharif 2024", demand: 3700 },
      { season: "Kharif 2025", demand: 3950 },
      { season: "Kharif 2026", demand: 4200, projected: true },
    ],
    inputs: [
      { name: "Urea", dose: "~35 kg / acre", stage: "Split across growth stages" },
      { name: "DAP", dose: "~40 kg / acre", stage: "Basal at transplanting" },
      { name: "NPK 19:19:19", dose: "~8 kg / acre", stage: "Flowering" },
    ],
  },
];

export const DEMAND_SUPPLY: DemandSupplyRow[] = [
  { crop: "Tomato", demand: 10000, supply: 6500, gap: 3500 },
  { crop: "Onion", demand: 12000, supply: 10500, gap: 1500 },
  { crop: "Potato", demand: 15000, supply: 16200, gap: -1200 },
  { crop: "Wheat", demand: 20000, supply: 19500, gap: 500 },
];

export const WEATHER: WeatherOutlook = {
  district: "Nashik",
  rainfall: "Normal",
  temperature: 27,
  humidity: 72,
  forecast: "Favorable",
  days: [
    { day: "Mon", temp: 27, rainChance: 20 },
    { day: "Tue", temp: 28, rainChance: 15 },
    { day: "Wed", temp: 27, rainChance: 35 },
    { day: "Thu", temp: 26, rainChance: 45 },
    { day: "Fri", temp: 28, rainChance: 20 },
    { day: "Sat", temp: 29, rainChance: 10 },
    { day: "Sun", temp: 28, rainChance: 25 },
  ],
};

export const SOURCES: SourceRef[] = [
  { category: "Agricultural guidance", source: "ICAR / agriculture research (demo reference)", icon: "book" },
  { category: "Historical data", source: "Government agriculture data (demo reference)", icon: "chart" },
  { category: "Weather", source: "Weather data provider (demo reference)", icon: "cloud" },
];

export const AGRI_BUSINESS = {
  season: "Kharif 2026",
  demand: [
    { input: "Urea", volume: "12,400 MT" },
    { input: "DAP", volume: "7,800 MT" },
    { input: "NPK", volume: "9,200 MT" },
  ],
  intent: [
    { crop: "Cotton", acres: 5200 },
    { crop: "Soybean", acres: 2100 },
    { crop: "Maize", acres: 800 },
  ],
  alerts: [
    { level: "error" as const, region: "Nashik", message: "Urea shortage expected" },
    { level: "warning" as const, region: "Pune", message: "Excess stock in depot" },
    { level: "warning" as const, region: "Vidarbha", message: "Rainfall delay affecting dispatch" },
  ],
  action: {
    input: "Urea",
    forecast: "12,400 MT",
    stock: "9,800 MT",
    safety: "1,500 MT",
    recommended: "Dispatch 4,100 MT",
  },
};

export const SUGGESTED_QUESTIONS = [
  "Why tomato?",
  "Why not onion?",
  "What happens if rainfall is lower?",
  "What fertilizer does tomato need?",
  "When should I sow tomato?",
];

export const MOCK_ANSWERS: { match: string[]; answer: string }[] = [
  {
    match: ["why tomato", "tomato"],
    answer:
      "Tomato is currently ranked #1 for your farm because the historical demand trend is positive, the expected demand-supply gap is high (+3,500 q), and the current weather scenario is favourable. Confidence is 82% — this is decision support, not a profit guarantee.",
  },
  {
    match: ["why not onion", "onion"],
    answer:
      "Onion is a strong second option (76% opportunity, low risk). It ranks below Tomato mainly because its projected demand gap is smaller (+1,500 q) and you grew Onion in the previous season, so rotation benefits are limited.",
  },
  {
    match: ["rainfall", "rain", "lower"],
    answer:
      "If rainfall drops by around 30%, Tomato suitability falls (84% → 61%) because it needs steadier moisture during fruit set. Onion holds up better (76% → 78%) and becomes the safer option in that scenario. You can test this on the Weather What-if screen.",
  },
  {
    match: ["fertilizer", "urea", "dap", "npk"],
    answer:
      "Indicative agronomic guidance for Tomato: roughly 45 kg/acre Urea in splits, 50 kg/acre DAP as basal, and 10 kg/acre NPK 19:19:19 around flowering. Final fertilizer recommendations should follow local agricultural advisories or a soil test.",
  },
  {
    match: ["sow", "when", "june"],
    answer:
      "For Nashik, the recommended Tomato sowing window is June–July, with an expected growing period of 8–12 weeks. Your selected sowing month (June) fits this window.",
  },
];
