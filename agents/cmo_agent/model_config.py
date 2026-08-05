# -*- coding: utf-8 -*-
"""
model_config.py — Shared Vertex AI / Gemini config logic for Google Antigravity agents
"""

import os
import logging
from google.antigravity import ModelTarget, VertexEndpoint

logger = logging.getLogger("cmo_agent.model_config")

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
