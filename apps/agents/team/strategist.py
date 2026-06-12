"""
Estrategista sub-agent — generates weekly content calendars.

The Estrategista creates 5-7 calendar items per week based on the tenant's
profile (persona, niche, goals) and performance data from the Analista.
It validates against the last 4 weeks to avoid repetition and ensures
minimum 24h spacing between items on the same platform.

Requirements: 5.1, 15.2
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from apps.agents.models import get_model_for_role
from apps.agents.team.prompts import ESTRATEGISTA_PROMPT


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

estrategista_agent = LlmAgent(
    name="estrategista",
    model=get_model_for_role("strategist"),
    instruction=ESTRATEGISTA_PROMPT,
    sub_agents=[],
)
