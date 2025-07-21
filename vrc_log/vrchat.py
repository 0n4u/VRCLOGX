import os
import platform
import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def get_windows_paths() -> Tuple[Path, Path]:
    return (
        Path(os.getenv("TEMP", "")) / "VRChat" / "VRChat" / "amplitude.cache",
        Path(os.getenv("LOCALAPPDATA", "")) / "Low" / "VRChat" / "VRChat",
    )


def get_linux_paths() -> Tuple[Path, Path]:
    steam_dir = Path.home() / ".local" / "share" / "Steam" / "steamapps" / "compatdata"
    vrchat_appid = "438100"
    compat_path = steam_dir / vrchat_appid

    if not compat_path.exists():
        compat_dirs = [
            d for d in steam_dir.iterdir() if d.is_dir() and d.name.isdigit()
        ]
        if compat_dirs:
            compat_path = max(compat_dirs, key=lambda d: d.stat().st_mtime)

    base_path = compat_path / "pfx" / "drive_c" / "users" / "steamuser"
    return (
        base_path / "Temp" / "VRChat" / "VRChat" / "amplitude.cache",
        base_path / "AppData" / "LocalLow" / "VRChat" / "VRChat",
    )


def get_vrchat_paths() -> Tuple[Path, Path]:
    return get_windows_paths() if platform.system() == "Windows" else get_linux_paths()
