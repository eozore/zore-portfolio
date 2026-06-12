"""
Director agent — root orchestrator for the Agentic Marketing Platform.

The Director is the ADK root_agent. It receives user messages, identifies
the task type, injects tenant context, and delegates to specialized sub-agents.

Requirements: 6.1, 6.2, 6.3, 6.4
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:
    from google.adk.agents import LlmAgent
except ImportError:  # pragma: no cover — ADK unavailable in local dev/test
    LlmAgent = None  # type: ignore[assignment, misc]

from apps.agents.director.prompts import DIRETOR_PROMPT
from apps.agents.models import get_model_for_role


# ---------------------------------------------------------------------------
# DelegationContext — injected into every sub-agent delegation
# ---------------------------------------------------------------------------


@dataclass
class DelegationContext:
    """
    Context data injected into every delegation from the Director to a sub-agent.

    This ensures each sub-agent operates with full awareness of the tenant's
    brand identity, current state, and configuration.

    Attributes
    ----------
    tenant_id : str
        The tenant identifier for data isolation.
    brand_voice : str
        The tenant's brand voice guidelines (max 2000 chars).
    niche : str
        The tenant's market niche (max 100 chars).
    persona : str
        The target persona description (max 2000 chars).
    languages : list[str]
        Preferred languages (ISO 639-1 codes).
    current_calendar : list[dict]
        Active calendar items (proposed/approved/in_progress).
    active_connections : list[str]
        Platforms with valid OAuth connections (e.g., ["linkedin", "youtube"]).
    publish_settings : dict[str, bool]
        Auto-publish toggle state per format (e.g., {"blog": True, "linkedin_post": False}).
    """

    tenant_id: str
    brand_voice: str = ""
    niche: str = ""
    persona: str = ""
    languages: list[str] = field(default_factory=list)
    current_calendar: list[dict[str, Any]] = field(default_factory=list)
    active_connections: list[str] = field(default_factory=list)
    publish_settings: dict[str, bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Task type routing
# ---------------------------------------------------------------------------

# Maps task categories to the sub-agent names that handle them.
# Used by the Director's orchestration logic to route delegations.
TASK_TYPE_ROUTES: dict[str, str] = {
    "content": "roteirista",
    "strategy": "estrategista",
    "research": "pesquisador",
    "analytics": "analista",
    "publishing": "publicador",
    "media": "produtor_de_midia",
}


def identify_task_type(message: str) -> list[str]:
    """
    Identify task type(s) from a user message using keyword heuristics.

    This is a lightweight pre-routing helper. The Director LLM itself will
    make the final delegation decision via its prompt instructions — this
    function serves as a fallback for programmatic routing when needed.

    Parameters
    ----------
    message : str
        The user's message text.

    Returns
    -------
    list[str]
        List of identified task types (keys from TASK_TYPE_ROUTES).
        Returns empty list if no type can be identified.
    """
    message_lower = message.lower()

    # Keyword sets for each task type
    keywords: dict[str, list[str]] = {
        "content": [
            "artigo", "post", "escrever", "escreva", "redigir", "texto",
            "roteiro", "blog", "legenda", "criar conteúdo", "conteúdo",
        ],
        "strategy": [
            "calendário", "planejar", "planejamento", "agenda", "agendar",
            "estratégia", "pauta", "pautas", "editorial",
        ],
        "research": [
            "pesquisar", "pesquisa", "tendência", "tendências", "referência",
            "referências", "mercado", "oportunidade", "análise de mercado",
        ],
        "analytics": [
            "métrica", "métricas", "performance", "resultado", "resultados",
            "analytics", "desempenho", "engajamento", "alcance",
        ],
        "publishing": [
            "publicar", "publicação", "postar", "enviar para",
            "agendar publicação", "cross-post", "publique",
        ],
        "media": [
            "imagem", "thumbnail", "visual", "arte", "design",
            "feed", "reel", "story", "vídeo", "video", "mídia",
        ],
    }

    identified: list[str] = []
    for task_type, words in keywords.items():
        if any(word in message_lower for word in words):
            identified.append(task_type)

    return identified


def build_delegation_context_prompt(context: DelegationContext) -> str:
    """
    Build a context string to inject into sub-agent delegations.

    This creates a structured summary of the tenant's context that the
    Director includes when delegating tasks to sub-agents.

    Parameters
    ----------
    context : DelegationContext
        The tenant's current context data.

    Returns
    -------
    str
        Formatted context string for injection into delegation prompts.
    """
    connections_str = ", ".join(context.active_connections) if context.active_connections else "nenhuma"
    languages_str = ", ".join(context.languages) if context.languages else "pt-BR"

    # Format publish settings
    settings_lines = []
    for fmt, auto in context.publish_settings.items():
        status = "auto" if auto else "aprovação manual"
        settings_lines.append(f"  - {fmt}: {status}")
    settings_str = "\n".join(settings_lines) if settings_lines else "  - (não configurado)"

    # Format calendar (show up to 10 most recent items)
    calendar_lines = []
    for item in context.current_calendar[:10]:
        platform = item.get("platform", "?")
        fmt = item.get("format", "?")
        status = item.get("status", "?")
        planned = item.get("plannedFor", "?")
        calendar_lines.append(f"  - [{status}] {platform}/{fmt} para {planned}")
    calendar_str = "\n".join(calendar_lines) if calendar_lines else "  - (calendário vazio)"

    return f"""## Contexto do Tenant

**Tenant ID**: {context.tenant_id}
**Voz de Marca**: {context.brand_voice or '(não definida)'}
**Nicho**: {context.niche or '(não definido)'}
**Persona**: {context.persona or '(não definida)'}
**Idiomas**: {languages_str}
**Conexões Ativas**: {connections_str}

### Configurações de Publicação
{settings_str}

### Calendário Atual
{calendar_str}
"""


# ---------------------------------------------------------------------------
# Director agent definition
# ---------------------------------------------------------------------------


def create_director_agent() -> Any:
    """
    Create and return the Director LlmAgent instance.

    This factory function is used to instantiate the Director at runtime
    when the ADK is available (Cloud Run with Vertex AI).

    Returns
    -------
    LlmAgent
        The configured Director agent with model and prompt.

    Raises
    ------
    RuntimeError
        If google.adk is not available (should not happen in production).
    """
    if LlmAgent is None:
        raise RuntimeError(
            "google.adk is not available. The Director agent requires "
            "the ADK runtime (Cloud Run with Vertex AI)."
        )

    return LlmAgent(
        name="diretor",
        model=get_model_for_role("director"),
        instruction=DIRETOR_PROMPT,
        sub_agents=[],  # Populated as sub-agents are created in tasks 7.4, 7.5, 7.7
    )


# Instantiate at module level if ADK is available; otherwise defer to runtime.
# This allows the module to be imported in test/dev environments without ADK.
if LlmAgent is not None:
    director_agent = create_director_agent()
    root_agent = director_agent
else:
    director_agent = None  # type: ignore[assignment]
    root_agent = None  # type: ignore[assignment]
