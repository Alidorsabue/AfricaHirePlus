"""
Score ATS « JD vs CV » : correspondance entre l'offre complète et le profil/candidat.
Utilisé en fallback quand l'offre n'a pas de règles de screening (pour alignement avec
une analyse type ChatGPT / ATS qui compare tout le JD au CV).
"""
from typing import Any


def compute_ats_match_score(application: Any) -> float:
    """
    Calcule un score 0–100 de correspondance offre/candidat à partir des mots-clés
    (extraits de toute l'offre) et de la similarité sémantique.
    N'utilise pas les règles de screening ni les critères pondérés.
    """
    from ml.feature_engineering import _keyword_match_score
    from ml.semantic_matching import compute_semantic_similarity

    keyword_score = _keyword_match_score(application)
    semantic_score = compute_semantic_similarity(application)
    # Pondération type ATS : 50 % mots-clés, 50 % sémantique
    raw = keyword_score * 50.0 + semantic_score * 50.0
    return round(min(100.0, max(0.0, raw)), 2)


def _education_rank(level: str) -> int:
    """Rang du niveau d'études (plus = mieux)."""
    if not level or not str(level).strip():
        return -1
    s = str(level).strip().lower()
    for syn, can in [("maîtrise", "master"), ("maitrise", "master"), ("bachelor", "licence"), ("bsc", "licence"), ("msc", "master"), ("mba", "master")]:
        if syn in s:
            s = can
            break
    order = ["bac", "licence", "master", "doctorat", "phd", "ingénieur"]
    for i, l in enumerate(order):
        if l in s or (s and s in l):
            return i
    return -1


def get_ats_breakdown(application: Any) -> dict:
    """
    Retourne le détail du calcul ATS par catégorie : mots-clés, niveau d'études,
    expérience, localisation, personnalisé, etc. Matching insensible à la casse/accents/apostrophes.
    """
    from ml.jd_keywords import extract_keywords_from_job
    from ml.semantic_matching import compute_semantic_similarity
    from ml.text_normalize import normalize_for_match, keyword_matches_text

    from apps.candidates.utils import get_candidate_experience_years, get_candidate_education_level

    candidate = application.candidate
    job = application.job_offer
    text_candidate = " ".join([
        str(getattr(candidate, "raw_cv_text", None) or ""),
        str(candidate.summary or ""),
        " ".join(candidate.skills or []),
        str(candidate.current_position or ""),
        str(candidate.education_level or ""),
        str(candidate.location or ""),
        str(candidate.country or ""),
    ])
    # Inclure les formations/expériences du formulaire pour le matching texte
    for e in (getattr(candidate, "education", None) or []):
        if isinstance(e, dict):
            text_candidate += " " + " ".join(str(v) for v in (e.values() or []))
    for e in (getattr(candidate, "experience", None) or []):
        if isinstance(e, dict):
            text_candidate += " " + " ".join(str(v) for v in (e.values() or []))
    normalized_cv = normalize_for_match(text_candidate)

    rules = getattr(job, "screening_rules", None) or []
    rules_list = list(rules.all().order_by("order")) if hasattr(rules, "all") else []

    def keywords_from_rules(rule_type: str) -> list:
        out = []
        for rule in rules_list:
            if getattr(rule, "rule_type", None) != rule_type:
                continue
            val = getattr(rule, "value", None) or {}
            if rule_type == "keywords" or rule_type == "custom":
                kw = val.get("keywords") or val.get("keywords_list") or []
                if isinstance(kw, str):
                    kw = [k.strip() for k in kw.split(",") if k.strip()]
                out.extend(kw)
            elif rule_type == "location":
                loc = val.get("location") or val.get("city") or val.get("cities")
                if isinstance(loc, list):
                    out.extend(str(x).strip() for x in loc if x)
                elif loc:
                    out.append(str(loc).strip())
        return out

    # Mots-clés : règles keywords ou extraction auto
    keywords_mots_cles = keywords_from_rules("keywords")
    if not keywords_mots_cles:
        keywords_mots_cles = extract_keywords_from_job(job, max_words=80, max_bigrams=40)

    found_mots_cles = []
    missing_mots_cles = []
    for kw in keywords_mots_cles:
        k = (kw or "").strip()
        if not k:
            continue
        if keyword_matches_text(k, normalized_cv):
            found_mots_cles.append(kw)
        else:
            missing_mots_cles.append(kw)

    score_mots_cles = round(len(found_mots_cles) / len(keywords_mots_cles), 4) if keywords_mots_cles else 0.0

    # Compétences : même source que mots-clés pour l’affichage par rubrique
    competences_found = list(found_mots_cles)
    competences_missing = list(missing_mots_cles)[:80]

    # Niveau d'études (formulaire + CV, ex. Master 2 en cours)
    niveau_required = None
    niveau_candidate = get_candidate_education_level(candidate)
    niveau_match = None
    for rule in rules_list:
        if getattr(rule, "rule_type", None) == "education_level":
            val = getattr(rule, "value", None) or {}
            niveau_required = (val.get("level") or val.get("education_level") or "").strip() or None
            break
    if niveau_required or niveau_candidate:
        r_rank = _education_rank(niveau_required or "")
        c_rank = _education_rank(niveau_candidate or "")
        niveau_match = c_rank >= r_rank and c_rank >= 0 if r_rank >= 0 else None

    # Expérience (formulaire : somme des postes par dates début/fin, ou CV)
    exp_required = None
    exp_candidate = get_candidate_experience_years(candidate)
    exp_match = None
    for rule in rules_list:
        if getattr(rule, "rule_type", None) == "min_experience":
            val = getattr(rule, "value", None) or {}
            try:
                exp_required = int(val.get("years") or val.get("min_years") or 0)
            except (TypeError, ValueError):
                exp_required = 0
            break
    if exp_required is not None:
        exp_match = exp_candidate >= exp_required

    # Localisation
    loc_required = keywords_from_rules("location")
    loc_candidate = " ".join(filter(None, [str(candidate.location or ""), str(candidate.country or "")]))
    loc_normalized = normalize_for_match(loc_candidate)
    loc_match = None
    if loc_required:
        loc_match = any(
            keyword_matches_text(loc, loc_normalized) or keyword_matches_text(loc, normalized_cv)
            for loc in loc_required if loc
        )

    # Personnalisé (custom)
    custom_kw = keywords_from_rules("custom")
    personnalise_found = [k for k in custom_kw if k.strip() and keyword_matches_text(k, normalized_cv)]
    personnalise_missing = [k for k in custom_kw if k.strip() and not keyword_matches_text(k, normalized_cv)]

    # Langue : pas de règle dédiée, section vide ou réutiliser des mots-clés si besoin
    langue_found = []
    langue_missing = []

    semantic_score = round(compute_semantic_similarity(application), 4)
    raw = score_mots_cles * 50.0 + semantic_score * 50.0
    total_score = round(min(100.0, max(0.0, raw)), 2)

    categories = {
        "mots_cles": {
            "keywords_found": found_mots_cles,
            "keywords_missing": missing_mots_cles[:80],
            "score": score_mots_cles,
        },
        "niveau_etudes": {
            "required": niveau_required,
            "candidate": niveau_candidate,
            "match": niveau_match,
        },
        "experience": {
            "required_years": exp_required,
            "candidate_years": exp_candidate,
            "match": exp_match,
        },
        "langue": {
            "keywords_found": langue_found,
            "keywords_missing": langue_missing,
        },
        "competences": {
            "keywords_found": competences_found,
            "keywords_missing": competences_missing,
        },
        "localisation": {
            "required": loc_required[:20] if loc_required else None,
            "candidate": loc_candidate.strip() or None,
            "match": loc_match,
        },
        "personnalise": {
            "keywords_found": personnalise_found,
            "keywords_missing": personnalise_missing[:40],
        },
    }

    return {
        "categories": categories,
        "keyword_score": score_mots_cles,
        "semantic_score": semantic_score,
        "total_score": total_score,
        # Rétrocompatibilité
        "keywords_from_job": keywords_mots_cles[:120],
        "keywords_found": found_mots_cles,
        "keywords_missing": missing_mots_cles[:80],
    }
