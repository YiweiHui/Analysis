"""File cache for DeepSeek reports, expiring at the next 08:00 Asia/Shanghai."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"
CACHE_DIR.mkdir(exist_ok=True)
TZ = ZoneInfo("Asia/Shanghai")


def next_8am(now: datetime | None = None) -> datetime:
    now = now.astimezone(TZ) if now else datetime.now(TZ)
    target = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if now >= target:
        target = target + timedelta(days=1)
    return target


def payload_hash(payload: dict) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _path(key: str) -> Path:
    safe = "".join(ch for ch in key if ch.isalnum() or ch in {"_", "-"})
    return CACHE_DIR / f"deepseek_{safe}.json"


def read_cache(key: str) -> tuple[str | None, str | None]:
    p = _path(key)
    if not p.exists():
        return None, None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(data["expires_at"])
        if datetime.now(TZ) >= expires_at:
            p.unlink(missing_ok=True)
            return None, None
        return data.get("text"), expires_at.strftime("%Y-%m-%d %H:%M")
    except Exception:
        p.unlink(missing_ok=True)
        return None, None


def write_cache(key: str, text: str) -> str:
    expires = next_8am()
    p = _path(key)
    p.write_text(json.dumps({"text": text, "expires_at": expires.isoformat()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return expires.strftime("%Y-%m-%d %H:%M")


def clear_cache(key: str) -> None:
    _path(key).unlink(missing_ok=True)
