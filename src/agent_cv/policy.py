import re
import unicodedata

from .profile import normalize

# These checks reduce common abuse and wasted inference. They are NOT the security boundary.
# The boundary is that the renderer accepts only IDs from the reviewed, retrieved facts.
ATTACK = re.compile(
    r"ignore.{0,70}(instruct|previous|rules|reglas)|ignora.{0,70}(instru|reglas|anteriores)|"
    r"(reveal|print|show|muestra|revela|imprime).{0,50}(system prompt|api.?key|secret|instrucciones internas|prompt del sistema)|"
    r"\b(base64|jailbreak|dan mode|developer mode|modo desarrollador|curl|subprocess)\b|"
    r"(actua|act|pretend).{0,30}(system|sistema|administrador|admin)|"
    r"(inventa|invent|finge|pretende).{0,60}(experien|trabaj|work|skill|habilidad|certific|titulo)|"
    r"(system|developer)\s*:|<\|(?:im_start|system|assistant)",
    re.I,
)
GENERAL_TASK = re.compile(
    r"\b(escribe|genera|programa|write|generate|implement|implementa|resuelve|solve|traduce|translate)\b.{0,90}"
    r"\b(codigo|code|script|programa|function|funcion|poema|poem|receta|recipe|ecuacion|equation|texto|text)\b|"
    r"\b(clima|weather|capital de|capital of|presidente|president|bitcoin|horoscopo|horoscope)\b",
    re.I,
)
PRIVATE = re.compile(
    r"\b(telefono|phone|celular|domicilio|address|salario|salary|sueldo|contrasena|password)\b|"
    r"\b(su|his|personal|private)\s+(correo|email|e-mail)\b|"
    r"\b(correo|email|e-mail)\s+(personal|privado|address|de contacto)\b|"
    r"^(dame|dime|revela|give|show).{0,30}\b(correo|email|e-mail)\b",
    re.I,
)
GREETING = re.compile(
    r"(?:(?:hola|hello|hi|hey|oye|buenas|buenos dias|buenas tardes|buenas noches)\s*)?"
    r"(?:estas ahi|estas disponible|sigues ahi|me escuchas|puedes ayudarme|me puedes ayudar|"
    r"estas listo|que tal|como estas|are you there|are you available|are you ready|"
    r"can you help me|how are you)?",
    re.I,
)


def language_of(question: str, previous_user: str = "") -> str:
    text = normalize(question)
    en = len(
        re.findall(
            r"\b(what|which|who|how|tell|your|his|he|does|did|have|about|experience|skills|projects|education|english|thanks|hello|hi|there|ready|available)\b",
            text,
        )
    )
    es = len(
        re.findall(
            r"\b(que|cual|quien|como|cuenta|tu|su|el|tiene|hizo|experiencia|habilidades|proyectos|estudios|espanol|hola|gracias)\b",
            text,
        )
    )
    if en == es == 0 and previous_user:
        return language_of(previous_user)
    return "en" if en > es else "es"


def precheck(question: str) -> str | None:
    normalized = normalize(question)
    if any(unicodedata.category(c) == "Cf" for c in question) or ATTACK.search(normalized):
        return "out_of_scope"
    if PRIVATE.search(normalized):
        return "private"
    if GENERAL_TASK.search(normalized):
        return "out_of_scope"
    social = re.sub(r"[^a-z0-9\s]", " ", normalized)
    social = " ".join(social.split())
    if social and (
        GREETING.fullmatch(social) or social in {"gracias", "muchas gracias", "thanks", "thank you"}
    ):
        return "greeting"
    if normalized.strip("¿?!. ") in {
        "quien eres",
        "who are you",
        "que puedes hacer",
        "what can you do",
        "como te llamas",
    }:
        return "greeting"
    return None


MESSAGES = {
    "es": {
        "greeting": "Hola, sí, estoy aquí. Listo para hablar de la carrera profesional de Fernando Peralta. Puedes preguntarme por su experiencia, habilidades, proyectos o formación.",
        "out_of_scope": "Puedo ayudarte con la trayectoria profesional documentada de Fernando Peralta. ¿Qué te gustaría conocer sobre su experiencia, habilidades o proyectos?",
        "private": "Solo comparto sus enlaces profesionales públicos: https://fernandoperalta.xyz y https://www.linkedin.com/in/fernandodperaltac/.",
        "unknown": "No tengo información documentada suficiente sobre ese punto del perfil de Fernando Peralta. Puedo responder sobre su experiencia, habilidades, proyectos y formación disponibles.",
    },
    "en": {
        "greeting": "Hello, yes, I am here and ready to talk about Fernando Peralta's professional career. You can ask about his experience, skills, projects, or education.",
        "out_of_scope": "I can help with Fernando Peralta's documented professional background. What would you like to know about his experience, skills, or projects?",
        "private": "I only share his public professional links: https://fernandoperalta.xyz and https://www.linkedin.com/in/fernandodperaltac/.",
        "unknown": "I do not have enough documented information about that aspect of Fernando Peralta's profile. I can answer questions about his available experience, skills, projects, and education.",
    },
}
