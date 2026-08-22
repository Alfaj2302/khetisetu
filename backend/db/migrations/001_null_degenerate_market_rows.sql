-- 001: Neutralise the degenerate crop_market_data rows.
--
-- 29 rows (3 district/crop pairs × ~10 years) carried
-- expected_demand_qty = 1, expected_supply_qty = 0. Because demand_gap is
-- GENERATED as (demand - supply), that gives a gap ratio of exactly 1.0 —
-- the maximum the scale allows — so scoring.demand_level_from_gap() returned
-- "High" and compute_opportunity_pct() returned 100. Live effect:
-- POST /farmer/crop-recommendation for Pune in June ranked Cotton #1 at 100%
-- off one quintal of synthetic demand.
--
-- ICRISAT (the ACTUAL rows in crop_production) reports ~0 cultivated area for
-- all three pairs, i.e. these crops are genuinely not grown in these
-- districts. So 1/0 was the synthetic generator's "no market here" placeholder,
-- not a real signal.
--
-- Fix: null the quantities. scoring.demand_level_from_gap() already guards on
-- falsy input and returns ("Medium", 0.0), so an uncultivated crop now scores
-- mid-pack on weather alone instead of topping the list. The row is kept (not
-- deleted) so the reason stays on the record.
--
-- Idempotent: after this runs, expected_supply_qty is NULL, so the WHERE
-- clause matches nothing on a re-run.

BEGIN;

UPDATE crop_market_data
SET expected_demand_qty = NULL,
    expected_supply_qty = NULL,
    demand_source_notes  = 'NO MARKET - ICRISAT reports ~0 cultivated area for this district/crop. '
                           'Previously held the placeholder demand=1 / supply=0, which produced a '
                           'demand_gap ratio of 1.0 (the maximum) and ranked an uncultivated crop '
                           'first. Nulled by migration 001 so scoring treats this as "no data" '
                           'rather than "maximum opportunity".'
WHERE expected_supply_qty = 0
  AND expected_demand_qty = 1;

COMMIT;
