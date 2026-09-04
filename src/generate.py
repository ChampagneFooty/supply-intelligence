"""Build the Vintara synthetic wine network. No analytics here."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import yaml

from src import CONFIG, DATA_STAR


def load_yaml(name: str) -> dict:
    with open(CONFIG / name, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_dates(network: dict) -> pd.DataFrame:
    n_hist = network["history_weeks"]
    n_plan = network["planning_weeks"]
    n_fcst = network["forecast_weeks"]
    start = date(network["prior_year"], 1, 5)
    rows = []
    for week_id in range(1, n_hist + n_plan + n_fcst + 1):
        if week_id <= n_hist:
            year_index = 0
            planning_week = week_id
        elif week_id <= n_hist + n_plan:
            year_index = 1
            planning_week = week_id - n_hist
        else:
            year_index = 2
            planning_week = week_id - n_hist
        week_start = start + timedelta(weeks=week_id - 1)
        month = week_start.month
        quarter = (month - 1) // 3 + 1
        is_harvest = planning_week in set(network["barossa_harvest_weeks"]) or planning_week in set(
            network["napa_harvest_weeks"]
        )
        rows.append(
            {
                "week_id": week_id,
                "week_start": week_start.isoformat(),
                "year_index": year_index,
                "planning_week": planning_week,
                "month": month,
                "quarter": quarter,
                "is_harvest": int(is_harvest),
            }
        )
    return pd.DataFrame(rows)


def seasonal_factor(market_id: str, planning_week: int) -> float:
    if market_id in {"M_UK", "M_US", "M_EU", "M_AS"} and planning_week >= 40:
        return 1.22
    if market_id == "M_AU" and (planning_week >= 48 or planning_week <= 8):
        return 1.12
    if 20 <= planning_week <= 24:
        return 1.05
    return 1.0


def build_demand(network: dict, dates: pd.DataFrame, planted: dict) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    hist_plan = dates[dates["year_index"] < 2]
    p2 = next(p for p in planted["problems"] if p["id"] == "P2")
    rows = []
    for brand in network["brands"]:
        for market in network["markets"]:
            for rec in hist_plan.itertuples(index=False):
                noise = float(np.clip(rng.normal(1.0, 0.04), 0.88, 1.12))
                base = brand["base_weekly_cases"] * market["share"] * seasonal_factor(market["id"], rec.planning_week)
                unconstrained = max(1.0, base * noise)
                actual = unconstrained
                rows.append(
                    {
                        "brand_id": brand["id"],
                        "market_id": market["id"],
                        "week_id": rec.week_id,
                        "year_index": rec.year_index,
                        "planning_week": rec.planning_week,
                        "unconstrained_demand": unconstrained,
                        "actual_cases": actual,
                        "promo_flag": int(rec.planning_week >= 40 and rec.planning_week <= 48),
                    }
                )
    demand = pd.DataFrame(rows)

    allocation_factor = demand["brand_id"].map(
        {b["id"]: (0.92 if b["tier"] == "luxury" else 1.0) for b in network["brands"]}
    )
    demand["allocated_cases"] = demand["unconstrained_demand"] * allocation_factor

    mask = (
        (demand["brand_id"] == p2["brand_id"])
        & (demand["market_id"] == p2["market_id"])
        & (demand["year_index"] == 1)
        & (demand["planning_week"].isin(p2["planning_weeks"]))
    )
    demand.loc[mask, "unconstrained_demand"] *= p2["demand_factor"]
    demand.loc[mask, "actual_cases"] *= p2["demand_factor"]
    return demand


def build_ops(network: dict, dates: pd.DataFrame, demand: pd.DataFrame, planted: dict):
    p3 = next(p for p in planted["problems"] if p["id"] == "P3")
    brand_home = {b["id"]: b["home_site"] for b in network["brands"]}
    demand = demand.copy()
    demand["home_site"] = demand["brand_id"].map(brand_home)
    weekly_brand = (
        demand.groupby(["brand_id", "week_id", "year_index", "planning_week", "home_site"], as_index=False)[
            "actual_cases"
        ].sum()
        .rename(columns={"actual_cases": "planned_cases"})
    )

    bottling = weekly_brand.rename(columns={"home_site": "site_id"})
    bottling["actual_cases"] = bottling["planned_cases"]
    bottling["line_hours"] = bottling["planned_cases"] / 80.0

    site_week = bottling.groupby(["site_id", "week_id", "year_index", "planning_week"], as_index=False)["planned_cases"].sum()
    typical = site_week.groupby("site_id")["planned_cases"].median()
    capacity_rows = []
    for rec in site_week.itertuples(index=False):
        planned_cap = float(typical[rec.site_id]) * 1.15
        actual_cap = planned_cap
        if (
            rec.site_id == p3["site_id"]
            and rec.year_index == 1
            and rec.planning_week in p3["planning_weeks"]
        ):
            actual_cap = planned_cap * p3["capacity_factor"]
        utilised = min(float(rec.planned_cases), actual_cap)
        capacity_rows.append(
            {
                "site_id": rec.site_id,
                "week_id": rec.week_id,
                "year_index": rec.year_index,
                "planning_week": rec.planning_week,
                "planned_capacity_cases": planned_cap,
                "bottling_capacity_cases": actual_cap,
                "utilised_cases": utilised,
                "planned_bottling_cases": rec.planned_cases,
            }
        )
    capacity = pd.DataFrame(capacity_rows)

    cap_lookup = capacity.set_index(["site_id", "week_id"])["utilised_cases"]
    plan_lookup = capacity.set_index(["site_id", "week_id"])["planned_bottling_cases"]

    def scale_actual(row):
        planned_site = plan_lookup.loc[(row.site_id, row.week_id)]
        utilised = cap_lookup.loc[(row.site_id, row.week_id)]
        if planned_site <= 0:
            return row.planned_cases
        return row.planned_cases * (utilised / planned_site)

    bottling["actual_cases"] = bottling.apply(scale_actual, axis=1)

    uk_markets = {"M_UK", "M_EU"}
    uk_demand = demand[demand["market_id"].isin(uk_markets)]
    uk_weekly = uk_demand.groupby(["brand_id", "week_id"], as_index=False)["actual_cases"].sum()
    lead = network["uk_transfer_lead_weeks"]
    transfers = uk_weekly.rename(columns={"actual_cases": "cases"})
    transfers["from_site"] = transfers["brand_id"].map(brand_home)
    transfers["to_site"] = "S_UKDC"
    transfers["lead_time_days"] = lead * 7
    transfers["arrive_week_id"] = transfers["week_id"] + lead
    return bottling, capacity, transfers


def build_bulk(network: dict, dates: pd.DataFrame, bottling: pd.DataFrame, planted: dict) -> pd.DataFrame:
    p1 = next(p for p in planted["problems"] if p["id"] == "P1")
    litres = network["litres_per_case"]
    harvest = {s["id"]: set(network["barossa_harvest_weeks"] if s["id"] == "S_BAR" else network["napa_harvest_weeks"]) for s in network["sites"] if s["type"] == "cellar_bottling"}
    rows = []
    hist_plan = dates[dates["year_index"] < 2]
    for brand in network["brands"]:
        site_id = brand["home_site"]
        brand_bot = bottling[bottling["brand_id"] == brand["id"]].set_index("week_id")
        weekly_out = float(brand_bot["actual_cases"].mean()) * litres
        n_harvest = len(harvest[site_id])
        planned_weekly_intake = weekly_out * network["planning_weeks"] / n_harvest
        stock = 16.0 * weekly_out
        for rec in hist_plan.itertuples(index=False):
            if rec.week_id not in brand_bot.index:
                continue
            outflow = float(brand_bot.loc[rec.week_id, "actual_cases"]) * litres
            planned_intake = planned_weekly_intake if rec.planning_week in harvest[site_id] else 0.0
            intake = planned_intake
            if (
                site_id == p1["site_id"]
                and rec.year_index == 1
                and rec.planning_week in p1["planning_weeks"]
            ):
                intake = planned_intake * p1["intake_factor"]
            stock = max(0.0, stock + intake - outflow)
            rows.append(
                {
                    "brand_id": brand["id"],
                    "vintage_id": brand["vintage_id"],
                    "site_id": site_id,
                    "week_id": rec.week_id,
                    "year_index": rec.year_index,
                    "planning_week": rec.planning_week,
                    "litres_on_hand": stock,
                    "planned_intake_litres": planned_intake,
                    "intake_litres": intake,
                    "outflow_litres": outflow,
                }
            )
    return pd.DataFrame(rows)


def build_bottled(network: dict, dates: pd.DataFrame, demand: pd.DataFrame, bottling: pd.DataFrame, transfers: pd.DataFrame) -> pd.DataFrame:
    hist_plan = dates[dates["year_index"] < 2]
    safety = {tier: spec["safety_weeks"] for tier, spec in network["tiers"].items()}
    service = {tier: spec["target_service_level"] for tier, spec in network["tiers"].items()}
    arrivals = transfers.groupby(["brand_id", "arrive_week_id"], as_index=False)["cases"].sum()
    arrivals = arrivals.rename(columns={"arrive_week_id": "week_id", "cases": "arrivals"})
    ship = transfers.groupby(["brand_id", "week_id"], as_index=False)["cases"].sum().rename(columns={"cases": "shipped"})
    demand_by = demand.groupby(["brand_id", "week_id"], as_index=False)["actual_cases"].sum()
    uk_demand = demand[demand["market_id"].isin(["M_UK", "M_EU"])].groupby(["brand_id", "week_id"], as_index=False)["actual_cases"].sum()
    uk_demand = uk_demand.rename(columns={"actual_cases": "uk_demand"})

    rows = []
    for brand in network["brands"]:
        avg = brand["base_weekly_cases"]
        cellar_stock = 8.0 * avg * 0.65
        dc_stock = 10.0 * avg * 0.35
        for rec in hist_plan.itertuples(index=False):
            btl = bottling[(bottling["brand_id"] == brand["id"]) & (bottling["week_id"] == rec.week_id)]
            produced = float(btl["actual_cases"].sum()) if len(btl) else 0.0
            shipped = float(ship.loc[ship["brand_id"].eq(brand["id"]) & ship["week_id"].eq(rec.week_id), "shipped"].sum())
            arrived = float(arrivals.loc[arrivals["brand_id"].eq(brand["id"]) & arrivals["week_id"].eq(rec.week_id), "arrivals"].sum())
            total_d = float(demand_by.loc[demand_by["brand_id"].eq(brand["id"]) & demand_by["week_id"].eq(rec.week_id), "actual_cases"].sum())
            uk_d = float(uk_demand.loc[uk_demand["brand_id"].eq(brand["id"]) & uk_demand["week_id"].eq(rec.week_id), "uk_demand"].sum())
            cellar_demand = max(0.0, total_d - uk_d)
            cellar_stock = max(0.0, cellar_stock + produced - shipped - cellar_demand)
            dc_stock = max(0.0, dc_stock + arrived - uk_d)
            ss = safety[brand["tier"]] * (avg / 5.0)
            rows.append(
                {
                    "brand_id": brand["id"],
                    "site_id": brand["home_site"],
                    "week_id": rec.week_id,
                    "year_index": rec.year_index,
                    "planning_week": rec.planning_week,
                    "cases_on_hand": cellar_stock,
                    "safety_stock": ss,
                    "target_service_level": service[brand["tier"]],
                }
            )
            rows.append(
                {
                    "brand_id": brand["id"],
                    "site_id": "S_UKDC",
                    "week_id": rec.week_id,
                    "year_index": rec.year_index,
                    "planning_week": rec.planning_week,
                    "cases_on_hand": dc_stock,
                    "safety_stock": ss * 0.4,
                    "target_service_level": service[brand["tier"]],
                }
            )
    return pd.DataFrame(rows)


def build_allocation(demand: pd.DataFrame) -> pd.DataFrame:
    out = demand[
        [
            "brand_id",
            "market_id",
            "week_id",
            "year_index",
            "planning_week",
            "allocated_cases",
            "unconstrained_demand",
        ]
    ].copy()
    return out


def write_star(tables: dict[str, pd.DataFrame]) -> None:
    DATA_STAR.mkdir(parents=True, exist_ok=True)
    for name, frame in tables.items():
        frame.to_parquet(DATA_STAR / f"{name}.parquet", index=False)


def main() -> None:
    network = load_yaml("network.yaml")
    planted = load_yaml("planted.yaml")
    dates = build_dates(network)
    brands = pd.DataFrame(network["brands"])
    markets = pd.DataFrame(network["markets"])
    sites = pd.DataFrame(network["sites"])
    vintages = pd.DataFrame(network["vintages"])
    demand = build_demand(network, dates, planted)
    bottling, capacity, transfers = build_ops(network, dates, demand, planted)
    bulk = build_bulk(network, dates, bottling, planted)
    bottled = build_bottled(network, dates, demand, bottling, transfers)
    allocation = build_allocation(demand)
    fact_demand = demand[
        [
            "brand_id",
            "market_id",
            "week_id",
            "year_index",
            "planning_week",
            "actual_cases",
            "unconstrained_demand",
            "promo_flag",
        ]
    ]
    write_star(
        {
            "dim_date": dates,
            "dim_brand": brands,
            "dim_market": markets,
            "dim_site": sites,
            "dim_vintage": vintages,
            "fact_demand": fact_demand,
            "fact_bottling": bottling,
            "fact_capacity": capacity,
            "fact_transfer": transfers,
            "fact_bulk_inventory": bulk,
            "fact_bottled_inventory": bottled,
            "fact_allocation": allocation,
        }
    )


def tables_count(path) -> int:
    return len(list(path.glob("*.parquet")))


if __name__ == "__main__":
    main()
    print(f"Wrote star tables to {DATA_STAR} ({tables_count(DATA_STAR)} files)")
