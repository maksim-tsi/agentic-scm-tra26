import os
import sys
from typing import get_type_hints


def test_graph_state_messages_annotated_with_add_messages() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src_root = os.path.join(repo_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from agentic.state import GraphState
    from langgraph.graph.message import add_messages

    hints = get_type_hints(GraphState, include_extras=True)
    msg_hint = hints["messages"]

    assert getattr(msg_hint, "__metadata__", None), "messages must use typing.Annotated[..., add_messages]"
    assert add_messages in msg_hint.__metadata__

