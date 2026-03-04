"""
Feature store interne : extraction des features à partir d'une candidature.
Alimente le modèle de scoring ML et permet la reproductibilité (features_json sauvegardé avec MLScore).
"""
import logging
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
    Matching insensible à la casse, aux accents et aux apostrophes (ex. "Gestion d'Informations" = "gestion information").
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
    Placeholder : comparaison simple sur les mots du titre de l'offre vs current_position + experience.
    """
    candidate = application.candidate
    job = application.job_offer
    title_words = set((job.title or '').lower().split())
    if not title_words:
        return 0.0
    candidate_text = ' '.join([
        str(candidate.current_position or ''),
        ' '.join(
            (e.get('job_title') or '')
            for e in (candidate.experience or [])
            if isinstance(e, dict)
        ),
    ]).lower()
    candidate_words = set(candidate_text.split())
    overlap = len(title_words & candidate_words) / len(title_words) if title_words else 0.0
    return round(min(1.0, overlap * 2), 2)  # léger boost si bon overlap


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


def extract_features(application: Any) -> dict[str, float | int]:
    """
    Extrait les features d'une candidature pour le modèle ML (feature store interne).

    Retourne un dict avec les clés :
    - years_experience
    - education_level (entier 0–5)
    - technical_score (0–100, dérivé des règles)
    - keyword_match_score (0–1)
    - previous_job_similarity (0–1)
    - semantic_similarity (0–1, analyse sémantique offre/candidat, TF-IDF ou embeddings)

    Chaque prédiction ML enregistre ce dict dans MLScore.features_json pour traçabilité.
    """
    from .semantic_matching import compute_semantic_similarity

    candidate = application.candidate
    years_experience = int(candidate.experience_years or 0)
    education_level = _education_level_to_numeric(candidate.education_level)
    technical_score = _technical_score_from_criteria(application)
    keyword_match_score = _keyword_match_score(application)
    previous_job_similarity = _previous_job_similarity(application)
    semantic_similarity = compute_semantic_similarity(application)

    features = {
        'years_experience': years_experience,
        'education_level': education_level,
        'technical_score': technical_score,
        'keyword_match_score': round(keyword_match_score, 2),
        'previous_job_similarity': previous_job_similarity,
        'semantic_similarity': round(semantic_similarity, 4),
    }
    logger.debug(
        "feature_engineering: application_id=%s features=%s",
        application.id,
        features,
    )
    return features
