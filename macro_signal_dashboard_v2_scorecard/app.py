from __future__ import annotations

import json
import pandas as pd
import streamlit as st

from src.backtest_engine import compute_forward_stats, compute_strategy_backtest, selected_bucket_stats
from src.cache_manager import clear_cache, payload_hash, read_cache, write_cache
from src.data_loader import load_asset_returns, load_indicator_config, load_macro_history
from src.llm_layer import build_context_payload, chat_with_context, generate_report, get_secret
from src.scoring_engine import compute_historical_scores, compute_score
from src.ui_panels import (
    inject_global_css,
    render_backtest_summary,
    render_dimension_score,
    render_indicator_trend,
    render_kpis,
    render_signal_hierarchy,
)
from src.ui_scorecard import detail_records_for_llm, render_macro_scorecard

st.set_page_config(page_title="宏观指标信号", layout="wide")
inject_global_css()


@st.cache_data(show_spinner=False)
def load_all_data():
    config = load_indicator_config()
    macro_history = load_macro_history()
    asset_returns = load_asset_returns()
    return config, macro_history, asset_returns


@st.cache_data(show_spinner=False)
def compute_all(config: pd.DataFrame, macro_history: pd.DataFrame, asset_returns: pd.DataFrame):
    current = compute_score(config, macro_history)
    score_history = compute_historical_scores(config, macro_history)
    forward_stats = compute_forward_stats(score_history, asset_returns)
    strategy_curve, strategy_metrics = compute_strategy_backtest(score_history, asset_returns)
    return current, score_history, forward_stats, strategy_curve, strategy_metrics


def build_backtest_brief(forward_stats: pd.DataFrame, current_bucket: str) -> dict:
    hs300 = selected_bucket_stats(forward_stats, current_bucket, "沪深300")
    bond = selected_bucket_stats(forward_stats, current_bucket, "中债综合财富")
    return {
        "current_bucket": current_bucket,
        "hs300_1m_mean": hs300.get("未来收益均值"),
        "hs300_1m_win_rate": hs300.get("胜率"),
        "bond_1m_mean": bond.get("未来收益均值"),
        "bond_1m_win_rate": bond.get("胜率"),
        "note": "回测数据为演示/虚拟数据，仅用于验证流程。",
    }


def build_context(current, forward_stats: pd.DataFrame) -> tuple[dict, dict]:
    latest_date = current.latest_date.strftime("%Y-%m-%d") if current.latest_date is not None else "—"
    current_summary = {
        "latest_data_date": latest_date,
        "overall_score": f"{current.overall_score:.1%}",
        "trigger_count": current.trigger_count,
        "valid_count": current.valid_count,
        "bucket": current.bucket,
        "label": current.label,
        "local_judgement": current.local_judgement,
        "dimension_scores": current.dimension_score.to_dict(orient="records"),
    }
    backtest_brief = build_backtest_brief(forward_stats, current.bucket)
    context = build_context_payload(current_summary, detail_records_for_llm(current.detail), backtest_brief)
    return current_summary, context


def get_deepseek_settings() -> tuple[str, str, str]:
    api_key = get_secret(st, "DEEPSEEK_API_KEY", "")
    base_url = get_secret(st, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = get_secret(st, "DEEPSEEK_MODEL", "deepseek-chat") or "deepseek-chat"
    return api_key, base_url, model


def deepseek_dialog(context_payload: dict, current_summary: dict, cache_key: str) -> None:
    api_key, base_url, model = get_deepseek_settings()
    cached_text, expires_text = read_cache(cache_key)

    st.markdown("### DeepSeek 分析助手")
    st.caption("数据和回测结果已作为上下文准备好；点击按钮后才会调用 DeepSeek。")

    if not api_key:
        st.warning("尚未在 Streamlit Secrets 中配置 DEEPSEEK_API_KEY。")

    if cached_text:
        st.success("已生成分析报告。")
        st.markdown(cached_text)
        latest_data_date = current_summary.get("latest_data_date", "当前最新数据日")
        st.caption(f"本报告基于 {latest_data_date} 数据生成，对该数据日负责；报告留存至 {expires_text}。")
        if st.button("清除报告缓存", type="secondary"):
            clear_cache(cache_key)
            st.rerun()
    else:
        if st.button("生成分析", type="primary", use_container_width=True):
            try:
                with st.spinner("正在生成 DeepSeek 分析..."):
                    text = generate_report(api_key, base_url, model, context_payload)
                    expires_at = write_cache(cache_key, text)
                st.success("生成成功。")
                st.markdown(text)
                latest_data_date = current_summary.get("latest_data_date", "当前最新数据日")
                st.caption(f"本报告基于 {latest_data_date} 数据生成，对该数据日负责；报告留存至 {expires_at}。")
                st.rerun()
            except Exception as exc:
                st.error(f"DeepSeek API 调用失败：{exc}")

    st.divider()
    st.markdown("#### 与 DeepSeek 对话【数据和回测结果已上传】")
    question = st.text_area("输入问题", placeholder="例如：本轮防御信号主要由哪些维度驱动？", height=100)
    if st.button("发送问题", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("请先输入问题。")
        else:
            try:
                with st.spinner("DeepSeek 正在回答..."):
                    answer = chat_with_context(api_key, base_url, model, context_payload, question.strip())
                st.markdown(answer)
            except Exception as exc:
                st.error(f"DeepSeek API 调用失败：{exc}")


def open_deepseek_modal(context_payload: dict, current_summary: dict, cache_key: str) -> None:
    if hasattr(st, "dialog"):
        @st.dialog("DeepSeek 分析助手", width="large")
        def _dialog():
            deepseek_dialog(context_payload, current_summary, cache_key)
        _dialog()
    else:
        with st.expander("DeepSeek 分析助手", expanded=True):
            deepseek_dialog(context_payload, current_summary, cache_key)


def main() -> None:
    config, macro_history, asset_returns = load_all_data()
    current, score_history, forward_stats, strategy_curve, strategy_metrics = compute_all(config, macro_history, asset_returns)
    current_summary, context_payload = build_context(current, forward_stats)
    cache_key = payload_hash({"context": context_payload, "version": "v2-scorecard-manual-deepseek"})

    with st.sidebar:
        st.subheader("数据源状态")
        st.info("当前模式：GitHub 仓库内演示/虚拟数据")
        st.caption("宏观历史数据格式：date, indicator_id, value。资产收益率格式：date, asset_id, asset_name, return。")
        st.divider()
        st.subheader("DeepSeek")
        st.caption("手动触发，不会因打开页面自动调用。")
        _, expires = read_cache(cache_key)
        if expires:
            st.caption(f"当前报告留存至：{expires}")

    st.title("宏观指标信号")
    st.caption("V2评分卡系统：本地评分模型 + 虚拟历史回测 + 手动 DeepSeek 解释层。")
    st.warning("当前内置数据均为演示/虚拟数据，只用于验证方法、部署和展示流程，不代表真实宏观数据库，也不应用于正式投研判断。")

    tabs = st.tabs(["当前信号", "回测模型", "逻辑解释"])

    with tabs[0]:
        render_kpis(current.overall_score, current.trigger_count, current.valid_count, current.label)
        st.markdown("#### 自动生成判断")
        st.info(current.local_judgement)
        st.caption("由回测结果和本地语言模板自动生成的判断，非 AI 大模型判断。")

        if st.button("DeepSeek 分析助手", type="primary"):
            open_deepseek_modal(context_payload, current_summary, cache_key)

        st.subheader("核心指标明细")
        render_macro_scorecard(current.detail)

        with st.expander("查看分级明细（含权重与维度贡献）", expanded=False):
            render_signal_hierarchy(current.detail, current.dimension_score)

        render_dimension_score(current.dimension_score)

        st.subheader("指标历史趋势")
        render_indicator_trend(macro_history, current.detail)

    with tabs[1]:
        st.subheader("回测模型结果")
        st.caption("当前为虚拟数据回测，仅用于验证信号 → 回测 → 解释的完整链路。")
        render_backtest_summary(forward_stats, strategy_curve, strategy_metrics, current.bucket)

        with st.expander("查看全部区间资产表现", expanded=False):
            if not forward_stats.empty:
                st.dataframe(
                    forward_stats.style.format({
                        "未来收益均值": "{:.2%}",
                        "未来收益中位数": "{:.2%}",
                        "胜率": "{:.1%}",
                        "最差表现": "{:.2%}",
                        "最好表现": "{:.2%}",
                    }),
                    use_container_width=True,
                    hide_index=True,
                )

    with tabs[2]:
        st.subheader("逻辑解释")
        st.markdown(
            """
            **1. 信号计算层**  
            每个指标按照配置表中的规则计算是否触发防御信号。例如低于移动平均、高于移动平均、环比下降或环比上升。

            **2. 维度评分层**  
            每个一级维度先计算触发比例，再乘以维度权重，得到维度加权贡献。

            **3. 总分解释层**  
            总防御分数 = 各维度加权贡献之和。当前解释标签由本地规则映射生成：0%–25% 偏进攻，25%–50% 中性观察，50%–75% 中性偏防御，75%–100% 高防御。

            **4. 回测层**  
            回测模型用历史评分区间观察未来 1/3/6 个月资产表现，并比较动态策略与固定基准。

            **5. DeepSeek 解释层**  
            DeepSeek 仅在用户手动点击时调用，只负责生成文字解释，不参与信号计算、分数计算或回测计算。
            """
        )
        st.json(context_payload)


if __name__ == "__main__":
    main()
