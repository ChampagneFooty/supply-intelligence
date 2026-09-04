# Locked architecture

Do not add abstractions, frameworks, extra agents, APIs, or ML models.

**Gate (already passed):** `outputs/insight_pack.json` exists and tests pass.

## Day 1 (done)

Wine-specific generator → deterministic engine → `insight_pack.json` → pytest.

## Day 2 (done)

Streamlit S&OP cockpit, cached Insight briefing, Power BI Desktop report.

- Cockpit: `streamlit run src/app.py`
- Brief: `python -m src.briefing` (cached; `--live` optional)
- Report: `powerbi/Supply Intelligence.pbix` (Tim). CSVs in `outputs/powerbi/`. DAX/gotchas in `docs/powerbi_model.md`.
- `powerbi/build_pbix.py` needs `pbix-mcp`, which does not install on Python 3.14. Do not use it here.

## Hard rule

Every number is deterministic. Commentary only narrates the frozen insight pack. Calculated vs AI is labelled. No supply action from the brief.

Agent handoff: `CLAUDE.md`.
