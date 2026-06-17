"""Backtest utilities for the V2 macro scorecard."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _compound_return(x: pd.Series) -> float:
    if x.empty:
        return np.nan
    return float((1 + x).prod() - 1)


def compute_forward_stats(score_history: pd.DataFrame, asset_returns: pd.DataFrame) -> pd.DataFrame:
    if score_history.empty or asset_returns.empty:
        return pd.DataFrame()

    score = score_history[["date", "bucket"]].copy()
    score["date"] = pd.to_datetime(score["date"])
    asset = asset_returns.copy()
    asset["date"] = pd.to_datetime(asset["date"])
    rows = []

    for horizon in [1, 3, 6]:
        for (asset_id, asset_name), adf in asset.groupby(["asset_id", "asset_name"]):
            adf = adf.sort_values("date").reset_index(drop=True)
            future_rows = []
            for i, row in adf.iterrows():
                fwd = adf.loc[i + 1:i + horizon, "return"]
                if len(fwd) < horizon:
                    future_ret = np.nan
                else:
                    future_ret = _compound_return(fwd)
                future_rows.append({"date": row["date"], "future_return": future_ret})
            fdf = pd.DataFrame(future_rows)
            merged = score.merge(fdf, on="date", how="inner")
            for bucket, bdf in merged.groupby("bucket"):
                vals = bdf["future_return"].dropna()
                if vals.empty:
                    continue
                rows.append({
                    "防御分数区间": bucket,
                    "观察窗口": f"未来{horizon}个月",
                    "资产ID": asset_id,
                    "资产名称": asset_name,
                    "样本数": int(len(vals)),
                    "未来收益均值": float(vals.mean()),
                    "未来收益中位数": float(vals.median()),
                    "胜率": float((vals > 0).mean()),
                    "最差表现": float(vals.min()),
                    "最好表现": float(vals.max()),
                })

    order = {"0%–25%": 0, "25%–50%": 1, "50%–75%": 2, "75%–100%": 3}
    out = pd.DataFrame(rows)
    if not out.empty:
        out["_order"] = out["防御分数区间"].map(order).fillna(99)
        out = out.sort_values(["观察窗口", "_order", "资产ID"]).drop(columns="_order").reset_index(drop=True)
    return out

def _weights_by_score(score: float) -> dict[str, float]:
    # Dynamic allocation used only for demo/backtest illustration.
    if score < 0.25:
        return {"hs300": 0.45, "zz500": 0.20, "cbond": 0.25, "cash": 0.05, "div_lowvol": 0.05}
    if score < 0.50:
        return {"hs300": 0.38, "zz500": 0.17, "cbond": 0.33, "cash": 0.07, "div_lowvol": 0.05}
    if score < 0.75:
        return {"hs300": 0.28, "zz500": 0.12, "cbond": 0.45, "cash": 0.10, "div_lowvol": 0.05}
    return {"hs300": 0.18, "zz500": 0.07, "cbond": 0.55, "cash": 0.15, "div_lowvol": 0.05}


def compute_strategy_backtest(score_history: pd.DataFrame, asset_returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if score_history.empty or asset_returns.empty:
        return pd.DataFrame(), pd.DataFrame()
    ret = asset_returns.pivot_table(index="date", columns="asset_id", values="return", aggfunc="first").sort_index()
    score = score_history.set_index("date")[["overall_score"]].sort_index()
    df = score.join(ret, how="inner").dropna()
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    rows = []
    for dt, row in df.iterrows():
        w = _weights_by_score(float(row["overall_score"]))
        dyn = sum(w.get(a, 0.0) * float(row.get(a, 0.0)) for a in w)
        fixed = 0.60 * float(row.get("hs300", 0.0)) + 0.35 * float(row.get("cbond", 0.0)) + 0.05 * float(row.get("cash", 0.0))
        rows.append({"date": dt, "动态策略收益": dyn, "固定基准收益": fixed})
    curve = pd.DataFrame(rows).sort_values("date")
    curve["动态策略净值"] = (1 + curve["动态策略收益"]).cumprod()
    curve["固定基准净值"] = (1 + curve["固定基准收益"]).cumprod()
    metrics = _metrics(curve)
    return curve, metrics


def _metrics(curve: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, ret_col, nav_col in [
        ("动态策略", "动态策略收益", "动态策略净值"),
        ("固定基准", "固定基准收益", "固定基准净值"),
    ]:
        r = curve[ret_col].dropna()
        nav = curve[nav_col].dropna()
        if r.empty or nav.empty:
            continue
        ann_ret = (nav.iloc[-1] / nav.iloc[0]) ** (12 / max(len(nav), 1)) - 1
        ann_vol = r.std(ddof=0) * np.sqrt(12)
        dd = nav / nav.cummax() - 1
        max_dd = float(dd.min())
        sharpe = ann_ret / ann_vol if ann_vol > 1e-12 else np.nan
        calmar = ann_ret / abs(max_dd) if abs(max_dd) > 1e-12 else np.nan
        rows.append({
            "策略": name,
            "累计收益": float(nav.iloc[-1] - 1),
            "年化收益": float(ann_ret),
            "年化波动": float(ann_vol),
            "最大回撤": max_dd,
            "夏普比率": float(sharpe) if pd.notna(sharpe) else np.nan,
            "卡玛比率": float(calmar) if pd.notna(calmar) else np.nan,
            "月度胜率": float((r > 0).mean()),
        })
    return pd.DataFrame(rows)


def selected_bucket_stats(forward_stats: pd.DataFrame, bucket: str, asset_name: str = "沪深300") -> dict:
    if forward_stats.empty:
        return {}
    focus = forward_stats[
        (forward_stats["防御分数区间"] == bucket)
        & (forward_stats["观察窗口"] == "未来1个月")
        & (forward_stats["资产名称"] == asset_name)
    ]
    if focus.empty:
        return {}
    return focus.iloc[0].to_dict()
