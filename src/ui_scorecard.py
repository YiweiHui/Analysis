"""HTML scorecard UI for macro signals."""

from __future__ import annotations

import html
import pandas as pd
import streamlit as st


def _esc(x) -> str:
    if x is None or pd.isna(x):
        return "—"
    return html.escape(str(x))


def _trigger_badge(value) -> str:
    v = str(value)
    if v == "1":
        return '<span class="sig-badge sig-one">1</span>'
    if v == "0":
        return '<span class="sig-badge sig-zero">0</span>'
    return '<span class="sig-badge sig-na">—</span>'


def render_macro_scorecard(detail: pd.DataFrame, dimension: str | None = None) -> None:
    """Render screenshot-like hierarchical scorecard as HTML.

    Layout follows the reference screenshot: a left merged dimension cell with weight,
    indicator rows on the right, plus one additional change column.
    """
    data = detail if dimension is None else detail[detail["dimension"] == dimension]
    if data.empty:
        st.info("该维度暂无指标。")
        return
    data = data.copy()
    if "display_order" in data.columns:
        data = data.sort_values(["display_order", "dimension", "indicator_name"])

    latest_dates = pd.to_datetime(data["latest_date"], errors="coerce").dropna()
    if not latest_dates.empty:
        st.caption(f"截至最新数据日：{latest_dates.max().strftime('%Y-%m-%d')}。变化为较上期绝对变化；百分比类指标变化统一以 pp 展示。")

    css = """
    <style>
    .macro-scorecard-wrap {
        width: 100%;
        overflow-x: hidden;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        background: #FFFFFF;
        margin-top: 0.35rem;
    }
    table.macro-scorecard {
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
        font-size: 14px;
        line-height: 1.35;
    }
    .macro-scorecard th {
        background: #F8FAFC;
        color: #374151;
        font-weight: 650;
        padding: 9px 10px;
        text-align: left;
        border-bottom: 1px solid #E5E7EB;
        border-right: 1px solid #EEF2F7;
        white-space: nowrap;
    }
    .macro-scorecard td {
        padding: 8px 10px;
        border-bottom: 1px solid #EEF2F7;
        border-right: 1px solid #EEF2F7;
        vertical-align: middle;
        color: #111827;
        overflow-wrap: anywhere;
    }
    .macro-scorecard tr:last-child td { border-bottom: none; }
    .dim-cell {
        background: #F3F4F6;
        color: #111827;
        font-weight: 650;
        width: 115px;
        vertical-align: top !important;
    }
    .dim-cell .weight {
        display: block;
        margin-top: 6px;
        font-weight: 500;
        color: #6B7280;
        font-size: 12px;
    }
    .indicator-cell { font-weight: 520; }
    .num-cell, .change-cell, .trigger-cell { white-space: nowrap; }
    .rule-cell { color: #374151; }
    .state-cell { white-space: nowrap; }
    .sig-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 22px;
        height: 22px;
        border-radius: 999px;
        font-weight: 700;
        font-size: 13px;
    }
    .sig-zero { background: #DCFCE7; color: #166534; }
    .sig-one { background: #FEE2E2; color: #991B1B; }
    .sig-na { background: #F3F4F6; color: #6B7280; }
    @media (max-width: 900px) {
        table.macro-scorecard { font-size: 12px; }
        .macro-scorecard th, .macro-scorecard td { padding: 6px 7px; }
    }
    </style>
    """

    colgroup = """
    <colgroup>
      <col style="width: 11%;">
      <col style="width: 26%;">
      <col style="width: 10%;">
      <col style="width: 11%;">
      <col style="width: 12%;">
      <col style="width: 16%;">
      <col style="width: 7%;">
      <col style="width: 7%;">
    </colgroup>
    """
    header = """
    <thead><tr>
      <th>维度(权重)</th>
      <th>指标名称</th>
      <th>最新数值</th>
      <th>变化</th>
      <th>较参考均值</th>
      <th>择时信号（防御）</th>
      <th>是否满足</th>
      <th>信号状态</th>
    </tr></thead>
    """

    body = ["<tbody>"]
    for dim, sub in data.groupby("dimension", sort=False):
        sub = sub.sort_values("display_order") if "display_order" in sub.columns else sub
        weight = float(sub["dimension_weight"].iloc[0])
        rowspan = len(sub)
        first = True
        for _, r in sub.iterrows():
            body.append("<tr>")
            if first:
                body.append(
                    f'<td class="dim-cell" rowspan="{rowspan}">{_esc(dim)}<span class="weight">({weight:.0%})</span></td>'
                )
                first = False
            body.append(f'<td class="indicator-cell">{_esc(r.get("indicator_name"))}</td>')
            body.append(f'<td class="num-cell">{_esc(r.get("latest_value_display"))}</td>')
            body.append(f'<td class="change-cell">{_esc(r.get("change_display"))}</td>')
            body.append(f'<td class="change-cell">{_esc(r.get("reference_change_display"))}</td>')
            body.append(f'<td class="rule-cell">{_esc(r.get("signal_text"))}</td>')
            body.append(f'<td class="trigger-cell">{_trigger_badge(r.get("signal_flag_display"))}</td>')
            body.append(f'<td class="state-cell">{_esc(r.get("signal_state"))}</td>')
            body.append("</tr>")
    body.append("</tbody>")
    table = css + '<div class="macro-scorecard-wrap"><table class="macro-scorecard">' + colgroup + header + "".join(body) + "</table></div>"
    st.markdown(table, unsafe_allow_html=True)


def detail_records_for_llm(detail: pd.DataFrame) -> list[dict]:
    cols = [
        "dimension", "indicator_name", "latest_value_display", "change_display",
        "reference_change_display", "signal_text", "signal_flag_display", "signal_state",
    ]
    return detail[cols].rename(columns={
        "dimension": "维度",
        "indicator_name": "指标",
        "latest_value_display": "最新值",
        "change_display": "变化",
        "reference_change_display": "较参考均值",
        "signal_text": "防御规则",
        "signal_flag_display": "是否触发",
        "signal_state": "状态",
    }).to_dict(orient="records")
