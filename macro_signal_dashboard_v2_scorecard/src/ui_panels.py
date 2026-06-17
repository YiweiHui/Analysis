"""Reusable Streamlit panels for the V2 dashboard."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def inject_global_css() -> None:
    st.markdown(
        """
        <style>
        .stButton > button[kind="primary"] {
            background-color: #111827 !important;
            color: #ffffff !important;
            border: 1px solid #111827 !important;
        }
        .stButton > button[kind="primary"]:hover {
            background-color: #000000 !important;
            color: #ffffff !important;
            border: 1px solid #000000 !important;
        }
        section[data-testid="stSidebar"] { background-color: #F8FAFC; }
        .small-note { color: #6B7280; font-size: 12px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(overall_score: float, trigger_count: int, valid_count: int, label: str) -> None:
    c1, c2, c3 = st.columns(3)
    c1.metric("总防御分数", f"{overall_score:.1%}")
    c2.metric("触发防御信号", f"{trigger_count}/{valid_count}")
    c3.metric("当前解释", label)


def render_dimension_score(dimension_score: pd.DataFrame) -> None:
    if dimension_score.empty:
        st.info("暂无维度得分。")
        return
    display = dimension_score.copy()
    display["dimension_score_pct"] = display["dimension_score"] * 100
    st.subheader("维度防御分数")
    st.bar_chart(display.set_index("dimension")[["dimension_score_pct"]])
    table = display[["dimension", "dimension_weight", "indicator_count", "valid_count", "trigger_count", "dimension_score", "weighted_score"]].rename(
        columns={
            "dimension": "一级维度",
            "dimension_weight": "维度权重",
            "indicator_count": "二级指标数",
            "valid_count": "有效指标数",
            "trigger_count": "触发数",
            "dimension_score": "维度防御比例",
            "weighted_score": "加权贡献",
        }
    )
    st.dataframe(
        table.style.format({"维度权重": "{:.1%}", "维度防御比例": "{:.1%}", "加权贡献": "{:.1%}"}),
        use_container_width=True,
        hide_index=True,
    )


def render_signal_hierarchy(detail: pd.DataFrame, dimension_score: pd.DataFrame | None = None) -> None:
    score_map = {}
    if dimension_score is not None and not dimension_score.empty:
        score_map = {str(row.dimension): row for row in dimension_score.itertuples(index=False)}
    for dim, sub in detail.groupby("dimension", sort=False):
        sub = sub.sort_values("display_order") if "display_order" in sub.columns else sub
        weight = float(sub["dimension_weight"].iloc[0])
        score_row = score_map.get(str(dim))
        if score_row is not None:
            valid_count = int(score_row.valid_count)
            trigger_count = int(score_row.trigger_count)
            dimension_score_value = float(score_row.dimension_score)
            weighted_score = float(score_row.weighted_score)
        else:
            valid = sub["signal_flag"].dropna()
            valid_count = int(len(valid))
            trigger_count = int(valid.sum()) if valid_count else 0
            dimension_score_value = trigger_count / valid_count if valid_count else 0.0
            weighted_score = dimension_score_value * weight
        title = f"{dim}｜维度权重 {weight:.0%}｜触发 {trigger_count}/{valid_count}｜维度防御比例 {dimension_score_value:.1%}｜加权贡献 {weighted_score:.1%}"
        with st.expander(title, expanded=False):
            table = sub[["indicator_name", "latest_value_display", "change_display", "reference_change_display", "signal_text", "signal_flag_display", "signal_state", "data_status"]].rename(
                columns={
                    "indicator_name": "二级指标",
                    "latest_value_display": "最新值",
                    "change_display": "变化",
                    "reference_change_display": "较参考均值",
                    "signal_text": "择时信号（防御）",
                    "signal_flag_display": "是否触发",
                    "signal_state": "状态",
                    "data_status": "数据状态",
                }
            )
            st.dataframe(table, use_container_width=True, hide_index=True)


def render_backtest_summary(forward_stats: pd.DataFrame, strategy_curve: pd.DataFrame, strategy_metrics: pd.DataFrame, current_bucket: str) -> None:
    st.markdown(f"当前防御分数对应历史区间：**{current_bucket}**")
    focus = forward_stats[(forward_stats["观察窗口"] == "未来1个月") & (forward_stats["防御分数区间"] == current_bucket)]
    if not focus.empty:
        st.dataframe(
            focus[["资产名称", "样本数", "未来收益均值", "胜率", "最差表现", "最好表现"]]
            .style.format({"未来收益均值": "{:.2%}", "胜率": "{:.1%}", "最差表现": "{:.2%}", "最好表现": "{:.2%}"}),
            use_container_width=True,
            hide_index=True,
        )
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("动态策略 vs 固定基准净值")
        if not strategy_curve.empty:
            st.line_chart(strategy_curve.set_index("date")[["动态策略净值", "固定基准净值"]])
    with c2:
        st.subheader("策略回测指标")
        if not strategy_metrics.empty:
            st.dataframe(
                strategy_metrics.style.format({
                    "累计收益": "{:.2%}", "年化收益": "{:.2%}", "年化波动": "{:.2%}",
                    "最大回撤": "{:.2%}", "夏普比率": "{:.2f}", "卡玛比率": "{:.2f}", "月度胜率": "{:.1%}",
                }),
                use_container_width=True,
                hide_index=True,
            )


def render_indicator_trend(series_df: pd.DataFrame, detail: pd.DataFrame) -> None:
    if detail.empty:
        return
    options = detail[["indicator_id", "indicator_name"]].drop_duplicates()
    label_map = {f"{row.indicator_name} ({row.indicator_id})": row.indicator_id for row in options.itertuples()}
    selected_label = st.selectbox("选择指标查看历史趋势", list(label_map.keys()))
    selected_id = label_map[selected_label]
    hist = series_df[series_df["indicator_id"].astype(str) == str(selected_id)].copy()
    if hist.empty:
        st.info("该指标暂无历史数据。")
        return
    hist["date"] = pd.to_datetime(hist["date"])
    st.line_chart(hist.sort_values("date").set_index("date")[["value"]])
