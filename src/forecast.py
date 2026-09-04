"""Seasonal naive + ETS forecasts. Applies new-release bias from network.yaml."""

from __future__ import annotations

import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from src.generate import load_yaml


def _ets_forecast(history: pd.Series, steps: int) -> list[float]:
    y = history.astype(float).clip(lower=0.1)
    if len(y) < 26:
        return [float(y.iloc[-1])] * steps
    try:
        fit = ExponentialSmoothing(
            y,
            trend="add",
            seasonal="add",
            seasonal_periods=13,
            initialization_method="estimated",
        ).fit(optimized=True)
        return [max(0.1, float(v)) for v in fit.forecast(steps)]
    except Exception:
        return [float(y.iloc[-1])] * steps


def run(star: dict[str, pd.DataFrame]) -> pd.DataFrame:
    network = load_yaml("network.yaml")
    demand = star["fact_demand"]
    dates = star["dim_date"]
    bias = {b["id"]: b["forecast_bias"] for b in network["brands"]}
    n_plan = network["planning_weeks"]
    n_fcst = network["forecast_weeks"]
    rows = []
    keys = demand[["brand_id", "market_id"]].drop_duplicates()
    for rec in keys.itertuples(index=False):
        series = (
            demand[(demand["brand_id"] == rec.brand_id) & (demand["market_id"] == rec.market_id)]
            .sort_values("week_id")
        )
        prior = series[series["year_index"] == 0]["actual_cases"].reset_index(drop=True)
        plan = series[series["year_index"] == 1]["actual_cases"].reset_index(drop=True)
        naive_plan = prior.tolist()
        ets_plan = _ets_forecast(prior, n_plan)
        last52 = pd.concat([prior, plan], ignore_index=True)
        naive_future = plan.tolist()[:n_fcst]
        ets_future = _ets_forecast(last52, n_fcst)
        factor = bias[rec.brand_id]
        plan_weeks = dates[dates["year_index"] == 1].sort_values("week_id")
        for i, drow in enumerate(plan_weeks.itertuples(index=False)):
            rows.append(
                {
                    "brand_id": rec.brand_id,
                    "market_id": rec.market_id,
                    "week_id": drow.week_id,
                    "year_index": 1,
                    "planning_week": drow.planning_week,
                    "model_name": "seasonal_naive",
                    "forecast_cases": naive_plan[i] * factor,
                }
            )
            rows.append(
                {
                    "brand_id": rec.brand_id,
                    "market_id": rec.market_id,
                    "week_id": drow.week_id,
                    "year_index": 1,
                    "planning_week": drow.planning_week,
                    "model_name": "ets",
                    "forecast_cases": ets_plan[i] * factor,
                }
            )
        fcst_weeks = dates[dates["year_index"] == 2].sort_values("week_id")
        for i, drow in enumerate(fcst_weeks.itertuples(index=False)):
            rows.append(
                {
                    "brand_id": rec.brand_id,
                    "market_id": rec.market_id,
                    "week_id": drow.week_id,
                    "year_index": 2,
                    "planning_week": drow.planning_week,
                    "model_name": "seasonal_naive",
                    "forecast_cases": naive_future[i] * factor,
                }
            )
            rows.append(
                {
                    "brand_id": rec.brand_id,
                    "market_id": rec.market_id,
                    "week_id": drow.week_id,
                    "year_index": 2,
                    "planning_week": drow.planning_week,
                    "model_name": "ets",
                    "forecast_cases": ets_future[i] * factor,
                }
            )
    return pd.DataFrame(rows)
