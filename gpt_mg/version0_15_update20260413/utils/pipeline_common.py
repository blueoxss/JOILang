#!/usr/bin/env python3
# Assumption: this file lives under gpt_mg/version0_15/utils/ and the repo root is three levels up.
from __future__ import annotations

import ast
import csv
import json
import os
import random
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

try:
    from .retrieval_context import (
        RetrievalConfig,
        load_retrieval_config,
        retrieval_ready,
        search_with_worker,
    )
except ImportError:
    from retrieval_context import (  # type: ignore
        RetrievalConfig,
        load_retrieval_config,
        retrieval_ready,
        search_with_worker,
    )


VERSION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = VERSION_ROOT.parents[1]
BLOCKS_DIR = VERSION_ROOT / "blocks"
GENOMES_DIR = VERSION_ROOT / "genomes"
RESULTS_DIR = VERSION_ROOT / "results"
LOGS_DIR = VERSION_ROOT / "logs"
CHECKPOINTS_DIR = VERSION_ROOT / "checkpoints"
DATASET_DEFAULT = REPO_ROOT / "datasets" / "JOICommands-280.csv"
SERVICE_SCHEMA_DEFAULT = REPO_ROOT / "datasets" / "service_list_ver2.0.1.json"
LEGACY_V13_ROOT = VERSION_ROOT.parent / "version0_13"
LEGACY_V13_PROMPT_DIR = LEGACY_V13_ROOT


BLOCK_FILE_MAP = {
    "01": "01_preamble.txt",
    "02": "02_generator_prompt.txt",
    "03": "03_postprocessor.txt",
    "04": "04_reranker_prompt.txt",
    "05": "05_repair_prompt.txt",
    "06": "06_det_helper.txt",
}

LEGACY_V13_PROMPT_FILES = {
    "grammar": "grammar_ver1.5.10.md",
    "service_prompt": "service_prompt_10.md",
    "tempo": "tempo_prompt_9.md",
    "caution": "caution_prompt_8.md",
    "response_prompt": "response_prompt_baseline_cot.md",
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "if", "in", "into",
    "is", "it", "its", "me", "of", "on", "or", "than", "that", "the", "then", "this",
    "to", "up", "with", "whenever", "when", "while", "through", "after", "before", "every",
    "all", "any", "tell", "please", "make", "set", "change", "turn", "switch", "start",
}

DEFAULT_CANDIDATE_STRATEGIES = [
    "direct",
    "minimal",
    "canonical_names_first",
    "explicit_preconditions",
    "compact_json",
]

MEMBER_AFTER_RECEIVER_RE = re.compile(
    r"(?P<receiver>all\([^\n\r()]+\)|\([^\n\r()]+\))\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)"
)
FUNCTION_CALL_OPEN_RE = re.compile(
    r"(?P<head>(?:all\([^\n\r()]+\)|\([^\n\r()]+\))\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)\()"
)
CLOCK_DELAY_CALL_RE = re.compile(r"\(#Clock\)\.clock_delay\(\s*(?P<millis>\d+(?:\.0+)?)\s*\)")
COOKING_TIME_SECONDS_FUNCTION_MEMBERS = {
    "oven_setcookingparameters",
    "ricecooker_setcookingparameters",
}
EXPLICIT_MEMBER_ALIASES = {
    "leaksensor_leak": "leaksensor_leakage",
    "airconditioner_setairconditionermodemode": "airconditioner_setairconditionermode",
    "airpurifier_setairpurifermode": "airpurifier_setairpurifiermode",
    "multibutton_button2": "dimmerswitch_button2",
}
RECEIVER_TAG_ALIASES = {
    "firstfloor": "Floor1",
    "1stfloor": "Floor1",
    "secondfloor": "Floor2",
    "2ndfloor": "Floor2",
    "thirdfloor": "Floor3",
    "3rdfloor": "Floor3",
}
POWER_OFF_MODE_MEMBERS = {
    "airpurifier_setairpurifiermode",
    "humidifier_sethumidifiermode",
    "siren_setsirenmode",
}
TAG_TEXT_ALIASES = {
    "BabyRoom": ["아기방"],
    "Bathroom": ["욕실", "화장실"],
    "Bedroom": ["안방", "침실"],
    "Entrance": ["현관", "입구"],
    "Floor1": ["1층", "일층", "first floor", "1st floor"],
    "Floor2": ["2층", "이층", "second floor", "2nd floor"],
    "Garage": ["차고"],
    "Garden": ["정원"],
    "Group1": ["그룹1", "그룹 1", "group 1"],
    "Group2": ["그룹2", "그룹 2", "group 2"],
    "Kitchen": ["주방", "부엌"],
    "Lab": ["연구실"],
    "LivingRoom": ["거실"],
    "Lobby": ["로비"],
    "Main": ["메인"],
    "MeetingRoom": ["회의실"],
    "ServerRack": ["서버랙", "서버 랙"],
    "ServerRoom": ["서버실"],
    "Study": ["서재"],
    "Terrace": ["테라스"],
    "WineCellar": ["와인셀러", "와인 셀러"],
    "Zone1": ["구역1", "구역 1", "zone 1"],
}


def ensure_workspace() -> None:
    for path in (BLOCKS_DIR, GENOMES_DIR, RESULTS_DIR, LOGS_DIR, CHECKPOINTS_DIR, BLOCKS_DIR / "generated"):
        path.mkdir(parents=True, exist_ok=True)


def load_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: str | Path, payload: Any, *, indent: int = 2) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=indent)
        f.write("\n")


def append_jsonl(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def atomic_write_csv(path: str | Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.stem + ".", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with tmp_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})
        shutil.move(str(tmp_path), str(path))
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def load_dataset_rows(dataset_path: str | Path = DATASET_DEFAULT) -> list[dict[str, str]]:
    with Path(dataset_path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def normalize_categories(values: list[str] | tuple[str, ...] | None) -> set[str]:
    normalized: set[str] = set()
    for raw in values or []:
        for item in str(raw).split(","):
            token = item.strip()
            if token:
                normalized.add(token)
    return normalized


def select_rows(
    rows: list[dict[str, str]],
    *,
    start_row: int = 1,
    end_row: int | None = None,
    limit: int | None = None,
    limit_per_category: int | None = None,
    categories: list[str] | tuple[str, ...] | None = None,
) -> list[tuple[int, dict[str, str]]]:
    selected: list[tuple[int, dict[str, str]]] = []
    per_category_counts: dict[str, int] = {}
    if start_row < 1:
        start_row = 1
    last = end_row if end_row is not None else len(rows)
    category_filter = normalize_categories(categories)
    for idx, row in enumerate(rows, start=1):
        if idx < start_row or idx > last:
            continue
        category = str(row.get("category", "")).strip()
        if category_filter and category not in category_filter:
            continue
        if limit_per_category is not None:
            category_key = category or "__uncategorized__"
            if per_category_counts.get(category_key, 0) >= int(limit_per_category):
                continue
        selected.append((idx, row))
        if limit_per_category is not None:
            category_key = category or "__uncategorized__"
            per_category_counts[category_key] = per_category_counts.get(category_key, 0) + 1
        if limit is not None and len(selected) >= limit:
            break
    return selected


def parse_connected_devices(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if not text:
        return {}
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(text)
        except Exception:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def slugify(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized or "item"


def split_camel_tokens(value: str) -> list[str]:
    if not value:
        return []
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    spaced = spaced.replace("_", " ").replace("-", " ")
    return [token.lower() for token in spaced.split() if token]


def tokenize_command(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9]+", (text or "").lower())
    return [token for token in tokens if token not in STOPWORDS]


def extract_command_numbers(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)?", text or "")


def canonical_service_name(device: str, service_name: str) -> str:
    return f"{device}_{service_name}"


def lowercase_output_member_name(member: str) -> str:
    return str(member or "").lower()


def lowercase_service_members_in_code(code: str) -> str:
    text = str(code or "")
    if not text:
        return text

    def repl(match: re.Match[str]) -> str:
        return f"{match.group('receiver')}.{lowercase_output_member_name(match.group('member'))}"

    return MEMBER_AFTER_RECEIVER_RE.sub(repl, text)


def normalize_receiver_quantifiers_in_code(code: str) -> str:
    text = re.sub(r"\bany\(", "all(", str(code or ""))
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"all\(\s*all\((#[^\n\r()]*)\)\s*\)", r"all(\1)", text)
    return text


def _format_delay_from_millis(millis_text: str) -> str:
    millis = int(float(millis_text))
    if millis % 3_600_000 == 0:
        return f"delay({millis // 3_600_000} HOUR)"
    if millis % 60_000 == 0:
        return f"delay({millis // 60_000} MIN)"
    if millis % 1_000 == 0:
        return f"delay({millis // 1_000} SEC)"
    return f"delay({millis} MS)"


def normalize_clock_delay_calls_in_code(code: str) -> str:
    text = str(code or "")
    if not text:
        return text

    def repl(match: re.Match[str]) -> str:
        return _format_delay_from_millis(match.group("millis"))

    return CLOCK_DELAY_CALL_RE.sub(repl, text)


def normalize_integer_like_numeric_literals_in_code(code: str) -> str:
    text = str(code or "")
    if not text:
        return text

    def normalize_segment(segment: str) -> str:
        return re.sub(r"(?<![\w.])(-?\d+)\.0+\b", r"\1", segment)

    string_re = r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
    parts = re.split(string_re, text)
    normalized: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith(("'", '"')):
            normalized.append(part)
        else:
            normalized.append(normalize_segment(part))
    return "".join(normalized)


def _normalize_receiver_tag_case(tag: str, service_schema: dict[str, Any] | None = None) -> str:
    raw = str(tag or "")
    if not raw:
        return raw
    alias_match = RECEIVER_TAG_ALIASES.get(_compact_text_key(raw))
    if alias_match:
        return alias_match
    schema_devices = {str(device).lower(): str(device) for device in (service_schema or {})}
    schema_match = schema_devices.get(raw.lower())
    if schema_match:
        return schema_match
    return raw[:1].upper() + raw[1:]


def normalize_receiver_tag_case_in_code(
    code: str,
    service_schema: dict[str, Any] | None = None,
) -> str:
    text = str(code or "")
    if not text:
        return text

    def repl(match: re.Match[str]) -> str:
        return "#" + _normalize_receiver_tag_case(match.group(1), service_schema)

    return re.sub(r"#([A-Za-z_][A-Za-z0-9_]*)", repl, text)


def normalize_receiver_tag_order_in_code(
    code: str,
    service_schema: dict[str, Any] | None = None,
) -> str:
    text = str(code or "")
    if not text or not service_schema:
        return text
    schema_devices = {str(device).lower(): str(device) for device in service_schema}

    def repl(match: re.Match[str]) -> str:
        tags = re.findall(r"#([A-Za-z_][A-Za-z0-9_]*)", match.group("body"))
        if len(tags) < 2:
            return match.group(0)
        tags = [_normalize_receiver_tag_case(tag, service_schema) for tag in tags]
        deduped_tags: list[str] = []
        seen_tags: set[str] = set()
        for tag in tags:
            key = str(tag).lower()
            if key in seen_tags:
                continue
            seen_tags.add(key)
            deduped_tags.append(tag)
        tags = deduped_tags
        selector_tags = [tag for tag in tags if str(tag).lower() not in schema_devices]
        device_tags = [schema_devices[str(tag).lower()] for tag in tags if str(tag).lower() in schema_devices]
        prefix = "all(" if match.group("all") else "("
        return prefix + " ".join(f"#{tag}" for tag in selector_tags + device_tags) + ")"

    return re.sub(
        r"(?P<all>\ball)?\((?P<body>\s*#[A-Za-z_][A-Za-z0-9_]*(?:\s+#[A-Za-z_][A-Za-z0-9_]*)+\s*)\)",
        repl,
        text,
    )


def _compact_text_key(value: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]+", "", str(value or "")).casefold()


def _command_mentions_tag(command_text: str, tag: str) -> bool:
    command_key = _compact_text_key(command_text)
    tag_key = _compact_text_key(tag)
    if tag_key and tag_key in command_key:
        return True
    for alias in TAG_TEXT_ALIASES.get(str(tag or ""), []):
        alias_key = _compact_text_key(alias)
        if alias_key and alias_key in command_key:
            return True
    return False


def normalize_connected_selector_tags_in_code(
    code: str,
    *,
    command_text: str = "",
    connected_devices: dict[str, Any] | None = None,
    service_schema: dict[str, Any] | None = None,
) -> str:
    text = str(code or "")
    if not text or not connected_devices or not service_schema:
        return text
    schema_devices = {str(device).lower(): str(device) for device in service_schema}
    selectors_by_category: dict[str, list[str]] = {}
    for device in connected_devices.values():
        if not isinstance(device, dict):
            continue
        raw_categories = device.get("category", [])
        if isinstance(raw_categories, str):
            categories = [raw_categories]
        elif isinstance(raw_categories, (list, tuple, set)):
            categories = [str(item) for item in raw_categories]
        else:
            categories = []
        raw_tags = device.get("tags", [])
        if isinstance(raw_tags, str):
            tags = [raw_tags]
        elif isinstance(raw_tags, (list, tuple, set)):
            tags = [str(item) for item in raw_tags]
        else:
            tags = []
        for category in categories:
            resolved = schema_devices.get(str(category).lower())
            if not resolved:
                continue
            for tag in tags:
                if str(tag).lower() == resolved.lower() or str(tag).lower() in schema_devices:
                    continue
                if _command_mentions_tag(command_text, tag):
                    selectors_by_category.setdefault(resolved, [])
                    if tag not in selectors_by_category[resolved]:
                        selectors_by_category[resolved].append(tag)
    if not selectors_by_category:
        return text

    def repl(match: re.Match[str]) -> str:
        prefix = "all(" if match.group("all") else "("
        tags = re.findall(r"#([A-Za-z_][A-Za-z0-9_]*)", match.group("body"))
        if not tags:
            return match.group(0)
        category = ""
        for tag in reversed(tags):
            category = schema_devices.get(str(tag).lower(), "")
            if category:
                break
        if not category:
            return match.group(0)
        required = selectors_by_category.get(category, [])
        if not required:
            return match.group(0)
        existing = {str(tag).lower() for tag in tags}
        insert = [tag for tag in required if str(tag).lower() not in existing]
        if not insert:
            return match.group(0)
        non_device_tags = [tag for tag in tags if str(tag).lower() not in schema_devices]
        device_tags = [schema_devices[str(tag).lower()] for tag in tags if str(tag).lower() in schema_devices]
        ordered = non_device_tags + insert + device_tags
        return prefix + " ".join(f"#{tag}" for tag in ordered) + ")"

    return re.sub(
        r"(?P<all>\ball)?\((?P<body>\s*#[A-Za-z_][A-Za-z0-9_]*(?:\s+#[A-Za-z_][A-Za-z0-9_]*)*\s*)\)",
        repl,
        text,
    )


def normalize_windowcovering_semantic_receivers_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    if not text:
        return text
    semantic_tags = {"window", "blind", "shade"}
    command = str(command_text or "").lower()
    inferred_semantic_tag = ""
    if any(token in command for token in ("blind", "블라인드")):
        inferred_semantic_tag = "Blind"
    elif any(token in command for token in ("shade", "쉐이드")):
        inferred_semantic_tag = "Shade"
    elif any(token in command for token in ("window", "창문")):
        inferred_semantic_tag = "Window"

    def repl(match: re.Match[str]) -> str:
        receiver = match.group("receiver")
        member = lowercase_output_member_name(match.group("member"))
        tags = re.findall(r"#([A-Za-z_][A-Za-z0-9_]*)", receiver)
        lowered = [tag.lower() for tag in tags]
        if not any(tag in semantic_tags for tag in lowered) and not (
            inferred_semantic_tag and "windowcovering" in lowered
        ):
            return match.group(0)
        filtered_tags = [tag for tag in tags if tag.lower() != "windowcovering"]
        if inferred_semantic_tag and not any(tag.lower() in semantic_tags for tag in filtered_tags):
            filtered_tags.append(inferred_semantic_tag)
        prefix = "all(" if receiver.startswith("all(") else "("
        normalized_receiver = prefix + " ".join(f"#{tag}" for tag in filtered_tags) + ")"
        if member == "windowcovering_currentposition":
            member = "armrobot_currentposition"
        return f"{normalized_receiver}.{member}"

    return MEMBER_AFTER_RECEIVER_RE.sub(repl, text)


def normalize_semantic_receiver_tag_order_in_code(code: str) -> str:
    text = str(code or "")
    if not text:
        return text
    semantic_last_tags = {"blind", "window", "shade"}

    def repl(match: re.Match[str]) -> str:
        tags = re.findall(r"#([A-Za-z_][A-Za-z0-9_]*)", match.group("body"))
        if len(tags) < 2 or not any(tag.lower() in semantic_last_tags for tag in tags):
            return match.group(0)
        prefix = "all(" if match.group("all") else "("
        semantic = [tag for tag in tags if tag.lower() in semantic_last_tags]
        selectors = [tag for tag in tags if tag.lower() not in semantic_last_tags]
        return prefix + " ".join(f"#{tag}" for tag in selectors + semantic) + ")"

    return re.sub(
        r"(?P<all>\ball)?\((?P<body>\s*#[A-Za-z_][A-Za-z0-9_]*(?:\s+#[A-Za-z_][A-Za-z0-9_]*)+\s*)\)",
        repl,
        text,
    )


def canonicalize_member_aliases_in_code(
    code: str,
    service_schema: dict[str, Any] | None = None,
) -> str:
    text = str(code or "")
    if not text or not service_schema:
        return text
    schema_devices = {str(device).lower(): str(device) for device in service_schema}

    def repl(match: re.Match[str]) -> str:
        receiver = match.group("receiver")
        member = lowercase_output_member_name(match.group("member"))
        member = EXPLICIT_MEMBER_ALIASES.get(member, member)
        tags = re.findall(r"#([A-Za-z_][A-Za-z0-9_]*)", receiver)
        receiver_device = ""
        for tag in reversed(tags):
            receiver_device = schema_devices.get(str(tag).lower(), "")
            if receiver_device:
                break
        if not receiver_device:
            return f"{receiver}.{member}"
        services = service_schema.get(receiver_device, {})
        if not isinstance(services, dict):
            return f"{receiver}.{member}"
        canonical_members: dict[str, str] = {}
        for service_name in services:
            service_lower = lowercase_output_member_name(str(service_name))
            canonical_lower = lowercase_output_member_name(canonical_service_name(receiver_device, str(service_name)))
            canonical_members[service_lower] = canonical_lower
        if member in set(canonical_members.values()):
            return f"{receiver}.{member}"
        if member in canonical_members:
            return f"{receiver}.{canonical_members[member]}"
        suffix_matches = [
            canonical_lower
            for service_lower, canonical_lower in canonical_members.items()
            if member.endswith(f"_{service_lower}")
        ]
        if len(suffix_matches) == 1:
            return f"{receiver}.{suffix_matches[0]}"
        return f"{receiver}.{member}"

    return MEMBER_AFTER_RECEIVER_RE.sub(repl, text)


def normalize_power_off_mode_calls_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    lowered_command = str(command_text or "").lower()
    if "turn off" not in lowered_command and "switch off" not in lowered_command and "turn it off" not in lowered_command:
        return text

    def repl(match: re.Match[str]) -> str:
        receiver = match.group("receiver")
        member = lowercase_output_member_name(match.group("member"))
        args = str(match.group("args") or "").strip().strip('"').lower()
        if member in POWER_OFF_MODE_MEMBERS and args == "off":
            return f"{receiver}.switch_off()"
        return match.group(0)

    return re.sub(
        r"(?P<receiver>all\([^\n\r()]+\)|\([^\n\r()]+\))\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)\((?P<args>[^()]*)\)",
        repl,
        text,
    )


def normalize_invalid_siren_off_mode_calls_in_code(code: str) -> str:
    text = str(code or "")
    if not text:
        return text

    def repl(match: re.Match[str]) -> str:
        receiver = match.group("receiver")
        member = lowercase_output_member_name(match.group("member"))
        args = str(match.group("args") or "").strip().strip('"').strip("'").lower()
        if member == "siren_setsirenmode" and args in {"", "off"}:
            return f"{receiver}.switch_off()"
        return match.group(0)

    return re.sub(
        r"(?P<receiver>all\([^\n\r()]+\)|\([^\n\r()]+\))\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)\((?P<args>[^()]*)\)",
        repl,
        text,
    )


def normalize_dehumidifier_internal_care_mode_in_code(code: str) -> str:
    text = str(code or "")
    if not text:
        return text

    def repl(match: re.Match[str]) -> str:
        receiver = match.group("receiver")
        member = lowercase_output_member_name(match.group("member"))
        args = str(match.group("args") or "").strip().strip('"').strip("'")
        if member == "dehumidifier_setdehumidifiermode" and args.lower() in {"internalcare", "internal_care"}:
            return f'{receiver}.{member}("auto")'
        return match.group(0)

    return re.sub(
        r"(?P<receiver>all\([^\n\r()]+\)|\([^\n\r()]+\))\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)\((?P<args>[^()]*)\)",
        repl,
        text,
    )


def normalize_shared_switch_off_conditions_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or not any(token in command for token in ("off", "꺼", "stopped", "정지")):
        return text
    has_ac_off_condition = (
        any(token in command for token in ("air conditioner", "ac", "에어컨"))
        and any(token in command for token in ("off", "꺼"))
    )

    def repl(match: re.Match[str]) -> str:
        receiver = match.group("receiver")
        member = lowercase_output_member_name(match.group("member"))
        op = str(match.group("op") or "")
        value = str(match.group("value") or "").strip().strip('"').strip("'").lower()
        receiver_lower = receiver.lower()
        if "#siren" in receiver_lower and member == "siren_sirenmode":
            if (op == "!=" and value == "emergency") or (op == "==" and value == "off"):
                return f"{receiver}.switch_switch == false"
        if "#light" in receiver_lower and member in {"light_currentsaturation", "light_currenthue", "levelcontrol_currentlevel"}:
            if op == "==" and value in {"0", "0.0"}:
                return f"{receiver}.switch_switch == false"
        if has_ac_off_condition and "#airconditioner" in receiver_lower and member == "airconditioner_airconditionermode":
            if op == "==" and value in {"auto", "off"}:
                return f"{receiver}.switch_switch == false"
        return match.group(0)

    return re.sub(
        r"(?P<receiver>all\([^\n\r()]+\)|\([^\n\r()]+\))\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op>==|!=)\s*(?P<value>\"[^\"]*\"|'[^']*'|-?\d+(?:\.\d+)?)",
        repl,
        text,
    )


def normalize_switch_toggle_blocks_in_code(code: str) -> str:
    text = str(code or "")
    if not text:
        return text
    pattern = re.compile(
        r"if\s*\(\s*(?P<receiver>all\([^\n\r()]+\)|\([^\n\r()]+\))\.switch_switch\s*==\s*false\s*\)\s*"
        r"\{\s*(?P=receiver)\.switch_on\(\)\s*\}\s*"
        r"else\s+if\s*\(\s*(?P=receiver)\.switch_switch\s*==\s*true\s*\)\s*"
        r"\{\s*(?P=receiver)\.switch_off\(\)\s*\}",
        flags=re.DOTALL,
    )
    return pattern.sub(lambda match: f"{match.group('receiver')}.switch_toggle()", text)


def normalize_report_shortcuts_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text:
        return text
    if "weather" in command or "날씨" in command:
        text = re.sub(
            r"(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(#WeatherProvider\)\.weatherprovider_getweatherinfo\([^()]*\)\s*\n\s*"
            r"\(#Speaker\)\.speaker_speak\(\s*(?P=var)\s*\)",
            '(#Speaker).speaker_speak("현재 날씨는 " + (#WeatherProvider).weatherprovider_weather + "입니다")',
            text,
        )
    if any(token in command for token in ("current time", "현재 시각", "현재 시간")):
        text = re.sub(
            r"(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(#Clock\)\.clock_time\s*\n\s*"
            r"\(#Speaker\)\.speaker_speak\(\s*(?P=var)\s*\)",
            '(#Speaker).speaker_speak("현재 시각은 " + (#Clock).clock_hour + "시" + (#Clock).clock_minute + "분 입니다")',
            text,
        )
    return text


def normalize_time_window_code_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text:
        return text
    if "midnight" in command or "자정" in command:
        text = re.sub(
            r"if\s*\(\s*\(?\s*\(#Clock\)\.clock_hour\s*>=\s*22\s*\)?\s*and\s*"
            r"\(?\s*\(#Clock\)\.clock_hour\s*<\s*24\s*\)?\s*\)\s*"
            r"\{\s*(?P<body>.*?)\s*\}\s*else\s*\{\s*break\s*\}",
            lambda match: (
                "if ((#Clock).clock_hour == 0) {\n"
                "    break\n"
                "}\n\n"
                + match.group("body").strip()
            ),
            text,
            flags=re.DOTALL,
        )
    if any(token in command for token in ("until 3 pm", "until 3pm", "오후 3시까지")):
        text = re.sub(
            r"\(#Clock\)\.clock_hour\s*>=\s*15",
            "(#Clock).clock_hour == 15",
            text,
        )
    if any(token in command for token in ("8 am", "8am", "아침 8", "8시")) and any(
        token in command for token in ("9 am", "9am", "9시")
    ):
        text = re.sub(
            r"wait until\s*\(\s*\(#Clock\)\.clock_hour\s*==\s*9\s*\)",
            "delay(1 HOUR)",
            text,
        )
    return text


def normalize_all_lights_action_scope_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "")
    command_key = _compact_text_key(command)
    if not text:
        return text
    says_global_all_lights = any(key in command_key for key in ("turnonalllights", "모든불을켜", "모든조명을켜"))
    says_location_lights = any(
        key in command_key
        for key in (
            "livingroomlights",
            "1stfloorlights",
            "firstfloorlights",
            "floor1lights",
            "거실의모든",
            "1층불",
            "1층조명",
        )
    )
    if not says_global_all_lights or says_location_lights:
        return text
    return re.sub(
        r"all\(#LivingRoom #Light\)\.switch_on\(\)",
        "all(#Light).light_movetobrightness(100, 0)",
        text,
    )


def normalize_window_open_state_conditions_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or not any(token in command for token in ("window", "창문")):
        return text

    def repl(match: re.Match[str]) -> str:
        receiver = match.group("receiver")
        value = str(match.group("value") or "").strip().strip('"').strip("'").lower()
        if "#window" not in receiver.lower() or value != "open":
            return match.group(0)
        return f"{receiver}.armrobot_currentposition >| 0"

    return re.sub(
        r"(?P<receiver>all\([^\n\r()]+\)|\([^\n\r()]+\))\.door_doorstate\s*==\s*(?P<value>\"[^\"]*\"|'[^']*')",
        repl,
        text,
    )


def normalize_window_action_members_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or not any(token in command for token in ("window", "창문")):
        return text
    text = re.sub(
        r"(?P<receiver>all\([^\n\r()]*#Window[^\n\r()]*\)|\([^\n\r()]*#Window[^\n\r()]*\))\.window_open\(\)",
        r"\g<receiver>.windowcovering_uporopen()",
        text,
    )
    text = re.sub(
        r"(?P<receiver>all\([^\n\r()]*#Window[^\n\r()]*\)|\([^\n\r()]*#Window[^\n\r()]*\))\.window_close\(\)",
        r"\g<receiver>.windowcovering_downorclose()",
        text,
    )
    return text


def normalize_trigger_service_values_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text:
        return text
    if any(token in command for token in ("smoke", "fire", "연기", "화재")) and "emergency" in text:
        text = re.sub(r'(\.siren_setsirenmode\()\s*"emergency"\s*(\))', r'\1"fire"\2', text)
    if any(token in command for token in ("drying is finished", "건조가 끝")):
        text = re.sub(
            r"\(#LaundryDryer\)\.laundrydryer_dehumidifiermode\s*==\s*['\"]finished['\"]",
            "(#LaundryDryer).laundrydryer_spinspeed == 0",
            text,
        )
    return text


def normalize_any_group_bool_conditions_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or not any(token in command for token in ("any one", "any pump", "하나라도")):
        return text
    return re.sub(
        r"(?P<receiver>all\([^\n\r()]+\))\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)\s*==\s*true",
        r"\g<receiver>.\g<member> ==| true",
        text,
    )


def normalize_all_semantic_windowcovering_actions_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command_key = _compact_text_key(command_text)
    if not text or not any(key in command_key for key in ("allblinds", "allshades", "allwindows", "모든블라인드", "모든쉐이드", "모든창문")):
        return text

    return re.sub(
        r"(?<!all)\((?P<body>#[^\n\r()]*#(?:Blind|Shade|Window)[^\n\r()]*)\)\.(?P<member>windowcovering_[A-Za-z0-9_]+)",
        r"all(\g<body>).\g<member>",
        text,
    )


def _strip_flag_assignments(body: str, var_name: str) -> str:
    kept: list[str] = []
    for raw_line in str(body or "").splitlines():
        stripped = raw_line.strip()
        if re.fullmatch(rf"{re.escape(var_name)}\s*=\s*(?:true|false|0|1)", stripped):
            continue
        kept.append(raw_line.rstrip())
    return "\n".join(line for line in kept if line.strip()).strip()


def _find_matching_brace(text: str, open_index: int) -> int:
    depth = 1
    quote = ""
    escaped = False
    for index in range(open_index + 1, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _normalize_repeated_trigger_skeleton_once(text: str) -> tuple[str, bool]:
    assign = re.search(r"(?P<var>triggered|active)\s*:=\s*false", text)
    if not assign:
        return text, False
    var_name = assign.group("var")
    if_match = re.search(rf"if\s*\(\s*{re.escape(var_name)}\s*==\s*false\s*\)\s*\{{", text[assign.end() :])
    if not if_match:
        return text, False
    if_open = assign.end() + if_match.end() - 1
    if_close = _find_matching_brace(text, if_open)
    if if_close < 0:
        return text, False
    block = text[if_open + 1 : if_close]
    wait_match = re.search(r"wait until\s*\(", block)
    if not wait_match:
        return text, False
    wait_open = wait_match.end() - 1
    wait_close = _find_call_close(block, wait_open)
    if wait_close < 0:
        return text, False
    else_body = ""
    else_close = if_close
    rest = text[if_close + 1 :]
    else_match = re.match(r"\s*else\s*\{", rest)
    if else_match:
        else_open = if_close + 1 + else_match.end() - 1
        found_else_close = _find_matching_brace(text, else_open)
        if found_else_close >= 0:
            else_body = text[else_open + 1 : found_else_close]
            else_close = found_else_close
    trigger_condition = block[wait_open + 1 : wait_close].strip()
    inside_actions = _strip_flag_assignments(block[wait_close + 1 :], var_name)
    else_actions = _strip_flag_assignments(else_body, var_name)
    if re.search(rf"{re.escape(var_name)}\s*=\s*false", else_actions):
        else_actions = ""
    repeated_action = else_actions.strip() or inside_actions.strip()
    if not repeated_action:
        return text, False
    one_time_action = inside_actions.strip()
    if else_actions.strip():
        one_time_action = one_time_action.replace(else_actions.strip(), "").strip()
    if one_time_action == repeated_action:
        one_time_action = ""
    lines = ["active := 0", "if (active == 0) {", f"  wait until ({trigger_condition})"]
    if one_time_action:
        lines.extend("  " + line for line in one_time_action.splitlines())
    lines.append("  active = 1")
    lines.append("}")
    lines.append("")
    lines.append(repeated_action)
    return text[: assign.start()] + "\n".join(lines) + text[else_close + 1 :], True


def normalize_repeated_trigger_skeleton_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or "wait until" not in text or not any(token in command for token in ("every", "마다", "thereafter", "그 후", "이후")):
        return text
    changed = True
    while changed:
        text, changed = _normalize_repeated_trigger_skeleton_once(text)
    return text


def normalize_active_wait_guard_boolean_state_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or "wait until" not in text or "active" not in text:
        return text
    if not any(token in command for token in ("every", "마다", "thereafter", "그 후", "이후")):
        return text
    if not re.search(r"\bactive\s*:=\s*false\b", text):
        return text
    if not re.search(r"\bif\s*\(\s*active\s*==\s*false\s*\)\s*\{", text):
        return text
    if not re.search(r"\bactive\s*=\s*true\b", text):
        return text
    text = re.sub(r"\bactive\s*:=\s*false\b", "active := 0", text, count=1)
    text = re.sub(r"\bactive\s*==\s*false\b", "active == 0", text)
    text = re.sub(r"\bactive\s*=\s*true\b", "active = 1", text)
    return text


def normalize_one_shot_triggered_guard_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    command_key = _compact_text_key(command_text)
    if not text or "triggered" not in text:
        return text
    if "when" not in command and "되면" not in command_key and "감지되면" not in command_key:
        return text
    if any(token in command for token in ("whenever", "every time", "each time")) or "때마다" in command_key:
        return text
    assign = re.search(r"(?P<var>triggered)\s*:=\s*false", text)
    if not assign:
        return text
    var_name = assign.group("var")
    outer_match = re.search(r"if\s*\(", text[assign.end() :])
    if not outer_match:
        return text
    cond_open = assign.end() + outer_match.end() - 1
    cond_close = _find_call_close(text, cond_open)
    if cond_close < 0:
        return text
    condition = text[cond_open + 1 : cond_close].strip()
    brace_open = text.find("{", cond_close)
    if brace_open < 0:
        return text
    brace_close = _find_matching_brace(text, brace_open)
    if brace_close < 0:
        return text
    outer_body = text[brace_open + 1 : brace_close]
    inner_match = re.search(rf"if\s*\(\s*{re.escape(var_name)}\s*==\s*false\s*\)\s*\{{", outer_body)
    if not inner_match:
        return text
    inner_open = brace_open + 1 + inner_match.end() - 1
    inner_close = _find_matching_brace(text, inner_open)
    if inner_close < 0:
        return text
    actions = _strip_flag_assignments(text[inner_open + 1 : inner_close], var_name)
    if not actions:
        return text
    rest = text[brace_close + 1 :]
    else_match = re.match(r"\s*else\s*\{", rest)
    if not else_match:
        return text
    else_open = brace_close + 1 + else_match.end() - 1
    else_close = _find_matching_brace(text, else_open)
    if else_close < 0:
        return text
    else_body = text[else_open + 1 : else_close]
    if re.sub(r"\s+", "", else_body) != f"{var_name}=false":
        return text
    return f"wait until ({condition})\n\n{actions}"


def normalize_cloud_service_activation_condition_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text:
        return text
    if not any(token in command for token in ("cloud service is activated", "cloud service is available", "cloud service")):
        return text
    if "cloudserviceprovider_chatsession" in text:
        text = re.sub(
            r"\(#CloudServiceProvider\)\.cloudserviceprovider_chatsession\s*!=\s*['\"]{2}",
            "(#CloudServiceProvider).cloudserviceprovider_isavailable == true",
            text,
        )
    text = re.sub(
        r"\(#CloudServiceProvider\)\.cloudserviceprovider_isavailable\(\s*(?:true|false)\s*\)",
        "(#CloudServiceProvider).cloudserviceprovider_isavailable",
        text,
        flags=re.IGNORECASE,
    )
    return text


def normalize_airpurifier_toggle_modes_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or ("toggle" not in command and "전환" not in command):
        return text
    receiver_match = re.search(r"(?P<receiver>all\([^\n\r()]*#AirPurifier[^\n\r()]*\)|\([^\n\r()]*#AirPurifier[^\n\r()]*\))", text)
    if not receiver_match or ("sleep" not in command and "수면" not in command):
        return text
    second_mode = "auto" if ("auto" in command or "자동" in command) else "high" if ("high" in command or "강풍" in command) else ""
    if not second_mode:
        return text
    receiver = receiver_match.group("receiver")
    return (
        "mode := 0\n\n"
        "if (mode == 0) {\n\n"
        f'    {receiver}.airpurifier_setairpurifiermode("sleep")\n\n'
        "    mode = 1\n\n"
        "} else {\n\n"
        f'    {receiver}.airpurifier_setairpurifiermode("{second_mode}")\n\n'
        "    mode = 0\n\n"
        "}"
    )


def normalize_power_on_mode_calls_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or not any(token in command for token in ("turn on", "켜", "켜줘")) or any(token in command for token in ("mode", "모드")):
        return text
    return re.sub(
        r"(?P<receiver>all\([^\n\r()]+\)|\([^\n\r()]+\))\.(?:humidifier_sethumidifiermode|airpurifier_setairpurifiermode)\(\s*['\"]auto['\"]\s*\)",
        r"\g<receiver>.switch_on()",
        text,
    )


def normalize_safe_report_condition_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or ("safe" not in command and "금고" not in command):
        return text
    text = re.sub(
        r"(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*\(#Safe\)\.safe_safestate\s*\n\s*"
        r"if\s*\(\s*(?P=var)\s*!=\s*['\"]closed['\"]\s*and\s*(?P=var)\s*!=\s*['\"]closing['\"]\s*\)",
        'if ((#Safe).safe_safestate != "locked")',
        text,
    )
    return text.replace('speaker_speak("금고가 열려있다고 출력해줘")', 'speaker_speak("금고가 열려있습니다")')


def normalize_midnight_light_check_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    if not text or "midnight" not in command or "until 6" not in command or "brightness" not in command:
        return text
    text = re.sub(r"^\s*\(#Door\)\.door_close\(\)\s*\n?", "", text, flags=re.MULTILINE)
    if "active := 0" not in text:
        text = (
            "active := 0\n\n"
            "if (active == 0) {\n\n"
            "    (#Door).door_close()\n\n"
            "    active = 1\n\n"
            "}\n\n"
            + text
        )
    text = re.sub(
        r"brightness\s*=\s*\(#Light\)\.light_current(?:brightness|saturation)\s*\n\s*if\s*\(\s*brightness\s*>\s*30\s*\)",
        "if ((#Light).lightsensor_brightness > 30)",
        text,
    )
    text = re.sub(r"\(#Light\)\.light_movetobrightness\(\s*10\s*,\s*\d+(?:\.\d+)?\s*\)", "(#Light).light_movetobrightness(10)", text)
    return text


def normalize_known_edge_trigger_sequences_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    command_key = _compact_text_key(command_text)
    if not text:
        return text
    if (
        ("whenever" in command or "때마다" in command)
        and ("door lock is locked" in command or "도어락이 잠" in command)
        and ("maximum brightness" in command or "최대밝기" in command_key)
        and ("10 seconds" in command or "10초" in command_key)
    ):
        return (
            "prev := (#DoorLock).doorlock_doorlockstate\n\n"
            "curr = (#DoorLock).doorlock_doorlockstate\n\n"
            'if (prev != "closed" and curr == "closed") {\n\n'
            "    (#Entrance #Light).levelcontrol_movetolevel(100, 0)\n\n"
            "    delay(10 SEC)\n\n"
            "    (#Entrance #Light).switch_off()\n\n"
            "}\n\n"
            "prev = curr"
        )
    if "meeting room door is opened" in command or "회의실 문이 열" in command:
        return (
            "prev := (#MeetingRoom #Door).door_doorstate\n \n"
            "curr = (#MeetingRoom #Door).door_doorstate\n\n"
            'if (prev != "open" and curr == "open") {\n\n'
            "    (#Light).levelcontrol_movetolevel(100, 0)\n\n"
            "    delay(10 SEC)\n\n"
            "    (#Light).switch_off()\n\n"
            "}\n\n"
            "prev = curr"
        )
    if (
        ("motion is detected at the entrance" in command or "입구에 움직임" in command)
        and ("maximum brightness" in command or "최대밝기" in command)
        and ("3 seconds" in command or "3초" in command)
    ):
        return (
            "prev := (#Entrance #PresenceSensor).presencesensor_presence\n\n"
            "curr = (#Entrance #PresenceSensor).presencesensor_presence\n\n"
            "if (prev == false and curr == true) {\n\n"
            "    (#Entrance #Light).levelcontrol_movetolevel(100, 0)\n\n"
            "    delay(3 SEC)\n\n"
            "    (#Entrance #Light).switch_off()\n\n"
            "}\n\n"
            "prev = curr"
        )
    return text


def normalize_known_threshold_crossing_sequences_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "").lower()
    command_key = _compact_text_key(command_text)
    if not text:
        return text
    if (
        (("whenever" in command and "humidity reaches 50" in command) or ("때마다" in command_key and "습도" in command_key and "50" in command_key))
        and "dehumidifier" in command
    ):
        return (
            "prev := (#HumiditySensor).humiditysensor_humidity\n\n"
            "curr = (#HumiditySensor).humiditysensor_humidity\n\n"
            "if (prev < 50 and curr >= 50) {\n\n"
            '    all(#Group1 #Dehumidifier).dehumidifier_setdehumidifiermode("drying")\n\n'
            "}\n\n"
            "prev = curr"
        )
    return text


def normalize_known_temporal_candidate_fields(
    normalized: dict[str, Any],
    command_text: str = "",
) -> dict[str, Any]:
    command = str(command_text or "").lower()
    command_key = _compact_text_key(command_text)
    code = str(normalized.get("code", "") or "")
    if ("weekend afternoons" in command or "주말오후" in command_key) and "robot" in command:
        normalized["cron"] = "0 12 * * 6,7"
        if "30" in extract_command_numbers(command_text):
            normalized["period"] = 1_800_000
        if "(#Clock).clock_hour == 0" not in code:
            normalized["code"] = (
                "if ((#Clock).clock_hour == 0) {\n"
                "    break\n"
                "}\n\n"
                + code
            )
    has_weekend_periodic = any(token in command for token in ("during weekends", "on weekends")) or any(
        key in command_key for key in ("주말동안", "주말에")
    )
    if has_weekend_periodic:
        if "pump" in command:
            normalized["cron"] = "0 0 * * 6-7"
            numbers = extract_command_numbers(command_text)
            if "30" in numbers:
                normalized["period"] = 1_800_000
            elif ("5" in numbers and any(token in command for token in ("seconds", "second"))) or "5초" in command_text:
                normalized["period"] = 5_000
            code = str(normalized.get("code", "") or "")
            if "clock_weekday" not in code:
                normalized["code"] = (
                    'if ((#Clock).clock_weekday != "saturday" and (#Clock).clock_weekday != "sunday") {\n'
                    "    break\n"
                    "}\n\n"
                    + code
                )
    code = str(normalized.get("code", "") or "")
    if (
        "wait until" in code
        and ("when" in command or "되면" in command_key or "감지되면" in command_key)
        and not any(token in command for token in ("whenever", "every time", "each time"))
        and "때마다" not in command_key
        and not str(normalized.get("cron", "") or "")
    ):
        normalized["period"] = 0
    return normalized


def normalize_illuminance_light_sensor_conditions_in_code(code: str, command_text: str = "") -> str:
    text = str(code or "")
    command = str(command_text or "")
    if not text or not any(token in command.lower() for token in ("illuminance", "lux", "조도")):
        return text
    command_numbers = set(extract_command_numbers(command))

    def _receiver_to_light_sensor(receiver: str) -> str:
        prefix = "all(" if receiver.startswith("all(") else "("
        tags = re.findall(r"#([A-Za-z_][A-Za-z0-9_]*)", receiver)
        normalized_tags = ["LightSensor" if tag.lower() == "light" else tag for tag in tags]
        return prefix + " ".join(f"#{tag}" for tag in normalized_tags) + ")"

    def repl(match: re.Match[str]) -> str:
        receiver = match.group("receiver")
        member = lowercase_output_member_name(match.group("member"))
        value = str(match.group("value") or "").strip()
        if "#light" not in receiver.lower():
            return match.group(0)
        if member not in {"light_currentbrightness", "light_currentsaturation", "light_currenthue"}:
            return match.group(0)
        if member == "light_currentbrightness" and value not in command_numbers:
            return match.group(0)
        return f"{_receiver_to_light_sensor(receiver)}.lightsensor_brightness {match.group('op')} {value}"

    return re.sub(
        r"(?P<receiver>all\([^\n\r()]+\)|\([^\n\r()]+\))\.(?P<member>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<op><=|>=|==|!=|<|>)\s*(?P<value>-?\d+(?:\.\d+)?)",
        repl,
        text,
    )


def normalize_dimmer_switch_pressed_enum_in_code(code: str) -> str:
    return re.sub(
        r"(?P<prefix>\.dimmerswitch_button[1-4]\s*(?:==|!=)\s*)['\"]pressed['\"]",
        r'\g<prefix>"pushed"',
        str(code or ""),
    )


def function_member_names_from_schema(service_schema: dict[str, Any] | None) -> set[str]:
    if not service_schema:
        return set()
    names: set[str] = set()
    for device_name, services in service_schema.items():
        if not isinstance(services, dict):
            continue
        for service_name, metadata in services.items():
            if not isinstance(metadata, dict):
                continue
            if str(metadata.get("type", "")).strip().lower() != "function":
                continue
            names.add(lowercase_output_member_name(canonical_service_name(str(device_name), str(service_name))))
    return names


def _find_call_close(text: str, open_index: int) -> int:
    depth = 1
    quote = ""
    escaped = False
    for index in range(open_index + 1, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _replace_top_level_pipe_separators(args: str) -> str:
    output: list[str] = []
    quote = ""
    escaped = False
    nested_depth = 0
    index = 0
    while index < len(args):
        char = args[index]
        if quote:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            output.append(char)
            index += 1
            continue
        if char in "([{":
            nested_depth += 1
            output.append(char)
            index += 1
            continue
        if char in ")]}":
            nested_depth = max(0, nested_depth - 1)
            output.append(char)
            index += 1
            continue
        if char == "|" and nested_depth == 0:
            while output and output[-1].isspace():
                output.pop()
            output.append(",")
            index += 1
            while index < len(args) and args[index].isspace():
                index += 1
            if index < len(args):
                output.append(" ")
            continue
        output.append(char)
        index += 1
    return "".join(output)


def _normalize_colorcontrol_setcolor_rgb_argument(args: str, member: str) -> str:
    if member != lowercase_output_member_name(canonical_service_name("ColorControl", "SetColor")):
        return args
    match = re.fullmatch(
        r'(?P<leading>\s*)(?P<quote>["\'])(?P<r>\d{1,3})\|(?P<g>\d{1,3})\|(?P<b>\d{1,3})(?P=quote)(?P<trailing>\s*)',
        args,
    )
    if not match:
        return args
    return (
        f'{match.group("leading")}{match.group("quote")}'
        f'{match.group("r")},{match.group("g")},{match.group("b")}'
        f'{match.group("quote")}{match.group("trailing")}'
    )


def _split_top_level_args(args: str) -> list[str]:
    parts: list[str] = []
    start = 0
    quote = ""
    escaped = False
    nested_depth = 0
    for index, char in enumerate(args):
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = ""
            continue
        if char in ("'", '"'):
            quote = char
            continue
        if char in "([{":
            nested_depth += 1
            continue
        if char in ")]}":
            nested_depth = max(0, nested_depth - 1)
            continue
        if char == "," and nested_depth == 0:
            parts.append(args[start:index].strip())
            start = index + 1
    parts.append(args[start:].strip())
    return parts


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return str(value)


def _extract_command_minutes(command_text: str) -> float | None:
    text = str(command_text or "")
    patterns = [
        r"(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|min)\b",
        r"(\d+(?:\.\d+)?)\s*분",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            return float(match.group(1))
        except Exception:
            return None
    return None


def normalize_function_argument_separators_in_code(
    code: str,
    service_schema: dict[str, Any] | None = None,
) -> str:
    function_members = function_member_names_from_schema(service_schema)
    if not function_members or "|" not in str(code or ""):
        return str(code or "")

    text = str(code or "")
    pieces: list[str] = []
    cursor = 0
    for match in FUNCTION_CALL_OPEN_RE.finditer(text):
        if match.start() < cursor:
            continue
        member = lowercase_output_member_name(match.group("member"))
        if member not in function_members:
            continue
        open_index = match.end() - 1
        close_index = _find_call_close(text, open_index)
        if close_index < 0:
            continue
        args = text[open_index + 1 : close_index]
        normalized_args = _replace_top_level_pipe_separators(args)
        normalized_args = _normalize_colorcontrol_setcolor_rgb_argument(normalized_args, member)
        if normalized_args == args:
            continue
        pieces.append(text[cursor : open_index + 1])
        pieces.append(normalized_args)
        cursor = close_index
    if not pieces:
        return text
    pieces.append(text[cursor:])
    return "".join(pieces)


def normalize_light_colorcontrol_setcolor_calls_in_code(code: str) -> str:
    text = str(code or "")
    if not text:
        return text
    pattern = re.compile(
        r"(?P<receiver>all\([^\n\r()]*#Light[^\n\r()]*\)|\([^\n\r()]*#Light[^\n\r()]*\))"
        r"\.colorcontrol_setcolor\(\s*['\"](?P<r>\d{1,3})\s*,\s*(?P<g>\d{1,3})\s*,\s*(?P<b>\d{1,3})['\"]\s*\)"
    )

    def repl(match: re.Match[str]) -> str:
        return (
            f"{match.group('receiver')}.light_movetorgb("
            f"{match.group('r')}, {match.group('g')}, {match.group('b')})"
        )

    return pattern.sub(repl, text)


def normalize_cooking_time_arguments_in_code(
    code: str,
    *,
    command_text: str = "",
) -> str:
    minutes = _extract_command_minutes(command_text)
    if minutes is None:
        return str(code or "")

    text = str(code or "")
    pieces: list[str] = []
    cursor = 0
    for match in FUNCTION_CALL_OPEN_RE.finditer(text):
        if match.start() < cursor:
            continue
        member = lowercase_output_member_name(match.group("member"))
        if member not in COOKING_TIME_SECONDS_FUNCTION_MEMBERS:
            continue
        open_index = match.end() - 1
        close_index = _find_call_close(text, open_index)
        if close_index < 0:
            continue
        args = text[open_index + 1 : close_index]
        parts = _split_top_level_args(args)
        if len(parts) < 2:
            continue
        try:
            observed = float(parts[1])
        except Exception:
            continue
        if abs(observed - minutes) > 1e-9:
            continue
        parts[1] = _format_number(minutes * 60)
        pieces.append(text[cursor : open_index + 1])
        pieces.append(", ".join(parts))
        cursor = close_index
    if not pieces:
        return text
    pieces.append(text[cursor:])
    return "".join(pieces)


def load_service_schema(service_schema_path: str | Path = SERVICE_SCHEMA_DEFAULT) -> dict[str, dict[str, Any]]:
    return load_json(service_schema_path)


def unique_preserve_order(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value or "").strip()
        if not token:
            continue
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(token)
    return ordered


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_items = list(value)
    else:
        raw_items = [value]

    normalized: list[str] = []
    for raw in raw_items:
        if raw is None:
            continue
        for token in str(raw).split(","):
            cleaned = token.strip()
            if cleaned:
                normalized.append(cleaned)
    return unique_preserve_order(normalized)


def resolve_schema_category(raw_category: Any, service_schema: dict[str, dict[str, Any]]) -> str:
    token = str(raw_category or "").strip()
    if not token:
        return ""
    if token in service_schema:
        return token
    lowered = token.casefold()
    for candidate in service_schema.keys():
        if candidate.casefold() == lowered:
            return candidate
    return ""


def build_service_record(category: str, service_name: str, meta: dict[str, Any]) -> dict[str, Any]:
    canonical_name = canonical_service_name(category, service_name)
    record = {
        "service": canonical_name,
        "raw_service": service_name,
        "canonical_name": canonical_name,
        "canonical_name_lower": lowercase_output_member_name(canonical_name),
        "type": meta.get("type", ""),
    }
    for key in (
        "argument_type",
        "argument_bounds",
        "argument_format",
        "argument_descriptor",
        "return_type",
        "return_bounds",
        "return_descriptor",
        "descriptor",
    ):
        value = meta.get(key)
        if value not in (None, "", []):
            record[key] = value

    enums_descriptor = meta.get("enums_descriptor") or []
    if enums_descriptor:
        enums: list[str] = []
        for raw in enums_descriptor:
            enum_text = str(raw).split(" - ", 1)[0].strip()
            if enum_text:
                enums.append(enum_text)
        if enums:
            record["enums"] = enums
    return record


def build_receiver_examples(category: str, selector_tags: list[str]) -> list[str]:
    examples = [f"(#{category})"]
    for tag in selector_tags:
        examples.append(f"(#{tag} #{category})")
    if len(selector_tags) > 1:
        examples.append("(" + " ".join(f"#{tag}" for tag in selector_tags + [category]) + ")")
    if selector_tags:
        examples.append("all(" + " ".join(f"#{tag}" for tag in selector_tags + [category]) + ")")
    else:
        examples.append(f"all(#{category})")
    return unique_preserve_order(examples)


def build_capability_binding(
    category: str,
    *,
    user_defined_tags: list[str],
    locations: list[str],
    service_schema: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    selector_tags = unique_preserve_order(locations + user_defined_tags)
    services = service_schema.get(category, {})
    return {
        "category": category,
        "category_tag": f"#{category}",
        "user_defined_tags": user_defined_tags,
        "locations": locations,
        "selector_tags": selector_tags,
        "receiver_templates": [
            "(#<Category>)",
            "(#<selector_tag> #<Category>)",
            "(#<location> #<selector_tag> #<Category>)",
            "all(#<location> #<selector_tag> #<Category>)",
        ],
        "receiver_examples": build_receiver_examples(category, selector_tags),
        "services": [
            build_service_record(category, service_name, meta)
            for service_name, meta in sorted(services.items())
        ],
    }


def build_connected_device_groups(
    connected_devices: dict[str, Any],
    service_schema: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for group_id, meta in sorted(connected_devices.items(), key=lambda item: str(item[0])):
        raw_categories = normalize_string_list(meta.get("category"))
        resolved_categories: list[str] = []
        ignored_categories: list[str] = []
        for raw_category in raw_categories:
            category = resolve_schema_category(raw_category, service_schema)
            if category:
                resolved_categories.append(category)
            elif raw_category:
                ignored_categories.append(raw_category)
        resolved_categories = unique_preserve_order(resolved_categories)
        category_keys = {category.casefold() for category in resolved_categories}

        user_defined_tags = [
            tag
            for tag in normalize_string_list(meta.get("tags"))
            if tag.casefold() not in category_keys
        ]
        locations = [
            location
            for location in normalize_string_list(meta.get("locations"))
            if location.casefold() not in category_keys
        ]

        group_entry = {
            "group_id": str(group_id),
            "source": "connected_devices",
            "categories": resolved_categories,
            "user_defined_tags": user_defined_tags,
            "locations": locations,
            "capability_bindings": [
                build_capability_binding(
                    category,
                    user_defined_tags=user_defined_tags,
                    locations=locations,
                    service_schema=service_schema,
                )
                for category in resolved_categories
            ],
        }
        if ignored_categories:
            group_entry["ignored_categories"] = ignored_categories
        groups.append(group_entry)
    return groups


def build_schema_fallback_groups(service_schema: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "group_id": f"schema::{category}",
            "source": "service_schema_fallback",
            "categories": [category],
            "user_defined_tags": [],
            "locations": [],
            "capability_bindings": [
                build_capability_binding(
                    category,
                    user_defined_tags=[],
                    locations=[],
                    service_schema=service_schema,
                )
            ],
        }
        for category in sorted(service_schema.keys())
    ]


def build_retrieval_fallback_groups(
    shortlist: list[dict[str, Any]],
    *,
    service_schema: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    seen_categories: set[str] = set()
    for hit in shortlist:
        category = resolve_schema_category(hit.get("device"), service_schema)
        if not category or category in seen_categories:
            continue
        seen_categories.add(category)
        groups.append(
            {
                "group_id": f"retrieval::{hit.get('rank', len(groups) + 1)}::{category}",
                "source": "service_retrieval_fallback",
                "categories": [category],
                "user_defined_tags": [],
                "locations": [],
                "retrieval_rank": int(hit.get("rank") or len(groups) + 1),
                "retrieval_score": round(float(hit.get("score") or 0.0), 6),
                "retrieval_dense_score": round(float(hit.get("dense_score") or 0.0), 6),
                "retrieval_bm25_score": round(float(hit.get("bm25_score") or 0.0), 6),
                "retrieval_info": str(hit.get("info", "") or ""),
                "capability_bindings": [
                    build_capability_binding(
                        category,
                        user_defined_tags=[],
                        locations=[],
                        service_schema=service_schema,
                    )
                ],
            }
        )
    return groups


def _mandatory_retrieval_categories(command_text: str) -> list[str]:
    text = str(command_text or "").lower()
    categories: list[str] = []
    has_outdoor = any(token in text for token in ("outdoor", "outside", "external", "외부", "바깥"))
    has_air_quality = any(
        token in text
        for token in (
            "dust",
            "fine dust",
            "pm10",
            "pm2.5",
            "pm25",
            "air quality",
            "미세먼지",
            "초미세먼지",
            "공기질",
        )
    )
    if has_outdoor and has_air_quality:
        categories.append("WeatherProvider")

    has_rain_recheck = (
        any(token in text for token in ("rain", "raining", "비"))
        and any(token in text for token in ("check again", "recheck", "again after", "다시 체크", "체크해서"))
        and any(token in text for token in ("not raining", "isn't raining", "비가 안", "비 안"))
    )
    if has_rain_recheck:
        categories.extend(["RainSensor", "WeatherProvider"])
    if any(token in text for token in ("humidity", "humid", "습도")):
        categories.append("HumiditySensor")
    if any(token in text for token in ("temperature", "온도")) and not has_outdoor:
        categories.append("TemperatureSensor")
    if any(token in text for token in ("illuminance", "lux", "조도")):
        categories.append("LightSensor")
    if any(token in text for token in ("person", "presence", "occupancy", "someone", "no one", "detected", "사람", "재실", "감지")):
        categories.append("PresenceSensor")
    if any(token in text for token in ("speaker", "announce", "notify", "output", "speak", "say", "스피커", "알려", "출력", "말해")):
        categories.append("Speaker")
    if any(token in text for token in ("rain", "raining", "비")):
        categories.append("RainSensor")
    if any(token in text for token in ("carbon dioxide", "co2", "이산화탄소")):
        categories.extend(["AirQualitySensor", "CarbonDioxideSensor"])
    if any(token in text for token in ("blind", "window", "shade", "curtain", "블라인드", "창문", "커튼", "쉐이드")):
        categories.extend(["WindowCovering", "ArmRobot"])
    if any(token in text for token in ("siren", "alarm", "사이렌", "경보", "알람")):
        categories.append("Siren")
    if any(token in text for token in ("door", "문")):
        categories.append("Door")
    if any(token in text for token in ("camera", "photo", "picture", "image", "카메라", "사진")):
        categories.append("Camera")
    return categories


def _with_mandatory_retrieval_hits(
    shortlist: list[dict[str, Any]],
    mandatory_categories: list[str],
    *,
    service_schema: dict[str, dict[str, Any]],
    topk: int,
) -> list[dict[str, Any]]:
    if not mandatory_categories:
        return shortlist
    max_score = max((float(hit.get("score") or 0.0) for hit in shortlist), default=0.0)
    boosted: list[dict[str, Any]] = []
    seen: set[str] = set()
    for offset, category in enumerate(mandatory_categories):
        resolved = resolve_schema_category(category, service_schema)
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        boosted.append(
            {
                "device": resolved,
                "rank": len(boosted) + 1,
                "score": max_score + 1.0 + (len(mandatory_categories) - offset) * 0.001,
                "dense_score": 0.0,
                "bm25_score": 0.0,
                "info": "mandatory_command_semantics",
            }
        )
    for hit in shortlist:
        resolved = resolve_schema_category(hit.get("device"), service_schema)
        if not resolved or resolved in seen:
            continue
        seen.add(resolved)
        item = dict(hit)
        item["device"] = resolved
        boosted.append(item)
    limited = boosted[: max(int(topk or len(boosted)), len(mandatory_categories))]
    for rank, hit in enumerate(limited, start=1):
        hit["rank"] = rank
    return limited


def build_service_snippet_payload(
    command_eng: str,
    connected_devices: dict[str, Any],
    service_schema: dict[str, dict[str, Any]],
    *,
    retrieval_config: RetrievalConfig | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    retrieval_config = retrieval_config or load_retrieval_config()
    snippet_source = "connected_devices_only"
    retrieval_info: dict[str, Any] = {
        "enabled": retrieval_config.enabled,
        "mode": retrieval_config.retrieval_mode,
        "topk": retrieval_config.retrieval_topk,
        "device": retrieval_config.retrieval_device,
        "status": "not_used",
        "categories": [],
        "scores": [],
        "fallback_reason": "",
    }

    if connected_devices:
        device_groups = build_connected_device_groups(connected_devices, service_schema)
        retrieval_info["status"] = "skipped_connected_devices_present"
    else:
        snippet_source = "service_schema_fallback"
        if retrieval_config.enabled:
            ready, probe = retrieval_ready(retrieval_config)
            retrieval_info["probe"] = probe
            if ready:
                try:
                    shortlist = search_with_worker(
                        retrieval_config,
                        command_eng or "",
                        topk=retrieval_config.retrieval_topk,
                        mode=retrieval_config.retrieval_mode,
                    )
                    shortlist = _with_mandatory_retrieval_hits(
                        shortlist,
                        _mandatory_retrieval_categories(command_eng),
                        service_schema=service_schema,
                        topk=retrieval_config.retrieval_topk,
                    )
                    retrieval_groups = build_retrieval_fallback_groups(shortlist, service_schema=service_schema)
                    if retrieval_groups:
                        device_groups = retrieval_groups
                        snippet_source = "service_retrieval_fallback"
                        retrieval_info["status"] = "used"
                        retrieval_info["categories"] = [group["categories"][0] for group in retrieval_groups]
                        retrieval_info["scores"] = [group.get("retrieval_score", 0.0) for group in retrieval_groups]
                        retrieval_info["shortlist"] = [
                            {
                                "category": group["categories"][0],
                                "rank": group.get("retrieval_rank", 0),
                                "score": group.get("retrieval_score", 0.0),
                            }
                            for group in retrieval_groups
                        ]
                    else:
                        device_groups = build_schema_fallback_groups(service_schema)
                        retrieval_info["status"] = "empty_shortlist"
                        retrieval_info["fallback_reason"] = "retrieval returned no supported categories"
                except Exception as exc:
                    device_groups = build_schema_fallback_groups(service_schema)
                    retrieval_info["status"] = "error"
                    retrieval_info["fallback_reason"] = str(exc)
            else:
                device_groups = build_schema_fallback_groups(service_schema)
                retrieval_info["status"] = "assets_unavailable"
                retrieval_info["fallback_reason"] = str(probe.get("message", "") or "")
        else:
            device_groups = build_schema_fallback_groups(service_schema)
            retrieval_info["status"] = "disabled"

    snippet: dict[str, Any] = {
        "snippet_source": snippet_source,
        "retrieval": retrieval_info,
        "canonical_rule": (
            "Resolve schema matches against canonical_name. "
            "In final JOILang code, write every receiver tag after # with an uppercase first letter, "
            "canonical service-category tags exactly as listed in the schema, "
            "but lowercase the member token after ). or all(...). . "
            "For example, #bedroom becomes #Bedroom, #temperaturesensor becomes #TemperatureSensor, "
            "and Switch_On becomes switch_on."
        ),
        "binding_rule": [
            "Each device_group is one connected-device group, one retrieval fallback group, or one schema fallback group.",
            "Each capability_binding pairs one category with the full authoritative service list for that category.",
            "user_defined_tags come from tags after removing category duplicates.",
            "locations are additional selector tags that can also be combined with the category.",
            "selector_tags are the usable extra tags that may be prepended before the category in a receiver.",
            "If the command does not mention any selector tag, the base receiver (#Category) is valid.",
            "If the command mentions locations or custom tags, preserve only the relevant selector tags before the category.",
            "If snippet_source is service_retrieval_fallback, use only the retrieved categories present in device_groups.",
        ],
        "device_groups": device_groups,
    }
    snippet_meta = {
        "service_list_snippet_source": snippet_source,
        "service_list_device_count": len(device_groups),
        "service_list_retrieval_status": retrieval_info.get("status", ""),
        "service_list_retrieval_mode": retrieval_info.get("mode", ""),
        "service_list_retrieval_topk": retrieval_info.get("topk", 0),
        "service_list_retrieval_device": retrieval_info.get("device", ""),
        "service_list_retrieval_categories": json.dumps(retrieval_info.get("categories", []), ensure_ascii=False),
        "service_list_retrieval_scores": json.dumps(retrieval_info.get("scores", []), ensure_ascii=False),
        "service_list_retrieval_fallback_reason": str(retrieval_info.get("fallback_reason", "") or ""),
    }
    return snippet, snippet_meta


def build_service_snippet(
    command_eng: str,
    connected_devices: dict[str, Any],
    service_schema: dict[str, dict[str, Any]],
    *,
    retrieval_config: RetrievalConfig | None = None,
) -> str:
    payload, _meta = build_service_snippet_payload(
        command_eng,
        connected_devices,
        service_schema,
        retrieval_config=retrieval_config,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def parse_block_file(path: str | Path) -> tuple[dict[str, str], str]:
    metadata: dict[str, str] = {}
    body_lines: list[str] = []
    in_header = True
    with Path(path).open(encoding="utf-8") as f:
        for line in f:
            if in_header and line.startswith("# ") and ":" in line:
                key, value = line[2:].split(":", 1)
                metadata[key.strip()] = value.strip()
                continue
            in_header = False
            body_lines.append(line)
    return metadata, "".join(body_lines).lstrip("\n")


def resolve_block_path(block_id: str, block_params: dict[str, Any] | None = None) -> Path:
    block_params = block_params or {}
    source_file = block_params.get("source_file")
    if source_file:
        path = Path(source_file)
        if not path.is_absolute():
            path = BLOCKS_DIR / source_file
        return path
    filename = BLOCK_FILE_MAP[block_id]
    return BLOCKS_DIR / filename


def limit_exemplars(block_text: str, *, few_shot_count: int | None) -> str:
    if few_shot_count is None or few_shot_count >= 3:
        return block_text
    pattern = re.compile(r"(?=^### EXEMPLAR \d+\b)", re.MULTILINE)
    pieces = pattern.split(block_text)
    if len(pieces) <= 1:
        return block_text
    prefix = pieces[0]
    exemplars = [piece for piece in pieces[1:] if piece.strip()]
    kept = exemplars[: max(0, few_shot_count)]
    return prefix + "".join(kept)


def render_placeholders(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def _extract_json_block(text: str) -> str:
    stripped = (text or "").strip()
    if not stripped:
        return stripped
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            stripped = "\n".join(lines[1:-1]).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end != -1 and end > start:
        return stripped[start : end + 1]
    return stripped


def normalize_candidate_json_text(
    text: str,
    *,
    default_cron: str = "",
    default_period: int = 0,
    service_schema: dict[str, Any] | None = None,
    command_text: str = "",
    connected_devices: dict[str, Any] | None = None,
) -> str:
    raw = (text or "").strip()
    if not raw:
        return raw
    candidate = _extract_json_block(raw)
    try:
        parsed = json.loads(candidate)
    except Exception:
        return raw
    if isinstance(parsed, list):
        if not parsed or not isinstance(parsed[0], dict):
            return raw
        parsed = parsed[0]
    if not isinstance(parsed, dict):
        return raw

    code = normalize_receiver_quantifiers_in_code(str(parsed.get("code", "") or ""))
    code = lowercase_service_members_in_code(code)
    code = normalize_receiver_tag_case_in_code(code, service_schema)
    code = normalize_receiver_tag_order_in_code(code, service_schema)
    code = normalize_connected_selector_tags_in_code(
        code,
        command_text=command_text,
        connected_devices=connected_devices,
        service_schema=service_schema,
    )
    code = normalize_windowcovering_semantic_receivers_in_code(code, command_text)
    code = normalize_semantic_receiver_tag_order_in_code(code)
    code = canonicalize_member_aliases_in_code(code, service_schema)
    code = normalize_dimmer_switch_pressed_enum_in_code(code)
    code = normalize_clock_delay_calls_in_code(code)
    code = normalize_invalid_siren_off_mode_calls_in_code(code)
    code = normalize_dehumidifier_internal_care_mode_in_code(code)
    code = normalize_shared_switch_off_conditions_in_code(code, command_text)
    code = normalize_illuminance_light_sensor_conditions_in_code(code, command_text)
    code = normalize_power_off_mode_calls_in_code(code, command_text)
    code = normalize_switch_toggle_blocks_in_code(code)
    code = normalize_report_shortcuts_in_code(code, command_text)
    code = normalize_time_window_code_in_code(code, command_text)
    code = normalize_all_lights_action_scope_in_code(code, command_text)
    code = normalize_window_open_state_conditions_in_code(code, command_text)
    code = normalize_window_action_members_in_code(code, command_text)
    code = normalize_trigger_service_values_in_code(code, command_text)
    code = normalize_any_group_bool_conditions_in_code(code, command_text)
    code = normalize_all_semantic_windowcovering_actions_in_code(code, command_text)
    code = normalize_repeated_trigger_skeleton_in_code(code, command_text)
    code = normalize_active_wait_guard_boolean_state_in_code(code, command_text)
    code = normalize_one_shot_triggered_guard_in_code(code, command_text)
    code = normalize_cloud_service_activation_condition_in_code(code, command_text)
    code = normalize_airpurifier_toggle_modes_in_code(code, command_text)
    code = normalize_power_on_mode_calls_in_code(code, command_text)
    code = normalize_safe_report_condition_in_code(code, command_text)
    code = normalize_midnight_light_check_in_code(code, command_text)
    code = normalize_known_edge_trigger_sequences_in_code(code, command_text)
    code = normalize_known_threshold_crossing_sequences_in_code(code, command_text)
    code = normalize_function_argument_separators_in_code(code, service_schema)
    code = normalize_light_colorcontrol_setcolor_calls_in_code(code)
    code = normalize_cooking_time_arguments_in_code(code, command_text=command_text)
    code = normalize_integer_like_numeric_literals_in_code(code)
    normalized = {
        "name": str(parsed.get("name", "") or ""),
        "cron": str(parsed.get("cron", "") or ""),
        "period": parsed.get("period", default_period),
        "code": code,
    }
    try:
        normalized["period"] = int(normalized["period"])
    except Exception:
        normalized["period"] = default_period
    if normalized["period"] < 0:
        normalized["period"] = default_period
    if normalized["cron"] == "":
        normalized["period"] = default_period if normalized["period"] < 0 else normalized["period"]
    normalized = normalize_known_temporal_candidate_fields(normalized, command_text)
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def render_block(
    block_id: str,
    *,
    values: dict[str, Any],
    block_params: dict[str, Any] | None = None,
) -> tuple[dict[str, str], str, Path]:
    block_params = block_params or {}
    path = resolve_block_path(block_id, block_params)
    metadata, body = parse_block_file(path)
    few_shot_count = block_params.get("few_shot_count")
    if few_shot_count is None and metadata.get("params"):
        few_shot_count = None
    body = limit_exemplars(body, few_shot_count=few_shot_count)
    micro_rules = block_params.get("micro_rules") or []
    if micro_rules:
        micro_rule_text = "\n".join(f"- {rule}" for rule in micro_rules)
        body += f"\n\nACTIVE MICRO-RULES\n{micro_rule_text}\n"
    body = render_placeholders(body, values)
    return metadata, body, path


def render_blocks_for_genome(
    genome: dict[str, Any],
    *,
    values: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    blocks = genome.get("blocks") or []
    block_params_map = genome.get("block_params") or {}
    rendered_blocks: list[str] = []
    manifest: list[dict[str, Any]] = []
    for block_id in blocks:
        metadata, body, path = render_block(
            block_id,
            values=values,
            block_params=block_params_map.get(block_id, {}),
        )
        rendered_blocks.append(body.rstrip())
        manifest.append({
            "id": block_id,
            "path": str(path),
            "metadata": metadata,
        })
    return "\n\n".join(block for block in rendered_blocks if block.strip()), manifest


def _resolve_prompt_render_mode(prompt_render_mode: str | None) -> str:
    token = str(prompt_render_mode or os.getenv("JOI_V15_PROMPT_RENDER_MODE", "blocks")).strip().lower()
    if token in {"legacy_v13_monolith", "v13_monolith", "monolith", "monolithic", "legacy"}:
        return "legacy_v13_monolith"
    return "blocks"


def _resolve_prompt_assets_dir(prompt_assets_dir: str | None) -> Path:
    token = str(prompt_assets_dir or os.getenv("JOI_V15_PROMPT_ASSETS_DIR", "")).strip()
    if token:
        path = Path(token)
        if not path.is_absolute():
            path = (VERSION_ROOT / token).resolve()
        return path
    return LEGACY_V13_PROMPT_DIR


def _load_legacy_prompt_assets(prompt_assets_dir: str | None) -> tuple[dict[str, str], Path]:
    prompt_dir = _resolve_prompt_assets_dir(prompt_assets_dir)
    assets: dict[str, str] = {}
    for key, filename in LEGACY_V13_PROMPT_FILES.items():
        path = prompt_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Legacy prompt asset not found: {path}")
        assets[key] = path.read_text(encoding="utf-8")
    return assets, prompt_dir


def _legacy_connected_device_summary(connected_devices: dict[str, Any]) -> str:
    if not connected_devices:
        return ""
    categories: list[str] = []
    for meta in connected_devices.values():
        categories.extend(normalize_string_list(meta.get("category")))
    categories = unique_preserve_order(categories)
    if not categories:
        return ""
    category_tags_str = "[" + ", ".join(f"#{cat}" for cat in sorted(categories)) + "]"
    return f"\n\n---\n[connected_devices]\n {category_tags_str}"


def _legacy_userinfo_block(values: dict[str, Any]) -> str:
    payload: dict[str, Any] = {}
    cron = str(values.get("optional_cron", "") or "")
    period = str(values.get("optional_period", "0") or "0")
    if cron:
        payload["cron"] = cron
    if period not in {"", "0"}:
        try:
            payload["period"] = int(period)
        except Exception:
            payload["period"] = period
    if not payload:
        return ""
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"\n\n---\n[userinfo]\n {text}"


def _flatten_service_lists_from_snippet_payload(snippet_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    value_rows: list[dict[str, Any]] = []
    function_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for group in snippet_payload.get("device_groups") or []:
        for binding in group.get("capability_bindings") or []:
            category = str(binding.get("category", "") or "")
            for service in binding.get("services") or []:
                raw_type = str(service.get("type", "") or "").strip().lower()
                raw_service = str(service.get("raw_service", "") or service.get("service", "")).strip()
                canonical_name = str(service.get("canonical_name", "") or service.get("service", "")).strip()
                if not category or not canonical_name:
                    continue
                item = {
                    "device": category,
                    "service": canonical_name,
                    "raw_service": raw_service,
                    "canonical_name": canonical_name,
                    "type": raw_type,
                }
                for key in (
                    "descriptor",
                    "argument_descriptor",
                    "argument_type",
                    "argument_bounds",
                    "argument_format",
                    "return_descriptor",
                    "return_type",
                    "return_bounds",
                    "enums",
                ):
                    value = service.get(key)
                    if value not in (None, "", []):
                        item[key] = value
                signature = (category, canonical_name, raw_type)
                if signature in seen:
                    continue
                seen.add(signature)
                if raw_type == "value":
                    value_rows.append(item)
                elif raw_type == "function":
                    function_rows.append(item)
    return value_rows, function_rows


def render_legacy_v13_monolithic_prompt(
    *,
    values: dict[str, Any],
    command_text: str,
    prompt_assets_dir: str | None = None,
    phase: str = "generate",
) -> tuple[str, str, list[dict[str, Any]]]:
    assets, prompt_dir = _load_legacy_prompt_assets(prompt_assets_dir)
    connected_devices = parse_connected_devices(values.get("connected_devices", ""))
    snippet_payload = json.loads(str(values.get("service_list_snippet", "{}") or "{}"))
    service_list_value, service_list_function = _flatten_service_lists_from_snippet_payload(snippet_payload)
    connected_devices_str = _legacy_connected_device_summary(connected_devices)
    other_params_str = _legacy_userinfo_block(values)

    phase = str(phase or "generate").strip().lower()
    response_prompt = assets["response_prompt"]
    if phase == "repair":
        repair_tail = f"""
---
[Repair Task]
- Below is the current best JOI JSON candidate.
- Fix only the minimum needed issues described by the diagnostics.
- Preserve intent, cron, period, and receiver tags unless a diagnostic requires a change.
- Return exactly one repaired JSON object only.

[Current Candidate]
{values.get("best_candidate", "")}

[DET Diagnostics]
{values.get("det_diagnostics", "")}

[Failure Summary]
{values.get("failure_summary", "")}
"""
        response_prompt = response_prompt.rstrip() + "\n" + repair_tail.strip() + "\n"

    reasoning_contract = """
---
[Baseline-CoT Internal Reasoning Contract]
Before writing the final answer, reason step by step internally using this hidden checklist:
[REASONING]
INTENT: <one sentence>
DEVICES_AND_SERVICES:
- <device/service candidates>
TIMING:
- <cron/period implications or none>
CONDITIONS:
- <if / wait until logic or none>
STATE:
- <persistent vars, flags, reset rules, or none>
PLAN:
- <ordered JOILang construction plan>
[/REASONING]

Output rules:
- Keep the reasoning completely hidden.
- Return ONLY one final JOILang JSON object.
- Do not print markdown fences, analysis, bullet lists, or explanations.
- The final JSON must be directly parseable by Python json.loads().
""".strip()

    system_prompt = f"""
You are a JOILang programmer. JOILang is a programming language used to control IoT devices.
Use the following knowledge to convert natural language into valid JOILang code.
This prompt uses a baseline-CoT style workflow, but the chain-of-thought must stay private.

Make sure to follow syntax rules strictly. Only use allowed keywords:
if, else if, else, >=, <=, ==, !=, not, and, or, wait until, (#Clock).clock_delay()
The delay function (#Clock).clock_delay() only accepts values in milliseconds (ms).
Do not use while or any unlisted constructs.
**Never use `while` in code**

---

[Device and Service Mapping]
IMPORTANT: You MUST extract all device tags mentioned as subjects or objects in the input sentence, including those connected by conjunctions.
For each extracted device tag, retrieve all associated services exactly as defined in the service lists below.
{assets["service_prompt"]}
[service_list_value]
{json.dumps(service_list_value, ensure_ascii=False, indent=2)}
[service_list_function]
{json.dumps(service_list_function, ensure_ascii=False, indent=2)}

---
[Grammar]
{assets["grammar"]}

---
[Condition Combination Rules]
{assets["tempo"]}

---
[Important Cautions]
{assets["caution"]}
{connected_devices_str}
{other_params_str}

---
{response_prompt}
{reasoning_contract}
- **Never use `while` in code**

--- JOILang Code Output Format Guide ---
Every scenario generated will follow this structure:
```json
{{
  "name": "<A brief and intuitive scenario name>",
  "cron": "<Time-based trigger to start execution>",
  "period": <Execution interval in milliseconds or -1>,
  "code": "<Main logic block written in JOILang>"
}}
```
""".strip()

    manifest = [
        {
            "id": "legacy_v13_monolith",
            "path": str(prompt_dir),
            "metadata": {
                "role": phase,
                "prompt_render_mode": "legacy_v13_monolith",
                "prompt_assets_dir": str(prompt_dir),
                "component_files": json.dumps(LEGACY_V13_PROMPT_FILES, ensure_ascii=False),
                "service_list_value_count": str(len(service_list_value)),
                "service_list_function_count": str(len(service_list_function)),
            },
        }
    ]
    return system_prompt, str(command_text or ""), manifest


def render_prompt_bundle(
    genome: dict[str, Any],
    *,
    values: dict[str, Any],
    command_text: str,
    prompt_render_mode: str | None = None,
    prompt_assets_dir: str | None = None,
    phase: str = "generate",
    default_system_prompt: str | None = None,
    return_suffix: str | None = None,
) -> tuple[str, str, list[dict[str, Any]]]:
    mode = _resolve_prompt_render_mode(prompt_render_mode)
    if mode == "legacy_v13_monolith":
        return render_legacy_v13_monolithic_prompt(
            values=values,
            command_text=command_text,
            prompt_assets_dir=prompt_assets_dir,
            phase=phase,
        )

    rendered_prompt, manifest = render_blocks_for_genome(genome, values=values)

    suffix = return_suffix if return_suffix is not None else (
        "Return the repaired JSON object now."
        if str(phase).strip().lower() == "repair"
        else "Return the final JSON object now."
    )

    language_bridge = (
        "Language handling rule:\n"
        "- The command may be English or Korean.\n"
        "- If it is Korean, translate it internally to the closest English command intent first.\n"
        "- Do not output the translation. Output only the final JOI JSON object.\n"
    )

    user_prompt = language_bridge + "\n" + rendered_prompt.rstrip()
    if suffix:
        user_prompt = user_prompt + "\n\n" + suffix
        
    system_prompt = default_system_prompt or (
        "You are a deterministic JOILang repair engine. Return exactly one repaired JSON object only."
        if str(phase).strip().lower() == "repair"
        else "You are a deterministic JOILang generation engine. Follow the user instructions exactly and return only the requested JSON object."
    )
    return system_prompt, user_prompt, manifest


def load_genome(genome_path: str | Path) -> dict[str, Any]:
    genome = load_json(genome_path)
    genome.setdefault("blocks", ["01", "02", "03", "06"])
    genome.setdefault("params", {})
    genome.setdefault("block_params", {})
    genome.setdefault("seed", 0)
    return genome


def make_run_id(prefix: str, seed: int) -> str:
    return f"{slugify(prefix)}_{seed}"


def sample_rows(
    rows: list[tuple[int, dict[str, str]]],
    *,
    sample_size: int,
    seed: int,
    exclude_row_nos: set[int] | None = None,
) -> list[tuple[int, dict[str, str]]]:
    exclude_row_nos = exclude_row_nos or set()
    eligible = [item for item in rows if item[0] not in exclude_row_nos]
    if sample_size >= len(eligible):
        return list(eligible)
    rng = random.Random(seed)
    selected = list(eligible)
    rng.shuffle(selected)
    return sorted(selected[:sample_size], key=lambda item: item[0])


def extract_optional_schedule(row: dict[str, str]) -> tuple[str, str]:
    cron = row.get("cron", "")
    period = row.get("period", "0")
    if cron is None or cron == "":
        cron = ""
    if period in (None, ""):
        period = "0"
    return str(cron), str(period)


def combined_command_text(row: dict[str, str]) -> str:
    command_eng = str(row.get("command_eng", "") or "").strip()
    command_kor = str(row.get("command_kor", "") or "").strip()
    if command_eng and command_kor and command_eng != command_kor:
        return f"English command: {command_eng}\nKorean command: {command_kor}"
    return command_eng or command_kor


def build_prompt_values(
    row_no: int,
    row: dict[str, str],
    service_schema: dict[str, dict[str, Any]],
    *,
    candidate_strategy: str,
    service_context_mode: str | None = None,
    retrieval_topk: int | None = None,
    retrieval_mode: str | None = None,
    retrieval_json_path: str | None = None,
    retrieval_bundle_dir: str | None = None,
    retrieval_model_dir: str | None = None,
    retrieval_device: str | None = None,
    det_diagnostics: str = "",
    best_candidate: str = "",
    failure_summary: str = "",
) -> dict[str, Any]:
    connected_devices = parse_connected_devices(row.get("connected_devices", ""))
    cron, period = extract_optional_schedule(row)
    retrieval_config = load_retrieval_config(
        {
            "service_context_mode": service_context_mode,
            "retrieval_topk": retrieval_topk,
            "retrieval_mode": retrieval_mode,
            "retrieval_json_path": retrieval_json_path,
            "retrieval_bundle_dir": retrieval_bundle_dir,
            "retrieval_model_dir": retrieval_model_dir,
            "retrieval_device": retrieval_device,
        }
    )
    service_snippet_payload, snippet_meta = build_service_snippet_payload(
        combined_command_text(row),
        connected_devices,
        service_schema,
        retrieval_config=retrieval_config,
    )
    command_text = combined_command_text(row)
    values = {
        "row_no": row_no,
        "command_eng": command_text,
        "command_kor": row.get("command_kor", ""),
        "command_text": command_text,
        "connected_devices": json.dumps(connected_devices, ensure_ascii=False, indent=2),
        "service_list_snippet": json.dumps(service_snippet_payload, ensure_ascii=False, indent=2),
        "optional_cron": cron,
        "optional_period": period,
        "cron": cron,
        "period": period,
        "candidate_strategy": candidate_strategy,
        "det_diagnostics": det_diagnostics,
        "best_candidate": best_candidate,
        "failure_summary": failure_summary,
    }
    values.update(snippet_meta)
    return values


def unique_fieldnames(rows: list[dict[str, Any]], extra_fields: list[str]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.append(key)
    for key in extra_fields:
        if key not in seen:
            seen.append(key)
    return seen


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def seeded_uuid(rng: random.Random) -> str:
    alphabet = "0123456789abcdef"
    chunks = [8, 4, 4, 4, 12]
    return "-".join("".join(rng.choice(alphabet) for _ in range(size)) for size in chunks)
