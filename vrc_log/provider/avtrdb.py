import aiohttp
import logging
import asyncio
from aiohttp import ClientTimeout
from typing import Any, Dict

from vrc_log import USER_AGENT
from .base import BaseProvider

logger = logging.getLogger(__name__)
URL: str = "https://api.avtrdb.com/v2/avatar/ingest"
MAX_RETRIES: int = 3
MAX_BACKOFF: int = 30


class AvtrDB(BaseProvider):
    kind: str = "avtrDB"

    async def send_avatar_id(self, avatar_id: str) -> bool:
        payload: Dict[str, Any] = {
            "avatar_ids": [avatar_id],
            "attribution": "VRCLogX",
        }
        logger.debug("Sending to AvtrDB: %s", payload)

        for retry in range(MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        URL,
                        json=payload,
                        headers={"User-Agent": USER_AGENT},
                        timeout=ClientTimeout(total=5),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get("valid_avatar_ids", 0) == 1
                        if response.status == 429 and retry < MAX_RETRIES:
                            backoff = min(MAX_BACKOFF, 10 * (2**retry))
                            logger.warning("Rate limited, retrying in %ss", backoff)
                            await asyncio.sleep(backoff)
                            continue
                        logger.error("AvtrDB failed - Status %d", response.status)
                        return False
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if retry < MAX_RETRIES:
                    backoff = min(MAX_BACKOFF, 5 * (2**retry))
                    logger.warning("Network error, retrying in %ss: %s", backoff, e)
                    await asyncio.sleep(backoff)
                    continue
                logger.error("Network error after retries: %s", e)
                return False
            except Exception as e:
                logger.exception("Unexpected AvtrDB error: %s", e)
                return False
        return False
