import math
import re
from collections import Counter

from .profile import Fact, Profile, normalize

STOP = set(
    "a al algo all and are as at be con como cual cuales de del describe detalle detalles do el ella en es experiencia experience explain fernando for from has have he his how i in la las le lo los me mi my of on or para peralta perfil por profesional professional profile que quien resume resumen se skills sobre su sus tell the their this to tu un una what which who with y you your años years".split()
)
STOP.update(
    "documenta documentado documentada documentados documented laboral laborales background currently actualmente tiene tiene hizo hacer ha hay hace como como pueden puede puedes cuentame cuentanos dime yourself aparece aparecen listed lista incluye declara desarrollado develop built build worked trabajo work acerca cuales cuantos cuanto was were que do does did is about little bit please favor favor mas more would could knows know tiene conoces".split()
)
STOP.update(
    {"ti", "tienes", "sabes", "sabe", "haces", "yourself", "donde", "when", "where", "why", "can"}
)
ALIASES = {
    "habilidades": "skills",
    "tecnologias": "skills",
    "tecnologia": "skills",
    "herramientas": "skills",
    "tools": "skills",
    "technologies": "skills",
    "proyectos": "projects",
    "proyecto": "projects",
    "project": "projects",
    "estudios": "education",
    "educacion": "education",
    "estudia": "education",
    "idiomas": "languages",
    "idioma": "languages",
    "languages": "languages",
    "ingles": "english",
    "aleman": "german",
    "espanol": "spanish",
    "equipo": "team",
    "liderazgo": "leadership",
    "lidero": "leadership",
    "automatizacion": "automation",
    "automatizo": "automation",
    "errores": "errors",
    "reduccion": "reduction",
    "extensiones": "extension",
    "contacto": "links",
    "contact": "links",
    "web": "links",
    "linkedin": "links",
    "certificaciones": "training",
    "cursos": "training",
    "certifications": "training",
    "trayectoria": "summary",
    "presentate": "summary",
    "introduce": "summary",
    "experiencia": "experience",
    "trabajo": "experience",
    "roles": "experience",
    "formacion": "training",
    "certificacion": "training",
    "certification": "training",
    "certificado": "training",
    "certificate": "training",
    "course": "training",
    "courses": "training",
    "hablame": "summary",
    "presentame": "summary",
    "carrera": "summary",
    "career": "summary",
    "empresas": "employers",
    "companies": "employers",
    "empleadores": "employers",
    "trabajado": "employers",
    "empresa": "employers",
    "companias": "employers",
    "compania": "employers",
    "organizaciones": "employers",
    "organizacion": "employers",
    "company": "employers",
    "employer": "employers",
    "organizations": "employers",
    "organisations": "employers",
}
ENTITY_ALIASES = {
    "devstoremx": "devstore mx",
    "applab.mx": "applabmx",
    "applab mx": "applabmx",
    "arkus nexus": "arkusnexus",
    "stitchers space": "stitchers.space",
}


def entity_text(text: str) -> str:
    text = normalize(text).replace("’", "'")
    for alias, canonical in ENTITY_ALIASES.items():
        text = text.replace(alias, canonical)
    return text


def tokens(text: str) -> list[str]:
    words = (word.strip(".") for word in re.findall(r"[a-z0-9+#.]+", normalize(text)))
    return [ALIASES.get(t, t) for t in words if t not in STOP and len(t) > 1]


EMPLOYER_HISTORY = re.compile(
    r"\b(empresas?|companias?|organizaciones?|empleadores?|companies|company|employers?|"
    r"organizations|organisations)\b|"
    r"\b(donde|where)\b.{0,80}\b(trabajado|trabajaste|trabajo|trabajaba|worked)\b|"
    r"\b(historial|historia)\s+laboral\b|\b(employment|work)\s+history\b"
)
EMPLOYER_GENERAL = {
    "employers",
    "experience",
    "summary",
    "son",
    "list",
    "listado",
    "listame",
    "enumerar",
    "enumera",
    "menciona",
    "mencionar",
    "nombre",
    "nombres",
    "name",
    "names",
    "historial",
    "historia",
    "history",
    "employment",
    "decir",
    "decirme",
    "decirnos",
    "mostrar",
    "mostrarme",
    "sido",
    "been",
    "empleado",
    "employed",
    "trabajaste",
    "trabajaba",
    "empresas",
    "dar",
    "darme",
    "compartir",
    "compartirme",
    "indicar",
    "indicarme",
    "contar",
    "contarme",
    "estan",
    "estuvo",
    "estuvieron",
    "documentadas",
    "documentados",
    "detalladamente",
}


def employer_query(question: str) -> list[str] | None:
    """Separate conversational wrappers from actual employer/technology constraints."""
    if not EMPLOYER_HISTORY.search(question):
        return None
    text = re.sub(
        r"^(?:(?:ok(?:ay)?|vale|bueno|oye|entonces|pero|por favor|please|hola|hello)\b[\s,¿?!:.]*)+",
        "",
        question,
    )
    text = re.sub(r"^(?:no (?:sabes|sabe|se|recuerdo|conoces)|don'?t you know)\b", "", text)
    query = tokens(text)
    # Preserve meaningful qualifiers that ordinary BM25 stop words would drop.
    query += re.findall(r"\b(currently|actualmente|no|not|never|nunca)\b", text)
    return query


class Retriever:
    """BM25 over a tiny reviewed corpus; bilingual aliases avoid an embedding server."""

    def __init__(self, profile: Profile):
        self.facts = profile.facts
        self.docs = [
            Counter(tokens(" ".join([f.entity, f.category, *f.tags, f.text_es, f.text_en])))
            for f in self.facts
        ]
        self.avg = sum(sum(d.values()) for d in self.docs) / len(self.docs)
        self.df = Counter(t for doc in self.docs for t in doc)
        self.entities = {
            self.organization(f)
            for f in self.facts
            if f.category in {"experience", "projects", "training"}
        }

    @staticmethod
    def organization(fact: Fact) -> str:
        return entity_text(fact.entity).removesuffix(" formacion")

    def conversation_context(self, messages: list[dict]) -> str:
        users = [message["content"] for message in messages if message["role"] == "user"]
        for text in reversed(users):
            if any(entity in entity_text(text) for entity in self.entities):
                return text
        return users[-1] if users else ""

    @staticmethod
    def facet(question: str) -> tuple[set[str] | None, str | None]:
        if re.search(
            r"\b(entren\w*|trained|training)\b.{0,50}\b(model\w*)|\b(model\w*)\b.{0,50}\b(entren\w*|trained|training)\b",
            question,
        ):
            return {"projects"}, "model_training"
        if re.search(
            r"\b(dinero|monetario|money|savings|ahorro|ahorro[s]?|dolares|pesos|usd|mxn)\b",
            question,
        ):
            return {"experience", "projects"}, "money"
        if re.search(
            r"certificaci|certification|certified|\b(formacion|training|curso|cursos|course|courses)\b",
            question,
        ):
            return {"training"}, "training"
        if re.search(
            r"\b(doctorado|phd|maestria|master|degree|titulo|estudios|educacion|education)\b",
            question,
        ):
            return {"education"}, "education"
        if re.search(
            r"\b(emplead\w*|employ\w*|puesto|cargo|roles|laboral)\b|"
            r"\b(?:worked|working)\s+(?:at|for)\b|"
            r"\btrabaj(?:o|a|ar)\s+(?:en|para)\b",
            question,
        ):
            return {"experience", "projects"}, "employment"
        return None, None

    def search(self, question: str, previous_user: str = "", limit: int = 4) -> list[Fact]:
        query = tokens(question)
        normalized = entity_text(question).lstrip("¿¡ \t\r\n")
        history_query = employer_query(normalized)
        history_constraints = set()
        if history_query is not None:
            if not set(history_query) - EMPLOYER_GENERAL:
                # A complete, reviewed overview is the evidence for this intent.
                # Do not inherit a previous employer or rank unrelated facts.
                return [f for f in self.facts if f.id == "career-overview"][:limit]
            query = history_query
            history_constraints = (
                set(history_query)
                - EMPLOYER_GENERAL
                - {
                    "using",
                    "used",
                    "usa",
                    "uso",
                    "usando",
                    "utiliza",
                    "utilizando",
                }
            )
        # A generic career-history match must not substitute for a requested
        # employer or technology. Keep it only when no specific topic is asked.
        generic = {
            "employers",
            "experience",
            "skills",
            "projects",
            "training",
            "education",
            "summary",
        }
        if "employers" in query and any(term not in generic for term in query):
            query = [term for term in query if term != "employers"]
        categories, facet = self.facet(normalized)
        if history_query is not None and facet is None:
            categories, facet = {"experience", "projects"}, "employment"
        degree_levels = []
        if re.search(r"\b(doctorado|phd)\b", normalized):
            degree_levels = ["doctorado", "phd"]
        elif re.search(r"\b(maestria|master)\b", normalized):
            degree_levels = ["maestria", "master"]
        specific_terms = set(query) - {"training", "education", "experience", "projects", "skills"}
        explicit = [e for e in self.entities if e in normalized]
        # Resolve short follow-ups from the last USER turn, never from submitted assistant claims.
        followup = bool(
            re.search(
                r"^(y\b|and\b|what about\b|how about\b)|\b(eso|ese|esa|alli|ahi|there|that|it|tecnologias|technologies)\b",
                normalized,
            )
        )
        if re.search(
            r"\b(en general|generalmente|in general|overall|cambiando de tema|changing topics)\b",
            normalized,
        ):
            followup = False
        if not explicit and followup and previous_user:
            prior = entity_text(previous_user)
            explicit = [e for e in self.entities if e in prior]
            if len(query) <= 3:
                query += tokens(previous_user)
        duration_intent = re.search(
            r"\b(cuant\w*|how many|how much)\b.{0,45}\b(anos|years|meses|months|tiempo|time)\b|"
            r"\b(cuanto tiempo|how long|duracion|antiguedad|tenure|desde cuando|since when)\b",
            normalized,
        )
        career_context = explicit or re.search(
            r"\b(experiencia|experience|profesional|professional|carrera|career|trayectoria|"
            r"trabaj\w*|work\w*|emple\w*|puesto|cargo|role|lleva\w*|desarrollo|developer)\b",
            normalized,
        )
        if duration_intent and career_context and not re.search(r"\b(quien|who)\b", normalized):
            facet = "tenure"
            categories = None
            query.append("tenure")
            tenure_general = {
                "tenure",
                "summary",
                "experience",
                "professional",
                "profesional",
                "employers",
                "total",
                "totales",
                "general",
                "tiempo",
                "time",
                "meses",
                "months",
                "antiguedad",
                "duracion",
                "llevas",
                "lleva",
                "llevo",
                "laboral",
                "development",
                "desarrollo",
                "links",
                "carrera",
                "comenzo",
                "empezo",
                "started",
                "since",
                "desde",
                "cuando",
                "anos",
                "many",
                "much",
                "long",
                "tengo",
                "tiene",
                "trabajando",
                "trabajas",
                "trabaja",
                "trabaje",
                "trabajo",
                "worked",
                "working",
                "work",
                "programando",
                "programming",
                "dedica",
                "dedicas",
                "dedicado",
                "desarrollador",
                "desarrolladora",
                "developer",
                "programador",
            }
            # No estimate for a technology or an unknown company can be inferred
            # from the total career duration.
            if not explicit and set(query) - tenure_general:
                return []
        if not query:
            return [f for f in self.facts if f.category == "summary" and "tenure" not in f.tags][:2]
        scored = []
        for fact, doc in zip(self.facts, self.docs, strict=True):
            if history_constraints and not all(doc[term] for term in history_constraints):
                continue
            if facet == "tenure":
                if "tenure" not in fact.tags:
                    continue
                if not explicit and "tenure-global" not in fact.tags:
                    continue
            elif "derived-tenure" in fact.tags:
                continue
            if explicit and self.organization(fact) not in explicit:
                continue
            if categories and fact.category not in categories:
                continue
            if facet == "employment" and "personal" in fact.tags:
                continue
            if degree_levels and not any(
                level in normalize(fact.text_es + fact.text_en) for level in degree_levels
            ):
                continue
            if facet == "model_training" and not re.search(
                r"entren|train", normalize(fact.text_es + fact.text_en)
            ):
                continue
            if facet == "money" and not re.search(
                r"dinero|monetari|money|savings|ahorro|dolar|pesos|usd|mxn|\$",
                normalize(fact.text_es + fact.text_en),
            ):
                continue
            if (
                facet in {"training", "education"}
                and specific_terms
                and not any(doc[t] for t in specific_terms)
            ):
                continue
            score = 0.0
            length = sum(doc.values())
            for term in set(query):
                tf = doc[term]
                if tf:
                    idf = math.log(
                        1 + (len(self.docs) - self.df[term] + 0.5) / (self.df[term] + 0.5)
                    )
                    score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / self.avg))
                    if term in tokens(" ".join(fact.tags)):
                        score += 1.5
            if score > 0:
                scored.append((score, fact))
        return [f for _, f in sorted(scored, key=lambda x: x[0], reverse=True)[:limit]]
