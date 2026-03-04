"""
Extraction de mots-clés et critères structurés depuis l'offre (priorité aux exigences).
- extract_keywords_from_job : pour le matching ATS (CV vs JD).
- extract_suggested_criteria : pour l'affichage des critères identifiés (keywords, expérience, éducation).
"""
import re
from typing import Any

# Mots vides FR/EN à ignorer
STOP_WORDS = frozenset({
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'its', 'may', 'who', 'how', 'why', 'when', 'what', 'which', 'that', 'this', 'with', 'from', 'their', 'there', 'they', 'them', 'then', 'than', 'been', 'being', 'into', 'over', 'such', 'only', 'just', 'more', 'some', 'other', 'about', 'after', 'before', 'between', 'under', 'again', 'during', 'where', 'through', 'each', 'very', 'could', 'should', 'would', 'will', 'your', 'les', 'des', 'une', 'dans', 'pour', 'qui', 'que', 'est', 'son', 'sont', 'aux', 'pas', 'sur', 'tout', 'nous', 'vous', 'avec', 'sans', 'sous', 'chez', 'donc', 'comme', 'mais', 'ou', 'et', 'si', 'ce', 'cette', 'ces', 'mon', 'ton', 'mes', 'tes', 'notre', 'votre', 'leur', 'leurs', 'plus', 'fait', 'faites', 'role', 'rôle', 'se', 'concentrera', 'assurera', 'développera', 'transformera', 'valorisa', 'imo', 'op', 'male', 'nutri', 'structura', 'informa', 'analy', 'on',
})

# Niveaux d'études reconnus (ordre de préférence pour le match)
EDUCATION_PATTERNS = [
    (r'\b(doctorat|phd|doctoral)\b', 'doctorat'),
    (r'\b(master|masters?|maîtrise|msc|mba)\b', 'master'),
    (r'\b(licence|bachelor|bsc|bac\s*\+?\s*\d?)\b', 'licence'),
    (r'\b(ingénieur|engineer)\b', 'ingénieur'),
    (r'\b(bac|baccalaureat|bacc)\b', 'bac'),
    (r'\b(diplôme|diploma|graduat)\b', 'licence'),  # générique
]

# Regex pour années d'expérience (FR/EN)
_EXP_ANS = r"(?:ans?|years?|anées?)"
_EXP_D_EXP = r"(?:d['']?\s*expérience|of\s+experience|d['']?\s*exp)"
EXPERIENCE_PATTERNS = [
    r"\b(?:au\s+moins|minimum|min\.?|at\s+least)\s*[:\s]*(\d+)\s*" + _EXP_ANS + r"\b",
    r"\b(\d+)\s*" + _EXP_ANS + r"\s*" + _EXP_D_EXP + r"\b",
    r"\b(?:expérience|experience)\s*[:\s]*(\d+)\s*" + _EXP_ANS + r"\b",
    r"\b(\d+)\s*[-à]\s*(\d+)\s*" + _EXP_ANS + r"\b",
    r"\b(\d+)\s*" + _EXP_ANS + r"\s*(?:et\s+plus|and\s+above|minimum)\b",
]


def _normalize(text: str, max_len: int = 50_000) -> str:
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r'\s+', ' ', text.strip()).lower()
    return text[:max_len]


def _tokens_from_text(text: str, min_len: int = 3) -> list[str]:
    tokens = re.findall(r'[a-z0-9éèêëàâäùûüîïôöç]{2,}', text)
    return [w for w in tokens if w not in STOP_WORDS and len(w) >= min_len]


def extract_keywords_from_job(job: Any, max_words: int = 80, max_bigrams: int = 40) -> list[str]:
    """
    Extrait une liste de mots et expressions clés depuis l'offre (priorité requirements, puis titre, description).
    Utilisé pour le matching ATS CV vs JD.
    """
    # Priorité : exigences d'abord (où sont les vrais critères), puis titre, puis description
    requirements = _normalize(str(getattr(job, 'requirements', None) or ''))
    title = _normalize(str(getattr(job, 'title', None) or ''))
    description = _normalize(str(getattr(job, 'description', None) or ''))
    text = ' '.join([requirements, title, description]).strip()
    if not text:
        return []

    tokens = _tokens_from_text(text, min_len=2)
    seen = set()
    unique_words = [w for w in tokens if w not in seen and not seen.add(w)]
    bigrams = []
    for i in range(len(unique_words) - 1):
        a, b = unique_words[i], unique_words[i + 1]
        if a not in STOP_WORDS and b not in STOP_WORDS and (len(a) > 3 or len(b) > 3):
            bigram = f"{a} {b}"
            if bigram not in seen:
                seen.add(bigram)
                bigrams.append(bigram)
    result = unique_words[:max_words] + bigrams[:max_bigrams]
    return result[: max_words + max_bigrams]


def _extract_keywords_from_text(text: str, min_len: int = 4, max_keywords: int = 50) -> list[str]:
    """Extrait mots-clés et bigrammes depuis un texte normalisé."""
    text = _normalize(text)
    if not text:
        return []
    tokens = _tokens_from_text(text, min_len=min_len)
    seen = set()
    words = [w for w in tokens if w not in seen and not seen.add(w)]
    bigrams = []
    for i in range(len(words) - 1):
        a, b = words[i], words[i + 1]
        if len(a) >= 4 or len(b) >= 4:
            bg = f"{a} {b}"
            if bg not in seen:
                seen.add(bg)
                bigrams.append(bg)
    result = words[: max_keywords - 15] + bigrams[:15]
    return result[:max_keywords]


def _extract_keywords_from_requirements_and_title(job: Any, max_keywords: int = 50) -> list[str]:
    """Extrait les mots-clés en priorité depuis les exigences et le titre ; sinon depuis la description."""
    requirements = str(getattr(job, 'requirements', None) or '').strip()
    title = str(getattr(job, 'title', None) or '').strip()
    description = str(getattr(job, 'description', None) or '').strip()

    # 1) Exigences + titre (priorité)
    text_primary = ' '.join([requirements, title])
    keywords = _extract_keywords_from_text(text_primary, min_len=4, max_keywords=max_keywords)

    # 2) Si rien trouvé (exigences/titre vides), utiliser la description
    if not keywords and description:
        keywords = _extract_keywords_from_text(description, min_len=4, max_keywords=max_keywords)

    return keywords


def _detect_min_experience(text: str) -> int | None:
    """Détecte un nombre d'années d'expérience minimum dans le texte."""
    if not text:
        return None
    text_lower = text.lower()
    for pattern in EXPERIENCE_PATTERNS:
        m = re.search(pattern, text_lower, re.IGNORECASE)
        if m:
            g = m.groups()
            if len(g) >= 2:
                try:
                    return min(int(g[0]), int(g[1]))
                except (ValueError, TypeError):
                    pass
            if g:
                try:
                    return int(g[0])
                except (ValueError, TypeError):
                    pass
    return None


def _detect_education_level(text: str) -> str | None:
    """Détecte un niveau d'études dans le texte (le plus exigeant trouvé)."""
    if not text:
        return None
    text_lower = text.lower()
    found = None
    for pattern, level in EDUCATION_PATTERNS:
        if re.search(pattern, text_lower):
            found = level
            break
    return found


def extract_suggested_criteria(job: Any) -> dict[str, Any]:
    """
    Extrait des critères structurés pour affichage dans Présélection/Sélection :
    - keywords : mots-clés issus des exigences et du titre (compétences, outils, etc.)
    - min_experience : années d'expérience min si détectées
    - education_level : niveau d'études si détecté
    """
    requirements = _normalize(str(getattr(job, 'requirements', None) or ''))
    description = _normalize(str(getattr(job, 'description', None) or ''))
    text_for_exp_edu = ' '.join([requirements, description])

    keywords = _extract_keywords_from_requirements_and_title(job, max_keywords=50)
    min_experience = _detect_min_experience(text_for_exp_edu)
    education_level = _detect_education_level(text_for_exp_edu)

    return {
        'keywords': keywords,
        'min_experience': min_experience,
        'education_level': education_level,
    }
