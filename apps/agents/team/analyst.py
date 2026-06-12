"""
Analista sub-agent — collects post-publication metrics and closes the cycle.

The Analista pulls performance data after content is published, identifies
patterns, and produces reports that feed back to the Estrategista for
continuous improvement of the content strategy.

Requirements: 5.1, 15.2
"""

from __future__ import annotations

from google.adk.agents import LlmAgent

from apps.agents.models import get_model_for_role
from apps.agents.team.prompts import ANALISTA_PROMPT


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

analista_agent = LlmAgent(
    name="analista",
    model=get_model_for_role("analyst"),
    instruction=ANALISTA_PROMPT,
    sub_agents=[],
)
