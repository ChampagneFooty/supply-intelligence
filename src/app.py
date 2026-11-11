"""S&OP cockpit. Reads the frozen insight pack and cached brief. No API key required."""

from __future__ import annotations

import json
import sys
from base64 import b64encode
from pathlib import Path

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import OUTPUTS, POWERBI
from src.generate import load_yaml

SHOCKS = {
    "P1": {
        "title": "Barossa harvest −30%",
        "weeks": (10, 14),
        "jump": "Barossa, weeks 10–14",
        "why": "We cut Barossa intake 30% in this window. The engine’s harvest exceptions live here.",
    },
    "P2": {
        "title": "UK Reserve Shiraz +40%",
        "weeks": (20, 24),
        "jump": "Reserve Shiraz · UK, weeks 20–24",
        "why": "We lifted UK demand 40% on Reserve Shiraz. Allocation shortfalls in the pack are this story.",
    },
    "P3": {
        "title": "Barossa bottling −35%",
        "weeks": (32, 35),
        "jump": "Barossa, weeks 32–35",
        "why": "We cut Barossa bottling capacity 35% in this window. Capacity-loss rows in the pack are this story.",
    },
    "BIAS": {
        "title": "New-release Chardonnay over-forecast",
        "weeks": (1, 52),
        "jump": "Single Vineyard Chardonnay, full year",
        "why": "We planted a 25% over-forecast on the new Chardonnay. Brand WAPE/bias on Planner is this story.",
    },
}

RED = "#8C1C2B"  # wine: calculated problem signal
CHARCOAL = "#1F2328"  # ink
IVORY = "#46505E"  # slate: neutral series on a light canvas
GOLD = "#B08D57"
STONE = "#B7BCC4"
LEAF = "#5F7F63"
PAPER = "#FFFFFF"
GRID = "#ECEAE6"
MUTED = "#6B7280"

st.set_page_config(page_title="Vintara Supply Insights", layout="wide")

_CELLAR_PATH = Path(__file__).resolve().parent / "static" / "cellar-background.jpg"
_CELLAR_URI = ""
if _CELLAR_PATH.exists():
    _CELLAR_URI = "data:image/jpeg;base64," + b64encode(_CELLAR_PATH.read_bytes()).decode("ascii")


def _load_pack() -> dict:
    path = OUTPUTS / "insight_pack.json"
    if not path.exists():
        st.error("insight_pack.json is missing. Run python -m src.engine first.")
        st.stop()
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_brief() -> dict | None:
    path = OUTPUTS / "briefing.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv(name: str) -> pd.DataFrame:
    path = POWERBI / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _pct(value, digits=1):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    return f"{float(value) * 100:.{digits}f}%"


def _money(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    return f"${float(value):,.0f}"


def _blank(value) -> bool:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return True
    return str(value).strip() in {"", "nan", "None"}


def _init_filters() -> None:
    st.session_state.setdefault("shock", "All")
    st.session_state.setdefault("brand_id", "All")
    st.session_state.setdefault("market_id", "All")
    st.session_state.setdefault("site_id", "All")
    st.session_state.setdefault("week_range", (1, 52))
    st.session_state.setdefault("exception_id", "")
    st.session_state.setdefault("network_pick", None)


def _focus_shock(shock_id: str) -> None:
    st.session_state.shock = shock_id
    st.session_state.week_range = SHOCKS[shock_id]["weeks"]
    if shock_id == "P2":
        st.session_state.brand_id = "B01"
        st.session_state.market_id = "M_UK"
    elif shock_id == "P1":
        st.session_state.site_id = "S_BAR"
    elif shock_id == "P3":
        st.session_state.site_id = "S_BAR"
    elif shock_id == "BIAS":
        st.session_state.brand_id = "B03"


def _clear_filters() -> None:
    st.session_state.shock = "All"
    st.session_state.brand_id = "All"
    st.session_state.market_id = "All"
    st.session_state.site_id = "All"
    st.session_state.week_range = (1, 52)
    st.session_state.exception_id = ""


def _set_brand(brand: str) -> None:
    st.session_state.brand_id = brand


def _set_market(market: str) -> None:
    st.session_state.market_id = market


def _set_site(site: str) -> None:
    st.session_state.site_id = site


def _apply_network_pick() -> None:
    pick = st.session_state.get("network_pick") or {}
    kind = pick.get("kind")
    nid = pick.get("id")
    if kind == "brand":
        st.session_state.brand_id = nid
    elif kind == "market":
        st.session_state.market_id = nid
    elif kind == "site":
        st.session_state.site_id = nid


def _slice_frame(
    df: pd.DataFrame,
    *,
    brand_id: str,
    market_id: str,
    site_id: str,
    week_range: tuple[int, int],
    shock: str,
    keep_unscoped: bool = True,
) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    week_lo, week_hi = week_range
    if "planning_week" in out.columns:
        weeks = pd.to_numeric(out["planning_week"], errors="coerce")
        keep_week = weeks.between(week_lo, week_hi)
        if keep_unscoped:
            keep_week = keep_week | weeks.isna()
        out = out.loc[keep_week]
    if brand_id != "All" and "brand_id" in out.columns:
        match = out["brand_id"].astype(str) == brand_id
        if keep_unscoped:
            match = match | out["brand_id"].map(_blank)
        out = out.loc[match]
    if market_id != "All" and "market_id" in out.columns:
        match = out["market_id"].astype(str) == market_id
        if keep_unscoped:
            match = match | out["market_id"].map(_blank)
        out = out.loc[match]
    if site_id != "All" and "site_id" in out.columns:
        match = out["site_id"].astype(str) == site_id
        if keep_unscoped:
            match = match | out["site_id"].map(_blank)
        out = out.loc[match]
    if shock != "All" and "planted_id" in out.columns:
        planted = out["planted_id"].fillna("").astype(str)
        if shock == "other":
            out = out.loc[~planted.isin(["P1", "P2", "P3", "BIAS"])]
        else:
            out = out.loc[planted == shock]
    return out


def _finish_chart(chart):
    return (
        chart.configure(background="transparent", padding={"left": 4, "right": 8, "top": 8, "bottom": 4})
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor=GRID,
            domain=False,
            tickColor=GRID,
            labelColor=MUTED,
            titleColor=MUTED,
            titleFont="Inter",
            labelFont="Inter",
            labelFontSize=12,
            titleFontSize=12,
            titleFontWeight=500,
            labelLimit=260,
        )
        .configure_axisX(grid=False, tickCount=8)
        .configure_legend(
            labelColor=CHARCOAL,
            titleColor=MUTED,
            labelFont="Inter",
            labelFontSize=12,
            orient="top",
            symbolType="stroke",
            symbolStrokeWidth=3,
            labelLimit=260,
        )
    )


def _line_chart(df: pd.DataFrame, x: str, y: str, color: str | None, title: str) -> None:
    if df.empty:
        st.info("No rows in this slice.")
        return
    encode = {
        "x": alt.X(f"{x}:Q", title="Planning week"),
        "y": alt.Y(f"{y}:Q", title=title),
        "tooltip": list(df.columns),
    }
    if color:
        encode["color"] = alt.Color(
            f"{color}:N",
            title="",
            scale=alt.Scale(range=[RED, IVORY, GOLD, LEAF, "#7C8DB5", "#C97B63", "#9B7FB0", STONE]),
        )
    chart = (
        alt.Chart(df)
        .mark_line(strokeWidth=2.5, interpolate="monotone")
        .encode(**encode)
        .properties(height=300)
        .interactive()
    )
    st.altair_chart(_finish_chart(chart), width="stretch")


def _bar_chart(df: pd.DataFrame, x: str, y: str, title: str, *, highlight_top: int = 1, worst: str = "high", fmt: str = ",.1f") -> None:
    """Horizontal bars. The worst rows are wine; the rest are neutral so the problem stands out."""
    if df.empty:
        st.info("No rows in this slice.")
        return
    data = df.copy()
    ranked = data[x].rank(ascending=(worst == "low"), method="first")
    data["_flag"] = ranked.le(highlight_top).map({True: "focus", False: "rest"})
    base = alt.Chart(data).encode(
        x=alt.X(f"{x}:Q", title=title, axis=alt.Axis(grid=True, gridColor=GRID)),
        y=alt.Y(f"{y}:N", sort=alt.EncodingSortField(field=x, order="ascending" if worst == "low" else "descending"), title="", axis=alt.Axis(labelColor=CHARCOAL, labelFontSize=13)),
        tooltip=[c for c in df.columns],
    )
    bars = base.mark_bar(cornerRadiusEnd=3, height={"band": 0.62}).encode(
        color=alt.Color("_flag:N", legend=None, scale=alt.Scale(domain=["focus", "rest"], range=[RED, STONE]))
    )
    labels = base.mark_text(align="left", dx=6, fontSize=12, font="Inter", color=CHARCOAL).encode(
        text=alt.Text(f"{x}:Q", format=fmt)
    )
    chart = (bars + labels).properties(height=max(170, 38 * len(data)))
    st.altair_chart(_finish_chart(chart), width="stretch")


def _kpi_card(label: str, value: str, note: str = "", *, tone: str = "") -> str:
    return (
        f'<div class="kpi {tone}"><div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>'
    )


def _money_short(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    v = float(value)
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:.0f}k"
    return f"${v:,.0f}"


def _network_positions(sites: list, brands: list, markets: list, *, compact: bool) -> dict[str, tuple[float, float]]:
    pos: dict[str, tuple[float, float]] = {}
    if not compact:
        for i, site in enumerate(sites):
            pos[site["id"]] = (0.0, 1.0 - i * (1.0 / max(len(sites) - 1, 1)))
        for i, brand in enumerate(brands):
            pos[brand["id"]] = (1.0, 1.0 - i * (1.0 / max(len(brands) - 1, 1)))
        for i, market in enumerate(markets):
            pos[market["id"]] = (2.0, 1.0 - i * (1.0 / max(len(markets) - 1, 1)))
        return pos
    n_sites = max(len(sites), 1)
    n_markets = max(len(markets), 1)
    for i, site in enumerate(sites):
        pos[site["id"]] = ((i + 0.5) / n_sites, 1.0)
    for i, brand in enumerate(brands):
        col = 0 if i < 4 else 1
        row = i % 4
        pos[brand["id"]] = (0.08 if col == 0 else 0.55, 0.70 - row * 0.14)
    for i, market in enumerate(markets):
        pos[market["id"]] = ((i + 0.5) / n_markets, 0.05)
    return pos


def _network_label(kind: str, name: str, *, compact: bool) -> str:
    if kind == "site":
        return name.replace(" Cellar & Bottling", "").replace(" Distribution Centre", " DC")
    if kind == "brand":
        label = name.replace("Vintara ", "")
        if compact:
            label = label.replace("Single Vineyard ", "SV ")
        return label
    if compact:
        return {"Australia": "AU", "United States": "US", "United Kingdom": "UK", "European Union": "EU"}.get(name, name)
    return name


def _supply_network_figure(
    network: dict,
    accuracy: pd.DataFrame,
    exc_slice: pd.DataFrame,
    val_slice: pd.DataFrame,
    alloc: pd.DataFrame,
    cap: pd.DataFrame,
    brand_id: str,
    market_id: str,
    site_id: str,
    *,
    compact: bool = False,
) -> go.Figure:
    brands = network["brands"]
    markets = network["markets"]
    sites = network["sites"]
    brand_names = {b["id"]: b["name"] for b in brands}
    market_names = {m["id"]: m["name"] for m in markets}
    site_names = {s["id"]: s["name"] for s in sites}
    pos = _network_positions(sites, brands, markets, compact=compact)

    brand_acc = pd.DataFrame()
    if not accuracy.empty:
        brand_acc = accuracy[(accuracy["grain"] == "brand") & (accuracy["model_name"] == "seasonal_naive")]

    def _exc_for(col: str, nid: str) -> pd.DataFrame:
        if exc_slice.empty or col not in exc_slice.columns:
            return pd.DataFrame()
        return exc_slice[exc_slice[col].astype(str) == nid]

    def _risk_for(col: str, nid: str) -> float:
        if val_slice.empty or col not in val_slice.columns:
            return 0.0
        hit = val_slice[val_slice[col].astype(str) == nid]
        if hit.empty or "value_at_risk" not in hit.columns:
            return 0.0
        return float(hit["value_at_risk"].sum())

    def _heat(exc: pd.DataFrame) -> str:
        if exc.empty:
            return "#C9CDD3"
        planted = {str(v) for v in exc["planted_id"].fillna("").astype(str) if str(v) not in {"", "nan"}}
        if planted & {"P1", "P2", "P3", "BIAS"}:
            return RED
        return GOLD

    nodes = []
    for site in sites:
        nid = site["id"]
        exc = _exc_for("site_id", nid)
        util = None
        if not cap.empty:
            plan = cap[(cap["year_index"] == 1) & (cap["site_id"] == nid)]
            if len(plan):
                util = float((plan["utilised_cases"] / plan["bottling_capacity_cases"].clip(lower=0.1)).mean())
        hover = [
            site_names[nid],
            "Site",
            site.get("type", "").replace("_", " "),
            f"Exceptions in slice: {len(exc)}",
            f"Synthetic $ at risk: {_money(_risk_for('site_id', nid))}",
        ]
        if util is not None:
            hover.append(f"Mean bottling utilisation (year 1): {_pct(util)}")
        selected = site_id == nid
        nodes.append(
            {
                "id": nid,
                "kind": "site",
                "label": _network_label("site", site_names[nid], compact=compact),
                "x": pos[nid][0],
                "y": pos[nid][1],
                "color": _heat(exc),
                "size": (26 if selected else 20) if compact else (22 if selected else 16),
                "hover": "<br>".join(hover),
            }
        )
    for brand in brands:
        nid = brand["id"]
        exc = _exc_for("brand_id", nid)
        acc_row = brand_acc[brand_acc["brand_id"] == nid] if len(brand_acc) else pd.DataFrame()
        wape = float(acc_row["wape"].iloc[0]) if len(acc_row) else None
        bias = float(acc_row["bias"].iloc[0]) if len(acc_row) else None
        hover = [
            brand_names[nid],
            f"Brand · {brand['tier']} · {brand['region']}",
            f"Home site: {site_names.get(brand['home_site'], brand['home_site'])}",
            f"Naive WAPE: {_pct(wape)}" if wape is not None else "Naive WAPE: —",
            f"Naive bias: {_pct(bias)}" if bias is not None else "Naive bias: —",
            f"Exceptions in slice: {len(exc)}",
            f"Synthetic $ at risk: {_money(_risk_for('brand_id', nid))}",
        ]
        selected = brand_id == nid
        nodes.append(
            {
                "id": nid,
                "kind": "brand",
                "label": _network_label("brand", brand_names[nid], compact=compact),
                "x": pos[nid][0],
                "y": pos[nid][1],
                "color": _heat(exc),
                "size": (24 if selected else 18) if compact else (20 if selected else 14),
                "hover": "<br>".join(hover),
            }
        )
    for market in markets:
        nid = market["id"]
        exc = _exc_for("market_id", nid)
        alloc_txt = "—"
        if not alloc.empty:
            plan = alloc[(alloc["year_index"] == 1) & (alloc["market_id"] == nid)]
            if brand_id != "All":
                plan = plan[plan["brand_id"] == brand_id]
            if len(plan):
                alloc_txt = _pct(float(plan["allocation_ratio"].mean()))
        hover = [
            market_names[nid],
            "Market",
            f"Channel: {market.get('channel', '—')}",
            f"Mean allocation ratio: {alloc_txt}",
            f"Exceptions in slice: {len(exc)}",
            f"Synthetic $ at risk: {_money(_risk_for('market_id', nid))}",
        ]
        selected = market_id == nid
        nodes.append(
            {
                "id": nid,
                "kind": "market",
                "label": _network_label("market", market_names[nid], compact=compact),
                "x": pos[nid][0],
                "y": pos[nid][1],
                "color": _heat(exc),
                "size": (24 if selected else 18) if compact else (20 if selected else 14),
                "hover": "<br>".join(hover),
            }
        )

    edges = []
    for brand in brands:
        edges.append((brand["id"], brand["home_site"]))
    if not alloc.empty:
        pairs = alloc[alloc["year_index"] == 1][["brand_id", "market_id"]].drop_duplicates()
        for rec in pairs.itertuples(index=False):
            if rec.brand_id in pos and rec.market_id in pos:
                edges.append((rec.brand_id, rec.market_id))

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for a, b in edges:
        xa, ya = pos[a]
        xb, yb = pos[b]
        hot = False
        if brand_id != "All" and brand_id in {a, b}:
            hot = True
        if market_id != "All" and market_id in {a, b}:
            hot = True
        if site_id != "All" and site_id in {a, b}:
            hot = True
        if brand_id == "All" and market_id == "All" and site_id == "All":
            hot = True
        if not hot:
            continue
        edge_x.extend([xa, xb, None])
        edge_y.extend([ya, yb, None])

    if compact:
        textpos = [
            "bottom center" if n["kind"] in {"site", "market"} else "middle right" for n in nodes
        ]
        annotations = [
            dict(x=0.5, y=1.16, text="SITES", showarrow=False, font=dict(color=MUTED, size=11, family="Inter"), xanchor="center"),
            dict(x=0.5, y=0.84, text="BRANDS", showarrow=False, font=dict(color=MUTED, size=11, family="Inter"), xanchor="center"),
            dict(x=0.5, y=0.18, text="MARKETS", showarrow=False, font=dict(color=MUTED, size=11, family="Inter"), xanchor="center"),
        ]
        axis_x = dict(visible=False, range=[-0.02, 1.02])
        axis_y = dict(visible=False, range=[-0.14, 1.22])
        margins = dict(l=8, r=8, t=28, b=36)
        height = 820
        font_size = 10
    else:
        textpos = "middle right"
        annotations = [
            dict(x=0, y=1.08, text="SITES", showarrow=False, font=dict(color=MUTED, size=11, family="Inter"), xanchor="center"),
            dict(x=1, y=1.08, text="BRANDS", showarrow=False, font=dict(color=MUTED, size=11, family="Inter"), xanchor="center"),
            dict(x=2, y=1.08, text="MARKETS", showarrow=False, font=dict(color=MUTED, size=11, family="Inter"), xanchor="center"),
        ]
        axis_x = dict(visible=False, range=[-0.15, 2.55])
        axis_y = dict(visible=False, range=[-0.12, 1.12])
        margins = dict(l=10, r=140, t=10, b=10)
        height = 460
        font_size = 11

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=edge_x,
            y=edge_y,
            mode="lines",
            line=dict(width=1, color="rgba(70,80,94,0.16)"),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[n["x"] for n in nodes],
            y=[n["y"] for n in nodes],
            mode="markers+text",
            text=[n["label"] for n in nodes],
            textposition=textpos,
            textfont=dict(color=CHARCOAL, size=font_size + 1, family="Inter"),
            cliponaxis=False,
            marker=dict(
                size=[n["size"] for n in nodes],
                color=[n["color"] for n in nodes],
                line=dict(width=2, color="#FFFFFF"),
            ),
            customdata=[[n["kind"], n["id"]] for n in nodes],
            hovertext=[n["hover"] for n in nodes],
            hovertemplate="%{hovertext}<extra></extra>",
            showlegend=False,
        )
    )
    fig.update_layout(
        height=height,
        margin=margins,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=axis_x,
        yaxis=axis_y,
        dragmode=False,
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="#E5E2DC", font_size=13, font_family="Inter", font_color=CHARCOAL),
        annotations=annotations,
    )
    return fig


def _network_event_points(event) -> list:
    sel = getattr(event, "selection", None) if event is not None else None
    if isinstance(sel, dict):
        return sel.get("points") or []
    if sel is not None:
        return getattr(sel, "points", None) or []
    return []


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
    p, label, button, input, li, td, th, span, div {
        font-family: "Inter", "Segoe UI", Helvetica, Arial, sans-serif;
    }
    .stApp { background: #F6F4F0 !important; }
    [data-testid="stHeader"] { background: transparent !important; }
    .main .block-container, [data-testid="stMainBlockContainer"] {
        padding-top: 1.6rem !important; max-width: 1320px;
    }
    h2, h3 { color: #1F2328 !important; font-weight: 650 !important; letter-spacing: -0.01em; }

    /* Hero band */
    .hero {
        position: relative; overflow: hidden;
        border-radius: 18px; padding: 30px 34px 26px 34px; margin: 0 0 18px 0;
        background:
          linear-gradient(115deg, rgba(48,10,18,0.94) 0%, rgba(110,22,38,0.88) 55%, rgba(140,28,43,0.70) 100%),
          url("CELLAR_URI") center/cover no-repeat;
        color: #FFFFFF;
        box-shadow: 0 10px 30px rgba(60,12,22,0.18);
    }
    .hero .eyebrow { letter-spacing: 0.28em; font-size: 0.72rem; font-weight: 600; color: #E8D2B0; margin: 0 0 6px 0; }
    .hero h1 {
        font-family: "Playfair Display", Georgia, serif !important;
        font-size: 2.4rem; font-weight: 700; line-height: 1.1; margin: 0 0 10px 0; padding: 0; color: #FFFFFF !important;
    }
    .hero .lede { color: rgba(255,255,255,0.82); font-size: 0.98rem; max-width: 52rem; margin: 0 0 14px 0; }
    .hero .chips { display: flex; gap: 8px; flex-wrap: wrap; }
    .chip {
        display: inline-block; padding: 4px 11px; border-radius: 999px; font-size: 0.72rem;
        font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
    }
    .chip-calc { background: #FFFFFF; color: #8C1C2B; }
    .chip-ai { background: rgba(232,210,176,0.16); color: #E8D2B0; border: 1px solid rgba(232,210,176,0.55); }
    .chip-slice { background: rgba(255,255,255,0.10); color: #FFFFFF; border: 1px solid rgba(255,255,255,0.25); text-transform: none; letter-spacing: 0; font-weight: 500; }

    /* KPI cards */
    .kpi-row { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin: 0 0 8px 0; }
    .kpi-group { font-size: 0.68rem; letter-spacing: 0.16em; font-weight: 600; color: #6B7280; margin: 6px 0 8px 2px; text-transform: uppercase; }
    .kpi {
        background: #FFFFFF; border-radius: 14px; padding: 16px 18px 14px 18px;
        border: 1px solid #ECE8E1; box-shadow: 0 1px 2px rgba(31,35,40,0.04), 0 6px 18px rgba(31,35,40,0.05);
    }
    .kpi.slice { background: #FBF6F2; border-color: #EBDCD3; }
    .kpi-label { font-size: 0.74rem; color: #6B7280; font-weight: 500; margin-bottom: 6px; }
    .kpi-value { font-size: 1.85rem; font-weight: 700; color: #1F2328; line-height: 1.1; letter-spacing: -0.02em; }
    .kpi.good .kpi-value { color: #3F6B46; }
    .kpi.alert .kpi-value { color: #8C1C2B; }
    .kpi-note { font-size: 0.74rem; color: #8A9099; margin-top: 4px; min-height: 1em; }

    /* Story cards */
    .story {
        background: #FFFFFF; border-radius: 14px; padding: 16px 16px 12px 16px; height: 100%;
        border: 1px solid #ECE8E1; border-top: 4px solid #8C1C2B;
        box-shadow: 0 6px 18px rgba(31,35,40,0.05);
        min-height: 178px; margin-bottom: 8px;
    }
    .story.on { box-shadow: 0 0 0 2px #8C1C2B, 0 8px 22px rgba(140,28,43,0.18); }
    .story .sid { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.12em; color: #8C1C2B; }
    .story .ok { float: right; font-size: 0.68rem; font-weight: 600; color: #3F6B46; background: #E8F1E9; padding: 2px 8px; border-radius: 999px; }
    .story .miss { float: right; font-size: 0.68rem; font-weight: 600; color: #8C1C2B; background: #F7E4E6; padding: 2px 8px; border-radius: 999px; }
    .story h4 { font-size: 1.02rem !important; font-weight: 650; color: #1F2328; margin: 8px 0 6px 0 !important; padding: 0 !important; }
    .story p { font-size: 0.84rem; color: #5B6270; margin: 0; line-height: 1.45; }

    /* Panels */
    [data-testid="stVerticalBlockBorderWrapper"] h1 { font-size: 1.55rem !important; color: #8C1C2B !important; }
    [data-testid="stVerticalBlockBorderWrapper"] h2 { font-size: 1.15rem !important; margin-top: 0.8rem !important; }
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #FFFFFF; border-radius: 14px !important; border-color: #ECE8E1 !important;
        box-shadow: 0 6px 18px rgba(31,35,40,0.05);
    }
    .section-title { font-size: 1.05rem; font-weight: 650; color: #1F2328; margin: 2px 0 2px 0; }
    .section-sub { font-size: 0.82rem; color: #6B7280; margin: 0 0 8px 0; }
    .stat-list { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 6px 0 14px 0; }
    .stat { background: #F8F6F2; border-radius: 10px; padding: 10px 12px; }
    .stat b { display: block; font-size: 1.25rem; color: #1F2328; }
    .stat span { font-size: 0.74rem; color: #6B7280; }

    .human-gate {
        border-left: 4px solid #B08D57; padding: 12px 16px; border-radius: 8px;
        background: #FBF5EA; color: #4A3B22; margin-bottom: 14px;
    }
    .badge-ai {
        background: #FFFFFF; color: #8A6A35; border: 1px solid #B08D57; border-radius: 999px;
        padding: 2px 10px; font-size: 11px; letter-spacing: 0.06em; font-weight: 600; text-transform: uppercase; margin-right: 8px;
    }
    .shock-now {
        border-left: 4px solid #8C1C2B; border-radius: 8px; background: #FBF0F1; color: #4A1A22;
        padding: 10px 14px; margin: 0.2rem 0 1rem 0; font-size: 0.9rem;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 10px !important; border: 1px solid #E2DDD5 !important; background: #FFFFFF !important;
        color: #1F2328 !important; font-weight: 500 !important; font-size: 0.85rem !important;
        transition: all .15s ease;
    }
    .stButton > button:hover { border-color: #8C1C2B !important; color: #8C1C2B !important; }
    .stButton > button[kind="primary"] { background: #8C1C2B !important; color: #FFFFFF !important; border-color: #8C1C2B !important; }

    /* Tabs */
    [data-testid="stTabs"] [role="tablist"] { gap: 6px; border-bottom: 1px solid #E5E1DA; margin-bottom: 10px; }
    [data-testid="stTab"] {
        font-size: 0.98rem !important; font-weight: 500 !important; color: #6B7280 !important;
        padding: 0.7rem 1.1rem !important; border-bottom: 3px solid transparent !important;
    }
    [data-testid="stTab"] p { font-size: inherit !important; color: inherit !important; }
    [data-testid="stTab"][aria-selected="true"] { color: #8C1C2B !important; font-weight: 650 !important; border-bottom: 3px solid #8C1C2B !important; }
    [data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none !important; }

    /* Sidebar */
    [data-testid="stSidebar"] { background: #FFFFFF !important; border-right: 1px solid #ECE8E1; }
    [data-testid="stSidebar"] .side-title { font-size: 0.72rem; letter-spacing: 0.18em; font-weight: 700; color: #8C1C2B; }

    /* Tables */
    [data-testid="stDataFrame"] { border-radius: 12px; overflow: hidden; border: 1px solid #ECE8E1; }

    @media (max-width: 900px) {
        .kpi-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .hero h1 { font-size: 1.7rem; }
        .hero { padding: 22px 20px; }
    }
    @media (max-width: 768px) {
        .main .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
        div[data-testid="stElementContainer"]:has(.net-flag-desktop) + div { display: none !important; }
    }
    @media (min-width: 769px) {
        div[data-testid="stElementContainer"]:has(.net-flag-mobile) + div { display: none !important; }
    }
    div[data-testid="stElementContainer"]:has(.net-flag-desktop),
    div[data-testid="stElementContainer"]:has(.net-flag-mobile) {
        display: none !important; height: 0 !important; margin: 0 !important; min-height: 0 !important;
    }
    </style>
    """.replace("CELLAR_URI", _CELLAR_URI),
    unsafe_allow_html=True,
)

_init_filters()
pack = _load_pack()
brief = _load_brief()
network = load_yaml("network.yaml")
brand_names = {b["id"]: b["name"] for b in network["brands"]}
market_names = {m["id"]: m["name"] for m in network["markets"]}
site_names = {s["id"]: s["name"] for s in network["sites"]}
kpis = pack["kpis"]
planted = pack["planted"]

exceptions = pd.DataFrame(pack["exceptions"])
if not exceptions.empty:
    exceptions["planted_id"] = exceptions["planted_id"].fillna("")
    exceptions["brand"] = exceptions["brand_id"].map(lambda x: brand_names.get(x, x) if not _blank(x) else "—")
    exceptions["market"] = exceptions["market_id"].map(lambda x: market_names.get(x, x) if not _blank(x) else "—")
    exceptions["site"] = exceptions["site_id"].map(lambda x: site_names.get(x, x) if not _blank(x) else "—")

value = pd.DataFrame(pack["value_register"])
if not value.empty:
    value["planted_id"] = value["planted_id"].fillna("")
    value["brand"] = value["brand_id"].map(lambda x: brand_names.get(x, x) if not _blank(x) else "—")

accuracy = pd.DataFrame(pack["accuracy_hierarchy"])
scenario = pd.DataFrame(pack["scenario"].get("rows") or [])
alloc = _read_csv("fact_allocation.csv")
cap = _read_csv("fact_capacity.csv")
demand = _read_csv("fact_demand.csv")
forecast = _read_csv("fact_forecast.csv")
bulk = _read_csv("fact_bulk_inventory.csv")

with st.sidebar:
    st.markdown('<div class="side-title">PLANNING SLICE</div>', unsafe_allow_html=True)
    st.caption("Filters persist across views. Network KPIs stay at pack grain. Slice KPIs follow the selection.")
    shock_options = ["All", "P1", "P2", "P3", "BIAS"]
    st.selectbox("Planted shock", shock_options, key="shock")
    st.selectbox(
        "Brand",
        ["All"] + [b["id"] for b in network["brands"]],
        format_func=lambda x: "All brands" if x == "All" else brand_names.get(x, x),
        key="brand_id",
    )
    st.selectbox(
        "Market",
        ["All"] + [m["id"] for m in network["markets"]],
        format_func=lambda x: "All markets" if x == "All" else market_names.get(x, x),
        key="market_id",
    )
    st.selectbox(
        "Site",
        ["All"] + [s["id"] for s in network["sites"]],
        format_func=lambda x: "All sites" if x == "All" else site_names.get(x, x),
        key="site_id",
    )
    st.slider("Planning weeks", 1, 52, key="week_range")
    st.button("Clear slice", width="stretch", on_click=_clear_filters)
    st.caption("Unscoped harvest and line exceptions remain visible when a brand or market is selected.")

week_lo, week_hi = st.session_state.week_range
shock = st.session_state.shock
brand_id = st.session_state.brand_id
market_id = st.session_state.market_id
site_id = st.session_state.site_id

exc_slice = _slice_frame(
    exceptions, brand_id=brand_id, market_id=market_id, site_id=site_id, week_range=(week_lo, week_hi), shock=shock
)
val_slice = _slice_frame(
    value, brand_id=brand_id, market_id=market_id, site_id=site_id, week_range=(week_lo, week_hi), shock=shock
)
slice_risk = float(val_slice["value_at_risk"].sum()) if len(val_slice) and "value_at_risk" in val_slice.columns else 0.0

slice_bits = [
    "All brands" if brand_id == "All" else brand_names.get(brand_id, brand_id),
    "All markets" if market_id == "All" else market_names.get(market_id, market_id),
    "All sites" if site_id == "All" else site_names.get(site_id, site_id),
    f"weeks {week_lo}–{week_hi}",
    "all shocks" if shock == "All" else f"{shock} · {SHOCKS[shock]['title']}",
]

slice_label = "  ·  ".join(slice_bits)
st.markdown(
    f"""
    <div class="hero">
      <p class="eyebrow">VINTARA ESTATES · S&amp;OP COCKPIT</p>
      <h1>Supply Insights</h1>
      <p class="lede">Fictional luxury wine group on synthetic planning data. Every number is calculated by the engine;
      AI commentary is labelled and never executes a supply action.</p>
      <div class="chips">
        <span class="chip chip-calc">Calculated</span>
        <span class="chip chip-ai">AI commentary</span>
        <span class="chip chip-slice">{slice_label}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

detected = planted["detected_count"]
st.markdown(
    '<div class="kpi-group">Network · full year &nbsp;&nbsp;|&nbsp;&nbsp; Current slice</div>'
    '<div class="kpi-row">'
    + _kpi_card("Planted problems detected", f"{detected}/3", "harvest · demand · bottling", tone="good" if detected == 3 else "alert")
    + _kpi_card("Forecast error (naive)", _pct(kpis["wape_seasonal_naive"]), "WAPE · seasonal naive", tone="good")
    + _kpi_card("Forecast error (ETS)", _pct(kpis["wape_ets"]), "naive wins on seasonal data")
    + _kpi_card("Value at risk", _money_short(kpis["value_at_risk_total"]), "synthetic $, ranking only", tone="alert")
    + _kpi_card("Exceptions in slice", f"{len(exc_slice):,}", f"of {len(exceptions):,} in the year", tone="slice")
    + _kpi_card("Slice value at risk", _money_short(slice_risk), "follows the filters", tone="slice")
    + "</div>",
    unsafe_allow_html=True,
)

exec_tab, planner_tab, value_tab, brief_tab = st.tabs(
    ["Executive", "Planner", "Value & portfolio", "S&OP brief"]
)

with exec_tab:
    st.markdown('<div class="section-title">Planted stories</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-sub">Four problems were planted in the synthetic year. Click one to slice the whole cockpit to it.</div>',
        unsafe_allow_html=True,
    )
    if shock in SHOCKS:
        meta_now = SHOCKS[shock]
        st.markdown(
            f'<div class="shock-now"><strong>Showing {shock}</strong> · {meta_now["jump"]}. '
            f"Top-row network KPIs stay full-year. Use <b>Clear slice</b> in the sidebar to reset.</div>",
            unsafe_allow_html=True,
        )
    story_cols = st.columns(4)
    for col, shock_id in zip(story_cols, ["P1", "P2", "P3", "BIAS"]):
        meta = SHOCKS[shock_id]
        found = planted.get(shock_id, shock_id == "BIAS")
        on_this = shock == shock_id
        pill = '<span class="ok">Detected</span>' if found else '<span class="miss">Missed</span>'
        with col:
            st.markdown(
                f'<div class="story{" on" if on_this else ""}"><span class="sid">{shock_id}</span>{pill}'
                f'<h4>{meta["title"]}</h4><p>{meta["why"]}</p></div>',
                unsafe_allow_html=True,
            )
            st.button(
                "Viewing" if on_this else "View this story",
                width="stretch",
                key=f"shock_jump_{shock_id}",
                type="primary" if on_this else "secondary",
                on_click=_focus_shock,
                args=(shock_id,),
            )

    st.write("")
    with st.container(border=True):
        left, right = st.columns((1.6, 1), gap="large")
        with left:
            st.markdown('<div class="section-title">Barossa bulk wine cover: plan vs harvest −30%</div>'
                        '<div class="section-sub">Weeks of cover. Shaded bands are the planted shock windows (P1 · P2 · P3). calc_id scn:harvest_shortfall</div>',
                        unsafe_allow_html=True)
            cover = pd.DataFrame()
            if len(scenario) and "metric" in scenario.columns:
                cover = scenario[(scenario["metric"] == "bulk_cover_weeks") & (scenario["year_index"] == 1)].copy()
                cover = _slice_frame(
                    cover,
                    brand_id=brand_id,
                    market_id="All",
                    site_id=site_id if site_id != "All" else "S_BAR",
                    week_range=(1, 52),
                    shock="All",
                    keep_unscoped=False,
                )
            if len(cover):
                weekly = cover.groupby("planning_week", as_index=False)[["baseline", "shocked"]].mean()
                weekly = weekly.melt("planning_week", var_name="series", value_name="weeks_of_cover")
                weekly["series"] = weekly["series"].map({"baseline": "Plan", "shocked": "Harvest −30%"})
                bands = pd.DataFrame(
                    [
                        {"shock": "P1", "start": 10, "end": 14},
                        {"shock": "P2", "start": 20, "end": 24},
                        {"shock": "P3", "start": 32, "end": 35},
                    ]
                )
                band = (
                    alt.Chart(bands)
                    .mark_rect(opacity=0.10)
                    .encode(
                        x="start:Q",
                        x2="end:Q",
                        color=alt.Color(
                            "shock:N",
                            legend=None,
                            scale=alt.Scale(domain=["P1", "P2", "P3"], range=[RED, GOLD, LEAF]),
                        ),
                    )
                )
                line = (
                    alt.Chart(weekly)
                    .mark_line(strokeWidth=3, interpolate="monotone")
                    .encode(
                        x=alt.X("planning_week:Q", title="Planning week"),
                        y=alt.Y("weeks_of_cover:Q", title="Bulk cover (weeks)"),
                        color=alt.Color(
                            "series:N",
                            title="",
                            scale=alt.Scale(domain=["Plan", "Harvest −30%"], range=[IVORY, RED]),
                        ),
                        tooltip=["planning_week", "series", "weeks_of_cover"],
                    )
                )
                st.altair_chart(_finish_chart((band + line).resolve_scale(color="independent").properties(height=330).interactive()), width="stretch")
                st.caption(
                    f"Harvest intake ratio on weeks 10–14, year 1 = **{pack['scenario']['intake_shocked_over_baseline']:.2f}** (network)."
                )
            else:
                st.info("No harvest scenario rows in this slice.")
        with right:
            st.markdown(
                '<div class="section-title">Network service</div><div class="section-sub">Full year, not re-sliced.</div>'
                '<div class="stat-list">'
                f'<div class="stat"><b>{_pct(kpis["fill_rate_proxy"], 1)}</b><span>Fill-rate proxy</span></div>'
                f'<div class="stat"><b>{_pct(kpis["pct_bottled_below_cover"], 2)}</b><span>Bottled below 4-wk cover</span></div>'
                f'<div class="stat"><b>{pack["mean_bulk_cover"]:.1f} wks</b><span>Mean bulk cover</span></div>'
                f'<div class="stat"><b>{_pct(pack["mean_allocation_ratio"])}</b><span>Mean allocation ratio</span></div>'
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown('<div class="section-title">Inspect exception</div>', unsafe_allow_html=True)
            if st.session_state.exception_id and not exc_slice.empty:
                picked = exc_slice[exc_slice["exception_id"] == st.session_state.exception_id]
                if picked.empty:
                    st.caption("Selected exception is outside this slice.")
                else:
                    row = picked.iloc[0]
                    st.write(
                        f"**{row['exception_id']}** · {row['type']} · {row['severity']}  \n"
                        f"{row['brand']} · {row['site']} · {row['market']} · week {int(row['planning_week']) if not _blank(row.get('planning_week')) else '—'}"
                    )
                    linked = value[value["exception_id"] == row["exception_id"]] if not value.empty else pd.DataFrame()
                    if len(linked):
                        vr = linked.iloc[0]
                        st.write(
                            f"Synthetic $ at risk: **{_money(vr['value_at_risk'])}**  \n"
                            f"Action code: **{vr['recommended_action_code']}**  \n"
                            f"{vr['calc_id']}"
                        )
                    if not _blank(row.get("brand_id")):
                        st.button("Focus this brand", on_click=_set_brand, args=(row["brand_id"],))
            else:
                st.caption("Select a row in the table.")

    st.write("")
    st.markdown(
        '<div class="section-title">Supply network</div>'
        '<div class="section-sub">Sites → brands → markets. Red nodes carry a planted exception in this slice. Tap a node to slice to it.</div>',
        unsafe_allow_html=True,
    )
    net_kwargs = dict(
        network=network,
        accuracy=accuracy,
        exc_slice=exc_slice,
        val_slice=val_slice,
        alloc=alloc,
        cap=cap,
        brand_id=brand_id,
        market_id=market_id,
        site_id=site_id,
    )
    chart_cfg = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}
    st.markdown('<div class="net-flag-desktop"></div>', unsafe_allow_html=True)
    net_wide = st.plotly_chart(
        _supply_network_figure(**net_kwargs, compact=False),
        width="stretch",
        on_select="rerun",
        selection_mode="points",
        key="supply_network",
        config=chart_cfg,
    )
    st.markdown('<div class="net-flag-mobile"></div>', unsafe_allow_html=True)
    net_narrow = st.plotly_chart(
        _supply_network_figure(**net_kwargs, compact=True),
        width="stretch",
        on_select="rerun",
        selection_mode="points",
        key="supply_network_mobile",
        config=chart_cfg,
    )
    points = _network_event_points(net_wide) or _network_event_points(net_narrow)
    if points:
        pt = points[0]
        cd = pt.get("customdata") if isinstance(pt, dict) else getattr(pt, "customdata", None)
        if cd is not None:
            kind, nid = (cd[0], cd[1]) if not isinstance(cd, str) else (None, None)
            if kind and nid:
                st.session_state.network_pick = {"kind": kind, "id": nid}
    pick = st.session_state.get("network_pick")
    if pick and pick.get("id"):
        kind = pick["kind"]
        nid = pick["id"]
        if kind == "brand":
            label = brand_names.get(nid, nid)
        elif kind == "market":
            label = market_names.get(nid, nid)
        else:
            label = site_names.get(nid, nid)
        slice_col, _ = st.columns((1, 3))
        slice_col.button(
            f"Slice to {label}",
            width="stretch",
            on_click=_apply_network_pick,
        )

    st.markdown(
        '<div class="section-title">Exceptions in slice</div><div class="section-sub">Click a row to inspect it. Sort any column.</div>',
        unsafe_allow_html=True,
    )
    show_cols = [
        c
        for c in [
            "exception_id",
            "planted_id",
            "type",
            "severity",
            "brand",
            "site",
            "market",
            "planning_week",
            "value",
            "calc_id",
        ]
        if c in exc_slice.columns
    ]
    table = exc_slice[show_cols].sort_values(["planted_id", "severity"], ascending=[False, True]) if show_cols else exc_slice
    event = st.dataframe(
        table,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "planning_week": st.column_config.NumberColumn("Week", format="%d"),
            "value": st.column_config.NumberColumn("Value", format="%.1f"),
        },
        key="exec_exceptions",
    )
    selected = event.selection.rows if event.selection else []
    if selected:
        st.session_state.exception_id = str(table.iloc[selected[0]]["exception_id"])

with planner_tab:
    st.subheader("Forecast accuracy")
    st.caption("Select a brand to apply it to the slice. Network WAPE remains at pack grain.")
    brand_acc = accuracy[(accuracy["grain"] == "brand") & (accuracy["model_name"] == "seasonal_naive")].copy()
    if brand_id != "All":
        brand_acc = brand_acc[brand_acc["brand_id"] == brand_id]
    brand_acc["brand"] = brand_acc["brand_id"].map(lambda x: brand_names.get(x, x))
    brand_acc["wape_pct"] = brand_acc["wape"] * 100
    brand_acc["bias_pct"] = brand_acc["bias"] * 100
    _bar_chart(brand_acc[["brand", "wape_pct", "bias_pct", "calc_id"]], "wape_pct", "brand", "Seasonal naive WAPE %")

    pick_cols = st.columns(len(brand_acc) if 0 < len(brand_acc) <= 8 else 1)
    if 0 < len(brand_acc) <= 8:
        for col, (_, row) in zip(pick_cols, brand_acc.sort_values("wape", ascending=False).iterrows()):
            col.button(
                row["brand"].replace("Vintara ", ""),
                width="stretch",
                on_click=_set_brand,
                args=(row["brand_id"],),
            )

    st.dataframe(
        brand_acc[["brand", "wape", "bias", "calc_id"]].sort_values("wape", ascending=False),
        width="stretch",
        hide_index=True,
        column_config={
            "wape": st.column_config.NumberColumn("WAPE", format="percent"),
            "bias": st.column_config.NumberColumn("Bias", format="percent"),
        },
    )

    d1, d2 = st.columns(2)
    with d1:
        st.markdown("**Demand vs seasonal-naive forecast**")
        st.caption("Planning year. Slice by brand and market.")
        if demand.empty or forecast.empty:
            st.info("Power BI CSVs not found. Run python -m src.engine.")
        else:
            dem = demand[demand["year_index"] == 1].copy()
            fc = forecast[(forecast["year_index"] == 1) & (forecast["model_name"] == "seasonal_naive")].copy()
            dem = _slice_frame(dem, brand_id=brand_id, market_id=market_id, site_id="All", week_range=(week_lo, week_hi), shock="All", keep_unscoped=False)
            fc = _slice_frame(fc, brand_id=brand_id, market_id=market_id, site_id="All", week_range=(week_lo, week_hi), shock="All", keep_unscoped=False)
            weekly_dem = dem.groupby("planning_week", as_index=False)["actual_cases"].sum() if len(dem) else pd.DataFrame()
            weekly_fc = fc.groupby("planning_week", as_index=False)["forecast_cases"].sum() if len(fc) else pd.DataFrame()
            series = pd.DataFrame()
            if len(weekly_dem):
                series = weekly_dem.rename(columns={"actual_cases": "cases"}).assign(series="Actual")
            if len(weekly_fc):
                add = weekly_fc.rename(columns={"forecast_cases": "cases"}).assign(series="Seasonal naive")
                series = pd.concat([series, add], ignore_index=True)
            if len(series):
                _line_chart(series, "planning_week", "cases", "series", "Cases")
            else:
                st.info("No demand/forecast rows in this slice.")
    with d2:
        st.markdown("**Allocation ratio by market**")
        if alloc.empty:
            st.info("fact_allocation.csv missing.")
        else:
            plan = alloc[alloc["year_index"] == 1].copy()
            plan = _slice_frame(plan, brand_id=brand_id, market_id=market_id, site_id="All", week_range=(week_lo, week_hi), shock="All", keep_unscoped=False)
            if len(plan):
                by_mkt = plan.groupby("market_id", as_index=False)["allocation_ratio"].mean()
                by_mkt["market"] = by_mkt["market_id"].map(market_names)
                _bar_chart(by_mkt[["market", "allocation_ratio", "market_id"]], "allocation_ratio", "market", "Mean allocation ratio", worst="low", fmt=".1%")
                mcols = st.columns(len(by_mkt))
                for col, (_, row) in zip(mcols, by_mkt.iterrows()):
                    col.button(
                        row["market"],
                        key=f"mkt_{row['market_id']}",
                        width="stretch",
                        on_click=_set_market,
                        args=(row["market_id"],),
                    )
            else:
                st.info("No allocation rows in this slice.")

    st.markdown("**Bottling utilisation by site**")
    st.caption("Filtered by site and week. Not related to brand.")
    if cap.empty:
        st.info("fact_capacity.csv missing.")
    else:
        plan_cap = cap[cap["year_index"] == 1].copy()
        plan_cap = _slice_frame(plan_cap, brand_id="All", market_id="All", site_id=site_id, week_range=(week_lo, week_hi), shock="All", keep_unscoped=False)
        if len(plan_cap):
            plan_cap["utilisation"] = plan_cap["utilised_cases"] / plan_cap["bottling_capacity_cases"].clip(lower=0.1)
            plan_cap["site"] = plan_cap["site_id"].map(site_names)
            _line_chart(plan_cap[["planning_week", "utilisation", "site"]], "planning_week", "utilisation", "site", "Utilisation")
            scols = st.columns(plan_cap["site_id"].nunique())
            for col, sid in zip(scols, sorted(plan_cap["site_id"].unique())):
                col.button(
                    site_names.get(sid, sid),
                    key=f"site_{sid}",
                    width="stretch",
                    on_click=_set_site,
                    args=(sid,),
                )
        else:
            st.info("No capacity rows in this slice.")

    if not bulk.empty:
        st.markdown("**Bulk weeks of cover**")
        cover_bulk = bulk[bulk["year_index"] == 1].copy()
        cover_bulk = _slice_frame(
            cover_bulk, brand_id=brand_id, market_id="All", site_id=site_id, week_range=(week_lo, week_hi), shock="All", keep_unscoped=False
        )
        if len(cover_bulk):
            cover_bulk["brand"] = cover_bulk["brand_id"].map(brand_names)
            weekly_cover = cover_bulk.groupby(["planning_week", "brand"], as_index=False)["weeks_of_cover"].mean()
            _line_chart(weekly_cover, "planning_week", "weeks_of_cover", "brand", "Weeks of cover")

with value_tab:
    st.subheader("Value register")
    st.caption("Synthetic dollars for ranking only. Select a row, then open Executive to inspect the exception.")
    if val_slice.empty:
        st.info("No value rows in this slice.")
    else:
        show = val_slice[
            [
                c
                for c in [
                    "exception_id",
                    "planted_id",
                    "type",
                    "brand",
                    "volume_at_risk",
                    "value_at_risk",
                    "recommended_action_code",
                    "calc_id",
                ]
                if c in val_slice.columns
            ]
        ].sort_values("value_at_risk", ascending=False)
        vevent = st.dataframe(
            show,
            width="stretch",
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "volume_at_risk": st.column_config.NumberColumn("Volume at risk", format="%.1f"),
                "value_at_risk": st.column_config.NumberColumn("$ at risk", format="$%.0f"),
            },
            key="value_table",
        )
        vsel = vevent.selection.rows if vevent.selection else []
        if vsel:
            st.session_state.exception_id = str(show.iloc[vsel[0]]["exception_id"])
            st.caption(f"Selected {st.session_state.exception_id}. Open Executive to inspect.")
        planted_val = val_slice.groupby(val_slice["planted_id"].replace("", "other"), as_index=False)["value_at_risk"].sum()
        planted_val = planted_val.rename(columns={"planted_id": "shock"})
        _bar_chart(planted_val, "value_at_risk", "shock", "Synthetic $ at risk", fmt="$,.0f")

    st.subheader("Supply AI portfolio")
    st.caption("What this proof of concept owns. Ranked in the pack, not a new metric.")
    port = pd.DataFrame(pack["portfolio"])
    st.dataframe(port, width="stretch", hide_index=True)
    st.markdown("**Adoption note**")
    st.write(
        "The S&OP lead owns the exception pack. Brand managers confirm allocation calls. "
        "Operations owns the bottling window. Nothing in this cockpit writes an order, a transfer, or a forecast override."
    )

with brief_tab:
    st.subheader("Governed S&OP briefing")
    st.markdown(
        '<div class="human-gate"><span class="badge-ai">AI commentary</span> '
        "Draft only. Human review required. No supply action is executed from this brief.</div>",
        unsafe_allow_html=True,
    )
    if not brief:
        st.warning("No cached brief yet. Run python -m src.briefing")
    else:
        st.caption(f"Mode: {brief.get('mode')} · {brief.get('generated_at')}")
        with st.container(border=True):
            st.markdown(brief.get("markdown") or "")
        with st.expander("Source references"):
            st.dataframe(pd.DataFrame(brief.get("source_refs") or []), width="stretch", hide_index=True)
