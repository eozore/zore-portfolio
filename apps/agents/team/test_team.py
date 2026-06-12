"""
Tests for team sub-agents (Estrategista, Pesquisador, Analista).

Validates:
- Each agent uses the correct model from models.py
- Each agent has a non-empty instruction (prompt)
- Prompts contain key elements per the design spec
- Agent names match the expected ADK identifiers

Requirements: 5.1, 15.2
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from apps.agents.team.prompts import (
    ANALISTA_PROMPT,
    ESTRATEGISTA_PROMPT,
    PESQUISADOR_PROMPT,
)


# ---------------------------------------------------------------------------
# Strategist (Estrategista) Tests
# ---------------------------------------------------------------------------


class TestEstrategistaAgent:
    """Tests for the Estrategista sub-agent."""

    def test_agent_creation_with_adk(self) -> None:
        """Verify agent instantiates correctly when google.adk is available."""
        try:
            from apps.agents.team.strategist import estrategista_agent

            assert estrategista_agent is not None
            assert estrategista_agent.name == "estrategista"
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_prompt_not_empty(self) -> None:
        """Verify ESTRATEGISTA_PROMPT is defined and non-empty."""
        assert len(ESTRATEGISTA_PROMPT) > 100

    def test_prompt_mentions_calendar(self) -> None:
        """Prompt must reference calendar generation (5-7 items)."""
        assert "5" in ESTRATEGISTA_PROMPT
        assert "7" in ESTRATEGISTA_PROMPT
        assert "calendário" in ESTRATEGISTA_PROMPT.lower()

    def test_prompt_mentions_pillars(self) -> None:
        """Prompt must reference content pillars."""
        assert "pilar" in ESTRATEGISTA_PROMPT.lower()

    def test_prompt_mentions_spacing(self) -> None:
        """Prompt must reference 24h minimum spacing."""
        assert "24" in ESTRATEGISTA_PROMPT

    def test_prompt_mentions_no_repetition(self) -> None:
        """Prompt must reference not repeating recent topics (last 4 weeks)."""
        assert "4 semanas" in ESTRATEGISTA_PROMPT

    def test_prompt_in_portuguese(self) -> None:
        """Prompt must be written in Portuguese."""
        assert "Você" in ESTRATEGISTA_PROMPT
        assert "Português" in ESTRATEGISTA_PROMPT

    def test_prompt_mentions_proposed_status(self) -> None:
        """Prompt must reference status=proposed for new items."""
        assert "proposed" in ESTRATEGISTA_PROMPT

    def test_prompt_mentions_json_output(self) -> None:
        """Prompt must define JSON output format."""
        assert "json" in ESTRATEGISTA_PROMPT.lower()
        assert "calendar_items" in ESTRATEGISTA_PROMPT

    def test_uses_correct_model(self) -> None:
        """Estrategista should use the 'strategist' role model (Pro tier)."""
        from apps.agents.models import get_model_for_role

        model = get_model_for_role("strategist")
        assert model == "gemini-2.5-pro"

    def test_uses_env_override(self) -> None:
        """Environment variable MODEL_STRATEGIST should override default."""
        from apps.agents.models import get_model_for_role

        with patch.dict(os.environ, {"MODEL_STRATEGIST": "custom-model-id"}):
            assert get_model_for_role("strategist") == "custom-model-id"


# ---------------------------------------------------------------------------
# Researcher (Pesquisador) Tests
# ---------------------------------------------------------------------------


class TestPesquisadorAgent:
    """Tests for the Pesquisador sub-agent."""

    def test_agent_creation_with_adk(self) -> None:
        """Verify agent instantiates correctly when google.adk is available."""
        try:
            from apps.agents.team.researcher import pesquisador_agent

            assert pesquisador_agent is not None
            assert pesquisador_agent.name == "pesquisador"
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_prompt_not_empty(self) -> None:
        """Verify PESQUISADOR_PROMPT is defined and non-empty."""
        assert len(PESQUISADOR_PROMPT) > 100

    def test_prompt_mentions_trends(self) -> None:
        """Prompt must reference trend research."""
        assert "tendência" in PESQUISADOR_PROMPT.lower() or "tendências" in PESQUISADOR_PROMPT.lower()

    def test_prompt_mentions_sources(self) -> None:
        """Prompt must require sources/references."""
        assert "fonte" in PESQUISADOR_PROMPT.lower() or "fontes" in PESQUISADOR_PROMPT.lower()

    def test_prompt_mentions_real_search(self) -> None:
        """Prompt must reference real web search."""
        assert "busca" in PESQUISADOR_PROMPT.lower() or "pesquisa real" in PESQUISADOR_PROMPT.lower()

    def test_prompt_mentions_opportunities(self) -> None:
        """Prompt must reference opportunity identification."""
        assert "oportunidade" in PESQUISADOR_PROMPT.lower() or "oportunidades" in PESQUISADOR_PROMPT.lower()

    def test_prompt_in_portuguese(self) -> None:
        """Prompt must be written in Portuguese."""
        assert "Você" in PESQUISADOR_PROMPT
        assert "Português" in PESQUISADOR_PROMPT

    def test_prompt_mentions_competition(self) -> None:
        """Prompt must reference competition analysis."""
        assert "concorrência" in PESQUISADOR_PROMPT.lower() or "concorrente" in PESQUISADOR_PROMPT.lower()

    def test_prompt_mentions_json_output(self) -> None:
        """Prompt must define structured JSON output."""
        assert "json" in PESQUISADOR_PROMPT.lower()
        assert "report" in PESQUISADOR_PROMPT

    def test_uses_correct_model(self) -> None:
        """Pesquisador should use the 'researcher' role model (Flash tier)."""
        from apps.agents.models import get_model_for_role

        model = get_model_for_role("researcher")
        assert model == "gemini-2.5-flash"

    def test_uses_env_override(self) -> None:
        """Environment variable MODEL_RESEARCHER should override default."""
        from apps.agents.models import get_model_for_role

        with patch.dict(os.environ, {"MODEL_RESEARCHER": "custom-flash"}):
            assert get_model_for_role("researcher") == "custom-flash"


# ---------------------------------------------------------------------------
# Analyst (Analista) Tests
# ---------------------------------------------------------------------------


class TestAnalistaAgent:
    """Tests for the Analista sub-agent."""

    def test_agent_creation_with_adk(self) -> None:
        """Verify agent instantiates correctly when google.adk is available."""
        try:
            from apps.agents.team.analyst import analista_agent

            assert analista_agent is not None
            assert analista_agent.name == "analista"
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_prompt_not_empty(self) -> None:
        """Verify ANALISTA_PROMPT is defined and non-empty."""
        assert len(ANALISTA_PROMPT) > 100

    def test_prompt_mentions_metrics(self) -> None:
        """Prompt must reference metric collection."""
        assert "métrica" in ANALISTA_PROMPT.lower() or "métricas" in ANALISTA_PROMPT.lower()

    def test_prompt_mentions_performance(self) -> None:
        """Prompt must reference performance analysis."""
        assert "performance" in ANALISTA_PROMPT.lower()

    def test_prompt_mentions_feedback_to_strategist(self) -> None:
        """Prompt must reference feeding data back to the Estrategista."""
        assert "estrategista" in ANALISTA_PROMPT.lower()

    def test_prompt_mentions_report(self) -> None:
        """Prompt must reference report deliverable."""
        assert "relatório" in ANALISTA_PROMPT.lower()

    def test_prompt_in_portuguese(self) -> None:
        """Prompt must be written in Portuguese."""
        assert "Você" in ANALISTA_PROMPT
        assert "Português" in ANALISTA_PROMPT

    def test_prompt_mentions_patterns(self) -> None:
        """Prompt must reference pattern identification."""
        assert "padrão" in ANALISTA_PROMPT.lower() or "padrões" in ANALISTA_PROMPT.lower()

    def test_prompt_mentions_json_output(self) -> None:
        """Prompt must define structured JSON output."""
        assert "json" in ANALISTA_PROMPT.lower()
        assert "report" in ANALISTA_PROMPT

    def test_uses_correct_model(self) -> None:
        """Analista should use the 'analyst' role model (Flash tier)."""
        from apps.agents.models import get_model_for_role

        model = get_model_for_role("analyst")
        assert model == "gemini-2.5-flash"

    def test_uses_env_override(self) -> None:
        """Environment variable MODEL_ANALYST should override default."""
        from apps.agents.models import get_model_for_role

        with patch.dict(os.environ, {"MODEL_ANALYST": "custom-analyst"}):
            assert get_model_for_role("analyst") == "custom-analyst"


# ---------------------------------------------------------------------------
# Package-level Tests
# ---------------------------------------------------------------------------


class TestTeamPackage:
    """Tests for the team package __init__.py exports."""

    def test_package_exports_exist(self) -> None:
        """Verify __init__.py exports all sub-agents."""
        try:
            from apps.agents.team import (
                estrategista_agent,
                pesquisador_agent,
                analista_agent,
            )

            assert estrategista_agent is not None
            assert pesquisador_agent is not None
            assert analista_agent is not None
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_agent_names_are_correct(self) -> None:
        """Verify agent names match expected ADK identifiers."""
        try:
            from apps.agents.team import (
                estrategista_agent,
                pesquisador_agent,
                analista_agent,
            )

            assert estrategista_agent.name == "estrategista"
            assert pesquisador_agent.name == "pesquisador"
            assert analista_agent.name == "analista"
        except ImportError:
            pytest.skip("google.adk not available locally")
