from __future__ import annotations

import argparse
import json
import pickle
import re
import sqlite3
import zlib
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import msgpack  # type: ignore
except Exception:  # pragma: no cover
    msgpack = None


def _decode_blob(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (dict, list, str, int, float, bool)):
        return value
    if not isinstance(value, (bytes, bytearray)):
        return value

    raw = bytes(value)
    variants = [raw]
    try:
        variants.insert(0, zlib.decompress(raw))
    except Exception:
        pass

    for blob in variants:
        if msgpack is not None:
            try:
                return msgpack.unpackb(blob, raw=False)
            except Exception:
                pass
        try:
            return json.loads(blob.decode("utf-8"))
        except Exception:
            pass
        try:
            return pickle.loads(blob)
        except Exception:
            pass
    return raw


def _safe_text(value: Any, max_len: int = 400) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False)
    except Exception:
        text = str(value)
    text = text.replace("\n", " ").strip()
    return text[:max_len]


def _task_id_from_thread(thread_id: str) -> str:
    m = re.match(r"^(.*)_[0-9a-f]{8}$", thread_id)
    if m:
        return m.group(1)
    return thread_id


def _unwrap_nested_blob(value: Any, depth: int = 4) -> Any:
    cur = value
    for _ in range(depth):
        if not isinstance(cur, (bytes, bytearray, memoryview)):
            break
        nxt = _decode_blob(cur)
        if nxt is cur:
            break
        cur = nxt
    return cur


def _find_task_key_in_checkpoint(decoded_checkpoint: Any) -> str | None:
    if not isinstance(decoded_checkpoint, dict):
        return None

    channel_values = decoded_checkpoint.get("channel_values")
    if not isinstance(channel_values, dict):
        return None

    for key in ("task_id", "current_task_id", "scm_task_id"):
        val = channel_values.get(key)
        if isinstance(val, str) and val:
            return val

    msgs = channel_values.get("messages")
    if isinstance(msgs, list):
        for msg in msgs:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            text = str(content).lower()
            if "task_id" in text:
                return text[:120]

    return None


def _extract_message_like(decoded_value: Any) -> str:
    decoded_value = _unwrap_nested_blob(decoded_value)

    if isinstance(decoded_value, dict):
        for key in ("content", "text", "error", "message", "final_answer"):
            if key in decoded_value:
                return _safe_text(decoded_value.get(key), max_len=500)
        return _safe_text({k: decoded_value[k] for k in list(decoded_value.keys())[:6]}, max_len=500)
    if isinstance(decoded_value, list):
        return _safe_text(decoded_value[:3], max_len=500)
    return _safe_text(decoded_value, max_len=500)


def _infer_event_label(channel: str, text: str) -> str:
    low = text.lower()
    if "validation" in low or "pydantic" in low:
        return "Tool Error (Validation)"
    if "graphrecursionerror" in low or "recursion limit" in low:
        return "Graph Recursion Error"
    if channel == "messages":
        if "tool" in low and "error" in low:
            return "Tool Error"
        if "final_execution" in low:
            return "Agent Final"
        return "Agent Message"
    if channel == "tasks":
        return "Planner/Task Update"
    if channel == "retrieved_context":
        return "YAAM Context"
    if channel in {"tool_calls", "tools_called"}:
        return "Tool Call"
    return f"Channel:{channel}"


def _classify_message_state(text: str) -> str:
    low = text.lower()
    if text == "b'\\x90'" or text == "[]":
        return "EMPTY_MESSAGE"
    if "there is no final answer" in low:
        return "NO_FINAL_ANSWER"
    if "the final answer is" in low:
        return "FINAL_ANSWER"
    if "validation" in low or "pydantic" in low:
        return "VALIDATION_ERROR"
    if "graphrecursionerror" in low or "recursion limit" in low:
        return "GRAPH_RECURSION_ERROR"
    return "OTHER_MESSAGE"


def _pick_threads(conn: sqlite3.Connection, model_id: str, limit: int) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        SELECT c.rowid, c.thread_id, c.checkpoint_id, c.metadata, c.checkpoint
        FROM checkpoints c
        ORDER BY c.rowid DESC
        """
    ).fetchall()

    selected: list[dict[str, str]] = []
    seen_threads: set[str] = set()
    for _rowid, thread_id_raw, checkpoint_id_raw, metadata_raw, checkpoint_raw in rows:
        thread_id = str(thread_id_raw)
        if thread_id in seen_threads:
            continue

        metadata = _decode_blob(metadata_raw)
        checkpoint = _decode_blob(checkpoint_raw)

        if not isinstance(metadata, dict):
            continue

        model = metadata.get("model_id")
        if model != model_id:
            continue

        src = metadata.get("source")
        if src != "loop":
            continue

        # Look for likely recursion termination checkpoints.
        step = metadata.get("step")
        if not isinstance(step, int) or step < 25:
            continue

        task_guess = _find_task_key_in_checkpoint(checkpoint)
        selected.append(
            {
                "thread_id": thread_id,
                "checkpoint_id": str(checkpoint_id_raw),
                "task_guess": task_guess or _task_id_from_thread(thread_id),
            }
        )
        seen_threads.add(thread_id)
        if len(selected) >= limit:
            break

    return selected


def _load_last_writes(conn: sqlite3.Connection, thread_id: str, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT c.rowid, w.checkpoint_id, w.task_id, w.idx, w.channel, w.type, w.value
        FROM writes w
        JOIN checkpoints c
          ON c.thread_id = w.thread_id
         AND c.checkpoint_ns = w.checkpoint_ns
         AND c.checkpoint_id = w.checkpoint_id
        WHERE w.thread_id = ?
        ORDER BY c.rowid DESC, w.idx DESC
        LIMIT ?
        """,
        (thread_id, limit),
    ).fetchall()

    out: list[dict[str, Any]] = []
    for rowid_raw, checkpoint_id, task_id, idx, channel, val_type, value_raw in rows:
        decoded_value = _decode_blob(value_raw)
        message = _extract_message_like(decoded_value)
        label = _infer_event_label(str(channel), message)
        out.append(
            {
                "rowid": int(rowid_raw),
                "checkpoint_id": str(checkpoint_id),
                "task_id": str(task_id),
                "idx": int(idx),
                "channel": str(channel),
                "type": str(val_type) if val_type is not None else None,
                "event_label": label,
                "message_state": _classify_message_state(message),
                "message": message,
            }
        )

    out.reverse()
    return out


def _build_ping_pong_snippet(events: list[dict[str, Any]], max_steps: int = 8) -> str:
    usable = [
        e
        for e in events
        if e.get("message") and e.get("channel") in {"messages", "tasks", "tool_calls", "tools_called"}
    ]
    if not usable:
        usable = events
    usable = usable[-max_steps:]

    parts: list[str] = []
    for e in usable:
        label = str(e.get("message_state") or e.get("event_label", "Event"))
        msg = str(e.get("message", "")).strip()
        if len(msg) > 140:
            msg = msg[:140] + "..."
        parts.append(f"{label}: {msg}")
    return " -> ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract checkpoint-level recursion loop evidence for Llama runs.")
    parser.add_argument("--db", type=Path, default=Path("outputs/langgraph_checkpoints.sqlite"))
    parser.add_argument(
        "--model-id",
        default="meta-llama/llama-3.1-8b-instruct",
        help="Model ID to target",
    )
    parser.add_argument("--threads", type=int, default=3, help="How many threads to sample")
    parser.add_argument("--writes-per-thread", type=int, default=18, help="How many recent writes to inspect per thread")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/llama_recursion_checkpoint_loops.json"),
        help="Output JSON artifact",
    )
    args = parser.parse_args()

    if not args.db.exists():
        raise FileNotFoundError(f"Checkpoint DB not found: {args.db}")

    conn = sqlite3.connect(str(args.db))
    try:
        picked = _pick_threads(conn, args.model_id, args.threads)
        analyses: list[dict[str, Any]] = []
        channel_counter: Counter[str] = Counter()

        for item in picked:
            thread_id = item["thread_id"]
            events = _load_last_writes(conn, thread_id, args.writes_per_thread)
            for e in events:
                channel_counter[str(e["channel"])] += 1

            analyses.append(
                {
                    "thread_id": thread_id,
                    "task_guess": item["task_guess"],
                    "events": events,
                    "ping_pong_snippet": _build_ping_pong_snippet(events),
                }
            )
    finally:
        conn.close()

    result = {
        "model_id": args.model_id,
        "sampled_threads": len(analyses),
        "channel_counts": dict(channel_counter),
        "threads": analyses,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Wrote: {args.out}")
    print(f"sampled_threads={len(analyses)}")
    if analyses:
        print(f"first_thread={analyses[0]['thread_id']}")
        print(f"snippet={analyses[0]['ping_pong_snippet']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
