# 90-second hiring-manager path

Synthetic wine network. Not Treasury Wine Estates.

## If you have one minute

1. Open the Streamlit cockpit (local: `streamlit run src/app.py`, or the Streamlit Cloud URL in the README).
2. Read the KPI strip: planted problems 3/3, naive WAPE vs ETS, synthetic $ at risk.
3. Open **S&OP brief**. Amber means commentary. Blue means calculated. Nothing on that page executes a supply action.

## If you have three minutes

4. **Executive** tab: harvest scenario line (plan vs −30% vintage) and the exception list. P1 / P2 / P3 are the three planted shocks.
5. **Planner** tab: brand WAPE — the new Chardonnay is the biased launch forecast.
6. **Value & portfolio** tab: dollar ranking plus the five-item roadmap. This proof of concept delivered forecast accuracy and exception detection.

## Power BI

Open `powerbi/Supply Intelligence.pbix`. Two pages: **Executive** and **Planner**. Data: `outputs/powerbi/*.csv`. Streamlit Executive / Planner tabs show the same story if Desktop is not available.

## What you are not looking at

- A chatbot
- A live language-model call (the brief is cached; no API key required)
- Real TWE volume or margin
