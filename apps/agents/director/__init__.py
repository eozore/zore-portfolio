"""
Director agent package — root orchestrator for the Agentic Marketing Platform.

The Director is the ADK root_agent that receives user messages, identifies
task types, and delegates to the appropriate sub-agents while injecting
tenant context (brand voice, niche, persona, calendar, settings).

Requirements: 6.1, 6.2, 6.3, 6.4
"""

from apps.agents.director.agent import (
    DelegationContext,
    create_director_agent,
    director_agent,
)

__all__ = ["director_agent", "create_director_agent", "DelegationContext"]
