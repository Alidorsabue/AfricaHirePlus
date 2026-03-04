"""
Inference : prédiction du score ML à partir des features.
Modèle fictif au départ ; à brancher sur un vrai modèle après training.
"""
import logging
from typing import Any

from .feature_engineering import extract_features
from .model_registry import get_current_model_version, load_model

logger = logging.getLogger(__name__)


def predict_score(application: Any, model_version: str | None = None) -> tuple[float, float, dict[str, Any] | None]:
    """
    Prédit le score ML pour une candidature.

    - Extrait les features via extract_features(application).
    - Applique le modèle (stub : combinaison linéaire simple des features).
    - Retourne (predicted_score, confidence_score, ml_explanation_json).

    predicted_score : 0–100
    confidence_score : 0–1 (pour stub fixe à 0.5)
    ml_explanation_json : dict pour future intégration SHAP (placeholder).
    """
    features = extract_features(application)
    version = model_version or get_current_model_version()
    load_model(version)  # no-op en stub

    # Stub : score = combinaison linéaire simple (à remplacer par vrai modèle)
    # Poids arbitraires pour démo ; le training pipeline apprendra les vrais poids
    # semantic_similarity = analyse sémantique (TF-IDF ou embeddings) pour matching automatique
    weight_exp = 2.0
    weight_edu = 5.0
    weight_tech = 0.5
    weight_kw = 25.0
    weight_sim = 15.0
    weight_semantic = 30.0  # matching sémantique offre/candidat
    raw = (
        min(features.get('years_experience', 0) * weight_exp, 20)
        + (features.get('education_level', 0) or 0) * weight_edu
        + (features.get('technical_score', 0) or 0) * weight_tech / 100.0 * 30
        + (features.get('keyword_match_score', 0) or 0) * weight_kw
        + (features.get('previous_job_similarity', 0) or 0) * weight_sim
        + (features.get('semantic_similarity', 0) or 0) * weight_semantic
    )
    # Normaliser sur 0–100
    predicted_score = round(min(100.0, max(0.0, raw)), 2)
    confidence_score = 0.5  # stub

    explanation = {
        'model_version': version,
        'feature_contributions': {
            k: float(v) if isinstance(v, (int, float)) else v
            for k, v in features.items()
        },
        'placeholder': 'Remplacer par sortie SHAP / feature importance après entraînement.',
    }

    logger.info(
        "inference: application_id=%s model_version=%s predicted_score=%.2f confidence=%.2f",
        application.id,
        version,
        predicted_score,
        confidence_score,
    )
    return predicted_score, confidence_score, explanation
