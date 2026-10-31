"""Offline derivation from a manually reviewed career timeline, never raw documents."""

import re
from collections import defaultdict
from datetime import date

from .profile import Fact, Profile, normalize

MONTHS_ES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
MONTHS_EN = (
    "January February March April May June July August September October November December".split()
)


def month_index(value: str) -> int:
    if not re.fullmatch(r"\d{4}-\d{2}", value):
        raise ValueError("Month must use YYYY-MM")
    parsed = date.fromisoformat(value + "-01")
    return parsed.year * 12 + parsed.month - 1


def covered_months(roles: list[dict], as_of: str) -> int:
    """Calendar-month estimate; include endpoints and union concurrent intervals."""
    cutoff = month_index(as_of)
    covered = set()
    for role in roles:
        start = month_index(role["start"])
        end = month_index(role["end"] or as_of)
        if end < start or start > cutoff:
            raise ValueError("Career interval is reversed or starts after the review month")
        covered.update(range(start, min(end, cutoff) + 1))
    return len(covered)


def duration(months: int, language: str) -> str:
    years, remainder = divmod(months, 12)
    parts = []
    if years:
        unit = (
            ("año" if years == 1 else "años")
            if language == "es"
            else ("year" if years == 1 else "years")
        )
        parts.append(f"{years} {unit}")
    if remainder or not parts:
        unit = (
            ("mes" if remainder == 1 else "meses")
            if language == "es"
            else ("month" if remainder == 1 else "months")
        )
        parts.append(f"{remainder} {unit}")
    return (" y " if language == "es" else " and ").join(parts)


def month_label(value: str, language: str) -> str:
    month_index(value)
    year, month = map(int, value.split("-"))
    if language == "es":
        return f"{MONTHS_ES[month - 1]} de {year}"
    return f"{MONTHS_EN[month - 1]} {year}"


def consolidate(profile: Profile, career: dict) -> Profile:
    """Regenerate derived facts, preserving reviewed base facts and provenance."""
    roles, as_of = career["roles"], career["as_of"]
    months = covered_months(roles, as_of)
    earliest = min(role["start"] for role in roles)
    sources = list(dict.fromkeys(source for role in roles for source in role["source_ids"]))
    facts = [fact for fact in profile.facts if "derived-tenure" not in fact.tags]
    facts.append(
        Fact(
            id="career-tenure",
            category="summary",
            entity="Fernando Peralta",
            tags=["derived-tenure", "tenure", "tenure-global", "años", "years", "antigüedad"],
            text_es=(
                f"Fernando tiene aproximadamente {duration(months, 'es')} de experiencia "
                f"profesional en desarrollo web, con una trayectoria iniciada en {earliest[:4]}. "
                f"El cálculo reúne sus empleos, proyectos profesionales y actividad en DevStore MX "
                f"hasta {month_label(as_of, 'es')}, sin sumar dos veces los meses de trabajos simultáneos."
            ),
            text_en=(
                f"Fernando has approximately {duration(months, 'en')} of professional web development "
                f"experience, with a career that started in {earliest[:4]}. "
                f"The estimate combines his jobs, professional projects and DevStore MX activity "
                f"through {month_label(as_of, 'en')}, counting overlapping months only once."
            ),
            source_ids=sources,
        )
    )
    grouped = defaultdict(list)
    for role in roles:
        grouped[role["entity"]].append(role)
    for entity, intervals in grouped.items():
        months = covered_months(intervals, as_of)
        start = min(role["start"] for role in intervals)
        end = max(role["end"] or as_of for role in intervals)
        slug = re.sub(r"[^a-z0-9]+", "-", normalize(entity)).strip("-")
        facts.append(
            Fact(
                id=f"tenure-{slug}",
                category="experience",
                entity=entity,
                tags=["derived-tenure", "tenure", "tenure-role", "años", "years", entity],
                text_es=(
                    f"Su experiencia en {entity} abarca aproximadamente {duration(months, 'es')}, "
                    f"de {month_label(start, 'es')} a {month_label(end, 'es')}. "
                    "Es una estimación por meses de los periodos registrados."
                ),
                text_en=(
                    f"His experience at {entity} spans approximately {duration(months, 'en')}, "
                    f"from {month_label(start, 'en')} to {month_label(end, 'en')}. "
                    "This is a calendar-month estimate of the recorded role periods."
                ),
                source_ids=list(
                    dict.fromkeys(source for role in intervals for source in role["source_ids"])
                ),
            )
        )
    return Profile.model_validate(
        {**profile.model_dump(), "facts": [f.model_dump() for f in facts]}
    )


def knowledge_markdown(profile: Profile, career: dict) -> str:
    lines = [
        f"# Conocimiento consolidado — {profile.name}",
        "",
        f"Versión: {profile.version}. Revisión temporal: {career['as_of']}.",
        "",
        "Esta fuente reúne hechos revisados de los CV, el sitio profesional y la exportación "
        "MHTML de LinkedIn. La API consume su versión estructurada en profile.json, nunca el "
        "HTML bruto. Las referencias se conservan internamente y se omiten en las respuestas.",
        "",
        "## Criterio de fechas y cálculo",
        "",
        "Las duraciones son aproximaciones por meses naturales con ambos extremos incluidos. "
        "Los meses simultáneos se cuentan una sola vez. Las actividades abiertas se limitan "
        "al mes de revisión; hay que actualizar esta fuente para extenderlas.",
        "",
        *[f"- {note}" for note in career["reconciliation"]],
        "",
        "## Trayectoria consolidada",
        "",
        "| Organización | Función | Inicio | Fin |",
        "| --- | --- | --- | --- |",
        *[
            f"| {r['entity']} | {r['role_es']} | {r['start']} | {r['end'] or 'En curso al revisar'} |"
            for r in career["roles"]
        ],
        "",
        "## Hechos para conversación",
        "",
    ]
    for fact in profile.facts:
        lines += [f"### {fact.id}", "", fact.text_es, "", fact.text_en, ""]
    return "\n".join(lines)
