"""
Permissions spécifiques au module Tests.

`IsCorrectorToken` : authentifie un correcteur externe via un token signé
(sans compte plateforme). Le token peut être passé en query string `?token=...`
ou en header `X-Corrector-Token: ...`.

Quand la permission accepte, elle attache `request.corrector_assignment` à la
requête pour que les views puissent récupérer le périmètre du correcteur.
"""
from __future__ import annotations

import logging

from django.utils import timezone
from rest_framework.permissions import BasePermission

logger = logging.getLogger(__name__)


def extract_corrector_token(request) -> str:
    """
    Extrait le token correcteur d'une requête.

    Ordre de priorité :
      1. Header `X-Corrector-Token` (recommandé, ne fuite pas dans les logs serveur).
      2. Query string `?token=...` (pratique pour le lien email).
      3. Body POST `token` (pour les soumissions de score).
    """
    token = request.headers.get('X-Corrector-Token')
    if token:
        return token.strip()
    token = request.query_params.get('token', '')
    if token:
        return token.strip()
    if hasattr(request, 'data') and isinstance(request.data, dict):
        return (request.data.get('token') or '').strip()
    return ''


class IsCorrectorToken(BasePermission):
    """
    Autorise UNIQUEMENT les correcteurs externes (token magique).

    Effets de bord :
      - Attache `request.corrector_assignment` à la requête.
      - Met à jour `last_used_at` / `first_used_at` / `use_count` (lazy).

    Cette permission est INCOMPATIBLE avec les permissions utilisateur connecté.
    Les vues correcteur doivent désactiver l'authentification DRF par défaut
    via `authentication_classes = []` pour éviter qu'un JWT valide ne court-circuite
    la vérification du token correcteur.
    """

    message = 'Token correcteur invalide, expiré ou révoqué.'

    def has_permission(self, request, view) -> bool:
        from .models import CorrectorAssignment

        token = extract_corrector_token(request)
        if not token:
            return False

        assignment = (
            CorrectorAssignment.objects
            .filter(token=token, is_revoked=False)
            .select_related('test', 'test__job_offer', 'company')
            .first()
        )
        if not assignment:
            logger.info('Tentative correcteur avec token invalide.')
            return False
        if assignment.expires_at and assignment.expires_at < timezone.now():
            logger.info('Token correcteur expiré : %s', assignment.email)
            return False

        # Mise à jour des compteurs d'usage (lazy, best-effort)
        now = timezone.now()
        update_fields = ['last_used_at', 'use_count', 'updated_at']
        assignment.last_used_at = now
        assignment.use_count = (assignment.use_count or 0) + 1
        if not assignment.first_used_at:
            assignment.first_used_at = now
            update_fields.append('first_used_at')
        assignment.save(update_fields=list(dict.fromkeys(update_fields)))

        # Attache l'assignation à la requête pour les views
        request.corrector_assignment = assignment
        return True
