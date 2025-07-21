import logging
from typing import List, Type

from vrc_log.settings import Settings
from .avtrdb import AvtrDB
from .paw import Paw
from .vrcwb import VrcWB
from .base import BaseProvider

logger = logging.getLogger(__name__)


def get_providers(settings: Settings) -> List[BaseProvider]:
    if not settings.upload_avatar_ids:
        return []

    provider_map: dict[str, Type[BaseProvider]] = {
        "AVTRDB": AvtrDB,
        "PAW": Paw,
        "VRCWB": VrcWB,
    }

    providers: List[BaseProvider] = []
    for provider_id in settings.providers:
        provider_class = provider_map.get(provider_id)
        if provider_class is not None:
            try:
                providers.append(provider_class())
            except Exception as e:
                logger.error("Provider init failed [%s]: %s", provider_id, e)

    return providers
