# Job 1 — nightly fertilizer-demand forecast

Fills the two tables `schema.sql` reserves for the batch ML job. The API only
ever reads them; nothing is computed while a user waits.

```
ml/features.py    build the panel + the aggregation/allocation share tables
ml/metrics.py     WAPE, bias, interval coverage
ml/baseline.py    seasonal naive — the number the model must beat
ml/train.py       fit, evaluate, calibrate intervals, save artifacts
ml/predict.py     forecast forward, allocate, write `forecast`
ml/recommend.py   forecast + inventory -> write `recommendations`
ml/run_nightly.sh cron entry point (flocked, idempotent)
```

## Run it

```bash
pip install -r requirements-ml.txt

.venv/bin/python ml/baseline.py                    # what we have to beat
.venv/bin/python ml/train.py                       # fit + save artifacts
.venv/bin/python ml/predict.py                     # DRY RUN
.venv/bin/python ml/predict.py --write             # writes `forecast`
.venv/bin/python ml/recommend.py --year 2026 --quarter 3 --write
```

Both write steps default to a dry run. Both are idempotent.

## The one thing to understand

**It forecasts district × quarter, not district × product × month.**

The `forecast` table wants per-product monthly rows, but measured on the 2024
holdout that granularity carries no signal:

| level | seasonal-naive WAPE | model WAPE |
|---|---|---|
| district × product × month | 136.8% | 100.3% |
| district × quarter | 72.2% | **57.6%** |

At product-month level, "predict zero" scores exactly 100.0% — so a 100.3%
model is worse than forecasting nothing, and it gets there by hedging toward
zero (bias −30.8). Aggregating to district-quarter is where a model starts
beating its baseline by a real margin.

So the production chain is:

```
district × quarter forecast          <- trained model, 57.6% WAPE
  ├─ split across months             <- historical month-of-quarter share
  └─ split across products           <- historical product-mix share
       └─ write district × product × month
```

Every written row is an **allocation of a forecast**, not a forecast at that
granularity. `forecast.confidence` carries the word `Allocated` on every row so
no consumer can mistake one for the other, and `recommendations.reason` repeats
it in full.

## Intervals are calibrated, not trusted

XGBoost's quantile heads gave **40.7%** coverage against an 80% target — the
stated range excluded the truth 6 times in 10. The interval is therefore rebuilt
from held-out residuals (split-conformal style), which brings coverage to
**70.4%**. The resulting band is wide (−1807/+1174 packets on ~2000 mean
quarterly volume). That width is the honest answer for this data.

## Units

**Packets**, matching `historical_sales.qty_in_pkts`. Nothing here produces
metric tons. The API used to expose these as `quantity_mt` / `forecast_mt` /
`current_stock_mt`; those were renamed and a `unit` field added, because a
1000× mislabel on a dispatch decision is not a cosmetic problem.

## Known limits

- **Sales data ends 2024-12.** Any 2026 row is a 7–8 quarter extrapolation with
  recursive lags, labelled `Allocated: Very Low`. Fix by loading newer sales.
- **No weather forecast.** `weather_forecast` is empty and no API is wired up,
  so future weather features use the climatological mean per district-quarter.
- **4 products are excluded.** Urea/DAP/MOP/NPK (ids 26–29) were added to
  `products` for dashboard parity and have zero real sales — nothing to learn.
- **`intent_acres` covers 2023+ only**, so it is NaN for most of the panel.
  Left as NaN deliberately; XGBoost splits on missingness.
- **Bias is +178 packets per district-quarter** (over-forecasting). For supply
  planning that is the safer direction, but it is not zero.
- **Retraining nightly is currently pointless** — the underlying sales data is
  static. The script does it anyway so the pipeline is correct once data flows.
