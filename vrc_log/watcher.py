import asyncio
import logging
from pathlib import Path
from typing import Dict, Set

logger = logging.getLogger(__name__)


class Watcher:
    def __init__(
        self,
        queue: asyncio.Queue[str],
        shutdown_event: asyncio.Event,
    ) -> None:
        self.queue: asyncio.Queue[str] = queue
        self.watched_files: Dict[Path, float] = {}
        self.shutdown_event: asyncio.Event = shutdown_event

    def watch(self, path: Path) -> None:
        try:
            if path.is_file() and path.stat().st_size > 0:
                self.watched_files[path] = path.stat().st_mtime
            elif path.is_dir():
                logger.debug("Skipping directory: %s", path)
        except Exception as e:
            logger.exception("Path error: %s", e)

    async def start(self) -> None:
        while not self.shutdown_event.is_set():
            try:
                paths_to_remove: Set[Path] = set()
                for path, last_mtime in list(self.watched_files.items()):
                    if self.shutdown_event.is_set():
                        break

                    try:
                        if not path.exists():
                            paths_to_remove.add(path)
                            continue

                        current_mtime = path.stat().st_mtime
                        if current_mtime > last_mtime:
                            self.watched_files[path] = current_mtime
                            await self.queue.put(str(path))
                    except Exception as e:
                        logger.exception("File error: %s", e)
                        paths_to_remove.add(path)

                for path in paths_to_remove:
                    self.watched_files.pop(path, None)
            except Exception as e:
                logger.exception("Watcher error: %s", e)

            await asyncio.sleep(1)
