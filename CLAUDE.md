# Supply Intelligence — Agent Reference

**Read this file first.** Live workspace: `C:\Users\timra\Documents\Cursor Agents\Supply Intelligence\`

Fictional company **Vintara Estates** (luxury-led global wine). Synthetic data. **Not** Treasury Wine Estates and not TWE brands. Built as a proof of concept for a TWE **Supply AI & Insights Manager** application.

Owner: Tim Raspe. Plain English with Tim. Do not invent metrics. Do not treat synthetic $ at risk as a P&L.

---

## Status (2026-09-04)

| Item | State |
|------|--------|
| Day 1 engine + `outputs/insight_pack.json` + tests | Complete. P1–P3 detected. |
| Cached S&OP brief | Complete. `outputs/briefing.md` / `briefing.json`. No API key. |
| Streamlit cockpit | Complete. `streamlit run src/app.py` |
| Power BI Desktop report | Complete. Tim built it. File: `powerbi/Supply Intelligence.pbix` |
| Streamlit Cloud public URL | Not published. Needs Tim’s Streamlit account. |
| TWE application documents | Not this repo’s job unless Tim asks. Resume live workspace is `Cursor Agents\Resume\`. |

**Do not reopen Day 1/2 architecture.** Do not add agents, FastAPI, extra ML, approval queues, or a chatbot.

---

## Hard rules

1. Every number is **deterministic** (generator + engine). LLM / briefing only narrates `insight_pack.json`.
2. Label **calculated** vs **AI commentary**. No supply action is executed from the brief.
3. Implement what is specified. Do not “improve” with new frameworks.
4. **Agents cannot edit `.pbix` canvases.** Give Tim click-by-click Desktop steps. Do not guess which field is on a visual; ask or look at a screenshot. Power BI X-axis pills do **not** have Don’t summarize / Sum / Average.
5. Python 3.14 here: `pbix-mcp` does not install. Do not ship a fake `.pbix`.
6. Never claim wine-industry employment. Vintara is a demo network.

---

## How to run

```text
.venv\Scripts\pip install -r requirements.txt
python -m src.generate
python -m src.engine
python -m src.briefing
python -m pytest
streamlit run src/app.py
```

Briefing `--live` only if `OPENAI_API_KEY` is set. Default path is cached from the pack.

---

## What exists

| Path | Meaning |
|------|---------|
| `config/` | Network, planted shocks P1–P3, rules, harvest scenario, portfolio YAML |
| `src/generate.py` | Synthetic wine star schema |
| `src/engine.py` | Forecast, accuracy, coverage, exceptions, scenario, value, pack |
| `src/briefing.py` | One Insight Agent; pack only |
| `src/app.py` | Streamlit: Executive, Planner, Value & portfolio, S&OP brief |
| `outputs/insight_pack.json` | Contract for UI, brief, tests |
| `outputs/powerbi/*.csv` | What the `.pbix` refreshes from |
| `powerbi/Supply Intelligence.pbix` | Tim’s Desktop report (Executive + Planner) |
| `docs/powerbi_model.md` | Relationships, DAX, Desktop gotchas |
| `docs/demo_script.md` | Hiring-manager 90-second path |
| `Vintara Supply Insights - Day 1 Explainer.docx` | Plain-English Day 1 note for Tim |
| `tests/` | Planted detection, scenario 0.70, briefing trace |

Headline pack figures (re-run engine if Tim regenerates data): naive WAPE ~4.7%; ETS WAPE ~27%; harvest intake ratio **0.70** on planning-year weeks 10–14; synthetic $ at risk ~$510k; 3/3 planted.

---

## Power BI — facts a new agent must not re-break

Tim already loaded CSVs via **Get data → Folder**. That leaves a file-list query (`powerbi`) with **Binary** + **Name**. **Reference** that query, then click **Binary** on one file. Do not Combine. Do not click Binary on the original list query.

Live `.pbix`: `powerbi/Supply Intelligence.pbix` (not `Vintara Supply Insights.pbix`).

**Harvest intake ratio** must filter `year_index = 1` and `planning_week` 10–14 and `metric = "harvest_intake_litres"`. Without the year filter the card shows **0.85** (2025 normal vintage mixed with 2026 shock).

**Planner accuracy table:** visual filters `grain = brand` and `model_name = seasonal_naive`, then **Average** of `wape` and `bias`. Without those filters, Sum of wape is hundreds of percent. Do not tell Tim to Don’t summarize on an **X-axis** pill.

**Capacity line:** X-axis = `fact_capacity[planning_week]` (Tim confirmed this). Legend = `dim_site[name]`. Visual filter `fact_capacity[year_index] = 1`. `fact_allocation` / `fact_capacity` are **not** related to `dim_date`; do not page-filter them with `dim_date[year_index]`.

Format % / $ via **Measure tools** or **Column tools**, not by clicking the card.

Full DAX and relationships: `docs/powerbi_model.md`.

---

## Planted problems

| ID | Shock | Weeks |
|----|--------|-------|
| P1 | Barossa harvest −30% | 10–14 |
| P2 | UK Reserve Shiraz demand +40% | 20–24 |
| P3 | Barossa bottling −35% | 32–35 |

New-release Chardonnay (B03) has a planted **25%** forecast over-bias.

---

## If Tim starts a new chat

- Workspace root must be this folder.
- Read this file + `README.md`. Do not rebuild the engine or the `.pbix` unprompted.
- Next work is only what Tim asks: Cloud deploy, TWE resume/letter (in **Resume** repo), PBI polish, or a small engine fix.
