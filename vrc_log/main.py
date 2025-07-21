import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Set, TypedDict, cast

import coloredlogs
import aiohttp
from vrc_log.discord_rpc import DiscordRPC
from vrc_log.utils import parse_avatar_ids, print_colorized
from vrc_log.vrchat import get_vrchat_paths
from vrc_log.watcher import Watcher
from vrc_log.provider import get_providers
from vrc_log.settings import Settings, get_settings
from vrc_log import __version__

logger = logging.getLogger(__name__)


class AvatarMetadata(TypedDict, total=False):
    id: str
    name: str
    author_name: str
    description: str
    image_url: str


class AvatarState:
    __slots__ = ("latest_avatar_id", "metadata")

    def __init__(self) -> None:
        self.latest_avatar_id: Optional[str] = None
        self.metadata: Optional[Dict[str, str]] = None


async def fetch_avatar_metadata(avatar_id: str) -> Optional[Dict[str, str]]:
    url = f"https://paw-api.amelia.fun/avatar?avatarId={avatar_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    result: Dict[str, Any] = await response.json()
                    avatar_data_raw = result.get("result")

                    if not isinstance(avatar_data_raw, dict):
                        logger.error("Invalid avatar data format")
                        return None

                    avatar_data: AvatarMetadata = cast(AvatarMetadata, avatar_data_raw)
                    return {
                        "id": avatar_id,
                        "name": str(avatar_data.get("name", "")).strip()
                        or "Unknown Avatar",
                        "author_name": str(avatar_data.get("author_name", "")).strip()
                        or "Unknown Author",
                        "description": str(avatar_data.get("description", "")).strip()
                        or "No description available",
                        "image_url": str(avatar_data.get("image_url", "")).strip(),
                    }
                logger.error("Metadata fetch failed: HTTP %d", response.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        logger.error("Network error: %s", e)
    except Exception as e:
        logger.exception("Metadata error: %s", e)
    return None


async def update_rpc_periodically(
    state: AvatarState,
    rpc: Optional[DiscordRPC],
    shutdown_event: asyncio.Event,
    interval: int = 20,
) -> None:
    logger.info("Starting RPC updates (%ds)", interval)
    while not shutdown_event.is_set():
        await asyncio.sleep(interval)

        if not rpc or not rpc.connected:
            continue

        if state.latest_avatar_id:
            if state.metadata is None or state.metadata["id"] != state.latest_avatar_id:
                metadata = await fetch_avatar_metadata(state.latest_avatar_id)
                state.metadata = metadata or state.metadata

            if state.metadata:
                try:
                    await rpc.update_avatar_presence(
                        name=state.metadata["name"],
                        author_name=state.metadata["author_name"],
                        description=state.metadata["description"],
                        image_url=state.metadata.get("image_url"),
                    )
                    continue
                except Exception as e:
                    logger.error("RPC update failed: %s", e)

        await rpc.update_presence("Watching for logs")
    logger.info("RPC updates stopped")


async def process_avatars(
    queue: asyncio.Queue[str],
    shutdown_event: asyncio.Event,
    rpc: Optional[DiscordRPC],
    settings: Settings,
    state: AvatarState,
) -> None:
    from vrc_log.provider.cache import Cache

    logger.info("Starting avatar processing")
    cache = Cache()
    providers = get_providers(settings)
    processed_ids: Set[str] = set()

    while not shutdown_event.is_set() or not queue.empty():
        try:
            path = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue

        try:
            avatar_ids = parse_avatar_ids(Path(path))
            if not avatar_ids:
                continue

            if rpc:
                await rpc.update_presence("Processing avatars")

            for avatar_id in avatar_ids:
                if shutdown_event.is_set():
                    break
                if avatar_id in processed_ids:
                    continue

                if await cache.check_avatar_id(avatar_id):
                    logger.info("Processing new avatar: %s", avatar_id)
                    processed_ids.add(avatar_id)
                    print_colorized(avatar_id)

                    if providers:
                        success = False
                        for provider in providers:
                            try:
                                if await provider.send_avatar_id(avatar_id):
                                    success = True
                                    logger.info("Uploaded to %s", provider.kind)
                                else:
                                    logger.warning("%s failed", provider.kind)
                            except Exception as e:
                                logger.exception("%s error: %s", provider.kind, e)

                        if success:
                            state.latest_avatar_id = avatar_id
        finally:
            queue.task_done()
            if rpc and queue.empty():
                await rpc.update_presence("Watching for logs")

    logger.info("Processed %d avatars", len(processed_ids))


def get_latest_log_file(log_dir: Path) -> Optional[Path]:
    try:
        return max(
            log_dir.glob("output_log_*.txt"),
            key=lambda p: p.stat().st_mtime,
            default=None,
        )
    except Exception:
        return None


async def main() -> None:
    shutdown_event = asyncio.Event()
    settings: Settings = get_settings()
    state = AvatarState()

    coloredlogs.install(  # type: ignore
        level=logging.DEBUG if settings.debug_logging else logging.INFO,
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("Starting VRCLogX v%s", __version__)

    rpc: Optional[DiscordRPC] = None
    rpc_task: Optional[asyncio.Task[None]] = None
    amp_path, low_path = get_vrchat_paths()
    logger.info("VRChat paths - AMP: %s, LOW: %s", amp_path, low_path)

    try:
        loop = asyncio.get_running_loop()
        if sys.platform != "win32":
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, shutdown_event.set)

        rpc = DiscordRPC(settings.debug_logging)
        await rpc.connect()
        await rpc.update_presence("Starting up")
        rpc_task = asyncio.create_task(
            update_rpc_periodically(state, rpc, shutdown_event)
        )

        queue: asyncio.Queue[str] = asyncio.Queue()
        watcher = Watcher(queue, shutdown_event)

        for path in (amp_path, low_path):
            if path.exists():
                watcher.watch(path)
                logger.info("Watching path: %s", path)

        if low_path.exists():
            if latest_log := get_latest_log_file(low_path):
                watcher.watch(latest_log)
                logger.info("Watching log: %s", latest_log)

        watcher_task = asyncio.create_task(watcher.start())
        await process_avatars(queue, shutdown_event, rpc, settings, state)
        watcher_task.cancel()

    except Exception as e:
        logger.exception("Critical error: %s", e)
    finally:
        shutdown_event.set()
        if rpc_task:
            rpc_task.cancel()
            await rpc_task
        if rpc:
            await rpc.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nVRCLogX interrupted")
    except Exception as e:
        logging.exception("Fatal error: %s", e)
