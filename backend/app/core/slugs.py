"""Slug generation for organizations and workspaces."""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session


def slugify(text: str) -> str:
    """Lowercase, alphanumeric slug with single hyphens (ASCII only)."""
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:100]


def unique_slug(db: Session, model, base: str) -> str:
    """Produce a slug guaranteed unique for ``model.slug``."""
    candidate = prefix = slugify(base) or "item"
    suffix = 2
    while db.execute(select(model).where(model.slug == candidate)).scalar_one_or_none():
        suffix_str = f"-{suffix}"
        candidate = f"{prefix[: 100 - len(suffix_str)]}{suffix_str}"
        suffix += 1
    return candidate
