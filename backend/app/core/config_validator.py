"""
config_validator.py
──────────────────────────────────────────────────────────────────────────────
Sprint 9: Startup Configuration Validation

Validates all required environment variables on application startup.
Performs fail-fast checks in production and logs detailed warnings in development.
"""

from __future__ import annotations

import logging
import os
from typing import List, Tuple

logger = logging.getLogger("it-agent-backend")


def validate_environment_config() -> Tuple[bool, List[str]]:
    """
    Validates application environment variables.

    Returns (is_valid: bool, errors: List[str]).
    """
    errors: List[str] = []
    warnings: List[str] = []

    env_mode = os.getenv("ENVIRONMENT", "development").lower()
    is_prod = env_mode in ("production", "prod")

    # 1. Database Configuration
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        warnings.append("DATABASE_URL is not set — defaulting to local SQLite database.")
    elif is_prod and db_url.startswith("sqlite"):
        warnings.append("DATABASE_URL is using SQLite in production mode. PostgreSQL is recommended.")

    # 2. Secret Key Configuration
    secret_key = os.getenv("SECRET_KEY") or os.getenv("JWT_SECRET")
    default_dev_key = "bridgestone-it-agent-super-secret-key-123456"
    if not secret_key:
        if is_prod:
            errors.append("CRITICAL: SECRET_KEY (or JWT_SECRET) environment variable is required in production.")
        else:
            warnings.append("SECRET_KEY is not set — using development default key.")
    elif secret_key == default_dev_key and is_prod:
        errors.append("CRITICAL: Default development SECRET_KEY detected in production environment.")

    # 3. AI Provider Configuration
    llm_provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if llm_provider not in ("gemini", "claude", "anthropic", "mock"):
        errors.append(f"Invalid LLM_PROVIDER '{llm_provider}'. Must be 'gemini', 'claude', or 'mock'.")

    if llm_provider == "gemini":
        gemini_key = os.getenv("GEMINI_API_KEY")
        if not gemini_key:
            warnings.append("GEMINI_API_KEY is not configured. AI services will operate in mock/fallback mode.")
    elif llm_provider in ("claude", "anthropic"):
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if not anthropic_key:
            warnings.append("ANTHROPIC_API_KEY is not configured. AI services will operate in mock/fallback mode.")

    # Log warnings
    for warn in warnings:
        logger.warning("Config Validation Warning: %s", warn)

    # Log errors
    for err in errors:
        logger.error("Config Validation Error: %s", err)

    is_valid = len(errors) == 0
    if is_valid:
        logger.info("✓ Environment Configuration Validation Passed (mode=%s, provider=%s).", env_mode, llm_provider)

    return is_valid, errors
