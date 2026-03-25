from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from messaging.sender import KassaSender


class HeartbeatService:
    def __init__(
        self,
        sender: KassaSender,
        interval_seconds: int,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.sender = sender
        self.interval_seconds = interval_seconds
        self.logger = logger or logging.getLogger(__name__)

    async def run(self) -> None:
        self.logger.info("Heartbeat service started.")
        try:
            while True:
                await self.sender.publish_heartbeat(datetime.now(timezone.utc))
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            self.logger.info("Heartbeat service stopped.")
            raise
