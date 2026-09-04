"""Assemble insight_pack.json and Power BI CSVs. No LLM."""

from __future__ import annotations

import json

import pandas as pd

from src import OUTPUTS, POWERBI
from src.generate import load_yaml


REQUIRED_KEYS = [
    "kpis",
    "exceptions",
    "accuracy_hierarchy",
    "scenario",
    "value_register",
    "portfolio",
    "planted",
]


def _jsonable(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def run(
    star: dict[str, pd.DataFrame],
    forecast: pd.DataFrame,
    accuracy: pd.DataFrame,
    exceptions: pd.DataFrame,
    scenario: pd.DataFrame,
    value_register: pd.DataFrame,
) -> dict:
    portfolio = load_yaml("portfolio.yaml")
    demand = star["fact_demand"]
    plan_demand = demand[demand["year_index"] == 1]
    naive_total = accuracy[(accuracy["grain"] == "total") & (accuracy["model_name"] == "seasonal_naive")].iloc[0]
    ets_total = accuracy[(accuracy["grain"] == "total") & (accuracy["model_name"] == "ets")].iloc[0]
    bulk = star["fact_bulk_inventory"]
    bottled = star["fact_bottled_inventory"]
    alloc = star["fact_allocation"]
    cap = star["fact_capacity"]
    plan_bulk = bulk[bulk["year_index"] == 1]
    plan_bot = bottled[bottled["year_index"] == 1]
    plan_alloc = alloc[alloc["year_index"] == 1]
    plan_cap = cap[cap["year_index"] == 1]
    below_cover = (plan_bot["weeks_of_cover"] < 4).mean()
    fill_proxy = 1 - float(below_cover)
    peak_util = float(
        (plan_cap["utilised_cases"] / plan_cap["bottling_capacity_cases"].clip(lower=0.1)).max()
    )
    planted_ids = set(exceptions["planted_id"].dropna().unique())
    harvest_weeks = scenario[
        (scenario["metric"] == "harvest_intake_litres")
        & (scenario["year_index"] == 1)
        & (scenario["planning_week"].between(10, 14))
        & (scenario["baseline"] > 0)
    ]
    pack = {
        "kpis": {
            "wape_seasonal_naive": float(naive_total["wape"]),
            "wape_ets": float(ets_total["wape"]),
            "bias_seasonal_naive": float(naive_total["bias"]),
            "bias_ets": float(ets_total["bias"]),
            "fill_rate_proxy": fill_proxy,
            "pct_bottled_below_cover": float(below_cover),
            "capacity_peak_utilisation": peak_util,
            "value_at_risk_total": float(value_register["value_at_risk"].sum()) if len(value_register) else 0.0,
            "exception_count": int(len(exceptions)),
            "calc_id": "kpi:summary",
        },
        "exceptions": exceptions.where(exceptions.notna(), None).to_dict(orient="records"),
        "accuracy_hierarchy": accuracy.where(accuracy.notna(), None).to_dict(orient="records"),
        "scenario": {
            "id": "harvest_shortfall",
            "intake_shocked_over_baseline": float(
                (harvest_weeks["shocked"] / harvest_weeks["baseline"]).mean()
            )
            if len(harvest_weeks)
            else None,
            "rows": scenario[scenario["year_index"] == 1].head(400).to_dict(orient="records"),
            "calc_id": "scn:harvest_shortfall",
        },
        "value_register": value_register.to_dict(orient="records"),
        "portfolio": portfolio["use_cases"],
        "planted": {
            "P1": "P1" in planted_ids,
            "P2": "P2" in planted_ids,
            "P3": "P3" in planted_ids,
            "detected_count": int(sum(x in planted_ids for x in ("P1", "P2", "P3"))),
        },
        "planning_year_actual_cases": float(plan_demand["actual_cases"].sum()),
        "mean_allocation_ratio": float(plan_alloc["allocation_ratio"].mean()),
        "mean_bulk_cover": float(plan_bulk["weeks_of_cover"].mean()),
    }
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    POWERBI.mkdir(parents=True, exist_ok=True)
    with open(OUTPUTS / "insight_pack.json", "w", encoding="utf-8") as handle:
        json.dump(pack, handle, indent=2, default=_jsonable)
    csv_tables = {
        "dim_date": star["dim_date"],
        "dim_brand": star["dim_brand"],
        "dim_market": star["dim_market"],
        "dim_site": star["dim_site"],
        "dim_vintage": star["dim_vintage"],
        "fact_demand": star["fact_demand"],
        "fact_forecast": forecast,
        "fact_accuracy": accuracy,
        "fact_bulk_inventory": star["fact_bulk_inventory"],
        "fact_bottled_inventory": star["fact_bottled_inventory"],
        "fact_allocation": star["fact_allocation"],
        "fact_capacity": star["fact_capacity"],
        "fact_bottling": star["fact_bottling"],
        "fact_exception": exceptions,
        "fact_scenario": scenario,
        "fact_value_register": value_register,
    }
    for name, frame in csv_tables.items():
        frame.to_csv(POWERBI / f"{name}.csv", index=False)
        frame.to_parquet(star_path(name), index=False)
    return pack


def star_path(name: str):
    from src import DATA_STAR

    return DATA_STAR / f"{name}.parquet"
