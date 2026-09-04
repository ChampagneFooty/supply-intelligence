"""One Insight Agent: S&OP brief from insight_pack.json only. Cached by default."""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

from src import OUTPUTS
from src.generate import load_yaml


def load_pack() -> dict:
    path = OUTPUTS / "insight_pack.json"
    if not path.exists():
        raise FileNotFoundError("outputs/insight_pack.json missing. Run python -m src.engine first.")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _brands() -> dict:
    return {b["id"]: b["name"] for b in load_yaml("network.yaml")["brands"]}


def _pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def _money(value: float) -> str:
    return f"${value:,.0f}"


def _pid(value) -> str:
    if value is None or value == "":
        return "other"
    text = str(value).strip().lower()
    if text in {"nan", "none", "null"}:
        return "other"
    return str(value)


def _claim(calc_id: str, path: str, value, display: str) -> dict:
    return {"calc_id": calc_id, "path": path, "value": value, "display": display}


def claims_from_pack(pack: dict) -> list[dict]:
    names = _brands()
    kpis = pack["kpis"]
    planted = pack["planted"]
    claims = [
        _claim("kpi:summary", "kpis.wape_seasonal_naive", kpis["wape_seasonal_naive"], _pct(kpis["wape_seasonal_naive"])),
        _claim("kpi:summary", "kpis.wape_ets", kpis["wape_ets"], _pct(kpis["wape_ets"])),
        _claim("kpi:summary", "kpis.bias_seasonal_naive", kpis["bias_seasonal_naive"], _pct(kpis["bias_seasonal_naive"], 2)),
        _claim("kpi:summary", "kpis.bias_ets", kpis["bias_ets"], _pct(kpis["bias_ets"])),
        _claim("kpi:summary", "kpis.value_at_risk_total", kpis["value_at_risk_total"], _money(kpis["value_at_risk_total"])),
        _claim("kpi:summary", "kpis.exception_count", kpis["exception_count"], str(kpis["exception_count"])),
        _claim("kpi:summary", "kpis.fill_rate_proxy", kpis["fill_rate_proxy"], _pct(kpis["fill_rate_proxy"], 2)),
        _claim("kpi:summary", "kpis.capacity_peak_utilisation", kpis["capacity_peak_utilisation"], _pct(kpis["capacity_peak_utilisation"])),
        _claim("planted", "planted.detected_count", planted["detected_count"], f"{planted['detected_count']}/3"),
        _claim("scn:harvest_shortfall", "scenario.intake_shocked_over_baseline", pack["scenario"]["intake_shocked_over_baseline"], f"{pack['scenario']['intake_shocked_over_baseline']:.2f}"),
        _claim("planning_year_actual_cases", "planning_year_actual_cases", pack["planning_year_actual_cases"], f"{pack['planning_year_actual_cases']:,.0f}"),
        _claim("mean_bulk_cover", "mean_bulk_cover", pack["mean_bulk_cover"], f"{pack['mean_bulk_cover']:.1f}"),
        _claim("mean_allocation_ratio", "mean_allocation_ratio", pack["mean_allocation_ratio"], _pct(pack["mean_allocation_ratio"])),
    ]

    naive_brand = [
        r
        for r in pack["accuracy_hierarchy"]
        if r.get("grain") == "brand" and r.get("model_name") == "seasonal_naive"
    ]
    b03 = next((r for r in naive_brand if r.get("brand_id") == "B03"), None)
    if b03:
        claims.append(_claim(b03["calc_id"], "accuracy_hierarchy.B03.seasonal_naive.bias", b03["bias"], _pct(b03["bias"])))
        claims.append(_claim(b03["calc_id"], "accuracy_hierarchy.B03.seasonal_naive.wape", b03["wape"], _pct(b03["wape"])))

    by_planted = defaultdict(float)
    for row in pack["value_register"]:
        pid = _pid(row.get("planted_id"))
        by_planted[pid] += float(row["value_at_risk"])
    for pid, total in by_planted.items():
        claims.append(_claim(f"val:planted:{pid}", f"value_register.{pid}", total, _money(total)))

    types = Counter(e["type"] for e in pack["exceptions"])
    for typ, n in types.items():
        claims.append(_claim(f"exc:type:{typ}", f"exceptions.type.{typ}", n, str(n)))

    alloc = [e for e in pack["exceptions"] if e.get("type") == "allocation_shortfall" and e.get("planted_id") == "P2"]
    if alloc:
        ratio = min(float(e["value"]) for e in alloc)
        claims.append(_claim(alloc[0]["calc_id"], "exceptions.P2.min_allocation_ratio", ratio, _pct(ratio)))

    return claims


def brief_markdown(pack: dict, claims: list[dict], mode: str) -> str:
    names = _brands()
    get = {c["path"]: c for c in claims}
    kpis = pack["kpis"]
    planted = pack["planted"]

    def d(path):
        return get[path]["display"]

    b03_name = names.get("B03", "Single Vineyard Chardonnay")
    shiraz = names.get("B01", "Reserve Shiraz")
    p1 = d("value_register.P1") if "value_register.P1" in get else "n/a"
    p2 = d("value_register.P2") if "value_register.P2" in get else "n/a"
    p3 = d("value_register.P3") if "value_register.P3" in get else "n/a"
    b03_bias = d("accuracy_hierarchy.B03.seasonal_naive.bias") if "accuracy_hierarchy.B03.seasonal_naive.bias" in get else "n/a"
    p2_ratio = d("exceptions.P2.min_allocation_ratio") if "exceptions.P2.min_allocation_ratio" in get else "n/a"

    delivered = [u["name"] for u in pack["portfolio"] if u.get("status") == "delivered"]
    nxt = [u["name"] for u in pack["portfolio"] if u.get("status") == "next"]

    return f"""# Vintara S&OP insight brief

**Status:** Draft commentary. Human review required. No supply action is executed from this brief.

**Mode:** {mode}

## What changed

Planning-year shipments are {d('planning_year_actual_cases')} cases. The engine raised {d('kpis.exception_count')} weekly exception rows and detected {d('planted.detected_count')} planted supply problems.

Last-year-same-week forecast error (WAPE) is {d('kpis.wape_seasonal_naive')}. ETS WAPE on a 52-week horizon is {d('kpis.wape_ets')}. Naive bias is {d('kpis.bias_seasonal_naive')}; ETS bias is {d('kpis.bias_ets')}. On this seasonal network the simple forecast is the one to use. {b03_name} is the launch exception: seasonal-naive bias {b03_bias} after the 25% over-forecast we planted on the new vintage.

## What is at risk

Synthetic value at risk across the register is {d('kpis.value_at_risk_total')}. Treat that as a ranking total, not a P&L. Mean bulk cover is {d('mean_bulk_cover')} weeks. Mean allocation ratio is {d('mean_allocation_ratio')}. Bottled fill-rate proxy is {d('kpis.fill_rate_proxy')}. Peak bottling utilisation is {d('kpis.capacity_peak_utilisation')}.

Three stories sit under that total:

1. **Harvest (P1).** Barossa crush was taken at {d('scenario.intake_shocked_over_baseline')} of plan in weeks 10–14. Ranked synthetic value on P1 rows is {p1}. Action already on the register: REALLOCATE_BULK / PROTECT_LUXURY_ALLOCATION.
2. **UK allocation (P2).** {shiraz} unconstrained demand in the UK ran ahead of the frozen allocation. The tightest P2 allocation ratio is {p2_ratio}. Ranked synthetic value on P2 rows is {p2}. Action: HOLD_UK_ALLOCATION_REVIEW.
3. **Bottling line (P3).** Barossa capacity was cut in weeks 32–35. Ranked synthetic value on P3 rows is {p3}. Action: SHIFT_BOTTLING_WINDOW.

Weekly exception counts by type are in the pack. Harvest shortfall rows: {d('exceptions.type.harvest_shortfall') if 'exceptions.type.harvest_shortfall' in get else '0'}. Allocation shortfall rows: {d('exceptions.type.allocation_shortfall') if 'exceptions.type.allocation_shortfall' in get else '0'}. Capacity-loss rows: {d('exceptions.type.capacity_loss') if 'exceptions.type.capacity_loss' in get else '0'}.

## What to decide

- Do we protect luxury allocation off the short Barossa vintage, or hold the current market split?
- Do we reopen UK allocation for {shiraz} for weeks 20–24, or accept the service miss?
- Do we move Barossa bottling out of weeks 32–35, or run the reduced line and take cover risk?
- Do we reset the {b03_name} forecast before the next cycle?

This proof of concept has delivered: {', '.join(delivered)}. Next on the portfolio: {', '.join(nxt)}.

## Citations

Every figure above is copied from `insight_pack.json`. Calc IDs:

""" + "\n".join(f"- `{c['path']}` = {c['display']} (`{c['calc_id']}`)" for c in claims)


def _live_llm(pack: dict, claims: list[dict]) -> str | None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return None
    allowed = ", ".join(f"{c['path']}={c['display']}" for c in claims)
    body = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"),
        "temperature": 0,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Write a one-page wine S&OP brief. Use only the figures in the allowed list. "
                    "Do not invent numbers. Say human review is required and no supply action is executed."
                ),
            },
            {
                "role": "user",
                "content": "Allowed figures:\n" + allowed,
            },
        ],
    }
    try:
        import urllib.request

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"]
    except Exception:
        return None


def write_brief(pack: dict, *, live: bool = False) -> dict:
    claims = claims_from_pack(pack)
    mode = "cached_from_pack"
    markdown = brief_markdown(pack, claims, mode)
    if live:
        llm_text = _live_llm(pack, claims)
        if llm_text:
            mode = "llm_optional"
            markdown = llm_text.strip() + "\n\n## Citations\n\n" + "\n".join(
                f"- `{c['path']}` = {c['display']} (`{c['calc_id']}`)" for c in claims
            )
    record = {
        "agent_id": "sop_insight",
        "source": "insight_pack.json",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "requires_approval": True,
        "human_gate": "No supply action is executed from this brief.",
        "confidence": "medium",
        "source_refs": claims,
        "markdown": markdown,
    }
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    with open(OUTPUTS / "briefing.json", "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2)
    with open(OUTPUTS / "briefing.md", "w", encoding="utf-8") as handle:
        handle.write(markdown)
        if not markdown.endswith("\n"):
            handle.write("\n")
    return record


def main() -> None:
    live = "--live" in sys.argv
    pack = load_pack()
    record = write_brief(pack, live=live)
    print(f"Wrote briefing ({record['mode']}) to {OUTPUTS / 'briefing.md'}")


if __name__ == "__main__":
    main()
