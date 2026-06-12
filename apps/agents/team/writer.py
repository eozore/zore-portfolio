"""
Roteirista sub-agent — produces content drafts in markdown and platform variants.

The Roteirista creates:
- Blog article in Markdown
- LinkedIn post variant (≤ 3000 chars)
- Instagram caption (≤ 2200 chars, ≤ 30 hashtags)
- YouTube description (≤ 5000 chars)

All outputs respect the tenant's configured brand voice (brandVoice).
Works iteratively with the Revisor inside a LoopAgent.

Requirements: 7.1, 7.2, 7.3, 7.4
"""

from __future__ import annotations

from typing import Any

try:
    from google.adk.agents import LlmAgent

    from apps.agents.models import get_model_for_role
    from apps.agents.team.prompts import ROTEIRISTA_PROMPT

    # ---------------------------------------------------------------------------
    # Agent definition
    # ---------------------------------------------------------------------------

    roteirista_agent = LlmAgent(
        name="roteirista",
        model=get_model_for_role("writer"),
        instruction=ROTEIRISTA_PROMPT,
        sub_agents=[],
    )
except ImportError:  # pragma: no cover — google.adk not available locally

    def __getattr__(name: str) -> Any:  # noqa: ANN001
        if name == "roteirista_agent":
            raise ImportError(
                "google.adk is not installed. Cannot instantiate roteirista_agent."
            )
        raise AttributeError(
            f"module 'apps.agents.team.writer' has no attribute {name!r}"
        )
