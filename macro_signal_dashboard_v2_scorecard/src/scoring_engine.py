"""Macro scorecard signal and scoring engine."""

from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
import numpy as np


@dataclass
class ScoreResult:
    detail: pd.DataFrame
    dimension_score: pd.DataFrame
    overall_score: float
    trigger_count: int
    valid_count: int
    latest_date: pd.Timestamp | None
    bucket: str
    label: str
    local_judgement: str


def format_value(value: float | int | None, unit: str = "", digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "—"
    unit = "" if pd.isna(unit) else str(unit).strip()
    if unit == "%":
        return f"{float(value):.{digits}f}%"
    if unit.lower() in {"pp", "pctpt", "百分点"}:
        return f"{float(value):.{digits}f}pp"
    if unit:
        return f"{float(value):.{digits}f}{unit}"
    return f"{float(value):.{digits}f}"


def format_change(latest: float | None, base: float | None, unit: str = "", digits: int = 2) -> str:
    if latest is None or base is None or pd.isna(latest) or pd.isna(base):
        return "—"
    diff = float(latest) - float(base)
    if abs(diff) < 1e-12:
        return "持平"
    arrow = "↑" if diff > 0 else "↓"
    # For all percent/pp indicators, changes are shown in percentage points only.
    unit = "" if pd.isna(unit) else str(unit).strip()
    change_unit = "pp" if unit in {"%", "pp", "pctpt", "百分点"} else unit
    abs_text = f"{abs(diff):.{digits}f}{change_unit}" if change_unit else f"{abs(diff):.{digits}f}"
    return f"{arrow} {abs_text}"


def _reference_value(series: pd.Series, current_idx: int, rule_type: str, window: int) -> float | None:
    if current_idx <= 0:
        return None
    if rule_type == "moving_average":
        start = max(0, current_idx - max(1, int(window)))
        ref = series.iloc[start:current_idx].mean()
        return float(ref) if pd.notna(ref) else None
    return float(series.iloc[current_idx - 1])


def _previous_value(series: pd.Series, current_idx: int) -> float | None:
    if current_idx <= 0:
        return None
    val = series.iloc[current_idx - 1]
    return float(val) if pd.notna(val) else None


def _signal_flag(latest: float | None, reference: float | None, rule_type: str, direction: str) -> float | None:
    if latest is None or reference is None or pd.isna(latest) or pd.isna(reference):
        return np.nan
    latest = float(latest)
    reference = float(reference)
    if direction == "below":
        return 1.0 if latest < reference else 0.0
    if direction == "above":
        return 1.0 if latest > reference else 0.0
    if direction == "down":
        return 1.0 if latest < reference else 0.0
    if direction == "up":
        return 1.0 if latest > reference else 0.0
    return np.nan


def _signal_text(rule_type: str, direction: str) -> str:
    if rule_type == "moving_average" and direction == "below":
        return "低于移动平均"
    if rule_type == "moving_average" and direction == "above":
        return "高于移动平均"
    if rule_type == "mom" and direction == "down":
        return "环比下降"
    if rule_type == "mom" and direction == "up":
        return "环比上升"
    return "规则未定义"


def score_bucket(score: float) -> str:
    if score < 0.25:
        return "0%–25%"
    if score < 0.50:
        return "25%–50%"
    if score < 0.75:
        return "50%–75%"
    return "75%–100%"


def score_label(score: float) -> str:
    if score < 0.25:
        return "偏进攻"
    if score < 0.50:
        return "中性观察"
    if score < 0.75:
        return "中性偏防御"
    return "高防御"


def compute_score(config: pd.DataFrame, history: pd.DataFrame, as_of: str | pd.Timestamp | None = None) -> ScoreResult:
    if as_of is None:
        as_of_ts = pd.to_datetime(history["date"].max())
    else:
        as_of_ts = pd.to_datetime(as_of)

    hist = history[history["date"] <= as_of_ts].copy()
    detail_rows: list[dict] = []
    latest_dates: list[pd.Timestamp] = []

    for cfg in config.itertuples(index=False):
        h = hist[hist["indicator_id"].astype(str) == str(cfg.indicator_id)].sort_values("date")
        if h.empty:
            detail_rows.append({
                "dimension": cfg.dimension,
                "dimension_weight": float(cfg.dimension_weight),
                "indicator_id": cfg.indicator_id,
                "indicator_name": cfg.indicator_name,
                "latest_value": np.nan,
                "previous_value": np.nan,
                "reference_value": np.nan,
                "signal_flag": np.nan,
                "data_status": "缺失",
                "latest_date": pd.NaT,
                "unit": cfg.unit,
                "digits": int(cfg.digits),
                "display_order": int(cfg.display_order),
                "rule_type": cfg.rule_type,
                "direction": cfg.direction,
                "window": int(cfg.window),
            })
            continue

        series = h["value"].reset_index(drop=True)
        current_idx = len(series) - 1
        latest = float(series.iloc[current_idx])
        previous = _previous_value(series, current_idx)
        reference = _reference_value(series, current_idx, str(cfg.rule_type), int(cfg.window))
        flag = _signal_flag(latest, reference, str(cfg.rule_type), str(cfg.direction))
        latest_date = pd.to_datetime(h["date"].iloc[-1])
        latest_dates.append(latest_date)

        detail_rows.append({
            "dimension": cfg.dimension,
            "dimension_weight": float(cfg.dimension_weight),
            "indicator_id": cfg.indicator_id,
            "indicator_name": cfg.indicator_name,
            "latest_value": latest,
            "previous_value": previous,
            "reference_value": reference,
            "latest_value_display": format_value(latest, cfg.unit, int(cfg.digits)),
            "change_display": format_change(latest, previous, cfg.unit, int(cfg.digits)),
            "reference_change_display": format_change(latest, reference, cfg.unit, int(cfg.digits)),
            "reference_value_display": format_value(reference, cfg.unit, int(cfg.digits)),
            "signal_text": _signal_text(str(cfg.rule_type), str(cfg.direction)),
            "signal_flag": flag,
            "signal_flag_display": "—" if pd.isna(flag) else str(int(flag)),
            "signal_state": "触发防御" if flag == 1 else ("未触发" if flag == 0 else "缺失"),
            "data_status": "正常",
            "latest_date": latest_date,
            "unit": cfg.unit,
            "digits": int(cfg.digits),
            "display_order": int(cfg.display_order),
            "rule_type": cfg.rule_type,
            "direction": cfg.direction,
            "window": int(cfg.window),
        })

    detail = pd.DataFrame(detail_rows).sort_values("display_order").reset_index(drop=True)
    dim_rows = []
    for dim, sub in detail.groupby("dimension", sort=False):
        valid = sub["signal_flag"].dropna()
        valid_count = int(len(valid))
        trigger_count = int(valid.sum()) if valid_count else 0
        dim_weight = float(sub["dimension_weight"].iloc[0])
        dim_score = trigger_count / valid_count if valid_count else 0.0
        dim_rows.append({
            "dimension": dim,
            "dimension_weight": dim_weight,
            "indicator_count": int(len(sub)),
            "valid_count": valid_count,
            "trigger_count": trigger_count,
            "dimension_score": dim_score,
            "weighted_score": dim_score * dim_weight,
        })

    dimension_score = pd.DataFrame(dim_rows)
    overall_score = float(dimension_score["weighted_score"].sum()) if not dimension_score.empty else 0.0
    valid_all = detail["signal_flag"].dropna()
    trigger_count = int(valid_all.sum()) if len(valid_all) else 0
    valid_count = int(len(valid_all))
    latest_date = max(latest_dates) if latest_dates else None
    bucket = score_bucket(overall_score)
    label = score_label(overall_score)
    local_judgement = (
        f"{label}。当前共有 {trigger_count}/{valid_count} 个有效指标触发防御信号，"
        f"加权总防御分数为 {overall_score:.1%}，处于 {bucket} 区间。"
        f"该判断由回测结果和本地语言模板自动生成，非 AI 大模型判断。"
    )

    return ScoreResult(
        detail=detail,
        dimension_score=dimension_score,
        overall_score=overall_score,
        trigger_count=trigger_count,
        valid_count=valid_count,
        latest_date=latest_date,
        bucket=bucket,
        label=label,
        local_judgement=local_judgement,
    )


def compute_historical_scores(config: pd.DataFrame, history: pd.DataFrame, min_periods: int = 12) -> pd.DataFrame:
    dates = sorted(pd.to_datetime(history["date"].unique()))
    rows = []
    if len(dates) <= min_periods:
        return pd.DataFrame()
    for dt in dates[min_periods:]:
        res = compute_score(config, history, as_of=dt)
        rows.append({
            "date": dt,
            "overall_score": res.overall_score,
            "trigger_count": res.trigger_count,
            "valid_count": res.valid_count,
            "bucket": res.bucket,
            "label": res.label,
        })
    return pd.DataFrame(rows)
