"""Standalone Redis Queue (RQ) Worker Entrypoint for Docker Compose & Production."""

from __future__ import annotations

import logging
import redis
from rq import Queue

from app.config import get_settings
from app.jobs.rq_tasks import CrossPlatformSimpleWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("pde_studio.rq_worker")


def main() -> None:
    settings = get_settings()
    logger.info(
        "Connecting RQ worker to Redis (%s) on queue '%s'...",
        settings.redis_url,
        settings.rq_queue_name,
    )
    conn = redis.Redis.from_url(settings.redis_url)
    queue = Queue(
        settings.rq_queue_name,
        connection=conn,
        default_timeout=settings.job_timeout_seconds,
    )
    worker = CrossPlatformSimpleWorker([queue], connection=conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
