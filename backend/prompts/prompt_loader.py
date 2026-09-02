"""
prompt_loader.py -- Loads and compiles persona prompts from YAML

This module reads the system_prompt.yaml template and fills in
the variables with real persona data from the database.

Usage:
    from backend.prompts.prompt_loader import build_system_prompt
    from backend.models.db_models import Persona

    persona = db.query(Persona).get(1)
    prompt = build_system_prompt(persona, target_language="en", context_chunks=[])
    print(prompt)  # Fully compiled system prompt ready for the LLM
"""

import os
from pathlib import Path
from typing import Optional

import yaml

from backend.utils.logger import logger


# Load the YAML template once at import time
_PROMPT_DIR = Path(__file__).parent
_PROMPT_FILE = _PROMPT_DIR / "system_prompt.yaml"

with open(_PROMPT_FILE, "r", encoding="utf-8") as f:
    _PROMPT_CONFIG = yaml.safe_load(f)

_TEMPLATE = _PROMPT_CONFIG["template"]
_DEFAULT_CONSTRAINTS = _PROMPT_CONFIG.get("default_constraints", [])
_LANGUAGE_NAMES = _PROMPT_CONFIG.get("language_names", {})


def get_language_name(lang_code: str) -> str:
    """Convert a language code to a human-readable name."""
    return _LANGUAGE_NAMES.get(lang_code, lang_code.upper())


def build_system_prompt(
    persona,
    target_language: str = "en",
    context_chunks: Optional[list[str]] = None,
) -> str:
    """
    Compile a system prompt from the YAML template + persona data.

    Args:
        persona: A Persona ORM object (from the database)
        target_language: ISO 639-1 language code (e.g., "en", "hi")
        context_chunks: RAG context chunks to inject (optional, Week 5)

    Returns:
        A fully compiled system prompt string ready for the LLM
    """
    # Format personality traits as a readable string
    personality = ", ".join(persona.personality_traits) if persona.personality_traits else "Professional and helpful"

    # Format knowledge areas
    knowledge = ", ".join(persona.knowledge_areas) if persona.knowledge_areas else "General knowledge"

    # Merge default constraints with persona-specific ones
    all_constraints = list(_DEFAULT_CONSTRAINTS)
    if persona.constraints:
        all_constraints.extend(persona.constraints)
    constraints_str = "\n".join(f"  - {c}" for c in all_constraints)

    # Format RAG context
    if context_chunks:
        context_str = "Use the following information from your documents to answer:\n"
        for i, chunk in enumerate(context_chunks, 1):
            context_str += f"  [{i}] {chunk}\n"
    else:
        context_str = "No specific documents available. Use your general knowledge."

    # Get human-readable language name
    language_name = get_language_name(target_language)

    # Fill in the template
    compiled = _TEMPLATE.format(
        name=persona.name or "Professor",
        role=persona.role or "Academic",
        institution=persona.institution or "University",
        personality=personality,
        knowledge=knowledge,
        speaking_style=persona.speaking_style or "Professional and clear",
        constraints=constraints_str,
        target_language=language_name,
        context=context_str,
    )

    logger.debug(
        f"Built system prompt for '{persona.name}' "
        f"(lang={language_name}, constraints={len(all_constraints)}, "
        f"context_chunks={len(context_chunks or [])})"
    )

    return compiled.strip()
