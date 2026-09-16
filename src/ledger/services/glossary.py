"""Glossary lookup and search expansion (D46)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledger.models.contract_schedule import GlossaryAlias, GlossaryTerm
from ledger.schemas.contract_schedule import GlossaryTermOut
from ledger.schemas.operations import SearchHitOut


def list_glossary(session: Session) -> list[GlossaryTermOut]:
    """Return every term with its aliases."""
    aliases_by_term: dict[str, list[str]] = {}
    for alias in session.scalars(select(GlossaryAlias).order_by(GlossaryAlias.alias)):
        aliases_by_term.setdefault(alias.term_code, []).append(alias.alias)
    rows = session.scalars(select(GlossaryTerm).order_by(GlossaryTerm.title)).all()
    return [
        GlossaryTermOut(
            term_code=row.term_code,
            title=row.title,
            definition=row.definition,
            href=row.href,
            aliases=aliases_by_term.get(row.term_code, []),
        )
        for row in rows
    ]


def glossary_search_hits(session: Session, needle: str) -> list[SearchHitOut]:
    """Match term codes, titles, definitions, and aliases (no dollars)."""
    lowered = needle.strip().lower()
    if not lowered:
        return []
    hits: list[SearchHitOut] = []
    seen: set[str] = set()
    aliases = {row.term_code: [] for row in session.scalars(select(GlossaryTerm))}
    for alias in session.scalars(select(GlossaryAlias)):
        aliases.setdefault(alias.term_code, []).append(alias.alias)
    for term in session.scalars(select(GlossaryTerm).order_by(GlossaryTerm.title)):
        blob = " ".join(
            [
                term.term_code,
                term.title,
                term.definition,
                *aliases.get(term.term_code, []),
            ]
        ).lower()
        if lowered not in blob:
            continue
        if term.term_code in seen:
            continue
        seen.add(term.term_code)
        hits.append(
            SearchHitOut(
                kind="glossary",
                id=term.term_code,
                label=f"{term.title} — {term.definition}",
                href=f"/help#{term.term_code}",
            )
        )
    return hits
