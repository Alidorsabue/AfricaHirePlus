"""
Inference v2 : prédiction du score ML à partir des features.

Améliorations clés vs v1 :
- Plafond d'expérience supprimé : 15 ans ne valent plus l'équivalent de 10 ans.
- Confiance calculée à partir de la qualité d'extraction CV + complétude profil.
- Pondération des features par leur fiabilité (cv_quality_score, profile_completeness).
- Boost de récupération : un candidat avec excellents critères techniques mais matching
  faible (à cause d'un vocabulaire différent) n'est plus pénalisé à zéro.
- Explication enrichie (contributions des features individuelles) pour traçabilité RH.

Le modèle reste un stub linéaire (à remplacer par un vrai modèle entraîné via training.py),
mais les heuristiques sont désormais bien plus robustes face aux failles d'extraction.
"""
import logging
from typing import Any

from .feature_engineering import extract_features
from .model_registry import get_current_model_version, load_model

logger = logging.getLogger(__name__)


# Poids des features dans le score brut (avant calibration 0–100)
# Total des max attendus ≈ 100 pour garder une lecture intuitive
_FEATURE_WEIGHTS: dict[str, float] = {
    "years_experience": 1.5,        # 0–~30 → 0–~45 (sans plafond)
    "education_level": 4.0,         # 0–5 → 0–20
    "technical_score": 0.2,         # 0–100 → 0–20
    "keyword_match_score": 15.0,    # 0–1 → 0–15
    "previous_job_similarity": 10.0, # 0–1 → 0–10
    "semantic_similarity": 20.0,    # 0–1 → 0–20
}


def _raw_score(features: dict[str, Any]) -> float:
    """Combinaison linéaire des features. Pas de plafond arbitraire sur l'expérience."""
    score = 0.0
    score += (features.get("years_experience", 0) or 0) * _FEATURE_WEIGHTS["years_experience"]
    score += (features.get("education_level", 0) or 0) * _FEATURE_WEIGHTS["education_level"]
    score += (features.get("technical_score", 0) or 0) * _FEATURE_WEIGHTS["technical_score"]
    score += (features.get("keyword_match_score", 0) or 0) * _FEATURE_WEIGHTS["keyword_match_score"]
    score += (features.get("previous_job_similarity", 0) or 0) * _FEATURE_WEIGHTS["previous_job_similarity"]
    score += (features.get("semantic_similarity", 0) or 0) * _FEATURE_WEIGHTS["semantic_similarity"]
    return score


def _recovery_boost(features: dict[str, Any]) -> float:
    """
    Boost de récupération pour les candidats pénalisés par une faille technique :
    - CV mal extrait mais critères techniques solides → on remonte le score.
    - Score keyword=0 avec semantic_similarity élevée → on remonte.
    Retourne un additif 0–15 à ajouter au score brut.
    """
    boost = 0.0
    cv_quality = features.get("cv_quality_score", 1.0) or 1.0
    keyword_score = features.get("keyword_match_score", 0) or 0
    semantic = features.get("semantic_similarity", 0) or 0
    technical = features.get("technical_score", 0) or 0

    # Cas 1 : CV de mauvaise qualité mais profil structuré est bon
    if cv_quality < 0.5 and technical >= 60:
        boost += 10.0
    # Cas 2 : 0 keyword matché alors que la similarité sémantique est forte (vocabulaire différent)
    if keyword_score == 0 and semantic >= 0.5:
        boost += 8.0
    # Cas 3 : matching faible mais expérience et niveau d'études très solides
    if keyword_score < 0.2 and (features.get("years_experience", 0) or 0) >= 5 and (features.get("education_level", 0) or 0) >= 3:
        boost += 5.0
    return min(boost, 15.0)


def _compute_confidence(features: dict[str, Any]) -> float:
    """
    Confiance 0–1 dans la prédiction. Tient compte de :
    - qualité d'extraction du CV (cv_quality_score)
    - complétude du profil (profile_completeness)
    - cohérence entre features (semantic vs keyword)
    """
    cv_q = features.get("cv_quality_score", 1.0) or 1.0
    profile_c = features.get("profile_completeness", 0.5) or 0.5
    # Cohérence : si keyword et semantic divergent fortement, confiance plus faible
    keyword = features.get("keyword_match_score", 0) or 0
    semantic = features.get("semantic_similarity", 0) or 0
    consistency = 1.0 - abs(keyword - semantic) * 0.5
    consistency = max(0.0, min(1.0, consistency))
    confidence = 0.45 * cv_q + 0.35 * profile_c + 0.20 * consistency
    return round(min(1.0, max(0.0, confidence)), 2)


def predict_score(application: Any, model_version: str | None = None) -> tuple[float, float, dict[str, Any] | None]:
    """
    Prédit le score ML pour une candidature.

    Pipeline :
      1. extract_features(application) → features (v2 incluant cv_quality_score).
      2. _raw_score(features) → score brut linéaire (sans plafond arbitraire).
      3. _recovery_boost(features) → additif pour les CV mal extraits avec bon profil.
      4. _compute_confidence(features) → confiance basée sur qualité CV + complétude + cohérence.
      5. Normalisation 0–100.

    Retourne (predicted_score, confidence, explanation_dict).
    """
    features = extract_features(application)
    version = model_version or get_current_model_version()
    load_model(version)  # no-op en stub

    raw = _raw_score(features)
    boost = _recovery_boost(features)
    predicted = round(min(100.0, max(0.0, raw + boost)), 2)
    confidence = _compute_confidence(features)

    # Contributions par feature (pour audit RH et future visualisation SHAP-like)
    contributions = {}
    for key, weight in _FEATURE_WEIGHTS.items():
        val = features.get(key, 0) or 0
        contributions[key] = {
            "value": val,
            "weight": weight,
            "contribution": round(val * weight, 2),
        }

    explanation = {
        "model_version": version,
        "raw_score": round(raw, 2),
        "recovery_boost": round(boost, 2),
        "final_score": predicted,
        "feature_contributions": contributions,
        "cv_quality_score": features.get("cv_quality_score"),
        "profile_completeness": features.get("profile_completeness"),
        "low_quality_flag": features.get("has_low_quality_cv") == 1,
        "note": (
            "Stub linéaire pondéré. Remplacer par un modèle entraîné après collecte de "
            "données (training.py). Le recovery_boost protège les candidats pénalisés "
            "par une mauvaise extraction CV ou un décalage de vocabulaire."
        ),
    }

    logger.info(
        "inference v2: application_id=%s version=%s score=%.2f confidence=%.2f "
        "raw=%.2f boost=%.2f cv_quality=%.2f",
        application.id, version, predicted, confidence, raw, boost,
        features.get("cv_quality_score", 0),
    )
    return predicted, confidence, explanation
