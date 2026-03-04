"""
Scoring hybride : combinaison configurable du score rule-based et du score ML.
final_score = (rule_based_score * rule_based_weight) + (ml_score * ml_weight)
Les poids sont lus depuis SelectionSettings (rule_based_weight, ml_weight).
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_hybrid_weights(selection_settings: Any) -> tuple[float, float]:
    """
    Récupère les poids depuis SelectionSettings.
    Retourne (rule_based_weight, ml_weight). Par défaut (0.6, 0.4).
    """
    if not selection_settings:
        return 0.6, 0.4
    rb = getattr(selection_settings, 'rule_based_weight', None)
    ml = getattr(selection_settings, 'ml_weight', None)
    if rb is None:
        rb = 0.6
    if ml is None:
        ml = 0.4
    # Normalisation sommaire si les deux sont renseignés
    total = float(rb) + float(ml)
    if total <= 0:
        return 0.6, 0.4
    return float(rb) / total, float(ml) / total


def compute_hybrid_score(
    rule_based_score: float,
    ml_score: float | None,
    rule_based_weight: float,
    ml_weight: float,
) -> float:
    """
    Calcule le score hybride.
    Si ml_score est None, retourne rule_based_score (équivalent à 100% rule-based).
    """
    if ml_score is None:
        return round(rule_based_score, 2)
    total = rule_based_weight + ml_weight
    if total <= 0:
        return round(rule_based_score, 2)
    score = (rule_based_score * rule_based_weight + ml_score * ml_weight) / total
    return round(score, 2)
