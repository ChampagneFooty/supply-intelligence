"""WAPE, MAPE and bias by brand, market, tier and total. Planning year only."""

from __future__ import annotations

import pandas as pd

from src.generate import load_yaml


def _metrics(g: pd.DataFrame) -> pd.Series:
    actual = g["actual_cases"]
    fcst = g["forecast_cases"]
    denom = actual.abs().sum()
    wape = float((actual - fcst).abs().sum() / denom) if denom else 0.0
    nz = actual != 0
    mape = float(((actual[nz] - fcst[nz]).abs() / actual[nz].abs()).mean()) if nz.any() else 0.0
    bias = float((fcst - actual).sum() / actual.sum()) if actual.sum() else 0.0
    return pd.Series({"wape": wape, "mape": mape, "bias": bias, "actual_sum": float(actual.sum())})


def run(star: dict[str, pd.DataFrame], forecast: pd.DataFrame) -> pd.DataFrame:
    network = load_yaml("network.yaml")
    tier = {b["id"]: b["tier"] for b in network["brands"]}
    demand = star["fact_demand"]
    plan = forecast[forecast["year_index"] == 1]
    merged = plan.merge(
        demand[["brand_id", "market_id", "week_id", "actual_cases"]],
        on=["brand_id", "market_id", "week_id"],
        how="inner",
    )
    merged["tier"] = merged["brand_id"].map(tier)
    frames = []
    for grain, cols in [
        ("total", ["model_name"]),
        ("brand", ["model_name", "brand_id"]),
        ("market", ["model_name", "market_id"]),
        ("tier", ["model_name", "tier"]),
        ("brand_market", ["model_name", "brand_id", "market_id"]),
    ]:
        metrics = merged.groupby(cols).apply(_metrics, include_groups=False).reset_index()
        metrics["grain"] = grain
        frames.append(metrics)
    out = pd.concat(frames, ignore_index=True)
    out["calc_id"] = out.apply(
        lambda r: f"acc:{r.grain}:{r.model_name}:{r.get('brand_id', '')}:{r.get('market_id', '')}:{r.get('tier', '')}",
        axis=1,
    )
    return out
