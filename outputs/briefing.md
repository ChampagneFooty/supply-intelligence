# Vintara S&OP insight brief

**Status:** Draft commentary. Human review required. No supply action is executed from this brief.

**Mode:** cached_from_pack

## What changed

Planning-year shipments are 251,691 cases. The engine raised 176 weekly exception rows and detected 3/3 planted supply problems.

Last-year-same-week forecast error (WAPE) is 4.7%. ETS WAPE on a 52-week horizon is 27.4%. Naive bias is 0.21%; ETS bias is 27.2%. On this seasonal network the simple forecast is the one to use. Vintara Single Vineyard Chardonnay is the launch exception: seasonal-naive bias 25.1% after the 25% over-forecast we planted on the new vintage.

## What is at risk

Synthetic value at risk across the register is $510,101. Treat that as a ranking total, not a P&L. Mean bulk cover is 19.9 weeks. Mean allocation ratio is 96.9%. Bottled fill-rate proxy is 99.76%. Peak bottling utilisation is 100.0%.

Three stories sit under that total:

1. **Harvest (P1).** Barossa crush was taken at 0.70 of plan in weeks 10–14. Ranked synthetic value on P1 rows is $276,627. Action already on the register: REALLOCATE_BULK / PROTECT_LUXURY_ALLOCATION.
2. **UK allocation (P2).** Vintara Reserve Shiraz unconstrained demand in the UK ran ahead of the frozen allocation. The tightest P2 allocation ratio is 65.7%. Ranked synthetic value on P2 rows is $16,368. Action: HOLD_UK_ALLOCATION_REVIEW.
3. **Bottling line (P3).** Barossa capacity was cut in weeks 32–35. Ranked synthetic value on P3 rows is $9,395. Action: SHIFT_BOTTLING_WINDOW.

Weekly exception counts by type are in the pack. Harvest shortfall rows: 25. Allocation shortfall rows: 5. Capacity-loss rows: 4.

## What to decide

- Do we protect luxury allocation off the short Barossa vintage, or hold the current market split?
- Do we reopen UK allocation for Vintara Reserve Shiraz for weeks 20–24, or accept the service miss?
- Do we move Barossa bottling out of weeks 32–35, or run the reduced line and take cover risk?
- Do we reset the Vintara Single Vineyard Chardonnay forecast before the next cycle?

This proof of concept has delivered: Forecast accuracy, Exception detection. Next on the portfolio: Scenario analysis, Allocation cockpit, Harvest-risk digital twin.

## Citations

Every figure above is copied from `insight_pack.json`. Calc IDs:

- `kpis.wape_seasonal_naive` = 4.7% (`kpi:summary`)
- `kpis.wape_ets` = 27.4% (`kpi:summary`)
- `kpis.bias_seasonal_naive` = 0.21% (`kpi:summary`)
- `kpis.bias_ets` = 27.2% (`kpi:summary`)
- `kpis.value_at_risk_total` = $510,101 (`kpi:summary`)
- `kpis.exception_count` = 176 (`kpi:summary`)
- `kpis.fill_rate_proxy` = 99.76% (`kpi:summary`)
- `kpis.capacity_peak_utilisation` = 100.0% (`kpi:summary`)
- `planted.detected_count` = 3/3 (`planted`)
- `scenario.intake_shocked_over_baseline` = 0.70 (`scn:harvest_shortfall`)
- `planning_year_actual_cases` = 251,691 (`planning_year_actual_cases`)
- `mean_bulk_cover` = 19.9 (`mean_bulk_cover`)
- `mean_allocation_ratio` = 96.9% (`mean_allocation_ratio`)
- `accuracy_hierarchy.B03.seasonal_naive.bias` = 25.1% (`acc:brand:seasonal_naive:B03:nan:nan`)
- `accuracy_hierarchy.B03.seasonal_naive.wape` = 25.1% (`acc:brand:seasonal_naive:B03:nan:nan`)
- `value_register.P1` = $276,627 (`val:planted:P1`)
- `value_register.other` = $207,712 (`val:planted:other`)
- `value_register.P2` = $16,368 (`val:planted:P2`)
- `value_register.P3` = $9,395 (`val:planted:P3`)
- `value_register.BIAS` = $0 (`val:planted:BIAS`)
- `exceptions.type.harvest_shortfall` = 25 (`exc:type:harvest_shortfall`)
- `exceptions.type.bulk_cover` = 113 (`exc:type:bulk_cover`)
- `exceptions.type.allocation_shortfall` = 5 (`exc:type:allocation_shortfall`)
- `exceptions.type.bottled_cover` = 2 (`exc:type:bottled_cover`)
- `exceptions.type.capacity_loss` = 4 (`exc:type:capacity_loss`)
- `exceptions.type.capacity_utilisation` = 26 (`exc:type:capacity_utilisation`)
- `exceptions.type.forecast_bias` = 1 (`exc:type:forecast_bias`)
- `exceptions.P2.min_allocation_ratio` = 65.7% (`exc:EXC0139`)
