from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional, TypeVar


T = TypeVar("T")


async def with_retries(
    action: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay_seconds: float = 5.0,
) -> T:
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            return await action()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == attempts:
                break
            await asyncio.sleep(base_delay_seconds * attempt)

    assert last_error is not None
    raise last_error
