"""
Unit tests for apps/agents/models.py — centralized model configuration.

Validates Requirements 5.1, 5.2, 5.3, 5.4.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from apps.agents.models import (
    ALL_ROLES,
    DEFAULT_FLASH_MODEL,
    DEFAULT_PRO_MODEL,
    ROLE_TIERS,
    TIER_DEFAULTS,
    ModelConfig,
    get_model_config,
    get_model_for_role,
    validate_all_models,
)


# ---------------------------------------------------------------------------
# Tests: get_model_for_role — defaults
# ---------------------------------------------------------------------------


class TestGetModelForRoleDefaults:
    """When no env var is set, use the tier default."""

    @pytest.mark.parametrize(
        "role",
        ["director", "strategist", "writer", "reviewer"],
    )
    def test_pro_tier_defaults(self, role: str):
        """Pro-tier roles default to Gemini 2.5 Pro."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_model_for_role(role)
        assert result == DEFAULT_PRO_MODEL

    @pytest.mark.parametrize(
        "role",
        ["researcher", "producer", "publisher", "analyst"],
    )
    def test_flash_tier_defaults(self, role: str):
        """Flash-tier roles default to Gemini 2.5 Flash."""
        with patch.dict(os.environ, {}, clear=True):
            result = get_model_for_role(role)
        assert result == DEFAULT_FLASH_MODEL


# ---------------------------------------------------------------------------
# Tests: get_model_for_role — env override
# ---------------------------------------------------------------------------


class TestGetModelForRoleEnvOverride:
    """When env var MODEL_* is set, use that value."""

    def test_env_overrides_default(self):
        """MODEL_DIRECTOR overrides the default pro model."""
        env = {"MODEL_DIRECTOR": "gemini-custom-model"}
        with patch.dict(os.environ, env, clear=True):
            result = get_model_for_role("director")
        assert result == "gemini-custom-model"

    def test_env_override_flash_role(self):
        """MODEL_RESEARCHER overrides the default flash model."""
        env = {"MODEL_RESEARCHER": "custom-flash"}
        with patch.dict(os.environ, env, clear=True):
            result = get_model_for_role("researcher")
        assert result == "custom-flash"

    def test_env_override_does_not_affect_other_roles(self):
        """Setting MODEL_DIRECTOR does not affect writer."""
        env = {"MODEL_DIRECTOR": "custom-pro"}
        with patch.dict(os.environ, env, clear=True):
            assert get_model_for_role("writer") == DEFAULT_PRO_MODEL


# ---------------------------------------------------------------------------
# Tests: get_model_for_role — invalid role
# ---------------------------------------------------------------------------


class TestGetModelForRoleInvalidRole:
    """Unknown roles raise ValueError."""

    def test_unknown_role_raises(self):
        with pytest.raises(ValueError, match="Unknown agent role"):
            get_model_for_role("nonexistent")

    def test_empty_role_raises(self):
        with pytest.raises(ValueError, match="Unknown agent role"):
            get_model_for_role("")


# ---------------------------------------------------------------------------
# Tests: get_model_config
# ---------------------------------------------------------------------------


class TestGetModelConfig:
    """get_model_config returns a fully populated ModelConfig."""

    def test_returns_model_config_with_default(self):
        with patch.dict(os.environ, {}, clear=True):
            config = get_model_config("director")

        assert isinstance(config, ModelConfig)
        assert config.model_id == DEFAULT_PRO_MODEL
        assert config.role == "director"
        assert config.tier == "pro"

    def test_returns_model_config_with_env_override(self):
        env = {"MODEL_ANALYST": "custom-analyst-model"}
        with patch.dict(os.environ, env, clear=True):
            config = get_model_config("analyst")

        assert config.model_id == "custom-analyst-model"
        assert config.role == "analyst"
        assert config.tier == "flash"

    def test_invalid_role_raises(self):
        with pytest.raises(ValueError):
            get_model_config("unknown")


# ---------------------------------------------------------------------------
# Tests: validate_all_models
# ---------------------------------------------------------------------------


class TestValidateAllModels:
    """validate_all_models returns configs for all roles."""

    def test_returns_all_roles(self):
        with patch.dict(os.environ, {}, clear=True):
            configs = validate_all_models()

        assert set(configs.keys()) == set(ALL_ROLES)
        for role, config in configs.items():
            assert config.role == role
            assert config.tier == ROLE_TIERS[role]
            assert config.model_id == TIER_DEFAULTS[ROLE_TIERS[role]]

    def test_respects_env_overrides(self):
        env = {"MODEL_WRITER": "custom-writer", "MODEL_PUBLISHER": "custom-pub"}
        with patch.dict(os.environ, env, clear=True):
            configs = validate_all_models()

        assert configs["writer"].model_id == "custom-writer"
        assert configs["publisher"].model_id == "custom-pub"
        # Others use defaults
        assert configs["director"].model_id == DEFAULT_PRO_MODEL


# ---------------------------------------------------------------------------
# Tests: ModelConfig dataclass
# ---------------------------------------------------------------------------


class TestModelConfigDataclass:
    """ModelConfig is frozen and stores correct attributes."""

    def test_frozen(self):
        config = ModelConfig(model_id="test", role="director", tier="pro")
        with pytest.raises(AttributeError):
            config.model_id = "other"  # type: ignore[misc]

    def test_equality(self):
        a = ModelConfig(model_id="m1", role="writer", tier="pro")
        b = ModelConfig(model_id="m1", role="writer", tier="pro")
        assert a == b


# ---------------------------------------------------------------------------
# Tests: ALL_ROLES constant
# ---------------------------------------------------------------------------


class TestAllRoles:
    """ALL_ROLES contains all 8 agent roles."""

    def test_count(self):
        assert len(ALL_ROLES) == 8

    def test_contains_expected_roles(self):
        expected = {
            "director", "strategist", "researcher", "writer",
            "producer", "reviewer", "publisher", "analyst",
        }
        assert set(ALL_ROLES) == expected
