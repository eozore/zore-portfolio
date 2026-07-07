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
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    if project_id:
        vertex_ep = VertexEndpoint(
            project=project_id,
            location="us-central1"
        )
        # For Vertex, use gemini-2.5-flash as primary, falling back to gemini-1.5-flash
        model_target1 = ModelTarget(
            name="gemini-2.5-flash",
            endpoint=vertex_ep
        )
        model_target2 = ModelTarget(
            name="gemini-1.5-flash",
            endpoint=vertex_ep
        )
        logger.info(f"Configured ModelTargets with Vertex fallback list (gemini-2.5-flash, gemini-1.5-flash) for project: {project_id}")
        return [model_target1, model_target2]
    else:
        logger.info("FIREBASE_PROJECT_ID not set. Defaulting to standard Gemini Developer API endpoint.")
        return None
