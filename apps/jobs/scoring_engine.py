"""
Moteur de scoring pondéré pour présélection et sélection (ATS).

Critères configurables par offre (criteria_json), opérateurs extensibles, critères obligatoires.
Structure criteria_json : {"criteria": [{"field", "operator", "value", "weight", "type"?(mandatory)}]}.
La somme des weights doit être <= 100. Score final normalisé sur 100.
Prêt pour extension ML (features, modèles) et audit RH (logs détaillés).
"""
import logging
from typing import Any

from apps.applications.models import Application

logger = logging.getLogger(__name__)

# Alias champ candidat (ex: years_experience -> experience_years)
FIELD_ALIASES = {
    'years_experience': 'experience_years',
}

# Opérateurs supportés : =, <=, <, >=, >, equals, contains, in
SUPPORTED_OPERATORS = frozenset({'=', '<=', '<', '>=', '>', 'equals', 'contains', 'in'})


def _get_value(application: Application, field: str) -> Any:
    """
    Résout la valeur d'un critère depuis la candidature.
    Cherche sur le candidat puis sur l'application (pour champs futurs type technical_test_score).
    """
    raw = field.strip()
    name = FIELD_ALIASES.get(raw, raw)
    candidate = application.candidate
    # Candidat
    if hasattr(candidate, name):
        return getattr(candidate, name, None)
    # Application (ex: technical_test_score, selection_score...)
    if hasattr(application, name):
        return getattr(application, name, None)
    return None


def _coerce_number(value: Any) -> float | int | None:
    """Convertit en nombre pour comparaisons numériques."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _evaluate_operator(actual: Any, operator: str, expected: Any) -> bool:
    """
    Évalue (actual operator expected).
    Gère =, <=, <, >=, >, equals, contains, in.
    """
    op = (operator or '').strip().lower()
    if op in ('=', 'equals'):
        if actual is None and expected is None:
            return True
        if actual is None:
            return False
        if isinstance(expected, list):
            return actual in expected
        return actual == expected
    if op in ('<=', '<', '>=', '>'):
        na = _coerce_number(actual)
        ne = _coerce_number(expected)
        if na is None or ne is None:
            return False
        if op == '<=':
            return na <= ne
        if op == '<':
            return na < ne
        if op == '>=':
            return na >= ne
        if op == '>':
            return na > ne
    if op == 'contains':
        if actual is None:
            return False
        text = str(actual).lower()
        needle = str(expected).lower() if expected is not None else ''
        return needle in text
    if op == 'in':
        if expected is None:
            return False
        if not isinstance(expected, list):
            expected = [expected]
        return actual in expected
    logger.warning("scoring_engine: opérateur non supporté %r, critère ignoré", operator)
    return False


def evaluate_criterion(application: Application, criterion: dict) -> bool:
    """
    Évalue un critère sur une candidature.
    criterion: { "field", "operator", "value", "weight", "type" (optionnel) }
    """
    field = criterion.get('field')
    operator = criterion.get('operator')
    value = criterion.get('value')
    if not field or operator is None:
        logger.debug("scoring_engine: critère ignoré (field/operator manquant)")
        return False
    actual = _get_value(application, field)
    return _evaluate_operator(actual, operator, value)


def validate_criteria_json(criteria_json: dict | None) -> None:
    """
    Valide la structure et la somme des poids (<= 100).
    Lève ValueError en cas d'erreur.
    """
    if not criteria_json:
        return
    if not isinstance(criteria_json, dict):
        raise ValueError("criteria_json doit être un objet avec une clé 'criteria' (liste).")
    criteria = criteria_json.get('criteria')
    if criteria is None:
        return
    if not isinstance(criteria, list):
        raise ValueError("criteria_json.criteria doit être une liste.")
    total_weight = 0
    for i, c in enumerate(criteria):
        if not isinstance(c, dict):
            raise ValueError(f"criteria[{i}] doit être un objet (field, operator, value, weight).")
        field = c.get('field')
        operator = c.get('operator')
        if not field or operator is None:
            raise ValueError(f"criteria[{i}]: field et operator sont requis.")
        op = c.get('operator')
        if op is not None and str(op).strip().lower() not in SUPPORTED_OPERATORS:
            raise ValueError(f"criteria[{i}]: opérateur non supporté (attendu: {', '.join(sorted(SUPPORTED_OPERATORS))}).")
        w = c.get('weight', 0)
        try:
            w = float(w)
        except (TypeError, ValueError):
            raise ValueError(f"criteria[{i}]: weight doit être un nombre.")
        if w < 0:
            raise ValueError(f"criteria[{i}]: weight ne peut pas être négatif.")
        total_weight += w
    if total_weight > 100:
        raise ValueError(f"La somme des poids des critères ne doit pas dépasser 100 (actuel: {total_weight}).")


def compute_weighted_score(
    application: Application,
    criteria_json: dict | None,
) -> dict:
    """
    Calcule le score pondéré et les détails pour une candidature.

    - Pour chaque critère : si condition respectée, score += weight ; sinon 0.
    - Si type "mandatory" et condition non respectée : score = 0 immédiatement.
    - Score final = somme des weights validés, normalisé sur 100 (si somme des weights < 100,
      le score reste la somme ; sinon on ne dépasse pas 100).

    Retourne:
        {
            "total_score": float (0-100),
            "details": [ {"criterion": str, "passed": bool, "weight_awarded": float}, ... ]
        }
    """
    result = {"total_score": 0.0, "details": []}
    if not criteria_json or not isinstance(criteria_json, dict):
        return result
    criteria = criteria_json.get('criteria')
    if not criteria or not isinstance(criteria, list):
        return result

    try:
        validate_criteria_json(criteria_json)
    except ValueError as e:
        logger.warning("scoring_engine: criteria_json invalide pour application %s: %s", application.id, e)
        return result

    total_possible = 0.0
    earned = 0.0
    for c in criteria:
        field = c.get('field', '')
        weight = float(c.get('weight', 0))
        is_mandatory = c.get('type') == 'mandatory'
        total_possible += weight
        passed = evaluate_criterion(application, c)
        detail = {
            "criterion": field,
            "passed": passed,
            "weight_awarded": weight if passed else 0.0,
        }
        result["details"].append(detail)
        # Audit RH : log par critère (niveau DEBUG)
        logger.debug(
            "scoring_engine: application_id=%s criterion=%s passed=%s weight_awarded=%.1f",
            application.id,
            field,
            passed,
            detail["weight_awarded"],
        )
        if is_mandatory and not passed:
            logger.info(
                "scoring_engine: critère obligatoire non respecté application_id=%s criterion=%s → score=0",
                application.id,
                field,
            )
            result["total_score"] = 0.0
            return result
        if passed:
            earned += weight

    # Normalisation sur 100 : si total_possible > 0, score = (earned / total_possible) * 100
    if total_possible > 0:
        result["total_score"] = round((earned / total_possible) * 100.0, 2)
    else:
        result["total_score"] = 0.0

    logger.info(
        "scoring_engine: application_id=%s total_score=%.2f earned=%.2f total_possible=%.2f (audit RH)",
        application.id,
        result["total_score"],
        earned,
        total_possible,
    )
    return result
