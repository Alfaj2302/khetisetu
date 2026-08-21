/** UI constants that are not backend data. */

/** The API's 1-12 `sowing_month` / `month` values; labels come from i18n. */
export const MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const;

/**
 * The chips on /ask.
 *
 * `question` is what gets sent to the API and `labelKey` is what the farmer
 * reads: the RAG corpus is indexed in English, so translating the outgoing
 * question would stop it matching any source.
 */
export const SUGGESTED_QUESTIONS = [
  { labelKey: "ask.suggestions.whyFirst", question: "Why is this crop ranked first?" },
  { labelKey: "ask.suggestions.lowerRainfall", question: "What happens if rainfall is lower?" },
  { labelKey: "ask.suggestions.fertilizer", question: "What fertilizer does this crop need?" },
  { labelKey: "ask.suggestions.whenToSow", question: "When should I sow?" },
  { labelKey: "ask.suggestions.demandGap", question: "How is the demand gap calculated?" },
] as const;
