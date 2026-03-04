"""
Services : correction automatique QCM, calcul score, sauvegarde résultats
et génération de rapports détaillés (score par section / compétence).
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Tuple

from django.utils import timezone

from apps.tests.models import Test, Question, CandidateTestResult, Answer
from apps.applications.models import Application


def _normalize_answer(value: Any):
    """Normalise une réponse pour comparaison."""
    if value is None:
        return None
    if isinstance(value, list):
        return sorted(str(x).strip().lower() for x in value)
    return str(value).strip().lower()


def _get_correct_ids(question: Question):
    """
    Retourne la liste des ids de réponses correctes (pour QCM).
    Utilise d'abord correct_answer (JSON) puis les options JSON (legacy).
    """
    if question.correct_answer is not None:
        ca = question.correct_answer
        if isinstance(ca, list):
            return sorted(str(x).strip().lower() for x in ca)
        return [str(ca).strip().lower()]
    # Fallback: options avec correct=True
    ids = []
    for opt in question.options or []:
        if isinstance(opt, dict) and opt.get('correct'):
            oid = opt.get('id')
            if oid is not None:
                ids.append(str(oid).strip().lower())
    return sorted(ids) if ids else []


def grade_question(question: Question, user_answer: Any) -> Tuple[Decimal, Decimal, Dict[str, Any]]:
    """
    Corrige une question.

    Retourne (points_obtenus, points_max, meta) où meta contient au moins :
    - is_correct: bool
    - pending_manual_review: bool (OPEN_TEXT)
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

    qcm_single_types = {
        Question.QuestionType.QCM_SINGLE,
        Question.QuestionType.SINGLE_CHOICE,
    }
    qcm_multi_types = {
        Question.QuestionType.QCM_MULTI,
        Question.QuestionType.MULTIPLE_CHOICE,
    }
    true_false_types = {
        Question.QuestionType.TRUE_FALSE,
        Question.QuestionType.BOOLEAN,
    }
    numeric_types = {
        Question.QuestionType.NUMERIC,
        Question.QuestionType.NUMBER,
    }
    open_text_types = {
        Question.QuestionType.OPEN_TEXT,
        Question.QuestionType.TEXT,
        Question.QuestionType.FILE_UPLOAD,
        Question.QuestionType.CODE,
    }

    # QCM simple / multiple
    if qtype in qcm_single_types or qtype in qcm_multi_types:
        correct_ids = _get_correct_ids(question)
        if not correct_ids:
            return Decimal('0'), points_max, meta
        answer_norm = _normalize_answer(user_answer)
        if answer_norm is None:
            return Decimal('0'), points_max, meta
        if isinstance(answer_norm, str):
            answer_norm = [answer_norm]
        answer_norm = sorted(answer_norm)
        if answer_norm == correct_ids:
            meta['is_correct'] = True
            return points_max, points_max, meta
        # Score proportionnel pour QCM multiple (sans pénalité négative)
        if qtype in qcm_multi_types and len(correct_ids) > 0:
            good = sum(1 for a in answer_norm if a in correct_ids)
            if good == 0:
                return Decimal('0'), points_max, meta
            ratio = max(0, good / len(correct_ids))
            pts = (points_max * Decimal(str(ratio))).quantize(Decimal('0.01'))
            return pts, points_max, meta
        return Decimal('0'), points_max, meta

    # Vrai/Faux
    if qtype in true_false_types and correct_answer is not None:
        u = str(user_answer).strip().lower() in ('1', 'true', 'yes', 'oui', 'vrai')
        c = correct_answer in (True, 'true', '1', 'yes', 'oui', 'vrai')
        if u == c:
            meta['is_correct'] = True
            return points_max, points_max, meta
        return Decimal('0'), points_max, meta

    # Numérique (tolérance ±1%)
    if qtype in numeric_types and correct_answer is not None:
        try:
            u = Decimal(str(user_answer))
            c = Decimal(str(correct_answer))
            if c == 0:
                # Si la bonne réponse est 0, on exige l'égalité stricte
                if u == c:
                    meta['is_correct'] = True
                    return points_max, points_max, meta
                return Decimal('0'), points_max, meta
            diff = abs(u - c)
            tolerance = abs(c) * Decimal('0.01')  # ±1 %
            if diff <= tolerance:
                meta['is_correct'] = True
                return points_max, points_max, meta
            return Decimal('0'), points_max, meta
        except (InvalidOperation, TypeError, ValueError):
            return Decimal('0'), points_max, meta

    # Texte libre : pas de correction auto, review manuelle
    if qtype in open_text_types:
        meta['pending_manual_review'] = True
        return Decimal('0'), points_max, meta

    # Autres types non pris en charge : 0 point
    return Decimal('0'), points_max, meta


def grade_test_answers(test: Test, answers: dict) -> Tuple[Decimal, Decimal, Dict[int, Dict[str, Any]], Dict[str, Any]]:
    """
    Corrige toutes les réponses pour un test.
    answers = { question_id: answer } ou { "question_<id>": answer }

    Retourne :
    - score total
    - score max
    - details_par_question: {question_id: {points, max, is_correct, pending_manual_review, section, competencies}}
    - aggregates: {
        "sections": {section_key: {"title": ..., "score": ..., "max_score": ...}},
        "competencies": {tag: {"score": ..., "max_score": ...}},
      }
    """
    questions = test.questions.all().order_by('order', 'id')
    total_score = Decimal('0')
    total_max = Decimal('0')
    details: Dict[int, Dict[str, Any]] = {}
    sections: Dict[str, Dict[str, Any]] = {}
    competencies: Dict[str, Dict[str, Any]] = {}

    for q in questions:
        key = q.id
        if key not in answers and f'question_{key}' in answers:
            key = f'question_{key}'
        user_ans = answers.get(key) if key in answers else answers.get(str(q.id))
        pts, max_pts, meta = grade_question(q, user_ans)
        total_score += pts
        total_max += max_pts

        section_title = (q.section.title if getattr(q, 'section', None) else '') or q.section_title or ''
        comp_tags = q.competencies or []

        details[q.id] = {
            'points': float(pts),
            'max': float(max_pts),
            'is_correct': bool(meta.get('is_correct')),
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

    return total_score, total_max, details, aggregates


def build_test_report(test: Test, answers: dict) -> Dict[str, Any]:
    """
    Génère un rapport détaillé JSON pour un test :
    - score_total / max_score
    - score par section
    - score par compétence
    - détail par question
    """
    score, max_score, details, aggregates = grade_test_answers(test, answers)
    report: Dict[str, Any] = {
        'score_total': float(score),
        'max_score': float(max_score),
        'sections': aggregates['sections'],
        'competencies': aggregates['competencies'],
        'questions': details,
    }
    return report


def submit_test_result(
    application: Application,
    test: Test,
    answers: dict,
    *,
    auto_complete: bool = True,
) -> CandidateTestResult:
    """
    Enregistre les réponses, corrige le QCM, calcule le score et sauvegarde le résultat.
    Crée ou met à jour le CandidateTestResult.

    Les OPEN_TEXT sont incluses dans le rapport avec pending_manual_review=True et score=0.
    """
    score, max_score, _, _ = grade_test_answers(test, answers)
    result, _ = CandidateTestResult.objects.get_or_create(
        application=application,
        test=test,
        defaults={
            'status': CandidateTestResult.Status.PENDING,
            'answers': {},
        },
    )
    result.answers = answers
    result.score = score
    result.max_score = max_score
    if auto_complete:
        result.status = CandidateTestResult.Status.SCORED
        result.submitted_at = timezone.now()
        result.is_completed = True
        if not result.started_at:
            result.started_at = timezone.now()
    result.save(
        update_fields=[
            'answers',
            'score',
            'max_score',
            'status',
            'submitted_at',
            'updated_at',
            'is_completed',
        ]
        if auto_complete
        else ['answers', 'updated_at'],
    )

    # Met à jour les objets Answer (une ligne par question)
    questions = test.questions.all().order_by('order', 'id')
    for q in questions:
        key = q.id
        if key not in answers and f'question_{key}' in answers:
            key = f'question_{key}'
        user_ans = answers.get(key) if key in answers else answers.get(str(q.id))
        pts, _, _ = grade_question(q, user_ans)
        Answer.objects.update_or_create(
            session=result,
            question=q,
            defaults={
                'response': user_ans,
                'score_obtained': pts,
            },
        )

    return result

