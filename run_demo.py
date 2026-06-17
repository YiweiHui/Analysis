from src.data_loader import load_asset_returns, load_indicator_config, load_macro_history
from src.scoring_engine import compute_score, compute_historical_scores
from src.backtest_engine import compute_forward_stats, compute_strategy_backtest

config = load_indicator_config()
history = load_macro_history()
assets = load_asset_returns()
current = compute_score(config, history)
score_hist = compute_historical_scores(config, history)
forward_stats = compute_forward_stats(score_hist, assets)
curve, metrics = compute_strategy_backtest(score_hist, assets)

print("当前状态:", current.label)
print("总防御分数:", f"{current.overall_score:.1%}")
print("触发:", f"{current.trigger_count}/{current.valid_count}")
print(current.detail[["dimension", "indicator_name", "latest_value_display", "change_display", "reference_change_display", "signal_text", "signal_flag_display", "signal_state"]])
print("\n回测摘要:")
print(forward_stats.head(10))
print("\n策略指标:")
print(metrics)
