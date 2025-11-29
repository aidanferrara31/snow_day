from __future__ import annotations

from typing import Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from snow_day.config import SchedulerConfig
from snow_day.logging import get_logger

logger = get_logger(__name__)


def build_scheduler(job: Callable[[], None], config: SchedulerConfig) -> Optional[AsyncIOScheduler]:
    if not config.enabled:
        logger.info("scheduler.disabled")
        return None

    scheduler = AsyncIOScheduler()
    trigger = CronTrigger.from_crontab(config.cron)
    scheduler.add_job(job, trigger=trigger, id="refresh-resorts", max_instances=1, coalesce=True)
    logger.info("scheduler.configured", cron=config.cron)
    return scheduler
