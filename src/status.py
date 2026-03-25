from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import psutil

from messaging.sender import KassaSender


class StatusService:
    def __init__(
        self,
        sender: KassaSender,
        interval_seconds: int,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.sender = sender
        self.interval_seconds = interval_seconds
        self.logger = logger or logging.getLogger(__name__)
        self.started_at = time.time()

    async def run(self) -> None:
        self.logger.info("Status service started.")
        try:
            while True:
                uptime = int(time.time() - self.started_at)
                cpu = psutil.cpu_percent(interval=None) / 100.0
                memory = psutil.virtual_memory().percent / 100.0
                disk = psutil.disk_usage("/").percent / 100.0

                status = "healthy"
                if cpu > 0.90 or memory > 0.90 or disk > 0.90:
                    status = "degraded"
                if cpu > 0.98 or memory > 0.98 or disk > 0.98:
                    status = "unhealthy"

                await self.sender.publish_status_check(
                    timestamp=datetime.now(timezone.utc),
                    status=status,
                    uptime=uptime,
                    cpu=cpu,
                    memory=memory,
                    disk=disk,
                )

                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            self.logger.info("Status service stopped.")
            raise
