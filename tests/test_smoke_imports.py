import os
import sys


def test_imports_smoke() -> None:
    repo_root = os.path.dirname(os.path.dirname(__file__))
    src_root = os.path.join(repo_root, "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    import agentic.state  # noqa: F401
    import evaluators.agentic_mas_client  # noqa: F401
    import evaluators.base  # noqa: F401
    import evaluators.naive_llm_client  # noqa: F401
    import memory.yaam_client  # noqa: F401

