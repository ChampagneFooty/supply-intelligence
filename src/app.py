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
    "P1": {"title": "Barossa harvest −30%", "weeks": (10, 14)},
    "P2": {"title": "UK Reserve Shiraz +40%", "weeks": (20, 24)},
    "P3": {"title": "Barossa bottling −35%", "weeks": (32, 35)},
    "BIAS": {"title": "New-release Chardonnay over-forecast", "weeks": (1, 52)},
}

RED = "#B11F24"
CHARCOAL = "#2C3139"
IVORY = "#F7F5F2"
GOLD = "#C4A36A"
STONE = "#8B909A"
LEAF = "#5C6B5A"

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
        chart.configure(background="transparent")
        .configure_view(strokeWidth=0)
        .configure_axis(
            gridColor="#3E4450",
            domainColor="#5A616C",
            labelColor="#C8C4BC",
            titleColor=IVORY,
            titleFont="Source Sans 3",
            labelFont="Source Sans 3",
        )
        .configure_legend(labelColor=IVORY, titleColor=IVORY, labelFont="Source Sans 3")
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
            scale=alt.Scale(range=[RED, GOLD, IVORY, LEAF, STONE]),
        )
    chart = alt.Chart(df).mark_line(point=True).encode(**encode).properties(height=280).interactive()
    st.altair_chart(_finish_chart(chart), width="stretch")


def _bar_chart(df: pd.DataFrame, x: str, y: str, title: str) -> None:
    if df.empty:
        st.info("No rows in this slice.")
        return
    chart = (
        alt.Chart(df)
        .mark_bar(color=RED)
        .encode(
            x=alt.X(f"{x}:Q", title=title),
            y=alt.Y(f"{y}:N", sort="-x", title=""),
            tooltip=list(df.columns),
        )
        .properties(height=max(160, 28 * len(df)))
    )
    st.altair_chart(_finish_chart(chart), width="stretch")


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
            return IVORY
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
            dict(x=0.5, y=1.16, text="SITES", showarrow=False, font=dict(color=STONE, size=11), xanchor="center"),
            dict(x=0.5, y=0.84, text="BRANDS", showarrow=False, font=dict(color=STONE, size=11), xanchor="center"),
            dict(x=0.5, y=0.18, text="MARKETS", showarrow=False, font=dict(color=STONE, size=11), xanchor="center"),
        ]
        axis_x = dict(visible=False, range=[-0.02, 1.02])
        axis_y = dict(visible=False, range=[-0.14, 1.22])
        margins = dict(l=8, r=8, t=28, b=36)
        height = 820
        font_size = 10
    else:
        textpos = "middle right"
        annotations = [
            dict(x=0, y=1.08, text="SITES", showarrow=False, font=dict(color=STONE, size=11), xanchor="center"),
            dict(x=1, y=1.08, text="BRANDS", showarrow=False, font=dict(color=STONE, size=11), xanchor="center"),
            dict(x=2, y=1.08, text="MARKETS", showarrow=False, font=dict(color=STONE, size=11), xanchor="center"),
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
            line=dict(width=1.2, color="rgba(196,163,106,0.35)"),
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
            textfont=dict(color=IVORY, size=font_size, family="Source Sans 3"),
            cliponaxis=False,
            marker=dict(
                size=[n["size"] for n in nodes],
                color=[n["color"] for n in nodes],
                line=dict(width=1.2, color=IVORY),
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
        hoverlabel=dict(bgcolor=CHARCOAL, font_size=13, font_family="Source Sans 3", font_color=IVORY),
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
    .stApp { border-top: 3px solid #B11F24; background-color: #2C3139 !important; }
    .stApp::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: 0;
        pointer-events: none;
        background-image: url("CELLAR_URI");
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        opacity: 0.08;
    }
    [data-testid="stAppViewContainer"],
    [data-testid="stHeader"],
    [data-testid="stMain"],
    .stMain,
    section.main,
    .main .block-container {
        background-color: transparent !important;
        background-image: none !important;
    }
    [data-testid="stAppViewContainer"] > * {
        position: relative;
        z-index: 1;
    }
    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"],
    h1, h2, h3, h4, p, label, button, input {
        font-family: "Source Sans 3", "Segoe UI", Helvetica, Arial, sans-serif !important;
    }
    .hero { margin: 0.4rem 0 1.4rem 0; }
    .hero .eyebrow {
        letter-spacing: 0.22em;
        font-size: 0.72rem;
        font-weight: 600;
        color: #C8C4BC;
        margin: 0 0 0.45rem 0;
    }
    .hero h1 {
        font-size: 2.15rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        line-height: 1.15;
        margin: 0 0 0.7rem 0;
        color: #F7F5F2;
    }
    .hero .rule { width: 56px; height: 2px; background: #B11F24; margin-bottom: 0.85rem; }
    .hero .lede { color: #C8C4BC; font-size: 0.98rem; max-width: 46rem; margin: 0; }
    .badge-calc {
        background: #B11F24; color: #fff; padding: 3px 10px;
        font-size: 11px; letter-spacing: 0.08em; font-weight: 600;
        margin-right: 8px; text-transform: uppercase;
    }
    .badge-ai {
        background: transparent; color: #C4A36A; border: 1px solid #C4A36A;
        padding: 2px 10px; font-size: 11px; letter-spacing: 0.08em;
        font-weight: 600; text-transform: uppercase;
    }
    .human-gate {
        border: 1px solid #B11F24; padding: 14px 16px;
        background: #3A2A2C; color: #F7F5F2;
    }
    .slice-bar {
        color: #C8C4BC; font-size: 0.88rem; letter-spacing: 0.04em;
        margin: 0.85rem 0 1.1rem 0;
    }
    div[data-testid="stMetric"] {
        background: #242830; padding: 16px 16px 14px 16px;
        border: 1px solid #3E4450;
    }
    div[data-testid="stMetric"] label { letter-spacing: 0.06em; text-transform: uppercase; font-size: 0.72rem; }
    h2, h3 { letter-spacing: 0.06em; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        letter-spacing: 0.14em;
    }
    [data-testid="stTab"] {
        font-size: 1.12rem !important;
        font-weight: 600 !important;
        padding: 0.95rem 1.4rem 0.8rem 1.4rem !important;
        color: #F7F5F2 !important;
        border-bottom: 4px solid transparent !important;
    }
    [data-testid="stTab"] p, [data-testid="stTab"] span {
        font-size: inherit !important;
        color: inherit !important;
    }
    [data-testid="stTab"][aria-selected="true"] {
        color: #F7F5F2 !important;
        font-weight: 700 !important;
        font-size: 1.22rem !important;
        border-bottom: 4px solid #B11F24 !important;
    }
    @media (max-width: 768px) {
        .main .block-container { padding-left: 0.75rem !important; padding-right: 0.75rem !important; }
        div[data-testid="stElementContainer"]:has(.net-flag-desktop) + div { display: none !important; }
        .hero h1 { font-size: 1.55rem !important; }
    }
    @media (min-width: 769px) {
        div[data-testid="stElementContainer"]:has(.net-flag-mobile) + div { display: none !important; }
    }
    div[data-testid="stElementContainer"]:has(.net-flag-desktop),
    div[data-testid="stElementContainer"]:has(.net-flag-mobile) {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        min-height: 0 !important;
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
    st.markdown("**PLANNING SLICE**")
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

st.markdown(
    """
    <div class="hero">
      <p class="eyebrow">VINTARA ESTATES</p>
      <h1>SUPPLY INSIGHTS</h1>
      <div class="rule"></div>
      <p class="lede">
        Fictional luxury wine group. Synthetic planning data.
        Calculated figures are marked in red. Commentary is marked in gold and is not an approved action.
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<span class="badge-calc">Calculated</span><span class="badge-ai">AI commentary</span>',
    unsafe_allow_html=True,
)
st.markdown(f'<div class="slice-bar">{"  ·  ".join(slice_bits)}</div>', unsafe_allow_html=True)

net1, net2, net3, net4, sl1, sl2 = st.columns(6)
net1.metric("Planted detected", f"{planted['detected_count']}/3")
net2.metric("Network naive WAPE", _pct(kpis["wape_seasonal_naive"]))
net3.metric("Network ETS WAPE", _pct(kpis["wape_ets"]))
net4.metric("Network $ at risk", _money(kpis["value_at_risk_total"]))
sl1.metric("Exceptions in slice", f"{len(exc_slice):,}")
sl2.metric("Slice $ at risk", _money(slice_risk))

exec_tab, planner_tab, value_tab, brief_tab = st.tabs(
    ["Executive", "Planner", "Value & portfolio", "S&OP brief"]
)

with exec_tab:
    st.subheader("Planted problems")
    st.caption("Select a shock to move the slice to that window.")
    cards = st.columns(4)
    for col, shock_id in zip(cards, ["P1", "P2", "P3", "BIAS"]):
        meta = SHOCKS[shock_id]
        detected = planted.get(shock_id, shock_id == "BIAS")
        label = f"{shock_id} · {'Detected' if detected else 'Missed'}"
        col.button(
            label,
            width="stretch",
            help=f"{meta['title']} · weeks {meta['weeks'][0]}–{meta['weeks'][1]}",
            on_click=_focus_shock,
            args=(shock_id,),
        )
        col.caption(f"{meta['title']}\nWeeks {meta['weeks'][0]}–{meta['weeks'][1]}")

    st.markdown("**Supply network**")
    st.caption(
        "Calculated graph of sites, brands and markets. Not a machine-learning cluster. "
        "Hover or tap a node for pack figures, then slice to it."
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

    left, right = st.columns((1.4, 1))
    with left:
        st.markdown("**Barossa bulk cover — plan vs harvest −30%**")
        st.caption("calc_id: scn:harvest_shortfall · hover to read a week")
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
                .mark_rect(opacity=0.16)
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
                .mark_line(point=True)
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
            st.altair_chart(_finish_chart((band + line).properties(height=300).interactive()), width="stretch")
            st.caption(
                f"Harvest intake ratio on weeks 10–14, year 1 = **{pack['scenario']['intake_shocked_over_baseline']:.2f}** (network)."
            )
        else:
            st.info("No harvest scenario rows in this slice.")
    with right:
        st.markdown("**Network coverage**")
        st.caption("These four stay at pack grain. They are not re-sliced.")
        st.write(
            f"Fill-rate proxy: **{_pct(kpis['fill_rate_proxy'], 2)}**  \n"
            f"Bottled below 4-week cover: **{_pct(kpis['pct_bottled_below_cover'], 2)}**  \n"
            f"Mean bulk cover: **{pack['mean_bulk_cover']:.1f} weeks**  \n"
            f"Mean allocation ratio: **{_pct(pack['mean_allocation_ratio'])}**"
        )
        st.markdown("**Inspect exception**")
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

    st.markdown("**Exceptions in slice**")
    st.caption("Click a row to inspect it. Sort any column.")
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
                _bar_chart(by_mkt[["market", "allocation_ratio", "market_id"]], "allocation_ratio", "market", "Mean allocation ratio")
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
        _bar_chart(planted_val, "value_at_risk", "shock", "Synthetic $ at risk")

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
        st.markdown(brief.get("markdown") or "")
        with st.expander("Source references"):
            st.dataframe(pd.DataFrame(brief.get("source_refs") or []), width="stretch", hide_index=True)
