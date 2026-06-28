"""Result of attempting to send a channel comment."""

from typing import NamedTuple


class CommentSendResult(NamedTuple):
    success: bool
    exclude_channel: bool = False
