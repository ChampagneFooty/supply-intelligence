"""Rule-based exceptions. Planted IDs are attached when the shock window and entity match."""

from __future__ import annotations

import pandas as pd

from src.generate import load_yaml


def run(star: dict[str, pd.DataFrame], accuracy: pd.DataFrame) -> pd.DataFrame:
    rules = load_yaml("rules.yaml")
    planted = load_yaml("planted.yaml")
    p1, p2, p3 = planted["problems"]
    rows = []
    n = 0

    def add(**kwargs):
        nonlocal n
        n += 1
        kwargs["exception_id"] = f"EXC{n:04d}"
        kwargs["calc_id"] = f"exc:{kwargs['exception_id']}"
        rows.append(kwargs)

    bulk = star["fact_bulk_inventory"]
    plan_bulk = bulk[bulk["year_index"] == 1]
    for rec in plan_bulk.itertuples(index=False):
        harvest_short = rec.planned_intake_litres > 0 and rec.intake_litres < 0.8 * rec.planned_intake_litres
        cover_low = rec.weeks_of_cover < rules["bulk_cover_exception_weeks"] and rec.planning_week >= 15
        if harvest_short or cover_low:
            planted_id = None
            if rec.site_id == p1["site_id"] and (
                rec.planning_week in p1["planning_weeks"]
                or (cover_low and rec.planning_week >= 15)
            ):
                planted_id = "P1"
            if harvest_short or cover_low:
                add(
                    type="harvest_shortfall" if harvest_short else "bulk_cover",
                    severity="high" if harvest_short or rec.weeks_of_cover < 8 else "medium",
                    brand_id=rec.brand_id,
                    site_id=rec.site_id,
                    market_id="",
                    week_id=rec.week_id,
                    planning_week=rec.planning_week,
                    planted_id=planted_id,
                    value=float(rec.intake_litres if harvest_short else rec.weeks_of_cover),
                    entity_ref=f"{rec.brand_id}|{rec.site_id}|{rec.week_id}",
                )

    alloc = star["fact_allocation"]
    plan_alloc = alloc[alloc["year_index"] == 1]
    for rec in plan_alloc.itertuples(index=False):
        if rec.allocation_ratio < rules["allocation_ratio_exception"]:
            planted_id = (
                "P2"
                if rec.brand_id == p2["brand_id"]
                and rec.market_id == p2["market_id"]
                and rec.planning_week in p2["planning_weeks"]
                else None
            )
            add(
                type="allocation_shortfall",
                severity="high" if rec.allocation_ratio < 0.75 else "medium",
                brand_id=rec.brand_id,
                site_id="",
                market_id=rec.market_id,
                week_id=rec.week_id,
                planning_week=rec.planning_week,
                planted_id=planted_id,
                value=float(rec.allocation_ratio),
                entity_ref=f"{rec.brand_id}|{rec.market_id}|{rec.week_id}",
            )

    bottled = star["fact_bottled_inventory"]
    plan_bot = bottled[(bottled["year_index"] == 1) & (bottled["weeks_of_cover"] < rules["bottled_cover_exception_weeks"])]
    for rec in plan_bot.itertuples(index=False):
        planted_id = None
        if rec.brand_id == p2["brand_id"] and rec.site_id == "S_UKDC" and rec.planning_week in p2["planning_weeks"]:
            planted_id = "P2"
        if rec.site_id == p3["site_id"] and rec.planning_week in list(range(32, 40)):
            planted_id = planted_id or "P3"
        add(
            type="bottled_cover",
            severity="high" if rec.weeks_of_cover < 2 else "medium",
            brand_id=rec.brand_id,
            site_id=rec.site_id,
            market_id="",
            week_id=rec.week_id,
            planning_week=rec.planning_week,
            planted_id=planted_id,
            value=float(rec.weeks_of_cover),
            entity_ref=f"{rec.brand_id}|{rec.site_id}|{rec.week_id}",
        )

    cap = star["fact_capacity"]
    plan_cap = cap[cap["year_index"] == 1]
    for rec in plan_cap.itertuples(index=False):
        util = rec.utilised_cases / rec.bottling_capacity_cases if rec.bottling_capacity_cases else 0
        lost = rec.bottling_capacity_cases < 0.8 * rec.planned_capacity_cases
        if util >= rules["capacity_utilisation_exception"] or lost:
            planted_id = (
                "P3"
                if rec.site_id == p3["site_id"] and rec.planning_week in p3["planning_weeks"]
                else None
            )
            add(
                type="capacity_loss" if lost else "capacity_utilisation",
                severity="high" if lost else "medium",
                brand_id="",
                site_id=rec.site_id,
                market_id="",
                week_id=rec.week_id,
                planning_week=rec.planning_week,
                planted_id=planted_id,
                value=float(util if not lost else rec.bottling_capacity_cases / rec.planned_capacity_cases),
                entity_ref=f"{rec.site_id}|{rec.week_id}",
            )

    brand_acc = accuracy[(accuracy["grain"] == "brand") & (accuracy["model_name"] == "seasonal_naive")]
    for rec in brand_acc.itertuples(index=False):
        if rec.wape >= rules["wape_exception"] or abs(rec.bias) >= rules["bias_abs_exception"]:
            add(
                type="forecast_bias" if abs(rec.bias) >= rules["bias_abs_exception"] else "forecast_wape",
                severity="medium",
                brand_id=rec.brand_id,
                site_id="",
                market_id="",
                week_id=None,
                planning_week=None,
                planted_id="BIAS" if rec.brand_id == "B03" else None,
                value=float(rec.bias if abs(rec.bias) >= rules["bias_abs_exception"] else rec.wape),
                entity_ref=rec.calc_id,
            )

    return pd.DataFrame(rows)
