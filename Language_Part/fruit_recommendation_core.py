"""
Fruit recommendation helpers.

This module turns a user's request into one fruit recommendation from the
fixed six-item menu, generates a teasing reply, and writes a compact JSON
record with the selected sequence number.
"""

from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from . import config
except ImportError:
    import config


FRUIT_MENU = (
    {
        "seq": 1,
        "name": "草莓",
        "keywords": ("草莓", "草莓味", "甜", "甜一点", "可爱", "浪漫", "少女心", "小清新"),
        "teases": (
            "别嘴硬了，你就是想来点甜的。",
            "你的需求很直白，甜味已经写在脸上了。",
            "看得出来你今天更适合一点温柔的甜。",
        ),
    },
    {
        "seq": 2,
        "name": "蓝莓",
        "keywords": ("蓝莓", "护眼", "熬夜", "加班", "学习", "抗氧化", "健康", "认真"),
        "teases": (
            "这么会过日子，连水果都开始走养生路线了。",
            "一看就是熬夜选手，先给你安排点蓝莓压压场。",
            "你这需求很会算账，蓝莓最懂这种精打细算。",
        ),
    },
    {
        "seq": 3,
        "name": "香蕉",
        "keywords": ("香蕉", "能量", "运动", "跑步", "早上", "便携", "充饥", "顶饿"),
        "teases": (
            "你这诉求很讲效率，香蕉这种省事选手正合适。",
            "别挑了，先把能量补上再说。",
            "看起来你今天需要的是快、准、稳的补给。",
        ),
    },
    {
        "seq": 4,
        "name": "杨桃",
        "keywords": ("杨桃", "清爽", "新鲜", "夏天", "换口味", "特别", "创意", "惊喜"),
        "teases": (
            "你明显不想走寻常路，那就来点杨桃。",
            "今天的你有点想换花样，杨桃刚好够特别。",
            "这口味一看就不爱平庸，安排。",
        ),
    },
    {
        "seq": 5,
        "name": "圣女果",
        "keywords": ("圣女果", "小番茄", "番茄", "轻食", "减脂", "零食", "追剧", "清单"),
        "teases": (
            "你这要求很克制，圣女果这种小而精的最适合。",
            "一听就是想随手吃两口，又不想太有负担。",
            "别看它小，整起气氛来一点不含糊。",
        ),
    },
    {
        "seq": 6,
        "name": "猕猴桃",
        "keywords": ("猕猴桃", "奇异果", "维c", "维生素", "免疫", "酸甜", "平衡", "清新"),
        "teases": (
            "你这个需求像猕猴桃，酸甜都要，谁也不偏。",
            "看得出来你想要一点平衡感，猕猴桃很懂。",
            "嘴上说随便，实际上想要的是刚刚好。",
        ),
    },
)

_FRUIT_BY_SEQ = {item["seq"]: item for item in FRUIT_MENU}
_NAME_TO_SEQ = {item["name"]: item["seq"] for item in FRUIT_MENU}
_NORMALIZE_RE = re.compile(r"[，。！？、,.!?:;；：\s]+")
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.S)
_LLM_INSUFFICIENT_BALANCE_MARKERS = (
    "insufficient balance",
    "insufficient_balance",
    "insufficient credits",
    "quota exceeded",
    "billing hard limit",
)


@dataclass(frozen=True)
class FruitRecommendation:
    seq: int
    name: str
    tease: str
    voice_text: str
    request_text: str
    source: str
    model: str = ""
    reason: str = ""


def _normalize_text(text: str) -> str:
    return _NORMALIZE_RE.sub("", (text or "").strip()).lower()


def _pick_tease(fruit_item: dict) -> str:
    teases = fruit_item.get("teases") or ()
    if isinstance(teases, (list, tuple)) and teases:
        return str(random.choice(teases)).strip()
    return f"你这需求有点有趣，那就选{fruit_item['name']}。"


def _fruit_item_for_seq(seq: int) -> dict:
    return _FRUIT_BY_SEQ.get(seq, _FRUIT_BY_SEQ[1])


def _score_fruit(request_text: str, fruit_item: dict) -> int:
    request_norm = _normalize_text(request_text)
    if not request_norm:
        return 0

    score = 0
    name = str(fruit_item["name"])
    if name and _normalize_text(name) in request_norm:
        score += 100

    for keyword in fruit_item.get("keywords", ()):
        keyword_norm = _normalize_text(str(keyword))
        if not keyword_norm:
            continue
        if keyword_norm in request_norm:
            score += 20 + len(keyword_norm)
        else:
            overlap = len(set(keyword_norm) & set(request_norm))
            score += overlap

    # Small deterministic bias so ties are stable.
    score += max(0, 10 - int(fruit_item["seq"]))
    return score


def _best_local_recommendation(request_text: str) -> FruitRecommendation:
    ranked = sorted(
        FRUIT_MENU,
        key=lambda item: (-_score_fruit(request_text, item), item["seq"]),
    )
    chosen = ranked[0]
    tease = _pick_tease(chosen)
    voice_text = f"我推荐{chosen['seq']}号{chosen['name']}，{tease}"
    return FruitRecommendation(
        seq=int(chosen["seq"]),
        name=str(chosen["name"]),
        tease=tease,
        voice_text=voice_text,
        request_text=request_text,
        source="local-fallback",
        reason="本地规则兜底",
    )


def _llm_is_required() -> bool:
    return not bool(getattr(config, "FRUIT_ALLOW_LOCAL_FALLBACK", False))


def _extract_seq_from_text(text: str) -> Optional[int]:
    normalized = _normalize_text(text)
    if not normalized:
        return None

    for fruit_item in FRUIT_MENU:
        if str(fruit_item["name"]) in normalized:
            return int(fruit_item["seq"])

    digit_match = re.search(r"(?<!\d)([1-6])(?!\d)", normalized)
    if digit_match:
        return int(digit_match.group(1))

    return None


def _parse_llm_payload(content: str) -> Optional[FruitRecommendation]:
    if not content:
        return None

    candidate = content.strip()
    match = _JSON_OBJECT_RE.search(candidate)
    if match:
        candidate = match.group(0)

    try:
        payload = json.loads(candidate)
    except Exception:
        payload = None

    if isinstance(payload, dict):
        seq_value = payload.get("seq", payload.get("sequence", payload.get("selected_seq")))
        try:
            seq = int(seq_value)
        except Exception:
            seq = None
        if seq is not None and 1 <= seq <= 6:
            fruit_item = _fruit_item_for_seq(seq)
            tease = str(payload.get("tease") or payload.get("comment") or payload.get("reason") or "").strip()
            if not tease:
                tease = _pick_tease(fruit_item)
            voice_text = f"我推荐{seq}号{fruit_item['name']}，{tease}"
            return FruitRecommendation(
                seq=seq,
                name=str(fruit_item["name"]),
                tease=tease,
                voice_text=voice_text,
                request_text="",
                source="ai",
                model=str(payload.get("model") or ""),
                reason=str(payload.get("reason") or ""),
            )

    seq = _extract_seq_from_text(content)
    if seq is None:
        return None
    fruit_item = _fruit_item_for_seq(seq)
    tease = _pick_tease(fruit_item)
    voice_text = f"我推荐{seq}号{fruit_item['name']}，{tease}"
    return FruitRecommendation(
        seq=seq,
        name=str(fruit_item["name"]),
        tease=tease,
        voice_text=voice_text,
        request_text="",
        source="ai",
    )


def _is_insufficient_balance_message(message: str) -> bool:
    message_norm = (message or "").lower()
    return any(marker in message_norm for marker in _LLM_INSUFFICIENT_BALANCE_MARKERS)


def _recommend_with_llm(request_text: str) -> Optional[FruitRecommendation]:
    if not getattr(config, "FRUIT_USE_LLM", True):
        return None

    api_key = str(
        getattr(config, "FRUIT_API_KEY", "")
        or getattr(config, "DEEPSEEK_API_KEY", "")
    ).strip()
    if not api_key:
        return None

    try:
        import openai  # type: ignore
    except Exception:
        return None

    base_url = str(
        getattr(config, "FRUIT_BASE_URL", "")
        or getattr(config, "DEEPSEEK_BASE_URL", "")
    ).strip() or "https://api.deepseek.com/v1"
    model = str(getattr(config, "FRUIT_CHAT_MODEL", "")).strip() or "deepseek-chat"

    fruit_lines = "\n".join(f"{item['seq']}. {item['name']}" for item in FRUIT_MENU)
    system_prompt = (
        "你是一个水果推荐助手。"
        "你只能从给定的 1-6 号水果里选 1 个。"
        "输出必须是严格 JSON，不要写多余解释，不要写 Markdown。"
        "JSON 字段：seq(1-6整数), tease(一句中文调侃，适合口语朗读), reason(可选简短理由)。"
    )
    user_prompt = (
        f"用户需求：{request_text}\n\n"
        f"可选水果：\n{fruit_lines}\n\n"
        "要求："
        "1) 只选一个最合适的水果。"
        "2) tease 要自然、口语化、带一点调侃，但不要冒犯。"
        "3) 如果用户说得很笼统，优先选最稳妥的水果。"
        "4) 只返回 JSON。"
    )

    timeout_sec = float(getattr(config, "FRUIT_LLM_TIMEOUT_SEC", 4.0))
    script = (
        "import json, sys\n"
        "api_key = sys.argv[1]\n"
        "base_url = sys.argv[2]\n"
        "model = sys.argv[3]\n"
        "system_prompt = sys.argv[4]\n"
        "user_prompt = sys.argv[5]\n"
        "try:\n"
        "    from openai import OpenAI\n"
        "    client = OpenAI(api_key=api_key, base_url=base_url, timeout=float(sys.argv[6]), max_retries=0)\n"
        "    response = client.chat.completions.create(\n"
        "        model=model,\n"
        "        temperature=0.6,\n"
        "        messages=[\n"
        "            {'role': 'system', 'content': system_prompt},\n"
        "            {'role': 'user', 'content': user_prompt},\n"
        "        ],\n"
        "    )\n"
        "    content = (response.choices[0].message.content or '').strip()\n"
        "    print(json.dumps({'content': content}, ensure_ascii=False))\n"
        "except Exception as exc:\n"
        "    message = str(exc)\n"
        "    response = getattr(exc, 'response', None)\n"
        "    status_code = getattr(response, 'status_code', None)\n"
        "    error_kind = 'request_failed'\n"
        "    if status_code == 402 or any(marker in message.lower() for marker in ['insufficient balance', 'insufficient_balance', 'insufficient credits', 'quota exceeded', 'billing hard limit']):\n"
        "        error_kind = 'insufficient_balance'\n"
        "    print(json.dumps({'error': error_kind, 'status_code': status_code, 'message': message}, ensure_ascii=False))\n"
    )

    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                api_key,
                base_url,
                model,
                system_prompt,
                user_prompt,
                str(timeout_sec),
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec + 1.5,
            check=False,
        )
    except Exception as exc:
        print(f"[WARN] Fruit LLM subprocess failed to start: {exc}")
        return None

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        if stderr:
            print(f"[WARN] Fruit LLM request failed: {stderr}")
        else:
            print(f"[WARN] Fruit LLM request failed with return code {completed.returncode}")
        return None

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return None

    try:
        payload = json.loads(stdout)
    except Exception as exc:
        print(f"[WARN] Fruit LLM returned non-JSON stdout: {exc}; stdout={stdout[:200]!r}")
        return None

    error_kind = str(payload.get("error") or "").strip()
    if error_kind:
        message = str(payload.get("message") or "").strip()
        status_code = payload.get("status_code")
        if error_kind == "insufficient_balance" or _is_insufficient_balance_message(message):
            print("[WARN] Fruit LLM unavailable: insufficient balance or quota. Falling back to local rules.")
        else:
            status_note = f" (status={status_code})" if status_code is not None else ""
            print(f"[WARN] Fruit LLM request failed{status_note}: {message or error_kind}")
        return None

    content = str(payload.get("content") or "").strip()

    parsed = _parse_llm_payload(content)
    if parsed is None:
        print(f"[WARN] Fruit LLM response could not be parsed: {content[:200]!r}")
        return None

    fruit_item = _fruit_item_for_seq(parsed.seq)
    tease = parsed.tease or _pick_tease(fruit_item)
    voice_text = f"我推荐{parsed.seq}号{fruit_item['name']}，{tease}"
    return FruitRecommendation(
        seq=parsed.seq,
        name=str(fruit_item["name"]),
        tease=tease,
        voice_text=voice_text,
        request_text=request_text,
        source="ai",
        model=model,
        reason=parsed.reason,
    )


def recommend_fruit(request_text: str) -> FruitRecommendation:
    request_text = (request_text or "").strip()

    if not request_text and _llm_is_required():
        llm_result = _recommend_with_llm("")
        if llm_result is not None:
            return llm_result
        raise RuntimeError("Fruit LLM unavailable and local fallback is disabled")
    if not request_text:
        return _best_local_recommendation("")

    llm_result = _recommend_with_llm(request_text)
    if llm_result is not None:
        return llm_result
    if _llm_is_required():
        raise RuntimeError("Fruit LLM unavailable and local fallback is disabled")
    return _best_local_recommendation(request_text)


def build_result_payload(result: FruitRecommendation) -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "request_text": result.request_text,
        "recommended_seq": int(result.seq),
        "recommended_name": result.name,
        "tease": result.tease,
        "voice_text": result.voice_text,
        "source": result.source,
        "model": result.model,
        "reason": result.reason,
    }


def write_result_json(result: FruitRecommendation, output_path: str | Path) -> Path:
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = build_result_payload(result)
    with output_file.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return output_file
