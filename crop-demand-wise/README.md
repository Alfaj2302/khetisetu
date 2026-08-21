# KhetiBridge Insights

# KhetiSetu — Master Product, UX/UI & Frontend Prototype Prompt

## ROLE

Act as a **Principal Product Designer + Senior UX Engineer with 15+ years of experience** designing mobile-first and responsive products for agriculture, fintech, healthcare, SaaS, and data-heavy platforms.

You have deep expertise in:

* UX strategy

* Information architecture

* Interaction design

* Design systems

* Mobile UX

* Responsive web applications

* Data visualization

* Accessibility

* Design for users with varying levels of digital literacy

* Indian-market product design

* Trust-building UX for AI products

* Designing complex workflows without making them feel complex

Do not design this like a generic SaaS dashboard.

Design it as a **real Indian AgriTech product** that can be presented directly to farmers, fertilizer suppliers, agri-businesses, investors, and hackathon judges.

---

# 1. PRODUCT

## Product Name

**KhetiSetu**

## Tagline

**"From Crop Decisions to Smart Supply."**

## Core Product Idea

KhetiSetu is an agriculture decision-support platform connecting **farmers and agri-businesses**.

The core farmer problem is:

> Farmers don't just need to know how to grow a crop. They need to know whether there is likely to be demand when their crop is ready.

KhetiSetu combines:

**Farmer Context**

+

**Historical Demand**

+

**Expected Supply**

+

**Weather**

+

**Crop Season Rules**

to identify:

**Demand Gap → Crop Opportunity → Recommendation**

The AI layer should explain recommendations rather than pretending to have perfect predictions.

---

# 2. IMPORTANT IMPLEMENTATION SCOPE

This is a **frontend-only prototype/demo**.

Do NOT build:

* Backend

* Database

* PostgreSQL

* Authentication

* Real API integrations

* Real ML model

* RAG backend

* LLM backend

* Weather API

* Government API

* Payment integration

* ERP integration

Use realistic **mock data and local frontend state**.

However, structure the frontend cleanly so that real APIs can be connected later.

Create a mock service layer such as:

* `getCropRecommendations()`

* `getWeather()`

* `getCropDetails()`

* `getScenarioResult()`

* `askKhetiSetu()`

These should currently return local mock data.

Do not create fake network calls.

Do not create buttons that do nothing.

Every visible interaction should either work locally or clearly communicate that it is demo functionality.

---

# 3. DESIGN PHILOSOPHY

The product should feel like:

> **Indian Agriculture + Trustworthy AI + Modern Startup**

The visual personality should be:

* Trustworthy

* Human

* Simple

* Farmer-friendly

* Intelligent

* Modern

* Professional

* Data-driven

* Calm

* Practical

* Premium without feeling expensive or corporate

The product should NOT feel:

* Like generic SaaS

* Like an enterprise ERP

* Like a dark AI dashboard

* Like a cryptocurrency application

* Like a cyberpunk AI product

* Like a children's farming app

* Like a government portal

* Overly technical

* Overloaded with cards

* Overloaded with green

* Overly animated

The design should communicate:

**"This product understands agriculture and can be trusted."**

---

# 4. USE THE PROVIDED KHETISETU LOGO

Use the supplied KhetiSetu logo as the primary brand identity.

The logo contains:

* Farmer

* Mobile technology

* Crop/plant

* Agricultural field

* Farm infrastructure

* Supply/logistics

* Green agricultural identity

* Earth/soil visual language

Do not redesign the logo.

Do not create a competing logo.

Build the UI around the existing brand identity.

Where appropriate, use the logo:

* Landing page header

* Application header

* Login/welcome areas if required

* Farmer experience

* Agri-business experience

Maintain adequate clear space around the logo.

---

# 5. KHETISETU DESIGN SYSTEM

Create a reusable design system and use it consistently across the entire application.

## PRIMARY BRAND COLORS

### Primary Green

`#087443`

Use for:

* Primary CTA

* Navigation active state

* Primary buttons

* Important links

* Selected controls

* Main brand elements

### Primary Dark

`#055C36`

Use for:

* Button pressed state

* Strong headers

* High-emphasis elements

* Dark green surfaces

### Primary Light

`#4CAF50`

Use for:

* Positive highlights

* Supporting icons

* Secondary emphasis

* Progress indicators

### Secondary Crop Green

`#65B82E`

Use for:

* Crop-related elements

* Secondary actions

* Growth indicators

* Opportunity visualization

* Illustrative accents

---

# 6. HARVEST / ACTION COLOR

### Harvest Amber

`#F2A900`

Use sparingly.

This represents:

* Harvest

* Opportunity

* Important information

* Highlights

* New recommendations

* Attention

* Important metrics

Do NOT use amber for every button.

Use it as an accent.

### Soft Harvest

`#FFC857`

Use for:

* Highlight backgrounds

* Secondary badges

* Subtle agricultural accents

---

# 7. EARTH COLORS

### Soil Brown

`#8B4A20`

Use for:

* Soil-related information

* Agriculture illustrations

* Land-related visualizations

* Occasional decorative elements

### Sand

`#D9A66A`

Use very sparingly for supporting surfaces.

Do not make brown a primary UI color.

---

# 8. NEUTRAL COLORS

### Application Background

`#F7FAF5`

Use instead of pure white for most page backgrounds.

This subtle green-tinted background should create an agricultural atmosphere.

### Surface / Card

`#FFFFFF`

### Input Background

`#F1F6EF`

### Primary Text

`#173B2A`

Do NOT use pure black for primary text.

### Secondary Text

`#5F6F65`

### Disabled Text

`#9AA69E`

### Border / Divider

`#DDE7DC`

### Text on Primary

`#FFFFFF`

---

# 9. SEMANTIC COLORS

### Success

`#2E8B57`

### Warning

`#E89B00`

### Error

`#D64545`

### Information

`#3182CE`

Do not communicate status using color alone.

Always combine color with:

* Icon

* Label

* Text

* Shape/badge

Example:

Instead of only showing red:

**🔴 HIGH RISK**

Instead of only green:

**✓ GOOD WEATHER**

---

# 10. COLOR USAGE RATIO

Do not make the entire interface green.

Target visual balance approximately:

* 60% neutral/background

* 25% primary green

* 10% secondary/light green

* 5% amber/brown/semantic accents

The application should breathe.

Green should establish the brand, not overwhelm the interface.

---

# 11. TYPOGRAPHY

Use a highly readable modern sans-serif font.

Prioritize readability over decorative typography.

Suggested:

**Inter**

or another highly readable equivalent available in the environment.

Typography hierarchy:

* Large hero heading

* Strong section headings

* Comfortable body text

* Highly readable form labels

* Clear numeric metrics

* Medium-weight button labels

Avoid extremely thin font weights.

For farmer-facing screens, prioritize readability and clarity over compactness.

---

# 12. SPACING & COMPONENT STYLE

Use a consistent spacing system.

Prefer:

* 4px base spacing

* 8px

* 12px

* 16px

* 24px

* 32px

* 48px

* 64px

Cards:

* Medium rounded corners

* Approximately 12–16px radius

* Soft border

* Very subtle shadow

* Generous internal padding

Avoid:

* Excessively rounded pill-shaped everything

* Huge shadows

* Glassmorphism everywhere

* Excessive gradients

* Excessive borders

Use depth subtly.

---

# 13. UX PRINCIPLE: FARMER FIRST

The farmer may not be highly digitally sophisticated.

Therefore:

* Avoid technical terminology where unnecessary.

* Explain complex information in simple language.

* Use familiar icons.

* Use clear labels.

* Keep forms short.

* Use progressive disclosure.

* Never expose unnecessary model/data complexity.

* Explain "why" behind recommendations.

* Make important actions obvious.

For example, prefer:

**"Where is your farm?"**

instead of:

**"Select geographic coordinates."**

Prefer:

**"How much land do you have?"**

instead of:

**"Enter cultivation area."**

---

# 14. CORE USER JOURNEY

The main demo flow must be:

Landing

↓

Find Best Crops

↓

Farmer Input

↓

Analyze Farm

↓

Top 3 Crop Opportunities

↓

Demand vs Supply

↓

Weather Suitability

↓

Risk + Confidence

↓

Why This Crop?

↓

AI Decision Trace

↓

View Crop Plan

↓

Fertilizer/Input Guidance

↓

Weather What-if

↓

Recommendation Changes

↓

Ask KhetiSetu

↓

AI Reliability

↓

Agri Business Preview

This should feel like one coherent product journey, not disconnected pages.

---

# 15. ROUTES / SCREENS

Create these screens:

1. Landing / Welcome

2. Farmer Dashboard / Input

3. Crop Recommendations

4. Crop Details

5. Why This Crop

6. Weather What-if

7. Ask KhetiSetu

8. AI Reliability & Responsible AI

9. Agri Business Dashboard

10. How It Works

Use routing where appropriate.

All navigation must actually work.

---

# 16. LANDING PAGE

Create a premium, visually impressive agriculture-tech landing page.

## Header

Left:

KhetiSetu logo

Navigation:

* Farmer

* Agri Business

* How It Works

* AI Reliability

Right:

**Demo Mode**

Primary CTA:

**Find Best Crops**

On mobile:

Use a clean hamburger menu.

---

# 17. HERO SECTION

Hero headline:

**"Know what to grow.

Know what the market needs."**

Supporting copy:

**"KhetiSetu combines historical crop demand, weather and agricultural season rules to help farmers identify crops with stronger future demand opportunities."**

Primary CTA:

**🌱 Find Best Crops**

Secondary CTA:

**See How It Works**

Hero imagery should communicate:

* Indian agriculture

* Crops

* Farmer

* Technology

* Data intelligence

Use realistic, premium agricultural imagery.

Avoid cartoon illustrations.

Add subtle data overlays such as:

**Nashik**

**Kharif 2026**

**🌧 Weather: Favorable**

**📈 Demand: Increasing**

**🌱 Opportunity: High**

Do not overdecorate.

---

# 18. LANDING BENEFITS

Show three concise benefits:

### Smarter Crop Decisions

Help farmers evaluate crop opportunities.

### Weather-Aware Recommendations

Understand how weather conditions influence suitability.

### Demand-Supply Intelligence

Identify demand gaps before making crop decisions.

Use simple icons and short explanations.

---

# 19. HOW IT WORKS

Create a clean five-step visual:

### 1. Farmer Context

Location • Land • Irrigation • Previous Crop

↓

### 2. Agricultural Data

Weather • Crop Calendar • Historical Data

↓

### 3. AI Forecast

Expected Demand • Expected Supply

↓

### 4. Crop Ranking

Top 3 Opportunities

↓

### 5. Explain & Simulate

AI Explanation • Weather What-if

Make this visually elegant.

---

# 20. FARMER INPUT EXPERIENCE

This is one of the most important screens.

Title:

**"Let's understand your farm."**

Use a clear step-based form.

Do not make it look like a long enterprise form.

Show progress:

**1 Farm → 2 Conditions → 3 Crop → 4 Results**

---

## STEP 1 — LOCATION

Question:

**"Where is your farm?"**

Fields:

State

Default:

**Maharashtra**

District

Default:

**Nashik**

Show location card:

📍 Nashik, Maharashtra

If useful, show a subtle map/location visualization.

---

# 21. STEP 2 — FARM SIZE

Question:

**"How much land do you have?"**

Input:

**5**

Unit:

**Acres**

Make the unit obvious.

Validate sensible numeric input.

---

# 22. STEP 3 — IRRIGATION

Question:

**"Is irrigation available?"**

Use a clear segmented control or toggle:

**Yes / No**

Default:

**Yes**

Make the selected state visually obvious.

---

# 23. STEP 4 — PREVIOUS CROP

Question:

**"What did you grow previously?"**

Default:

**Onion**

Options:

* Cotton

* Onion

* Tomato

* Soybean

* Maize

* Wheat

* Potato

* Chilli

---

# 24. STEP 5 — SOWING MONTH

Question:

**"When are you planning to sow?"**

Default:

**June**

Allow:

January–December

Use a clear dropdown.

---

# 25. PRIMARY FORM CTA

Button:

**🌱 Find Best Crops**

When clicked:

Show a polished loading state.

Do not simply show a spinner.

Show:

**"Analyzing your farm..."**

Supporting microcopy:

**"Checking crop season, demand, weather and supply conditions."**

Use a short 1–2 second simulated transition.

Then show recommendations.

---

# 26. CROP RECOMMENDATIONS

Title:

**"Your Crop Opportunities"**

Subtitle:

**"Based on your location, season, weather and historical demand."**

At the top, show the farmer context as a compact summary:

📍 Nashik

📐 5 acres

💧 Irrigation available

🌾 Previous crop: Onion

📅 Sowing: June

Then:

**"Top 3 Crops to Consider"**

---

# 27. RECOMMENDATION CARD DESIGN

Create large, premium recommendation cards.

The first recommendation should be visually dominant.

Do NOT make all three cards look identical.

Rank them clearly:

**#1**

**#2**

**#3**

---

## RECOMMENDATION #1

### Tomato

Opportunity:

**84%**

Demand:

**HIGH**

Expected Demand:

**+18% vs seasonal average**

Expected Supply:

**6,500 q**

Expected Demand:

**10,000 q**

Demand Gap:

**+3,500 q**

Opportunity:

**VERY HIGH**

Weather:

**GOOD**

Risk:

**MEDIUM**

Confidence:

**82%**

Buttons:

**View Crop Plan**

**Why Tomato?**

---

## RECOMMENDATION #2

### Onion

Opportunity:

**76%**

Demand:

**HIGH**

Expected Demand:

**+10%**

Demand Gap:

**+1,500 q**

Risk:

**LOW**

Confidence:

**79%**

CTA:

**View Crop Plan**

---

## RECOMMENDATION #3

### Chilli

Opportunity:

**68%**

Demand:

**MEDIUM**

Demand Gap:

**+900 q**

Risk:

**MEDIUM**

Confidence:

**71%**

CTA:

**View Crop Plan**

---

# 28. OPPORTUNITY SCORE

Make the opportunity score visually meaningful.

Use:

* Large percentage

* Circular progress/ring or elegant meter

* Supporting label

Example:

**84%**

**High Opportunity**

Do not use giant dashboards full of gauges.

One strong visualization is enough.

---

# 29. DEMAND VS SUPPLY

Create a section:

**"Demand vs Expected Supply"**

Use a professional bar chart.

Data:

Tomato

Demand: 10,000 q

Supply: 6,500 q

Gap: +3,500 q

Onion

Demand: 12,000 q

Supply: 10,500 q

Gap: +1,500 q

Potato

Demand: 15,000 q

Supply: 16,200 q

Gap: -1,200 q

Wheat

Demand: 20,000 q

Supply: 19,500 q

Gap: +500 q

Clearly communicate:

**Positive gap = opportunity**

**Negative gap = possible oversupply**

Use accessible labels and tooltips.

---

# 30. WEATHER SECTION

Create:

**"Nashik Weather Outlook"**

Show:

🌧 Rainfall

**Normal**

🌡 Temperature

**27°C**

💧 Humidity

**72%**

☁ Forecast

**Favorable**

Then a compact 7-day forecast:

Mon — 27° — Rain 20%

Tue — 28° — Rain 15%

Wed — 27° — Rain 35%

Thu — 26° — Rain 45%

Fri — 28° — Rain 20%

On mobile, allow horizontal scrolling.

CTA:

**Test Weather Scenario**

---

# 31. CROP DETAILS

When the user clicks:

**View Crop Plan**

Open the detailed crop page.

Header:

**Tomato**

Opportunity:

**84%**

Badges:

**HIGH DEMAND**

**GOOD WEATHER**

**MEDIUM RISK**

Then sections:

---

## WHY TOMATO?

Show a concise AI explanation:

"Tomato is currently ranked highly because historical demand in Nashik has increased over recent seasons, expected weather conditions are favorable, and the projected demand gap is positive."

Make this human-readable.

---

# 32. DEMAND OUTLOOK

Show a line chart:

Past 3 seasons → projected upcoming season.

Clearly distinguish:

Historical

vs

Projected

Do not visually imply that projected values are actual historical facts.

---

# 33. WEATHER SUITABILITY

Show:

* Rainfall

* Temperature

* Humidity

Use simple visual indicators.

---

# 34. CROP SEASON

Show:

Recommended sowing:

**June–July**

Expected growing period:

**8–12 weeks**

Use a simple timeline.

---

# 35. FERTILIZER / INPUT GUIDANCE

Show example input cards:

* Urea

* DAP

* NPK

IMPORTANT:

Label this:

**"Indicative agronomic guidance"**

Add disclaimer:

**"Final fertilizer recommendations should follow local agricultural advisories / soil-test recommendations."**

Do not present mock fertilizer values as guaranteed prescriptions.

---

# 36. RISK

Show:

**Medium Risk**

Possible risks:

* Rainfall variability

* Market demand uncertainty

Use icon + text + badge.

Never use color alone.

---

# 37. CONFIDENCE

Show:

**82% Confidence**

Explain:

**"Confidence is based on historical data coverage, weather availability and seasonal consistency."**

Make clear:

**Confidence is not probability of profit.**

---

# 38. SOURCES / EVIDENCE

Show:

**"Based on agricultural knowledge sources"**

Button:

**View Sources**

Create the component so real source URLs can be connected later.

Example source categories:

📚 Agricultural Guidance

Source: ICAR / Agriculture Research

📊 Historical Data

Source: Government agriculture data

🌦 Weather

Source: Weather data provider

Do not claim that these are live integrations.

This is demo data.

---

# 39. WHY THIS CROP — DECISION TRACE

When user clicks:

**Why Tomato?**

Open a polished right-side drawer on desktop.

On mobile:

Convert it to a bottom sheet.

Title:

**"Why did KhetiSetu recommend Tomato?"**

Show decision trace:

✓ Historical demand

Demand increased over last 3 seasons

✓ Seasonal suitability

Tomato is eligible for the selected sowing window

✓ Weather

Expected conditions are favorable

✓ Demand gap

Expected demand is higher than expected supply

✓ Farmer context

Irrigation is available

Then:

**AI Confidence**

**82%**

Add:

**"AI does not guarantee crop profitability. This recommendation is decision support based on available data."**

This screen is extremely important for building trust.

---

# 40. WEATHER WHAT-IF

Create a visually impressive interactive scenario screen.

Title:

**"What if the weather changes?"**

Show:

Current rainfall:

**100%**

Slider:

**-30% ←──────────→ +30%**

When slider changes, dynamically update mock recommendation scores.

Default:

Tomato: **84%**

Onion: **76%**

If rainfall is -30%:

Tomato: **61%**

Onion: **78%**

Then dynamically show:

**Recommendation changed**

🏆 **New safer option: Onion**

Explanation:

**"Lower rainfall reduces Tomato suitability. Onion becomes the safer alternative under this scenario."**

The transition should be smooth.

Make this one of the most visually impressive interactions in the application.

---

# 41. ASK KHETISETU

Create a farmer-friendly assistant.

Title:

**"Ask KhetiSetu"**

Subtitle:

**"Ask about your crop recommendation."**

Suggested questions:

* Why tomato?

* Why not onion?

* What happens if rainfall is lower?

* What fertilizer does tomato need?

* When should I sow tomato?

Create a polished chat interface.

This is a frontend mock.

No real LLM.

Example response:

"Tomato is currently ranked #1 for your farm because the historical demand trend is positive, the expected demand-supply gap is high, and the current weather scenario is favorable."

Below each response show:

**Sources used**

📚 Agricultural guidance

🌦 Weather

📊 Historical crop data

---

# 42. AI RELIABILITY & RESPONSIBLE AI

Create a dedicated screen for hackathon judges.

This screen should look polished, credible and data-driven.

Title:

**"AI Reliability & Responsible AI"**

---

## FORECAST EVALUATION

Show:

Baseline:

**14.8% error**

ML Model:

**8.6% error**

Improvement:

**41.9%**

Clearly label:

**Demo evaluation values**

Never make demo numbers appear like production-validated results.

---

## CONFIDENCE

Show:

High

Medium

Low

Explanation:

**"Confidence decreases when historical data is limited or weather conditions are unusual."**

---

## RESPONSIBLE AI

Checklist:

✓ Source-backed recommendations

✓ Confidence shown

✓ Farmer data protected

✓ No unsupported numeric claims

✓ Human decision remains final

✓ Synthetic demo data clearly labeled

---

## EDGE CASES

Create cards for:

* No historical data

* Weather unavailable

* Extreme rainfall

* New district

* No reliable source

Message:

**"AI will reduce confidence or ask for more information instead of guessing."**

---

# 43. AGRI BUSINESS DASHBOARD

Create a separate role experience.

Header:

**KhetiSetu — Agri Business**

Subtitle:

**"From farmer intent to smart supply planning."**

Show:

**Kharif 2026**

---

## EXPECTED DEMAND

Urea:

**12,400 MT**

DAP:

**7,800 MT**

NPK:

**9,200 MT**

---

# 44. FARMER CROP INTENT

Title:

**"Farmer Crop Intent"**

Nashik:

Cotton — 5,200 acres

Soybean — 2,100 acres

Maize — 800 acres

IMPORTANT:

Clearly communicate that this is:

**Aggregated / anonymized farmer intent**

Never display individual farmer information.

---

# 45. SUPPLY ALERTS

Show:

🔴 Nashik — Urea shortage

🟡 Pune — Excess stock

🟡 Vidarbha — Rainfall delay

Use semantic status colors carefully.

---

# 46. RECOMMENDED ACTION

Urea

Forecast:

**12,400 MT**

Current stock:

**9,800 MT**

Safety stock:

**1,500 MT**

Recommended:

**Dispatch 4,100 MT**

Actions:

**View Forecast**

**View Inventory**

**View Transfers**

These can open demo views, drawers or informational states.

Do not create dead buttons.

---

# 47. NAVIGATION

Desktop:

Use a clean top navigation/header.

Logo

Farmer

Agri Business

How It Works

AI Reliability

Right:

**Demo Mode**

For application screens, use a lightweight contextual navigation system if needed.

Do not create an oversized sidebar unless the content genuinely requires it.

---

# 48. MOBILE UX

The product must work beautifully at:

**390px**

Also optimize for:

**1024px tablet**

and

**1440px desktop**

Mobile is NOT simply a compressed desktop.

Make deliberate mobile decisions.

On mobile:

* Stack cards

* Use full-width CTAs

* Use bottom sheets instead of side drawers

* Horizontal-scroll weather cards

* Keep charts readable

* Use large tap targets

* Avoid tiny text

* Use sticky primary actions when useful

* Consider bottom navigation for the authenticated/demo application experience

Forms should be extremely comfortable to use with one hand.

---

# 49. RESPONSIVE BEHAVIOR

At desktop:

Use spacious multi-column layouts.

At tablet:

Reduce column count.

At mobile:

Single-column priority layout.

Important information order should remain:

1. Recommendation

2. Opportunity score

3. Why

4. Demand/supply

5. Weather

6. Risk

7. Confidence

8. Details

Do not hide critical information simply because the screen is smaller.

---

# 50. ACCESSIBILITY

Follow strong accessibility principles.

Implement:

* Semantic HTML

* Proper form labels

* Keyboard navigation

* Visible focus states

* Good contrast

* Accessible buttons

* Accessible dropdowns

* Accessible sliders

* Screen-reader-friendly labels

* Meaningful chart descriptions

* Status indicators that don't rely only on color

* Minimum comfortable touch targets

Do not sacrifice accessibility for visual design.

---

# 51. DATA VISUALIZATION

Charts should be:

* Simple

* Clean

* Readable

* Purpose-driven

Do not create dashboards full of charts.

Every chart must answer a clear question.

Examples:

**"Is demand greater than expected supply?"**

**"How has demand changed?"**

**"How does weather affect crop suitability?"**

Use Recharts or another lightweight charting solution if necessary.

Charts should have:

* Labels

* Tooltips

* Clear legends

* Accessible descriptions

* Historical/projected distinction

---

# 52. MOCK DATA

Create all demo data centrally.

Prefer:

`mockData.ts`

Default farmer:

State: Maharashtra

District: Nashik

Land: 5 acres

Irrigation: Yes

Previous crop: Onion

Sowing month: June

Default recommendations:

Tomato:

* Opportunity: 84

* Demand: High

* Demand gap: +3500 q

* Weather: 87

* Risk: Medium

* Confidence: 82

Onion:

* Opportunity: 76

* Demand: High

* Demand gap: +1500 q

* Weather: 82

* Risk: Low

* Confidence: 79

Chilli:

* Opportunity: 68

* Demand: Medium

* Demand gap: +900 q

* Weather: 74

* Risk: Medium

* Confidence: 71

Potato:

* Demand: 15000 q

* Supply: 16200 q

* Gap: -1200 q

Wheat:

* Demand: 20000 q

* Supply: 19500 q

* Gap: +500 q

Clearly label these as:

**Demo Data**

where appropriate.

---

# 53. INTERACTIONS

The frontend must feel genuinely functional.

Implement:

1. District dropdown changes district.

2. Land input updates farm size.

3. Irrigation toggle works.

4. Previous crop dropdown works.

5. Sowing month dropdown works.

6. Find Best Crops shows loading state.

7. Recommendations appear after loading.

8. Recommendation cards are clickable.

9. View Crop Plan opens crop details.

10. Why This Crop opens explanation drawer/bottom sheet.

11. Rainfall slider dynamically updates scores.

12. Recommendation changes based on mock scenario.

13. Ask KhetiSetu opens chat.

14. Suggested questions populate/send mock responses.

15. Farmer / Agri Business navigation works.

16. How It Works navigation works.

17. AI Reliability navigation works.

18. Responsive layouts work.

19. Back navigation works.

20. Appropriate toast/feedback states work.

---

# 54. UX STATES

Every important interaction should have appropriate states:

### Loading

Show meaningful copy rather than only a spinner.

### Success

Show clear confirmation.

### Empty

Explain what is missing.

### Error

Explain what happened and what the user can do.

### Disabled

Make disabled states visually obvious.

### Hover

Use subtle hover feedback on desktop.

### Focus

Use clear focus states.

### Pressed

Buttons should have a clear pressed state.

---

# 55. MICROINTERACTIONS

Use animation carefully.

Good examples:

* Button press

* Card hover

* Score animation

* Chart entrance

* Loading transition

* Slider updates

* Drawer opening

* Recommendation ranking change

Animations should be:

* Fast

* Smooth

* Purposeful

Avoid:

* Excessive bouncing

* Large page transitions

* Decorative animation everywhere

* Distracting particle effects

The product should feel premium, not flashy.

---

# 56. FARMER TRUST

Trust is a central UX requirement.

Always distinguish:

**Data**

from

**AI interpretation**

from

**Demo values**

from

**Agronomic guidance**

For example:

### Historical Data

"Demand increased over recent seasons."

### AI Interpretation

"This contributes to a higher opportunity score."

### Demo Projection

"Expected demand: 10,000 q"

### Disclaimer

"AI recommendations are decision support and do not guarantee profitability."

This distinction is critical.

---

# 57. AGRICULTURAL SAFETY

Do not make fertilizer recommendations appear medically or scientifically authoritative.

Use:

**Indicative agronomic guidance**

and:

**"Final fertilizer recommendations should follow local agricultural advisories / soil-test recommendations."**

Do not claim:

"Use exactly X kg."

unless clearly presented as mock/demo data.

---

# 58. RESPONSIBLE AI LANGUAGE

Avoid statements like:

* Guaranteed profit

* Guaranteed yield

* Guaranteed demand

* Best crop for everyone

* 100% accurate

* AI knows exactly what will happen

Prefer:

* Recommended

* Opportunity

* Expected

* Projected

* Estimated

* Confidence

* Based on available data

* Scenario

* Decision support

---

# 59. COMPONENT ARCHITECTURE

Create reusable components.

Examples:

* `Header`

* `Logo`

* `Navigation`

* `FarmerInputForm`

* `FormStep`

* `LocationCard`

* `CropRecommendationCard`

* `OpportunityScore`

* `DemandSupplyChart`

* `WeatherCard`

* `ForecastCard`

* `RiskBadge`

* `ConfidenceIndicator`

* `AIExplanation`

* `DecisionTrace`

* `SourceCard`

* `WhatIfSlider`

* `ChatPanel`

* `MetricCard`

* `Toast`

* `Modal`

* `Drawer`

* `BottomSheet`

* `DemoDataBadge`

Do not duplicate UI unnecessarily.

---

# 60. CODE STRUCTURE

Use:

* React

* TypeScript

* Tailwind CSS

* Component-based architecture

* Responsive design

* Typed mock data

* Reusable components

* Clean separation between UI and mock service logic

Create typed interfaces for future backend integration.

Example:

```ts

interface CropRecommendation {

  crop: string;

  opportunityScore: number;

  expectedDemand: number;

  expectedSupply: number;

  demandGap: number;

  weatherSuitability: number;

  risk: string;

  confidence: number;

  explanation: string;

}

```

Future backend endpoints may eventually be:

```text

POST /recommend

GET /crops

GET /districts

POST /scenario

POST /ask

```

Do not implement these APIs now.

---

# 61. DESIGN FOR FUTURE APK

Although this prototype is web-based, design the system so that the visual language can later be reused in the KhetiSetu Android application.

Therefore:

* Use mobile-friendly components

* Use touch-friendly controls

* Use consistent spacing

* Use the same color tokens

* Use the same semantic colors

* Use the same typography hierarchy

* Avoid web-only visual patterns where possible

The design system should translate naturally into React Native.

---

# 62. DO NOT OVERDESIGN

This is extremely important.

Do NOT:

* Put every metric inside a card.

* Put cards inside cards inside cards.

* Use gradients everywhere.

* Use green everywhere.

* Use huge rounded containers.

* Use excessive glass effects.

* Use unnecessary sidebars.

* Use excessive charts.

* Use giant numbers without context.

* Use meaningless animations.

* Use stock AI/cyberpunk visual language.

* Make it look like ChatGPT.

Use whitespace and hierarchy.

---

# 63. VISUAL HIERARCHY

Every screen should have one primary question.

For example:

Farmer Input:

**"What information do I need to provide?"**

Recommendations:

**"Which crops should I consider?"**

Crop Details:

**"Why is this crop recommended?"**

Weather What-if:

**"What changes if the weather changes?"**

AI Reliability:

**"Why should I trust this system?"**

Agri Business:

**"What does farmer intent mean for supply planning?"**

Design the screen hierarchy around these questions.

---

# 64. HACKATHON DEMO OPTIMIZATION

The product will be demonstrated in approximately 5 minutes.

The following screens deserve the highest visual polish:

1. Farmer Input

2. Crop Recommendations

3. Demand vs Supply

4. Crop Details

5. Why This Crop

6. Weather What-if

7. AI Reliability

The demo should feel like a story.

The audience should understand the value without needing a long explanation.

---

# 65. FIVE-MINUTE DEMO STORY

The intended presentation flow is:

### Step 1

Landing page.

Show:

**"Know what to grow. Know what the market needs."**

### Step 2

Click:

**Find Best Crops**

### Step 3

Enter:

Maharashtra

Nashik

5 acres

Irrigation Yes

Previous crop Onion

Sowing June

### Step 4

Click:

**Find Best Crops**

Show:

**Analyzing your farm...**

### Step 5

Display:

**Tomato — #1**

**84% Opportunity**

### Step 6

Show:

Demand:

10,000 q

Supply:

6,500 q

Gap:

+3,500 q

### Step 7

Show weather suitability.

### Step 8

Click:

**Why Tomato?**

Show decision trace.

### Step 9

Click:

**View Crop Plan**

Show crop details and indicative fertilizer guidance.

### Step 10

Click:

**Test Weather Scenario**

Reduce rainfall by 30%.

Show:

Tomato:

84% → 61%

Onion:

76% → 78%

### Step 11

Show:

**New safer option: Onion**

### Step 12

Open:

**Ask KhetiSetu**

Ask:

**"Why tomato?"**

Show mock explanation with sources.

### Step 13

Open:

**AI Reliability**

Show responsible AI and evaluation.

### Step 14

Open:

**Agri Business**

Show how farmer crop intent translates into fertilizer supply planning.

This should feel like one connected story.

---

# 66. IMPORTANT PRODUCT DIFFERENTIATOR

Do not accidentally turn KhetiSetu into a generic:

"AI farming assistant."

The central differentiator must remain visible throughout the experience:

> **Farmers need to understand not only what they can grow, but whether there may be demand when the crop is ready.**

The product connects:

**Farmer Context**

*

**Historical Demand**

*

**Expected Supply**

*

**Weather**

*

**Crop Season**

↓

**Demand Gap**

↓

**Crop Opportunity**

↓

**Recommendation**

↓

**Explainability**

↓

**Scenario Planning**

This is the core product story.

---

# 67. FINAL QUALITY BAR

Before considering the implementation complete, review the entire application as a **15-year senior UX professional**.

Ask:

### UX

* Is the primary user journey obvious?

* Can a farmer understand the screens without technical knowledge?

* Is information presented progressively?

* Are the important actions obvious?

* Are there unnecessary steps?

### Visual Design

* Does it feel like a serious AgriTech startup?

* Is the KhetiSetu brand identity consistent?

* Is green used with restraint?

* Is the hierarchy clear?

* Is whitespace sufficient?

* Are charts readable?

### Trust

* Are AI claims appropriately qualified?

* Are demo values clearly labeled?

* Are recommendations explainable?

* Are sources represented?

* Are confidence and risk understandable?

### Mobile

* Does it feel intentionally designed for mobile?

* Are controls easy to tap?

* Are charts readable?

* Are drawers converted to bottom sheets?

* Are CTAs easy to reach?

### Accessibility

* Is contrast sufficient?

* Are labels clear?

* Does keyboard navigation work?

* Are statuses understandable without color?

### Engineering

* Is the code componentized?

* Is mock data centralized?

* Are types defined?

* Is future API integration straightforward?

* Are there unnecessary dependencies?

---

# 68. FINAL INSTRUCTION TO LOVABLE

Build the **complete, polished, responsive KhetiSetu frontend prototype now**.

Do not ask me to design individual screens one by one.

Do not wait for additional UX instructions.

Make reasonable professional UX decisions wherever the specification does not explicitly define a detail.

Prioritize:

1. Farmer usability

2. Product clarity

3. Trust

4. Visual polish

5. Mobile responsiveness

6. Accessibility

7. Interactive demo experience

8. Consistent design system

9. Future scalability

Use the provided KhetiSetu logo and the exact brand palette defined above.

The final product should look like a **serious Indian AgriTech startup**, not a template.

It should be polished enough to demonstrate directly to:

* Hackathon judges

* Farmers

* Fertilizer suppliers

* Agri-businesses

* Investors

* Product stakeholders

The finished experience should communicate this idea within seconds:

> **KhetiSetu helps farmers make smarter crop decisions by connecting what they can grow with what the market may need — while helping agri-businesses prepare supply intelligently.**

Build the entire experience with this principle at the center.

This project was built with [Lovable](https://lovable.dev).

**Live app**: https://crop-demand-wise.lovable.app

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/5dab251b-3c87-4e67-b29f-9a631b21672d).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
