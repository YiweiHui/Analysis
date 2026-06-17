# 部署说明

## GitHub 上传

仓库根目录应直接包含：

- `app.py`
- `requirements.txt`
- `src/`
- `data/`
- `.streamlit/`

不要上传：

- `.streamlit/secrets.toml`
- `__pycache__/`
- `*.pyc`

## Streamlit Cloud

创建 App 时填写：

- Branch: `main`
- Main file path: `app.py`

## Secrets

在 Streamlit Cloud 的 App settings → Secrets 中填写：

```toml
DEEPSEEK_API_KEY = "你的 DeepSeek API Key"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
```

DeepSeek 不会自动调用；只有点击“生成分析”或“发送问题”才会调用。
