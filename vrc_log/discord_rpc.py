# TS PMO discord rpc isn't for the weak.
import logging
import asyncio
import socket
from typing import Protocol, Type, Optional, Dict, Any, cast

try:
    from pypresence import AioPresence as _ImportedAioPresence  # type: ignore
except ImportError:
    _ImportedAioPresence = None

logger = logging.getLogger(__name__)
CLIENT_ID: str = "1383879069073932330"
MAX_DESCRIPTION_LENGTH: int = 128


class AioPresenceProto(Protocol):
    def __init__(self, client_id: str) -> None: ...
    async def connect(self) -> None: ...
    async def update(self, **kwargs: Any) -> None: ...
    async def close(self) -> None: ...


AioPresenceClass: Type[AioPresenceProto] = cast(
    Type[AioPresenceProto],
    _ImportedAioPresence,
)


class DiscordRPC:
    def __init__(self, debug: bool = False) -> None:
        self.debug: bool = debug
        self.rpc: Optional[AioPresenceProto] = None
        self.connected: bool = False

    async def connect(self) -> None:
        if _ImportedAioPresence is None:
            logger.critical("Required library missing: pypresence")
            self.connected = False
            return

        try:
            rpc_instance = AioPresenceClass(CLIENT_ID)
            await rpc_instance.connect()
            self.rpc = rpc_instance
            self.connected = True
            logger.info("Connected to Discord RPC")
        except (ConnectionRefusedError, socket.gaierror, asyncio.TimeoutError) as e:
            logger.error("Connection error: %s", e, exc_info=self.debug)
            self.connected = False
        except Exception as e:
            logger.exception("Unexpected connection error: %s", e, exc_info=self.debug)
            self.connected = False

    async def update_presence(self, state: str) -> None:
        if not self.connected or self.rpc is None:
            logger.debug("Skipping presence update - not connected")
            return

        try:
            await self.rpc.update(
                state=state,
                large_image="VRCLogX",
                large_text="VRCLogX",
            )
        except (asyncio.TimeoutError, ConnectionRefusedError, socket.gaierror) as e:
            logger.error("Network error: %s", e, exc_info=self.debug)
            self.connected = False
        except Exception as e:
            logger.exception("RPC update error: %s", e, exc_info=self.debug)
            self.connected = False

    async def update_avatar_presence(
        self,
        name: str,
        author_name: str,
        description: str,
        image_url: Optional[str] = None,
    ) -> None:
        if not self.connected or self.rpc is None:
            logger.debug("Skipping avatar presence - not connected")
            return

        clean_name = name.strip() or "Unknown Avatar"
        clean_author = author_name.strip() or "Unknown Author"
        clean_desc = description.strip() or "No description available"

        if len(clean_desc) > MAX_DESCRIPTION_LENGTH:
            clean_desc = clean_desc[: MAX_DESCRIPTION_LENGTH - 3] + "..."
            logger.debug(
                "Truncated description to %d characters", MAX_DESCRIPTION_LENGTH
            )

        activity: Dict[str, Any] = {
            "details": clean_name,
            "state": f"by {clean_author}",
            "large_image": image_url or "VRCLogX",
            "large_text": clean_desc,
        }

        try:
            await self.rpc.update(**activity)
        except (asyncio.TimeoutError, ConnectionRefusedError, socket.gaierror) as e:
            logger.error("Network error: %s", e, exc_info=self.debug)
            self.connected = False
        except Exception as e:
            logger.exception("RPC avatar update error: %s", e, exc_info=self.debug)
            self.connected = False

    async def close(self) -> None:
        if self.rpc and self.connected:
            try:
                await self.rpc.close()
            except Exception as e:
                logger.error("Error closing RPC: %s", e, exc_info=self.debug)
        self.rpc = None
        self.connected = False
