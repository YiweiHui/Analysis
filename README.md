# 宏观指标信号 V2 评分卡系统

这是一个可部署到 Streamlit Cloud 的 V2 评分卡看板工程。

## 功能

- 宏观指标本地规则评分
- HTML 分层评分卡表格
- 虚拟历史回测模型
- DeepSeek 手动弹窗分析
- DeepSeek 报告缓存至下一次 UTC+8 早上 8 点
- GitHub / Streamlit Cloud 可直接部署

## 本地运行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud Secrets

不要把 API Key 写进代码或 GitHub。请在 Streamlit Cloud → App settings → Secrets 中配置：

```toml
DEEPSEEK_API_KEY = "你的 DeepSeek API Key"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
```

## 数据说明

当前 `data/` 内数据均为演示/虚拟数据，仅用于验证方法和部署流程。

- `indicator_config.csv`：指标配置和信号规则
- `macro_history.csv`：宏观指标历史数据
- `asset_returns.csv`：资产月度收益率数据

## 注意

DeepSeek 只作为解释层，不参与信号计算、分数计算或回测计算。
