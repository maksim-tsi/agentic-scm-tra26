#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver


def _to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if hasattr(value, "model_dump"):
        try:
            return _to_jsonable(value.model_dump())
        except Exception:
            pass
    if hasattr(value, "dict"):
        try:
            return _to_jsonable(value.dict())
        except Exception:
            pass
    return str(value)


def _message_role(msg: Any) -> str:
    cls = type(msg).__name__.lower()
    if "human" in cls:
        return "user"
    if "ai" in cls:
        return "assistant"
    if "tool" in cls:
        return "tool"
    if "system" in cls:
        return "system"

    msg_type = getattr(msg, "type", None)
    if isinstance(msg_type, str) and msg_type:
        return msg_type

    if isinstance(msg, dict):
        role = msg.get("role")
        if isinstance(role, str) and role:
            return role
    return "unknown"


def _message_content(msg: Any) -> str:
    content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    try:
        return json.dumps(_to_jsonable(content), ensure_ascii=False)
    except Exception:
        return str(content)


def _message_tool_calls(msg: Any) -> list[dict[str, Any]]:
    raw = None
    if isinstance(msg, dict):
        raw = msg.get("tool_calls")
        if raw is None:
            addl = msg.get("additional_kwargs")
            if isinstance(addl, dict):
                raw = addl.get("tool_calls")
    else:
        raw = getattr(msg, "tool_calls", None)
        if raw is None:
            addl = getattr(msg, "additional_kwargs", None)
            if isinstance(addl, dict):
                raw = addl.get("tool_calls")

    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out

    for tc in raw:
        if isinstance(tc, dict):
            fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
            out.append(
                {
                    "id": tc.get("id"),
                    "name": fn.get("name") or tc.get("name"),
                    "arguments": fn.get("arguments") or tc.get("args") or tc.get("arguments"),
                }
            )
            continue

        fn_obj = getattr(tc, "function", None)
        name = getattr(fn_obj, "name", None) if fn_obj is not None else getattr(tc, "name", None)
        arguments = getattr(fn_obj, "arguments", None) if fn_obj is not None else getattr(tc, "args", None)
        out.append(
            {
                "id": getattr(tc, "id", None),
                "name": name,
                "arguments": arguments,
            }
        )

    return out


def _message_name(msg: Any) -> str | None:
    if isinstance(msg, dict):
        name = msg.get("name")
    else:
        name = getattr(msg, "name", None)
    return str(name) if name else None


def _message_tool_call_id(msg: Any) -> str | None:
    if isinstance(msg, dict):
        tcid = msg.get("tool_call_id")
    else:
        tcid = getattr(msg, "tool_call_id", None)
    return str(tcid) if tcid else None


@dataclass
class CheckpointSnapshot:
    checkpoint_id: str
    ts: str
    metadata: dict[str, Any]
    channel_values: dict[str, Any]


def _load_latest_checkpoint(db_path: Path, thread_id: str) -> CheckpointSnapshot:
    config = {"configurable": {"thread_id": thread_id}}
    with SqliteSaver.from_conn_string(str(db_path)) as saver:
        tuples = list(saver.list(config))

    if not tuples:
        raise RuntimeError(f"No checkpoints found for thread_id={thread_id}")

    def _ts_key(item: Any) -> str:
        checkpoint = getattr(item, "checkpoint", {}) or {}
        ts = checkpoint.get("ts")
        return ts if isinstance(ts, str) else ""

    latest = max(tuples, key=_ts_key)
    cp = getattr(latest, "checkpoint", {}) or {}
    md = getattr(latest, "metadata", {}) or {}
    return CheckpointSnapshot(
        checkpoint_id=str(cp.get("id") or ""),
        ts=str(cp.get("ts") or ""),
        metadata=_to_jsonable(md),
        channel_values=cp.get("channel_values") or {},
    )


def _extract_messages(snapshot: CheckpointSnapshot) -> list[dict[str, Any]]:
    raw_messages = snapshot.channel_values.get("messages")
    if not isinstance(raw_messages, list):
        return []

    out: list[dict[str, Any]] = []
    for i, msg in enumerate(raw_messages):
        out.append(
            {
                "index": i,
                "class": type(msg).__name__,
                "role": _message_role(msg),
                "name": _message_name(msg),
                "tool_call_id": _message_tool_call_id(msg),
                "tool_calls": _message_tool_calls(msg),
                "content": _message_content(msg),
            }
        )
    return out


def _analyze_trace(messages: list[dict[str, Any]]) -> dict[str, Any]:
    kraljic_call: dict[str, Any] | None = None
    kraljic_output: dict[str, Any] | None = None
    store_calls: list[dict[str, Any]] = []
    final_execution_done_message: dict[str, Any] | None = None

    for msg in messages:
        if msg["role"] == "assistant":
            for tc in msg.get("tool_calls") or []:
                name = str(tc.get("name") or "")
                if "kraljic_matrix" in name and kraljic_call is None:
                    kraljic_call = {
                        "message_index": msg["index"],
                        "tool_call_id": tc.get("id"),
                        "name": name,
                        "arguments": tc.get("arguments"),
                    }
                if name == "store_intermediate_fact":
                    store_calls.append(
                        {
                            "message_index": msg["index"],
                            "tool_call_id": tc.get("id"),
                            "arguments": tc.get("arguments"),
                        }
                    )

        content = msg.get("content") or ""
        if msg["role"] == "assistant" and "FINAL_EXECUTION_DONE:" in content:
            final_execution_done_message = {
                "message_index": msg["index"],
                "content": content,
            }

    if kraljic_call is not None:
        call_id = kraljic_call.get("tool_call_id")
        for msg in messages:
            if msg["role"] != "tool":
                continue
            if call_id and msg.get("tool_call_id") == call_id:
                kraljic_output = {
                    "message_index": msg["index"],
                    "tool_call_id": msg.get("tool_call_id"),
                    "name": msg.get("name"),
                    "content": msg.get("content"),
                }
                break

        if kraljic_output is None:
            for msg in messages:
                if msg["role"] == "tool" and "kraljic" in str(msg.get("name") or ""):
                    kraljic_output = {
                        "message_index": msg["index"],
                        "tool_call_id": msg.get("tool_call_id"),
                        "name": msg.get("name"),
                        "content": msg.get("content"),
                    }
                    break

    executor_fallback_after_kraljic: dict[str, Any] | None = None
    if kraljic_output is not None and not store_calls:
        start_idx = int(kraljic_output["message_index"])
        for msg in messages:
            if int(msg["index"]) <= start_idx:
                continue
            if msg["role"] == "assistant":
                executor_fallback_after_kraljic = {
                    "message_index": msg["index"],
                    "content": msg.get("content"),
                    "tool_calls": msg.get("tool_calls") or [],
                }
                break

    return {
        "kraljic_tool_call": kraljic_call,
        "kraljic_tool_output": kraljic_output,
        "store_intermediate_fact_calls": store_calls,
        "store_intermediate_fact_called": bool(store_calls),
        "executor_message_after_kraljic_when_no_store": executor_fallback_after_kraljic,
        "final_execution_done_message": final_execution_done_message,
    }


def _segment_runs(messages: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """
    Split a merged LangGraph message history into invocation-like segments.

    Heuristic: each top-level HumanMessage starts a new segment.
    """
    segments: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for msg in messages:
        if msg.get("role") == "user" and current:
            segments.append(current)
            current = [msg]
            continue
        current.append(msg)

    if current:
        segments.append(current)
    return segments


def _extract_attr_map(attrs: Any) -> dict[str, Any]:
    if isinstance(attrs, dict):
        return {str(k): _to_jsonable(v) for k, v in attrs.items()}
    return {}


def _maybe_extract_prompt_like_fields(span: dict[str, Any]) -> dict[str, Any]:
    keys_of_interest = [
        "input",
        "output",
        "input_value",
        "output_value",
        "llm.input_messages",
        "llm.input",
        "llm.prompt",
        "openinference.input",
        "openinference.output",
    ]
    attrs = _extract_attr_map(span.get("attributes"))
    selected: dict[str, Any] = {}
    for key in keys_of_interest:
        if key in attrs:
            selected[key] = attrs[key]
    return selected


def _phoenix_best_effort(thread_id: str, phoenix_base_url: str, project_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "base_url": phoenix_base_url,
        "project": project_name,
        "status": "not_attempted",
        "errors": [],
        "candidate_spans": [],
        "finalizer_prompt_candidates": [],
    }

    try:
        from phoenix.client import Client
    except Exception as exc:
        result["status"] = "unavailable"
        result["errors"].append(f"phoenix client import failed: {type(exc).__name__}: {exc}")
        return result

    try:
        client = Client(base_url=phoenix_base_url)

        traces = []
        session_candidates = [thread_id, f"task-{thread_id}"]
        for sid in session_candidates:
            try:
                traces = client.traces.get_traces(
                    project_identifier=project_name,
                    session_id=sid,
                    include_spans=True,
                    limit=20,
                )
            except Exception as exc:
                result["errors"].append(f"get_traces(session_id={sid}) failed: {type(exc).__name__}: {exc}")
                continue
            if traces:
                break

        spans: list[dict[str, Any]] = []
        if traces:
            for tr in traces:
                trj = _to_jsonable(tr)
                if isinstance(trj, dict):
                    tr_spans = trj.get("spans") or []
                    if isinstance(tr_spans, list):
                        for s in tr_spans:
                            if isinstance(s, dict):
                                spans.append(s)
        else:
            # Fallback query: pull recent spans and filter locally by session/task id hints.
            try:
                span_rows = client.spans.get_spans(project_identifier=project_name, limit=500)
                for s in span_rows:
                    sj = _to_jsonable(s)
                    if isinstance(sj, dict):
                        spans.append(sj)
            except Exception as exc:
                result["errors"].append(f"get_spans failed: {type(exc).__name__}: {exc}")

        session_keys = {thread_id, f"task-{thread_id}"}
        filtered: list[dict[str, Any]] = []
        for span in spans:
            attrs = _extract_attr_map(span.get("attributes"))
            haystack = json.dumps({"attrs": attrs, "name": span.get("name")}, ensure_ascii=False)
            if any(sk in haystack for sk in session_keys):
                filtered.append(span)

        if not filtered:
            # keep at least some recent spans for diagnostics if no direct match was found
            filtered = spans[:20]

        candidates: list[dict[str, Any]] = []
        finalizer_like: list[dict[str, Any]] = []
        for span in filtered:
            attrs = _extract_attr_map(span.get("attributes"))
            name = str(span.get("name") or "")
            row = {
                "name": name,
                "span_id": span.get("span_id") or span.get("id"),
                "trace_id": span.get("trace_id") or (span.get("context") or {}).get("trace_id"),
                "attributes": attrs,
                "prompt_fields": _maybe_extract_prompt_like_fields(span),
            }
            candidates.append(row)

            prompt_blob = json.dumps(row["prompt_fields"], ensure_ascii=False)
            attrs_blob = json.dumps(attrs, ensure_ascii=False)
            if "YAAM L2 Facts (working memory):" in prompt_blob or "YAAM L2 Facts (working memory):" in attrs_blob:
                finalizer_like.append(row)
            elif "SCM Finalizer Node" in prompt_blob or "SCM Finalizer Node" in attrs_blob:
                finalizer_like.append(row)
            elif "finalizer" in name.lower():
                finalizer_like.append(row)

        result["status"] = "ok"
        result["candidate_spans"] = candidates
        result["finalizer_prompt_candidates"] = finalizer_like
        return result
    except Exception as exc:
        result["status"] = "error"
        result["errors"].append(f"phoenix query failed: {type(exc).__name__}: {exc}")
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug trace and memory evidence flow for sc_ra_001")
    parser.add_argument("--thread-id", default="sc_ra_001")
    parser.add_argument("--db", default="outputs/langgraph_checkpoints.sqlite")
    parser.add_argument("--phoenix-url", default="http://127.0.0.1:6006")
    parser.add_argument("--phoenix-project", default=None)
    parser.add_argument("--out", default="outputs/debug_trace_sc_ra_001.json")
    args = parser.parse_args()

    load_dotenv()
    project_name = args.phoenix_project or os.getenv("PHOENIX_PROJECT_NAME") or "scm-cert-eval-sandbox"

    db_path = Path(args.db)
    if not db_path.exists():
        raise RuntimeError(f"Checkpoint DB not found: {db_path}")

    snapshot = _load_latest_checkpoint(db_path=db_path, thread_id=args.thread_id)
    messages = _extract_messages(snapshot)
    analysis = _analyze_trace(messages)
    segments = _segment_runs(messages)
    latest_segment = segments[-1] if segments else []
    latest_segment_analysis = _analyze_trace(latest_segment) if latest_segment else {}
    phoenix = _phoenix_best_effort(
        thread_id=args.thread_id,
        phoenix_base_url=args.phoenix_url,
        project_name=project_name,
    )

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "thread_id": args.thread_id,
        "checkpoint_db": str(db_path),
        "latest_checkpoint": {
            "checkpoint_id": snapshot.checkpoint_id,
            "ts": snapshot.ts,
            "metadata": snapshot.metadata,
        },
        "state_summary": {
            "has_retrieved_context": bool(snapshot.channel_values.get("retrieved_context")),
            "retrieved_context_count": len(snapshot.channel_values.get("retrieved_context") or []),
            "has_evidence_table": bool(snapshot.channel_values.get("evidence_table")),
            "evidence_table_count": len(snapshot.channel_values.get("evidence_table") or []),
            "has_final_answer": bool(snapshot.channel_values.get("final_answer")),
        },
        "messages": messages,
        "trace_analysis": analysis,
        "run_segments": [
            {
                "segment_index": i,
                "message_count": len(seg),
                "start_message_index": seg[0]["index"] if seg else None,
                "end_message_index": seg[-1]["index"] if seg else None,
                "starts_with": seg[0]["content"][:120] if seg else "",
                "analysis": _analyze_trace(seg),
            }
            for i, seg in enumerate(segments)
        ],
        "latest_segment_analysis": latest_segment_analysis,
        "phoenix": phoenix,
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote diagnostic JSON: {out_path}")
    print(f"Messages: {len(messages)}")
    print(
        "store_intermediate_fact_called="
        f"{analysis.get('store_intermediate_fact_called')}"
    )
    ktc = analysis.get("kraljic_tool_call") or {}
    kto = analysis.get("kraljic_tool_output") or {}
    print(f"kraljic_tool_call={json.dumps(ktc, ensure_ascii=False)}")
    print(f"kraljic_tool_output={json.dumps(kto, ensure_ascii=False)}")
    print(f"phoenix_status={phoenix.get('status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
