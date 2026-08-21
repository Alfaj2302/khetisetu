/** UI constants that are not backend data. */

/** Month labels for the API's 1-12 `sowing_month` / `month` fields. */
export const MONTHS = [
  { value: 1, label: "January" },
  { value: 2, label: "February" },
  { value: 3, label: "March" },
  { value: 4, label: "April" },
  { value: 5, label: "May" },
  { value: 6, label: "June" },
  { value: 7, label: "July" },
  { value: 8, label: "August" },
  { value: 9, label: "September" },
  { value: 10, label: "October" },
  { value: 11, label: "November" },
  { value: 12, label: "December" },
] as const;

export const SUGGESTED_QUESTIONS = [
  "Why is this crop ranked first?",
  "What happens if rainfall is lower?",
  "What fertilizer does this crop need?",
  "When should I sow?",
  "How is the demand gap calculated?",
] as const;
