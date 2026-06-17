"""DeepSeek explanation layer. It never participates in scoring; it only writes explanations."""

from __future__ import annotations

import json
from typing import Any
import requests


def get_secret(st_module: Any, key: str, default: str = "") -> str:
    try:
        return st_module.secrets.get(key, default)
    except Exception:
        return default


def build_context_payload(current_summary: dict, table_records: list[dict], backtest_summary: dict) -> dict:
    return {
        "current_summary": current_summary,
        "scorecard_table": table_records,
        "backtest_summary": backtest_summary,
        "note": "所有评分和回测结果由本地程序计算；DeepSeek 仅负责解释文字，不参与信号判断。",
    }


def call_deepseek(api_key: str, base_url: str, model: str, system_prompt: str, user_prompt: str, timeout: int = 60) -> str:
    if not api_key:
        raise ValueError("未配置 DeepSeek API Key。")
    base_url = (base_url or "https://api.deepseek.com").rstrip("/")
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 1200,
    }
    resp = requests.post(url, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=payload, timeout=timeout)
    if resp.status_code >= 400:
        raise RuntimeError(f"DeepSeek API 调用失败：HTTP {resp.status_code} - {resp.text[:500]}")
    data = resp.json()
    return data["choices"][0]["message"]["content"].strip()


def generate_report(api_key: str, base_url: str, model: str, context_payload: dict) -> str:
    system_prompt = (
        "你是信托FOF/资产配置投后分析助手。请只基于用户提供的结构化数据与回测结果写分析，"
        "不要编造外部事实，不要声称这是投资建议。语言应专业、克制、适合内部投后看板。"
    )
    user_prompt = (
        "请基于以下宏观评分卡与虚拟回测结果，生成一段150-250字中文分析。"
        "必须包含：当前状态、主要触发维度、回测提示、仓位含义、风险提示。"
        "说明：数据如标注为虚拟/演示，则不得用于正式投研判断。\n\n"
        + json.dumps(context_payload, ensure_ascii=False, indent=2, default=str)
    )
    return call_deepseek(api_key, base_url, model, system_prompt, user_prompt)


def chat_with_context(api_key: str, base_url: str, model: str, context_payload: dict, question: str) -> str:
    system_prompt = (
        "你是宏观评分卡数据问答助手。你只能基于已上传的评分卡和回测结果回答，"
        "如果问题超出数据范围，需明确说明无法由当前数据支持。"
    )
    user_prompt = (
        "以下是已上传的数据和回测结果。请回答用户问题。\n\n"
        + json.dumps(context_payload, ensure_ascii=False, indent=2, default=str)
        + "\n\n用户问题：" + question
    )
    return call_deepseek(api_key, base_url, model, system_prompt, user_prompt)
