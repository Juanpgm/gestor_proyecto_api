"""Shared dual-read execution helper for composite adapters.

A single coroutine runs the Firestore and Postgres sides concurrently, decides
which side is authoritative (the configured ``primary``), tolerates a failure on
the non-primary side, and hands both successful results to a comparison callback.

Divergence is observational only: it is logged, never raised. A backend hiccup on
the secondary side must not break the response — the primary result is returned.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

# Callback signature: (method_name, firestore_result, postgres_result) -> None
CompareCallback = Callable[[str, Any, Any], None]


async def gather_dual(
    fs_coro: Awaitable[Any],
    pg_coro: Awaitable[Any],
    *,
    primary: str,
    logger: logging.Logger,
    method_name: str,
    on_both: Optional[CompareCallback],
) -> Any:
    """Run both sides concurrently and return the ``primary`` side's result.

    - Both coroutines run under ``asyncio.gather(..., return_exceptions=True)``.
    - If the primary side raised, the exception is logged and re-raised (a broken
      primary is a real failure the caller must see).
    - If only the secondary side raised, it is logged at WARNING and the primary
      result is returned unchanged (the read still succeeds).
    - If both sides succeeded, ``on_both`` (the comparison/divergence hook) is
      invoked with the Firestore result as left and the Postgres result as right.
    """
    fs_result, pg_result = await asyncio.gather(
        fs_coro, pg_coro, return_exceptions=True
    )

    if primary == "firestore":
        primary_result, secondary_result = fs_result, pg_result
        secondary_label = "postgres"
    else:
        primary_result, secondary_result = pg_result, fs_result
        secondary_label = "firestore"

    if isinstance(primary_result, BaseException):
        logger.error(
            "dual-read %s: primary side (%s) failed: %r",
            method_name,
            primary,
            primary_result,
        )
        raise primary_result

    if isinstance(secondary_result, BaseException):
        logger.warning(
            "dual-read %s: secondary side (%s) failed, returning primary only: %r",
            method_name,
            secondary_label,
            secondary_result,
        )
        return primary_result

    if on_both is not None:
        on_both(method_name, fs_result, pg_result)

    return primary_result
