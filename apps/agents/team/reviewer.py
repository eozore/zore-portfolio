"""
Revisor sub-agent — validates content against brand voice, facts, and limits.

The Revisor checks:
- Brand voice alignment
- Character limits per platform (LinkedIn ≤ 3000, Instagram ≤ 2200, YouTube ≤ 5000)
- Hashtag count (Instagram ≤ 30)
- Grammar and style
- Content policies compliance
- Factual accuracy

Emits "APROVADO" when all criteria pass, or structured corrections otherwise.
Emits "REJEITADO_TERMINAL" for plagiarism, factual errors, or policy violations.

Requirements: 7.1, 7.3, 7.5, 7.6
"""

from __future__ import annotations

from typing import Any

try:
    from google.adk.agents import LlmAgent

    from apps.agents.models import get_model_for_role
    from apps.agents.team.prompts import REVISOR_PROMPT

    # ---------------------------------------------------------------------------
    # Agent definition
    # ---------------------------------------------------------------------------

    revisor_agent = LlmAgent(
        name="revisor",
        model=get_model_for_role("reviewer"),
        instruction=REVISOR_PROMPT,
        sub_agents=[],
    )
except ImportError:  # pragma: no cover — google.adk not available locally

    def __getattr__(name: str) -> Any:  # noqa: ANN001
        if name == "revisor_agent":
            raise ImportError(
                "google.adk is not installed. Cannot instantiate revisor_agent."
            )
        raise AttributeError(
            f"module 'apps.agents.team.reviewer' has no attribute {name!r}"
        )
