"""
Feature store interne : extraction des features à partir d'une candidature.

Alimente le modèle de scoring ML et permet la reproductibilité (features_json sauvegardé
avec MLScore). Version durcie v2 :

- Nouveau feature `cv_quality_score` (0–1) calculé depuis raw_cv_text → permet au modèle
  de ne pas pénaliser un candidat à cause d'une mauvaise extraction technique.
- Nouveau feature `profile_completeness` (0–1) : indicateur de complétude du profil.
- `_keyword_match_score` utilise désormais le matching tolérant (text_normalize v2).
- Métadonnées de confiance retournées pour traçabilité.
"""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Niveaux d'éducation ordonnés (plus l'index est élevé, plus le niveau est élevé)
EDUCATION_LEVEL_RANK = ['bac', 'licence', 'master', 'doctorat', 'phd', 'ingénieur']


def _education_level_to_numeric(level: str | None) -> int:
    """Convertit le niveau d'éducation en entier 0–5 (0 = inconnu/non reconnu)."""
    if not level or not level.strip():
        return 0
    level_lower = level.strip().lower()
    for i, label in enumerate(EDUCATION_LEVEL_RANK, start=1):
        if label in level_lower or level_lower in label:
            return i
    return 0


def _keyword_match_score(application: Any) -> float:
    """
    Score de correspondance mots-clés (0–1) : overlap entre compétences/CV et exigences de l'offre.
    Utilise screening rules keywords si présentes, sinon extraction automatique depuis toute l'offre.
    Matching tolérant (text_normalize v2) : insensible casse/accents/apostrophes + pluriels +
    stemming + synonymes + fuzzy matching.
    """
    from .jd_keywords import extract_keywords_from_job
    from .text_normalize import normalize_for_match, keyword_matches_text

    candidate = application.candidate
    job = application.job_offer
    text_candidate = ' '.join([
        str(candidate.raw_cv_text or ''),
        str(candidate.summary or ''),
        ' '.join(candidate.skills or []),
        str(candidate.current_position or ''),
    ])
    normalized_cv = normalize_for_match(text_candidate)
    keywords = []
    for rule in job.screening_rules.all().order_by('order'):
        if rule.rule_type == 'keywords':
            kw = rule.value.get('keywords') or rule.value.get('keywords_list') or []
            if isinstance(kw, str):
                kw = [k.strip() for k in kw.split(',') if k.strip()]
            keywords.extend(kw)
    if not keywords:
        keywords = extract_keywords_from_job(job, max_words=80, max_bigrams=40)
    if not keywords:
        return 0.0
    found = sum(1 for kw in keywords if kw.strip() and keyword_matches_text(kw, normalized_cv))
    return round(found / len(keywords), 2) if keywords else 0.0


def _previous_job_similarity(application: Any) -> float:
    """
    Similarité approximative entre poste actuel / expériences et intitulé de l'offre (0–1).
    Utilise le matching tolérant (fuzzy + stem) pour résister aux variantes orthographiques.
    """
    from .text_normalize import normalize_for_match, keyword_matches_text

    candidate = application.candidate
    job = application.job_offer
    title = (job.title or '').strip()
    if not title:
        return 0.0
    title_norm = normalize_for_match(title)
    title_tokens = [t for t in title_norm.split() if len(t) >= 3]
    if not title_tokens:
        return 0.0
    candidate_text = ' '.join([
        str(candidate.current_position or ''),
        ' '.join(
            (e.get('job_title') or '')
            for e in (candidate.experience or [])
            if isinstance(e, dict)
        ),
    ])
    candidate_norm = normalize_for_match(candidate_text)
    if not candidate_norm:
        return 0.0
    matched = sum(1 for t in title_tokens if keyword_matches_text(t, candidate_norm))
    ratio = matched / len(title_tokens)
    return round(min(1.0, ratio * 1.5), 2)  # léger boost si bon overlap


def _technical_score_from_criteria(application: Any) -> float:
    """
    Score technique 0–100 dérivé des critères rule-based (preselection_score ou weighted score).
    Utilisé comme feature pour le ML.
    """
    from apps.jobs.scoring_engine import compute_weighted_score
    from apps.jobs.services import _get_selection_settings

    settings = _get_selection_settings(application.job_offer)
    criteria = getattr(settings, 'criteria_json', None) or {}
    if isinstance(criteria, dict) and criteria.get('criteria'):
        result = compute_weighted_score(application, criteria)
        return round(result['total_score'], 2)
    if application.preselection_score is not None:
        return round(float(application.preselection_score), 2)
    if application.screening_score is not None:
        return round(float(application.screening_score), 2)
    return 0.0


def _cv_quality_score(application: Any) -> float:
    """
    Indicateur 0–1 de la qualité d'extraction du CV.
    Calcul heuristique basé sur le ratio lettres/caractères et la longueur du texte.
    Permet au modèle ML de ne pas pénaliser un candidat dont le CV a été mal extrait
    (OCR de mauvaise qualité, PDF scanné, etc.).

    Retourne 1.0 si pas de CV uploadé (pas de pénalité, le candidat a saisi son profil
    manuellement et c'est tout aussi valable).
    """
    raw = (getattr(application.candidate, 'raw_cv_text', None) or '').strip()
    if not raw:
        # Pas de CV → on ne pénalise pas (le profil manuel est valide).
        return 1.0
    total = len(raw)
    if total < 100:
        return 0.1  # texte beaucoup trop court, extraction probablement défaillante
    letter_ratio = sum(1 for c in raw if c.isalpha()) / total
    length_bonus = min(1.0, total / 1500)
    garbage_count = len(re.findall(r"[\ufffd\u25a1]|(\?{3,})", raw))
    garbage_penalty = max(0.0, 1.0 - (garbage_count / max(total, 1)) * 20)
    score = letter_ratio * 0.5 + length_bonus * 0.3 + garbage_penalty * 0.2
    return round(min(1.0, max(0.0, score)), 3)


def _profile_completeness(application: Any) -> float:
    """
    Indicateur 0–1 de complétude du profil candidat.
    Évalue combien de champs structurés sont renseignés : skills, expérience,
    formation, langues, résumé.

    Un profil très complet mais sans CV peut être tout aussi valable qu'un profil
    avec CV — ce signal aide le modèle à pondérer la confiance des autres features.
    """
    c = application.candidate
    signals = [
        bool(c.skills),
        bool(c.summary and c.summary.strip()),
        bool(c.experience_years and c.experience_years > 0),
        bool(c.education_level and c.education_level.strip()),
        bool(c.current_position and c.current_position.strip()),
        bool(getattr(c, 'experience', None)),
        bool(getattr(c, 'education', None)),
        bool(getattr(c, 'languages', None)),
        bool((c.raw_cv_text or '').strip()),
    ]
    return round(sum(1 for s in signals if s) / len(signals), 2)


def extract_features(application: Any) -> dict[str, float | int]:
    """
    Extrait les features d'une candidature pour le modèle ML (feature store interne).

    Clés retournées (toutes traçables dans MLScore.features_json) :

    Features cœur (v1) :
      - years_experience
      - education_level (0–5)
      - technical_score (0–100)
      - keyword_match_score (0–1)
      - previous_job_similarity (0–1)
      - semantic_similarity (0–1)

    Features v2 (safety net + traçabilité) :
      - cv_quality_score (0–1) : qualité d'extraction du CV
      - profile_completeness (0–1) : complétude du profil saisi
      - has_low_quality_cv (0|1) : flag binaire pour le modèle
    """
    from .semantic_matching import compute_semantic_similarity

    candidate = application.candidate
    years_experience = int(candidate.experience_years or 0)
    education_level = _education_level_to_numeric(candidate.education_level)
    technical_score = _technical_score_from_criteria(application)
    keyword_match_score = _keyword_match_score(application)
    previous_job_similarity = _previous_job_similarity(application)
    semantic_similarity = compute_semantic_similarity(application)
    cv_quality_score = _cv_quality_score(application)
    profile_completeness = _profile_completeness(application)

    features: dict[str, float | int] = {
        'years_experience': years_experience,
        'education_level': education_level,
        'technical_score': technical_score,
        'keyword_match_score': round(keyword_match_score, 2),
        'previous_job_similarity': previous_job_similarity,
        'semantic_similarity': round(semantic_similarity, 4),
        'cv_quality_score': cv_quality_score,
        'profile_completeness': profile_completeness,
        'has_low_quality_cv': 1 if cv_quality_score < 0.4 else 0,
    }
    logger.debug(
        "feature_engineering v2: application_id=%s features=%s",
        application.id,
        features,
    )
    return features


def needs_human_review(application: Any, features: dict | None = None) -> tuple[bool, list[str]]:
    """
    Détermine si une candidature doit être marquée pour revue manuelle plutôt qu'auto-rejetée.

    Critères (au moins UN suffit) :
      - CV mal extrait (cv_quality_score < 0.4)
      - Profil très incomplet (profile_completeness < 0.3) avec un score faible
      - Aucun keyword matché alors que le candidat a saisi des compétences

    Retourne (needs_review, raisons[]).

    À utiliser dans la chaîne de présélection : si needs_review=True, on log un warning
    et on évite de marquer le candidat REJECTED_PRESELECTION pour permettre au RH de
    réviser manuellement.
    """
    if features is None:
        features = extract_features(application)

    reasons: list[str] = []
    if features.get('cv_quality_score', 1.0) < 0.4:
        reasons.append(
            f"CV mal extrait (qualité {features.get('cv_quality_score', 0):.2f} < 0.4) — extraction défaillante, pas un défaut du candidat."
        )
    if features.get('has_low_quality_cv') == 1:
        # Déjà couvert ci-dessus, mais on garde la trace explicite
        pass
    if features.get('profile_completeness', 1.0) < 0.3:
        reasons.append(
            f"Profil candidat très incomplet ({features.get('profile_completeness', 0):.2f}) — risque de faux négatif."
        )
    # Cas : keywords nuls alors que skills saisis (preuve d'un échec de matching)
    candidate = application.candidate
    if (
        features.get('keyword_match_score', 1.0) == 0
        and getattr(candidate, 'skills', None)
        and len(candidate.skills) >= 3
    ):
        reasons.append(
            "0 keyword matché alors que le candidat a saisi ≥3 compétences — possible décalage de vocabulaire."
        )

    return (len(reasons) > 0, reasons)
