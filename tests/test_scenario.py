import pandas as pd

from src import DATA_STAR
from src.generate import load_yaml


def test_harvest_scenario_intake_factor():
    cfg = load_yaml("scenarios.yaml")["demo"]
    scenario = pd.read_parquet(DATA_STAR / "fact_scenario.parquet")
    harvest = scenario[
        (scenario["metric"] == "harvest_intake_litres")
        & (scenario["year_index"] == 1)
        & (scenario["planning_week"].isin(cfg["planning_weeks"]))
        & (scenario["baseline"] > 0)
    ]
    assert len(harvest) > 0
    ratio = (harvest["shocked"] / harvest["baseline"]).mean()
    assert abs(ratio - cfg["intake_factor"]) <= cfg["metric_tolerance"]
