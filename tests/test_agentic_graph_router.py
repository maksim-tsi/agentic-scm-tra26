import os
import sys

from langchain_core.messages import AIMessage


def _ensure_src_on_path() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src_root = os.path.join(repo_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)


def test_executor_router_routes_tool_calls_to_tools() -> None:
    _ensure_src_on_path()
    from agentic.graph import executor_router

    msg = AIMessage(content="call", tool_calls=[{"name": "t1", "args": {}, "id": "1", "type": "tool_call"}])
    assert executor_router({"messages": [msg]}) == "executor_tools"


def test_executor_router_routes_final_marker_to_finalizer() -> None:
    _ensure_src_on_path()
    from agentic.graph import executor_router

    msg = AIMessage(content="FINAL_EXECUTION_DONE: ok")
    assert executor_router({"messages": [msg]}) == "finalizer"


def test_executor_router_fallbacks_to_tools() -> None:
    _ensure_src_on_path()
    from agentic.graph import executor_router

    msg = AIMessage(content="still working")
    assert executor_router({"messages": [msg]}) == "executor_tools"

