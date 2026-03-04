"""
Middleware générique pour logger l'adresse IP des requêtes.

Utilisable pour tracer les sessions de tests techniques (anti-triche basique).
"""
from __future__ import annotations

import logging
from typing import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class RequestIPLoggingMiddleware:
    """
    Ajoute request.client_ip et logge l'IP + path.

    À utiliser en combinaison avec les vues de tests techniques pour éventuellement
    stocker l'IP dans CandidateTestResult.client_ip.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR')
        )
        request.client_ip = ip  # type: ignore[attr-defined]
        logger.debug('Request from IP %s on %s', ip, request.path)
        response = self.get_response(request)
        return response

