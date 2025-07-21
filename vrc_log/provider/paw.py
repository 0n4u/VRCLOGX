import aiohttp
import logging
import asyncio
from aiohttp import ClientTimeout

from vrc_log import USER_AGENT
from .base import BaseProvider

logger = logging.getLogger(__name__)
URL: str = "https://paw-api.amelia.fun/update"
MAX_RETRIES: int = 3
MAX_BACKOFF: int = 30


class Paw(BaseProvider):
    kind: str = "PAW"

    async def send_avatar_id(self, avatar_id: str) -> bool:
        for retry in range(MAX_RETRIES + 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        URL,
                        params={"avatarId": avatar_id},
                        headers={"User-Agent": USER_AGENT},
                        timeout=ClientTimeout(total=5),
                    ) as response:
                        if response.status == 200:
                            data = await response.json()
                            return data.get("success", False)
                        if response.status == 429 and retry < MAX_RETRIES:
                            backoff = min(MAX_BACKOFF, 10 * (2**retry))
                            logger.warning("Rate limited, retrying in %ss", backoff)
                            await asyncio.sleep(backoff)
                            continue
                        logger.error("PAW failed - Status %d", response.status)
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
                logger.exception("Unexpected PAW error: %s", e)
                return False
        return False
