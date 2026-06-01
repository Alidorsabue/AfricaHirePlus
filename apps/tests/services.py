"""
Services métier du module Tests : correction QCM, scoring intègre, rapports,
helpers anti-triche et audit.

Durcissement v2 (P2 / P6) :
  - Bug QCM_MULTI corrigé : pénalité pour mauvaises réponses cochées
    (ratio = max(0, (good - wrong) / total_correct)).
  - Tolérance numérique configurable par question (Question.numeric_tolerance).
  - `pending_review_points` calculés et stockés sur CandidateTestResult.
  - `is_passed` évalué automatiquement via `passing_score`.
  - `recompute_test_total_score()` : synchronise Test.total_score.
  - Suppression du double parcours des questions (perf).
  - Bulk Answer (perf P6).
  - `manual_review_answer()` + audit log P6.
  - Shuffle / pool questions P5.
"""
from __future__ import annotations

import logging
import random
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Tuple

from django.db import transaction
from django.utils import timezone

from apps.applications.models import Application
from apps.tests.models import (
    Answer,
    CandidateTestResult,
    CorrectorAssignment,
    Question,
    Test,
    TestAuditLog,
)

logger = logging.getLogger(__name__)


# Tolérance numérique par défaut si Question.numeric_tolerance n'est pas défini.
DEFAULT_NUMERIC_TOLERANCE = Decimal('0.01')  # ±1 %


# ---------------------------------------------------------------------------
# Constantes : familles de types
# ---------------------------------------------------------------------------
QCM_SINGLE_TYPES = frozenset({
    Question.QuestionType.QCM_SINGLE,
    Question.QuestionType.SINGLE_CHOICE,
})
QCM_MULTI_TYPES = frozenset({
    Question.QuestionType.QCM_MULTI,
    Question.QuestionType.MULTIPLE_CHOICE,
})
TRUE_FALSE_TYPES = frozenset({
    Question.QuestionType.TRUE_FALSE,
    Question.QuestionType.BOOLEAN,
})
NUMERIC_TYPES = frozenset({
    Question.QuestionType.NUMERIC,
    Question.QuestionType.NUMBER,
})
OPEN_TEXT_TYPES = frozenset({
    Question.QuestionType.OPEN_TEXT,
    Question.QuestionType.TEXT,
    Question.QuestionType.FILE_UPLOAD,
    Question.QuestionType.CODE,
})


# ---------------------------------------------------------------------------
# Helpers de normalisation
# ---------------------------------------------------------------------------
def _normalize_answer(value: Any):
    """Normalise une réponse pour comparaison (lowercase, strip, sort si liste)."""
    if value is None:
        return None
    if isinstance(value, list):
        return sorted(str(x).strip().lower() for x in value)
    return str(value).strip().lower()


def _get_correct_ids(question: Question) -> List[str]:
    """
    Retourne la liste triée des ids de réponses correctes (pour QCM).
    Priorité : `correct_answer` JSON, puis options[i].correct=True (legacy).
    """
    if question.correct_answer is not None:
        ca = question.correct_answer
        if isinstance(ca, list):
            return sorted(str(x).strip().lower() for x in ca)
        return [str(ca).strip().lower()]
    ids: List[str] = []
    for opt in (question.options or []):
        if isinstance(opt, dict) and opt.get('correct'):
            oid = opt.get('id')
            if oid is not None:
                ids.append(str(oid).strip().lower())
    return sorted(ids)


# ---------------------------------------------------------------------------
# P2 — Notation d'une question (avec correction du bug QCM_MULTI sur-coché)
# ---------------------------------------------------------------------------
def grade_question(
    question: Question, user_answer: Any
) -> Tuple[Decimal, Decimal, Dict[str, Any]]:
    """
    Note une question et retourne (points_obtenus, points_max, meta).

    `meta` contient au minimum :
      - is_correct (bool|None) : None si pending_manual_review
      - pending_manual_review (bool)

    Règles de scoring (P2 — corrigées) :
      - QCM single : tout ou rien.
      - QCM multi : ratio = max(0, (bonnes_cochées - mauvaises_cochées) / nb_bonnes).
        Empêche un candidat de tout cocher pour obtenir 100 %.
      - Vrai/Faux : tout ou rien.
      - Numérique : tolérance configurable (Question.numeric_tolerance).
      - Open text / Code / File upload : 0 + pending_manual_review=True.
    """
    points_max = Decimal(question.points or 1)
    meta: Dict[str, Any] = {
        'is_correct': False,
        'pending_manual_review': False,
    }

    if user_answer is None:
        return Decimal('0'), points_max, meta

    qtype = question.question_type
    correct_answer = question.correct_answer

    # --- QCM single ---
    if qtype in QCM_SINGLE_TYPES:
        correct_ids = _get_correct_ids(question)
        if not correct_ids:
            return Decimal('0'), points_max, meta
        answer_norm = _normalize_answer(user_answer)
        if isinstance(answer_norm, str):
            answer_norm = [answer_norm]
        if sorted(answer_norm or []) == correct_ids:
            meta['is_correct'] = True
            return points_max, points_max, meta
        return Decimal('0'), points_max, meta

    # --- QCM multi : ratio AVEC pénalité pour mauvaises réponses (FIX P2) ---
    if qtype in QCM_MULTI_TYPES:
        correct_ids = _get_correct_ids(question)
        if not correct_ids:
            return Decimal('0'), points_max, meta
        answer_norm = _normalize_answer(user_answer) or []
        if isinstance(answer_norm, str):
            answer_norm = [answer_norm]
        chosen_set = set(answer_norm)
        correct_set = set(correct_ids)
        if chosen_set == correct_set:
            meta['is_correct'] = True
            return points_max, points_max, meta
        good = len(chosen_set & correct_set)
        wrong = len(chosen_set - correct_set)
        # Ratio strict avec pénalité : tout cocher ne paie plus.
        ratio = max(0.0, (good - wrong) / len(correct_set))
        if ratio <= 0:
            return Decimal('0'), points_max, meta
        pts = (points_max * Decimal(str(ratio))).quantize(Decimal('0.01'))
        return pts, points_max, meta

    # --- Vrai / Faux ---
    if qtype in TRUE_FALSE_TYPES and correct_answer is not None:
        u = str(user_answer).strip().lower() in ('1', 'true', 'yes', 'oui', 'vrai')
        c = correct_answer in (True, 'true', '1', 'yes', 'oui', 'vrai')
        if u == c:
            meta['is_correct'] = True
            return points_max, points_max, meta
        return Decimal('0'), points_max, meta

    # --- Numérique : tolérance configurable par question ---
    if qtype in NUMERIC_TYPES and correct_answer is not None:
        try:
            u = Decimal(str(user_answer).strip())
            c = Decimal(str(correct_answer))
        except (InvalidOperation, TypeError, ValueError):
            return Decimal('0'), points_max, meta
        tol_value = question.numeric_tolerance
        if tol_value is None:
            tol_pct = DEFAULT_NUMERIC_TOLERANCE
        else:
            try:
                tol_pct = Decimal(str(tol_value))
            except (InvalidOperation, TypeError, ValueError):
                tol_pct = DEFAULT_NUMERIC_TOLERANCE
        if c == 0:
            tolerance_abs = tol_pct  # si correct=0 et tol>0, on tolère |u| <= tol
        else:
            tolerance_abs = abs(c) * tol_pct
        if abs(u - c) <= tolerance_abs:
            meta['is_correct'] = True
            return points_max, points_max, meta
        return Decimal('0'), points_max, meta

    # --- Texte libre / code / file upload : review manuelle ---
    if qtype in OPEN_TEXT_TYPES:
        meta['pending_manual_review'] = True
        meta['is_correct'] = None
        return Decimal('0'), points_max, meta

    # Type inconnu — 0 par défaut.
    logger.warning("grade_question: type non géré '%s' (question id=%s)", qtype, question.id)
    return Decimal('0'), points_max, meta


def grade_test_answers(
    test: Test, answers: dict
) -> Tuple[Decimal, Decimal, Decimal, Dict[int, Dict[str, Any]], Dict[str, Any]]:
    """
    Corrige toutes les réponses pour un test en un seul parcours.

    Retourne :
      - total_score
      - total_max
      - pending_review_points : points encore à attribuer manuellement
      - details_par_question
      - aggregates : { sections: {...}, competencies: {...} }

    Notes perf (P6) :
      - select_related('section') pour éviter le N+1 sur q.section.title.
      - Un seul parcours questions (vs deux dans la v1).
    """
    questions = test.questions.all().select_related('section').order_by('order', 'id')

    total_score = Decimal('0')
    total_max = Decimal('0')
    pending = Decimal('0')
    details: Dict[int, Dict[str, Any]] = {}
    sections: Dict[str, Dict[str, Any]] = {}
    competencies: Dict[str, Dict[str, Any]] = {}

    for q in questions:
        # Lookup tolérant : answers[id] ou answers[str(id)] ou answers[f'question_{id}']
        user_ans = _lookup_answer(answers, q.id)
        pts, max_pts, meta = grade_question(q, user_ans)
        total_score += pts
        total_max += max_pts
        if meta.get('pending_manual_review'):
            pending += max_pts

        section_title = (q.section.title if q.section_id and q.section else '') or q.section_title or ''
        comp_tags = q.competencies or []

        details[q.id] = {
            'points': float(pts),
            'max': float(max_pts),
            'is_correct': meta.get('is_correct'),
            'pending_manual_review': bool(meta.get('pending_manual_review')),
            'section': section_title,
            'competencies': comp_tags,
        }

        if section_title:
            sec = sections.setdefault(
                section_title,
                {'title': section_title, 'score': Decimal('0'), 'max_score': Decimal('0')},
            )
            sec['score'] += pts
            sec['max_score'] += max_pts

        for tag in comp_tags:
            tag_str = str(tag)
            comp = competencies.setdefault(
                tag_str,
                {'name': tag_str, 'score': Decimal('0'), 'max_score': Decimal('0')},
            )
            comp['score'] += pts
            comp['max_score'] += max_pts

    aggregates = {
        'sections': {
            name: {
                'title': v['title'],
                'score': float(v['score']),
                'max_score': float(v['max_score']),
            }
            for name, v in sections.items()
        },
        'competencies': {
            name: {
                'name': v['name'],
                'score': float(v['score']),
                'max_score': float(v['max_score']),
            }
            for name, v in competencies.items()
        },
    }
    return total_score, total_max, pending, details, aggregates


def _lookup_answer(answers: dict, qid: int) -> Any:
    """Récupère la réponse pour qid quel que soit le format de clé fourni."""
    if qid in answers:
        return answers[qid]
    sqid = str(qid)
    if sqid in answers:
        return answers[sqid]
    legacy = f'question_{qid}'
    if legacy in answers:
        return answers[legacy]
    return None


def build_test_report(test: Test, answers: dict) -> Dict[str, Any]:
    """Génère un rapport détaillé JSON pour un test."""
    score, max_score, pending, details, aggregates = grade_test_answers(test, answers)
    return {
        'score_total': float(score),
        'max_score': float(max_score),
        'pending_review_points': float(pending),
        'sections': aggregates['sections'],
        'competencies': aggregates['competencies'],
        'questions': details,
    }


# ---------------------------------------------------------------------------
# Soumission + sauvegarde de la session
# ---------------------------------------------------------------------------
@transaction.atomic
def submit_test_result(
    application: Application,
    test: Test,
    answers: dict,
    *,
    auto_complete: bool = True,
    client_ip: str | None = None,
) -> CandidateTestResult:
    """
    Enregistre les réponses, corrige le QCM, calcule le score et met à jour le résultat.

    - Calcule pending_review_points (P2)
    - Évalue is_passed via passing_score (P2)
    - Bulk Answer.update_or_create (P6)
    - Audit log (P6)
    """
    total_score, max_score, pending_points, details, _aggregates = grade_test_answers(test, answers)

    result, _ = CandidateTestResult.objects.get_or_create(
        application=application,
        test=test,
        defaults={
            'status': CandidateTestResult.Status.PENDING,
            'answers': {},
        },
    )
    old_status = result.status
    result.answers = answers
    result.score = total_score
    result.max_score = max_score
    result.pending_review_points = pending_points

    if test.passing_score is not None and max_score > 0:
        # On considère "passed" si score atteint passing_score MÊME en ignorant
        # les points en attente (la barre est franchissable sans attendre la
        # review manuelle).
        result.is_passed = total_score >= Decimal(test.passing_score)
    else:
        result.is_passed = None

    if auto_complete:
        result.status = CandidateTestResult.Status.SCORED
        result.submitted_at = timezone.now()
        result.is_completed = True
        if not result.started_at:
            result.started_at = timezone.now()

    if client_ip and not result.client_ip:
        result.client_ip = client_ip
    if client_ip:
        result.last_seen_ip = client_ip

    update_fields = [
        'answers', 'score', 'max_score', 'pending_review_points',
        'is_passed', 'last_seen_ip', 'updated_at',
    ]
    if auto_complete:
        update_fields.extend(['status', 'submitted_at', 'is_completed', 'started_at'])
    if client_ip and not CandidateTestResult.objects.filter(pk=result.pk, client_ip__isnull=False).exists():
        update_fields.append('client_ip')
    # Dé-dup pour éviter erreur Django sur doublons d'update_fields
    update_fields = list(dict.fromkeys(update_fields))
    result.save(update_fields=update_fields)

    # ----- Persistance des Answer en bulk (P6) -----
    questions = list(test.questions.all().select_related('section').order_by('order', 'id'))
    existing = {a.question_id: a for a in result.answer_rows.all()}
    to_create: List[Answer] = []
    to_update: List[Answer] = []
    for q in questions:
        user_ans = _lookup_answer(answers, q.id)
        d = details.get(q.id, {})
        pts = Decimal(str(d.get('points', 0)))
        is_correct = d.get('is_correct')
        pending = bool(d.get('pending_manual_review'))
        ans = existing.get(q.id)
        if ans:
            ans.response = user_ans
            ans.score_obtained = pts
            ans.is_correct = is_correct if not pending else None
            ans.pending_manual_review = pending
            to_update.append(ans)
        else:
            to_create.append(
                Answer(
                    session=result,
                    question=q,
                    response=user_ans,
                    score_obtained=pts,
                    is_correct=is_correct if not pending else None,
                    pending_manual_review=pending,
                )
            )
    if to_create:
        Answer.objects.bulk_create(to_create)
    if to_update:
        Answer.objects.bulk_update(
            to_update,
            fields=['response', 'score_obtained', 'is_correct', 'pending_manual_review', 'updated_at'],
        )

    # Audit log : changement de statut
    if old_status != result.status:
        TestAuditLog.objects.create(
            session=result,
            action=TestAuditLog.Action.STATUS_CHANGE,
            old_value={'status': old_status},
            new_value={'status': result.status},
            reason='Soumission automatique par le candidat.',
            client_ip=client_ip,
        )

    return result


# ---------------------------------------------------------------------------
# P2 — Recalcul du total_score d'un Test
# ---------------------------------------------------------------------------
def recompute_test_total_score(test: Test) -> Decimal:
    """
    Met à jour Test.total_score = somme des points des questions.
    À appeler après création/édition de questions (déjà branché dans le serializer).
    """
    total = (
        test.questions.all().aggregate(s=models_sum('points'))['s'] or 0
    )
    test.total_score = Decimal(total)
    test.save(update_fields=['total_score', 'updated_at'])
    return test.total_score


def models_sum(field: str):
    """Helper pour aggregate(Sum)."""
    from django.db.models import Sum
    return Sum(field)


# ---------------------------------------------------------------------------
# P5 — Ordre des questions (shuffle / pool)
# ---------------------------------------------------------------------------
def determine_question_order(
    test: Test, result: CandidateTestResult
) -> List[int]:
    """
    Détermine l'ordre des questions présentées à un candidat.

    - Si test.questions_per_session défini : tire N questions au hasard.
    - Si test.shuffle_questions : mélange l'ordre.
    - Sinon : ordre standard (order, id).

    Le seed est dérivé de result.id pour que l'ordre soit STABLE entre les
    rechargements (refresh F5 ne donne pas un nouvel ordre).
    """
    qs = list(test.questions.all().values_list('id', flat=True).order_by('order', 'id'))
    if not qs:
        return []
    rng = random.Random(result.id)
    if test.questions_per_session and test.questions_per_session < len(qs):
        qs = rng.sample(qs, test.questions_per_session)
    elif test.shuffle_questions:
        rng.shuffle(qs)
    return qs


def get_questions_for_session(
    test: Test, result: CandidateTestResult
) -> List[Question]:
    """
    Retourne les Question dans l'ordre demandé pour la session.
    Mémorise l'ordre sur result.question_order pour cohérence multi-requêtes.
    """
    if not result.question_order:
        ordered_ids = determine_question_order(test, result)
        result.question_order = ordered_ids
        result.save(update_fields=['question_order', 'updated_at'])
    else:
        ordered_ids = result.question_order
    by_id = {q.id: q for q in test.questions.all().select_related('section')}
    return [by_id[i] for i in ordered_ids if i in by_id]


# ---------------------------------------------------------------------------
# P4 — Expiration auto des sessions abandonnées
# ---------------------------------------------------------------------------
def expire_session_if_needed(result: CandidateTestResult) -> bool:
    """
    Marque la session EXPIRED si le timer global est dépassé.
    Retourne True si la session a été expirée par cet appel.
    """
    if result.is_finalized:
        return False
    duration = result.test.duration_minutes
    if not duration or not result.started_at:
        return False
    from datetime import timedelta
    deadline = result.started_at + timedelta(minutes=duration)
    if timezone.now() <= deadline:
        return False
    old_status = result.status
    result.status = CandidateTestResult.Status.EXPIRED
    result.is_completed = True
    if not result.submitted_at:
        result.submitted_at = timezone.now()
    result.save(update_fields=['status', 'is_completed', 'submitted_at', 'updated_at'])
    TestAuditLog.objects.create(
        session=result,
        action=TestAuditLog.Action.STATUS_CHANGE,
        old_value={'status': old_status},
        new_value={'status': result.status},
        reason='Expiration automatique (timer dépassé).',
    )
    return True


# ---------------------------------------------------------------------------
# P6 / P8 — Review manuelle d'une réponse (recruteur OU correcteur externe)
# ---------------------------------------------------------------------------
@transaction.atomic
def manual_review_answer(
    answer: Answer,
    *,
    score_obtained: Decimal | float | int,
    is_correct: bool | None,
    actor: Any | None = None,
    corrector: 'CorrectorAssignment | None' = None,
    reason: str = '',
    client_ip: str | None = None,
) -> Answer:
    """
    Met à jour le score d'une réponse — utilisable par :
      - un recruteur (passer `actor=user`),
      - un correcteur externe (passer `corrector=assignment`).

    Fonctionne pour TOUS les types de question, y compris les réponses
    automatiquement corrigées (QCM, true/false, numérique). Permet à un
    correcteur d'overrider une notation automatique manifestement injuste
    (réponse alternative valide, énoncé ambigu, etc.).

    Effets :
      - Met à jour `Answer.score_obtained`, `is_correct`, `pending_manual_review=False`.
      - Recalcule le score total de la session à partir des `Answer` (source
        de vérité, plus du JSON `answers`).
      - Met à jour `pending_review_points` et `is_passed` de la session.
      - Trace dans `TestAuditLog` (MANUAL_REVIEW si recruteur,
        CORRECTOR_REVIEW si correcteur).
    """
    points_max = Decimal(answer.question.points or 1)
    new_score = Decimal(str(score_obtained))
    if new_score < 0:
        new_score = Decimal('0')
    if new_score > points_max:
        new_score = points_max

    old_score = answer.score_obtained
    old_correct = answer.is_correct
    was_pending = answer.pending_manual_review

    answer.score_obtained = new_score
    answer.is_correct = is_correct
    answer.pending_manual_review = False
    answer.save(update_fields=['score_obtained', 'is_correct', 'pending_manual_review', 'updated_at'])

    # Recalcul du total de la session à partir des Answer (source de vérité)
    session = answer.session
    agg = (
        session.answer_rows.aggregate(s=models_sum('score_obtained'))['s']
        or Decimal('0')
    )
    session.score = Decimal(str(agg))
    session.pending_review_points = (
        session.answer_rows.filter(pending_manual_review=True)
        .aggregate(s=models_sum('question__points'))['s']
        or Decimal('0')
    )
    if session.test.passing_score is not None and session.max_score:
        session.is_passed = session.score >= Decimal(session.test.passing_score)
    session.save(update_fields=['score', 'pending_review_points', 'is_passed', 'updated_at'])

    # Choix de l'action selon le type d'acteur
    if corrector is not None:
        action = TestAuditLog.Action.CORRECTOR_REVIEW
    elif was_pending:
        action = TestAuditLog.Action.MANUAL_REVIEW
    else:
        action = TestAuditLog.Action.SCORE_OVERRIDE

    TestAuditLog.objects.create(
        session=session,
        answer=answer,
        action=action,
        actor=actor,
        corrector=corrector,
        old_value={
            'score_obtained': float(old_score) if old_score is not None else None,
            'is_correct': old_correct,
            'was_pending_review': was_pending,
        },
        new_value={'score_obtained': float(new_score), 'is_correct': is_correct},
        reason=reason,
        client_ip=client_ip,
    )
    return answer


# ---------------------------------------------------------------------------
# P8 — Display code anonymisé pour les correcteurs externes
# ---------------------------------------------------------------------------
def ensure_display_code(result: CandidateTestResult) -> str:
    """
    Garantit que `result.display_code` est défini (pour l'anonymisation
    correcteur). Génère un code de 8 chars hex préfixé 'C-' (ex. 'C-A3F9B2C1'),
    unique au sein du test, avec retry en cas de collision.

    Idempotent : si le code existe déjà, le retourne tel quel.
    """
    if result.display_code:
        return result.display_code
    test_id = result.test_id
    for _ in range(20):
        candidate = f'C-{secrets.token_hex(4).upper()}'
        if not CandidateTestResult.objects.filter(
            test_id=test_id, display_code=candidate,
        ).exists():
            result.display_code = candidate
            result.save(update_fields=['display_code', 'updated_at'])
            return candidate
    # Probabilité quasi nulle (16^8 = 4 milliards) — fallback ultime
    result.display_code = f'C-{secrets.token_hex(8).upper()}'
    result.save(update_fields=['display_code', 'updated_at'])
    return result.display_code


# ---------------------------------------------------------------------------
# P8 — Assignation d'un correcteur externe
# ---------------------------------------------------------------------------
@transaction.atomic
def assign_corrector(
    test: Test,
    email: str,
    *,
    assigned_by: Any,
    full_name: str = '',
    assigned_application_ids: Iterable[int] | None = None,
    expires_in_days: int | None = 30,
    client_ip: str | None = None,
) -> CorrectorAssignment:
    """
    Crée (ou re-active) une assignation correcteur pour un test.

    Politique :
      - 1 assignation par (test, email). Si elle existe et est révoquée,
        on la réactive et on regénère un nouveau token.
      - Si `assigned_application_ids` est None : `all_candidates=True` (voit tout).
      - Si `assigned_application_ids` est une liste (même vide) : restreint à
        ces Applications uniquement. Les Applications doivent appartenir à
        l'offre du test (filtrage de sécurité).
      - `expires_in_days` : durée de validité du token (None = pas d'expiration).

    Renvoie l'assignation (créée ou réactivée). Le caller envoie ensuite
    l'email via `apps.emails.services.send_corrector_invitation`.
    """
    email = (email or '').strip().lower()
    if not email:
        raise ValueError("Email du correcteur requis.")

    expires_at = None
    if expires_in_days:
        expires_at = timezone.now() + timedelta(days=int(expires_in_days))

    assignment, created = CorrectorAssignment.objects.get_or_create(
        test=test, email=email,
        defaults={
            'company': test.company,
            'full_name': full_name or '',
            'assigned_by': assigned_by,
            'expires_at': expires_at,
            'all_candidates': assigned_application_ids is None,
        },
    )
    if not created:
        # Réactivation + rotation du token (sécurité : un email déjà utilisé
        # ne doit pas garder l'ancien token compromis).
        from .models import _generate_corrector_token
        assignment.is_revoked = False
        assignment.revoked_at = None
        assignment.revoked_by = None
        assignment.expires_at = expires_at
        assignment.token = _generate_corrector_token()
        assignment.full_name = full_name or assignment.full_name
        assignment.assigned_by = assigned_by
        assignment.all_candidates = assigned_application_ids is None
        assignment.save()

    # M2M : applications explicitement attribuées
    if assigned_application_ids is not None:
        # Filtrer pour sécurité : ne garder que les Apps de l'offre du test
        valid_apps = Application.objects.filter(
            pk__in=list(assigned_application_ids),
            job_offer_id=test.job_offer_id,
        ) if test.job_offer_id else Application.objects.none()
        assignment.assigned_applications.set(valid_apps)
    else:
        assignment.assigned_applications.clear()

    # Audit log — on rattache à la première session disponible si possible
    sample_session = (
        CandidateTestResult.objects.filter(test=test).order_by('id').first()
    )
    if sample_session:
        TestAuditLog.objects.create(
            session=sample_session,
            action=TestAuditLog.Action.CORRECTOR_ASSIGNED,
            actor=assigned_by,
            new_value={
                'corrector_email': email,
                'all_candidates': assignment.all_candidates,
                'assigned_count': assignment.assigned_applications.count(),
                'expires_at': expires_at.isoformat() if expires_at else None,
            },
            reason=f'Correcteur {email} assigné au test "{test.title}".',
            client_ip=client_ip,
        )
    return assignment


def revoke_corrector(
    assignment: CorrectorAssignment,
    *,
    revoked_by: Any,
    reason: str = '',
    client_ip: str | None = None,
) -> CorrectorAssignment:
    """Révoque un correcteur (le token devient invalide immédiatement)."""
    if assignment.is_revoked:
        return assignment
    assignment.is_revoked = True
    assignment.revoked_at = timezone.now()
    assignment.revoked_by = revoked_by
    assignment.save(update_fields=['is_revoked', 'revoked_at', 'revoked_by', 'updated_at'])

    sample_session = (
        CandidateTestResult.objects.filter(test=assignment.test).order_by('id').first()
    )
    if sample_session:
        TestAuditLog.objects.create(
            session=sample_session,
            action=TestAuditLog.Action.CORRECTOR_REVOKED,
            actor=revoked_by,
            corrector=assignment,
            new_value={'corrector_email': assignment.email},
            reason=reason or f'Correcteur {assignment.email} révoqué.',
            client_ip=client_ip,
        )
    return assignment


def get_visible_sessions_for_corrector(
    assignment: CorrectorAssignment,
) -> 'Iterable[CandidateTestResult]':
    """
    Retourne le queryset des `CandidateTestResult` visibles par ce correcteur.

    - Toujours filtré au test de l'assignation.
    - Si `all_candidates=False` : restreint aux Applications listées dans
      `assigned_applications`.
    - Toujours filtré aux sessions ayant été soumises (SCORED ou SUBMITTED)
      ou expirées (EXPIRED). Les sessions PENDING / IN_PROGRESS ne sont
      pas montrées (rien à corriger).
    """
    qs = CandidateTestResult.objects.filter(
        test=assignment.test,
        status__in=[
            CandidateTestResult.Status.SCORED,
            CandidateTestResult.Status.SUBMITTED,
            CandidateTestResult.Status.EXPIRED,
        ],
    ).select_related('test', 'application')
    if not assignment.all_candidates:
        qs = qs.filter(application__in=assignment.assigned_applications.all())
    return qs
