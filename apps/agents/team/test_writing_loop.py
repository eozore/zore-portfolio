"""
Tests for the Writing Loop agents (Roteirista, Revisor, LoopAgent).

Validates:
- Each agent uses the correct model from models.py
- Each agent has a non-empty instruction (prompt)
- Prompts contain key elements per the design spec
- Agent names match the expected ADK identifiers
- LoopAgent has correct max_iterations
- VersionTracker preserves intermediate versions correctly
- should_exit_loop detects APROVADO and REJEITADO_TERMINAL

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from apps.agents.team.prompts import ROTEIRISTA_PROMPT, REVISOR_PROMPT
from apps.agents.team.writing_loop import (
    MAX_LOOP_ITERATIONS,
    EXIT_KEYWORD_APPROVED,
    EXIT_KEYWORD_REJECTED,
    ContentIteration,
    VersionTracker,
    should_exit_loop,
)


# ---------------------------------------------------------------------------
# Roteirista (Writer) Tests
# ---------------------------------------------------------------------------


class TestRoteiristaAgent:
    """Tests for the Roteirista sub-agent."""

    def test_agent_creation_with_adk(self) -> None:
        """Verify agent instantiates correctly when google.adk is available."""
        try:
            from apps.agents.team.writer import roteirista_agent

            assert roteirista_agent is not None
            assert roteirista_agent.name == "roteirista"
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_prompt_not_empty(self) -> None:
        """Verify ROTEIRISTA_PROMPT is defined and non-empty."""
        assert len(ROTEIRISTA_PROMPT) > 100

    def test_prompt_mentions_markdown(self) -> None:
        """Prompt must reference markdown production for blog."""
        assert "markdown" in ROTEIRISTA_PROMPT.lower()
        assert "blog" in ROTEIRISTA_PROMPT.lower()

    def test_prompt_mentions_linkedin_limit(self) -> None:
        """Prompt must reference LinkedIn ≤ 3000 chars limit."""
        assert "3000" in ROTEIRISTA_PROMPT
        assert "linkedin" in ROTEIRISTA_PROMPT.lower()

    def test_prompt_mentions_instagram_limit(self) -> None:
        """Prompt must reference Instagram ≤ 2200 chars and ≤ 30 hashtags."""
        assert "2200" in ROTEIRISTA_PROMPT
        assert "30" in ROTEIRISTA_PROMPT
        assert "instagram" in ROTEIRISTA_PROMPT.lower()

    def test_prompt_mentions_youtube_limit(self) -> None:
        """Prompt must reference YouTube ≤ 5000 chars."""
        assert "5000" in ROTEIRISTA_PROMPT
        assert "youtube" in ROTEIRISTA_PROMPT.lower()

    def test_prompt_mentions_brand_voice(self) -> None:
        """Prompt must reference brand voice alignment."""
        assert "brandvoice" in ROTEIRISTA_PROMPT.lower() or "voz de marca" in ROTEIRISTA_PROMPT.lower()

    def test_prompt_mentions_corrections(self) -> None:
        """Prompt must reference incorporating Revisor corrections."""
        assert "correç" in ROTEIRISTA_PROMPT.lower()

    def test_prompt_mentions_json_output(self) -> None:
        """Prompt must define JSON output format."""
        assert "json" in ROTEIRISTA_PROMPT.lower()
        assert "blog_article" in ROTEIRISTA_PROMPT

    def test_prompt_in_portuguese(self) -> None:
        """Prompt must be written in Portuguese."""
        assert "Você" in ROTEIRISTA_PROMPT

    def test_uses_correct_model(self) -> None:
        """Roteirista should use the 'writer' role model (Pro tier)."""
        from apps.agents.models import get_model_for_role

        model = get_model_for_role("writer")
        assert model == "gemini-2.5-pro"

    def test_uses_env_override(self) -> None:
        """Environment variable MODEL_WRITER should override default."""
        from apps.agents.models import get_model_for_role

        with patch.dict(os.environ, {"MODEL_WRITER": "custom-writer-model"}):
            assert get_model_for_role("writer") == "custom-writer-model"


# ---------------------------------------------------------------------------
# Revisor (Reviewer) Tests
# ---------------------------------------------------------------------------


class TestRevisorAgent:
    """Tests for the Revisor sub-agent."""

    def test_agent_creation_with_adk(self) -> None:
        """Verify agent instantiates correctly when google.adk is available."""
        try:
            from apps.agents.team.reviewer import revisor_agent

            assert revisor_agent is not None
            assert revisor_agent.name == "revisor"
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_prompt_not_empty(self) -> None:
        """Verify REVISOR_PROMPT is defined and non-empty."""
        assert len(REVISOR_PROMPT) > 100

    def test_prompt_mentions_aprovado(self) -> None:
        """Prompt must reference APROVADO verdict."""
        assert "APROVADO" in REVISOR_PROMPT

    def test_prompt_mentions_rejeitado_terminal(self) -> None:
        """Prompt must reference REJEITADO_TERMINAL verdict."""
        assert "REJEITADO_TERMINAL" in REVISOR_PROMPT

    def test_prompt_mentions_linkedin_limit(self) -> None:
        """Prompt must reference LinkedIn ≤ 3000 chars limit."""
        assert "3000" in REVISOR_PROMPT

    def test_prompt_mentions_instagram_limit(self) -> None:
        """Prompt must reference Instagram ≤ 2200 chars and ≤ 30 hashtags."""
        assert "2200" in REVISOR_PROMPT
        assert "30" in REVISOR_PROMPT

    def test_prompt_mentions_youtube_limit(self) -> None:
        """Prompt must reference YouTube ≤ 5000 chars limit."""
        assert "5000" in REVISOR_PROMPT

    def test_prompt_mentions_brand_voice(self) -> None:
        """Prompt must reference brand voice validation."""
        assert "voz de marca" in REVISOR_PROMPT.lower() or "brandvoice" in REVISOR_PROMPT.lower()

    def test_prompt_mentions_corrections_format(self) -> None:
        """Prompt must define correction structure (excerpt, violation_type, instruction)."""
        assert "excerpt" in REVISOR_PROMPT
        assert "violation_type" in REVISOR_PROMPT
        assert "instruction" in REVISOR_PROMPT

    def test_prompt_mentions_plagiarism(self) -> None:
        """Prompt must reference plagiarism as terminal rejection reason."""
        assert "plágio" in REVISOR_PROMPT.lower() or "plagiarism" in REVISOR_PROMPT.lower()

    def test_prompt_mentions_policy(self) -> None:
        """Prompt must reference content policy validation."""
        assert "política" in REVISOR_PROMPT.lower() or "policy" in REVISOR_PROMPT.lower()

    def test_prompt_in_portuguese(self) -> None:
        """Prompt must be written in Portuguese."""
        assert "Você" in REVISOR_PROMPT

    def test_uses_correct_model(self) -> None:
        """Revisor should use the 'reviewer' role model (Pro tier)."""
        from apps.agents.models import get_model_for_role

        model = get_model_for_role("reviewer")
        assert model == "gemini-2.5-pro"

    def test_uses_env_override(self) -> None:
        """Environment variable MODEL_REVIEWER should override default."""
        from apps.agents.models import get_model_for_role

        with patch.dict(os.environ, {"MODEL_REVIEWER": "custom-reviewer"}):
            assert get_model_for_role("reviewer") == "custom-reviewer"


# ---------------------------------------------------------------------------
# Writing Loop (LoopAgent) Tests
# ---------------------------------------------------------------------------


class TestWritingLoop:
    """Tests for the writing loop LoopAgent configuration."""

    def test_loop_agent_creation(self) -> None:
        """Verify LoopAgent instantiates correctly when google.adk is available."""
        try:
            from apps.agents.team.writing_loop import writing_loop_agent

            assert writing_loop_agent is not None
            assert writing_loop_agent.name == "loop_escrita_revisao"
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_loop_max_iterations(self) -> None:
        """LoopAgent should have max_iterations=5."""
        assert MAX_LOOP_ITERATIONS == 5

    def test_loop_has_both_sub_agents(self) -> None:
        """LoopAgent should have roteirista and revisor as sub_agents."""
        try:
            from apps.agents.team.writing_loop import writing_loop_agent

            agent_names = [a.name for a in writing_loop_agent.sub_agents]
            assert "roteirista" in agent_names
            assert "revisor" in agent_names
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_exit_keywords_defined(self) -> None:
        """Exit keywords must be APROVADO and REJEITADO_TERMINAL."""
        assert EXIT_KEYWORD_APPROVED == "APROVADO"
        assert EXIT_KEYWORD_REJECTED == "REJEITADO_TERMINAL"


# ---------------------------------------------------------------------------
# should_exit_loop Tests
# ---------------------------------------------------------------------------


class TestShouldExitLoop:
    """Tests for the loop exit condition helper."""

    def test_exit_on_aprovado(self) -> None:
        """Should exit when output contains APROVADO."""
        assert should_exit_loop("APROVADO\n\nResumo: Conteúdo atende todos os critérios.") is True

    def test_exit_on_rejeitado_terminal(self) -> None:
        """Should exit on terminal rejection."""
        assert should_exit_loop("REJEITADO_TERMINAL\n\nMotivo: Plágio detectado.") is True

    def test_no_exit_on_corrections(self) -> None:
        """Should NOT exit when corrections are emitted."""
        output = '{"verdict": "CORREÇÕES", "corrections": [{"excerpt": "abc"}]}'
        assert should_exit_loop(output) is False

    def test_no_exit_on_empty(self) -> None:
        """Should NOT exit on empty output."""
        assert should_exit_loop("") is False

    def test_no_exit_on_partial_keyword(self) -> None:
        """Should NOT exit on partial keywords like APROVAR (not APROVADO)."""
        assert should_exit_loop("Preciso APROVAR este item") is False

    def test_exit_aprovado_in_middle_of_text(self) -> None:
        """Should exit if APROVADO appears anywhere in the output."""
        assert should_exit_loop("O conteúdo foi APROVADO pelo revisor.") is True

    def test_exit_rejeitado_terminal_in_context(self) -> None:
        """Should exit if REJEITADO_TERMINAL appears in structured output."""
        output = "Verdict: REJEITADO_TERMINAL\nMotivo: Violação de política."
        assert should_exit_loop(output) is True


# ---------------------------------------------------------------------------
# VersionTracker Tests
# ---------------------------------------------------------------------------


class TestVersionTracker:
    """Tests for intermediate version preservation."""

    def test_initial_state(self) -> None:
        """New tracker should have zero iterations and no content."""
        tracker = VersionTracker(task_id="task-001")
        assert tracker.task_id == "task-001"
        assert tracker.current_iteration == 0
        assert tracker.latest_content is None
        assert tracker.iterations == []

    def test_record_first_iteration(self) -> None:
        """First iteration should be recorded with iteration_number=1."""
        tracker = VersionTracker(task_id="task-001")
        result = tracker.record_iteration(
            content="# Draft 1\n\nContent here.",
            reviewer_verdict=None,
        )
        assert result.iteration_number == 1
        assert result.task_id == "task-001"
        assert result.content == "# Draft 1\n\nContent here."
        assert tracker.current_iteration == 1

    def test_record_multiple_iterations(self) -> None:
        """Multiple iterations should increment iteration_number correctly."""
        tracker = VersionTracker(task_id="task-002")

        tracker.record_iteration(content="Draft 1")
        tracker.record_iteration(content="Draft 2", reviewer_verdict="CORREÇÕES")
        result = tracker.record_iteration(
            content="Draft 3",
            reviewer_verdict="APROVADO",
        )

        assert result.iteration_number == 3
        assert tracker.current_iteration == 3
        assert tracker.latest_content == "Draft 3"

    def test_iterations_are_preserved(self) -> None:
        """All intermediate versions must be retrievable."""
        tracker = VersionTracker(task_id="task-003")

        tracker.record_iteration(content="V1")
        tracker.record_iteration(content="V2")
        tracker.record_iteration(content="V3")

        versions = tracker.iterations
        assert len(versions) == 3
        assert versions[0].content == "V1"
        assert versions[1].content == "V2"
        assert versions[2].content == "V3"

    def test_corrections_stored(self) -> None:
        """Corrections from the Revisor should be stored per iteration."""
        tracker = VersionTracker(task_id="task-004")
        corrections = [
            {
                "excerpt": "texto errado",
                "violation_type": "grammar",
                "instruction": "Corrigir para 'texto correto'",
            }
        ]
        result = tracker.record_iteration(
            content="Draft with error",
            reviewer_verdict="CORREÇÕES",
            corrections=corrections,
        )
        assert result.corrections == corrections
        assert result.reviewer_verdict == "CORREÇÕES"

    def test_task_id_associated_with_all_iterations(self) -> None:
        """All iterations must be associated with the same task_id."""
        tracker = VersionTracker(task_id="task-005")
        tracker.record_iteration(content="A")
        tracker.record_iteration(content="B")

        for iteration in tracker.iterations:
            assert iteration.task_id == "task-005"

    def test_iterations_returns_copy(self) -> None:
        """iterations property should return a copy, not the internal list."""
        tracker = VersionTracker(task_id="task-006")
        tracker.record_iteration(content="X")

        returned = tracker.iterations
        returned.append(ContentIteration(task_id="fake", iteration_number=99, content="hacked"))

        assert len(tracker.iterations) == 1


# ---------------------------------------------------------------------------
# Package Export Tests
# ---------------------------------------------------------------------------


class TestWritingLoopExports:
    """Tests for team package exports of writing loop agents."""

    def test_package_exports_roteirista(self) -> None:
        """Verify __init__.py exports roteirista_agent."""
        try:
            from apps.agents.team import roteirista_agent

            assert roteirista_agent is not None
            assert roteirista_agent.name == "roteirista"
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_package_exports_revisor(self) -> None:
        """Verify __init__.py exports revisor_agent."""
        try:
            from apps.agents.team import revisor_agent

            assert revisor_agent is not None
            assert revisor_agent.name == "revisor"
        except ImportError:
            pytest.skip("google.adk not available locally")

    def test_package_exports_writing_loop(self) -> None:
        """Verify __init__.py exports writing_loop_agent."""
        try:
            from apps.agents.team import writing_loop_agent

            assert writing_loop_agent is not None
            assert writing_loop_agent.name == "loop_escrita_revisao"
        except ImportError:
            pytest.skip("google.adk not available locally")
