"""Harvest -30% scenario vs planned intake. Re-rolls Barossa bulk stock."""

from __future__ import annotations

import pandas as pd

from src.generate import load_yaml


def run(star: dict[str, pd.DataFrame]) -> pd.DataFrame:
    cfg = load_yaml("scenarios.yaml")["demo"]
    bulk = star["fact_bulk_inventory"].copy()
    barossa = bulk[bulk["site_id"] == cfg["site_id"]].sort_values(["brand_id", "week_id"])
    litres = load_yaml("network.yaml")["litres_per_case"]
    rows = []
    for brand_id, grp in barossa.groupby("brand_id"):
        grp = grp.sort_values("week_id")
        baseline_stock = None
        shocked_stock = None
        for rec in grp.itertuples(index=False):
            if baseline_stock is None:
                # opening stock is on-hand before this week's flow; reverse actual flow
                opening = rec.litres_on_hand - rec.intake_litres + rec.outflow_litres
                baseline_stock = opening
                shocked_stock = opening
            baseline_intake = rec.planned_intake_litres
            shocked_intake = rec.planned_intake_litres
            if rec.year_index == 1 and rec.planning_week in cfg["planning_weeks"]:
                shocked_intake = rec.planned_intake_litres * cfg["intake_factor"]
            baseline_stock = max(0.0, baseline_stock + baseline_intake - rec.outflow_litres)
            shocked_stock = max(0.0, shocked_stock + shocked_intake - rec.outflow_litres)
            weekly_use = rec.outflow_litres if rec.outflow_litres else litres
            rows.append(
                {
                    "scenario_id": cfg["id"],
                    "brand_id": brand_id,
                    "site_id": rec.site_id,
                    "week_id": rec.week_id,
                    "year_index": rec.year_index,
                    "planning_week": rec.planning_week,
                    "metric": "harvest_intake_litres",
                    "baseline": baseline_intake,
                    "shocked": shocked_intake,
                    "delta": shocked_intake - baseline_intake,
                }
            )
            rows.append(
                {
                    "scenario_id": cfg["id"],
                    "brand_id": brand_id,
                    "site_id": rec.site_id,
                    "week_id": rec.week_id,
                    "year_index": rec.year_index,
                    "planning_week": rec.planning_week,
                    "metric": "bulk_cover_weeks",
                    "baseline": baseline_stock / weekly_use,
                    "shocked": shocked_stock / weekly_use,
                    "delta": (shocked_stock - baseline_stock) / weekly_use,
                }
            )
    return pd.DataFrame(rows)
