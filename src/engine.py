"""Run the deterministic engine. Writes insight_pack.json and Power BI CSVs."""

from __future__ import annotations

import pandas as pd

from src import DATA_STAR
from src import accuracy as accuracy_mod
from src import coverage as coverage_mod
from src import exceptions as exceptions_mod
from src import forecast as forecast_mod
from src import pack as pack_mod
from src import scenario as scenario_mod
from src import value as value_mod


def load_star() -> dict[str, pd.DataFrame]:
    tables = {}
    for path in DATA_STAR.glob("*.parquet"):
        tables[path.stem] = pd.read_parquet(path)
    required = [
        "dim_date",
        "dim_brand",
        "fact_demand",
        "fact_bulk_inventory",
        "fact_bottled_inventory",
        "fact_allocation",
        "fact_capacity",
        "fact_bottling",
    ]
    missing = [name for name in required if name not in tables]
    if missing:
        raise FileNotFoundError(f"Star tables missing {missing}. Run python -m src.generate first.")
    return tables


def main() -> None:
    star = load_star()
    forecast = forecast_mod.run(star)
    accuracy = accuracy_mod.run(star, forecast)
    covered = coverage_mod.run(star)
    star.update(covered)
    exceptions = exceptions_mod.run(star, accuracy)
    scenario = scenario_mod.run(star)
    value_register = value_mod.run(star, exceptions)
    pack = pack_mod.run(star, forecast, accuracy, exceptions, scenario, value_register)
    print(
        "insight_pack.json written. "
        f"P1={pack['planted']['P1']} P2={pack['planted']['P2']} P3={pack['planted']['P3']} "
        f"exceptions={pack['kpis']['exception_count']} "
        f"$at_risk={pack['kpis']['value_at_risk_total']:.0f}"
    )


if __name__ == "__main__":
    main()
