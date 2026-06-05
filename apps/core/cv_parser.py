"""
cv_parser — Extraction de données structurées depuis le texte brut d'un CV.

Complément à `cv_extraction` (qui produit le texte) : `cv_parser` enrichit le profil
candidat à partir du texte extrait, pour éviter qu'un CV bien rédigé soit pénalisé
parce que le candidat n'a pas (encore) rempli les champs structurés du formulaire.

Sortie : ParsedCV — dataclass avec skills, experience_years, education_level,
languages, emails, phones et un niveau de confiance par champ.

Aucune dépendance externe lourde : regex + référentiel TECH_SKILLS (ml/jd_keywords).
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# PATTERNS DÉTECTION
# ─────────────────────────────────────────────────────────────

# Emails
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
# Téléphones (international + national, tolère espaces/tirets/points)
_PHONE_RE = re.compile(
    r"(?:\+\d{1,3}[\s.\-]?)?(?:\(?\d{2,4}\)?[\s.\-]?){2,5}\d{2,4}"
)

# Sections classiques du CV (en-têtes) — détection insensible à la casse/accents
_SECTION_PATTERNS: dict[str, list[str]] = {
    "skills": [
        r"\bcomp[eé]tences?(?:\s+(?:techniques?|cl[eé]s|principales))?\b",
        r"\bskills?\b", r"\btechnical\s+skills?\b", r"\bkey\s+skills?\b",
        r"\bsavoir[\s\-]faire\b", r"\btechnologies?\b", r"\boutils?\b", r"\btools?\b",
    ],
    "experience": [
        r"\bexp[eé]riences?(?:\s+(?:professionnelle[s]?|pro))?\b",
        r"\bexperience\b", r"\bwork\s+(?:experience|history)\b",
        r"\bparcours\s+(?:professionnel|pro)\b", r"\bemploi[s]?\b",
        r"\bemployment\b", r"\bprofessional\s+experience\b",
    ],
    "education": [
        r"\bformations?\b", r"\b[eé]tudes?\b", r"\b[eé]ducation\b",
        r"\bdipl[oô]mes?\b", r"\bcursus\b", r"\bacademic\s+background\b",
        r"\bqualifications?\b",
    ],
    "languages": [
        r"\blangues?\b", r"\blanguages?\b", r"\blinguistique\b",
    ],
}

# Langues + niveaux (FR/EN, normalisés)
_LANGUAGES_KNOWN: dict[str, list[str]] = {
    "français": ["francais", "français", "french", "fr"],
    "anglais": ["anglais", "english", "en"],
    "espagnol": ["espagnol", "spanish", "es", "espanol"],
    "allemand": ["allemand", "german", "de", "deutsch"],
    "italien": ["italien", "italian", "it"],
    "portugais": ["portugais", "portuguese", "pt"],
    "arabe": ["arabe", "arabic", "ar"],
    "chinois": ["chinois", "mandarin", "chinese", "zh"],
    "japonais": ["japonais", "japanese", "ja"],
    "russe": ["russe", "russian", "ru"],
    "swahili": ["swahili", "kiswahili"],
    "wolof": ["wolof"],
    "bambara": ["bambara"],
    "lingala": ["lingala"],
    "haoussa": ["haoussa", "hausa"],
    "yoruba": ["yoruba"],
    "amharique": ["amharique", "amharic"],
}

_LANGUAGE_LEVELS = {
    "natif": ["natif", "native", "maternelle", "mother tongue", "langue maternelle"],
    "courant": ["courant", "fluent", "bilingue", "bilingual", "c2", "c1"],
    "professionnel": ["professionnel", "professional", "advanced", "avance", "b2"],
    "intermediaire": ["intermediaire", "intermédiaire", "intermediate", "b1"],
    "basique": ["basique", "basic", "elementary", "debutant", "débutant", "a1", "a2", "notions"],
}


# ─────────────────────────────────────────────────────────────
# DATACLASS DE SORTIE
# ─────────────────────────────────────────────────────────────

@dataclass
class ParsedCV:
    """Résultat de parsing d'un CV. Chaque champ a une confiance 0-1."""
    skills: list[str] = field(default_factory=list)
    experience_years: int | None = None
    education_level: str | None = None
    languages: list[dict[str, str]] = field(default_factory=list)  # [{language, proficiency}]
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    # Confiance par champ (0–1) : faible quand l'extraction est incertaine
    confidence: dict[str, float] = field(default_factory=dict)
    # Warnings : raisons pour lesquelles certains champs n'ont pas été extraits
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "skills": self.skills,
            "experience_years": self.experience_years,
            "education_level": self.education_level,
            "languages": self.languages,
            "emails": self.emails,
            "phones": self.phones,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Lowercase + dé-accentuation pour la détection insensible aux accents."""
    if not text:
        return ""
    s = text.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip()


def _find_section(text: str, section_name: str) -> str | None:
    """
    Tente d'extraire le contenu d'une section (entre son titre et le titre suivant).
    Retourne None si non trouvée. Le contenu est dans la casse originale.
    """
    patterns = _SECTION_PATTERNS.get(section_name, [])
    all_section_patterns: list[str] = []
    for pats in _SECTION_PATTERNS.values():
        all_section_patterns.extend(pats)
    section_re = "|".join(all_section_patterns)

    _section_flags = re.IGNORECASE | re.MULTILINE
    for p in patterns:
        # Cherche l'en-tête (sur une ligne propre ou avec ponctuation)
        regex = re.compile(
            rf"^\s*(?:[•\-*]+\s*)?({p})\s*[:\-]?\s*$|({p})\s*[:\-]",
            _section_flags,
        )
        m = regex.search(text)
        if not m:
            continue
        start = m.end()
        # Cherche le prochain en-tête de section pour borner
        next_section = re.compile(
            rf"^\s*(?:[•\-*]+\s*)?({section_re})\s*[:\-]?\s*$|({section_re})\s*[:\-]",
            _section_flags,
        )
        next_m = next_section.search(text, start)
        end = next_m.start() if next_m else min(start + 4000, len(text))
        snippet = text[start:end].strip()
        if snippet:
            return snippet
    return None


# ─────────────────────────────────────────────────────────────
# EXTRACTEURS PAR CHAMP
# ─────────────────────────────────────────────────────────────

def extract_skills(raw_text: str, search_in_section_first: bool = True) -> tuple[list[str], float]:
    """
    Détecte les compétences techniques présentes dans le CV via le référentiel TECH_SKILLS.
    Stratégie : on cherche d'abord dans la section "Compétences" si elle existe (signal
    plus fort), puis dans tout le CV en complément.
    Retourne (skills, confidence).
    """
    from ml.jd_keywords import _detect_known_skills  # import local pour éviter cycle

    if not raw_text:
        return [], 0.0

    primary_skills: list[str] = []
    if search_in_section_first:
        section = _find_section(raw_text, "skills")
        if section:
            primary_skills = _detect_known_skills(section)

    # Recherche complémentaire dans tout le CV (skills mentionnés dans expériences)
    all_skills = _detect_known_skills(raw_text)
    # Préserver l'ordre : section d'abord, puis le reste sans doublon
    seen: set[str] = set(primary_skills)
    merged = list(primary_skills)
    for s in all_skills:
        if s not in seen:
            merged.append(s)
            seen.add(s)

    # Confiance : forte si trouvée dans la section dédiée, modérée sinon
    if not merged:
        confidence = 0.0
    elif primary_skills:
        confidence = 0.9 if len(primary_skills) >= 3 else 0.7
    else:
        confidence = 0.5  # trouvée seulement dans le corps du CV
    return merged, confidence


def extract_experience_years(raw_text: str) -> tuple[int | None, float]:
    """
    Détecte le nombre d'années d'expérience depuis le CV.
    Stratégie en cascade :
      1. Phrase explicite ("X ans d'expérience" / "X years of experience").
      2. Section expérience : agrégation des dates de chaque poste (calcul cumulé).
      3. Aucune détection → None.
    Retourne (years, confidence).
    """
    if not raw_text:
        return None, 0.0

    # 1) Phrase explicite — réutilise les patterns de jd_keywords
    from ml.jd_keywords import _detect_min_experience
    direct = _detect_min_experience(raw_text)
    if direct is not None and 0 < direct <= 50:
        return direct, 0.85

    # 2) Agrégation des dates dans la section expérience
    section = _find_section(raw_text, "experience") or raw_text
    # Pattern de période : "2020 - 2023", "Jan 2020 - Dec 2022", "2020 - présent"
    period_re = re.compile(
        r"(\d{4})\s*(?:[-–à]|to|au)\s*(\d{4}|pr[eé]sent|present|today|aujourd['\s]?hui|now|en\s+cours)",
        re.IGNORECASE,
    )
    current_year = date.today().year
    total_months = 0
    periods_found = 0
    for m in period_re.finditer(section):
        try:
            start = int(m.group(1))
        except (ValueError, TypeError):
            continue
        end_raw = (m.group(2) or "").lower()
        try:
            end = int(end_raw)
        except ValueError:
            end = current_year
        if not (1970 <= start <= current_year + 1) or end < start:
            continue
        total_months += (end - start) * 12
        periods_found += 1

    if periods_found > 0 and total_months > 0:
        years = max(1, round(total_months / 12))
        # Confiance modérée : on a calculé sans certitude sur la simultanéité des postes
        confidence = 0.6 if periods_found >= 2 else 0.5
        return years, confidence

    return None, 0.0


def extract_education_level(raw_text: str) -> tuple[str | None, float]:
    """
    Détecte le niveau d'études le plus élevé mentionné.
    Réutilise les patterns de jd_keywords (EDUCATION_PATTERNS).
    Retourne (level, confidence).
    """
    if not raw_text:
        return None, 0.0

    from ml.jd_keywords import EDUCATION_PATTERNS

    # On parcourt du plus exigeant au moins exigeant
    found_level = None
    for pattern, level in EDUCATION_PATTERNS:
        if pattern.search(raw_text):
            found_level = level
            break  # le premier trouvé est le plus exigeant (l'ordre des patterns le garantit)

    if not found_level:
        return None, 0.0

    # Confiance forte si trouvé dans la section "Formation"
    section = _find_section(raw_text, "education")
    if section:
        for pattern, level in EDUCATION_PATTERNS:
            if pattern.search(section) and level == found_level:
                return found_level, 0.9
    return found_level, 0.7


def extract_languages(raw_text: str) -> tuple[list[dict[str, str]], float]:
    """
    Détecte les langues parlées et leur niveau dans le CV.
    Stratégie : cherche dans la section "Langues" puis dans tout le texte.
    Retourne (languages, confidence) où languages est [{language, proficiency}].
    """
    if not raw_text:
        return [], 0.0

    section = _find_section(raw_text, "languages") or raw_text
    section_norm = _normalize(section)

    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for canonical, variants in _LANGUAGES_KNOWN.items():
        for v in variants:
            v_norm = _normalize(v)
            if v_norm and re.search(rf"\b{re.escape(v_norm)}\b", section_norm):
                if canonical in seen:
                    continue
                # Cherche un niveau à proximité (50 caractères après la mention de la langue)
                idx = section_norm.find(v_norm)
                window = section_norm[idx : idx + 60]
                proficiency = None
                for level_name, level_variants in _LANGUAGE_LEVELS.items():
                    for lv in level_variants:
                        if re.search(rf"\b{re.escape(_normalize(lv))}\b", window):
                            proficiency = level_name
                            break
                    if proficiency:
                        break
                found.append({"language": canonical, "proficiency": proficiency or "non précisé"})
                seen.add(canonical)
                break

    if not found:
        return [], 0.0
    confidence = 0.85 if _find_section(raw_text, "languages") else 0.5
    return found, confidence


def extract_contact_info(raw_text: str) -> tuple[list[str], list[str]]:
    """Extrait emails et téléphones du CV."""
    if not raw_text:
        return [], []
    emails = list(dict.fromkeys(_EMAIL_RE.findall(raw_text)))[:5]
    # Téléphones : on garde ceux d'au moins 7 chiffres pour éviter le bruit
    phones_raw = _PHONE_RE.findall(raw_text)
    phones: list[str] = []
    seen: set[str] = set()
    for p in phones_raw:
        digits = re.sub(r"\D", "", p)
        if len(digits) < 7 or len(digits) > 16:
            continue
        clean = p.strip()
        if clean not in seen:
            seen.add(clean)
            phones.append(clean)
        if len(phones) >= 5:
            break
    return emails, phones


# ─────────────────────────────────────────────────────────────
# ORCHESTRATEUR
# ─────────────────────────────────────────────────────────────

def parse_cv(raw_text: str) -> ParsedCV:
    """
    Orchestre l'extraction de tous les champs structurés depuis raw_cv_text.
    Ne lève jamais d'exception : retourne un ParsedCV avec warnings explicatifs.
    """
    result = ParsedCV()

    if not raw_text or not isinstance(raw_text, str):
        result.warnings.append("Texte CV vide ou invalide.")
        return result

    if len(raw_text) < 50:
        result.warnings.append(
            f"Texte CV très court ({len(raw_text)} chars) — extraction probablement incomplète."
        )

    try:
        skills, conf_skills = extract_skills(raw_text)
        result.skills = skills
        result.confidence["skills"] = conf_skills
        if not skills:
            result.warnings.append("Aucune compétence du référentiel détectée.")
    except Exception as e:
        logger.warning("cv_parser: erreur extract_skills : %s", e)
        result.warnings.append(f"Erreur skills: {e}")

    try:
        years, conf_exp = extract_experience_years(raw_text)
        result.experience_years = years
        result.confidence["experience_years"] = conf_exp
        if years is None:
            result.warnings.append("Années d'expérience non détectées dans le CV.")
    except Exception as e:
        logger.warning("cv_parser: erreur extract_experience_years : %s", e)
        result.warnings.append(f"Erreur experience: {e}")

    try:
        level, conf_edu = extract_education_level(raw_text)
        result.education_level = level
        result.confidence["education_level"] = conf_edu
        if not level:
            result.warnings.append("Niveau d'études non détecté.")
    except Exception as e:
        logger.warning("cv_parser: erreur extract_education_level : %s", e)
        result.warnings.append(f"Erreur education: {e}")

    try:
        languages, conf_lang = extract_languages(raw_text)
        result.languages = languages
        result.confidence["languages"] = conf_lang
    except Exception as e:
        logger.warning("cv_parser: erreur extract_languages : %s", e)
        result.warnings.append(f"Erreur languages: {e}")

    try:
        emails, phones = extract_contact_info(raw_text)
        result.emails = emails
        result.phones = phones
    except Exception as e:
        logger.warning("cv_parser: erreur extract_contact_info : %s", e)

    logger.info(
        "cv_parser: skills=%d exp=%s edu=%s langs=%d emails=%d phones=%d warnings=%d",
        len(result.skills), result.experience_years, result.education_level,
        len(result.languages), len(result.emails), len(result.phones),
        len(result.warnings),
    )
    return result


def enrich_candidate_from_cv(candidate, raw_text: str, overwrite: bool = False) -> dict:
    """
    Enrichit un candidat avec les données extraites du CV.
    Par défaut, ne touche QUE les champs vides (overwrite=False).
    Retourne un dict des champs mis à jour avec leur source de confiance.

    Args:
        candidate: instance Candidate Django (modifié in-place, save() pas appelé ici)
        raw_text: texte brut du CV
        overwrite: si True, remplace même les champs déjà renseignés (par défaut False)

    Returns:
        {"updated_fields": [...], "parsed": ParsedCV.to_dict()}
    """
    parsed = parse_cv(raw_text)
    updated_fields: list[str] = []

    # skills : on fusionne avec l'existant (pas de remplacement destructif)
    existing_skills = getattr(candidate, "skills", None) or []
    existing_set = {s.lower() for s in existing_skills}
    new_skills = [s for s in parsed.skills if s.lower() not in existing_set]
    if new_skills and (overwrite or not existing_skills):
        candidate.skills = list(existing_skills) + new_skills
        updated_fields.append("skills")
    elif new_skills:
        # Ajout incrémental même quand des skills existent déjà
        candidate.skills = list(existing_skills) + new_skills
        updated_fields.append("skills")

    # experience_years : on remplit si vide ou faible confiance
    if parsed.experience_years is not None:
        current = getattr(candidate, "experience_years", None)
        if overwrite or current is None or current == 0:
            candidate.experience_years = parsed.experience_years
            updated_fields.append("experience_years")

    # education_level : on remplit si vide
    if parsed.education_level:
        current = (getattr(candidate, "education_level", "") or "").strip()
        if overwrite or not current:
            candidate.education_level = parsed.education_level
            updated_fields.append("education_level")

    # languages : on ajoute les langues manquantes
    if parsed.languages:
        existing_langs = getattr(candidate, "languages", None) or []
        existing_names = {
            (l.get("language") or "").lower()
            for l in existing_langs
            if isinstance(l, dict)
        }
        new_langs = [l for l in parsed.languages if l["language"].lower() not in existing_names]
        if new_langs and (overwrite or not existing_langs):
            candidate.languages = list(existing_langs) + new_langs
            updated_fields.append("languages")
        elif new_langs:
            candidate.languages = list(existing_langs) + new_langs
            updated_fields.append("languages")

    return {"updated_fields": updated_fields, "parsed": parsed.to_dict()}
