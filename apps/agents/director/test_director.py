"""
Unit tests for the Director agent module.

Tests cover:
- DelegationContext dataclass creation and defaults
- Task type identification from user messages
- Delegation context prompt building
- Director agent instantiation with correct model
"""

from __future__ import annotations

import pytest

from apps.agents.director.agent import (
    DelegationContext,
    TASK_TYPE_ROUTES,
    build_delegation_context_prompt,
    create_director_agent,
    identify_task_type,
)
from apps.agents.director.prompts import DIRETOR_PROMPT


# ---------------------------------------------------------------------------
# DelegationContext tests
# ---------------------------------------------------------------------------


class TestDelegationContext:
    """Tests for the DelegationContext dataclass."""

    def test_minimal_creation(self) -> None:
        """Can create with just tenant_id."""
        ctx = DelegationContext(tenant_id="tenant_123")
        assert ctx.tenant_id == "tenant_123"
        assert ctx.brand_voice == ""
        assert ctx.niche == ""
        assert ctx.persona == ""
        assert ctx.languages == []
        assert ctx.current_calendar == []
        assert ctx.active_connections == []
        assert ctx.publish_settings == {}

    def test_full_creation(self) -> None:
        """Can create with all fields populated."""
        ctx = DelegationContext(
            tenant_id="tenant_abc",
            brand_voice="Tom profissional e acessível",
            niche="Marketing Digital para SaaS",
            persona="Fundador de startup B2B, 30-45 anos",
            languages=["pt", "en"],
            current_calendar=[
                {"platform": "linkedin", "format": "linkedin_post", "status": "proposed", "plannedFor": "2025-01-15"}
            ],
            active_connections=["linkedin", "youtube"],
            publish_settings={"blog": True, "linkedin_post": False},
        )
        assert ctx.tenant_id == "tenant_abc"
        assert ctx.brand_voice == "Tom profissional e acessível"
        assert ctx.niche == "Marketing Digital para SaaS"
        assert ctx.persona == "Fundador de startup B2B, 30-45 anos"
        assert ctx.languages == ["pt", "en"]
        assert len(ctx.current_calendar) == 1
        assert ctx.active_connections == ["linkedin", "youtube"]
        assert ctx.publish_settings == {"blog": True, "linkedin_post": False}

    def test_mutable_defaults_are_independent(self) -> None:
        """Each instance gets its own mutable defaults (no shared state)."""
        ctx1 = DelegationContext(tenant_id="a")
        ctx2 = DelegationContext(tenant_id="b")
        ctx1.languages.append("pt")
        assert ctx2.languages == []


# ---------------------------------------------------------------------------
# Task type identification tests
# ---------------------------------------------------------------------------


class TestIdentifyTaskType:
    """Tests for the identify_task_type helper."""

    def test_content_keywords(self) -> None:
        """Detects content creation tasks."""
        result = identify_task_type("Escreva um artigo sobre IA")
        assert "content" in result

    def test_strategy_keywords(self) -> None:
        """Detects strategy/planning tasks."""
        result = identify_task_type("Crie um calendário editorial para a próxima semana")
        assert "strategy" in result

    def test_research_keywords(self) -> None:
        """Detects research tasks."""
        result = identify_task_type("Pesquise tendências de marketing para SaaS")
        assert "research" in result

    def test_analytics_keywords(self) -> None:
        """Detects analytics tasks."""
        result = identify_task_type("Quais são as métricas do último mês?")
        assert "analytics" in result

    def test_publishing_keywords(self) -> None:
        """Detects publishing tasks."""
        result = identify_task_type("Publicar o artigo no blog")
        assert "publishing" in result

    def test_media_keywords(self) -> None:
        """Detects media creation tasks."""
        result = identify_task_type("Crie uma thumbnail para o vídeo")
        assert "media" in result

    def test_multiple_types(self) -> None:
        """Can identify multiple task types in one message."""
        result = identify_task_type("Escreva um artigo e publique no blog")
        assert "content" in result
        assert "publishing" in result

    def test_unknown_message(self) -> None:
        """Returns empty list for unrecognizable messages."""
        result = identify_task_type("Olá, como vai?")
        assert result == []

    def test_case_insensitive(self) -> None:
        """Keyword matching is case-insensitive."""
        result = identify_task_type("ESCREVA UM ARTIGO")
        assert "content" in result


# ---------------------------------------------------------------------------
# Delegation context prompt tests
# ---------------------------------------------------------------------------


class TestBuildDelegationContextPrompt:
    """Tests for the build_delegation_context_prompt helper."""

    def test_includes_tenant_id(self) -> None:
        """Prompt includes tenant_id."""
        ctx = DelegationContext(tenant_id="tenant_xyz")
        prompt = build_delegation_context_prompt(ctx)
        assert "tenant_xyz" in prompt

    def test_includes_brand_voice(self) -> None:
        """Prompt includes brand voice when set."""
        ctx = DelegationContext(
            tenant_id="t1",
            brand_voice="Profissional e criativo",
        )
        prompt = build_delegation_context_prompt(ctx)
        assert "Profissional e criativo" in prompt

    def test_includes_niche(self) -> None:
        """Prompt includes niche when set."""
        ctx = DelegationContext(tenant_id="t1", niche="Fintech")
        prompt = build_delegation_context_prompt(ctx)
        assert "Fintech" in prompt

    def test_includes_persona(self) -> None:
        """Prompt includes persona when set."""
        ctx = DelegationContext(tenant_id="t1", persona="CTO de startup")
        prompt = build_delegation_context_prompt(ctx)
        assert "CTO de startup" in prompt

    def test_shows_active_connections(self) -> None:
        """Prompt shows connected platforms."""
        ctx = DelegationContext(
            tenant_id="t1",
            active_connections=["linkedin", "youtube"],
        )
        prompt = build_delegation_context_prompt(ctx)
        assert "linkedin" in prompt
        assert "youtube" in prompt

    def test_empty_connections_shows_nenhuma(self) -> None:
        """Prompt shows 'nenhuma' when no connections."""
        ctx = DelegationContext(tenant_id="t1")
        prompt = build_delegation_context_prompt(ctx)
        assert "nenhuma" in prompt

    def test_shows_publish_settings(self) -> None:
        """Prompt shows publish settings with status."""
        ctx = DelegationContext(
            tenant_id="t1",
            publish_settings={"blog": True, "linkedin_post": False},
        )
        prompt = build_delegation_context_prompt(ctx)
        assert "blog: auto" in prompt
        assert "linkedin_post: aprovação manual" in prompt

    def test_shows_calendar_items(self) -> None:
        """Prompt shows calendar items."""
        ctx = DelegationContext(
            tenant_id="t1",
            current_calendar=[
                {"platform": "linkedin", "format": "linkedin_post", "status": "proposed", "plannedFor": "2025-01-15"},
            ],
        )
        prompt = build_delegation_context_prompt(ctx)
        assert "linkedin" in prompt
        assert "proposed" in prompt

    def test_empty_calendar_shows_vazio(self) -> None:
        """Prompt shows empty state for calendar."""
        ctx = DelegationContext(tenant_id="t1")
        prompt = build_delegation_context_prompt(ctx)
        assert "calendário vazio" in prompt

    def test_default_language_pt_br(self) -> None:
        """Default language is pt-BR when none set."""
        ctx = DelegationContext(tenant_id="t1")
        prompt = build_delegation_context_prompt(ctx)
        assert "pt-BR" in prompt


# ---------------------------------------------------------------------------
# DIRETOR_PROMPT validation tests
# ---------------------------------------------------------------------------


class TestDiretorPrompt:
    """Tests for the DIRETOR_PROMPT content."""

    def test_prompt_is_not_empty(self) -> None:
        """Prompt is a non-empty string."""
        assert isinstance(DIRETOR_PROMPT, str)
        assert len(DIRETOR_PROMPT) > 100

    def test_prompt_mentions_orchestration(self) -> None:
        """Prompt instructs orchestration behavior."""
        assert "orquest" in DIRETOR_PROMPT.lower()

    def test_prompt_mentions_delegation(self) -> None:
        """Prompt instructs delegation to sub-agents."""
        assert "deleg" in DIRETOR_PROMPT.lower()

    def test_prompt_mentions_brand_voice(self) -> None:
        """Prompt mentions brand voice context."""
        assert "voz de marca" in DIRETOR_PROMPT.lower() or "brandVoice" in DIRETOR_PROMPT

    def test_prompt_mentions_portuguese(self) -> None:
        """Prompt instructs Portuguese responses by default."""
        assert "Português" in DIRETOR_PROMPT or "pt-BR" in DIRETOR_PROMPT

    def test_prompt_mentions_error_handling(self) -> None:
        """Prompt includes error handling instructions."""
        assert "erro" in DIRETOR_PROMPT.lower()

    def test_prompt_mentions_all_sub_agents(self) -> None:
        """Prompt references all sub-agents."""
        assert "Estrategista" in DIRETOR_PROMPT
        assert "Pesquisador" in DIRETOR_PROMPT
        assert "Roteirista" in DIRETOR_PROMPT
        assert "Revisor" in DIRETOR_PROMPT
        assert "Produtor" in DIRETOR_PROMPT
        assert "Publicador" in DIRETOR_PROMPT
        assert "Analista" in DIRETOR_PROMPT


# ---------------------------------------------------------------------------
# Task type routes tests
# ---------------------------------------------------------------------------


class TestTaskTypeRoutes:
    """Tests for the TASK_TYPE_ROUTES mapping."""

    def test_all_categories_have_routes(self) -> None:
        """All expected task categories are mapped."""
        expected = {"content", "strategy", "research", "analytics", "publishing", "media"}
        assert set(TASK_TYPE_ROUTES.keys()) == expected

    def test_routes_map_to_agent_names(self) -> None:
        """Each route maps to a valid agent name."""
        expected_agents = {
            "roteirista", "estrategista", "pesquisador",
            "analista", "publicador", "produtor_de_midia",
        }
        assert set(TASK_TYPE_ROUTES.values()) == expected_agents


# ---------------------------------------------------------------------------
# Factory function tests
# ---------------------------------------------------------------------------


class TestCreateDirectorAgent:
    """Tests for the create_director_agent factory."""

    def test_raises_without_adk(self) -> None:
        """Raises RuntimeError when ADK is not available."""
        # In test env, LlmAgent is None, so factory should raise
        with pytest.raises(RuntimeError, match="google.adk is not available"):
            create_director_agent()
