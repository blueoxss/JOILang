#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SECTION_RE = re.compile(r"^\s*(#{1,6}\s+.+|\[[^\]]+\]\s*|---(?:\s+.*)?$)")


def token_estimate(text: str) -> int:
    return max(1, int(len(text.split()) * 1.35))


def classify_block_family(title: str, text: str) -> str:
    haystack = f"{title}\n{text}".lower()
    if "service_list" in haystack or "service list" in haystack:
        return "service_list"
    if "device and service" in haystack or "service mapping" in haystack:
        return "service_mapping"
    if "grammar" in haystack or "syntax" in haystack:
        return "grammar"
    if "condition combination" in haystack or "tempo" in haystack or "cron" in haystack or "period" in haystack:
        return "temporal_rules"
    if "caution" in haystack or "never use" in haystack:
        return "caution"
    if "connected_devices" in haystack:
        return "connected_devices"
    if "output format" in haystack or "json object" in haystack:
        return "output_contract"
    if "reasoning" in haystack or "chain-of-thought" in haystack:
        return "reasoning_contract"
    if "example" in haystack:
        return "examples"
    if "response" in haystack:
        return "response_contract"
    if "you are" in haystack[:300]:
        return "preamble"
    return "misc"


def _title_from_text(text: str, index: int) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:120]
    return f"Block {index:03d}"


def decompose_prompt_to_blocks(system_prompt: str) -> list[dict[str, Any]]:
    text = str(system_prompt or "")
    if not text:
        return []
    lines = text.splitlines(keepends=True)
    segments: list[str] = []
    current: list[str] = []

    for line in lines:
        starts_section = bool(SECTION_RE.match(line))
        if starts_section and current:
            segments.append("".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        segments.append("".join(current))

    blocks: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        title = _title_from_text(segment, index)
        blocks.append(
            {
                "block_id": f"B{index:03d}",
                "family": classify_block_family(title, segment),
                "title": title,
                "text": segment,
                "start_marker": title,
                "token_estimate": token_estimate(segment),
                "order": index,
                "source": "decomposed_from_monolith",
            }
        )
    return blocks


def write_decomposed_blocks(blocks: list[dict[str, Any]], out_path: str | Path) -> None:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blocks, ensure_ascii=False, indent=2), encoding="utf-8")
