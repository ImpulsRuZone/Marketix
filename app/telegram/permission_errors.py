"""Detect Telegram permission errors that require channel exclusion."""

from typing import Optional

# Exact error from GetDiscussionMessageRequest when linked group is inaccessible
MANDATORY_EXCLUSION_MARKER = "private and you lack permission"

_OTHER_PERMISSION_MARKERS = (
    "getdiscussionmessage",
    "channel_private",
    "chat_write_forbidden",
    "you were banned",
)


def get_permission_error_text(exc: Exception) -> str:
    return str(exc).strip()


def is_mandatory_exclusion_error(exc: Exception) -> bool:
    """True for: private and you lack permission (required exclusion trigger)."""
    return MANDATORY_EXCLUSION_MARKER in get_permission_error_text(exc).lower()


def is_permission_error(exc: Exception) -> bool:
    """Broader permission/access errors (retry join, may also exclude)."""
    text = get_permission_error_text(exc).lower()
    if is_mandatory_exclusion_error(exc):
        return True
    return any(marker in text for marker in _OTHER_PERMISSION_MARKERS)


def should_exclude_channel(exc: Exception) -> bool:
    """Channel must be removed from monitoring for this error."""
    return is_mandatory_exclusion_error(exc) or is_permission_error(exc)
