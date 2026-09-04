# Power BI model

Live file (Tim, Desktop): `powerbi/Supply Intelligence.pbix`

Load CSVs from `outputs/powerbi/`. Do not load parquet. Do not invent new metrics in the report.

Python 3.14 cannot run `pbix-mcp`. Do not compile a `.pbix` from the agent.

## How this file was built

**Get data → Folder** on `outputs/powerbi` produces a file-list query (Binary + Name). Keep that query with **Enable load** off.

For each table: **Reference** the file-list query → click **Binary** on that CSV → Use first row as headers → rename (no `.csv`). Do **not** Combine. Do **not** click Binary on the original list query (that destroys the list).

`dim_brand` key is **`id`**, not `brand_id`.

## Desktop gotchas (do not repeat)

- **Harvest intake ratio** without `year_index = 1` and weeks 10–14 shows **0.85** (2025 + 2026 mixed). Use the DAX below.
- Format % / $ on **Measure tools** or **Column tools**, not by clicking the card.
- **Don’t summarize** lives on Column tools or on a **Values/Columns** pill, never on an **X-axis** pill.
- Planner WAPE table: visual filters `grain = brand` and `model_name = seasonal_naive`, then **Average** of `wape` and `bias`. Sum without those filters is hundreds of percent.
- Do not page-filter allocation or capacity with `dim_date[year_index]`. Those facts are not related to `dim_date`. Filter `fact_allocation[year_index]` and `fact_capacity[year_index]` on the visual.
- Capacity chart X-axis is `fact_capacity[planning_week]`. Legend is `dim_site[name]`.

## Pages (as built)

1. **Executive** — KPI cards, exception table, harvest scenario lines (`metric = bulk_cover_weeks`).
2. **Planner** — brand WAPE/bias table, allocation by market, capacity utilisation by week and site.

The Streamlit Executive and Planner tabs tell the same story.

## Relationships

| From | To |
|------|----|
| fact_demand[brand_id] | dim_brand[id] |
| fact_demand[market_id] | dim_market[id] |
| fact_demand[week_id] | dim_date[week_id] |
| fact_forecast[brand_id] | dim_brand[id] |
| fact_forecast[week_id] | dim_date[week_id] |
| fact_accuracy[brand_id] | dim_brand[id] |
| fact_bulk_inventory[brand_id] | dim_brand[id] |
| fact_bulk_inventory[site_id] | dim_site[id] |
| fact_bulk_inventory[week_id] | dim_date[week_id] |
| fact_bottled_inventory[brand_id] | dim_brand[id] |
| fact_bottled_inventory[site_id] | dim_site[id] |
| fact_allocation[brand_id] | dim_brand[id] |
| fact_allocation[market_id] | dim_market[id] |
| fact_exception[brand_id] | dim_brand[id] |
| fact_value_register[exception_id] | fact_exception[exception_id] |
| fact_scenario[brand_id] | dim_brand[id] |
| fact_capacity[site_id] | dim_site[id] |

Filter planning year with `dim_date[year_index] = 1` unless you are looking at history.

## Measures (DAX)

```dax
WAPE naive =
CALCULATE(
    AVERAGE(fact_accuracy[wape]),
    fact_accuracy[grain] = "total",
    fact_accuracy[model_name] = "seasonal_naive"
)

WAPE ETS =
CALCULATE(
    AVERAGE(fact_accuracy[wape]),
    fact_accuracy[grain] = "total",
    fact_accuracy[model_name] = "ets"
)

Bias naive =
CALCULATE(
    AVERAGE(fact_accuracy[bias]),
    fact_accuracy[grain] = "total",
    fact_accuracy[model_name] = "seasonal_naive"
)

Weeks of cover (bulk) =
AVERAGE(fact_bulk_inventory[weeks_of_cover])

Weeks of cover (bottled) =
AVERAGE(fact_bottled_inventory[weeks_of_cover])

Allocation ratio =
AVERAGE(fact_allocation[allocation_ratio])

Fill rate proxy =
VAR below =
    CALCULATE(
        COUNTROWS(fact_bottled_inventory),
        fact_bottled_inventory[weeks_of_cover] < 4
    )
RETURN 1 - DIVIDE(below, COUNTROWS(fact_bottled_inventory))

Capacity utilisation =
DIVIDE(
    SUM(fact_capacity[utilised_cases]),
    SUM(fact_capacity[bottling_capacity_cases])
)

$ at risk (synthetic) =
SUM(fact_value_register[value_at_risk])

Exception count =
COUNTROWS(fact_exception)

Harvest intake ratio =
DIVIDE(
    CALCULATE(
        SUM(fact_scenario[shocked]),
        fact_scenario[metric] = "harvest_intake_litres",
        fact_scenario[year_index] = 1,
        fact_scenario[planning_week] >= 10,
        fact_scenario[planning_week] <= 14
    ),
    CALCULATE(
        SUM(fact_scenario[baseline]),
        fact_scenario[metric] = "harvest_intake_litres",
        fact_scenario[year_index] = 1,
        fact_scenario[planning_week] >= 10,
        fact_scenario[planning_week] <= 14
    )
)
```

`$ at risk (synthetic)` is a ranking measure. It is not a P&L.

## Refresh

After `python -m src.engine`, open the `.pbix` and click Refresh if the CSV paths still point at `outputs/powerbi/`.
