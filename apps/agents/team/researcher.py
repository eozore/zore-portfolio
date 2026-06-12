"""
Pesquisador sub-agent — researches trends and opportunities.

The Pesquisador searches for trending topics, content angles, competition
analysis, and market opportunities relevant to the tenant's niche. It delivers
structured reports with sources for the Estrategista and Roteirista to use.

Requirements: 5.1, 15.2
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from apps.agents.models import get_model_for_role
from apps.agents.team.prompts import PESQUISADOR_PROMPT


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

pesquisador_agent = LlmAgent(
    name="pesquisador",
    model=get_model_for_role("researcher"),
    instruction=PESQUISADOR_PROMPT,
    sub_agents=[],
)
