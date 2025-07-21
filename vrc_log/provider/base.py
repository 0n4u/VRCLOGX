import abc
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProviderProtocol(Protocol):
    kind: str

    async def send_avatar_id(self, avatar_id: str) -> bool: ...


class BaseProvider(abc.ABC):
    kind: str = ""

    @abc.abstractmethod
    async def send_avatar_id(self, avatar_id: str) -> bool:
        raise NotImplementedError("Providers must implement send_avatar_id")
