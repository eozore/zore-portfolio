"""
Team sub-agents package — specialized agents for the Agentic Marketing Platform.

This package contains the sub-agents coordinated by the Director:
- Estrategista: Generates weekly content calendars (5-7 items)
- Pesquisador: Researches trends and opportunities
- Analista: Collects post-publication metrics and feeds back to strategy
- Roteirista: Produces content drafts (blog + platform variants)
- Revisor: Validates content quality (brand voice, limits, facts)
- LoopAgent (writing_loop): Iterates Roteirista ↔ Revisor until approval
- Produtor de Mídia: Generates HTML/CSS templates for visual assets
- Publicador: Executes publication gate and publishes via MCP

Requirements: 5.1, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 10.1, 10.5, 15.2, 19.1, 19.2, 19.4, 19.5, 22.1, 22.3
"""

from __future__ import annotations

__all__ = [
    "estrategista_agent",
    "pesquisador_agent",
    "analista_agent",
    "roteirista_agent",
    "revisor_agent",
    "writing_loop_agent",
    "produtor_agent",
    "publicador_agent",
]


def __getattr__(name: str):  # noqa: ANN001
    """Lazy-load agents to avoid importing google.adk at module level."""
    if name == "estrategista_agent":
        from apps.agents.team.strategist import estrategista_agent

        return estrategista_agent
    if name == "pesquisador_agent":
        from apps.agents.team.researcher import pesquisador_agent

        return pesquisador_agent
    if name == "analista_agent":
        from apps.agents.team.analyst import analista_agent

        return analista_agent
    if name == "roteirista_agent":
        from apps.agents.team.writer import roteirista_agent

        return roteirista_agent
    if name == "revisor_agent":
        from apps.agents.team.reviewer import revisor_agent

        return revisor_agent
    if name == "writing_loop_agent":
        from apps.agents.team.writing_loop import writing_loop_agent

        return writing_loop_agent
    if name == "produtor_agent":
        from apps.agents.team.producer import produtor_agent

        return produtor_agent
    if name == "publicador_agent":
        from apps.agents.team.publisher import publicador_agent

        return publicador_agent
    raise AttributeError(f"module 'apps.agents.team' has no attribute {name!r}")
