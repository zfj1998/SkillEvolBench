"""Pinned OpenCode continuity markers shared by the adapter and hook.

The raw OpenCode export remains the source of truth.  These optional ATIF
markers preserve just enough of OpenCode 1.18.3's automatic compaction shape
for the independently generated canonical trajectory to be checked as well.
Trajectories without a compaction turn are unchanged.
"""

from __future__ import annotations


OPENCODE_EVENT_KEY = "opencode_event"
OPENCODE_AUTO_COMPACTION_KIND = "auto_compaction"
OPENCODE_COMPACTION_SUMMARY_KIND = "compaction_summary"
OPENCODE_COMPACTION_CONTINUE_KIND = "compaction_continue"
OPENCODE_POST_COMPACTION_ASSISTANT_KIND = "post_compaction_assistant"
OPENCODE_SYNTHETIC_CONTINUE = (
    "Continue if you have next steps, or stop and ask for clarification if you "
    "are unsure how to proceed."
)
_OPENCODE_OVERFLOW_CONTINUE_PREFIX = (
    "The previous request exceeded the provider's size limit due to large media "
    "attachments.\n"
    "The conversation was compacted and media files were removed from context.\n"
    "If the user was asking about attached images or files, explain that the "
    "attachments were too large to process and suggest they try again with "
    "smaller or fewer files.\n\n"
)


def opencode_synthetic_continue(*, overflow: bool) -> str:
    """Return the exact OpenCode 1.18.3 auto-continuation text."""

    prefix = _OPENCODE_OVERFLOW_CONTINUE_PREFIX if overflow else ""
    return prefix + OPENCODE_SYNTHETIC_CONTINUE


__all__ = [
    "OPENCODE_AUTO_COMPACTION_KIND",
    "OPENCODE_COMPACTION_CONTINUE_KIND",
    "OPENCODE_COMPACTION_SUMMARY_KIND",
    "OPENCODE_EVENT_KEY",
    "OPENCODE_POST_COMPACTION_ASSISTANT_KIND",
    "OPENCODE_SYNTHETIC_CONTINUE",
    "opencode_synthetic_continue",
]
