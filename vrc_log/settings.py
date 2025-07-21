import logging

logger = logging.getLogger(__name__)


class Settings:
    def __init__(self) -> None:
        self.debug_logging: bool = False
        self.upload_avatar_ids: bool = True
        self.providers: list[str] = ["AVTRDB", "PAW", "VRCWB"]


def get_settings() -> Settings:
    return Settings()
