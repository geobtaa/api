"""
Celery task for enriching API usage logs with user agent parsing.

This task runs asynchronously to avoid blocking API requests. It:
1. Parses user agents to extract browser, OS, and device type
2. Updates the api_usage_logs record with the enriched data

Inspired by Ahoy's background job pattern for analytics enrichment.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from user_agents import parse

from app.tasks.worker import celery_app
from db.config import DATABASE_URL

logger = logging.getLogger(__name__)


def _parse_user_agent(user_agent: Optional[str]) -> Dict[str, Any]:
    """
    Parse user agent string to extract browser, OS, and device type.

    Args:
        user_agent: User agent string

    Returns:
        Dictionary with browser, os, and device_type
    """
    if not user_agent:
        return {}

    try:
        ua = parse(user_agent)

        result = {}

        # Browser name
        if ua.browser.family:
            result["browser"] = ua.browser.family[:100]  # Truncate to max length

        # Operating system
        if ua.os.family:
            result["os"] = ua.os.family[:100]  # Truncate to max length

        # Device type (mobile, tablet, desktop, bot, etc.)
        if ua.is_mobile:
            result["device_type"] = "mobile"
        elif ua.is_tablet:
            result["device_type"] = "tablet"
        elif ua.is_pc:
            result["device_type"] = "desktop"
        elif ua.is_bot:
            result["device_type"] = "bot"
        else:
            result["device_type"] = "other"

        return result

    except Exception as e:
        logger.warning(f"Error parsing user agent '{user_agent}': {e}")
        return {}


@celery_app.task(bind=True, name="enrich_api_usage_log")
def enrich_api_usage_log(self, log_id: int) -> Dict[str, Any]:
    """
    Celery task to enrich an API usage log with user agent parsing.

    Args:
        log_id: ID of the api_usage_logs record to enrich

    Returns:
        Dictionary with enrichment results
    """
    logger.info(f"Starting enrichment for API usage log ID {log_id}")

    # Create event loop for async operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(_enrich_log_async(log_id))
        return result
    finally:
        loop.close()


async def _enrich_log_async(log_id: int) -> Dict[str, Any]:
    """
    Async implementation of log enrichment.

    Args:
        log_id: ID of the api_usage_logs record to enrich

    Returns:
        Dictionary with enrichment results
    """
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with async_session_factory() as session:
            # Fetch the log record
            select_query = text("""
                SELECT id, user_agent
                FROM api_usage_logs
                WHERE id = :log_id
            """)

            result = await session.execute(select_query, {"log_id": log_id})
            log_record = result.fetchone()

            if not log_record:
                logger.warning(f"API usage log {log_id} not found")
                return {"status": "error", "log_id": log_id, "error": "Log not found"}

            # Extract data
            user_agent = (
                log_record.user_agent if hasattr(log_record, "user_agent") else log_record[1]
            )

            # Parse user agent (synchronous operation, but fast)
            ua_data = _parse_user_agent(user_agent)

            if not ua_data:
                logger.debug(f"No enrichment data for log {log_id}")
                return {"status": "success", "log_id": log_id, "enriched": False}

            # Update the log record
            update_query = text("""
                UPDATE api_usage_logs
                SET 
                    browser = :browser,
                    os = :os,
                    device_type = :device_type
                WHERE id = :log_id
            """)

            update_params = {
                "log_id": log_id,
                "browser": ua_data.get("browser"),
                "os": ua_data.get("os"),
                "device_type": ua_data.get("device_type"),
            }

            await session.execute(update_query, update_params)
            await session.commit()

            logger.info(f"Successfully enriched API usage log {log_id}")
            return {
                "status": "success",
                "log_id": log_id,
                "enriched": True,
                "data": ua_data,
            }

    except Exception as e:
        logger.error(f"Error enriching API usage log {log_id}: {e}", exc_info=True)
        return {"status": "error", "log_id": log_id, "error": str(e)}

    finally:
        await engine.dispose()


@celery_app.task(bind=True, name="enrich_api_usage_logs_batch")
def enrich_api_usage_logs_batch(self, batch_size: int = 100) -> Dict[str, Any]:
    """
    Enrich a batch of API usage logs that haven't been enriched yet.

    This is useful for backfilling enrichment data or processing logs in bulk.

    Args:
        batch_size: Number of logs to process in this batch

    Returns:
        Dictionary with batch processing results
    """
    logger.info(f"Starting batch enrichment for {batch_size} API usage logs")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        result = loop.run_until_complete(_enrich_batch_async(batch_size))
        return result
    finally:
        loop.close()


async def _enrich_batch_async(batch_size: int) -> Dict[str, Any]:
    """
    Async implementation of batch enrichment.

    Args:
        batch_size: Number of logs to process

    Returns:
        Dictionary with batch processing results
    """
    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
    async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    stats = {"processed": 0, "enriched": 0, "errors": 0}

    try:
        async with async_session_factory() as session:
            # Find logs that need enrichment (where UA fields are NULL)
            select_query = text("""
                SELECT id, user_agent
                FROM api_usage_logs
                WHERE browser IS NULL
                  AND user_agent IS NOT NULL
                ORDER BY requested_at DESC
                LIMIT :batch_size
            """)

            result = await session.execute(select_query, {"batch_size": batch_size})
            logs = result.fetchall()

            if not logs:
                logger.info("No logs found that need enrichment")
                return {"status": "success", **stats}

            logger.info(f"Found {len(logs)} logs to enrich")

            # Process each log
            for log in logs:
                log_id = log.id if hasattr(log, "id") else log[0]
                user_agent = log.user_agent if hasattr(log, "user_agent") else log[1]

                try:
                    # Parse user agent
                    ua_data = _parse_user_agent(user_agent)

                    if ua_data:
                        # Update the log
                        update_query = text("""
                            UPDATE api_usage_logs
                            SET 
                                browser = COALESCE(:browser, browser),
                                os = COALESCE(:os, os),
                                device_type = COALESCE(:device_type, device_type)
                            WHERE id = :log_id
                        """)

                        update_params = {
                            "log_id": log_id,
                            "browser": ua_data.get("browser"),
                            "os": ua_data.get("os"),
                            "device_type": ua_data.get("device_type"),
                        }

                        await session.execute(update_query, update_params)
                        stats["enriched"] += 1

                    stats["processed"] += 1

                except Exception as e:
                    logger.error(f"Error enriching log {log_id}: {e}")
                    stats["errors"] += 1
                    stats["processed"] += 1

            await session.commit()

            logger.info(f"Batch enrichment complete: {stats}")
            return {"status": "success", **stats}

    except Exception as e:
        logger.error(f"Error in batch enrichment: {e}", exc_info=True)
        return {"status": "error", "error": str(e), **stats}

    finally:
        await engine.dispose()
