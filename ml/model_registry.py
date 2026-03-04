"""
Registry des modèles ML : versioning et chargement.
En production, peut pointer vers un artefact (fichier, S3, MLflow, etc.).
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Version du modèle stub (remplacée par un vrai modèle après entraînement)
CURRENT_MODEL_VERSION = '20250226-stub'


def get_current_model_version() -> str:
    """Retourne la version du modèle actuellement utilisée en inference."""
    return CURRENT_MODEL_VERSION


def load_model(version: str | None = None) -> Any:
    """
    Charge le modèle pour la version donnée. Pour l'instant retourne None (stub).
    À remplacer par un vrai chargement (joblib, pickle, ONNX, etc.) ou appel à un service.
    """
    ver = version or get_current_model_version()
    logger.info("model_registry: load_model version=%s (stub)", ver)
    return None  # Pas de modèle réel pour l'instant
