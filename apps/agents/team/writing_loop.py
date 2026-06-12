"""
Writing Loop — LoopAgent orchestrating Roteirista ↔ Revisor iterations.

The LoopAgent runs the Roteirista and Revisor iteratively:
- max_iterations=5
- Exit condition: Revisor emits "APROVADO" or "REJEITADO_TERMINAL"
- Otherwise: corrections are passed back and the loop continues

Each iteration preserves an intermediate version associated with a task_id
and iteration_number for auditing and version history.

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from google.adk.agents import LoopAgent

    _ADK_AVAILABLE = True
except ImportError:  # pragma: no cover
    _ADK_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_LOOP_ITERATIONS = 5
"""Maximum number of Roteirista ↔ Revisor iterations before forced exit."""

EXIT_KEYWORD_APPROVED = "APROVADO"
"""Keyword emitted by the Revisor to signal content approval."""

EXIT_KEYWORD_REJECTED = "REJEITADO_TERMINAL"
"""Keyword emitted by the Revisor for fatal rejection (plagiarism, policy)."""


# ---------------------------------------------------------------------------
# Version Tracking
# ---------------------------------------------------------------------------


@dataclass
class ContentIteration:
    """Represents a single iteration's content snapshot."""

    task_id: str
    iteration_number: int
    content: str
    reviewer_verdict: str | None = None
    corrections: list[dict[str, str]] = field(default_factory=list)


class VersionTracker:
    """
    Tracks intermediate versions produced during the writing loop.

    Each iteration stores the content produced by the Roteirista and
    the verdict/corrections from the Revisor, associated with a task_id
    and iteration_number.

    Requirements: 7.7
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        self._versions: list[ContentIteration] = []

    @property
    def iterations(self) -> list[ContentIteration]:
        """Return all preserved iterations."""
        return list(self._versions)

    @property
    def current_iteration(self) -> int:
        """Return the current iteration number (1-based)."""
        return len(self._versions)

    @property
    def latest_content(self) -> str | None:
        """Return the latest content produced, or None if no iterations yet."""
        if not self._versions:
            return None
        return self._versions[-1].content

    def record_iteration(
        self,
        content: str,
        reviewer_verdict: str | None = None,
        corrections: list[dict[str, str]] | None = None,
    ) -> ContentIteration:
        """
        Record a new iteration snapshot.

        Args:
            content: The content produced by the Roteirista in this iteration.
            reviewer_verdict: The Revisor's verdict (APROVADO, CORREÇÕES, REJEITADO_TERMINAL).
            corrections: List of correction dicts with keys: excerpt, violation_type, instruction.

        Returns:
            The recorded ContentIteration.
        """
        iteration = ContentIteration(
            task_id=self.task_id,
            iteration_number=self.current_iteration + 1,
            content=content,
            reviewer_verdict=reviewer_verdict,
            corrections=corrections or [],
        )
        self._versions.append(iteration)
        return iteration


# ---------------------------------------------------------------------------
# Exit condition helper
# ---------------------------------------------------------------------------


def should_exit_loop(reviewer_output: str) -> bool:
    """
    Determine if the LoopAgent should exit based on Revisor output.

    Returns True if the Revisor approved the content or issued a terminal
    rejection (plagiarism, factual errors, policy violations).

    Args:
        reviewer_output: The text output from the Revisor agent.

    Returns:
        True if the loop should terminate.
    """
    return (
        EXIT_KEYWORD_APPROVED in reviewer_output
        or EXIT_KEYWORD_REJECTED in reviewer_output
    )


# ---------------------------------------------------------------------------
# LoopAgent definition
# ---------------------------------------------------------------------------


def _build_writing_loop_agent() -> Any:
    """
    Build the LoopAgent combining Roteirista and Revisor.

    Separated into a factory to avoid import errors when google.adk
    is not available locally (e.g., during unit tests of other components).
    """
    if not _ADK_AVAILABLE:
        raise ImportError(
            "google.adk is not installed. Cannot build writing_loop_agent."
        )

    from google.adk.agents import LoopAgent  # noqa: F811

    from apps.agents.team.writer import roteirista_agent
    from apps.agents.team.reviewer import revisor_agent

    return LoopAgent(
        name="loop_escrita_revisao",
        sub_agents=[roteirista_agent, revisor_agent],
        max_iterations=MAX_LOOP_ITERATIONS,
    )


# Eagerly build when ADK is available; otherwise expose lazy accessor
if _ADK_AVAILABLE:
    writing_loop_agent = _build_writing_loop_agent()
else:

    def __getattr__(name: str) -> Any:  # noqa: ANN001
        if name == "writing_loop_agent":
            return _build_writing_loop_agent()
        raise AttributeError(
            f"module 'apps.agents.team.writing_loop' has no attribute {name!r}"
        )
