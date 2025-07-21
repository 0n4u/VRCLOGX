import re
import logging
from pathlib import Path
from typing import List, Pattern, Set

logger = logging.getLogger(__name__)
AVATAR_ID_PATTERN: Pattern[str] = re.compile(
    r"avtr_[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}"
)


def parse_avatar_ids(path: Path) -> List[str]:
    if not path.is_file():
        return []

    avatar_ids: Set[str] = set()
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                avatar_ids.update(AVATAR_ID_PATTERN.findall(line))
    except Exception as e:
        logger.exception("File read error: %s", e)
    return list(avatar_ids)


class ColorCycler:
    def __init__(self) -> None:
        self.index: int = 0
        self.colors = ["red", "green", "yellow", "blue", "magenta", "cyan"]

    def next_color(self) -> int:
        color_code = 31 + (self.index % 6)
        self.index = (self.index + 1) % 6
        return color_code


color_cycler = ColorCycler()


def print_colorized(avatar_id: str) -> None:
    color_code = color_cycler.next_color()
    print(f"\033[1;{color_code}mvrcx://avatar/{avatar_id}\033[0m")
