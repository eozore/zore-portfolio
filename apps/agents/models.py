"""
Centralized model configuration for the Agents service.

Each agent role maps to an LLM model via environment variables (MODEL_*).
If no env var is set for a given role, the default is used based on tier:
  - Pro tier (Gemini 2.5 Pro): director, strategist, writer, reviewer
  - Flash tier (Gemini 2.5 Flash): researcher, producer, publisher, analyst

Requirements: 5.1, 5.2, 5.3, 5.4
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

# Default model IDs
DEFAULT_PRO_MODEL = "gemini-2.5-pro"
DEFAULT_FLASH_MODEL = "gemini-2.5-flash"

# Type alias for tiers
Tier = Literal["pro", "flash"]

# Mapping of roles to their default tier
ROLE_TIERS: dict[str, Tier] = {
    "director": "pro",
    "strategist": "pro",
    "researcher": "flash",
    "writer": "pro",
    "producer": "flash",
    "reviewer": "pro",
    "publisher": "flash",
    "analyst": "flash",
}

# All available agent roles
ALL_ROLES: list[str] = list(ROLE_TIERS.keys())

# Default model per tier
TIER_DEFAULTS: dict[Tier, str] = {
    "pro": DEFAULT_PRO_MODEL,
    "flash": DEFAULT_FLASH_MODEL,
}


@dataclass(frozen=True)
class ModelConfig:
    """Configuration for a model assigned to an agent role."""

    model_id: str
    role: str
    tier: Tier


def get_model_for_role(role: str) -> str:
    """
    Return the model ID configured for the given agent role.

    Reads from env var MODEL_{ROLE_UPPERCASE}. If not set, returns the
    default model for the role's tier.

    Raises:
        ValueError: If the role is not recognized.
    """
    if role not in ROLE_TIERS:
        raise ValueError(
            f"Unknown agent role: '{role}'. Valid roles: {ALL_ROLES}"
        )

    env_key = f"MODEL_{role.upper()}"
    tier = ROLE_TIERS[role]
    default = TIER_DEFAULTS[tier]
    return os.environ.get(env_key, default)


def get_model_config(role: str) -> ModelConfig:
    """
    Return full ModelConfig for a given agent role.

    Raises:
        ValueError: If the role is not recognized.
    """
    if role not in ROLE_TIERS:
        raise ValueError(
            f"Unknown agent role: '{role}'. Valid roles: {ALL_ROLES}"
        )

    model_id = get_model_for_role(role)
    tier = ROLE_TIERS[role]
    return ModelConfig(model_id=model_id, role=role, tier=tier)


def validate_all_models() -> dict[str, ModelConfig]:
    """
    Validate that all required agent roles can be resolved to a model.

    Returns a dict mapping role -> ModelConfig for all roles.
    This is useful at startup to confirm all env vars resolve correctly.

    Raises:
        ValueError: If any role cannot be resolved (should not happen with
                    defaults in place, but guards against code errors).
    """
    configs: dict[str, ModelConfig] = {}
    for role in ALL_ROLES:
        configs[role] = get_model_config(role)
    return configs
