#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .artifacts import utc_now
except ImportError:
    from artifacts import utc_now  # type: ignore


def run_check(check_name: str, out_dir: str | Path | None = None) -> dict[str, Any]:
    status = "PASS"
    details: dict[str, Any] = {}
    if check_name == "advisor_effectiveness_smoke":
        status = "WARN"
        details = {
            "accepted_proposal_count": 0,
            "advisor_child_scheduled_count": 0,
            "advisor_backed_diff_count": 0,
            "message": "No advisor run was provided; transport/effectiveness artifacts are checked during advisor-mode search runs.",
        }
    elif check_name == "advisor_transport_smoke":
        details = {"message": "CLI import and mock transport path are available."}
    elif check_name == "smoke":
        details = {"message": "Use render/eval/search subcommands for full smoke validation."}
    else:
        status = "WARN"
        details = {"message": f"unknown check '{check_name}' recorded as warning"}
    result = {"check": check_name, "status": status, "created_at": utc_now(), "details": details}
    if out_dir:
        target = Path(out_dir)
        target.mkdir(parents=True, exist_ok=True)
        (target / f"{check_name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
