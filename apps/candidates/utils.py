"""
Utilitaires candidat : calcul des années d'expérience et inférence du niveau d'études
à partir du formulaire (liste expériences / formations) ou du texte du CV.
"""
import re
from datetime import date
from typing import Any


def _parse_year(s: Any) -> int | None:
    """Parse une année (int ou string numérique)."""
    if s is None:
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _parse_month(s: Any) -> int:
    """Parse un mois (1-12). Nom de mois ou numéro. Retourne 1 si invalide."""
    if s is None:
        return 1
    if isinstance(s, int) and 1 <= s <= 12:
        return s
    s = str(s).strip().lower()
    months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ]
    for i, m in enumerate(months):
        if m in s or s == str(i + 1):
            return (i % 12) + 1
    try:
        n = int(s)
        if 1 <= n <= 12:
            return n
    except (TypeError, ValueError):
        pass
    return 1


def _years_between(start_year: int, start_month: int, end_year: int, end_month: int) -> float:
    """Durée en années entre deux dates (approximation)."""
    start = start_year + (start_month - 1) / 12.0
    end = end_year + (end_month - 1) / 12.0
    if end < start:
        return 0.0
    return round(end - start, 2)


def get_candidate_experience_years(candidate: Any) -> int:
    """
    Retourne le nombre d'années d'expérience du candidat :
    - Si experience_years est renseigné et > 0, on l'utilise.
    - Sinon on calcule à partir de la liste experience (date début / fin par poste).
    - Sinon on tente d'extraire du texte du CV (ex. "6 ans d'expérience").
    """
    if getattr(candidate, "experience_years", None) is not None:
        try:
            y = int(candidate.experience_years)
            if y > 0:
                return y
        except (TypeError, ValueError):
            pass

    experience = getattr(candidate, "experience", None)
    if isinstance(experience, list) and experience:
        total = 0.0
        today = date.today()
        current_year = today.year
        current_month = today.month
        for entry in experience:
            if not isinstance(entry, dict):
                continue
            start_year = _parse_year(entry.get("start_year"))
            if start_year is None:
                continue
            start_month = _parse_month(entry.get("start_month"))
            end_year = _parse_year(entry.get("end_year"))
            end_month = _parse_month(entry.get("end_month"))
            if end_year is None:
                end_year = current_year
                end_month = current_month
            total += _years_between(start_year, start_month, end_year, end_month)
        if total > 0:
            return max(0, int(round(total)))

    raw = (getattr(candidate, "raw_cv_text", None) or "") or ""
    raw += " " + (getattr(candidate, "summary", None) or "")
    if raw:
        patterns = [
            r"\b(\d+)\s*ans?\s*(?:d['\s]*expérience|d['\s]*exp|of\s+experience)\b",
            r"\b(?:expérience|experience)\s*[:\s]*(\d+)\s*ans?\b",
            r"\b(\d+)\s*[-–]\s*(\d+)\s*ans?\b",
        ]
        for pattern in patterns:
            m = re.search(pattern, raw, re.IGNORECASE)
            if m:
                g = m.groups()
                try:
                    if len(g) >= 2:
                        return max(int(g[0]), int(g[1]))
                    return int(g[0])
                except (ValueError, TypeError):
                    pass
    return 0


def get_candidate_education_level(candidate: Any) -> str | None:
    """
    Retourne le niveau d'études le plus élevé du candidat :
    - Si education_level est renseigné, on l'utilise (normalisé).
    - Sinon on déduit de la liste education (degree_type, discipline, etc.).
    - Sinon on parse le CV (ex. "Encours : Master 2", "Licence en ...").
    """
    level = (getattr(candidate, "education_level", None) or "").strip()
    if level:
        return _normalize_education_level(level)

    education = getattr(candidate, "education", None)
    if isinstance(education, list):
        best_rank = -1
        best_level = None
        rank_order = ["bac", "licence", "master", "doctorat", "phd", "ingénieur"]
        for entry in education:
            if not isinstance(entry, dict):
                continue
            text = " ".join(
                str(entry.get(k) or "")
                for k in ("degree_type", "discipline", "other_specializations", "study_level", "institution")
            ).lower()
            for i, lev in enumerate(rank_order):
                if lev in text or (lev == "master" and ("maîtrise" in text or "maitrise" in text or "msc" in text or "mba" in text)):
                    if i > best_rank:
                        best_rank = i
                        best_level = lev
            if "encours" in text or "en cours" in text or "in progress" in text:
                for i, lev in enumerate(rank_order):
                    if lev in text and i > best_rank:
                        best_rank = i
                        best_level = lev
        if best_level:
            return best_level

    raw = (getattr(candidate, "raw_cv_text", None) or "") or ""
    raw += " " + (getattr(candidate, "summary", None) or "")
    if raw:
        from ml.jd_keywords import _detect_education_level
        detected = _detect_education_level(raw)
        if detected:
            return detected
        raw_lower = raw.lower()
        if "master" in raw_lower or "maîtrise" in raw_lower or "maitrise" in raw_lower or "msc" in raw_lower or "mba" in raw_lower:
            return "master"
        if "licence" in raw_lower or "bachelor" in raw_lower or "bsc" in raw_lower:
            return "licence"
        if "doctorat" in raw_lower or "phd" in raw_lower:
            return "doctorat"
        if "bac" in raw_lower or "baccalaureat" in raw_lower:
            return "bac"
    return None


def _normalize_education_level(level: str) -> str:
    """Normalise un libellé de niveau (ex. Master 2, Maîtrise -> master)."""
    s = (level or "").strip().lower()
    if not s:
        return level or ""
    if "doctorat" in s or "phd" in s:
        return "doctorat"
    if "master" in s or "maîtrise" in s or "maitrise" in s or "msc" in s or "mba" in s or "master 2" in s or "master2" in s:
        return "master"
    if "licence" in s or "bachelor" in s or "bsc" in s:
        return "licence"
    if "ingénieur" in s or "engineer" in s:
        return "ingénieur"
    if "bac" in s or "baccalaureat" in s:
        return "bac"
    return s
