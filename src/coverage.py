"""Bulk and bottled weeks of cover, plus allocation ratio."""

from __future__ import annotations

import pandas as pd

from src.generate import load_yaml


def run(star: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    network = load_yaml("network.yaml")
    litres = network["litres_per_case"]
    demand = star["fact_demand"]
    weekly_demand = demand.groupby(["brand_id", "week_id"], as_index=False)["actual_cases"].sum()
    weekly_demand = weekly_demand.rename(columns={"actual_cases": "weekly_cases"})

    bulk = star["fact_bulk_inventory"].copy()
    bulk = bulk.merge(weekly_demand, on=["brand_id", "week_id"], how="left")
    bulk["weekly_cases"] = bulk["weekly_cases"].fillna(0.1)
    bulk["weeks_of_cover"] = bulk["litres_on_hand"] / (bulk["weekly_cases"] * litres)

    bottled = star["fact_bottled_inventory"].copy()
    site_demand = weekly_demand.copy()
    bottled = bottled.merge(site_demand, on=["brand_id", "week_id"], how="left")
    bottled["weekly_cases"] = bottled["weekly_cases"].fillna(0.1)
    # UK DC only serves UK+EU share (~0.35). Cellar serves the rest.
    uk_share = 0.35
    bottled.loc[bottled["site_id"] == "S_UKDC", "weekly_cases"] = bottled.loc[
        bottled["site_id"] == "S_UKDC", "weekly_cases"
    ] * uk_share
    bottled.loc[bottled["site_id"] != "S_UKDC", "weekly_cases"] = bottled.loc[
        bottled["site_id"] != "S_UKDC", "weekly_cases"
    ] * (1 - uk_share)
    bottled["weeks_of_cover"] = bottled["cases_on_hand"] / bottled["weekly_cases"].clip(lower=0.1)

    allocation = star["fact_allocation"].copy()
    allocation["allocation_ratio"] = allocation["allocated_cases"] / allocation["unconstrained_demand"].clip(
        lower=0.1
    )
    return {"fact_bulk_inventory": bulk, "fact_bottled_inventory": bottled, "fact_allocation": allocation}
