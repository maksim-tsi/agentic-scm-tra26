from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _pick_top_trace_ids(rows: list[dict[str, Any]], predicate: Any, limit: int) -> list[str]:
    selected: list[str] = []
    for row in rows:
        if not predicate(row):
            continue
        trace_id = row.get("trace_id")
        if isinstance(trace_id, str) and trace_id:
            selected.append(trace_id)
        if len(selected) >= limit:
            break
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate compact Phoenix metrics and build deep-dive shortlist.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_compact.jsonl"),
    )
    parser.add_argument(
        "--metrics-out",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_metrics_summary.json"),
    )
    parser.add_argument(
        "--shortlist-out",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_selective_shortlist.json"),
    )
    parser.add_argument("--per-bucket", type=int, default=12, help="Trace count per anomaly bucket")
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Input compact file not found: {args.input}")

    rows = _load_jsonl(args.input)

    status_counter: Counter[str] = Counter()
    model_counter: Counter[str] = Counter()
    run_mode_counter: Counter[str] = Counter()
    error_category_counter: Counter[str] = Counter()
    span_name_counter: Counter[str] = Counter()

    yaam_positive = 0
    tool_positive = 0
    error_positive = 0

    for row in rows:
        status = row.get("status")
        if isinstance(status, str):
            status_counter[status] += 1

        models = row.get("model_ids")
        if isinstance(models, list):
            for model in models:
                if isinstance(model, str) and model:
                    model_counter[model] += 1

        run_modes = row.get("run_modes")
        if isinstance(run_modes, list):
            for mode in run_modes:
                if isinstance(mode, str) and mode:
                    run_mode_counter[mode] += 1

        err_cats = row.get("error_categories")
        if isinstance(err_cats, list):
            for item in err_cats:
                if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], int):
                    error_category_counter[item[0]] += item[1]

        top_span_names = row.get("top_span_names")
        if isinstance(top_span_names, list):
            for item in top_span_names:
                if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], int):
                    span_name_counter[item[0]] += item[1]

        if isinstance(row.get("yaam_signal_hits"), int) and row["yaam_signal_hits"] > 0:
            yaam_positive += 1
        if isinstance(row.get("tool_signal_hits"), int) and row["tool_signal_hits"] > 0:
            tool_positive += 1
        if isinstance(row.get("error_signal_hits"), int) and row["error_signal_hits"] > 0:
            error_positive += 1

    total = len(rows)

    # Selective deep-dive shortlist buckets.
    shortlist = {
        "graph_recursion_or_high_error_signal": _pick_top_trace_ids(
            rows,
            lambda r: isinstance(r.get("error_signal_hits"), int) and r["error_signal_hits"] >= 8,
            args.per_bucket,
        ),
        "pydantic_or_json_structure": _pick_top_trace_ids(
            rows,
            lambda r: any(
                isinstance(it, list)
                and len(it) == 2
                and isinstance(it[0], str)
                and it[0] in {"pydantic_validation", "json_structure"}
                and isinstance(it[1], int)
                and it[1] > 0
                for it in (r.get("error_categories") if isinstance(r.get("error_categories"), list) else [])
            ),
            args.per_bucket,
        ),
        "provider_or_rate_limit": _pick_top_trace_ids(
            rows,
            lambda r: any(
                isinstance(it, list)
                and len(it) == 2
                and isinstance(it[0], str)
                and it[0] in {"provider_api", "rate_limit_429", "timeout"}
                and isinstance(it[1], int)
                and it[1] > 0
                for it in (r.get("error_categories") if isinstance(r.get("error_categories"), list) else [])
            ),
            args.per_bucket,
        ),
        "low_yaam_signal_with_tools": _pick_top_trace_ids(
            rows,
            lambda r: (
                isinstance(r.get("tool_signal_hits"), int)
                and r["tool_signal_hits"] >= 3
                and isinstance(r.get("yaam_signal_hits"), int)
                and r["yaam_signal_hits"] == 0
            ),
            args.per_bucket,
        ),
    }

    unique_shortlist: list[str] = []
    seen: set[str] = set()
    for ids in shortlist.values():
        for trace_id in ids:
            if trace_id not in seen:
                seen.add(trace_id)
                unique_shortlist.append(trace_id)

    metrics = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "input_file": str(args.input),
        "total_traces": total,
        "status_distribution": status_counter.most_common(),
        "model_distribution": model_counter.most_common(),
        "run_mode_distribution": run_mode_counter.most_common(),
        "error_category_distribution": error_category_counter.most_common(),
        "top_span_names": span_name_counter.most_common(15),
        "yaam_signal_positive_traces": yaam_positive,
        "tool_signal_positive_traces": tool_positive,
        "error_signal_positive_traces": error_positive,
    }

    shortlist_payload = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "input_file": str(args.input),
        "per_bucket": args.per_bucket,
        "buckets": shortlist,
        "unique_trace_ids": unique_shortlist,
        "unique_trace_count": len(unique_shortlist),
    }

    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    args.shortlist_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    args.shortlist_out.write_text(json.dumps(shortlist_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Total traces analyzed: {total}")
    print(f"Metrics written: {args.metrics_out}")
    print(f"Shortlist written: {args.shortlist_out}")
    print(f"Unique shortlist traces: {len(unique_shortlist)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())