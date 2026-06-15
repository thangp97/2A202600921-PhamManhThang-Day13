from __future__ import annotations

import os
from typing import Any

try:
    from langfuse import observe, get_client

    class _LangfuseContext:
        """Wrapper giữ nguyên interface cũ, map sang Langfuse 3.x API."""

        def update_current_trace(self, **kwargs: Any) -> None:
            get_client().update_current_trace(**kwargs)

        def update_current_observation(self, **kwargs: Any) -> None:
            # usage_details chỉ được nhận bởi generation, không phải span
            if "usage_details" in kwargs:
                get_client().update_current_generation(**kwargs)
            else:
                get_client().update_current_span(**kwargs)

    langfuse_context = _LangfuseContext()

except Exception:
    def observe(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorator(func):
            return func
        return decorator

    class _DummyContext:
        def update_current_trace(self, **kwargs: Any) -> None:
            return None

        def update_current_observation(self, **kwargs: Any) -> None:
            return None

    langfuse_context = _DummyContext()  # type: ignore[assignment]


def tracing_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
