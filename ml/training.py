"""
Training pipeline : entraînement du modèle de scoring (structure prête pour ML réel).
Pour l'instant pas d'entraînement (modèle stub) ; à connecter à des données labellisées plus tard.
"""
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Répertoire des artefacts (modèles sauvegardés) — à configurer selon l'environnement
DEFAULT_ARTIFACTS_DIR = Path(__file__).resolve().parent / 'artifacts'


def prepare_training_data(job_offer_ids: list[int] | None = None) -> Any:
    """
    Prépare le dataset d'entraînement à partir des candidatures (et éventuellement des outcomes).
    À implémenter : requête Application + labels (hired, shortlisted, etc.).
    Retourne X (features), y (target) au format attendu par le modèle.
    """
    logger.info("training: prepare_training_data job_offer_ids=%s (stub)", job_offer_ids)
    return None  # stub


def train_model(
    X: Any = None,
    y: Any = None,
    artifact_path: Path | str | None = None,
    version: str | None = None,
) -> str:
    """
    Lance l'entraînement du modèle et enregistre l'artefact.
    Retourne la version du modèle enregistrée.
    """
    path = artifact_path or DEFAULT_ARTIFACTS_DIR
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    ver = version or 'stub'
    logger.info("training: train_model artifact_path=%s version=%s (stub)", path, ver)
    return ver


def run_training_pipeline(
    job_offer_ids: list[int] | None = None,
    output_version: str | None = None,
) -> dict[str, Any]:
    """
    Pipeline complet : préparation des données, entraînement, enregistrement.
    Retourne un résumé (version, métriques placeholder, chemin artefact).
    """
    data = prepare_training_data(job_offer_ids=job_offer_ids)
    version = train_model(X=None, y=None, version=output_version)
    return {
        'model_version': version,
        'metrics': {},  # À remplir après entraînement réel
        'artifacts_dir': str(DEFAULT_ARTIFACTS_DIR),
    }
