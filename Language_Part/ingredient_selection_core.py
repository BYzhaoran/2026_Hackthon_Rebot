"""
Shared ingredient selection helpers.

This module keeps the LLM-driven selector strict, but guarantees a best-effort
fallback when the model returns nothing or something unusable.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence


@dataclass
class SelectionOutcome:
    ids: List[int]
    note: str = ""
    used_fallback: bool = False


_CATEGORY_HINTS = {
    "vegetable": ["vegetable", "veg", "蔬菜", "菜", "青菜"],
    "fruit": ["fruit", "水果", "果"],
    "protein": ["protein", "蛋白", "肉", "蛋", "豆", "海鲜"],
    "meat": ["meat", "肉", "猪", "牛", "鸡", "鸭", "羊"],
    "dairy": ["dairy", "奶", "乳", "芝士", "奶酪"],
    "grain": ["grain", "主食", "米", "面", "麦", "饭"],
    "spice": ["spice", "调料", "香料", "酱", "盐", "糖"],
    "drink": ["drink", "beverage", "饮料", "饮品", "水", "茶", "咖啡"],
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def extract_selected_ids(raw: str) -> List[int]:
    raw = (raw or "").strip()
    if not raw:
        return []

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            ids = data.get("selected_ids", [])
            if isinstance(ids, list):
                return sorted({int(x) for x in ids})
    except Exception:
        pass

    matches = re.findall(r"\d+", raw)
    return sorted({int(x) for x in matches})


def _iter_aliases(item: Dict[str, Any]) -> Iterable[str]:
    aliases = item.get("aliases", [])
    if isinstance(aliases, str):
        yield aliases
    elif isinstance(aliases, Sequence):
        for alias in aliases:
            if isinstance(alias, str) and alias.strip():
                yield alias


def _category_keywords(category: str) -> List[str]:
    category_norm = normalize_text(category)
    hints = list(_CATEGORY_HINTS.get(category_norm, []))
    if category_norm and category_norm not in hints:
        hints.append(category_norm)
    return [normalize_text(x) for x in hints if x]


def score_ingredient(request_text: str, item: Dict[str, Any]) -> int:
    request_norm = normalize_text(request_text)
    if not request_norm:
        return 0

    score = 0
    name = normalize_text(str(item.get("name", "")))
    category = normalize_text(str(item.get("category", "")))
    aliases = [normalize_text(alias) for alias in _iter_aliases(item)]

    candidates = [name, category, *aliases]

    for candidate in candidates:
        if not candidate:
            continue
        if candidate in request_norm:
            score += 100 + len(candidate) * 2
        elif request_norm in candidate:
            score += 80 + len(request_norm)
        else:
            overlap = len(set(request_norm) & set(candidate))
            score += overlap * 3

    for hint in _category_keywords(category):
        if hint and hint in request_norm:
            score += 25

    # Favor closer matches with more token overlap.
    score += len(set(request_norm) & set(name)) * 4
    return score


def best_effort_select_ids(
    request_text: str,
    ingredients: Sequence[Dict[str, Any]],
    *,
    max_results: int = 3,
) -> SelectionOutcome:
    scored: List[tuple[int, int, Dict[str, Any]]] = []
    for fallback_index, item in enumerate(ingredients):
        try:
            item_id = int(item.get("id"))
        except Exception:
            continue
        scored.append((score_ingredient(request_text, item), fallback_index, {"id": item_id, **item}))

    if not scored:
        return SelectionOutcome(ids=[], note="没有可用食材，无法推荐。", used_fallback=True)

    scored.sort(key=lambda x: (-x[0], x[1], int(x[2]["id"])))
    top = scored[: max(1, max_results)]
    ids = [int(item["id"]) for _, _, item in top]

    top_names = [str(item.get("name", "")) for _, _, item in top if str(item.get("name", ""))]
    if top_names:
        note = "没有找到完全匹配，我先按最接近的给你选了：" + "，".join(top_names) + "。"
    else:
        note = "没有找到完全匹配，我先按最接近的给你选了。"

    return SelectionOutcome(ids=ids, note=note, used_fallback=True)
