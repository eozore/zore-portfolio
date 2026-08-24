# -*- coding: utf-8 -*-
"""
model_config.py — Shared Vertex AI / Gemini config logic for Google Antigravity agents
"""

import os
import logging
from google.antigravity import ModelTarget, VertexEndpoint

logger = logging.getLogger("cmo_agent.model_config")

# Nome do modelo do caminho ANTIGRAVITY (chat curto: interview, critic,
# research). O conteúdo longo NÃO passa por aqui — ele vai pelo
# vertex_generate.VERTEX_MODEL, que é outro modelo. Confundir os dois foi o
# que produziu 7 registros de auditoria com o modelo errado.
DEFAULT_MODEL_NAME = "gemini-2.5-flash"

# USD por 1 milhão de tokens (tier pago, texto).
#   https://ai.google.dev/gemini-api/docs/pricing
#   https://cloud.google.com/vertex-ai/generative-ai/pricing
#
# Um modelo que não estiver nesta tabela é registrado com custo zero e um
# aviso no log — perder o registro seria pior do que perder o valor. Ao trocar
# de modelo em VERTEX_MODEL, acrescente a linha aqui.
MODEL_PRICING_USD_PER_1M: dict[str, dict[str, float]] = {
    "gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50},
    "gemini-3.5-flash":      {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash":      {"input": 0.30, "output": 2.50},
    "gemini-2.5-pro":        {"input": 1.25, "output": 10.00},
    # Mantido só para ler registros históricos gravados antes da correção.
    "gemini-1.5-flash":      {"input": 0.075, "output": 0.30},
}

# Set dummy API key to bypass default image validation checks
if not os.environ.get("GEMINI_API_KEY"):
    os.environ["GEMINI_API_KEY"] = "dummy-key-to-bypass-validation"

def get_model_config():
    """
    Config para agentes de chat interativo (interview, critic, research).
    Usa gemini-2.5-flash via antigravity SDK — output curto, sem risco de loop.
    Quando o projeto tiver acesso ao Gemini 3.x no Vertex, trocar para gemini-3.5-flash.
    """
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    if project_id:
        vertex_ep = VertexEndpoint(project=project_id, location="us-central1")
        return [
            ModelTarget(name="gemini-2.5-flash", endpoint=vertex_ep),
        ]
    logger.info("FIREBASE_PROJECT_ID not set. Defaulting to standard Gemini Developer API endpoint.")
    return None


def get_long_context_model_config():
    """
    Mantido por compatibilidade — agora redireciona para get_model_config().
    Os agentes de contexto longo usam vertex_generate.py diretamente (sem antigravity).
    """
    return get_model_config()
