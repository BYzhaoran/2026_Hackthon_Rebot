"""
Wake word detection helpers.

This module keeps wake-word matching lightweight and configurable. It accepts
exact aliases like "大厨" and a small set of similar pronunciations, then can
strip the wake word out of the transcript before passing the remaining text to
the main pipeline.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, Tuple

try:
    from . import config
except ImportError:
    import config


_PUNCT_RE = re.compile(r"[，。！？、,.!?:;；：\s]+")


def _normalize(text: str) -> str:
    return _PUNCT_RE.sub("", (text or "").strip())


def _alias_iter() -> Iterable[str]:
    aliases = [config.WAKE_WORD, *getattr(config, "WAKE_WORD_ALIASES", [])]
    seen = set()
    for alias in aliases:
        if not alias:
            continue
        alias = str(alias).strip()
        if not alias or alias in seen:
            continue
        seen.add(alias)
        yield alias


def _substring_similarity(text: str, alias: str) -> float:
    if not text or not alias:
        return 0.0
    if len(text) < len(alias):
        return SequenceMatcher(None, text, alias).ratio()
    best = 0.0
    span = len(alias)
    for idx in range(0, len(text) - span + 1):
        candidate = text[idx : idx + span]
        best = max(best, SequenceMatcher(None, candidate, alias).ratio())
        if best >= 1.0:
            break
    return best


def contains_wake_word(text: str) -> Tuple[bool, str]:
    """
    Return whether the transcript contains a wake word and which alias matched.
    """
    normalized = _normalize(text)
    if not normalized:
        return False, ""

    threshold = float(getattr(config, "WAKE_WORD_MATCH_THRESHOLD", 0.5))
    for alias in _alias_iter():
        if alias in normalized:
            return True, alias
        if _substring_similarity(normalized, alias) >= threshold:
            return True, alias
    return False, ""


def strip_wake_word(text: str) -> str:
    """
    Remove wake words and nearby filler phrases from a transcript.
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    for alias in sorted(_alias_iter(), key=len, reverse=True):
        cleaned = cleaned.replace(alias, " ")

    fillers = [
        "请",
        "麻烦",
        "帮我",
        "帮我把",
        "帮忙",
        "给我",
        "来点",
        "来一份",
        "告诉我",
        "我想要",
        "我要",
        "我想",
        "一下",
    ]
    for filler in fillers:
        cleaned = cleaned.replace(filler, " ")

    cleaned = re.sub(r"[，。！？、,.!?:;；：\s]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def is_wake_command(text: str) -> bool:
    matched, _ = contains_wake_word(text)
    return matched
