"""Source Protocol for raw 802.11 frames."""

from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class FrameSource(Protocol):
    def __iter__(self) -> Iterator[Any]: ...
    def close(self) -> None: ...
