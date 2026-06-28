"""Result of attempting to send a channel comment."""

from typing import NamedTuple, Optional


class CommentSendResult(NamedTuple):
    success: bool
    exclude_channel: bool = False
    error_message: Optional[str] = None

