"""NTP helpers for runtime clock checks."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import ntplib


@dataclass(frozen=True)
class TimeSyncResult:
    server: str
    offset_seconds: float
    remote_time: float
    local_time: float


async def check_time(server: str = "pool.ntp.org") -> TimeSyncResult:
    """Query NTP and return the observed offset without changing system time."""

    def query() -> TimeSyncResult:
        local_time = time.time()
        response = ntplib.NTPClient().request(server)
        return TimeSyncResult(
            server=server,
            offset_seconds=float(response.offset),
            remote_time=float(response.tx_time),
            local_time=local_time,
        )

    return await asyncio.to_thread(query)


__all__ = ["TimeSyncResult", "check_time"]
