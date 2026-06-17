"""Data loading utilities for the V2 macro scorecard."""

from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def load_indicator_config(path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path) if path else DATA_DIR / "indicator_config.csv"
    df = pd.read_csv(p)
    required = {
        "dimension", "dimension_weight", "indicator_id", "indicator_name",
        "unit", "digits", "rule_type", "direction", "window", "display_order"
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"indicator_config.csv 缺少字段: {sorted(missing)}")
    df["enabled"] = df.get("enabled", True)
    df = df[df["enabled"].astype(str).str.lower().isin(["true", "1", "yes"])]
    df["dimension_weight"] = df["dimension_weight"].astype(float)
    df["digits"] = df["digits"].astype(int)
    df["window"] = df["window"].astype(int)
    df["display_order"] = df["display_order"].astype(int)
    return df.sort_values("display_order").reset_index(drop=True)


def load_macro_history(path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path) if path else DATA_DIR / "macro_history.csv"
    df = pd.read_csv(p)
    required = {"date", "indicator_id", "value"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"macro_history.csv 缺少字段: {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna(subset=["date", "indicator_id", "value"]).sort_values(["indicator_id", "date"]).reset_index(drop=True)


def load_asset_returns(path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path) if path else DATA_DIR / "asset_returns.csv"
    df = pd.read_csv(p)
    required = {"date", "asset_id", "asset_name", "return"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"asset_returns.csv 缺少字段: {sorted(missing)}")
    df["date"] = pd.to_datetime(df["date"])
    df["return"] = pd.to_numeric(df["return"], errors="coerce")
    return df.dropna(subset=["date", "asset_id", "return"]).sort_values(["asset_id", "date"]).reset_index(drop=True)
