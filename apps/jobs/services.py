"""
Services métier : offres d'emploi, clôture, scoring, présélection, sélection, KPI, export Excel.
"""
import logging
from decimal import Decimal
from django.db.models import Avg, Count, Max, Min, Q
from django.utils import timezone

from apps.jobs.models import JobOffer, PreselectionSettings, ScreeningRule, SelectionSettings
from apps.jobs.scoring_engine import compute_weighted_score
from apps.applications.models import Application
from apps.candidates.models import Candidate

logger = logging.getLogger(__name__)


def _get_preselection_settings(job_offer: JobOffer) -> PreselectionSettings | None:
    """Retourne les paramètres de présélection de l'offre (ou None)."""
    return getattr(job_offer, 'preselection_settings', None) or PreselectionSettings.objects.filter(
        job_offer=job_offer
    ).first()


def _get_preselection_threshold(job_offer: JobOffer) -> float:
    """Seuil de présélection pour l'offre. Par défaut 60% si non défini."""
    settings = _get_preselection_settings(job_offer)
    if settings is not None and getattr(settings, 'score_threshold', None) is not None:
        return float(settings.score_threshold)
    return 60.0


def _get_selection_settings(job_offer: JobOffer) -> SelectionSettings | None:
    """Retourne les paramètres de sélection de l'offre (ou None)."""
    return getattr(job_offer, 'selection_settings', None) or SelectionSettings.objects.filter(
        job_offer=job_offer
    ).first()


def close_offer(job_offer: JobOffer) -> JobOffer:
    """Clôture une offre : status=closed et closed_at=now (sans effet si déjà clôturée)."""
    if job_offer.status == JobOffer.Status.CLOSED:
        return job_offer
    job_offer.status = JobOffer.Status.CLOSED
    job_offer.closed_at = timezone.now()
    job_offer.save(update_fields=['status', 'closed_at', 'updated_at'])
    return job_offer


def compute_screening_score(application: Application) -> Decimal | None:
    """
    Calcule le score de screening pondéré selon les règles de l'offre.
    Règles : KEYWORDS (mots-clés CV), MIN_EXPERIENCE, EDUCATION_LEVEL, etc.
    Retourne le score total (somme pondérée des règles validées) ou None si aucune règle.
    """
    job = application.job_offer
    candidate = application.candidate
    rules = job.screening_rules.all().order_by('order')
    if not rules.exists():
        return None

    total_weight = sum(r.weight for r in rules)
    earned = Decimal('0')
    # Texte sur lequel matcher les mots-clés (normalisé : casse, accents, apostrophes)
    from ml.text_normalize import normalize_for_match, keyword_matches_text
    text_to_match_raw = ' '.join([
        str(candidate.raw_cv_text or ''),
        str(candidate.summary or ''),
        ' '.join(candidate.skills or []),
        str(candidate.education_level or ''),
        str(candidate.current_position or ''),
    ])
    text_to_match_normalized = normalize_for_match(text_to_match_raw)

    for rule in rules:
        score_rule = Decimal('0')
        if rule.rule_type == ScreeningRule.RuleType.KEYWORDS:
            keywords = rule.value.get('keywords') or rule.value.get('keywords_list') or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(',') if k.strip()]
            if keywords:
                found = sum(1 for kw in keywords if kw.strip() and keyword_matches_text(kw, text_to_match_normalized))
                score_rule = rule.weight * (Decimal(found) / len(keywords))
            else:
                score_rule = Decimal('0')

        elif rule.rule_type == ScreeningRule.RuleType.SKILLS:
            keywords = rule.value.get('keywords') or rule.value.get('skills') or rule.value.get('keywords_list') or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(',') if k.strip()]
            if keywords:
                skills_text = normalize_for_match(' '.join(candidate.skills or []))
                found = sum(1 for kw in keywords if kw.strip() and keyword_matches_text(kw, skills_text))
                score_rule = rule.weight * (Decimal(found) / len(keywords))
            else:
                score_rule = Decimal('0')

        elif rule.rule_type == ScreeningRule.RuleType.LANGUAGE:
            keywords = rule.value.get('keywords') or rule.value.get('languages') or rule.value.get('keywords_list') or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(',') if k.strip()]
            if keywords:
                cand_langs = []
                for item in (candidate.languages or []):
                    if isinstance(item, dict) and item.get('language'):
                        cand_langs.append(str(item.get('language', '')).strip())
                    elif isinstance(item, str):
                        cand_langs.append(item.strip())
                langs_text = normalize_for_match(' '.join(cand_langs) + ' ' + text_to_match_raw)
                found = sum(1 for kw in keywords if kw.strip() and keyword_matches_text(kw, langs_text))
                score_rule = rule.weight * (Decimal(found) / len(keywords))
            else:
                score_rule = Decimal('0')

        elif rule.rule_type == ScreeningRule.RuleType.MIN_EXPERIENCE:
            min_years = rule.value.get('years') or rule.value.get('min_years') or 0
            try:
                min_years = int(min_years)
            except (TypeError, ValueError):
                min_years = 0
            from apps.candidates.utils import get_candidate_experience_years
            cand_years = get_candidate_experience_years(candidate)
            if cand_years >= min_years:
                score_rule = rule.weight
            elif min_years > 0:
                score_rule = rule.weight * (Decimal(cand_years) / min_years)

        elif rule.rule_type == ScreeningRule.RuleType.EDUCATION_LEVEL:
            required = (rule.value.get('level') or rule.value.get('education_level') or '').lower()
            from apps.candidates.utils import get_candidate_education_level
            cand_level_raw = get_candidate_education_level(candidate)
            cand_level = (cand_level_raw or '').lower()
            # Hiérarchie : bac < licence < master < doctorat. Un niveau supérieur ou égal satisfait l'exigence (ex. Licence demandé → Master/Doctorat acceptés).
            levels_order = ['bac', 'licence', 'master', 'doctorat', 'phd', 'ingénieur']

            def _normalize_education(s):
                if not s:
                    return s
                s = s.strip().lower()
                for synonym, canonical in [('maîtrise', 'master'), ('maitrise', 'master'), ('bachelor', 'licence'), ('bsc', 'licence'), ('msc', 'master'), ('mba', 'master')]:
                    if synonym in s:
                        return canonical
                return s

            def level_rank(s):
                norm = _normalize_education(s)
                for i, l in enumerate(levels_order):
                    if l in norm or norm and l in s:
                        return i
                return -1

            if required and cand_level:
                if required in cand_level or cand_level in required:
                    score_rule = rule.weight
                elif level_rank(cand_level) >= level_rank(required) and level_rank(cand_level) >= 0:
                    score_rule = rule.weight  # Niveau candidat >= niveau demandé (ex. Master quand Licence demandé)
                else:
                    score_rule = rule.weight * Decimal('0.5')
            elif not required:
                score_rule = rule.weight

        else:
            # CUSTOM / LOCATION : pondération partielle si critère vague
            score_rule = rule.weight * Decimal('0.5')

        earned += score_rule

    if total_weight <= 0:
        return None
    # Score en pourcentage (0–100), arrondi à 2 décimales
    score = (earned / total_weight) * Decimal('100')
    return score.quantize(Decimal('0.01'))


def run_auto_preselection(application: Application, threshold: float | None = None) -> bool:
    """
    Lance le scoring sur une candidature et passe en PRESELECTED si score >= seuil.
    Seuil : paramètre threshold si fourni, sinon seuil de l'offre (PreselectionSettings), sinon 60%.
    Si aucune règle de screening : utilise le score ATS JD vs CV (fallback).
    Retourne True si le statut a été mis à jour.
    """
    if threshold is None:
        threshold = _get_preselection_threshold(application.job_offer)
    score = compute_screening_score(application)
    if score is None:
        try:
            from ml.ats_score import compute_ats_match_score
            score_f = compute_ats_match_score(application)
            application.screening_score = None
            application.preselection_score = score_f
            application.save(update_fields=['screening_score', 'preselection_score', 'updated_at'])
            if score_f >= threshold:
                application.status = Application.Status.PRESELECTED
                application.save(update_fields=['status', 'updated_at'])
                return True
            application.status = Application.Status.REJECTED_PRESELECTION
            application.save(update_fields=['status', 'updated_at'])
            return False
        except Exception as e:
            logger.warning("run_auto_preselection: fallback ATS failed application_id=%s: %s", application.id, e)
            return False
    application.screening_score = score
    application.preselection_score = float(score)
    application.save(update_fields=['screening_score', 'preselection_score', 'updated_at'])
    if float(score) >= threshold:
        application.status = Application.Status.PRESELECTED
        application.save(update_fields=['status', 'updated_at'])
        return True
    application.status = Application.Status.REJECTED_PRESELECTION
    application.save(update_fields=['status', 'updated_at'])
    return False


def compute_preselection(application: Application) -> float | None:
    """
    Calcule le score de présélection pour une candidature et met à jour le statut (Présélectionné / Refusé)
    selon score >= seuil. Si PreselectionSettings.criteria_json contient des critères pondérés, utilise
    compute_weighted_score. Sinon fallback compute_screening_score ou score ATS. Seuil par défaut 60%.
    Le statut est toujours aligné sur le score vs seuil (y compris après « Recalculer les scores » sur une offre clôturée).
    Retourne le score (float) ou None.
    """
    job = application.job_offer
    threshold = _get_preselection_threshold(job)
    settings = _get_preselection_settings(job)
    criteria = (getattr(settings, 'criteria_json', None) or {}) if settings else {}
    criteria_list = criteria.get('criteria') if isinstance(criteria, dict) else None

    if criteria_list and len(criteria_list) > 0:
        result = compute_weighted_score(application, criteria)
        score_f = result['total_score']
        application.screening_score = None
        application.preselection_score = score_f
        application.preselection_score_details = result.get('details')
    else:
        score = compute_screening_score(application)
        if score is None:
            # Fallback ATS : score JD vs CV (mots-clés extraits de l'offre + similarité sémantique)
            try:
                from ml.ats_score import compute_ats_match_score
                score_f = compute_ats_match_score(application)
                application.screening_score = None
                application.preselection_score = score_f
                application.preselection_score_details = None
                logger.info(
                    "compute_preselection: application_id=%s pas de règles → score ATS JD/CV=%.2f",
                    application.id,
                    score_f,
                )
            except Exception as e:
                logger.warning("compute_preselection: fallback ATS failed application_id=%s: %s", application.id, e)
                return None
        else:
            score_f = float(score)
            application.screening_score = score
            application.preselection_score = score_f
            application.preselection_score_details = None

    application.save(update_fields=['screening_score', 'preselection_score', 'preselection_score_details', 'updated_at'])
    # Toujours aligner le statut sur le score vs seuil (offre ouverte ou clôturée)
    if score_f >= threshold:
        application.status = Application.Status.PRESELECTED
    else:
        application.status = Application.Status.REJECTED_PRESELECTION
    application.save(update_fields=['status', 'updated_at'])
    return score_f


def refresh_preselection_scores_for_job(job_offer: JobOffer) -> int:
    """
    Recalcule le score de présélection pour toutes les candidatures de l'offre.
    Utile pour mettre à jour les scores existants avec la logique ATS (JD vs CV)
    quand l'offre n'a pas de règles ou pour resynchroniser après changement de règles.
    Retourne le nombre de candidatures mises à jour.
    """
    applications = (
        Application.objects.filter(job_offer=job_offer)
        .select_related('candidate', 'job_offer')
        .prefetch_related('job_offer__screening_rules', 'job_offer__preselection_settings')
    )
    updated = 0
    for app in applications:
        try:
            score = compute_preselection(app)
            if score is not None:
                updated += 1
        except Exception as e:
            logger.warning("refresh_preselection_scores_for_job: application_id=%s error=%s", app.id, e)
    logger.info("refresh_preselection_scores_for_job: job_id=%s updated=%d total=%d", job_offer.id, updated, applications.count())
    return updated


def _compute_score_from_selection_rules(candidate: Candidate, rules_list: list) -> float | None:
    """
    Calcule un score (0–100) à partir d'une liste de règles de sélection (dicts).
    Même logique que compute_screening_score mais pour des règles en dict (rule_type, value, weight).
    """
    if not rules_list:
        return None
    total_weight = sum(
        Decimal(str(r.get('weight', 10))) for r in rules_list
    )
    if total_weight <= 0:
        return None
    text_to_match = ' '.join([
        str(getattr(candidate, 'raw_cv_text', None) or ''),
        str(candidate.summary or ''),
        ' '.join(candidate.skills or []),
        str(candidate.education_level or ''),
        str(candidate.current_position or ''),
    ]).lower()
    earned = Decimal('0')
    # Hiérarchie niveau d'études : un niveau supérieur ou égal satisfait l'exigence (Licence demandé → Master/Doctorat OK)
    levels_order = ['bac', 'licence', 'master', 'doctorat', 'phd', 'ingénieur']

    def _normalize_edu(s):
        if not s:
            return s
        s = s.strip().lower()
        for syn, can in [('maîtrise', 'master'), ('maitrise', 'master'), ('bachelor', 'licence'), ('bsc', 'licence'), ('msc', 'master'), ('mba', 'master')]:
            if syn in s:
                return can
        return s

    def _edu_rank(s):
        norm = _normalize_edu(s)
        if not norm:
            return -1
        for i, l in enumerate(levels_order):
            if l in norm:
                return i
        return -1

    for rule in rules_list:
        rule_type = rule.get('rule_type') or 'custom'
        value = rule.get('value') or {}
        weight = Decimal(str(rule.get('weight', 10)))
        score_rule = Decimal('0')
        if rule_type == 'keywords':
            keywords = value.get('keywords') or value.get('keywords_list') or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(',') if k.strip()]
            if keywords:
                found = sum(1 for kw in keywords if kw.lower() in text_to_match)
                score_rule = weight * (Decimal(found) / len(keywords))
        elif rule_type == 'skills':
            keywords = value.get('keywords') or value.get('skills') or value.get('keywords_list') or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(',') if k.strip()]
            if keywords:
                skills_text = ' '.join(candidate.skills or []).lower()
                found = sum(1 for kw in keywords if kw.lower() in skills_text)
                score_rule = weight * (Decimal(found) / len(keywords))
        elif rule_type == 'language':
            keywords = value.get('keywords') or value.get('languages') or value.get('keywords_list') or []
            if isinstance(keywords, str):
                keywords = [k.strip() for k in keywords.split(',') if k.strip()]
            if keywords:
                cand_langs = []
                for item in (getattr(candidate, 'languages', None) or []):
                    if isinstance(item, dict) and item.get('language'):
                        cand_langs.append(str(item.get('language', '')).strip().lower())
                    elif isinstance(item, str):
                        cand_langs.append(item.strip().lower())
                langs_text = ' '.join(cand_langs) + ' ' + text_to_match
                found = sum(1 for kw in keywords if kw.lower() in langs_text)
                score_rule = weight * (Decimal(found) / len(keywords))
        elif rule_type == 'min_experience':
            min_years = value.get('years') or value.get('min_years') or 0
            try:
                min_years = int(min_years)
            except (TypeError, ValueError):
                min_years = 0
            cand_years = candidate.experience_years or 0
            if cand_years >= min_years:
                score_rule = weight
            elif min_years > 0:
                score_rule = weight * (Decimal(cand_years) / min_years)
        elif rule_type == 'education_level':
            required = (value.get('level') or value.get('education_level') or '').lower()
            cand_level = (candidate.education_level or '').lower()

            if required and cand_level:
                if required in cand_level or cand_level in required:
                    score_rule = weight
                elif _edu_rank(cand_level) >= _edu_rank(required) and _edu_rank(cand_level) >= 0:
                    score_rule = weight  # Niveau candidat >= niveau demandé
                else:
                    score_rule = weight * Decimal('0.5')
            elif not required:
                score_rule = weight
        else:
            score_rule = weight * Decimal('0.5')
        earned += score_rule

    score = (earned / total_weight) * Decimal('100')
    return float(score.quantize(Decimal('0.01')))


def _get_ml_score_for_application(application: Application) -> float | None:
    """
    Retourne le dernier score ML pour cette candidature (dernière prédiction enregistrée).
    None si pas de prédiction ou si scoring_mode ne l'utilise pas.
    """
    from apps.applications.models import MLScore
    last = MLScore.objects.filter(application=application).order_by('-created_at').first()
    return float(last.predicted_score) if last else None


def _compute_selection_score_for_application(application: Application) -> tuple[float, list | None]:
    """
    Calcule le score de sélection pour une candidature.
    Prend en compte scoring_mode (RULE_BASED / HYBRID / ML_ONLY) et coefficients configurables.
    Si SelectionSettings.criteria_json contient des critères pondérés (clé "criteria"),
    utilise le moteur compute_weighted_score. Sinon fallback preselection/screening.
    Retourne (score, details) où details est la liste des critères (pour interprétabilité) ou None.
    """
    settings = _get_selection_settings(application.job_offer)
    scoring_mode = getattr(settings, 'scoring_mode', None) or 'rule_based'

    rule_based_score = 0.0
    details = None
    criteria = getattr(settings, 'criteria_json', None) or {}
    if isinstance(criteria, dict):
        criteria_list = criteria.get('criteria')
        if criteria_list and len(criteria_list) > 0:
            result = compute_weighted_score(application, criteria)
            rule_based_score = result['total_score']
            details = result.get('details')
        else:
            rules = criteria.get('selection_rules') or []
            if isinstance(rules, list) and len(rules) > 0:
                score = _compute_score_from_selection_rules(application.candidate, rules)
                if score is not None:
                    rule_based_score = score
    if rule_based_score == 0.0 and application.preselection_score is not None:
        rule_based_score = float(application.preselection_score)
    if rule_based_score == 0.0 and application.screening_score is not None:
        rule_based_score = float(application.screening_score)

    if scoring_mode == 'ml_only':
        ml_score = _get_ml_score_for_application(application)
        if ml_score is not None:
            return round(ml_score, 2), details
        # Fallback sur rule-based si pas encore de prédiction ML
        return rule_based_score, details

    if scoring_mode == 'hybrid':
        from ml.hybrid_scoring import get_hybrid_weights, compute_hybrid_score
        rb_weight, ml_weight = get_hybrid_weights(settings)
        ml_score = _get_ml_score_for_application(application)
        final = compute_hybrid_score(rule_based_score, ml_score, rb_weight, ml_weight)
        return final, details

    return rule_based_score, details


def compute_selection(job_offer: JobOffer) -> list[Application]:
    """
    Génère la shortlist : prend les PRESELECTED (hors is_manually_adjusted pour recalcul),
    calcule selection_score, filtre par threshold, trie DESC, limite max_candidates,
    met status SHORTLISTED / REJECTED_SELECTION.
    Retourne la liste des applications shortlistées.
    """
    settings = _get_selection_settings(job_offer)
    threshold = float(settings.score_threshold) if settings else 60.0
    max_candidates = (settings.max_candidates or 0) if settings else 0

    # Candidats présélectionnés ; on recalcule le score pour ceux non manuellement ajustés
    base = Application.objects.filter(
        job_offer=job_offer,
        status=Application.Status.PRESELECTED,
    ).select_related('candidate')

    to_score = [a for a in base if not a.is_manually_adjusted]
    for app in to_score:
        score, details = _compute_selection_score_for_application(app)
        app.selection_score = score
        app.selection_score_details = details
        app.save(update_fields=['selection_score', 'selection_score_details', 'updated_at'])

    # Inclure les manuellement shortlistés (manually_added_to_shortlist) avec leur score actuel
    shortlist_candidates = list(
        base.order_by('-selection_score', '-preselection_score', 'id')
    )
    # Filtrer par seuil (sauf manually_added_to_shortlist)
    above_threshold = [
        a for a in shortlist_candidates
        if (a.selection_score or 0) >= threshold or a.manually_added_to_shortlist
    ]
    if max_candidates > 0:
        above_threshold = above_threshold[:max_candidates]

    # Marquer shortlistés vs refusés
    shortlisted_ids = {a.id for a in above_threshold}
    for app in base:
        if app.id in shortlisted_ids:
            app.status = Application.Status.SHORTLISTED
        else:
            app.status = Application.Status.REJECTED_SELECTION
        app.save(update_fields=['status', 'updated_at'])

    return list(Application.objects.filter(id__in=shortlisted_ids).order_by('-selection_score', 'id'))


def simulate_selection(job_offer: JobOffer, threshold: float, max_candidates: int) -> list[dict]:
    """
    Simule une shortlist sans modifier la base : applique le même scoring que compute_selection
    (règles de sélection, scoring_mode rule_based/hybrid/ml_only), puis filtre par seuil et max.
    Retourne une liste de dicts (application_id, candidate, preselection_score, selection_score, rank).
    """
    base = list(
        Application.objects.filter(
            job_offer=job_offer,
            status=Application.Status.PRESELECTED,
        ).select_related('candidate')
    )
    # Recalculer le score de sélection pour chaque candidat (même logique que compute_selection)
    scored = []
    for app in base:
        score, _ = _compute_selection_score_for_application(app)
        scored.append((app, score))
    # Trier par score de sélection décroissant, puis preselection_score, puis id
    scored.sort(key=lambda x: (-(x[1] or 0), -(x[0].preselection_score or 0), x[0].id))
    results = []
    for rank, (app, selection_score) in enumerate(scored, 1):
        if (selection_score or 0) < threshold and not app.manually_added_to_shortlist:
            continue
        results.append({
            'application_id': app.id,
            'candidate_id': app.candidate_id,
            'candidate_name': app.candidate.get_full_name(),
            'preselection_score': app.preselection_score,
            'selection_score': selection_score,
            'rank': len(results) + 1,
        })
        if max_candidates > 0 and len(results) >= max_candidates:
            break
    return results


def compute_kpi(job_offer: JobOffer) -> dict:
    """Calcule les KPI d'une offre (agrégations ORM)."""
    qs = Application.objects.filter(job_offer=job_offer)
    total = qs.count()
    if total == 0:
        return {
            'total_applications': 0,
            'total_preselected': 0,
            'total_shortlisted': 0,
            'rejection_rate_preselection': 0.0,
            'rejection_rate_selection': 0.0,
            'average_preselection_score': None,
            'average_selection_score': None,
            'highest_score': None,
            'lowest_score': None,
        }
    agg = qs.aggregate(
        total_preselected=Count('id', filter=Q(status=Application.Status.PRESELECTED)),
        total_shortlisted=Count('id', filter=Q(status=Application.Status.SHORTLISTED)),
        avg_preselection=Avg('preselection_score'),
        avg_selection=Avg('selection_score'),
        max_score=Max('preselection_score'),
        min_score=Min('preselection_score'),
    )
    rejected_preselection = qs.filter(status=Application.Status.REJECTED_PRESELECTION).count()
    rejected_selection = qs.filter(status=Application.Status.REJECTED_SELECTION).count()
    preselected_count = agg['total_preselected'] or 0
    shortlisted_count = agg['total_shortlisted'] or 0
    return {
        'total_applications': total,
        'total_preselected': preselected_count,
        'total_shortlisted': shortlisted_count,
        'rejection_rate_preselection': round((rejected_preselection / total) * 100, 2) if total else 0.0,
        'rejection_rate_selection': round((rejected_selection / total) * 100, 2) if total else 0.0,
        'average_preselection_score': round(agg['avg_preselection'], 2) if agg['avg_preselection'] is not None else None,
        'average_selection_score': round(agg['avg_selection'], 2) if agg['avg_selection'] is not None else None,
        'highest_score': round(agg['max_score'], 2) if agg['max_score'] is not None else None,
        'lowest_score': round(agg['min_score'], 2) if agg['min_score'] is not None else None,
    }


def generate_shortlist_xlsx(job_offer: JobOffer, recruiter_name: str = '') -> bytes:
    """
    Génère un fichier Excel de la shortlist (rang, nom candidat, scores, date, nom recruteur).
    """
    from io import BytesIO
    from openpyxl import Workbook

    shortlisted = (
        Application.objects.filter(
            job_offer=job_offer,
            status=Application.Status.SHORTLISTED,
        )
        .select_related('candidate')
        .order_by('-selection_score', '-preselection_score', 'id')
    )
    generated_at = timezone.now().strftime('%d/%m/%Y %H:%M')
    recruiter = recruiter_name or (getattr(job_offer.created_by, 'get_full_name', lambda: '')() if job_offer.created_by else '')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Shortlist'
    ws.append(['Shortlist - %s' % job_offer.title])
    ws.append(['Généré le', generated_at])
    ws.append(['Recruteur', recruiter or '-'])
    ws.append([])
    ws.append(['Rang', 'Candidat', 'Email', 'Score présélection', 'Score sélection'])
    for rank, app in enumerate(shortlisted, 1):
        prescore = round(app.preselection_score, 2) if app.preselection_score is not None else ''
        selscore = round(app.selection_score, 2) if app.selection_score is not None else ''
        ws.append([rank, app.candidate.get_full_name(), app.candidate.email or '', prescore, selscore])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
