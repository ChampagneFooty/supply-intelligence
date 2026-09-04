"""Value register: volume at risk × synthetic ASP × (1 − expected fill)."""

from __future__ import annotations

import pandas as pd

from src.generate import load_yaml


def run(star: dict[str, pd.DataFrame], exceptions: pd.DataFrame) -> pd.DataFrame:
    network = load_yaml("network.yaml")
    rules = load_yaml("rules.yaml")
    asp = {b["id"]: network["tiers"][b["tier"]]["asp_per_case"] for b in network["brands"]}
    demand = star["fact_demand"]
    weekly = demand.groupby(["brand_id", "week_id"], as_index=False)["actual_cases"].sum()
    rows = []
    for rec in exceptions.itertuples(index=False):
        if rec.severity not in {"high", "medium"}:
            continue
        brand_id = rec.brand_id or "B01"
        volume = 0.0
        if rec.week_id is not None:
            hit = weekly[(weekly["brand_id"] == brand_id) & (weekly["week_id"] == rec.week_id)]
            volume = float(hit["actual_cases"].sum()) if len(hit) else 0.0
        else:
            hit = weekly[weekly["brand_id"] == brand_id]
            volume = float(hit["actual_cases"].mean()) if len(hit) else 0.0
        if rec.type == "allocation_shortfall":
            expected_fill = rules["expected_fill_if_allocation_breach"]
            volume = volume * (1 - float(rec.value))
        elif rec.type in {"capacity_loss", "capacity_utilisation"}:
            expected_fill = rules["expected_fill_if_capacity_breach"]
            volume = volume * 0.35
        elif rec.type in {"harvest_shortfall", "bulk_cover", "bottled_cover"}:
            expected_fill = rules["expected_fill_if_cover_breach"]
            volume = volume * 0.25
        else:
            expected_fill = 0.90
            volume = volume * 0.10
        unit_asp = asp.get(brand_id, 85)
        dollars = volume * unit_asp * (1 - expected_fill)
        rows.append(
            {
                "exception_id": rec.exception_id,
                "planted_id": rec.planted_id,
                "type": rec.type,
                "brand_id": rec.brand_id,
                "volume_at_risk": volume,
                "asp_per_case": unit_asp,
                "expected_fill": expected_fill,
                "value_at_risk": dollars,
                "driver": rec.entity_ref,
                "recommended_action_code": _action(rec.type),
                "calc_id": f"val:{rec.exception_id}",
            }
        )
    return pd.DataFrame(rows)


def _action(exc_type: str) -> str:
    return {
        "harvest_shortfall": "REALLOCATE_BULK",
        "bulk_cover": "PROTECT_LUXURY_ALLOCATION",
        "allocation_shortfall": "HOLD_UK_ALLOCATION_REVIEW",
        "bottled_cover": "EXPEDITE_TRANSFER",
        "capacity_loss": "SHIFT_BOTTLING_WINDOW",
        "capacity_utilisation": "SHIFT_BOTTLING_WINDOW",
        "forecast_bias": "RESET_NEW_RELEASE_FORECAST",
        "forecast_wape": "RESET_NEW_RELEASE_FORECAST",
    }.get(exc_type, "REVIEW")
