# Vintara Supply Insights

A working AI-enabled Supply Intelligence & Planning proof of concept for a **Supply AI & Insights Manager** application.

Fictional company: **Vintara Estates**. Synthetic data. Not Treasury Wine Estates, not TWE brands.

Every number is calculated. AI commentary is labelled, cited, and never executed as a supply action. There is no chatbot.

**Live cockpit:** [https://supply-intelligence-tkkqjhmezc4adxhf6aeppv.streamlit.app/](https://supply-intelligence-tkkqjhmezc4adxhf6aeppv.streamlit.app/)  
**Code:** [https://github.com/ChampagneFooty/supply-intelligence](https://github.com/ChampagneFooty/supply-intelligence)

**New agent:** read `CLAUDE.md` first. Hiring-manager path: `docs/demo_script.md`. Tim’s Day 1 explainer: `Vintara Supply Insights - Day 1 Explainer.docx`.

---

## Status (2026-09-04)

| Item | State |
|------|--------|
| Architecture | Locked. No extra agents, APIs, or ML models. |
| Day 1 — engine + `insight_pack.json` + tests | Complete. P1–P3 detected. |
| Day 2 — Streamlit + cached brief + Power BI | Complete. |
| Power BI file | `powerbi/Supply Intelligence.pbix` (Tim, Desktop) |
| Public Streamlit URL | [Live app](https://supply-intelligence-tkkqjhmezc4adxhf6aeppv.streamlit.app/) — `src/app.py` on Streamlit Community Cloud |

**Pack headlines:** seasonal-naive WAPE ~4.7%; ETS WAPE ~27% (naive wins on this seasonal network); harvest intake **0.70** on 2026 weeks 10–14; synthetic value-at-risk in the pack; 7 pytest checks.

---

## How to run

```text
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
python -m src.generate
python -m src.engine
python -m src.briefing
python -m pytest
streamlit run src/app.py
```

`python -m src.briefing` writes `outputs/briefing.json` and `outputs/briefing.md` from the pack. No API key unless `--live` and `OPENAI_API_KEY` are set.

Open Power BI: `powerbi/Supply Intelligence.pbix`. Refresh from `outputs/powerbi/*.csv`. Model notes: `docs/powerbi_model.md`. Do not rebuild the `.pbix` from Python on this machine (`pbix-mcp` fails on Python 3.14).

### Streamlit Community Cloud

Presentation URL (no API key): [https://supply-intelligence-tkkqjhmezc4adxhf6aeppv.streamlit.app/](https://supply-intelligence-tkkqjhmezc4adxhf6aeppv.streamlit.app/)

The app reads committed `outputs/insight_pack.json`, `outputs/briefing.json`, and `outputs/powerbi/*.csv`. Redeploy from [share.streamlit.io](https://share.streamlit.io) if the GitHub repo changes. Main file: `src/app.py`. Python version is pinned in `runtime.txt` (3.12).

---

## What this is (and is not)

| In scope | Out of scope |
|----------|----------------|
| Wine-specific synthetic network | Generic FMCG toy data |
| Seasonal naive + ETS, WAPE / bias | Extra ML models |
| Coverage, exceptions, harvest scenario, $ at risk | Multi-agent mesh, FastAPI, approval ticket queue |
| `insight_pack.json` as the contract | Invented executive dollar headlines |
| One governed S&OP brief, cached | A live chatbot |
| Power BI two-page report from engine CSVs | Recalculating metrics inside the report |

---

## Vintara network

- 8 brands: 3 luxury, 3 masstige, 2 commercial
- 5 markets: AU, US, UK, EU, Asia
- 3 sites: Barossa cellar/bottling, Napa cellar/bottling, UK DC
- 52-week planning year, 52-week prior year, 13-week forward forecast

| ID | Shock | Weeks |
|----|--------|-------|
| P1 | Harvest shortfall −30% at Barossa | 10–14 |
| P2 | Demand +40% on Vintara Reserve Shiraz in the UK | 20–24 |
| P3 | Bottling line −35% at Barossa | 32–35 |

---

## Deterministic vs AI

| Calculated | Commentary (one brief, cached) |
|------------|--------------------------------|
| Network, forecasts, WAPE/bias | S&OP narrative |
| Coverage, allocation, capacity | “So what” wording |
| Exceptions, harvest scenario, $ at risk | Recommended actions (codes already on the value register) |
| Portfolio ranks from YAML | — |

---

## Repository

```text
CLAUDE.md         Agent handoff (read first)
AGENTS.md         Short pointer to CLAUDE.md
config/           network, planted shocks, rules, scenario, portfolio
src/              generate, engine, briefing, Streamlit app
data/star/        parquet
outputs/          insight_pack.json, briefing, powerbi CSVs
powerbi/          Supply Intelligence.pbix (Tim)
docs/             demo script and Power BI model
tests/            planted, scenario, briefing trace
```
