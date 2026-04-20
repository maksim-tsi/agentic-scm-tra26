from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


RECURSION_PAT = re.compile(r"graphrecursionerror|recursion\s+limit|recursion", re.I)
RATE_PAT = re.compile(r"\b429\b|rate\s*limit|too many requests", re.I)
VALIDATION_PAT = re.compile(r"pydantic|validation\s*error|field required", re.I)
JSON_PAT = re.compile(r"json\s*invalid|invalid\s*json|expected value at line", re.I)
TOOL_PAT = re.compile(r"tool|executor_tools|tools_called|function_call", re.I)


@dataclass(frozen=True)
class TraceEvidence:
    trace_id: str
    bucket: str
    span_count: int
    repeated_tool_signature: str | None
    repeated_tool_count: int
    recursion_hits: int
    rate_hits: int
    validation_hits: int
    json_hits: int
    candidate_cause: str
    snippets: list[str]


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


def _extract_error_category_set(compact_row: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    cats = compact_row.get("error_categories")
    if isinstance(cats, list):
        for item in cats:
            if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str):
                if isinstance(item[1], int) and item[1] > 0:
                    out.add(item[0])
    return out


def _trace_text_and_tool_signatures(trace_obj: dict[str, Any]) -> tuple[str, Counter[str], int]:
    spans = trace_obj.get("spans")
    if not isinstance(spans, list):
        return "", Counter(), 0

    tool_sigs: Counter[str] = Counter()
    blobs: list[str] = []

    for span in spans:
        if not isinstance(span, dict):
            continue
        name = span.get("name")
        if isinstance(name, str):
            blobs.append(name)

        attrs = span.get("attributes")
        attrs_map = attrs if isinstance(attrs, dict) else {}
        low_blob = json.dumps({"name": name, "attrs": attrs_map}, ensure_ascii=False)
        blobs.append(low_blob)

        # Build a stable tool signature if this looks like a tool span.
        if TOOL_PAT.search(low_blob):
            tool_name = None
            for key in (
                "tool.name",
                "tool",
                "name",
                "function.name",
                "tool_name",
            ):
                val = attrs_map.get(key)
                if isinstance(val, str) and val:
                    tool_name = val
                    break

            # Arguments often live in payload-like fields.
            arg_val = None
            for key in (
                "input",
                "input_value",
                "tool.input",
                "llm.input",
                "openinference.input",
            ):
                val = attrs_map.get(key)
                if isinstance(val, (str, int, float, bool, list, dict)):
                    arg_val = val
                    break

            arg_text = json.dumps(arg_val, ensure_ascii=False)[:180] if arg_val is not None else ""
            if tool_name:
                sig = f"{tool_name}|{arg_text}"
                tool_sigs[sig] += 1

    return "\n".join(blobs), tool_sigs, len(spans)


def _snippets(text: str, pattern: re.Pattern[str], limit: int = 3) -> list[str]:
    out: list[str] = []
    for m in pattern.finditer(text):
        start = max(0, m.start() - 120)
        end = min(len(text), m.end() + 180)
        snippet = text[start:end].replace("\n", " ")
        out.append(snippet)
        if len(out) >= limit:
            break
    return out


def _infer_cause(
    *,
    recursion_hits: int,
    rate_hits: int,
    validation_hits: int,
    json_hits: int,
    repeated_tool_count: int,
) -> str:
    if recursion_hits > 0 and repeated_tool_count >= 3 and validation_hits > 0:
        return "Loop likely driven by repeated tool invocation with invalid/unstable schema-constrained output."
    if recursion_hits > 0 and repeated_tool_count >= 3:
        return "Loop likely driven by repeated tool invocation pattern without convergence."
    if recursion_hits > 0 and json_hits > 0:
        return "Loop likely driven by repeated JSON parse/structure failures in iterative agent steps."
    if rate_hits > 0:
        return "Provider throttling/rate-limit signatures present; failures likely external API backpressure."
    if validation_hits > 0:
        return "Primary blocker appears to be validation/schema mismatch, not provider-level failure."
    return "No strong single-cause signal; mixed or weak evidence."


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract focused evidence for recursion and rate-limit Phoenix traces.")
    parser.add_argument(
        "--compact",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_compact.jsonl"),
        help="Compacted per-trace file",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_analyst_raw.jsonl"),
        help="Raw per-trace file",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/phoenix_traces_2026-04-20_focused_evidence.json"),
        help="Focused evidence output JSON",
    )
    parser.add_argument("--max-per-bucket", type=int, default=25)
    args = parser.parse_args()

    if not args.compact.exists():
        raise FileNotFoundError(f"Missing compact file: {args.compact}")
    if not args.raw.exists():
        raise FileNotFoundError(f"Missing raw file: {args.raw}")

    compact_rows = _load_jsonl(args.compact)
    raw_rows = _load_jsonl(args.raw)

    raw_by_trace: dict[str, dict[str, Any]] = {}
    for row in raw_rows:
        trace_id = row.get("trace_id")
        if isinstance(trace_id, str) and trace_id and trace_id not in raw_by_trace:
            raw_by_trace[trace_id] = row

    rec_ids: list[str] = []
    rate_ids: list[str] = []
    for row in compact_rows:
        trace_id = row.get("trace_id")
        if not isinstance(trace_id, str) or not trace_id:
            continue
        cats = _extract_error_category_set(row)
        if "recursion" in cats:
            rec_ids.append(trace_id)
        if "rate_limit_429" in cats or "provider_api" in cats:
            rate_ids.append(trace_id)

    rec_ids = rec_ids[: args.max_per_bucket]
    rate_ids = rate_ids[: args.max_per_bucket]

    evidence_rows: list[TraceEvidence] = []
    bucket_counter: Counter[str] = Counter()
    cause_counter: Counter[str] = Counter()

    for bucket, ids in (("recursion", rec_ids), ("rate_limit", rate_ids)):
        for trace_id in ids:
            raw_row = raw_by_trace.get(trace_id)
            if not isinstance(raw_row, dict):
                continue
            trace_obj = raw_row.get("trace")
            if not isinstance(trace_obj, dict):
                continue

            text_blob, tool_sigs, span_count = _trace_text_and_tool_signatures(trace_obj)
            text_low = text_blob.lower()

            recursion_hits = len(RECURSION_PAT.findall(text_low))
            rate_hits = len(RATE_PAT.findall(text_low))
            validation_hits = len(VALIDATION_PAT.findall(text_low))
            json_hits = len(JSON_PAT.findall(text_low))

            repeated_sig = None
            repeated_count = 0
            if tool_sigs:
                repeated_sig, repeated_count = tool_sigs.most_common(1)[0]

            cause = _infer_cause(
                recursion_hits=recursion_hits,
                rate_hits=rate_hits,
                validation_hits=validation_hits,
                json_hits=json_hits,
                repeated_tool_count=repeated_count,
            )

            snippets = []
            snippets.extend(_snippets(text_blob, RECURSION_PAT, limit=1))
            snippets.extend(_snippets(text_blob, RATE_PAT, limit=1))
            snippets.extend(_snippets(text_blob, VALIDATION_PAT, limit=1))
            snippets.extend(_snippets(text_blob, JSON_PAT, limit=1))
            snippets = snippets[:4]

            evidence = TraceEvidence(
                trace_id=trace_id,
                bucket=bucket,
                span_count=span_count,
                repeated_tool_signature=repeated_sig,
                repeated_tool_count=repeated_count,
                recursion_hits=recursion_hits,
                rate_hits=rate_hits,
                validation_hits=validation_hits,
                json_hits=json_hits,
                candidate_cause=cause,
                snippets=snippets,
            )
            evidence_rows.append(evidence)
            bucket_counter[bucket] += 1
            cause_counter[cause] += 1

    # Build concise publication helper summary.
    by_bucket: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in evidence_rows:
        by_bucket[ev.bucket].append(
            {
                "trace_id": ev.trace_id,
                "span_count": ev.span_count,
                "repeated_tool_signature": ev.repeated_tool_signature,
                "repeated_tool_count": ev.repeated_tool_count,
                "recursion_hits": ev.recursion_hits,
                "rate_hits": ev.rate_hits,
                "validation_hits": ev.validation_hits,
                "json_hits": ev.json_hits,
                "candidate_cause": ev.candidate_cause,
                "snippets": ev.snippets,
            }
        )

    payload = {
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "input_compact": str(args.compact),
        "input_raw": str(args.raw),
        "selected_trace_counts": {"recursion": len(rec_ids), "rate_limit": len(rate_ids)},
        "analyzed_trace_count": len(evidence_rows),
        "bucket_counts_analyzed": dict(bucket_counter),
        "candidate_causes": cause_counter.most_common(),
        "evidence": by_bucket,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Focused evidence file: {args.out}")
    print(f"Selected recursion traces: {len(rec_ids)}")
    print(f"Selected rate-limit/provider traces: {len(rate_ids)}")
    print(f"Analyzed traces with usable payload: {len(evidence_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())