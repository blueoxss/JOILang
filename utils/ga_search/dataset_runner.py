#!/usr/bin/env python3
from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Any


def load_dataset_rows(dataset_path: str | Path) -> list[dict[str, Any]]:
    with Path(dataset_path).open(encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def normalize_categories(values: list[str] | tuple[str, ...] | None) -> set[str]:
    out: set[str] = set()
    for raw in values or []:
        for item in str(raw).split(","):
            token = item.strip()
            if token:
                out.add(token)
    return out


def select_dataset_rows(
    rows: list[dict[str, Any]],
    *,
    row_no: int | None = None,
    start_row: int = 1,
    end_row: int | None = None,
    categories: list[str] | tuple[str, ...] | None = None,
    limit_per_category: int | None = None,
    sample_size: int | None = None,
    seed: int = 0,
) -> list[tuple[int, dict[str, Any]]]:
    if row_no is not None:
        if row_no < 1 or row_no > len(rows):
            raise IndexError(f"row_no out of range: {row_no}")
        row = dict(rows[row_no - 1])
        if "gt" not in row or not str(row.get("gt") or "").strip():
            raise ValueError(f"row {row_no} is missing official gt column")
        return [(row_no, row)]

    category_filter = normalize_categories(categories)
    end = end_row if end_row is not None else len(rows)
    selected: list[tuple[int, dict[str, Any]]] = []
    per_category: dict[str, int] = {}
    for idx, row in enumerate(rows, start=1):
        if idx < max(1, start_row) or idx > end:
            continue
        category = str(row.get("category", "")).strip()
        if category_filter and category not in category_filter:
            continue
        if limit_per_category is not None:
            key = category or "__uncategorized__"
            if per_category.get(key, 0) >= limit_per_category:
                continue
            per_category[key] = per_category.get(key, 0) + 1
        if "gt" not in row or not str(row.get("gt") or "").strip():
            raise ValueError(f"row {idx} is missing official gt column")
        selected.append((idx, dict(row)))

    if sample_size is not None and sample_size > 0 and len(selected) > sample_size:
        rng = random.Random(seed)
        selected = sorted(rng.sample(selected, sample_size), key=lambda item: item[0])
    return selected


def command_text(row: dict[str, Any]) -> str:
    return str(row.get("command_eng") or row.get("command_kor") or "").strip()
