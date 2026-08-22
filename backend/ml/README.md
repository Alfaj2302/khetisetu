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
python3 -m venv .venv
.venv/bin/pip install -r requirements-ml.txt

.venv/bin/python ml/baseline.py                    # what we have to beat
.venv/bin/python ml/train.py                       # fit + save artifacts
.venv/bin/python ml/predict.py                     # DRY RUN
.venv/bin/python ml/predict.py --write             # writes `forecast`
.venv/bin/python ml/recommend.py --year 2026 --quarter 4 --write
```

Both write steps default to a dry run. Both are idempotent. Or just run
`ml/run_nightly.sh`, which does all three against the quarter after the current
one and takes about 20 seconds on the seeded data.

## The one thing to understand

**It forecasts district × quarter, not district × product × month.**

The `forecast` table wants per-product monthly rows, but measured on the 2024
holdout that granularity carries no signal:

| level | seasonal-naive WAPE | model WAPE |
|---|---|---|
| district × product × month | 136.8% | 99.2% |
| district × quarter | 72.2% | **59.8%** |

At product-month level, "predict zero" scores exactly 100.0% — so a 99.2%
model is worth nothing over forecasting nothing, and it gets there by hedging
toward zero (bias −42.0). Aggregating to district-quarter is where a model
starts beating its baseline by a real margin.

Numbers above are from xgboost 3.4.1 on the seeded database (107 quarterly
rows: 52 fit / 28 calibrate / 27 test). An earlier xgboost 2.x run recorded
57.6% at district-quarter; the conclusion is unchanged, but re-run `train.py`
rather than trusting either figure after a dependency bump.

## Which forecaster actually ships

`train.py` compares the model against the seasonal naive on the holdout and
records the verdict as `use_model` in the artifact metadata. `predict.py`
**honours it**: if the model loses, the forecast is produced by the seasonal
naive instead, using the baseline's own conformal offsets, and every row is
written under `model_version = <version>_baseline` so a dashboard row can never
claim to come from a model that was benched. Force it either way with
`predict.py --force-baseline`.

Because the two paths write different labels, each write clears the sibling
label as well — otherwise the night a retrain flips the verdict would leave
both sets in `forecast` and double every number on the dashboard.

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

XGBoost's quantile heads gave **48.1%** coverage against an 80% target — the
stated range excluded the truth half the time. The interval is therefore rebuilt
by split conformal prediction from residuals on a fold used for nothing else,
which brings coverage to **81.5%** (offsets −1997/+1706 packets on ~2000 mean
quarterly volume). That width is the honest answer for this data.

Two things make that a real conformal interval rather than a percentile of
convenience, and both were needed to hit the target:

* **The calibration fold is clean.** Early stopping is gone — its only possible
  eval set was the calibration year, and reusing it meant the interval width was
  derived from data the fit had already seen. Dropping it costs nothing measured
  (WAPE is flat at 58–60% for `n_estimators` anywhere in 100..900; shallow trees
  on 52 rows plateau early) and the fold becomes genuinely untouched.
* **The quantile level carries the finite-sample correction**,
  `ceil((n+1)(1−α/2))/n` rather than a plain 90th percentile. At n = 28 that is
  the difference between 63% and 81.5% coverage.

The seasonal-naive baseline gets its own offsets (−2036/+2631, coverage 85.2%),
so the fallback path is not left inventing a width.

## Units

**Packets**, matching `historical_sales.qty_in_pkts`. Nothing here produces
metric tons. The API used to expose these as `quantity_mt` / `forecast_mt` /
`current_stock_mt`; those were renamed and a `unit` field added, because a
1000× mislabel on a dispatch decision is not a cosmetic problem.

## The planning window is derived, not fixed

`run_nightly.sh` plans for the quarter **after** the current one, computed from
`date`. It used to hardcode 2026-Q3, which meant every night forever would
rebuild `recommendations` for one long-past quarter while the dashboard looked
live. `TARGET_YEAR` / `TARGET_QUARTER` / `THROUGH_YEAR` still override it for a
backfill.

Paired with that, `predict.py` always forecasts at least 4 quarters past the
last observation. A derived window will eventually name a quarter the loaded
sales data has already passed, and the old code raised `SystemExit` there —
which under `set -e` would have killed the nightly job outright.

## Known limits

- **Sales data ends 2024-12.** Any 2026 row is a 7–8 quarter extrapolation with
  recursive lags, labelled `Allocated: Very Low`. Fix by loading newer sales.
- **No weather forecast.** `weather_forecast` is empty and no API is wired up,
  so future weather features use the climatological mean per district-quarter.
  This is the one open dependency in Job 1 — it needs a weather provider and a
  credential, not more code. The fallback is implemented and labelled.
- **4 products are excluded.** Urea/DAP/MOP/NPK (ids 26–29) were added to
  `products` for dashboard parity and have zero real sales — nothing to learn.
  24 of the 25 remaining products get forecast rows.
- **`intent_acres` covers 2023+ only**, so it is NaN for most of the panel.
  Left as NaN deliberately; XGBoost splits on missingness.
- **Bias is +215 packets per district-quarter** (over-forecasting). For supply
  planning that is the safer direction, but it is not zero.
- **Retraining nightly is currently pointless** — the underlying sales data is
  static. The script does it anyway so the pipeline is correct once data flows.
