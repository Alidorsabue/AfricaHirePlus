"""
Moteur de scoring pondéré v2 — scoring graduel, matching sémantique,
catégories, confiance, audit enrichi.

Compatibilité v1 préservée :
- `validate_criteria_json` est toujours exporté (utilisé par les serializers et les tests).
- `compute_weighted_score` retourne toujours `total_score`, `details`, `mandatory_failed`.
- Le champ `details[*]` conserve `criterion`, `passed`, `weight_awarded` (clés v1) et
  ajoute `category`, `ratio`, `weight_max`, `mandatory` (enrichissements v2).
"""
import logging
from typing import Any
from difflib import SequenceMatcher

from apps.applications.models import Application

logger = logging.getLogger(__name__)

FIELD_ALIASES = {
    'years_experience': 'experience_years',
}

SUPPORTED_OPERATORS = frozenset({
    '=', '<=', '<', '>=', '>',
    'equals', 'contains', 'in',
    'range',        # NOUVEAU : {"value": [min, max]}
    'similar_to',   # NOUVEAU : matching sémantique fuzzy
    'skills_match', # NOUVEAU : matching liste de compétences
})


# ─────────────────────────────────────────────
# Helpers d'accès et de coercition
# ─────────────────────────────────────────────

def _get_value(application: Application, field: str) -> Any:
    """Lit une valeur sur l'application ou son candidat (avec alias rétro-compatibles)."""
    if not field:
        return None
    raw = field.strip()
    name = FIELD_ALIASES.get(raw, raw)
    candidate = getattr(application, 'candidate', None)
    if candidate is not None and hasattr(candidate, name):
        return getattr(candidate, name)
    if hasattr(application, name):
        return getattr(application, name)
    return None


def _coerce_number(value: Any) -> float | int | None:
    """Convertit en nombre si possible (str, Decimal, bool…). Retourne None sinon."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        return float(str(value).strip().replace(',', '.'))
    except (TypeError, ValueError):
        return None


def _evaluate_operator(actual: Any, operator: str, expected: Any) -> bool:
    """Évaluation binaire pour les opérateurs simples (=, equals, contains, in, comparaisons)."""
    op = (operator or '').strip().lower()

    if op in ('=', 'equals'):
        if actual is None:
            return False
        return str(actual).strip().lower() == str(expected).strip().lower()

    if op == 'contains':
        if actual is None:
            return False
        return str(expected).strip().lower() in str(actual).strip().lower()

    if op == 'in':
        if not isinstance(expected, (list, tuple, set)):
            return False
        actual_norm = str(actual).strip().lower() if actual is not None else ''
        return any(str(v).strip().lower() == actual_norm for v in expected)

    if op in ('>=', '>', '<=', '<'):
        na = _coerce_number(actual)
        ne = _coerce_number(expected)
        if na is None or ne is None:
            return False
        if op == '>=':
            return na >= ne
        if op == '>':
            return na > ne
        if op == '<=':
            return na <= ne
        return na < ne

    logger.warning("scoring_engine v2: opérateur non supporté %r, critère ignoré", operator)
    return False


# ─────────────────────────────────────────────
# Validation du criteria_json
# ─────────────────────────────────────────────

def validate_criteria_json(criteria_json: dict | None) -> None:
    """
    Valide la structure du criteria_json (lève ValueError sinon).
    Règles :
      - `criteria` doit être une liste (ou None/absent).
      - Chaque critère : `field` non vide, `operator` supporté, `weight` numérique >= 0.
      - Somme des poids <= 100.
    """
    if not criteria_json:
        return
    if not isinstance(criteria_json, dict):
        raise ValueError("criteria_json doit être un objet JSON.")
    criteria = criteria_json.get('criteria')
    if criteria is None:
        return
    if not isinstance(criteria, list):
        raise ValueError("criteria doit être une liste.")

    total_weight = 0.0
    for i, c in enumerate(criteria):
        if not isinstance(c, dict):
            raise ValueError(f"criteria[{i}] doit être un objet.")
        field = (c.get('field') or '').strip() if isinstance(c.get('field'), str) else c.get('field')
        if not field:
            raise ValueError(f"criteria[{i}]: champ 'field' obligatoire.")
        op = c.get('operator')
        if op is not None and str(op).strip().lower() not in SUPPORTED_OPERATORS:
            raise ValueError(
                f"criteria[{i}]: opérateur non supporté "
                f"(attendu: {', '.join(sorted(SUPPORTED_OPERATORS))})."
            )
        weight = c.get('weight', 0)
        try:
            w = float(weight)
        except (TypeError, ValueError):
            raise ValueError(f"criteria[{i}]: weight doit être numérique.")
        if w < 0:
            raise ValueError(f"criteria[{i}]: weight ne peut pas être négatif.")
        total_weight += w

    if total_weight > 100.000001:  # tolérance flottante
        raise ValueError(
            f"La somme des poids des critères doit être <= 100 (actuelle: {total_weight:g})."
        )


# ─────────────────────────────────────────────
# NOUVEAU : scoring graduel (partial credit)
# ─────────────────────────────────────────────

def _partial_score_numeric(actual: float, operator: str, expected: Any) -> float:
    """
    Retourne un ratio 0.0–1.0 pour les comparaisons numériques.
    Ex: requis >= 5 ans, candidat a 3 ans → ratio = 3/5 = 0.60
    """
    if operator in ('>=', '>'):
        if actual >= expected:
            return 1.0
        if expected > 0:
            return max(0.0, actual / expected)
    if operator in ('<=', '<'):
        if actual <= expected:
            return 1.0
        if actual > 0:
            return max(0.0, expected / actual)
    return 1.0 if actual == expected else 0.0


def _semantic_similarity(a: str, b: str) -> float:
    """Score de similarité textuelle 0.0–1.0 (insensible à la casse)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _skills_match_score(actual_skills: list | str, required_skills: list) -> float:
    """
    Compare les compétences avec tolérance sémantique.
    Retourne le ratio de compétences requises couvertes.
    Ex: requis=[Python, Django, React], candidat=[python, django] → 2/3 = 0.67
    """
    if not required_skills:
        return 1.0
    if isinstance(actual_skills, str):
        actual_skills = [s.strip() for s in actual_skills.split(',')]
    actual_lower = [s.lower() for s in (actual_skills or [])]
    matched = 0
    for req in required_skills:
        req_lower = req.lower()
        # Match exact ou similarité > 0.80
        if any(
            req_lower == act or _semantic_similarity(req_lower, act) >= 0.80
            for act in actual_lower
        ):
            matched += 1
    return matched / len(required_skills)


# ─────────────────────────────────────────────
# Évaluation avec score partiel
# ─────────────────────────────────────────────

def evaluate_criterion_with_score(application: Application, criterion: dict) -> tuple[bool, float]:
    """
    Évalue un critère et retourne (passed: bool, ratio: float 0.0–1.0).
    Le ratio permet le scoring graduel (partial credit).
    """
    field = criterion.get('field', '').strip()
    operator = criterion.get('operator', '').strip().lower()
    expected = criterion.get('value')
    partial = criterion.get('partial', True)  # scoring graduel activé par défaut

    actual = _get_value(application, field)

    # ── Opérateur range ──
    if operator == 'range':
        if not isinstance(expected, list) or len(expected) != 2:
            return False, 0.0
        na = _coerce_number(actual)
        if na is None:
            return False, 0.0
        in_range = expected[0] <= na <= expected[1]
        if in_range:
            return True, 1.0
        # Scoring graduel : distance au bord le plus proche
        if partial:
            distance = min(abs(na - expected[0]), abs(na - expected[1]))
            span = expected[1] - expected[0]
            ratio = max(0.0, 1.0 - distance / max(span, 1))
            return False, ratio
        return False, 0.0

    # ── Matching sémantique fuzzy ──
    if operator == 'similar_to':
        if actual is None:
            return False, 0.0
        ratio = _semantic_similarity(str(actual), str(expected))
        threshold = criterion.get('threshold', 0.75)
        return ratio >= threshold, ratio if partial else (1.0 if ratio >= threshold else 0.0)

    # ── Matching compétences ──
    if operator == 'skills_match':
        if not isinstance(expected, list):
            expected = [expected]
        ratio = _skills_match_score(actual, expected)
        min_ratio = criterion.get('min_match', 0.5)  # 50% des skills minimum
        return ratio >= min_ratio, ratio if partial else (1.0 if ratio >= min_ratio else 0.0)

    # ── Opérateurs numériques avec scoring graduel ──
    if operator in ('>=', '>', '<=', '<'):
        na = _coerce_number(actual)
        ne = _coerce_number(expected)
        if na is None or ne is None:
            return False, 0.0
        passed = _evaluate_operator(actual, operator, expected)
        if passed:
            return True, 1.0
        if partial:
            ratio = _partial_score_numeric(na, operator, ne)
            return False, ratio
        return False, 0.0

    # ── Opérateurs standards (=, contains, in, equals) ──
    passed = _evaluate_operator(actual, operator, expected)
    return passed, 1.0 if passed else 0.0


def compute_weighted_score(
    application: Application,
    criteria_json: dict | None,
) -> dict:
    """
    Calcule le score pondéré avec scoring graduel, catégories et indice de confiance.

    Retourne:
    {
        "total_score": float (0–100),
        "confidence": float (0–1),   # NOUVEAU
        "categories": {...},          # NOUVEAU : score par catégorie
        "details": [...],
        "mandatory_failed": bool,
    }
    """
    result = {
        "total_score": 0.0,
        "confidence": 0.0,
        "categories": {},
        "details": [],
        "mandatory_failed": False,
    }
    if not criteria_json or not isinstance(criteria_json, dict):
        return result
    criteria = criteria_json.get('criteria', [])
    if not criteria:
        return result

    try:
        validate_criteria_json(criteria_json)
    except ValueError as e:
        logger.warning("scoring_engine v2: criteria invalide app=%s: %s", application.id, e)
        return result

    total_possible = 0.0
    earned = 0.0
    criteria_evaluated = 0

    for c in criteria:
        field = c.get('field', '')
        weight = float(c.get('weight', 0))
        category = c.get('category', 'general')  # NOUVEAU : groupement
        is_mandatory = c.get('type') == 'mandatory'
        total_possible += weight
        criteria_evaluated += 1

        passed, ratio = evaluate_criterion_with_score(application, c)
        weight_awarded = round(weight * ratio, 2)  # scoring graduel
        earned += weight_awarded

        detail = {
            "criterion": field,
            "category": category,
            "passed": passed,
            "ratio": round(ratio, 3),
            "weight_awarded": weight_awarded,
            "weight_max": weight,
            "mandatory": is_mandatory,
        }
        result["details"].append(detail)

        # Agrégation par catégorie
        if category not in result["categories"]:
            result["categories"][category] = {"earned": 0.0, "possible": 0.0}
        result["categories"][category]["earned"] += weight_awarded
        result["categories"][category]["possible"] += weight

        if is_mandatory and not passed:
            logger.info("scoring_engine v2: mandatory fail app=%s criterion=%s", application.id, field)
            result["total_score"] = 0.0
            result["mandatory_failed"] = True
            return result

    if total_possible > 0:
        result["total_score"] = round((earned / total_possible) * 100.0, 2)
        # Indice de confiance : basé sur le nb de critères évalués vs attendus
        result["confidence"] = round(min(1.0, criteria_evaluated / max(len(criteria), 1)), 2)
        # Score par catégorie normalisé
        for cat, vals in result["categories"].items():
            p = vals["possible"]
            result["categories"][cat]["score"] = round((vals["earned"] / p * 100) if p > 0 else 0, 2)

    logger.info(
        "scoring_engine v2: app=%s score=%.2f confidence=%.2f earned=%.2f/%.2f",
        application.id, result["total_score"], result["confidence"], earned, total_possible,
    )
    return result