"""Build powerbi/Vintara Supply Insights.pbix from engine CSVs. Run after src.engine."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import POWERBI

OUT = ROOT / "powerbi" / "Vintara Supply Insights.pbix"


def _rows(name: str) -> list[dict]:
    frame = pd.read_csv(POWERBI / f"{name}.csv")
    frame = frame.where(frame.notna(), None)
    return frame.to_dict(orient="records")


def _cols(name: str, types: dict[str, str]) -> list[dict]:
    frame = pd.read_csv(POWERBI / f"{name}.csv", nrows=0)
    out = []
    for col in frame.columns:
        out.append({"name": col, "data_type": types.get(col, "String")})
    return out


def main() -> None:
    from pbix_mcp.builder import PBIXBuilder

    builder = PBIXBuilder()
    csv_dir = str(POWERBI.resolve())

    dim_types = {"id": "String"}
    builder.add_table("dim_brand", _cols("dim_brand", dim_types), rows=_rows("dim_brand"), source_csv=str(POWERBI / "dim_brand.csv"))
    builder.add_table("dim_market", _cols("dim_market", dim_types), rows=_rows("dim_market"), source_csv=str(POWERBI / "dim_market.csv"))
    builder.add_table("dim_site", _cols("dim_site", dim_types), rows=_rows("dim_site"), source_csv=str(POWERBI / "dim_site.csv"))
    builder.add_table(
        "dim_date",
        _cols("dim_date", {"week_id": "Int64", "year_index": "Int64", "planning_week": "Int64", "month": "Int64", "quarter": "Int64", "is_harvest": "Int64"}),
        rows=_rows("dim_date"),
        source_csv=str(POWERBI / "dim_date.csv"),
    )

    num = {
        "week_id": "Int64",
        "year_index": "Int64",
        "planning_week": "Int64",
        "wape": "Double",
        "mape": "Double",
        "bias": "Double",
        "actual_sum": "Double",
        "weeks_of_cover": "Double",
        "allocation_ratio": "Double",
        "allocated_cases": "Double",
        "unconstrained_demand": "Double",
        "actual_cases": "Double",
        "forecast_cases": "Double",
        "litres_on_hand": "Double",
        "intake_litres": "Double",
        "planned_intake_litres": "Double",
        "outflow_litres": "Double",
        "cases_on_hand": "Double",
        "safety_stock": "Double",
        "utilised_cases": "Double",
        "bottling_capacity_cases": "Double",
        "planned_capacity_cases": "Double",
        "value": "Double",
        "volume_at_risk": "Double",
        "asp_per_case": "Double",
        "value_at_risk": "Double",
        "baseline": "Double",
        "shocked": "Double",
        "delta": "Double",
        "expected_fill": "Double",
    }

    for table in [
        "fact_demand",
        "fact_accuracy",
        "fact_exception",
        "fact_value_register",
        "fact_scenario",
        "fact_allocation",
        "fact_bulk_inventory",
        "fact_bottled_inventory",
        "fact_capacity",
    ]:
        builder.add_table(table, _cols(table, num), rows=_rows(table), source_csv=str(POWERBI / f"{table}.csv"))

    builder.add_relationship("fact_demand", "brand_id", "dim_brand", "id")
    builder.add_relationship("fact_demand", "market_id", "dim_market", "id")
    builder.add_relationship("fact_demand", "week_id", "dim_date", "week_id")
    builder.add_relationship("fact_accuracy", "brand_id", "dim_brand", "id")
    builder.add_relationship("fact_exception", "brand_id", "dim_brand", "id")
    builder.add_relationship("fact_value_register", "exception_id", "fact_exception", "exception_id")
    builder.add_relationship("fact_allocation", "brand_id", "dim_brand", "id")
    builder.add_relationship("fact_allocation", "market_id", "dim_market", "id")
    builder.add_relationship("fact_bulk_inventory", "brand_id", "dim_brand", "id")
    builder.add_relationship("fact_bulk_inventory", "site_id", "dim_site", "id")
    builder.add_relationship("fact_capacity", "site_id", "dim_site", "id")
    builder.add_relationship("fact_scenario", "brand_id", "dim_brand", "id")

    builder.add_measure(
        "fact_accuracy",
        "WAPE naive",
        'CALCULATE(AVERAGE(fact_accuracy[wape]), fact_accuracy[grain] = "total", fact_accuracy[model_name] = "seasonal_naive")',
    )
    builder.add_measure(
        "fact_accuracy",
        "WAPE ETS",
        'CALCULATE(AVERAGE(fact_accuracy[wape]), fact_accuracy[grain] = "total", fact_accuracy[model_name] = "ets")',
    )
    builder.add_measure("fact_bulk_inventory", "Weeks of cover (bulk)", "AVERAGE(fact_bulk_inventory[weeks_of_cover])")
    builder.add_measure("fact_allocation", "Allocation ratio", "AVERAGE(fact_allocation[allocation_ratio])")
    builder.add_measure("fact_value_register", "$ at risk (synthetic)", "SUM(fact_value_register[value_at_risk])")
    builder.add_measure("fact_exception", "Exception count", "COUNTROWS(fact_exception)")
    builder.add_measure(
        "fact_capacity",
        "Capacity utilisation",
        "DIVIDE(SUM(fact_capacity[utilised_cases]), SUM(fact_capacity[bottling_capacity_cases]))",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    path = builder.save(str(OUT))
    print(f"Wrote {path} from {csv_dir}")


if __name__ == "__main__":
    main()
